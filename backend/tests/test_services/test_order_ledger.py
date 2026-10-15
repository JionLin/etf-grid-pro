import pytest

from backend.repositories.ledger_repository import LedgerRepository
from backend.services.analysis.order_ledger import may_fill_today
from services.analysis.order_ledger import StalePostedOrders


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


def _wipe(repo, code):
    conn = repo._connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM grid_ledger_plan WHERE etf_code = %s", (code,))
            row = cursor.fetchone()
            if not row:
                return
            cursor.execute("DELETE FROM grid_ledger_order WHERE plan_id = %s", (row["id"],))
            cursor.execute("DELETE FROM grid_ledger_plan WHERE id = %s", (row["id"],))
        conn.commit()
    finally:
        conn.close()


def test_resave_asks_before_stale_posted_orders_stay_beside_the_new_grid():
    repo = LedgerRepository()
    code = "515241"
    _wipe(repo, code)
    repo.save_plan(code, "测试", 1.25, 0, 0, [
        {"side": "买入", "trigger_price": 1.20, "shares": 500, "note": "小网"},
        {"side": "买入", "trigger_price": 1.05, "shares": 800, "note": "大网"},
    ])
    plan = repo.get_plan(code)
    for item in plan["orders"]:
        repo.set_status(item["id"], "已挂")

    fresh = [
        {"side": "买入", "trigger_price": 1.20, "shares": 500, "note": "小网"},
        {"side": "买入", "trigger_price": 1.10, "shares": 600, "note": "中网"},
    ]
    with pytest.raises(StalePostedOrders) as caught:
        repo.save_plan(code, "测试", 1.25, 0, 0, fresh)
    assert any(round(float(item["trigger_price"]), 3) == 1.05 for item in caught.value.orders)
    untouched = repo.get_plan(code)
    assert {item["status"] for item in untouched["orders"]} == {"已挂"}
    assert any(round(float(item["trigger_price"]), 3) == 1.05 for item in untouched["orders"])

    kept = repo.save_plan(code, "测试", 1.25, 0, 0, fresh, posted_policy="keep")
    by_price = {round(float(item["trigger_price"]), 3): item for item in kept["orders"] if item["status"] != "作废"}
    assert by_price[1.20]["status"] == "已挂"
    assert by_price[1.10]["status"] == "未挂"
    stale = next(item for item in kept["orders"] if round(float(item["trigger_price"]), 3) == 1.05)
    assert stale["status"] == "作废"

    repo.set_status(by_price[1.20]["id"], "已挂")
    voided = repo.save_plan(code, "测试", 1.25, 0, 0, fresh, posted_policy="void")
    live = [item for item in voided["orders"] if item["status"] != "作废"]
    assert all(item["status"] == "未挂" for item in live)
    assert not any(item["status"] == "已挂" for item in voided["orders"])


def test_ledger_keeps_same_price_tracks_on_separate_rows():
    repo = LedgerRepository()
    code = "515242"
    _wipe(repo, code)
    orders = [
        {"side": "买入", "trigger_price": 1.28, "shares": 500, "note": "中网", "rail": "中网"},
        {"side": "买入", "trigger_price": 1.28, "shares": 500, "note": "大网", "rail": "大网"},
    ]
    repo.save_plan(code, "测试", 1.3, 0, 0, orders)
    first = [item for item in repo.get_plan(code)["orders"] if item["status"] != "作废"]
    assert sorted(item["rail"] for item in first) == ["中网", "大网"]
    mid = next(item for item in first if item["rail"] == "中网")
    repo.set_status(mid["id"], "已成")
    second = repo.save_plan(code, "测试", 1.3, 0, 0, list(reversed(orders)))
    live = {item["rail"]: item["status"] for item in second["orders"] if item["status"] != "作废"}
    assert live == {"中网": "已成", "大网": "未挂"}
