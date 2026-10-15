"""全市场 ETF 日线时序与回测矩阵启动自检与增量自愈服务。
提供非阻塞后台线程调度、MySQL 分布式互斥锁、15:30 交易结算时段判定、
增量日 K 线同步以及级联多周期回测矩阵原子刷新。
"""

import logging
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from repositories.market_data_repository import MarketDataRepository
from repositories.db_config import db_type, sqlite_path
from repositories.mysql_connection import DEFAULT_DATABASE, connect
from repositories.universe_matrix_repository import UniverseMatrixRepository
from services.analysis.universe_matrix_backtest_service import UniverseMatrixBacktestService
from services.data.akshare_client import AkShareClient
from services.data.market_clock import (
    as_shanghai,
    expected_settled_date,
    last_completed_trading_day,
    shanghai_now,
)
from services.data.universe_bar_sync_service import UniverseBarSyncService

logger = logging.getLogger(__name__)

LOCK_NAME = "etf_grid_startup_sync_lock"


def pool_is_backfilling(status: Optional[Dict[str, Any]], item_count: int) -> bool:
    """全市场引导未完成时，即使池子里已经有标的，页面也要显示进度。"""
    snapshot = status or {}
    if snapshot.get("bootstrap_active"):
        return True
    if item_count:
        return False
    if snapshot.get("last_error"):
        return False
    return bool(snapshot.get("backfilling"))


def resume_universe_bootstrap(
    *,
    bootstrap_repo,
    market_repo,
    sync_service,
    list_loader,
    pool_builder,
    workers: int = 5,
    progress_callback=None,
) -> Dict[str, Any]:
    """续传全市场日 K。只拉还没有进度的代码，拉完后重建标的池。"""
    saved = bootstrap_repo.saved_instruments()
    latest = None
    try:
        latest = list_loader() or None
    except Exception as exc:
        logger.warning("拉取全市场名单失败，沿用已保存的名单: %s", exc)
    instruments = latest or saved
    if not instruments:
        return {
            "pending": [],
            "complete": False,
            "synced_now": False,
            "done": 0,
            "total": 0,
            "reason": "empty_market_list",
        }

    bars = set(market_repo.codes_with_bars() or [])
    pending = bootstrap_repo.prepare(instruments, bars)
    progress = bootstrap_repo.progress()
    if not pending:
        return {
            "pending": [],
            "complete": True,
            "synced_now": False,
            "done": progress["done"],
            "total": progress["total"],
        }

    def _record(result, index, total):
        bootstrap_repo.record_result(result)
        if progress_callback:
            progress_callback(result, index, total)

    summary = sync_service.sync_universe(
        instruments=pending,
        is_incremental=False,
        workers=workers,
        progress_callback=_record,
    )
    for result in summary.get("results") or []:
        bootstrap_repo.record_result(result)
    pending_after = bootstrap_repo.pending_instruments()
    try:
        pool_builder(force_refresh=True)
    except Exception as exc:
        logger.warning("引导后续建标的池失败: %s", exc)
    progress = bootstrap_repo.progress()
    return {
        "pending": pending_after,
        "complete": not pending_after,
        "synced_now": True,
        "done": progress["done"],
        "total": progress["total"],
    }


