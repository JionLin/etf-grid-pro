"""近 5 年日 K 是否已经盖住。引导用它判断要不要向前补历史。"""

from datetime import datetime, timedelta
from typing import Optional

from services.data.market_clock import SHANGHAI, as_shanghai

HISTORY_SLACK_DAYS = 45
FIVE_YEAR_EXTRA_DAYS = 5 * 365 + 30
# 单页满载时，东财或腾讯往往停在这一档，后面的历史被截掉。
CAPPED_PAGE_BARS = 630


def five_year_bounds(moment: Optional[datetime] = None) -> tuple:
    """返回近 5 年的日历起止，格式 YYYY-MM-DD。"""
    now = as_shanghai(moment or datetime.now(SHANGHAI)).replace(tzinfo=None)
    end_date = now.strftime("%Y-%m-%d")
    start_date = (now - timedelta(days=FIVE_YEAR_EXTRA_DAYS)).strftime("%Y-%m-%d")
    return start_date, end_date


def history_reaches_window(
    min_date: Optional[str],
    target_start: Optional[str],
    slack_days: int = HISTORY_SLACK_DAYS,
) -> bool:
    """最早一根日 K 已经落到 5 年窗口起点附近。"""
    if min_date is None or target_start is None:
        return False
    try:
        earliest = datetime.strptime(str(min_date)[:10], "%Y-%m-%d")
        start = datetime.strptime(str(target_start)[:10], "%Y-%m-%d")
    except ValueError:
        return False
    return earliest <= start + timedelta(days=slack_days)
