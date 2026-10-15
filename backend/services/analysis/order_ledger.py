"""本地挂单账本。状态只在本机数据库里改，不连接券商。"""
from typing import Optional

ORDER_STATUSES = ("未挂", "已挂", "已成", "作废", "待买入")
OPEN_STATUSES = ("未挂", "已挂")
GRID_STATUSES = ("未挂", "已挂", "已成", "作废")


def normalize_side(side: str) -> str:
    text = str(side or "").strip().upper()
    if text in ("BUY", "买入"):
        return "买入"
    if text in ("SELL", "卖出"):
        return "卖出"
    raise ValueError("方向只能是买入或卖出")


def is_base_order(note: str = "", rail: str = "", role: str = "") -> bool:
    if str(role or "") == "base" or str(rail or "") == "底仓":
        return True
    return str(note or "").startswith("底仓")


def normalize_status(status: str) -> str:
    text = str(status or "").strip()
    if text not in ORDER_STATUSES:
        raise ValueError("状态只能是未挂、已挂、已成、作废或待买入")
    return text


def initial_status(note: str = "", rail: str = "", role: str = "") -> str:
    if is_base_order(note, rail, role):
        return "待买入"
    return "未挂"


def order_key(side: str, trigger_price: float, shares: int) -> tuple:
    return (normalize_side(side), round(float(trigger_price), 3), int(shares))


def may_fill_today(
    side: str,
    trigger_price: float,
    current_price: Optional[float],
    status: str,
    note: str = "",
    rail: str = "",
    role: str = "",
) -> bool:
    """未完成的网格单到价时标为今天可能成交。底仓是待买入，不按条件单到价规则判断。"""
    if is_base_order(note, rail, role) or status == "待买入":
        return False
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
