import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from config.constants import ETFConstants
from repositories.etf_pool_repository import ETFPoolRepository
from repositories.market_data_repository import MarketDataRepository
from services.analysis.backtest_engine import GridBacktestEngine
from services.analysis.etf_analysis_service import ETFAnalysisService
from services.analysis.grid_calculator import CompositeGridCalculator
from algorithms.grid.optimizer import GridOptimizer

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

# 各周期的标准交易日及有效性阈值 (75% 门槛)
# 90天约 60 交易日 (门槛 45)
# 180天约 120 交易日 (门槛 90)
# 365天(1年)约 245 交易日 (门槛 180)
# 730天(2年)约 490 交易日 (门槛 365)
# 1095天(3年)约 735 交易日 (门槛 550)
# 1825天(5年)约 1225 交易日 (门槛 915)
PERIOD_SPECS = [
    {"key": "90d", "days": 90, "trading_days": 60, "min_days": 45, "label": "90天"},
    {"key": "180d", "days": 180, "trading_days": 120, "min_days": 90, "label": "半年"},
    {"key": "1y", "days": 365, "trading_days": 245, "min_days": 180, "label": "1年"},
    {"key": "2y", "days": 730, "trading_days": 490, "min_days": 365, "label": "2年"},
    {"key": "3y", "days": 1095, "trading_days": 735, "min_days": 550, "label": "3年"},
    {"key": "5y", "days": 1825, "trading_days": 1225, "min_days": 915, "label": "5年"},
]


