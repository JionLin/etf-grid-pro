import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

from repositories.etf_pool_repository import ETFPoolRepository
from repositories.market_data_repository import MarketDataRepository
from services.data.akshare_client import AkShareClient
from services.data.bar_metrics import drop_unfinished_session_bar
from services.data.market_clock import SHANGHAI, as_shanghai, last_completed_trading_day

logger = logging.getLogger(__name__)


class UniverseBarSyncService:
    """全市场 537 只做 T 成熟 ETF 5 年日线时序同步与审计服务"""

    def __init__(
        self,
        market_repo: Optional[MarketDataRepository] = None,
        pool_repo: Optional[ETFPoolRepository] = None,
        client: Optional[AkShareClient] = None,
    ):
        self.market_repo = market_repo or MarketDataRepository()
        self.pool_repo = pool_repo or ETFPoolRepository()
        self.client = client or AkShareClient()

    def get_shoppable_universe(self) -> List[Dict[str, Any]]:
        """获取全市场 537 只做 T 成熟标的"""
        return self.pool_repo.list_shoppable_universe()

    def get_default_5y_dates(self) -> Tuple[str, str]:
        """计算默认 5 年起止日期 (YYYY-MM-DD)"""
        now = as_shanghai(datetime.now(SHANGHAI)).replace(tzinfo=None)
        end_date = now.strftime("%Y-%m-%d")
        start_date = (now - timedelta(days=5 * 365 + 30)).strftime("%Y-%m-%d")
        return start_date, end_date

    def sync_single_etf(
        self,
        etf_code: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_reload: bool = False,
        is_incremental: bool = False,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        同步单只 ETF 的日线数据，支持断点续传与重试。
        """
        clean_code = etf_code.split(".")[0]
        def_start, def_end = self.get_default_5y_dates()
        target_start = start_date or def_start
        target_end = end_date or def_end

        # 收盘前留下的当天 K 线不能当成已完成，先删掉再判断要不要补。
        self.market_repo.delete_preclose_session_bars(etf_code=clean_code)
        local_stat = self.market_repo.get_date_range(clean_code)
        local_count = local_stat.get("total_count", 0)
        local_min = local_stat.get("min_date")
        local_max = local_stat.get("max_date")
        completed = last_completed_trading_day()

        if not force_reload and local_count > 0 and local_max:
            latest_text = str(local_max)[:10]
            latest_dt = datetime.strptime(latest_text, "%Y-%m-%d")
            if latest_text == completed and (
                is_incremental or local_count >= 1000 or (local_min and local_min <= target_start)
            ):
                return {
                    "etf_code": clean_code,
                    "status": "skipped",
                    "rows_added": 0,
                    "total_rows": local_count,
                    "min_date": local_min,
                    "max_date": local_max,
                    "error": None,
                }
            if is_incremental:
                if latest_text > completed:
                    target_start = completed
                else:
                    target_start = (latest_dt + timedelta(days=1)).strftime("%Y-%m-%d")

        # 通过重试拉取数据
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                # 优先使用 Tencent 备用前复权源（绕过代理且 5 年数据分段完整）
                df = self.client._get_fallback_kline(
                    clean_code,
                    start_date=target_start,
                    end_date=target_end,
                )

                if df is not None and not df.empty:
                    df = drop_unfinished_session_bar(df)
                if df is not None and not df.empty:
                    saved = self.market_repo.save_bars(clean_code, df)
                    updated_stat = self.market_repo.get_date_range(clean_code)
                    return {
                        "etf_code": clean_code,
                        "status": "synced",
                        "rows_added": saved,
                        "total_rows": updated_stat.get("total_count", 0),
                        "min_date": updated_stat.get("min_date"),
                        "max_date": updated_stat.get("max_date"),
                        "error": None,
                    }
                else:
                    # 如果是增量模式，且区间较短，没有新数据可能只是非交易日
                    if is_incremental:
                        return {
                            "etf_code": clean_code,
                            "status": "skipped",
                            "rows_added": 0,
                            "total_rows": local_count,
                            "min_date": local_min,
                            "max_date": local_max,
                            "error": None,
                        }
                    last_error = "拉取到的行情数据为空"
            except Exception as exc:
                last_error = str(exc)
                logger.warning(f"拉取 {clean_code} 第 {attempt} 次失败: {exc}")
                time.sleep(0.3 * attempt)

        return {
            "etf_code": clean_code,
            "status": "failed",
            "rows_added": 0,
            "total_rows": local_count,
            "min_date": local_min,
            "max_date": local_max,
            "error": last_error,
        }

    def sync_universe(
        self,
        instruments: Optional[List[Dict[str, Any]]] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        force_reload: bool = False,
        is_incremental: bool = False,
        workers: int = 5,
        progress_callback: Optional[Callable[[Dict[str, Any], int, int], None]] = None,
    ) -> Dict[str, Any]:
        """
        批量并发同步全市场标的
        """
        target_instruments = instruments or self.get_shoppable_universe()
        total = len(target_instruments)
        results: List[Dict[str, Any]] = []

        completed_count = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            future_to_code = {
                executor.submit(
                    self.sync_single_etf,
                    inst["etf_code"],
                    start_date=start_date,
                    end_date=end_date,
                    force_reload=force_reload,
                    is_incremental=is_incremental,
                ): inst["etf_code"]
                for inst in target_instruments
            }

            for future in as_completed(future_to_code):
                completed_count += 1
                try:
                    res = future.result()
                except Exception as exc:
                    code = future_to_code[future]
                    res = {
                        "etf_code": code,
                        "status": "failed",
                        "rows_added": 0,
                        "total_rows": 0,
                        "min_date": None,
                        "max_date": None,
                        "error": str(exc),
                    }
                results.append(res)
                if progress_callback:
                    progress_callback(res, completed_count, total)

        synced = sum(1 for r in results if r["status"] == "synced")
        skipped = sum(1 for r in results if r["status"] == "skipped")
        failed = [r for r in results if r["status"] == "failed"]

        return {
            "total": total,
            "synced": synced,
            "skipped": skipped,
            "failed_count": len(failed),
            "failed_details": failed,
            "results": results,
        }

    def audit_universe(
        self,
        instruments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        审计 537 只标的在本地 MySQL 的覆盖率与健康状态
        """
        target_instruments = instruments or self.get_shoppable_universe()
        def_start, _ = self.get_default_5y_dates()

        rows = []
        full_covered = 0
        partially_covered = 0
        uncovered = 0
        total_bars = 0

        for inst in target_instruments:
            code = inst["etf_code"]
            stat = self.market_repo.get_date_range(code)
            count = stat.get("total_count", 0)
            min_d = stat.get("min_date")
            max_d = stat.get("max_date")
            total_bars += count

            is_covered_5y = count >= 1150 or (min_d and min_d <= def_start)
            if is_covered_5y:
                full_covered += 1
                health = "健康 (>=5年)"
            elif count > 0:
                partially_covered += 1
                health = f"部分 ({count}日K)"
            else:
                uncovered += 1
                health = "缺失 (0条)"

            rows.append({
                "etf_code": code,
                "name": inst.get("etf_name") or inst.get("name", ""),
                "sector": inst.get("sector", ""),
                "bars_count": count,
                "min_date": min_d or "-",
                "max_date": max_d or "-",
                "health": health,
            })

        return {
            "total_universe": len(target_instruments),
            "full_covered": full_covered,
            "partially_covered": partially_covered,
            "uncovered": uncovered,
            "total_bars_in_db": total_bars,
            "rows": rows,
        }
