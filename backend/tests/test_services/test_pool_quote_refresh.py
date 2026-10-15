"""标的池已落库后，首页最新价必须改用实时行情，不能停在建池当日。"""
import threading
from datetime import datetime
from zoneinfo import ZoneInfo
from unittest.mock import MagicMock, patch

import pandas as pd

from backend.services.data.akshare_client import AkShareClient


def _stale_pool():
    items = []
    for index in range(20):
        code = "515220" if index == 0 else f"{510000 + index:06d}"
        items.append({
            "etf_code": code,
            "name": "煤炭ETF国泰" if code == "515220" else f"ETF{code}",
            "sector": "周期资源",
            "latest_price": 1.292 if code == "515220" else 1.0,
            "pct_change": -2.05 if code == "515220" else 0.1,
            "amount_10k": 10000.0,
            "amount_ma20_10k": 9000.0,
            "atr_pct": 2.0,
        })
    return items


def test_cached_pool_replaces_previous_close_with_live_quote():
    """515220 建池快照是 1.292 / -2.05%，实时最新价是 1.303 / +0.85%，昨收不得再当现价。"""
    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    client.pool_repo.get_pool.return_value = _stale_pool()
    spot_rows = [{
        "代码": "sh515220",
        "名称": "煤炭ETF国泰",
        "最新价": 1.303,
        "涨跌幅": 0.851,
        "昨收": 1.292,
    }]

    with patch.object(client, "_load_category_spot_rows", return_value=spot_rows):
        refreshed = client.build_or_get_etf_pool()

    coal = next(item for item in refreshed if item["etf_code"] == "515220")
    assert coal["latest_price"] == 1.303
    assert coal["pct_change"] == 0.851
    assert coal["quote_date"] == AkShareClient.quote_date_label(datetime.now(ZoneInfo("Asia/Shanghai")))
    client.pool_repo.update_quotes.assert_called_once()
    saved = client.pool_repo.update_quotes.call_args.args[0]
    assert ("515220", 1.303, 0.851) in saved


def test_extract_spot_quote_ignores_previous_close_when_latest_missing():
    assert AkShareClient.extract_spot_quote({"代码": "515220", "昨收": 1.292, "涨跌幅": -2.05}) is None
    assert AkShareClient.extract_spot_quote({"代码": "515220", "最新价": 0, "昨收": 1.303, "涨跌幅": 0}) is None


def _price_client():
    client = AkShareClient.__new__(AkShareClient)
    client.cache = MagicMock()
    client._quote_cache = {}
    client._spot_lock = threading.Lock()
    client._spot_frame = None
    client._spot_fetched_at = 0.0
    return client


def _spot_frame():
    return pd.DataFrame([{
        "代码": "515220",
        "名称": "煤炭ETF",
        "最新价": 1.303,
        "昨收": 1.292,
        "涨跌幅": 0.851,
        "成交量": 1000,
        "成交额": 2000,
        "开盘价": 1.30,
        "最高价": 1.31,
        "最低价": 1.29,
        "涨跌额": 0.011,
        "振幅": 1.5,
        "换手率": 1.2,
        "量比": 1.0,
        "IOPV实时估值": 1.303,
        "基金折价率": 0.0,
        "数据日期": "20261015",
        "更新时间": 1,
    }])


def _clock(moment):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment

    return Clock


def test_intraday_day_cache_is_not_served():
    """当天未收盘时，日缓存里的快照不能当成最新价，必须重新拉行情。"""
    client = _price_client()
    client.get_latest_trading_date = MagicMock(return_value="20261015")
    client.cache.get_daily_cache.return_value = {"current_price": 1.292, "pct_change": -2.05}

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 10, 0))), \
         patch.object(client, "_load_spot_frame", return_value=_spot_frame()):
        quote = client.get_latest_price("515220")

    client.cache.get_daily_cache.assert_not_called()
    client.cache.set_daily_cache.assert_not_called()
    assert quote["current_price"] == 1.303


def test_preclose_fallback_quote_is_not_persisted():
    """东财失败走腾讯备用时，15:00 前的报价不能写入当天交易日缓存。"""
    client = _price_client()
    client.get_latest_trading_date = MagicMock(return_value="20261015")
    fallback = {"current_price": 1.303, "pct_change": 0.85}

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 10, 30))), \
         patch.object(client, "_load_spot_frame", side_effect=RuntimeError("eastmoney down")), \
         patch.object(client, "_get_fallback_quote", return_value=fallback):
        quote = client.get_latest_price("515220")

    assert quote["current_price"] == 1.303
    client.cache.set_daily_cache.assert_not_called()


def test_closed_fallback_quote_is_persisted():
    """收盘后的备用行情才允许写入交易日缓存。"""
    client = _price_client()
    client.get_latest_trading_date = MagicMock(return_value="20261015")
    client.cache.get_daily_cache.return_value = None
    fallback = {"current_price": 1.303, "pct_change": 0.85}

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 15, 30))), \
         patch.object(client, "_load_spot_frame", side_effect=RuntimeError("eastmoney down")), \
         patch.object(client, "_get_fallback_quote", return_value=fallback):
        quote = client.get_latest_price("515220")

    assert quote["current_price"] == 1.303
    client.cache.set_daily_cache.assert_called_once_with(
        "20261015", "price", "515220", fallback
    )