def codes_from_spot_rows(rows: Optional[List[Dict[str, Any]]]) -> List[Dict[str, str]]:
    """从全市场行情行抽出 6 位代码。空池启动时用这份列表回补日 K，不依赖已有标的池。"""
    seen = set()
    instruments: List[Dict[str, str]] = []
    for row in rows or []:
        raw = str(row.get("代码") or row.get("code") or "").lower()
        code = raw.replace("sh", "").replace("sz", "").strip()
        if len(code) != 6 or not code.isdigit() or code in seen:
            continue
        seen.add(code)
        name = str(row.get("名称") or row.get("name") or code).strip() or code
        instruments.append({"etf_code": code, "etf_name": name})
    return instruments


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
        bootstrap_repo=None,
    ):
        if hasattr(self, "_initialized") and self._initialized and market_repo is None:
            return
        from repositories.universe_bootstrap_repository import UniverseBootstrapRepository

        self.market_repo = market_repo or MarketDataRepository()
        self.matrix_repo = matrix_repo or UniverseMatrixRepository()
        self.sync_service = sync_service or UniverseBarSyncService()
        self.matrix_service = matrix_service or UniverseMatrixBacktestService()
        self.client = akshare_client or AkShareClient()
        self.bootstrap_repo = bootstrap_repo or UniverseBootstrapRepository()

        if not hasattr(self, "_status"):
            self._status: Dict[str, Any] = {
                "is_syncing": False,
                "current_stage": "idle",  # idle | checking | syncing_bars | calculating_matrix | completed | failed
                "last_synced_at": None,
                "last_error": None,
                "synced_bars_count": 0,
                "matrix_refreshed": False,
                "backfilling": True,
                "bootstrap_active": False,
                "bootstrap_done": 0,
                "bootstrap_total": 0,
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
        expected_date = last_completed_trading_day(moment, trading_days)

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
        """MySQL 用 GET_LOCK。SQLite 用数据库文件旁的进程锁。"""
        if db_type() == "sqlite":
            return self._acquire_sqlite_lock()
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
        """释放同步锁。"""
        if db_type() == "sqlite":
            self._release_sqlite_lock()
            return
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT RELEASE_LOCK('{LOCK_NAME}')")
        except Exception as e:
            logger.warning("释放 MySQL 分布式锁异常: %s", e)

    def _acquire_sqlite_lock(self) -> bool:
        import fcntl

        path = sqlite_path(DEFAULT_DATABASE).with_suffix(".lock")
        path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(path, "a", encoding="utf-8")
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            handle.close()
            return False
        self._sqlite_lock_handle = handle
        return True

    def _release_sqlite_lock(self) -> None:
        import fcntl

        handle = getattr(self, "_sqlite_lock_handle", None)
        if handle is None:
            return
        try:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            handle.close()
        except Exception as exc:
            logger.warning("释放 SQLite 文件锁异常: %s", exc)
        finally:
            self._sqlite_lock_handle = None

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
            removed = self.market_repo.delete_preclose_session_bars()
            if removed:
                logger.info("已清除 %s 根收盘前写入的当日 K 线，等待正式收盘覆盖。", removed)
            bootstrap = self._resume_bootstrap(workers)
            if bootstrap.get("reason") == "empty_market_list":
                universe = self._current_shoppable_universe()
                if isinstance(universe, list) and len(universe) == 0:
                    logger.warning("标的池为空且市场列表没有代码，跳过日 K 回补。")
                    self._set_status(
                        is_syncing=False,
                        current_stage="idle",
                        backfilling=False,
                        bootstrap_active=False,
                        last_error="市场列表为空，未能回补日K",
                    )
                    return {"status": "skipped", "reason": "empty_market_list"}
            if bootstrap.get("pending"):
                self._remember_bootstrap(bootstrap, active=True)
                self._set_status(is_syncing=False, current_stage="syncing_bars", backfilling=True)
                return {
                    "status": "partial",
                    "reason": "universe_bootstrap_incomplete",
                    "bootstrap": {
                        "done": bootstrap.get("done") or 0,
                        "total": bootstrap.get("total") or 0,
                    },
                }

            freshness = self.check_freshness()
            logger.info("启动数据新鲜度自检: %s", freshness)

            if (
                not force
                and not freshness["needs_bar_sync"]
                and not freshness["needs_matrix_refresh"]
            ):
                logger.info("本地日 K 线时序与回测矩阵已最新 (%s)，无需同步。", freshness["local_max_date"])
                self._remember_bootstrap(bootstrap, active=False)
                self._set_status(is_syncing=False, current_stage="idle", backfilling=False)
                return {"status": "skipped", "reason": "already_up_to_date", "freshness": freshness}

            total_added = 0
            if freshness["needs_bar_sync"] or force:
                self._set_status(current_stage="syncing_bars", backfilling=False, bootstrap_active=False)
                logger.info("→ 启动 ETF 增量时序同步（按已有标的池增量）...")
                sync_res = self.sync_service.sync_universe(
                    instruments=None,
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
                backfilling=False,
                bootstrap_active=False,
                last_error=None,
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
            self._set_status(
                is_syncing=False,
                current_stage="failed",
                last_error=public_error,
                backfilling=False,
            )
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

    def run_full_universe_sync(self, workers: int = 5) -> Dict[str, Any]:
        """同步全市场名单里还没有日 K 的代码，并重建标的池。不跑回测矩阵。"""
        conn = None
        has_lock = False
        try:
            conn = connect(DEFAULT_DATABASE)
            has_lock = self.acquire_distributed_lock(conn)
            if not has_lock:
                logger.info("另一工作进程正在执行同步任务或持有锁，全市场引导跳过。")
                return {"status": "skipped", "reason": "lock_held_by_another_process"}
            self._set_status(
                is_syncing=True,
                current_stage="syncing_bars",
                backfilling=True,
                bootstrap_active=True,
                last_error=None,
            )
            outcome = self._resume_bootstrap(workers)
            active = bool(outcome.get("pending"))
            self._remember_bootstrap(outcome, active=active)
            self._set_status(
                is_syncing=False,
                current_stage="completed" if outcome.get("complete") else "syncing_bars",
                backfilling=active,
            )
            status = "success" if outcome.get("complete") else "partial"
            if outcome.get("reason") == "empty_market_list":
                status = "skipped"
            return {"status": status, **outcome}
        finally:
            if conn:
                if has_lock:
                    self.release_distributed_lock(conn)
                try:
                    conn.close()
                except Exception:
                    pass

    def _resume_bootstrap(self, workers: int) -> Dict[str, Any]:
        outcome = resume_universe_bootstrap(
            bootstrap_repo=self.bootstrap_repo,
            market_repo=self.market_repo,
            sync_service=self.sync_service,
            list_loader=self.codes_from_market_list,
            pool_builder=self.client.build_or_get_etf_pool,
            workers=workers,
        )
        self._remember_bootstrap(outcome, active=not outcome.get("complete"))
        return outcome

    def _remember_bootstrap(self, outcome: Dict[str, Any], active: bool) -> None:
        self._set_status(
            bootstrap_active=active,
            bootstrap_done=outcome.get("done") or 0,
            bootstrap_total=outcome.get("total") or 0,
        )

    def _current_shoppable_universe(self) -> Any:
        getter = getattr(self.sync_service, "get_shoppable_universe", None)
        if not callable(getter):
            return None
        try:
            return getter()
        except Exception as exc:
            logger.warning("读取可购标的池失败: %s", exc)
            return None

    def codes_from_market_list(self) -> List[Dict[str, str]]:
        loader = getattr(self.client, "_load_category_spot_rows", None)
        if not callable(loader):
            return []
        try:
            rows = loader()
        except Exception as exc:
            logger.warning("拉取市场列表失败，无法回补日K: %s", exc)
            return []
        return codes_from_spot_rows(rows)
