import pytest

from backend.repositories.ledger_repository import LedgerRepository
from backend.services.analysis.order_ledger import may_fill_today


def test_may_fill_today_only_flags_open_orders_that_price_has_reached():
    assert may_fill_today("买入", 1.28, 1.25, "已挂") is True
    assert may_fill_today("买入", 1.20, 1.25, "未挂") is False
    assert may_fill_today("卖出", 1.30, 1.31, "未挂") is True
    assert may_fill_today("卖出", 1.40, 1.31, "已挂") is False
    assert may_fill_today("买入", 1.28, 1.20, "已成") is False
    assert may_fill_today("买入", 1.28, 1.20, "作废") is False
    assert may_fill_today("买入", 1.25, 1.25, "待买入", note="底仓，单独下单，不是网格条件单") is False
    assert may_fill_today("买入", 1.25, 1.20, "未挂", note="底仓，单独下单") is False


def test_ledger_keeps_status_and_flags_a_live_order():
    repo = LedgerRepository()
    code = "515229"
    repo.save_plan(code, "测试", 1.25, 1000, 1.25, [
        {"side": "买入", "trigger_price": 1.25, "shares": 1000, "note": "底仓，单独下单，不是网格条件单"},
        {"side": "买入", "trigger_price": 1.28, "shares": 500, "note": "小网"},
        {"side": "卖出", "trigger_price": 1.40, "shares": 300, "note": "小网"},
    ])
    first = repo.get_plan(code, current_price=1.25)
    base = next(item for item in first["orders"] if "底仓" in item["note"])
    assert base["status"] == "待买入"
    assert base["may_fill_today"] is False
    buy = next(item for item in first["orders"] if item["note"] == "小网" and item["side"] == "买入")
    assert buy["may_fill_today"] is True
    repo.set_status(buy["id"], "已挂")
    repo.save_plan(code, "测试", 1.25, 1000, 1.25, [
        {"side": "买入", "trigger_price": 1.25, "shares": 1000, "note": "底仓，单独下单，不是网格条件单"},
        {"side": "买入", "trigger_price": 1.28, "shares": 500, "note": "小网"},
        {"side": "卖出", "trigger_price": 1.40, "shares": 300, "note": "小网"},
    ])
    second = repo.get_plan(code, current_price=1.50)
    kept = next(item for item in second["orders"] if item["note"] == "小网" and item["side"] == "买入")
    assert kept["status"] == "已挂"
    base_again = next(item for item in second["orders"] if "底仓" in item["note"])
    assert base_again["status"] == "待买入"
    assert base_again["may_fill_today"] is False
    sell = next(item for item in second["orders"] if item["side"] == "卖出")
    assert sell["may_fill_today"] is True
    with pytest.raises(ValueError, match="状态只能是"):
        repo.set_status(kept["id"], "成交了")
