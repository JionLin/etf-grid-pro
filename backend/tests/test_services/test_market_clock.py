"""上海时区与休市日。"""
from datetime import datetime, timezone

from backend.services.data.market_clock import (
    expected_settled_date,
    gap_is_only_non_trading,
    is_market_closed,
    quote_date_label,
)


def test_utc_clock_converts_to_shanghai_session():
    before_open = datetime(2026, 10, 14, 23, 30, tzinfo=timezone.utc)
    assert quote_date_label(before_open) == "2026-10-14"
    assert is_market_closed(before_open) is False

    at_close = datetime(2026, 10, 15, 7, 0, tzinfo=timezone.utc)
    assert is_market_closed(at_close) is True
    assert quote_date_label(at_close) == "2026-10-15"


def test_holiday_uses_calendar_and_weekend_fallback_stays():
    national_day = ["20260930", "20261008"]
    assert quote_date_label(datetime(2026, 10, 8, 8, 0), national_day) == "2026-09-30"
    assert expected_settled_date(datetime(2026, 10, 7, 16, 0), national_day) == "2026-09-30"
    assert expected_settled_date(datetime(2026, 10, 8, 16, 0), national_day) == "2026-10-08"
    assert expected_settled_date(datetime(2026, 9, 19, 14, 0)) == "2026-09-18"
    assert gap_is_only_non_trading("2026-09-30", "2026-10-07", national_day) is True
    assert gap_is_only_non_trading("2026-10-16", "2026-10-18") is True
    assert gap_is_only_non_trading("2026-10-15", "2026-10-18") is False
