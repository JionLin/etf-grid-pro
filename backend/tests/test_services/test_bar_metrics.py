"""本地日 K 不够时不能再用名称波幅或当日成交额冒充 ATR 和月均成交。"""
import pandas as pd

from backend.services.data.akshare_client import AkShareClient
from backend.services.data.bar_metrics import INSUFFICIENT_DATA_LABEL, measure_local_metrics


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


def test_classify_does_not_invent_atr_from_name():
    classified = AkShareClient.classify_etf_item("芯片ETF", "512760")
    assert classified["sector"] == "科技芯片"
    assert classified["atr_pct"] is None
    assert classified["elasticity"] == INSUFFICIENT_DATA_LABEL
