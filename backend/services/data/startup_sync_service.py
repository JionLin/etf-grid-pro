"""全市场 ETF 日线时序与回测矩阵启动自检与增量自愈服务。
提供非阻塞后台线程调度、MySQL 分布式互斥锁、15:30 交易结算时段判定、
增量日 K 线同步以及级联多周期回测矩阵原子刷新。
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, Optional

from repositories.market_data_repository import MarketDataRepository
from repositories.mysql_connection import DEFAULT_DATABASE, connect
from repositories.universe_matrix_repository import UniverseMatrixRepository
from services.analysis.universe_matrix_backtest_service import UniverseMatrixBacktestService
from services.data.akshare_client import AkShareClient
from services.data.market_clock import as_shanghai, expected_settled_date, shanghai_now
from services.data.universe_bar_sync_service import UniverseBarSyncService

logger = logging.getLogger(__name__)

LOCK_NAME = "etf_grid_startup_sync_lock"


class StartupSyncService:
    """启动自检与增量自愈单例服务。"""

    _instance = None
    _state_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._state_lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        market_repo: Optional[MarketDataRepository] = None,
        matrix_repo: Optional[UniverseMatrixRepository] = None,
        sync_service: Optional[UniverseBarSyncService] = None,
        matrix_service: Optional[UniverseMatrixBacktestService] = None,
        akshare_client: Optional[AkShareClient] = None,
    ):
        if hasattr(self, "_initialized") and self._initialized and market_repo is None:
            return
        self.market_repo = market_repo or MarketDataRepository()
        self.matrix_repo = matrix_repo or UniverseMatrixRepository()
        self.sync_service = sync_service or UniverseBarSyncService()
        self.matrix_service = matrix_service or UniverseMatrixBacktestService()
        self.client = akshare_client or AkShareClient()

        if not hasattr(self, "_status"):
            self._status: Dict[str, Any] = {
                "is_syncing": False,
                "current_stage": "idle",  # idle | checking | syncing_bars | calculating_matrix | completed | failed
                "last_synced_at": None,
                "last_error": None,
                "synced_bars_count": 0,
                "matrix_refreshed": False,
            }
        self._initialized = True

    def get_status(self) -> Dict[str, Any]:
        """获取当前同步状态快照。"""
        with self._state_lock:
            return dict(self._status)

    def _set_status(self, **kwargs):
        with self._state_lock:
            self._status.update(kwargs)

    @staticmethod
    def calculate_expected_settled_date(
        now: Optional[datetime] = None,
        trading_days: Optional[list] = None,
    ) -> str:
        """根据 A 股 15:30 结算规则推算当前应收录的最新交易日 (YYYY-MM-DD)。

        没有交易日历时只排除周末。传入日历后，节假日继续往前找到上一个交易日。
        """
        return expected_settled_date(now, trading_days)

    def check_freshness(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """检查本地日 K 线时序与回测矩阵的新鲜度。"""
        moment = as_shanghai(now) if now is not None else shanghai_now()
        trading_days = None
        loader = getattr(getattr(self, "client", None), "cached_trading_days", None)
        if callable(loader):
            trading_days = loader(moment)
        expected_date = self.calculate_expected_settled_date(now, trading_days)

        # 1. 检查代表性核心标的 510300 及全库的最大收录日期
        range_stat = self.market_repo.get_date_range("510300")
        local_max_date = range_stat.get("max_date")

        needs_bar_sync = False
        if not local_max_date or str(local_max_date)[:10] < expected_date:
            needs_bar_sync = True

        # 2. 检查多周期回测矩阵是否落后
        needs_matrix_refresh = False
        try:
            conn = connect(DEFAULT_DATABASE)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS total, MAX(updated_at) AS last_up FROM universe_matrix_backtest")
                row = cur.fetchone()
                m_row = dict(row) if row else {}
                m_total = m_row.get("total", 0)
                m_last = m_row.get("last_up")
                if m_total == 0:
                    needs_matrix_refresh = True
                elif m_last:
                    last_str = str(m_last)[:10]
                    if local_max_date and last_str < str(local_max_date)[:10]:
                        needs_matrix_refresh = True
            conn.close()
        except Exception as e:
            logger.warning("查询回测矩阵状态异常: %s", e)
            needs_matrix_refresh = True

        return {
            "expected_date": expected_date,
            "local_max_date": local_max_date,
            "needs_bar_sync": needs_bar_sync,
            "needs_matrix_refresh": needs_matrix_refresh or needs_bar_sync,
        }

    def acquire_distributed_lock(self, conn) -> bool:
        """尝试获取 MySQL 命名互斥锁，等待 0 秒立即返回。"""
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT GET_LOCK('{LOCK_NAME}', 0) AS locked")
                row = cur.fetchone()
                if not row:
                    return False
                r_dict = dict(row)
                return bool(r_dict.get("locked") == 1)
        except Exception as e:
            logger.warning("获取 MySQL 分布式锁失败: %s", e)
            return False

    def release_distributed_lock(self, conn) -> None:
        """释放 MySQL 命名互斥锁。"""
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT RELEASE_LOCK('{LOCK_NAME}')")
        except Exception as e:
            logger.warning("释放 MySQL 分布式锁异常: %s", e)

    def run_sync_pipeline(self, workers: int = 5, force: bool = False) -> Dict[str, Any]:
        """执行完整的自检、增量日 K 线同步与回测矩阵级联刷新管道。"""
        conn = None
        has_lock = False
        try:
            conn = connect(DEFAULT_DATABASE)
            has_lock = self.acquire_distributed_lock(conn)
            if not has_lock and not force:
                logger.info("另一工作进程正在执行同步任务或持有锁，当前跳过。")
                return {"status": "skipped", "reason": "lock_held_by_another_process"}

            self._set_status(is_syncing=True, current_stage="checking", last_error=None)
            freshness = self.check_freshness()
            logger.info("启动数据新鲜度自检: %s", freshness)

            if not force and not freshness["needs_bar_sync"] and not freshness["needs_matrix_refresh"]:
                logger.info("本地日 K 线时序与回测矩阵已最新 (%s)，无需同步。", freshness["local_max_date"])
                self._set_status(is_syncing=False, current_stage="idle")
                return {"status": "skipped", "reason": "already_up_to_date", "freshness": freshness}

            # 阶段 1: 增量拉取全市场 537 只 ETF 日 K 线
            total_added = 0
            if freshness["needs_bar_sync"] or force:
                self._set_status(current_stage="syncing_bars")
                logger.info("→ 启动全市场 537 只 ETF 增量时序并发同步...")
                sync_res = self.sync_service.sync_universe(
                    is_incremental=True,
                    workers=workers,
                )
                total_added = sum(r.get("rows_added", 0) for r in sync_res.get("results", []))
                logger.info("✓ 增量同步完成: 成功补录 %d 条最新日线，跳过 %d 只已最新标的", total_added, sync_res.get("skipped", 0))

            # 阶段 2: 内存多周期回测并刷新 universe_matrix_backtest 表
            self._set_status(current_stage="calculating_matrix")
            logger.info("→ 启动全市场多周期回测矩阵级联刷新...")
            t0 = time.time()
            all_matrix_results = self.matrix_service.run_universe_matrix(
                workers=max(4, workers),
                total_capital=30000.0,
                scaling_ratio=0.10,
                reinvest_mode="pool_shares",
                step_mode="atr",
            )
            saved_count = self.matrix_repo.batch_save(all_matrix_results)
            cost_matrix = time.time() - t0
            logger.info("✓ 回测矩阵刷新沉淀成功: 共更新 %d 只标的 (耗时 %.2f 秒)", saved_count, cost_matrix)

            now_str = shanghai_now().strftime("%Y-%m-%d %H:%M:%S")
            self._set_status(
                is_syncing=False,
                current_stage="completed",
                last_synced_at=now_str,
                synced_bars_count=total_added,
                matrix_refreshed=True,
            )
            return {
                "status": "success",
                "synced_at": now_str,
                "synced_bars_count": total_added,
                "matrix_count": saved_count,
            }

        except Exception as e:
            logger.error("启动同步管道执行异常: %s", e, exc_info=True)
            public_error = "启动同步失败，请查看服务端日志"
            self._set_status(is_syncing=False, current_stage="failed", last_error=public_error)
            return {"status": "failed", "error": public_error}
        finally:
            if conn:
                if has_lock:
                    self.release_distributed_lock(conn)
                try:
                    conn.close()
                except Exception:
                    pass

    def start_in_background(self, delay_seconds: float = 3.0, workers: int = 5):
        """以非阻塞 daemon 线程方式启动后台自检与增量同步。"""
        def _worker():
            if delay_seconds > 0:
                time.sleep(delay_seconds)
            try:
                self.run_sync_pipeline(workers=workers)
            except Exception as ex:
                logger.warning("后台同步守护线程未捕获异常: %s", ex)

        thread = threading.Thread(target=_worker, name="StartupSyncDaemon", daemon=True)
        thread.start()
        logger.info("✓ 已激活非阻塞后台启动自检守护线程 (延迟 %.1f 秒调度)", delay_seconds)
        return thread
