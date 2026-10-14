"""当年交易日历不能停在永久缓存里。"""
from backend.services.data.trading_calendar import load_trading_year


class _MemoryCache:
    def __init__(self):
        self.permanent = {}
        self.daily = {}

    def get_permanent_cache(self, cache_type, key):
        return self.permanent.get((cache_type, key))

    def set_permanent_cache(self, cache_type, key, data):
        self.permanent[(cache_type, key)] = list(data)

    def get_daily_cache(self, trade_date, cache_type, key):
        return self.daily.get((trade_date, cache_type, key))

    def set_daily_cache(self, trade_date, cache_type, key, data):
        self.daily[(trade_date, cache_type, key)] = list(data)


def test_past_year_is_read_from_permanent_cache():
    cache = _MemoryCache()
    calls = {"n": 0}

    def fetch_year(_year):
        calls["n"] += 1
        return ["20250102"]

    assert load_trading_year(cache, 2025, fetch_year, today="20261015") == ["20250102"]
    assert load_trading_year(cache, 2025, fetch_year, today="20261015") == ["20250102"]
    assert calls["n"] == 1


def test_current_year_ignores_stale_permanent_cache_and_refreshes_next_day():
    cache = _MemoryCache()
    cache.permanent[("trading_cal", "2026")] = ["20260105"]
    calls = {"n": 0}

    def fetch_year(_year):
        calls["n"] += 1
        if calls["n"] == 1:
            return ["20261015"]
        return ["20261015", "20261016"]

    assert load_trading_year(cache, 2026, fetch_year, today="20261015") == ["20261015"]
    assert load_trading_year(cache, 2026, fetch_year, today="20261015") == ["20261015"]
    assert calls["n"] == 1
    assert load_trading_year(cache, 2026, fetch_year, today="20261016") == ["20261015", "20261016"]
    assert calls["n"] == 2
    assert cache.permanent[("trading_cal", "2026")] == ["20261015", "20261016"]
