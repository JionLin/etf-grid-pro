"""本地网格账本。SQLite 与 MySQL 共用这些语句。"""
from typing import Any, Dict, List, Optional

from services.analysis.order_ledger import may_fill_today, normalize_side, normalize_status, order_key
from services.data.market_clock import shanghai_now

from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database


class LedgerRepository:
    def __init__(self, database: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        ensure_database(self.database)

    def _connect(self):
        return connect(self.database)

    def save_plan(
        self,
        etf_code: str,
        etf_name: str,
        anchor_price: float,
        base_shares: int,
        base_price: float,
        orders: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        code = str(etf_code or "").strip()
        if not code:
            raise ValueError("账本需要 ETF 代码")
        now = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
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
                cursor.execute(
                    "SELECT id, side, trigger_price, shares, status FROM grid_ledger_order WHERE plan_id = %s",
                    (plan_id,),
                )
                existing = list(cursor.fetchall())
                used = set()
                for order in orders or []:
                    side = normalize_side(order.get("side") or order.get("action"))
                    price = round(float(order.get("trigger_price", order.get("price"))), 3)
                    shares = int(order.get("shares") or 0)
                    note = str(order.get("note") or "")[:255]
                    if shares <= 0 or price <= 0:
                        continue
                    match = None
                    for row in existing:
                        if row["id"] in used:
                            continue
                        if order_key(row["side"], row["trigger_price"], row["shares"]) == order_key(side, price, shares):
                            match = row
                            break
                    if match:
                        used.add(match["id"])
                        cursor.execute(
                            "UPDATE grid_ledger_order SET note = %s, updated_at = %s WHERE id = %s",
                            (note, now, match["id"]),
                        )
                    else:
                        cursor.execute(
                            """
                            INSERT INTO grid_ledger_order
                                (plan_id, side, trigger_price, shares, note, status, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (plan_id, side, price, shares, note, "未挂", now),
                        )
                        used.add(cursor.lastrowid)
                for row in existing:
                    if row["id"] in used or row["status"] in ("已成", "已挂"):
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
                cursor.execute("SELECT * FROM grid_ledger_plan WHERE etf_code = %s", (code,))
                plan = cursor.fetchone()
                if not plan:
                    return {"etf_code": code, "orders": []}
                cursor.execute(
                    """
                    SELECT id, side, trigger_price, shares, note, status
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
                        item["side"], item["trigger_price"], current_price, item["status"]
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
