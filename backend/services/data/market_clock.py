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


def session_bar_unfinished(
    trade_date: object,
    moment: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> bool:
    """交易日收盘前，当天这根日 K 还没收完，不能写入日线表或参与 ATR。"""
    now = as_shanghai(moment) if moment is not None else shanghai_now()
    if not is_trading_day(now, trading_days):
        return False
    if now.strftime("%H:%M") >= MARKET_CLOSE:
        return False
    if hasattr(trade_date, "strftime"):
        label = trade_date.strftime("%Y-%m-%d")
    else:
        label = str(trade_date)[:10]
    return label == now.strftime("%Y-%m-%d")


def in_continuous_session(
    moment: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> bool:
    """交易日 09:30 至 15:00 之间。开盘前、收盘后和休市日都不是。"""
    day = as_shanghai(moment)
    clock = day.strftime("%H:%M")
    return is_trading_day(day, trading_days) and MARKET_OPEN <= clock < MARKET_CLOSE


def _positive_number(value: object) -> bool:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return False
    return number == number and number > 0


def spot_quote_unusable(
    price: object,
    turnover: object = None,
    moment: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> bool:
    """开盘前、收盘后、休市日的最新价 <= 0 或成交额为 0，不能当成有效行情。

    成交额缺字段时不据此判无效，避免没有该列的正常报价被丢掉。
    连续竞价里只拒绝非正价格。
    """
    if in_continuous_session(moment, trading_days):
        return not _positive_number(price)
    if not _positive_number(price):
        return True
    if turnover is None:
        return False
    return not _positive_number(turnover)


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
