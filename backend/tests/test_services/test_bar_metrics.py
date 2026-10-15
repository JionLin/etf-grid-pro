"""本地日 K 不够时不能再用名称波幅或当日成交额冒充 ATR 和月均成交。"""
from datetime import datetime
from unittest.mock import MagicMock

import pandas as pd

from backend.services.data.akshare_client import AkShareClient
from backend.services.data.bar_metrics import INSUFFICIENT_DATA_LABEL, measure_local_metrics
from backend.services.data.t0_rules import is_t0_instrument
from backend.services.data.universe_bar_sync_service import UniverseBarSyncService


def _bars(count: int, amount: float = 50_000_000.0) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=count, freq="B")
    return pd.DataFrame({
        "date": dates,
        "open": [1.0] * count,
        "high": [1.02] * count,
        "low": [0.98] * count,
        "close": [1.0] * count,
        "amount": [amount] * count,
    })


def test_twenty_bars_use_real_atr_and_average_turnover():
    metrics = measure_local_metrics(_bars(20, amount=80_000_000.0))
    assert metrics["atr_sufficient"] is True
    assert metrics["turnover_sufficient"] is True
    assert metrics["atr_pct"] > 0
    assert metrics["elasticity"] != INSUFFICIENT_DATA_LABEL
    assert metrics["amount_ma20_10k"] == 8000.0


def test_unfinished_today_bar_is_excluded_from_atr_and_turnover():
    dates = pd.date_range("2026-09-15", periods=21, freq="B")
    amounts = [80_000_000.0] * 20 + [8_000_000_000.0]
    frame = pd.DataFrame({
        "date": dates,
        "open": [1.0] * 21,
        "high": [1.02] * 21,
        "low": [0.98] * 21,
        "close": [1.0] * 21,
        "amount": amounts,
    })
    before_close = datetime(2026, 10, 13, 11, 30)
    assert dates[-1].strftime("%Y-%m-%d") == "2026-10-13"
    metrics = measure_local_metrics(frame, moment=before_close)
    assert metrics["bar_count"] == 20
    assert metrics["amount_ma20_10k"] == 8000.0
    after_close = measure_local_metrics(frame, moment=datetime(2026, 10, 13, 15, 0))
    assert after_close["bar_count"] == 21
    assert after_close["amount_ma20_10k"] != 8000.0


def test_sync_does_not_store_today_before_close(monkeypatch):
    from backend.services.data import market_clock
    import services.data.market_clock as used_clock

    frozen = datetime(2026, 10, 15, 11, 0, tzinfo=market_clock.SHANGHAI)
    monkeypatch.setattr(market_clock, "shanghai_now", lambda: frozen)
    monkeypatch.setattr(used_clock, "shanghai_now", lambda: frozen)
    frame = pd.DataFrame({
        "trade_date": [pd.Timestamp("2026-10-14"), pd.Timestamp("2026-10-15")],
        "open": [1.0, 1.0],
        "close": [1.1, 1.05],
        "high": [1.2, 1.1],
        "low": [1.0, 0.9],
        "vol": [100.0, 100.0],
        "amount": [1_000_000.0, 9_000_000_000.0],
    })
    client = MagicMock()
    client._get_fallback_kline.return_value = frame
    market_repo = MagicMock()
    market_repo.get_date_range.return_value = {
        "total_count": 0,
        "min_date": None,
        "max_date": None,
    }
    market_repo.save_bars.side_effect = lambda code, bars: len(bars)
    service = UniverseBarSyncService(market_repo=market_repo, pool_repo=MagicMock(), client=client)
    result = service.sync_single_etf("510300", start_date="2026-10-01", end_date="2026-10-15")
    saved = market_repo.save_bars.call_args.args[1]
    assert list(pd.to_datetime(saved["trade_date"]).dt.strftime("%Y-%m-%d")) == ["2026-10-14"]
    assert result["status"] == "synced"