def test_weekend_still_serves_previous_close_cache():
    """非交易日读到的是上一交易日收盘缓存，可以继续用。"""
    client = _price_client()
    client.get_latest_trading_date = MagicMock(return_value="20261016")
    cached = {"current_price": 1.303, "pct_change": 0.85}
    client.cache.get_daily_cache.return_value = cached

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 17, 11, 0))), \
         patch.object(client, "_load_spot_frame") as spot:
        quote = client.get_latest_price("515220")

    assert quote is cached
    spot.assert_not_called()


def test_preopen_zero_quote_keeps_stored_price_and_shows_previous_close_date():
    """开盘前新浪最新价和成交额都是 0 时，不覆盖已有价格，并标出上一交易日。"""
    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    pool = _stale_pool()
    pool[0]["latest_price"] = 1.303
    pool[0]["pct_change"] = 0.851
    client.pool_repo.get_pool.return_value = pool
    rows = [{
        "代码": "sh515220",
        "名称": "煤炭ETF国泰",
        "最新价": 0,
        "涨跌幅": 0,
        "成交额": 0,
        "昨收": 1.303,
    }]

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 8, 0))), \
         patch.object(client, "_load_category_spot_rows", return_value=rows):
        refreshed = client.build_or_get_etf_pool()

    coal = next(item for item in refreshed if item["etf_code"] == "515220")
    assert coal["latest_price"] == 1.303
    assert coal["pct_change"] == 0.851
    assert coal["quote_date"] == "2026-10-14"
    client.pool_repo.update_quotes.assert_not_called()


def test_preopen_zero_price_falls_back_to_last_bar_when_stored_price_is_empty():
    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    pool = _stale_pool()
    pool[0]["latest_price"] = 0
    pool[0]["pct_change"] = 0
    client.pool_repo.get_pool.return_value = pool

    def metrics(code):
        if code != "515220":
            return {"last_bar": None}
        return {
            "last_bar": {
                "close": 1.303,
                "trade_date": "2026-10-14",
                "amount_10k": 68047.65,
                "pct_change": 0.85,
            }
        }

    client._local_bar_metrics = metrics
    rows = [{"代码": "sh515220", "最新价": 0, "涨跌幅": 0, "成交额": 0, "昨收": 1.303}]

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 8, 0))), \
         patch.object(client, "_load_category_spot_rows", return_value=rows):
        refreshed = client.build_or_get_etf_pool()

    coal = next(item for item in refreshed if item["etf_code"] == "515220")
    assert coal["latest_price"] == 1.303
    assert coal["pct_change"] == 0.85
    assert coal["quote_date"] == "2026-10-14"
    client.pool_repo.update_quotes.assert_called_once_with([("515220", 1.303, 0.85)])


def test_preopen_rebuild_keeps_names_when_turnover_is_zero():
    """全量重建时，开盘前的 0 成交额不能把池子滤空，价格用最后一根收盘。"""
    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    client.pool_repo.get_pool.return_value = []
    client._local_bar_metrics = lambda _code: {
        "amount_ma20_10k": 67975.81,
        "turnover_sufficient": True,
        "atr_sufficient": True,
        "atr_pct": 2.52,
        "elasticity": "稳健型",
        "last_bar": {
            "close": 1.303,
            "trade_date": "2026-10-14",
            "amount_10k": 68047.65,
            "pct_change": 0.85,
        },
    }
    rows = [{
        "代码": "sh515220",
        "名称": "煤炭ETF国泰",
        "最新价": 0,
        "涨跌幅": 0,
        "成交额": 0,
    }]

    with patch("backend.services.data.akshare_client.datetime", _clock(datetime(2026, 10, 15, 8, 0))), \
         patch.object(client, "_load_category_spot_rows", return_value=rows):
        client.build_or_get_etf_pool(min_amount_10k=1000)

    saved = client.pool_repo.save_pool.call_args.args[0]
    assert saved[0]["etf_code"] == "515220"
    assert saved[0]["latest_price"] == 1.303
    assert saved[0]["pct_change"] == 0.85
    assert saved[0]["amount_10k"] == 68047.65


def test_category_fetch_timeout_falls_back_to_cached_pool():
    import requests

    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    cached = [{"etf_code": "515220", "latest_price": 1.303, "pct_change": 0.851}]
    client.pool_repo.get_pool.return_value = cached

    with patch("requests.get", side_effect=requests.Timeout("slow")) as get:
        result = client.build_or_get_etf_pool(min_amount_10k=1000)

    assert get.call_args.kwargs["timeout"] == 10
    assert result[0]["latest_price"] == 1.303
    assert result[0]["quote_date"]
    client.pool_repo.save_pool.assert_not_called()


def test_quote_date_label_rolls_back_before_open_and_weekend():
    assert AkShareClient.quote_date_label(datetime(2026, 10, 15, 10, 0)) == "2026-10-15"
    assert AkShareClient.quote_date_label(datetime(2026, 10, 12, 8, 0)) == "2026-10-09"
    assert AkShareClient.quote_date_label(datetime(2026, 10, 17, 11, 0)) == "2026-10-16"


def test_quote_date_and_gap_follow_trading_calendar():
    """日历里没有的工作日是休市，不能再当成可交易日。"""
    national_day = ["20260930", "20261008"]
    assert AkShareClient.quote_date_label(datetime(2026, 10, 8, 8, 0), national_day) == "2026-09-30"
    assert AkShareClient.quote_date_label(datetime(2026, 10, 8, 10, 0), national_day) == "2026-10-08"
    assert AkShareClient.gap_is_only_weekend("2026-09-30", "2026-10-07", national_day) is True
    assert AkShareClient.gap_is_only_weekend("2026-09-30", "2026-10-08", national_day) is False
