import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .etf_taxonomy import assign_subsector, catalog_rows
from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database

logger = logging.getLogger(__name__)

SHOPPABLE_SECTORS = (
    "科技芯片",
    "新能源制造",
    "医药健康",
    "大金融",
    "大消费",
    "周期资源",
    "公用红利",
    "国防军工",
    "跨境全球",
    "大宗商品",
    "核心宽基",
)
UNCLASSIFIED_SECTOR = "未归类"

_UPSERT_INSTRUMENT = """
INSERT INTO etf_instrument (
    etf_code, name, sector, subsector_code, is_t0, list_date,
    latest_price, pct_change, amount_10k, amount_ma20_10k, atr_pct,
    elasticity, score, is_seed, updated_at
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
ON DUPLICATE KEY UPDATE
    name = VALUES(name),
    sector = VALUES(sector),
    subsector_code = VALUES(subsector_code),
    is_t0 = VALUES(is_t0),
    list_date = VALUES(list_date),
    latest_price = VALUES(latest_price),
    pct_change = VALUES(pct_change),
    amount_10k = VALUES(amount_10k),
    amount_ma20_10k = VALUES(amount_ma20_10k),
    atr_pct = VALUES(atr_pct),
    elasticity = VALUES(elasticity),
    score = VALUES(score),
    updated_at = VALUES(updated_at)
"""


