"""A 股时钟。无时区的时间按上海墙钟理解，带时区的时间先换到上海。"""
from datetime import datetime, timedelta
from typing import Iterable, Optional, Set

from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MARKET_OPEN = "09:30"
MARKET_CLOSE = "15:00"
SETTLEMENT_CLOCK = (15, 30)


def shanghai_now() -> datetime:
    """当前上海时间。"""
    return datetime.now(SHANGHAI)


def as_shanghai(moment: Optional[datetime] = None) -> datetime:
    """换成上海时间。测试里传入的无时区时间保持原来的钟点。"""
    current = shanghai_now() if moment is None else moment
    if current.tzinfo is None:
        return current.replace(tzinfo=SHANGHAI)
    return current.astimezone(SHANGHAI)


def is_market_closed(moment: Optional[datetime] = None, close_hm: str = MARKET_CLOSE) -> bool:
    """上海时间到达收盘时刻。"""
    return as_shanghai(moment).strftime("%H:%M") >= close_hm


def _trading_day_keys(trading_days: Optional[Iterable[str]]) -> Optional[Set[str]]:
    if not trading_days:
        return None
    return {str(day).replace("-", "")[:8] for day in trading_days}


def is_trading_day(day: datetime, trading_days: Optional[Iterable[str]] = None) -> bool:
    """有交易日历时按日历，否则只排除周六日。"""
    keys = _trading_day_keys(trading_days)
    if keys is None:
        return day.weekday() < 5
    return day.strftime("%Y%m%d") in keys


def quote_date_label(now: datetime, trading_days: Optional[Iterable[str]] = None) -> str:
    """行情所属交易日。开盘前、周末和日历中的休市日沿用上一交易日。"""
    day = as_shanghai(now)
    before_open = day.strftime("%H:%M") < MARKET_OPEN
    if is_trading_day(day, trading_days) and not before_open:
        return day.strftime("%Y-%m-%d")
    if is_trading_day(day, trading_days) and before_open:
        day = day - timedelta(days=1)
    for _ in range(16):
        if is_trading_day(day, trading_days):
            return day.strftime("%Y-%m-%d")
        day = day - timedelta(days=1)
    return day.strftime("%Y-%m-%d")


def expected_settled_date(
    now: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> str:
    """15:30 之后才把当天算进已结算交易日。有日历时休市日继续往前找。"""
    current = as_shanghai(now)
    if trading_days:
        day = current
        before_settle = (day.hour, day.minute) < SETTLEMENT_CLOCK
        if is_trading_day(day, trading_days) and not before_settle:
            return day.strftime("%Y-%m-%d")
        if is_trading_day(day, trading_days) and before_settle:
            day = day - timedelta(days=1)
        for _ in range(16):
            if is_trading_day(day, trading_days):
                return day.strftime("%Y-%m-%d")
            day = day - timedelta(days=1)
        return day.strftime("%Y-%m-%d")

    weekday = current.weekday()
    if weekday == 5:
        target = current - timedelta(days=1)
    elif weekday == 6:
        target = current - timedelta(days=2)
    elif (current.hour, current.minute) < SETTLEMENT_CLOCK:
        target = current - timedelta(days=3 if weekday == 0 else 1)
    else:
        target = current
    return target.strftime("%Y-%m-%d")


def gap_is_only_non_trading(
    local_max: str,
    target_end: str,
    trading_days: Optional[Iterable[str]] = None,
) -> bool:
    """缺口里没有交易日才可以跳过补齐。没日历时交易日等于工作日。"""
    start = datetime.strptime(str(local_max)[:10], "%Y-%m-%d") + timedelta(days=1)
    end = datetime.strptime(str(target_end)[:10], "%Y-%m-%d")
    if start > end:
        return False
    day = start
    while day <= end:
        if is_trading_day(day, trading_days):
            return False
        day += timedelta(days=1)
    return True
