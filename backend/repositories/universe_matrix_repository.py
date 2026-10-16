import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .mysql_connection import DEFAULT_DATABASE, connect
from .mysql_schema import ensure_database

logger = logging.getLogger(__name__)

PRIMARY_SECTORS = [
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
]


class UniverseMatrixRepository:
    """
    全市场 537 只成熟 ETF 多周期回测大宽表仓储操作
    """

    def __init__(self, database: Optional[str] = None):
        self.database = database or DEFAULT_DATABASE
        ensure_database(self.database)

    def _connect(self):
        return connect(self.database)

    @staticmethod
    def make_config_signature(
        step_mode: str = "atr",
        atr_multipliers: Optional[Dict[str, float]] = None,
        eda_steps: Optional[Dict[str, float]] = None,
    ) -> Tuple[str, str]:
        """
        生成策略参数唯一指纹与人类可读标签
        """
        if step_mode == "atr":
            mults = atr_multipliers or {"small": 0.6, "medium": 1.2, "large": 2.5}
            s, m, l = mults.get("small", 0.6), mults.get("medium", 1.2), mults.get("large", 2.5)
            config_key = f"atr_{s}_{m}_{l}"
            config_label = f"ATR自适应 ({s}/{m}/{l})"
        else:
            steps = eda_steps or {"small": 5.0, "medium": 15.0, "large": 30.0}
            s, m, l = steps.get("small", 5.0), steps.get("medium", 15.0), steps.get("large", 30.0)
            config_key = f"fixed_{s}_{m}_{l}"
            config_label = f"固定步长 ({int(s)}%/{int(m)}%/{int(l)}%)"
        return config_key, config_label

    def batch_save(self, records: List[Dict[str, Any]]) -> int:
        """
        批量保存或替换多周期回测矩阵记录 (REPLACE INTO 幂等写入)
        """
        if not records:
            return 0

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        sql = """
        REPLACE INTO universe_matrix_backtest (
            etf_code, config_key, config_label, etf_name, sector, is_default_preset,
            step_mode, atr_small_mult, atr_mid_mult, atr_large_mult,
            step_small_ratio, step_mid_ratio, step_large_ratio,
            total_capital, scaling_ratio, reinvest_mode, total_bars,
            
            is_valid_90d, ret_90d, mdd_90d, calmar_90d, trades_90d, free_shares_90d, base_price_90d,
            is_valid_180d, ret_180d, mdd_180d, calmar_180d, trades_180d, free_shares_180d, base_price_180d,
            is_valid_1y, ret_1y, mdd_1y, calmar_1y, trades_1y, free_shares_1y, base_price_1y,
            is_valid_2y, ret_2y, mdd_2y, calmar_2y, trades_2y, free_shares_2y, base_price_2y,
            is_valid_3y, ret_3y, mdd_3y, calmar_3y, trades_3y, free_shares_3y, base_price_3y,
            is_valid_5y, ret_5y, mdd_5y, calmar_5y, trades_5y, free_shares_5y, base_price_5y,
            updated_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s, %s, %s, %s, %s, %s, %s,
            %s
        )
        """

        rows = []
        for item in records:
            p = item.get("periods") or {}
            step_mode = item.get("step_mode", "atr")
            atr_m = item.get("atr_multipliers") or {"small": 0.6, "medium": 1.2, "large": 2.5}
            eda_s = item.get("eda_steps") or {"small": 5.0, "medium": 15.0, "large": 30.0}

            config_key, config_label = self.make_config_signature(step_mode, atr_m, eda_s)
            is_default = 1 if (step_mode == "atr" and atr_m.get("small") == 0.6 and atr_m.get("large") == 2.5) else 0

            def parse_period(key):
                obj = p.get(key) or {}
                valid = 1 if obj.get("is_valid") else 0
                ret = obj.get("annual_return")
                mdd = obj.get("max_drawdown")
                calmar = obj.get("calmar_ratio")
                trades = obj.get("trade_count", 0)
                free = obj.get("free_shares", 0)
                bp = obj.get("base_price")
                return (valid, ret, mdd, calmar, trades, free, bp)

            row = (
                item.get("etf_code"),
                config_key,
                config_label,
                item.get("etf_name", ""),
                item.get("sector", "未入池"),
                is_default,
                
                step_mode,
                atr_m.get("small") if step_mode == "atr" else None,
                atr_m.get("medium") if step_mode == "atr" else None,
                atr_m.get("large") if step_mode == "atr" else None,
                eda_s.get("small") if step_mode == "fixed_eda" else None,
                eda_s.get("medium") if step_mode == "fixed_eda" else None,
                eda_s.get("large") if step_mode == "fixed_eda" else None,

                float(item.get("total_capital", 30000.0)),
                float(item.get("scaling_ratio", 0.10)),
                item.get("reinvest_mode", "pool_shares"),
                int(item.get("total_bars", 0)),

                *parse_period("90d"),
                *parse_period("180d"),
                *parse_period("1y"),
                *parse_period("2y"),
                *parse_period("3y"),
                *parse_period("5y"),
                now_str,
            )
            rows.append(row)

        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.executemany(sql, rows)
            conn.commit()
            return len(rows)
        finally:
            conn.close()

    def query_matrix(
        self,
        sector: Optional[str] = None,
        search: Optional[str] = None,
        sort_by: str = "5y",
        sort_order: str = "desc",
        only_valid_5y: bool = False,
        config_key: Optional[str] = None,
        is_default_only: bool = True,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        多条件带索引高效查询大宽表
        """
        where_clauses = ["1=1"]
        params = []

        if is_default_only:
            where_clauses.append("is_default_preset = 1")
        elif config_key:
            where_clauses.append("config_key = %s")
            params.append(config_key)

        if sector and sector != "全部":
            where_clauses.append("sector = %s")
            params.append(sector)

        if search and search.strip():
            where_clauses.append("(etf_code LIKE %s OR etf_name LIKE %s)")
            q = f"%{search.strip()}%"
            params.extend([q, q])

        if only_valid_5y:
            where_clauses.append("is_valid_5y = 1")

        # 排序字段映射
        sort_col_map = {
            "5y": "ret_5y",
            "3y": "ret_3y",
            "2y": "ret_2y",
            "1y": "ret_1y",
            "180d": "ret_180d",
            "90d": "ret_90d",
        }
        order_col = sort_col_map.get(sort_by, "ret_5y")
        direction = "DESC" if sort_order.lower() == "desc" else "ASC"

        where_sql = " AND ".join(where_clauses)

        # 统计总数
        count_sql = f"SELECT COUNT(*) AS total FROM universe_matrix_backtest WHERE {where_sql}"

        # 记录查询
        offset = max(0, (page - 1) * page_size)
        # 排序时如果指定列为 NULL 则排在最后
        query_sql = f"""
        SELECT * FROM universe_matrix_backtest
        WHERE {where_sql}
        ORDER BY CASE WHEN {order_col} IS NULL THEN 1 ELSE 0 END, {order_col} {direction}
        LIMIT %s OFFSET %s
        """

        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(count_sql, params)
                count_row = cursor.fetchone() or {}
                total = int(count_row.get("total", 0) if isinstance(count_row, dict) else count_row[0])

                query_params = list(params) + [page_size, offset]
                cursor.execute(query_sql, query_params)
                db_rows = cursor.fetchall()

            # 转换为结构化 records
            records = [self._row_to_record(dict(r)) for r in db_rows]
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "records": records,
            }
        finally:
            conn.close()

    def aggregate_sectors(self, config_key: Optional[str] = None, is_default_only: bool = True) -> List[Dict[str, Any]]:
        """
        直接使用 SQL GROUP BY sector 实时聚合 11 大赛道胜率、平均年化、平均回撤与标杆
        """
        where_cond = "is_default_preset = 1" if is_default_only else "config_key = %s"
        params = [] if is_default_only else [config_key]

        sql = f"""
        SELECT * FROM (
            SELECT 
                sector,
                COUNT(*) AS total_etfs,
                SUM(is_valid_5y) AS valid_5y,
                ROUND(SUM(CASE WHEN is_valid_5y = 1 AND ret_5y > 0 THEN 1 ELSE 0 END) / NULLIF(SUM(is_valid_5y), 0) * 100, 1) AS win_rate_5y,
                ROUND(AVG(CASE WHEN is_valid_5y = 1 THEN ret_5y ELSE NULL END), 2) AS avg_annual_ret_5y,
                ROUND(AVG(CASE WHEN is_valid_5y = 1 THEN mdd_5y ELSE NULL END), 2) AS avg_mdd_5y,
                ROUND(AVG(CASE WHEN is_valid_5y = 1 THEN trades_5y ELSE NULL END), 1) AS avg_trades_5y,

                SUM(is_valid_3y) AS valid_3y,
                ROUND(SUM(CASE WHEN is_valid_3y = 1 AND ret_3y > 0 THEN 1 ELSE 0 END) / NULLIF(SUM(is_valid_3y), 0) * 100, 1) AS win_rate_3y,
                ROUND(AVG(CASE WHEN is_valid_3y = 1 THEN ret_3y ELSE NULL END), 2) AS avg_annual_ret_3y,
                ROUND(AVG(CASE WHEN is_valid_3y = 1 THEN mdd_3y ELSE NULL END), 2) AS avg_mdd_3y,

                SUM(is_valid_1y) AS valid_1y,
                ROUND(SUM(CASE WHEN is_valid_1y = 1 AND ret_1y > 0 THEN 1 ELSE 0 END) / NULLIF(SUM(is_valid_1y), 0) * 100, 1) AS win_rate_1y,
                ROUND(AVG(CASE WHEN is_valid_1y = 1 THEN ret_1y ELSE NULL END), 2) AS avg_annual_ret_1y
            FROM universe_matrix_backtest
            WHERE {where_cond}
            GROUP BY sector
        ) t
        ORDER BY CASE WHEN avg_annual_ret_5y IS NULL THEN 1 ELSE 0 END, avg_annual_ret_5y DESC
        """

        conn = self._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute(sql, params)
                agg_rows = cursor.fetchall()

                # 为每个赛道单独查询 Top Pick 标杆标的
                sector_results = []
                for row_raw in agg_rows:
                    row = dict(row_raw)
                    sec_name = row["sector"]
                    top_pick_sql = f"""
                    SELECT etf_code, etf_name, ret_5y, mdd_5y, ret_3y
                    FROM universe_matrix_backtest
                    WHERE {where_cond} AND sector = %s
                    ORDER BY 
                        CASE WHEN is_valid_5y = 1 THEN 1 ELSE 0 END DESC,
                        CASE WHEN ret_5y IS NOT NULL THEN ret_5y ELSE ret_3y END DESC
                    LIMIT 1
                    """
                    tp_params = list(params) + [sec_name]
                    cursor.execute(top_pick_sql, tp_params)
                    tp_row = cursor.fetchone()

                    top_pick = None
                    if tp_row and isinstance(tp_row, dict):
                        ret5 = tp_row.get("ret_5y")
                        ret3 = tp_row.get("ret_3y")
                        p_years = "5年" if ret5 is not None else "3年"
                        ann = ret5 if ret5 is not None else ret3
                        top_pick = {
                            "etf_code": tp_row.get("etf_code"),
                            "etf_name": tp_row.get("etf_name"),
                            "benchmark_period": p_years,
                            "annual_return": ann,
                            "max_drawdown": tp_row.get("mdd_5y"),
                        }

                    sector_results.append({
                        "sector": sec_name,
                        "total_etfs": row.get("total_etfs", 0),
                        "stat_5y": {
                            "valid_count": row.get("valid_5y") or 0,
                            "win_rate": row.get("win_rate_5y"),
                            "avg_annual_return": row.get("avg_annual_ret_5y"),
                            "avg_max_drawdown": row.get("avg_mdd_5y"),
                            "avg_trades": row.get("avg_trades_5y"),
                        },
                        "stat_3y": {
                            "valid_count": row.get("valid_3y") or 0,
                            "win_rate": row.get("win_rate_3y"),
                            "avg_annual_return": row.get("avg_annual_ret_3y"),
                            "avg_max_drawdown": row.get("avg_mdd_3y"),
                        },
                        "stat_1y": {
                            "valid_count": row.get("valid_1y") or 0,
                            "win_rate": row.get("win_rate_1y"),
                            "avg_annual_return": row.get("avg_annual_ret_1y"),
                        },
                        "top_pick": top_pick,
                    })

                return sector_results
        finally:
            conn.close()

    @staticmethod
    def _row_to_record(row: Dict[str, Any]) -> Dict[str, Any]:
        """将数据库大宽表行还原为前端标准 JSON 格式 (同时具备年化收益率与累计总收益率)"""
        cal_days_map = {
            "90d": 90,
            "180d": 180,
            "1y": 365,
            "2y": 730,
            "3y": 1095,
            "5y": 1825,
        }

        def build_p(prefix):
            is_v = bool(row.get(f"is_valid_{prefix}"))
            ann = row.get(f"ret_{prefix}")
            cal_d = cal_days_map.get(prefix, 365)
            tot = round(ann * (cal_d / 365.0), 2) if ann is not None else None

            return {
                "is_valid": is_v,
                "reason": None if is_v else "上市不足",
                "annual_return": ann,
                "total_return": tot,
                "max_drawdown": row.get(f"mdd_{prefix}"),
                "calmar_ratio": row.get(f"calmar_{prefix}"),
                "trade_count": row.get(f"trades_{prefix}"),
                "free_shares": row.get(f"free_shares_{prefix}"),
                "base_price": row.get(f"base_price_{prefix}"),
            }

        return {
            "etf_code": row["etf_code"],
            "etf_name": row["etf_name"],
            "sector": row["sector"],
            "total_bars": row["total_bars"],
            "config_key": row["config_key"],
            "config_label": row["config_label"],
            "periods": {
                "90d": build_p("90d"),
                "180d": build_p("180d"),
                "1y": build_p("1y"),
                "2y": build_p("2y"),
                "3y": build_p("3y"),
                "5y": build_p("5y"),
            },
        }

    def codes_for_default_preset(self) -> set:
        """默认参数矩阵里已经有结果的代码。"""
        ensure_database(self.database)
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT etf_code FROM universe_matrix_backtest WHERE is_default_preset = 1"
                )
                return {str(row["etf_code"]) for row in cur.fetchall() if row.get("etf_code")}
        finally:
            conn.close()

    def get_validity_map(self) -> Dict[str, Dict[str, bool]]:
        """获取所有标的的周期有效性字典，供首页选品雷达毫秒级过滤成熟度"""
        ensure_database(DEFAULT_DATABASE)
        conn = connect(DEFAULT_DATABASE)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT etf_code, is_valid_5y, is_valid_3y, is_valid_1y "
                    "FROM universe_matrix_backtest "
                    "WHERE is_default_preset = 1"
                )
                rows = cur.fetchall()
                res: Dict[str, Dict[str, bool]] = {}
                for r in rows:
                    if isinstance(r, dict):
                        res[str(r.get("etf_code", ""))] = {
                            "is_valid_5y": bool(r.get("is_valid_5y", 0)),
                            "is_valid_3y": bool(r.get("is_valid_3y", 0)),
                            "is_valid_1y": bool(r.get("is_valid_1y", 0)),
                        }
                return res
        finally:
            conn.close()

