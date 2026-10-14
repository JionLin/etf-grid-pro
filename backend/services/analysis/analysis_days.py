"""分析接口接受的历史窗口。不在名单里的天数必须拒绝，不能悄悄改成 180。"""
from typing import Any, Optional


ALLOWED_ANALYSIS_DAYS = (90, 180, 365, 1825)
DEFAULT_ANALYSIS_DAYS = 180


def resolve_analysis_days(raw_value: Any, default: Optional[int] = None) -> int:
    """解析分析周期。缺省用 180，名单外抛出 ValueError。

    Args:
        raw_value: 请求里的 analysisDays
        default: 空值时的默认天数

    Returns:
        int: 服务端实际采用的天数
    """
    fallback = DEFAULT_ANALYSIS_DAYS if default is None else default
    if raw_value in (None, ""):
        return fallback
    try:
        days = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("分析周期只能是 90、180、365 或 1825 天") from exc
    if days not in ALLOWED_ANALYSIS_DAYS:
        raise ValueError("分析周期只能是 90、180、365 或 1825 天")
    return days
