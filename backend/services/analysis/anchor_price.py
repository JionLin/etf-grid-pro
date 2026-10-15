"""开网锚点。分位用本次区间的收盘价，双均用 20 日与 60 日均价，都不是指数估值。"""
from typing import Optional, Sequence


def _positive(values: Sequence[float]) -> list:
    cleaned = []
    for value in values or []:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if number > 0:
            cleaned.append(number)
    return cleaned


def price_at_percentile(closes: Sequence[float], percentile: float) -> Optional[float]:
    ordered = sorted(_positive(closes))
    if not ordered:
        return None
    pct = min(100.0, max(0.0, float(percentile)))
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = (len(ordered) - 1) * (pct / 100.0)
    low = int(rank)
    high = min(low + 1, len(ordered) - 1)
    weight = rank - low
    return round(ordered[low] * (1 - weight) + ordered[high] * weight, 3)


def dual_average_price(closes: Sequence[float], short: int = 20, long: int = 60) -> Optional[float]:
    series = _positive(closes)
    if len(series) < short:
        return None
    short_ma = sum(series[-short:]) / short
    window = series[-long:] if len(series) >= long else series
    long_ma = sum(window) / len(window)
    return round((short_ma + long_ma) / 2.0, 3)


def resolve_grid_anchor(
    source: str,
    live_price: float,
    closes: Optional[Sequence[float]] = None,
    manual_price: Optional[float] = None,
    percentile: Optional[float] = None,
    dual_ma_price: Optional[float] = None,
):
    kind = str(source or "market")
    if kind == "percentile":
        price = price_at_percentile(closes or [], 50 if percentile is None else percentile)
        if price is None:
            raise ValueError("收盘价不足以计算分位锚点")
        return price, "收盘价分位"
    if kind == "dual_ma":
        if dual_ma_price is not None and float(dual_ma_price) > 0:
            return round(float(dual_ma_price), 3), "手填双均价"
        price = dual_average_price(closes or [])
        if price is None:
            raise ValueError("收盘价不足以计算双均锚点")
        return price, "双均价"
    if kind in ("manual", "custom") and manual_price is not None and float(manual_price) > 0:
        return round(float(manual_price), 3), "手填价格"
    if manual_price is not None and float(manual_price) > 0 and kind not in ("market", "percentile", "dual_ma"):
        return round(float(manual_price), 3), "手填价格"
    live = float(live_price)
    return round(live, 3), "盘中最新价"
