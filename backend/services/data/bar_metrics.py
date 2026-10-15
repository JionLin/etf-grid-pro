"""用本地日 K 计算 14 日 ATR 和 20 日均成交额。不够长就标数据不足。"""
from datetime import datetime
from typing import Any, Dict, Iterable, Optional

import pandas as pd

try:
    from algorithms.atr.calculator import ATRCalculator
except ImportError:
    from backend.algorithms.atr.calculator import ATRCalculator

try:
    from services.data.market_clock import session_bar_unfinished
except ImportError:
    from backend.services.data.market_clock import session_bar_unfinished


INSUFFICIENT_DATA_LABEL = "数据不足"
ATR_BAR_COUNT = 14
TURNOVER_BAR_COUNT = 20
FAKE_LIST_DATE = "2023前成熟上市"


def elasticity_from_atr(atr_pct: float) -> str:
    """按真实 ATR 百分比划分弹性档。

    Args:
        atr_pct: 14 日 ATR 占价格的百分比

    Returns:
        str: 高弹性、稳健型或低波防守
    """
    if atr_pct >= 3.0:
        return "高弹性"
    if atr_pct >= 2.0:
        return "稳健型"
    return "低波防守"


def _date_column(frame: pd.DataFrame) -> Optional[str]:
    if "trade_date" in frame.columns:
        return "trade_date"
    if "date" in frame.columns:
        return "date"
    return None


def drop_unfinished_session_bar(
    frame: Optional[pd.DataFrame],
    moment: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> Optional[pd.DataFrame]:
    """收盘前丢掉今天这根未完成日 K。历史交易日原样保留。"""
    if frame is None or frame.empty:
        return frame
    column = _date_column(frame)
    if column is None:
        return frame
    keep = [
        not session_bar_unfinished(value, moment, trading_days)
        for value in frame[column].tolist()
    ]
    if all(keep):
        return frame
    return frame.loc[keep].reset_index(drop=True)


def measure_local_metrics(
    frame: Optional[pd.DataFrame],
    moment: Optional[datetime] = None,
    trading_days: Optional[Iterable[str]] = None,
) -> Dict[str, Any]:
    """从本地日 K 读取 ATR 和 20 日均成交额。样本不够时不编造数值。

    Args:
        frame: 含 high/low/close，以及可选 amount 的日 K

    Returns:
        dict: atr_pct、elasticity、amount_ma20_10k 和是否足够
    """
    empty = {
        "atr_pct": None,
        "elasticity": INSUFFICIENT_DATA_LABEL,
        "amount_ma20_10k": None,
        "atr_sufficient": False,
        "turnover_sufficient": False,
        "bar_count": 0,
    }
    if frame is None or frame.empty:
        return empty

    bars = drop_unfinished_session_bar(frame, moment, trading_days)
    if bars is None or bars.empty:
        return empty
    bars = bars.copy()
    if "date" not in bars.columns and "trade_date" in bars.columns:
        bars = bars.rename(columns={"trade_date": "date"})
    empty["bar_count"] = len(bars)

    if "amount" in bars.columns and len(bars) >= TURNOVER_BAR_COUNT:
        average_yuan = float(bars.tail(TURNOVER_BAR_COUNT)["amount"].astype(float).mean())
        empty["amount_ma20_10k"] = round(average_yuan / 10000.0, 2)
        empty["turnover_sufficient"] = True

    if len(bars) < ATR_BAR_COUNT or "date" not in bars.columns:
        return empty
    try:
        calculated = ATRCalculator(period=ATR_BAR_COUNT).calculate_atr(bars)
        atr_pct = round(float(calculated.iloc[-1]["atr_pct"]), 2)
    except (KeyError, TypeError, ValueError):
        return empty
    if atr_pct != atr_pct:
        return empty
    empty["atr_pct"] = atr_pct
    empty["elasticity"] = elasticity_from_atr(atr_pct)
    empty["atr_sufficient"] = True
    return empty
