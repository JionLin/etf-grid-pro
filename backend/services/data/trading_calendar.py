"""交易日历缓存。往年永久保存，当年按上海日期每天重新拉取。"""
from typing import Callable, List, Optional

from .market_clock import as_shanghai


def load_trading_year(
    cache,
    year: int,
    fetch_year: Callable[[int], List[str]],
    today: Optional[str] = None,
) -> List[str]:
    """返回某年交易日。当年不沿用永久缓存，避免停在旧的不完整日历上。"""
    current_day = today or as_shanghai().strftime("%Y%m%d")
    key = str(year)
    is_past_year = year < int(current_day[:4])
    if is_past_year:
        cached = cache.get_permanent_cache("trading_cal", key)
        if isinstance(cached, list) and cached:
            return [str(day) for day in cached]
    else:
        cached = cache.get_daily_cache(current_day, "trading_cal", key)
        if isinstance(cached, list) and cached:
            return [str(day) for day in cached]

    year_data = [str(day) for day in (fetch_year(year) or [])]
    if not year_data:
        return []
    if is_past_year:
        cache.set_permanent_cache("trading_cal", key, year_data)
    else:
        cache.set_daily_cache(current_day, "trading_cal", key, year_data)
        cache.set_permanent_cache("trading_cal", key, year_data)
    return year_data
