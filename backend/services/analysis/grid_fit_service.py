"""网格适合度榜：协议评估、独立存储与补齐任务。不写入个人回测档案。"""
import inspect
import logging
import os
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from repositories.etf_pool_repository import SHOPPABLE_SECTORS
from repositories.grid_fit_repository import GridFitRepository

logger = logging.getLogger(__name__)

PROTOCOL_VERSION = "v1"
PROTOCOL_CAPITAL = 30000.0
PROTOCOL_WINDOW_DAYS = 1825
FULL_SAMPLE_FLOOR_DAYS = 1800  # 容忍 A 股因周末与节假日休市产生的日历日跨度偏差（真实5年日K首尾通常为1815~1822天）
SHORT_SAMPLE_FLOOR_DAYS = 1095
ATR_SELL_FLOOR = 12
EDA_SELL_FLOOR = 2
DRAWDOWN_CEILING = float(os.environ.get("DRAWDOWN_CEILING", 35.0))
DEFAULT_EDA_RATIOS = {"small": 0.05, "medium": 0.15, "large": 0.30}
DEFAULT_ATR_MULTIPLIERS = {"small": 0.6, "medium": 1.2, "large": 2.5}
CASH_NAME_KEYWORDS = ("货币", "日利", "添益", "快钱", "快线", "财富宝")
STEP_MODES = ("atr", "fixed_eda")

_job_lock = threading.Lock()
_state_lock = threading.Lock()
_job_state = {"status": "idle", "error": None}


def annualized_grid_cash_yield(grid_cash_profit: float, calendar_days: int) -> float:
    """做 T 现金利润按本金和日历天数年化。利润为负时结果必须为负。"""
    if calendar_days <= 0:
        return 0.0
    return round(float(grid_cash_profit) / PROTOCOL_CAPITAL * 365.0 / calendar_days, 4)


def classify_protocol_cell(
    step_mode: str,
    calendar_days: int,
    sell_count: int,
    grid_cash_profit: float,
    max_drawdown: float,
) -> Dict[str, Any]:
    """按窗口、成交密度和回撤给单格判定状态。不产生启发式分数。"""
    cash_yield = annualized_grid_cash_yield(grid_cash_profit, calendar_days) if calendar_days > 0 else None
    if calendar_days < SHORT_SAMPLE_FLOOR_DAYS:
        return {
            "status": "not_ready",
            "status_reason": "未就绪",
            "cash_yield": None,
            "rank": None,
        }

    sells_per_year = sell_count * 365.0 / calendar_days
    sell_floor = ATR_SELL_FLOOR if step_mode == "atr" else EDA_SELL_FLOOR
    if sells_per_year < sell_floor:
        return {
            "status": "too_sparse",
            "status_reason": "成交过稀",
            "cash_yield": cash_yield,
            "rank": None,
        }
    if max_drawdown > DRAWDOWN_CEILING:
        return {
            "status": "drawdown",
            "status_reason": "回撤超线",
            "cash_yield": cash_yield,
            "rank": None,
        }
    if calendar_days < FULL_SAMPLE_FLOOR_DAYS:
        return {
            "status": "short_sample",
            "status_reason": "样本短于五年",
            "cash_yield": cash_yield,
            "rank": None,
        }
    return {
        "status": "ranked",
        "status_reason": "已入榜",
        "cash_yield": cash_yield,
        "rank": None,
    }