def test_incremental_sync_refetches_when_last_close_is_missing(monkeypatch):
    from backend.services.data import market_clock

    monkeypatch.setattr(
        "services.data.market_clock.shanghai_now",
        lambda: datetime(2026, 10, 15, 16, 0, tzinfo=market_clock.SHANGHAI),
    )
    fresh = pd.DataFrame({
        "trade_date": [pd.Timestamp("2026-10-15")],
        "open": [1.28],
        "close": [1.303],
        "high": [1.31],
        "low": [1.27],
        "vol": [100.0],
        "amount": [1000.0],
    })
    client = MagicMock()
    client._get_fallback_kline.return_value = fresh
    market_repo = MagicMock()
    market_repo.get_date_range.return_value = {
        "total_count": 20,
        "min_date": "2020-03-02",
        "max_date": "2026-10-14",
    }
    market_repo.save_bars.return_value = 1
    service = UniverseBarSyncService(market_repo=market_repo, pool_repo=MagicMock(), client=client)
    result = service.sync_single_etf("515220", is_incremental=True)
    assert result["status"] == "synced"
    market_repo.delete_preclose_session_bars.assert_called_once()
    client._get_fallback_kline.assert_called_once()

    market_repo.get_date_range.return_value["max_date"] = "2026-10-15"
    done = service.sync_single_etf("515220", is_incremental=True)
    assert done["status"] == "skipped"


def test_cash_yield_and_spread_are_ranked_on_separate_scales():
    from backend.services.data.bar_metrics import rank_pool_items

    ordered = rank_pool_items([
        {"etf_code": "588000", "score": 42.0, "score_kind": "spread"},
        {"etf_code": "515220", "score": 8.9, "score_kind": "cash_yield"},
        {"etf_code": "512400", "score": 12.6, "score_kind": "cash_yield"},
        {"etf_code": "510300", "score": 18.0, "score_kind": "spread"},
    ])
    assert [item["etf_code"] for item in ordered] == ["512400", "515220", "588000", "510300"]


def test_rank_score_uses_cash_yield_and_does_not_saturate():
    from backend.services.data.bar_metrics import pool_rank_score
    from backend.services.analysis.backtest_engine import closed_loop_win_rate

    liquid, kind = pool_rank_score(3.0, 80000)
    quieter, _ = pool_rank_score(1.6, 4000)
    assert kind == "spread"
    assert liquid != 98
    assert liquid > quieter
    yielded, yield_kind = pool_rank_score(3.0, 80000, cash_yield=0.126)
    assert yield_kind == "cash_yield"
    assert yielded == 12.6
    assert closed_loop_win_rate([
        {"action": "SELL", "slot_type": "SELL_GRID", "profit": 10},
        {"action": "SELL", "slot_type": "BUY_GRID", "profit": -0.2},
        {"action": "SELL", "slot_type": "BUY_GRID", "profit": 1.5},
    ]) == 50.0
    assert closed_loop_win_rate([
        {"action": "SELL", "slot_type": "SELL_GRID", "profit": 10},
    ]) is None
    from backend.services.analysis.backtest_engine import annualized_cash_yield_pct
    assert annualized_cash_yield_pct(3000, 30000, 365) == 10.0


def test_short_history_is_marked_insufficient():
    metrics = measure_local_metrics(_bars(5))
    assert metrics["atr_sufficient"] is False
    assert metrics["turnover_sufficient"] is False
    assert metrics["atr_pct"] is None
    assert metrics["amount_ma20_10k"] is None
    assert metrics["elasticity"] == INSUFFICIENT_DATA_LABEL


def test_pct_change_uses_previous_close_not_open():
    records = AkShareClient.pct_change_versus_previous_close([
        {"trade_date": "2026-09-11", "open": 1.32, "close": 1.292},
        {"trade_date": "2026-09-10", "open": 1.30, "close": 1.319},
    ])
    by_date = {str(item["trade_date"]): item["pct_chg"] for item in records}
    assert by_date["2026-09-10"] == 0.0
    assert by_date["2026-09-11"] == -2.05


def test_weekend_gap_does_not_hide_a_missing_weekday():
    assert AkShareClient.gap_is_only_weekend("2026-10-16", "2026-10-18") is True
    assert AkShareClient.gap_is_only_weekend("2026-10-15", "2026-10-18") is False


def test_t0_rule_is_shared_by_code_and_name():
    assert is_t0_instrument("159941", "") is True
    assert is_t0_instrument("518880", "黄金ETF") is True
    assert is_t0_instrument("515220", "煤炭ETF国泰") is False
    assert AkShareClient.classify_etf_item("黄金ETF", "518880")["is_t0"] is True
    assert AkShareClient.classify_etf_item("煤炭ETF国泰", "515220")["is_t0"] is False


def test_classify_does_not_invent_atr_from_name():
    classified = AkShareClient.classify_etf_item("芯片ETF", "512760")
    assert classified["sector"] == "科技芯片"
    assert classified["atr_pct"] is None
    assert classified["elasticity"] == INSUFFICIENT_DATA_LABEL
