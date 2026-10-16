"""全市场日 K 引导进度。同一套表在 SQLite 和 MySQL 上读写。"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Set

from services.data.history_window import history_reaches_window

from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database

logger = logging.getLogger(__name__)

_PENDING = "pending"
_SYNCED = "synced"
_EMPTY = "empty"
_DONE = {_SYNCED, _EMPTY}
EMPTY_RECHECK_DAYS = 7


class UniverseBootstrapRepository:
    """记录全市场名单和每只代码是否已经拉过日 K。"""

    def __init__(self, database: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        ensure_database(self.database)

    def _connect(self):
        return connect(self.database)

    def reset(self) -> None:
        """清掉引导进度。测试用来隔离用例。"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM universe_bootstrap_code")
                cursor.execute("DELETE FROM universe_bootstrap")
            conn.commit()
        finally:
            conn.close()

    def progress(self) -> Dict[str, Any]:
        """首页用的进度。未完成时 active 为真，完成或还没有名单时为假。"""
        row = self._state_row()
        total = int((row or {}).get("total_codes") or 0)
        done = int((row or {}).get("done_codes") or 0)
        active = bool(row) and not row.get("completed_at") and total > 0
        return {"active": active, "done": done, "total": total}

    def is_complete(self) -> bool:
        row = self._state_row()
        return bool(row and row.get("completed_at"))

    def saved_instruments(self) -> List[Dict[str, str]]:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT etf_code, etf_name FROM universe_bootstrap_code ORDER BY etf_code"
                )
                rows = cursor.fetchall()
        finally:
            conn.close()
        return [
            {"etf_code": row["etf_code"], "etf_name": row["etf_name"]}
            for row in rows
        ]

    def pending_instruments(self) -> List[Dict[str, str]]:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT etf_code, etf_name FROM universe_bootstrap_code
                    WHERE status = %s ORDER BY etf_code
                    """,
                    (_PENDING,),
                )
                rows = cursor.fetchall()
        finally:
            conn.close()
        return [
            {"etf_code": row["etf_code"], "etf_name": row["etf_name"]}
            for row in rows
        ]

    def prepare(
        self,
        instruments: List[Dict[str, str]],
        codes_with_bars: Iterable[str],
        spans: Optional[Dict[str, Dict[str, Any]]] = None,
        target_start: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        """按最新名单对齐进度。日 K 已经盖住近 5 年的不再拉取，只有最近一截的改回待补。"""
        latest = []
        seen = set()
        for item in instruments or []:
            code = str(item.get("etf_code") or "").strip()
            if len(code) != 6 or not code.isdigit() or code in seen:
                continue
            seen.add(code)
            name = str(item.get("etf_name") or code).strip() or code
            latest.append({"etf_code": code, "etf_name": name})
        if not latest:
            return self.pending_instruments()

        covered: Set[str] = {str(code) for code in (codes_with_bars or [])}
        span_map = spans or {}
        now = _now()
        reopened: List[str] = []
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT etf_code, status, history_settled FROM universe_bootstrap_code"
                )
                existing = {}
                settled = {}
                for row in cursor.fetchall():
                    existing[row["etf_code"]] = row["status"]
                    settled[row["etf_code"]] = int(row.get("history_settled") or 0)
                keep = [item["etf_code"] for item in latest]
                placeholders = ",".join(["%s"] * len(keep))
                cursor.execute(
                    f"DELETE FROM universe_bootstrap_code WHERE etf_code NOT IN ({placeholders})",
                    keep,
                )
                for item in latest:
                    code = item["etf_code"]
                    previous = existing.get(code)
                    span = span_map.get(code) or {}
                    reaches = history_reaches_window(span.get("min_date"), target_start)
                    needs_history = bool(
                        target_start
                        and code in covered
                        and not settled.get(code)
                        and not reaches
                    )
                    if needs_history:
                        status = _PENDING
                        if previous == _SYNCED:
                            reopened.append(code)
                    elif previous in _DONE:
                        status = previous
                    elif code in covered:
                        status = _SYNCED
                    else:
                        status = _PENDING
                    cursor.execute(
                        """
                        INSERT INTO universe_bootstrap_code (etf_code, etf_name, status, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            etf_name = VALUES(etf_name),
                            status = VALUES(status),
                            updated_at = VALUES(updated_at)
                        """,
                        (code, item["etf_name"], status, now),
                    )
                self._recount(cursor, now)
            conn.commit()
        finally:
            conn.close()
        if reopened:
            logger.info("日K没有覆盖近5年，改回待补 %s 只", len(reopened))
        return self.pending_instruments()

    def recheck_barless_empties(self, codes_with_bars: Iterable[str]) -> List[str]:
        """把没有日 K、却被记成空行情的代码改回待拉取。

        第一次启动写下 empty_recheck_at。这次修复之前的尝试都会改回。
        之后同一只代码最多每 7 天再查一次，避免真的没有行情的代码每次启动都重拉。
        本地已经有日 K 的不改。有代码被改回时清掉完成时间。
        """
        covered = {str(code) for code in (codes_with_bars or [])}
        now = _now()
        now_dt = datetime.strptime(now, "%Y-%m-%d %H:%M:%S")
        cutoff = (now_dt - timedelta(days=EMPTY_RECHECK_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT empty_recheck_at FROM universe_bootstrap WHERE id = %s",
                    (1,),
                )
                state = cursor.fetchone() or {}
                flag = state.get("empty_recheck_at")
                cursor.execute(
                    """
                    SELECT etf_code, updated_at FROM universe_bootstrap_code
                    WHERE status = %s
                    """,
                    (_EMPTY,),
                )
                targets = []
                for row in cursor.fetchall():
                    code = str(row["etf_code"])
                    if code in covered:
                        continue
                    updated = str(row.get("updated_at") or "")
                    before_fix = not flag or not updated or updated < str(flag)
                    stale = not updated or updated <= cutoff
                    if before_fix or stale:
                        targets.append(code)
                if not flag:
                    cursor.execute(
                        """
                        INSERT INTO universe_bootstrap (
                            id, list_fetched_at, completed_at, total_codes, done_codes,
                            updated_at, empty_recheck_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            empty_recheck_at = COALESCE(empty_recheck_at, VALUES(empty_recheck_at))
                        """,
                        (1, now, None, 0, 0, now, now),
                    )
                if not targets:
                    conn.commit()
                    return []
                for code in targets:
                    cursor.execute(
                        """
                        UPDATE universe_bootstrap_code
                        SET status = %s, updated_at = %s
                        WHERE etf_code = %s
                        """,
                        (_PENDING, now, code),
                    )
                self._recount(cursor, now)
                conn.commit()
            return targets
        finally:
            conn.close()

    def record_result(self, result: Dict[str, Any]) -> None:
        """把单只代码的同步结果写进进度。网络失败保持 pending，下次再拉。"""
        code = str((result or {}).get("etf_code") or "").strip()
        if not code:
            return
        remote_status = str((result or {}).get("status") or "")
        error = str((result or {}).get("error") or "")
        if remote_status in ("synced", "skipped"):
            status = _SYNCED
        elif remote_status == "failed" and "为空" in error:
            status = _EMPTY
        else:
            return
        settled_flag = None
        if "history_settled" in (result or {}):
            settled_flag = 1 if result.get("history_settled") else 0
        now = _now()
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO universe_bootstrap_code (
                        etf_code, etf_name, status, updated_at, history_settled
                    ) VALUES (%s, %s, %s, %s, COALESCE(%s, 0))
                    ON DUPLICATE KEY UPDATE
                        status = VALUES(status),
                        updated_at = VALUES(updated_at),
                        history_settled = COALESCE(%s, history_settled)
                    """,
                    (code, code, status, now, settled_flag, settled_flag),
                )
                self._recount(cursor, now)
            conn.commit()
        except Exception as exc:
            logger.warning("写入引导进度失败 (%s): %s", code, exc)
        finally:
            conn.close()

    def _recount(self, cursor, now: str) -> None:
        cursor.execute(
            "SELECT status, COUNT(*) AS total FROM universe_bootstrap_code GROUP BY status"
        )
        counts = {row["status"]: int(row["total"] or 0) for row in cursor.fetchall()}
        total = sum(counts.values())
        done = counts.get(_SYNCED, 0) + counts.get(_EMPTY, 0)
        completed_at = now if total and done == total else None
        cursor.execute(
            """
            INSERT INTO universe_bootstrap (
                id, list_fetched_at, completed_at, total_codes, done_codes, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                list_fetched_at = VALUES(list_fetched_at),
                completed_at = VALUES(completed_at),
                total_codes = VALUES(total_codes),
                done_codes = VALUES(done_codes),
                updated_at = VALUES(updated_at)
            """,
            (1, now, completed_at, total, done, now),
        )

    def _state_row(self) -> Optional[Dict[str, Any]]:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT * FROM universe_bootstrap WHERE id = %s", (1,))
                    return cursor.fetchone()
            finally:
                conn.close()
        except Exception as exc:
            logger.warning("读取引导进度失败: %s", exc)
            return None


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
