"""本地网格账本。SQLite 与 MySQL 共用这些语句。"""
from typing import Any, Dict, List, Optional

from services.analysis.order_ledger import (
    StalePostedOrders,
    initial_status,
    may_fill_today,
    normalize_side,
    normalize_status,
    order_key,
)
from services.data.market_clock import shanghai_now

from .db_config import is_sqlite
from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database


def _incoming_orders(orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    incoming = []
    for order in orders or []:
        try:
            side = normalize_side(order.get("side") or order.get("action"))
            price = round(float(order.get("trigger_price", order.get("price"))), 3)
            shares = int(order.get("shares") or 0)
        except (TypeError, ValueError):
            continue
        if shares <= 0 or price <= 0:
            continue
        note = str(order.get("note") or "")[:255]
        rail = str(order.get("rail") or "")
        role = str(order.get("role") or "")
        incoming.append({
            "side": side,
            "price": price,
            "shares": shares,
            "note": note,
            "rail": rail,
            "role": role,
            "key": order_key(side, price, shares, rail),
        })
    return incoming


def _stale_posted(existing: List[Dict[str, Any]], incoming: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    remaining: Dict[tuple, int] = {}
    for order in incoming:
        remaining[order["key"]] = remaining.get(order["key"], 0) + 1
    stale = []
    for row in existing:
        if row["status"] != "已挂":
            continue
        key = order_key(row["side"], row["trigger_price"], row["shares"], row.get("rail") or "")
        if remaining.get(key, 0) > 0:
            remaining[key] -= 1
            continue
        stale.append(row)
    return stale


class LedgerRepository:
    def __init__(self, database: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        ensure_database(self.database)

    def _connect(self):
        return connect(self.database)

    def _ensure_rail_column(self, cursor) -> None:
        if is_sqlite():
            cursor.execute("PRAGMA table_info(grid_ledger_order)")
            names = {row["name"] for row in cursor.fetchall()}
            if "rail" not in names:
                cursor.execute("ALTER TABLE grid_ledger_order ADD COLUMN rail TEXT NOT NULL DEFAULT ''")
            return
        cursor.execute(
            """
            SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'grid_ledger_order' AND COLUMN_NAME = 'rail'
            """,
            (self.database,),
        )
        if cursor.fetchone() is None:
            cursor.execute(
                "ALTER TABLE grid_ledger_order ADD COLUMN rail VARCHAR(32) NOT NULL DEFAULT '' COMMENT '所属网格'"
            )

    def save_plan(
        self,
        etf_code: str,
        etf_name: str,
        anchor_price: float,
        base_shares: int,
        base_price: float,
        orders: List[Dict[str, Any]],
        posted_policy: Optional[str] = None,
    ) -> Dict[str, Any]:
        code = str(etf_code or "").strip()
        if not code:
            raise ValueError("账本需要 ETF 代码")
        policy = str(posted_policy or "").strip()
        if policy not in ("", "void", "keep"):
            raise ValueError("请选择作废旧已挂单，或只保留新表里还有的档")
        incoming = _incoming_orders(orders)
        now = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                self._ensure_rail_column(cursor)
                cursor.execute("SELECT id FROM grid_ledger_plan WHERE etf_code = %s", (code,))
                plan_row = cursor.fetchone()
                existing: List[Dict[str, Any]] = []
                if plan_row:
                    cursor.execute(
                        """
                        SELECT id, side, trigger_price, shares, note, rail, status
                        FROM grid_ledger_order WHERE plan_id = %s
                        """,
                        (int(plan_row["id"]),),
                    )
                    existing = list(cursor.fetchall())
                stale = _stale_posted(existing, incoming)
                if stale and policy not in ("void", "keep"):
                    raise StalePostedOrders(stale)

                cursor.execute(
                    """
                    INSERT INTO grid_ledger_plan
                        (etf_code, etf_name, anchor_price, base_shares, base_price, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        etf_name = VALUES(etf_name),
                        anchor_price = VALUES(anchor_price),
                        base_shares = VALUES(base_shares),
                        base_price = VALUES(base_price),
                        updated_at = VALUES(updated_at)
                    """,
                    (code, etf_name or "", float(anchor_price or 0), int(base_shares or 0), float(base_price or 0), now, now),
                )
                cursor.execute("SELECT id FROM grid_ledger_plan WHERE etf_code = %s", (code,))
                plan_id = int(cursor.fetchone()["id"])
                voided_ids = set()
                if policy == "void":
                    for row in existing:
                        if row["status"] != "已挂":
                            continue
                        cursor.execute(
                            "UPDATE grid_ledger_order SET status = %s, updated_at = %s WHERE id = %s",
                            ("作废", now, row["id"]),
                        )
                        voided_ids.add(row["id"])
                used = set(voided_ids)
                for order in incoming:
                    match = None
                    for row in existing:
                        if row["id"] in used:
                            continue
                        if order_key(row["side"], row["trigger_price"], row["shares"], row.get("rail") or "") == order["key"]:
                            match = row
                            break
                    if match:
                        used.add(match["id"])
                        cursor.execute(
                            "UPDATE grid_ledger_order SET note = %s, rail = %s, updated_at = %s WHERE id = %s",
                            (order["note"], order["rail"], now, match["id"]),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO grid_ledger_order
                                (plan_id, side, trigger_price, shares, note, rail, status, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                plan_id,
                                order["side"],
                                order["price"],
                                order["shares"],
                                order["note"],
                                order["rail"],
                                initial_status(order["note"], order["rail"], order["role"]),
                                now,
                            ),
                        )
                        used.add(cursor.lastrowid)
                for row in existing:
                    if row["id"] in used or row["status"] == "已成":
                        continue
                    if row["status"] == "已挂" and policy != "keep":
                        continue
                    cursor.execute(
                        "UPDATE grid_ledger_order SET status = %s, updated_at = %s WHERE id = %s",
                        ("作废", now, row["id"]),
                    )
            conn.commit()
        finally:
            conn.close()
        return self.get_plan(code)

    def set_status(self, order_id: int, status: str) -> None:
        label = normalize_status(status)
        now = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE grid_ledger_order SET status = %s, updated_at = %s WHERE id = %s",
                    (label, now, int(order_id)),
                )
                if cursor.rowcount == 0:
                    raise ValueError("没有这笔委托")
            conn.commit()
        finally:
            conn.close()

    def get_plan(self, etf_code: str, current_price: Optional[float] = None) -> Dict[str, Any]:
        code = str(etf_code or "").strip()
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                self._ensure_rail_column(cursor)
                cursor.execute("SELECT * FROM grid_ledger_plan WHERE etf_code = %s", (code,))
                plan = cursor.fetchone()
                if not plan:
                    return {"etf_code": code, "orders": []}
                cursor.execute(
                    """
                    SELECT id, side, trigger_price, shares, note, rail, status
                    FROM grid_ledger_order
                    WHERE plan_id = %s
                    ORDER BY trigger_price DESC, id ASC
                    """,
                    (plan["id"],),
                )
                orders = []
                for row in cursor.fetchall():
                    item = dict(row)
                    item["trigger_price"] = round(float(item["trigger_price"]), 3)
                    item["may_fill_today"] = may_fill_today(
                        item["side"],
                        item["trigger_price"],
                        current_price,
                        item["status"],
                        note=item.get("note") or "",
                        rail=item.get("rail") or "",
                    )
                    orders.append(item)
        finally:
            conn.close()
        return {
            "id": plan["id"],
            "etf_code": plan["etf_code"],
            "etf_name": plan["etf_name"],
            "anchor_price": plan["anchor_price"],
            "base_shares": plan["base_shares"],
            "base_price": plan["base_price"],
            "orders": orders,
        }
