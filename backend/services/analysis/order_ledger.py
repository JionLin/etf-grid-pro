"""本地挂单账本。状态只在本机数据库里改，不连接券商。"""
from typing import Optional

ORDER_STATUSES = ("未挂", "已挂", "已成", "作废")
OPEN_STATUSES = ("未挂", "已挂")


def normalize_side(side: str) -> str:
    text = str(side or "").strip().upper()
    if text in ("BUY", "买入"):
        return "买入"
    if text in ("SELL", "卖出"):
        return "卖出"
    raise ValueError("方向只能是买入或卖出")


def normalize_status(status: str) -> str:
    text = str(status or "").strip()
    if text not in ORDER_STATUSES:
        raise ValueError("状态只能是未挂、已挂、已成或作废")
    return text


def order_key(side: str, trigger_price: float, shares: int) -> tuple:
    return (normalize_side(side), round(float(trigger_price), 3), int(shares))


def may_fill_today(side: str, trigger_price: float, current_price: Optional[float], status: str) -> bool:
    """未完成的买单现价已到或低于触发价，卖单现价已到或高于触发价，标为今天可能成交。"""
    if status not in OPEN_STATUSES or current_price is None:
        return False
    try:
        live = float(current_price)
        trigger = float(trigger_price)
    except (TypeError, ValueError):
        return False
    if live <= 0 or trigger <= 0:
        return False
    label = normalize_side(side)
    if label == "买入":
        return live <= trigger
    return live >= trigger
