import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import pandas as pd

from services.data.market_clock import (
    SHANGHAI,
    bar_saved_before_close,
    session_bar_unfinished,
)
from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database

logger = logging.getLogger(__name__)

_UPSERT_BARS = """
INSERT INTO etf_daily_bar (
    etf_code, trade_date, open, close, high, low, vol, amount, pct_chg, created_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    open = VALUES(open),
    close = VALUES(close),
    high = VALUES(high),
    low = VALUES(low),
    vol = VALUES(vol),
    amount = VALUES(amount),
    pct_chg = VALUES(pct_chg),
    created_at = VALUES(created_at)
"""


class MarketDataRepository:
    """ETF 日 K 线时序库。同一标的同一交易日幂等覆盖。"""

    def __init__(self, database: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        ensure_database(self.database)

    def _connect(self):
        return connect(self.database)

    def _normalize_date_str(self, val: Any) -> str:
        if val is None:
            return ""
        text = str(val).strip()
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        if len(text) >= 10:
            return text[:10].replace("/", "-")
        return text

    def save_bars(self, etf_code: str, bars: Union[pd.DataFrame, List[Dict[str, Any]]]) -> int:
        from services.data.market_clock import shanghai_now

        captured_at = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
        records = [
            (*row, captured_at)
            for row in self._to_records(etf_code, bars)
            if not self._session_bar_unfinished(row[1])
        ]
        if not records:
            return 0
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.executemany(_UPSERT_BARS, records)
                conn.commit()
            finally:
                conn.close()
            return len(records)
        except Exception as exc:
            logger.error("批量保存日 K 失败 (%s): %s", etf_code, exc)
            return 0

    @staticmethod
    def _session_bar_unfinished(trade_date: str) -> bool:
        return session_bar_unfinished(trade_date)

    def _to_records(self, etf_code: str, bars: Union[pd.DataFrame, List[Dict[str, Any]]]) -> List[tuple]:
        if bars is None:
            return []
        clean_code = etf_code.split(".")[0]
        if isinstance(bars, pd.DataFrame):
            if bars.empty:
                return []
            mapped = [self._row_from_mapping(clean_code, row, bars) for _, row in bars.iterrows()]
        else:
            mapped = [self._row_from_mapping(clean_code, row, None) for row in bars]
        return [row for row in mapped if row]

    def _row_from_mapping(self, clean_code: str, row: Any, frame: Optional[pd.DataFrame]) -> Optional[tuple]:
        date_key = "date" if frame is not None and "date" in frame.columns else "trade_date"
        if frame is None:
            date_key = "trade_date" if row.get("trade_date") else "date"
        trade_date = self._normalize_date_str(row.get(date_key))
        if not trade_date:
            return None
        opened = float(row.get("open", 0.0) or 0.0)
        return (
            clean_code,
            trade_date,
            opened,
            float(row.get("close", 0.0) or 0.0),
            float(row.get("high", opened) or opened),
            float(row.get("low", opened) or opened),
            float(row.get("vol", 0.0) or 0.0),
            float(row.get("amount", 0.0) or 0.0),
            float(row.get("pct_chg", 0.0) or 0.0),
        )

    def codes_with_bars(self) -> set:
        """已经有至少一根日 K 的代码。引导续传时这些代码不再整段重拉。"""
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT DISTINCT etf_code FROM etf_daily_bar")
                    rows = cursor.fetchall()
            finally:
                conn.close()
            return {str(row["etf_code"]) for row in rows if row.get("etf_code")}
        except Exception as exc:
            logger.warning("读取已有日 K 的代码失败: %s", exc)
            return set()

    def get_date_range(self, etf_code: str) -> Dict[str, Any]:
        clean_code = etf_code.split(".")[0]
        empty = {"min_date": None, "max_date": None, "total_count": 0}
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT MIN(trade_date) AS min_date, MAX(trade_date) AS max_date, COUNT(*) AS count
                        FROM etf_daily_bar WHERE etf_code = %s
                        """,
                        (clean_code,),
                    )
                    row = cursor.fetchone()
            finally:
                conn.close()
            if row and row["count"] > 0:
                return {
                    "min_date": row["min_date"],
                    "max_date": row["max_date"],
                    "total_count": row["count"],
                }
        except Exception as exc:
            logger.warning("查询日 K 起止失败 (%s): %s", etf_code, exc)
        return empty

    def get_bars(
        self,
        etf_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> pd.DataFrame:
        clean_code = etf_code.split(".")[0]
        params: List[Any] = [clean_code]
        query = (
            "SELECT trade_date, open, close, high, low, vol, amount, pct_chg "
            "FROM etf_daily_bar WHERE etf_code = %s"
        )
        if start_date:
            query += " AND trade_date >= %s"
            params.append(self._normalize_date_str(start_date))
        if end_date:
            query += " AND trade_date <= %s"
            params.append(self._normalize_date_str(end_date))
        query += " ORDER BY trade_date ASC"
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
            finally:
                conn.close()
            if not rows:
                return pd.DataFrame()
            data = list(rows)
            bounded_by_dates = bool(start_date and end_date)
            if limit and len(data) > limit and not bounded_by_dates:
                data = data[-limit:]
            frame = pd.DataFrame(data)
            frame["trade_date"] = pd.to_datetime(frame["trade_date"])
            return frame
        except Exception as exc:
            logger.error("提取日 K 失败 (%s): %s", etf_code, exc)
            return pd.DataFrame()

    def get_all_bars(self, etf_code: str) -> pd.DataFrame:
        return self.get_bars(etf_code=etf_code, start_date=None, end_date=None)

    def delete_preclose_session_bars(
        self,
        moment: Optional[datetime] = None,
        etf_code: Optional[str] = None,
    ) -> int:
        """删掉收盘前写入的当天 K 线，让随后的同步用正式收盘覆盖。"""
        now = moment or datetime.now(SHANGHAI)
        today = now.strftime("%Y-%m-%d") if hasattr(now, "strftime") else str(now)[:10]
        query = "SELECT etf_code, trade_date, created_at FROM etf_daily_bar WHERE trade_date = %s"
        params: List[Any] = [today]
        if etf_code:
            query += " AND etf_code = %s"
            params.append(etf_code.split(".")[0])
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                doomed = [
                    (row["etf_code"], str(row["trade_date"])[:10])
                    for row in rows
                    if bar_saved_before_close(row["trade_date"], row.get("created_at"), now)
                ]
                for code, trade_date in doomed:
                    cursor.execute(
                        "DELETE FROM etf_daily_bar WHERE etf_code = %s AND trade_date = %s",
                        (code, trade_date),
                    )
            conn.commit()
            return len(doomed)
        finally:
            conn.close()

    def count_bars(self) -> int:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) AS count FROM etf_daily_bar")
                return int(cursor.fetchone()["count"])
        finally:
            conn.close()