class UniverseMatrixBacktestService:
    """
    全市场 537 只成熟做 T 标的多周期网格回测矩阵调度与赛道横评服务
    """

    def __init__(self):
        self.pool_repo = ETFPoolRepository()
        self.market_repo = MarketDataRepository()
        self.backtest_engine = GridBacktestEngine()
        self.grid_optimizer = GridOptimizer()
        self.composite_grid_calculator = CompositeGridCalculator()
        self.etf_service = ETFAnalysisService()

    def get_shoppable_universe(self) -> List[Dict[str, Any]]:
        """获取成熟选品池清单"""
        return self.pool_repo.list_shoppable_universe()

    def run_single_etf_matrix(
        self,
        etf_code: str,
        etf_name: str = "",
        sector: str = "",
        total_capital: float = 30000.0,
        scaling_ratio: float = 0.10,
        reinvest_mode: str = "pool_shares",
        step_mode: str = "atr",
    ) -> Dict[str, Any]:
        """
        对单只 ETF 进行 6 个周期的网格回测：
        - 从 MySQL 一次性拉取全部日 K 线并在内存中切片；
        - 基准锚点价格 P0 严格采用各周期首日真实开盘价；
        - 上市未满周期的次新 ETF 严格留空 (None)。
        """
        clean_code = etf_code.split(".")[0]
        # 1. 一次性获取该标的在 MySQL 中的所有历史日线
        df = self.market_repo.get_bars(clean_code)
        date_col = "trade_date" if df is not None and "trade_date" in df.columns else "date"

        empty_period = {
            "is_valid": False,
            "reason": "无本地日线数据",
            "annual_return": None,
            "total_return": None,
            "max_drawdown": None,
            "calmar_ratio": None,
            "trade_count": None,
            "free_shares": None,
            "base_price": None,
            "latest_price": None,
            "actual_days": 0,
        }

        if df is None or df.empty:
            return {
                "etf_code": clean_code,
                "etf_name": etf_name,
                "sector": sector,
                "total_bars": 0,
                "periods": {spec["key"]: empty_period.copy() for spec in PERIOD_SPECS},
                "error": "无本地日线数据",
            }

        # 确保按日期升序且同时拥有 trade_date 与 date 列
        df = df.sort_values(by=date_col).reset_index(drop=True)
        if "trade_date" in df.columns and "date" not in df.columns:
            df["date"] = df["trade_date"]
        total_bars = len(df)

        trade_mode = "t0" if ETFConstants.is_t0_etf(clean_code, etf_name) else "t1"
        period_results: Dict[str, Any] = {}

        now = datetime.now()
        for spec in PERIOD_SPECS:
            key = spec["key"]
            cal_days_target = spec["days"]
            cutoff_date = (now - timedelta(days=cal_days_target)).strftime("%Y-%m-%d")

            # 2. 严格按真实自然日期过滤截取切片 (与单测引擎 start_date 完全同源)
            slice_df = df[df["date"] >= cutoff_date].copy().reset_index(drop=True)
            if slice_df.empty or len(slice_df) < 15:
                period_results[key] = {
                    "is_valid": False,
                    "reason": f"上市不足 (仅{len(slice_df)}交易日)",
                    "annual_return": None,
                    "total_return": None,
                    "max_drawdown": None,
                    "calmar_ratio": None,
                    "trade_count": None,
                    "free_shares": None,
                    "base_price": None,
                    "latest_price": float(df.iloc[-1]["close"]),
                    "actual_days": len(slice_df),
                }
                continue

            slice_len = len(slice_df)
            dt_first = pd.to_datetime(slice_df.iloc[0]["date"])
            dt_last = pd.to_datetime(slice_df.iloc[-1]["date"])
            actual_cal_days = max(1, (dt_last - dt_first).days)
            cal_days = actual_cal_days

            # 标的全局物理上市天数
            global_first_dt = pd.to_datetime(df.iloc[0]["date"])
            full_cal_days = max(1, (dt_last - global_first_dt).days)

            # 次新 ETF 严格物理有效性判定：全局物理上市日历跨度不足 85% 或交易日数不足 55% 坚决判定为上市不足留空
            is_partial_history = (full_cal_days < int(cal_days_target * 0.85)) or (slice_len < int(cal_days_target * 0.55))
            if is_partial_history:
                period_results[key] = {
                    "is_valid": False,
                    "reason": f"上市未满 (历史仅{slice_len}交易日)",
                    "annual_return": None,
                    "total_return": None,
                    "max_drawdown": None,
                    "calmar_ratio": None,
                    "trade_count": None,
                    "free_shares": None,
                    "base_price": None,
                    "latest_price": float(df.iloc[-1]["close"]),
                    "actual_days": slice_len,
                }
                continue

            # 3. 基准锚点价格 P0 严格采用该切片首日的真实开盘价 (open)
            first_open = slice_df.iloc[0].get("open")
            if pd.notna(first_open) and float(first_open) > 0:
                p0 = float(first_open)
            else:
                p0 = float(slice_df.iloc[0]["close"])

            latest_p = float(slice_df.iloc[-1]["close"])

            # 4. 基于当前切片计算 ATR 自适应步长
            try:
                atr_ratio = self.etf_service._current_atr_ratio(slice_df)
            except Exception:
                atr_ratio = 0.025  # 默认 2.5%

            try:
                composite_steps = self.grid_optimizer.calculate_composite_steps(
                    p0, atr_ratio, adjustment_coefficient=1.0, step_mode=step_mode
                )
                composite_grid = self.composite_grid_calculator.calculate_composite_grid(
                    total_capital, p0, composite_steps, base_position_ratio=0.5,
                    scaling_ratio=scaling_ratio
                )

                backtest_res = self.backtest_engine.run_backtest(
                    daily_df=slice_df,
                    total_capital=total_capital,
                    composite_grid=composite_grid,
                    reinvest_mode=reinvest_mode,
                    trade_mode=trade_mode,
                )

                summary = backtest_res.get("summary", {})
                profit_pool = backtest_res.get("profit_pool", {})

                tot_return = float(summary.get("strategy_return", 0.0) or 0.0)
                ann_return = round(tot_return * (365.0 / cal_days), 2) if cal_days > 0 else tot_return
                mdd = round(float(summary.get("max_drawdown", 0.0) or 0.0), 2)
                calmar = round(ann_return / mdd, 2) if mdd > 0 else (ann_return if ann_return > 0 else 0.0)
                t_count = int(summary.get("total_trades_count", 0) or 0)
                free_sh = int(profit_pool.get("free_shares", 0) or 0)
                longest_underwater = summary.get("longest_underwater_days")

                period_results[key] = {
                    "is_valid": True,
                    "reason": None,
                    "annual_return": ann_return,
                    "total_return": tot_return,
                    "max_drawdown": mdd,
                    "calmar_ratio": calmar,
                    "trade_count": t_count,
                    "free_shares": free_sh,
                    "longest_underwater_days": longest_underwater,
                    "base_price": round(p0, 3),
                    "latest_price": round(latest_p, 3),
                    "actual_days": slice_len,
                }
            except Exception as e:
                logger.warning(f"标的 {clean_code} 周期 {key} 回测异常: {e}")
                period_results[key] = {
                    "is_valid": False,
                    "reason": "回测计算异常",
                    "annual_return": None,
                    "total_return": None,
                    "max_drawdown": None,
                    "calmar_ratio": None,
                    "trade_count": None,
                    "free_shares": None,
                    "base_price": None,
                    "latest_price": round(latest_p, 3),
                    "actual_days": slice_len,
                }

        return {
            "etf_code": clean_code,
            "etf_name": etf_name,
            "sector": sector,
            "total_bars": total_bars,
            "periods": period_results,
            "error": None,
        }

    def run_universe_matrix(
        self,
        instruments: Optional[List[Dict[str, Any]]] = None,
        total_capital: float = 30000.0,
        scaling_ratio: float = 0.10,
        reinvest_mode: str = "pool_shares",
        step_mode: str = "atr",
        workers: int = 8,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> List[Dict[str, Any]]:
        """
        并发运行全选品池多周期矩阵回测
        """
        target_list = instruments or self.get_shoppable_universe()
        total = len(target_list)
        results: List[Dict[str, Any]] = []

        completed = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_to_info = {
                executor.submit(
                    self.run_single_etf_matrix,
                    inst["etf_code"],
                    etf_name=inst.get("etf_name") or inst.get("name", ""),
                    sector=inst.get("sector", ""),
                    total_capital=total_capital,
                    scaling_ratio=scaling_ratio,
                    reinvest_mode=reinvest_mode,
                    step_mode=step_mode,
                ): inst
                for inst in target_list
            }

            for future in as_completed(future_to_info):
                inst = future_to_info[future]
                completed += 1
                try:
                    res = future.result()
                    results.append(res)
                except Exception as exc:
                    logger.error(f"标的 {inst.get('etf_code')} 矩阵回测抛出异常: {exc}")
                    results.append({
                        "etf_code": inst.get("etf_code"),
                        "etf_name": inst.get("etf_name", ""),
                        "sector": inst.get("sector", ""),
                        "total_bars": 0,
                        "periods": {s["key"]: None for s in PERIOD_SPECS},
                        "error": str(exc),
                    })

                if progress_callback:
                    progress_callback(completed, total, inst.get("etf_code", ""))

        # 排序：按 5 年年化降序 (无 5 年有效记录的按 3 年年化排，再按 1 年排)
        def sort_key(item):
            p = item.get("periods", {})
            ret_5y = (p.get("5y") or {}).get("annual_return")
            ret_3y = (p.get("3y") or {}).get("annual_return")
            ret_1y = (p.get("1y") or {}).get("annual_return")
            return (
                ret_5y if ret_5y is not None else -999.0,
                ret_3y if ret_3y is not None else -999.0,
                ret_1y if ret_1y is not None else -999.0,
            )

        results.sort(key=sort_key, reverse=True)
        return results

    def aggregate_sector_rankings(self, matrix_results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        按首页 11 大赛道聚合胜率、平均年化、平均最大回撤与年均成交次数
        """
        sector_groups: Dict[str, List[Dict[str, Any]]] = {s: [] for s in PRIMARY_SECTORS}
        for item in matrix_results:
            sec = item.get("sector")
            if sec in sector_groups:
                sector_groups[sec].append(item)

        sector_stats: List[Dict[str, Any]] = []

        for sector_name in PRIMARY_SECTORS:
            etfs = sector_groups[sector_name]
            total_count = len(etfs)

            # 统计 5 年、3 年、1 年各周期的有效样本
            stat_5y = self._calculate_period_group_stat(etfs, "5y")
            stat_3y = self._calculate_period_group_stat(etfs, "3y")
            stat_1y = self._calculate_period_group_stat(etfs, "1y")

            # 评选 Top Pick 标杆 (优先 5 年有效且年化最高；若无 5 年则选 3 年)
            top_pick = self._select_sector_top_pick(etfs)

            sector_stats.append({
                "sector": sector_name,
                "total_etfs": total_count,
                "stat_5y": stat_5y,
                "stat_3y": stat_3y,
                "stat_1y": stat_1y,
                "top_pick": top_pick,
            })

        # 排序：按 5 年平均年化收益率降序
        sector_stats.sort(
            key=lambda s: s["stat_5y"]["avg_annual_return"] if s["stat_5y"]["valid_count"] > 0 else -999.0,
            reverse=True,
        )
        return sector_stats

    def _calculate_period_group_stat(self, etfs: List[Dict[str, Any]], period_key: str) -> Dict[str, Any]:
        """计算指定赛道在某个周期的统计指标"""
        valid_items = []
        positive_count = 0
        annual_returns = []
        max_drawdowns = []
        trade_counts = []

        for item in etfs:
            p = (item.get("periods") or {}).get(period_key)
            if p and p.get("is_valid") and p.get("annual_return") is not None:
                valid_items.append(item)
                ann = p["annual_return"]
                annual_returns.append(ann)
                if ann > 0:
                    positive_count += 1
                if p.get("max_drawdown") is not None:
                    max_drawdowns.append(p["max_drawdown"])
                if p.get("trade_count") is not None:
                    trade_counts.append(p["trade_count"])

        valid_count = len(valid_items)
        if valid_count == 0:
            return {
                "valid_count": 0,
                "win_rate": None,
                "avg_annual_return": None,
                "avg_max_drawdown": None,
                "avg_trades": None,
            }

        win_rate = round((positive_count / valid_count) * 100, 1)
        avg_ann = round(float(np.mean(annual_returns)), 2)
        avg_mdd = round(float(np.mean(max_drawdowns)), 2) if max_drawdowns else None
        avg_trades = round(float(np.mean(trade_counts)), 1) if trade_counts else None

        return {
            "valid_count": valid_count,
            "win_rate": win_rate,
            "avg_annual_return": avg_ann,
            "avg_max_drawdown": avg_mdd,
            "avg_trades": avg_trades,
        }

    def _select_sector_top_pick(self, etfs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """甄选赛道标杆标的"""
        candidates = []
        for item in etfs:
            p = item.get("periods") or {}
            p5 = p.get("5y")
            p3 = p.get("3y")
            p1 = p.get("1y")

            # 优先看 5 年有效标的
            if p5 and p5.get("is_valid") and p5.get("annual_return") is not None:
                candidates.append((5, p5["annual_return"], p5.get("max_drawdown"), item))
            elif p3 and p3.get("is_valid") and p3.get("annual_return") is not None:
                candidates.append((3, p3["annual_return"], p3.get("max_drawdown"), item))
            elif p1 and p1.get("is_valid") and p1.get("annual_return") is not None:
                candidates.append((1, p1["annual_return"], p1.get("max_drawdown"), item))

        if not candidates:
            return None

        # 排序：优先周期长(5>3>1)，其次年化收益率高
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best = candidates[0]
        period_years, best_ann, best_mdd, best_item = best

        return {
            "etf_code": best_item.get("etf_code"),
            "etf_name": best_item.get("etf_name"),
            "benchmark_period": f"{period_years}年",
            "annual_return": best_ann,
            "max_drawdown": best_mdd,
        }