class ETFPoolRepository:
    """可购标的池。读写只走 MySQL，不再写 JSON 镜像。"""

    def __init__(self, database: Optional[str] = None, json_path: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        self.json_path = json_path
        ensure_database(self.database)
        self._seed_catalog()

    def _connect(self):
        return connect(self.database)

    def _seed_catalog(self) -> None:
        rows = catalog_rows()
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                for sector in SHOPPABLE_SECTORS:
                    cursor.execute(
                        """
                        INSERT INTO etf_sector (sector_code, name) VALUES (%s, %s)
                        ON DUPLICATE KEY UPDATE name = VALUES(name)
                        """,
                        (sector, sector),
                    )
                for row in rows:
                    cursor.execute(
                        """
                        INSERT INTO etf_subsector (subsector_code, sector_code, name, sort_order)
                        VALUES (%s, %s, %s, %s)
                        ON DUPLICATE KEY UPDATE
                            sector_code = VALUES(sector_code),
                            name = VALUES(name),
                            sort_order = VALUES(sort_order)
                        """,
                        (row["subsector_code"], row["sector_code"], row["name"], row["sort_order"]),
                    )
            conn.commit()
        finally:
            conn.close()

    def save_pool(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        tuples = [self._instrument_tuple(record, now_str) for record in records]
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(_UPSERT_INSTRUMENT, tuples)
            conn.commit()
            return len(tuples)
        except Exception as exc:
            logger.error("批量保存标的池失败: %s", exc)
            raise
        finally:
            conn.close()

    def update_quotes(self, quotes: List[tuple]) -> int:
        """按代码更新最新价和涨跌幅。

        Args:
            quotes: (etf_code, latest_price, pct_change)

        Returns:
            int: 更新语句影响的行数
        """
        if not quotes:
            return 0
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = [
            (float(price), float(pct), now_str, str(code))
            for code, price, pct in quotes
        ]
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    UPDATE etf_instrument
                    SET latest_price = %s, pct_change = %s, updated_at = %s
                    WHERE etf_code = %s
                    """,
                    payload,
                )
                updated = cursor.rowcount
            conn.commit()
            return updated
        except Exception as exc:
            logger.error("更新标的池行情失败: %s", exc)
            raise
        finally:
            conn.close()

    def _instrument_tuple(self, record: Dict[str, Any], now_str: str) -> tuple:
        sector = record["sector"]
        subsector = record.get("subsector")
        if subsector is None and "subsector_code" not in record:
            subsector = assign_subsector(record["name"], sector)
        elif subsector is None:
            subsector = record.get("subsector_code")
        return (
            record["etf_code"],
            record["name"],
            sector,
            subsector,
            1 if record.get("is_t0") else 0,
            record.get("list_date", ""),
            float(record.get("latest_price", 0.0) or 0.0),
            float(record.get("pct_change", 0.0) or 0.0),
            float(record.get("amount_10k", 0.0) or 0.0),
            float(record.get("amount_ma20_10k", record.get("amount_10k", 0.0)) or 0.0),
            float(record.get("atr_pct", 0.0) or 0.0),
            record.get("elasticity", "稳健型"),
            float(record.get("score", 80.0) or 0.0),
            1 if record.get("is_seed") else 0,
            now_str,
        )

    def get_pool(
        self,
        sector: Optional[str] = None,
        is_t0: Optional[bool] = None,
        elasticity: Optional[str] = None,
        subsector: Optional[str] = None,
        min_amount_10k: float = 0.0,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
        commodity_exempt: bool = False,
        limit: int = 600,
    ) -> List[Dict[str, Any]]:
        try:
            query, params = self._pool_query(
                sector, is_t0, elasticity, subsector, min_amount_10k, min_ma20_amount_10k, min_atr_pct, limit,
                commodity_exempt=commodity_exempt,
            )
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
            finally:
                conn.close()
            return [self._to_item(row) for row in rows]
        except Exception as exc:
            logger.error("查询标的池失败: %s", exc)
            return []

    def _pool_query(
        self,
        sector,
        is_t0,
        elasticity,
        subsector,
        min_amount_10k,
        min_ma20,
        min_atr,
        limit,
        commodity_exempt: bool = False,
    ):
        if commodity_exempt:
            atr_sql = "(atr_pct >= %s OR (sector = %s AND atr_pct >= %s))"
            atr_params: List[Any] = [min_atr, "大宗商品", min(float(min_atr), 1.0)]
        else:
            atr_sql = "atr_pct >= %s"
            atr_params = [min_atr]
        query = (
            "SELECT * FROM etf_instrument "
            f"WHERE amount_ma20_10k >= %s AND amount_10k >= %s AND {atr_sql}"
        )
        params: List[Any] = [min_ma20, min_amount_10k, *atr_params]
        if sector and sector != "全部":
            query += " AND sector = %s"
            params.append(sector)
        else:
            placeholders = ",".join(["%s"] * len(SHOPPABLE_SECTORS))
            query += f" AND sector IN ({placeholders})"
            params.extend(SHOPPABLE_SECTORS)
        if is_t0 is True:
            query += " AND is_t0 = 1"
        if elasticity and elasticity != "全部":
            query += " AND elasticity = %s"
            params.append(elasticity)
        if subsector and subsector != "全部":
            query += " AND subsector_code = %s"
            params.append(subsector)
        query += " ORDER BY amount_ma20_10k DESC LIMIT %s"
        params.append(limit)
        return query, params

    def _to_item(self, row: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "etf_code": row["etf_code"],
            "name": row["name"],
            "sector": row["sector"],
            "subsector": row.get("subsector_code"),
            "is_t0": bool(row["is_t0"]),
            "list_date": row["list_date"],
            "latest_price": row["latest_price"],
            "pct_change": row["pct_change"],
            "amount_10k": row["amount_10k"],
            "amount_ma20_10k": row["amount_ma20_10k"],
            "atr_pct": row["atr_pct"],
            "elasticity": row["elasticity"],
            "score": row["score"],
            "is_seed": bool(row.get("is_seed")),
            "updated_at": row["updated_at"],
        }

    def get_sectors_summary(
        self,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
    ) -> Dict[str, Any]:
        try:
            placeholders = ",".join(["%s"] * len(SHOPPABLE_SECTORS))
            params: List[Any] = [min_ma20_amount_10k, min_atr_pct, *SHOPPABLE_SECTORS]
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT sector, COUNT(*) AS count, AVG(atr_pct) AS avg_atr
                        FROM etf_instrument
                        WHERE amount_ma20_10k >= %s AND atr_pct >= %s
                          AND sector IN ({placeholders})
                        GROUP BY sector ORDER BY count DESC
                        """,
                        params,
                    )
                    sector_rows = cursor.fetchall()
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) AS count FROM etf_instrument
                        WHERE amount_ma20_10k >= %s AND atr_pct >= %s AND is_t0 = 1
                          AND sector IN ({placeholders})
                        """,
                        params,
                    )
                    t0_count = cursor.fetchone()["count"]
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) AS count FROM etf_instrument
                        WHERE amount_ma20_10k >= %s AND atr_pct >= %s
                          AND sector IN ({placeholders})
                        """,
                        params,
                    )
                    total_count = cursor.fetchone()["count"]
                    cursor.execute(
                        """
                        SELECT COUNT(*) AS count FROM etf_instrument
                        WHERE amount_ma20_10k >= %s AND atr_pct >= %s AND sector = %s
                        """,
                        (min_ma20_amount_10k, min_atr_pct, UNCLASSIFIED_SECTOR),
                    )
                    unclassified_count = cursor.fetchone()["count"]
            finally:
                conn.close()
            return {
                "total_count": total_count,
                "t0_count": t0_count,
                "unclassified_count": unclassified_count,
                "sectors": [
                    {"name": row["sector"], "count": row["count"], "avg_atr": round(row["avg_atr"] or 0.0, 2)}
                    for row in sector_rows
                ],
            }
        except Exception as exc:
            logger.error("查询赛道统计失败: %s", exc)
            return {"total_count": 0, "t0_count": 0, "unclassified_count": 0, "sectors": []}

    def list_subsector_summary(
        self,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
    ) -> List[Dict[str, Any]]:
        """小类目录含计数为零的小类。"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.sector_code AS sector, s.name AS name, COUNT(i.etf_code) AS count
                    FROM etf_subsector s
                    LEFT JOIN etf_instrument i
                      ON i.subsector_code = s.subsector_code
                     AND i.amount_ma20_10k >= %s
                     AND i.atr_pct >= %s
                    GROUP BY s.sector_code, s.name, s.sort_order
                    ORDER BY s.sector_code, s.sort_order
                    """,
                    (min_ma20_amount_10k, min_atr_pct),
                )
                return [
                    {"sector": row["sector"], "name": row["name"], "count": int(row["count"])}
                    for row in cursor.fetchall()
                ]
        finally:
            conn.close()

    def list_shoppable_universe(
        self,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
    ) -> List[Dict[str, str]]:
        try:
            placeholders = ",".join(["%s"] * len(SHOPPABLE_SECTORS))
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"""
                        SELECT etf_code, name, sector FROM etf_instrument
                        WHERE amount_ma20_10k >= %s AND atr_pct >= %s
                          AND sector IN ({placeholders})
                        ORDER BY sector, etf_code
                        """,
                        (min_ma20_amount_10k, min_atr_pct, *SHOPPABLE_SECTORS),
                    )
                    return [
                        {"etf_code": row["etf_code"], "etf_name": row["name"], "sector": row["sector"]}
                        for row in cursor.fetchall()
                    ]
            finally:
                conn.close()
        except Exception as exc:
            logger.error("读取适合度宇宙失败: %s", exc)
            return []

    def find_name(self, etf_code: str) -> Optional[str]:
        clean_code = str(etf_code or "").split(".")[0].strip()
        if not clean_code:
            return None
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT name FROM etf_instrument WHERE etf_code = %s",
                        (clean_code,),
                    )
                    row = cursor.fetchone()
            finally:
                conn.close()
            if row and row["name"]:
                return str(row["name"])
        except Exception as exc:
            logger.warning("读取标的名称失败 (%s): %s", clean_code, exc)
        return None

    def list_sector_map(self) -> Dict[str, str]:
        try:
            placeholders = ",".join(["%s"] * len(SHOPPABLE_SECTORS))
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"SELECT etf_code, sector FROM etf_instrument WHERE sector IN ({placeholders})",
                        SHOPPABLE_SECTORS,
                    )
                    return {row["etf_code"]: row["sector"] for row in cursor.fetchall()}
            finally:
                conn.close()
        except Exception as exc:
            logger.error("读取赛道映射失败: %s", exc)
            return {}

    def reclassify_persisted(self, classify_fn) -> Dict[str, int]:
        updated = 0
        removed = 0
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM etf_instrument")
                rows = cursor.fetchall()
                for row in rows:
                    classified = classify_fn(row["name"], row["etf_code"])
                    if classified.get("excluded"):
                        cursor.execute(
                            "DELETE FROM etf_instrument WHERE etf_code = %s",
                            (row["etf_code"],),
                        )
                        removed += 1
                        continue
                    sector = classified["sector"]
                    cursor.execute(
                        """
                        UPDATE etf_instrument
                        SET sector = %s, subsector_code = %s, is_t0 = %s,
                            atr_pct = CASE WHEN atr_pct IS NULL OR atr_pct = 0 THEN %s ELSE atr_pct END,
                            elasticity = CASE WHEN elasticity IS NULL OR elasticity = '' THEN %s ELSE elasticity END,
                            updated_at = %s
                        WHERE etf_code = %s
                        """,
                        (
                            sector,
                            assign_subsector(row["name"], sector),
                            1 if classified.get("is_t0") else 0,
                            float(classified.get("atr_pct") or 0.0),
                            classified.get("elasticity") or "稳健型",
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            row["etf_code"],
                        ),
                    )
                    updated += 1
            conn.commit()
            # 提交分类后，自动基于 MySQL 真实 K 线刷新计算 14 日 Wilder ATR
            self.refresh_real_atr_from_bars()
            return {"updated": updated, "removed": removed}
        except Exception as exc:
            logger.error("重刷标的池分类失败: %s", exc)
            raise
        finally:
            conn.close()

    def list_subsector_members(self) -> List[tuple]:
        """每个小类按 20 日均成交额从高到低列出成员，供代表未过线时顺延。"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                placeholders = ",".join(["%s"] * len(SHOPPABLE_SECTORS))
                cursor.execute(
                    f"""
                    SELECT etf_code, name, sector, subsector_code, amount_ma20_10k
                    FROM etf_instrument
                    WHERE subsector_code IS NOT NULL AND subsector_code <> ''
                      AND sector IN ({placeholders})
                    ORDER BY subsector_code, amount_ma20_10k DESC, etf_code
                    """,
                    SHOPPABLE_SECTORS,
                )
                grouped: Dict[str, List[Dict[str, Any]]] = {}
                for row in cursor.fetchall():
                    grouped.setdefault(row["subsector_code"], []).append({
                        "etf_code": row["etf_code"],
                        "etf_name": row["name"],
                        "sector": row["sector"],
                        "subsector": row["subsector_code"],
                        "amount_ma20_10k": row["amount_ma20_10k"],
                    })
                return list(grouped.items())
        finally:
            conn.close()

    def set_subsector_seed(self, subsector: str, etf_code: str) -> None:
        """一个小类只保留一只种子。"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE etf_instrument SET is_seed = 0 WHERE subsector_code = %s",
                    (subsector,),
                )
                cursor.execute(
                    """
                    UPDATE etf_instrument SET is_seed = 1
                    WHERE etf_code = %s AND subsector_code = %s
                    """,
                    (etf_code, subsector),
                )
            conn.commit()
        finally:
            conn.close()

    def mark_seed_representatives(self) -> List[Dict[str, Any]]:
        """每个有成员的小类只标记流动性最高的一只。"""
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE etf_instrument SET is_seed = 0")
                cursor.execute(
                    """
                    SELECT i.etf_code, i.name, i.sector, i.subsector_code, i.amount_ma20_10k
                    FROM etf_instrument i
                    INNER JOIN (
                        SELECT subsector_code, MAX(amount_ma20_10k) AS max_amount
                        FROM etf_instrument
                        WHERE subsector_code IS NOT NULL AND subsector_code <> ''
                        GROUP BY subsector_code
                    ) picked
                      ON picked.subsector_code = i.subsector_code
                     AND picked.max_amount = i.amount_ma20_10k
                    """
                )
                winners = self._one_winner_per_subsector(cursor.fetchall())
                for row in winners:
                    cursor.execute(
                        "UPDATE etf_instrument SET is_seed = 1 WHERE etf_code = %s",
                        (row["etf_code"],),
                    )
            conn.commit()
            return winners
        finally:
            conn.close()

    def _one_winner_per_subsector(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        chosen: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            code = row["subsector_code"]
            current = chosen.get(code)
            if current is None or row["etf_code"] < current["etf_code"]:
                chosen[code] = row
        return [
            {
                "etf_code": row["etf_code"],
                "etf_name": row["name"],
                "sector": row["sector"],
                "subsector": row["subsector_code"],
            }
            for row in chosen.values()
        ]

    def list_seeds(self) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT etf_code, name, sector, subsector_code
                    FROM etf_instrument
                    WHERE is_seed = 1 AND subsector_code IS NOT NULL
                    ORDER BY sector, subsector_code
                    """
                )
                return [
                    {
                        "etf_code": row["etf_code"],
                        "etf_name": row["name"],
                        "sector": row["sector"],
                        "subsector": row["subsector_code"],
                    }
                    for row in cursor.fetchall()
                ]
        finally:
            conn.close()

    def get_count(self) -> int:
        try:
            conn = self._connect()
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT COUNT(*) AS count FROM etf_instrument")
                    return int(cursor.fetchone()["count"])
            finally:
                conn.close()
        except Exception:
            return 0

    def refresh_real_atr_from_bars(self) -> int:
        """基于 etf_daily_bar 中的真实历史 K 线，为 etf_instrument 中的标的重新计算 14 日 Wilder ATR 与弹性等级。"""
        import pandas as pd
        try:
            from services.data.bar_metrics import FAKE_LIST_DATE, INSUFFICIENT_DATA_LABEL, measure_local_metrics
        except ImportError:
            from backend.services.data.bar_metrics import (
                FAKE_LIST_DATE,
                INSUFFICIENT_DATA_LABEL,
                measure_local_metrics,
            )

        conn = self._connect()
        updated_count = 0
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT MAX(trade_date) AS max_date FROM etf_daily_bar")
                row = cursor.fetchone()
                if not row:
                    logger.warning("etf_daily_bar 表无数据，跳过真实 ATR 刷新")
                    return 0
                max_date = row.get("max_date") if isinstance(row, dict) else row[0]
                if not max_date:
                    return 0

                cursor.execute(
                    """
                    SELECT etf_code, trade_date AS date, open, high, low, close, vol, amount
                    FROM etf_daily_bar
                    WHERE trade_date >= DATE_SUB(%s, INTERVAL 60 DAY)
                    ORDER BY etf_code, date ASC
                    """,
                    (max_date,),
                )
                rows = cursor.fetchall()
                if not rows:
                    return 0

                df = pd.DataFrame(rows)
                updates = []
                for code, group in df.groupby("etf_code"):
                    try:
                        metrics = measure_local_metrics(group)
                    except Exception as calc_err:
                        logger.debug("标的 %s 计算真实 ATR 失败: %s", code, calc_err)
                        continue
                    if metrics["atr_sufficient"]:
                        atr_pct = metrics["atr_pct"]
                        elasticity = metrics["elasticity"]
                    else:
                        atr_pct = 0.0
                        elasticity = INSUFFICIENT_DATA_LABEL
                    ma20 = metrics["amount_ma20_10k"] if metrics["turnover_sufficient"] else 0.0
                    updates.append((atr_pct, elasticity, ma20, FAKE_LIST_DATE, INSUFFICIENT_DATA_LABEL, code))

                if updates:
                    cursor.executemany(
                        """
                        UPDATE etf_instrument
                        SET atr_pct = %s, elasticity = %s, amount_ma20_10k = %s,
                            list_date = CASE
                                WHEN list_date IS NULL OR list_date = '' OR list_date = %s
                                THEN %s ELSE list_date END
                        WHERE etf_code = %s
                        """,
                        updates,
                    )
                    conn.commit()
                    updated_count = len(updates)
                    logger.info("✓ 成功基于真实日 K 线刷新 %d 只标的的 14 日 Wilder ATR 与弹性评级", updated_count)
            return updated_count
        except Exception as exc:
            logger.error("刷新真实 ATR 失败: %s", exc)
            conn.rollback()
            return 0
        finally:
            conn.close()