def assign_sector_ranks(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """名次只在同一赛道、同一已入榜步长列内计算。"""
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        if row.get("status") != "ranked":
            row["rank"] = None
            continue
        key = f"{row.get('sector')}|{row.get('step_mode')}"
        grouped.setdefault(key, []).append(row)
    for peers in grouped.values():
        peers.sort(key=lambda item: item.get("cash_yield") or 0.0, reverse=True)
        for index, item in enumerate(peers, start=1):
            item["rank"] = index
    return rows


def current_job_status() -> Dict[str, Optional[str]]:
    with _state_lock:
        return dict(_job_state)


def build_protocol_callbacks(analysis_service, history_client):
    """协议回测只走引擎。不得调用会自动归档的个人档案接口。"""
    prepared: Dict[str, Dict[str, Any]] = {}

    def sync_history(code: str):
        return history_client.sync_window_history(code, PROTOCOL_WINDOW_DAYS)

    def run_protocol(code: str, step_mode: str) -> Dict[str, Any]:
        cached = prepared.setdefault(code, {})
        if "name" not in cached:
            cached["name"] = analysis_service.resolve_etf_name(code)
        result = analysis_service.run_strategy_backtest(
            etf_code=code,
            total_capital=PROTOCOL_CAPITAL,
            backtest_days=PROTOCOL_WINDOW_DAYS,
            reinvest_mode="pool_shares",
            step_mode=step_mode,
            eda_step_ratios=DEFAULT_EDA_RATIOS if step_mode == "fixed_eda" else None,
            atr_multipliers=DEFAULT_ATR_MULTIPLIERS if step_mode == "atr" else None,
            atr_ratio=cached.get("atr_ratio"),
            etf_name=cached.get("name"),
        )
        meta = result.get("history_meta") or {}
        if meta.get("atr_ratio") is not None:
            cached["atr_ratio"] = meta["atr_ratio"]
        return result

    return sync_history, run_protocol


def protocol_runner_avoids_archive() -> bool:
    source = inspect.getsource(build_protocol_callbacks)
    return "save_run" not in source and "/api/backtest" not in source


class GridFitBoardService:
    """适合度榜查询与补齐任务。回测只走引擎，不调用档案归档。"""

    def __init__(self, repo: Optional[GridFitRepository] = None):
        self.repo = repo or GridFitRepository()

    def list_board(
        self,
        sector: Optional[str] = None,
        sector_map: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        rows = assign_sector_ranks(self._universe_rows(sector_map))
        progress = self.progress_counts(rows)
        display_rows = rows
        if sector and sector != "全部":
            display_rows = [row for row in rows if row.get("sector") == sector]
        instruments = self._group_instruments(display_rows)
        board, short_sample, not_ready, failed, blocked = self._split_instruments(instruments)
        board.sort(key=_atr_sort_key)
        return {
            "board": board,
            "short_sample": short_sample,
            "not_ready": not_ready,
            "failed": failed,
            "blocked": blocked,
            "progress": progress,
            "job": current_job_status(),
        }

    def progress_counts(self, rows: Optional[List[Dict[str, Any]]] = None) -> Dict[str, int]:
        source = rows if rows is not None else self._universe_rows(None)
        instruments = self._group_instruments(source)
        counts = {"ranked": 0, "short_sample": 0, "not_ready": 0, "failed": 0}
        for item in instruments:
            bucket = self._instrument_bucket(item)
            if bucket in counts:
                counts[bucket] += 1
        return counts

    def run_batch(
        self,
        universe: List[Dict[str, str]],
        sync_fn: Callable[[str], Any],
        backtest_fn: Callable[[str, str], Dict[str, Any]],
    ) -> Dict[str, int]:
        """逐只补行情并跑两种协议。单只失败不中断其余标的，也不写个人档案。"""
        for item in universe:
            code = item["etf_code"]
            name = item.get("etf_name") or item.get("name") or code
            sector = item.get("sector")
            if _is_cash_name(name) or sector not in SHOPPABLE_SECTORS:
                continue
            try:
                frame = sync_fn(code)
                calendar_days, fingerprint = _coverage(frame)
            except Exception as exc:
                logger.exception("适合度榜行情同步失败 %s: %s", code, exc)
                self._mark_failed(code, name, sector, "行情同步失败", None)
                continue
            if calendar_days < SHORT_SAMPLE_FLOOR_DAYS:
                self._mark_not_ready(code, name, sector, calendar_days, fingerprint)
                continue
            for step_mode in STEP_MODES:
                previous = self.repo.find_run(code, step_mode, PROTOCOL_VERSION)
                if _can_skip(previous, fingerprint):
                    continue
                try:
                    result = backtest_fn(code, step_mode)
                    self._store_result(code, name, sector, step_mode, result, fingerprint)
                except Exception as exc:
                    logger.exception("适合度榜回测失败 %s %s: %s", code, step_mode, exc)
                    self.repo.upsert_run({
                        "etf_code": code,
                        "etf_name": name,
                        "sector": sector,
                        "step_mode": step_mode,
                        "protocol_version": PROTOCOL_VERSION,
                        "calendar_days": calendar_days,
                        "status": "failed",
                        "status_reason": "回测计算异常",
                        "cash_yield": None,
                        "source_fingerprint": fingerprint,
                    })
        return self.progress_counts()

    def run_representatives(
        self,
        groups: List[tuple],
        sync_fn: Callable[[str], Any],
        backtest_fn: Callable[[str, str], Dict[str, Any]],
        pool_repo,
    ) -> Dict[str, int]:
        """每个小类先跑成交额最高的一只。未入榜时按成交额改试下一只。"""
        for subsector, members in groups:
            chosen = None
            for member in members:
                self.run_batch([member], sync_fn, backtest_fn)
                if chosen is None:
                    chosen = member["etf_code"]
                if self._representative_ranked(member["etf_code"]):
                    chosen = member["etf_code"]
                    break
            if chosen:
                pool_repo.set_subsector_seed(subsector, chosen)
        return self.progress_counts()

    def _representative_ranked(self, code: str) -> bool:
        for step_mode in STEP_MODES:
            row = self.repo.find_run(code, step_mode, PROTOCOL_VERSION)
            if row and row.get("status") == "ranked":
                return True
        return False

    def _universe_rows(self, sector_map: Optional[Dict[str, str]]) -> List[Dict[str, Any]]:
        resolved = []
        for row in self.repo.list_runs(PROTOCOL_VERSION):
            if _is_cash_name(row.get("etf_name")):
                continue
            if sector_map is not None:
                mapped = sector_map.get(row["etf_code"])
                if not mapped:
                    continue
            else:
                mapped = row.get("sector")
            if mapped not in SHOPPABLE_SECTORS:
                continue
            copied = dict(row)
            copied["sector"] = mapped
            resolved.append(copied)
        return resolved

    def _group_instruments(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        by_code: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            item = by_code.setdefault(row["etf_code"], {
                "etf_code": row["etf_code"],
                "etf_name": row.get("etf_name"),
                "sector": row.get("sector"),
                "atr": None,
                "fixed_eda": None,
            })
            item["sector"] = row.get("sector") or item.get("sector")
            if row.get("step_mode") in STEP_MODES:
                item[row["step_mode"]] = row
        return list(by_code.values())

    def _split_instruments(self, instruments: List[Dict[str, Any]]):
        board, short_sample, not_ready, failed, blocked = [], [], [], [], []
        for item in instruments:
            bucket = self._instrument_bucket(item)
            if bucket == "ranked":
                board.append(item)
            elif bucket == "short_sample":
                short_sample.append(item)
            elif bucket == "not_ready":
                not_ready.append(item)
            elif bucket == "failed":
                failed.append(item)
            else:
                blocked.append(item)
        return board, short_sample, not_ready, failed, blocked

    def _instrument_bucket(self, item: Dict[str, Any]) -> str:
        statuses = {
            side.get("status")
            for side in (item.get("atr"), item.get("fixed_eda"))
            if side
        }
        if "ranked" in statuses:
            return "ranked"
        if "failed" in statuses and statuses <= {"failed"}:
            return "failed"
        if "short_sample" in statuses:
            return "short_sample"
        if "not_ready" in statuses:
            return "not_ready"
        if "failed" in statuses:
            return "failed"
        return "blocked"

    def _store_result(self, code, name, sector, step_mode, result, fingerprint):
        summary = result.get("summary") or {}
        meta = result.get("history_meta") or summary.get("history_meta") or {}
        calendar_days = int(meta.get("actual_calendar_days") or 0)
        sell_count = int(summary.get("sell_trades_count") or 0)
        profit = float(summary.get("grid_cash_profit") or 0.0)
        judged = classify_protocol_cell(
            step_mode,
            calendar_days,
            sell_count,
            profit,
            float(summary.get("max_drawdown") or 0.0),
        )
        annual_return = summary.get("annualized_return")
        if annual_return is None and calendar_days > 0:
            annual_return = round(
                float(summary.get("strategy_return") or 0.0) * 365.0 / calendar_days,
                4,
            )
        self.repo.upsert_run({
            "etf_code": code,
            "etf_name": name,
            "sector": sector,
            "step_mode": step_mode,
            "protocol_version": PROTOCOL_VERSION,
            "calendar_days": calendar_days,
            "sell_count": sell_count,
            "grid_cash_profit": profit,
            "cash_yield": judged["cash_yield"],
            "annual_return": annual_return,
            "alpha": summary.get("alpha"),
            "max_drawdown": summary.get("max_drawdown"),
            "status": judged["status"],
            "status_reason": judged["status_reason"],
            "source_fingerprint": fingerprint,
        })

    def _mark_failed(self, code, name, sector, reason, fingerprint):
        for step_mode in STEP_MODES:
            self.repo.upsert_run({
                "etf_code": code,
                "etf_name": name,
                "sector": sector,
                "step_mode": step_mode,
                "protocol_version": PROTOCOL_VERSION,
                "status": "failed",
                "status_reason": reason,
                "cash_yield": None,
                "source_fingerprint": fingerprint,
            })

    def _mark_not_ready(self, code, name, sector, calendar_days, fingerprint):
        for step_mode in STEP_MODES:
            self.repo.upsert_run({
                "etf_code": code,
                "etf_name": name,
                "sector": sector,
                "step_mode": step_mode,
                "protocol_version": PROTOCOL_VERSION,
                "calendar_days": calendar_days,
                "status": "not_ready",
                "status_reason": "未就绪",
                "cash_yield": None,
                "source_fingerprint": fingerprint,
            })


def _atr_sort_key(item: Dict[str, Any]):
    atr = item.get("atr") or {}
    if atr.get("status") != "ranked" or atr.get("cash_yield") is None:
        return (1, 0.0, item.get("etf_code") or "")
    return (0, -float(atr["cash_yield"]), item.get("etf_code") or "")


def _can_skip(previous: Optional[Dict[str, Any]], fingerprint: Optional[str]) -> bool:
    if not previous or not fingerprint:
        return False
    if previous.get("status") == "failed":
        return False
    return previous.get("source_fingerprint") == fingerprint


def _is_cash_name(name: Optional[str]) -> bool:
    text = name or ""
    return any(keyword in text for keyword in CASH_NAME_KEYWORDS)


def _coverage(frame) -> tuple:
    if frame is None:
        return 0, None
    if isinstance(frame, dict):
        return int(frame.get("calendar_days") or 0), frame.get("fingerprint")
    if hasattr(frame, "empty") and frame.empty:
        return 0, None
    date_col = "date" if "date" in frame.columns else "trade_date"
    first = _as_date(frame.iloc[0][date_col])
    last = _as_date(frame.iloc[-1][date_col])
    return int((last - first).days), last.strftime("%Y-%m-%d")


def _as_date(value):
    if hasattr(value, "strftime") and hasattr(value, "year"):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d")


def start_background_batch(universe, sync_fn, backtest_fn, repo=None) -> Dict[str, str]:
    """启动本地补齐任务。已有任务在跑时不重复启动。"""
    if not _job_lock.acquire(blocking=False):
        return {"status": "running"}
    service = GridFitBoardService(repo)
    with _state_lock:
        _job_state["status"] = "running"
        _job_state["error"] = None

    def _worker():
        try:
            service.run_batch(universe, sync_fn, backtest_fn)
            with _state_lock:
                _job_state["status"] = "idle"
        except Exception as exc:
            logger.exception("适合度榜补齐失败: %s", exc)
            with _state_lock:
                _job_state["status"] = "idle"
                _job_state["error"] = "适合度榜补齐失败"
        finally:
            _job_lock.release()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return {"status": "started"}


def start_background_representatives(groups, sync_fn, backtest_fn, pool_repo, repo=None) -> Dict[str, str]:
    """后台按小类顺延代表。已有任务在跑时不重复启动。"""
    if not _job_lock.acquire(blocking=False):
        return {"status": "running"}
    service = GridFitBoardService(repo)
    with _state_lock:
        _job_state["status"] = "running"
        _job_state["error"] = None

    def _worker():
        try:
            service.run_representatives(groups, sync_fn, backtest_fn, pool_repo)
            with _state_lock:
                _job_state["status"] = "idle"
        except Exception as exc:
            logger.exception("适合度榜补齐失败: %s", exc)
            with _state_lock:
                _job_state["status"] = "idle"
                _job_state["error"] = "适合度榜补齐失败"
        finally:
            _job_lock.release()

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return {"status": "started"}
