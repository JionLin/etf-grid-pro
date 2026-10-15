"""T+0 判定只有这一处。代码表和名称关键词必须一起用。"""
from typing import Tuple


T0_ETF_CODES = {
    "513130",
    "513180",
    "159920",
    "513100",
    "159941",
    "513500",
    "513050",
    "164824",
    "513520",
    "159866",
    "513880",
    "513000",
}

T0_NAME_MARKERS: Tuple[str, ...] = (
    "债", "短融", "存单", "黄金", "豆粕", "能源化工", "白银", "有色期货",
    "金ETF", "上海金", "恒生", "港股", "纳斯达克", "纳指", "标普", "日经",
    "德国", "法国", "美股", "海外", "中概", "亚太", "道琼斯", "巴西", "日本东证",
)


def is_t0_instrument(code: str, name: str = "") -> bool:
    """代码在名单里，或名称命中跨境、债券、商品关键词，都是 T+0。

    Args:
        code: ETF 代码，可带 sh/sz 或交易所后缀
        name: ETF 名称。只有代码时仍可命中代码表

    Returns:
        bool: 是否按 T+0 交易
    """
    raw_code = str(code or "").split(".")[0].replace("sh", "").replace("sz", "").strip()
    if raw_code in T0_ETF_CODES:
        return True
    text = str(name or "")
    return any(marker in text for marker in T0_NAME_MARKERS)
