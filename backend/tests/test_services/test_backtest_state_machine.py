"""
网格回测槽位状态机全场景单元测试
覆盖小网5格上限、连跌防重复买入、反弹做T卖出、模式B留利润与T+1规则
"""

import pytest
import pandas as pd
from backend.services.analysis.backtest_engine import GridBacktestEngine, GridSlot


@pytest.fixture
def mock_composite_grid():
    """构造包含多轨的阶梯参数字典"""
    return {
        "rails": {
            "small": {
                "name": "小网 (高频做T)",
                "tag": "小网",
                "step_ratio": 0.05,
                "buy_levels": [
                    {"level_index": 1, "price": 0.314, "shares": 1700},
                    {"level_index": 2, "price": 0.297, "shares": 1900},
                    {"level_index": 3, "price": 0.280, "shares": 2000},
                    {"level_index": 4, "price": 0.265, "shares": 2100},
                    {"level_index": 5, "price": 0.250, "shares": 2200},
                    {"level_index": 6, "price": 0.235, "shares": 2300},  # 第6格，应被截断
                ],
                "sell_levels": [
                    {"level_index": 1, "price": 0.347, "shares": 1700},
                    {"level_index": 2, "price": 0.365, "shares": 1900},
                    {"level_index": 3, "price": 0.383, "shares": 2000},
                    {"level_index": 4, "price": 0.402, "shares": 2100},
                    {"level_index": 5, "price": 0.422, "shares": 2200},
                    {"level_index": 6, "price": 0.443, "shares": 2300},  # 第6格，应被截断
                ]
            }
        }
    }


def test_grid_slots_limit(mock_composite_grid):
    """测试小网槽位数硬上限截断为 5 档"""
    engine = GridBacktestEngine()
    slots = engine.build_grid_slots(mock_composite_grid, current_price=0.330)
    
    small_buys = [s for s in slots if s.rail == "small" and s.slot_type == "BUY_GRID"]
    small_sells = [s for s in slots if s.rail == "small" and s.slot_type == "SELL_GRID"]
    
    assert len(small_buys) == 5, f"小网买入槽位数应为5，实际为{len(small_buys)}"
    assert len(small_sells) == 5, f"小网卖出槽位数应为5，实际为{len(small_sells)}"
    assert all(s.level <= 5 for s in small_buys)


def test_downward_continuous_drop_no_repeat_buy(mock_composite_grid):
    """测试连跌与低位震荡时，已买槽位上锁，严禁天天重复买入同一档位"""
    engine = GridBacktestEngine()
    # 模拟连跌4天，价格一直在0.29附近低位震荡
    k_lines = [
        {"date": "2026-06-01", "open": 0.330, "high": 0.330, "low": 0.310, "close": 0.312},  # 触发买1 (0.314)
        {"date": "2026-06-02", "open": 0.312, "high": 0.313, "low": 0.295, "close": 0.296},  # 触发买2 (0.297)
        {"date": "2026-06-03", "open": 0.296, "high": 0.300, "low": 0.294, "close": 0.295},  # 低位震荡，不买！
        {"date": "2026-06-04", "open": 0.295, "high": 0.301, "low": 0.293, "close": 0.294},  # 低位震荡，不买！
        {"date": "2026-06-05", "open": 0.294, "high": 0.300, "low": 0.292, "close": 0.293},  # 低位震荡，不买！
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(df, total_capital=100000, composite_grid=mock_composite_grid)
    trades = res["total_trades_all"]
    
    # 总买入笔数应该刚好是 2 笔 (买1 和 买2 各买入 1 次)，绝不能买 5~10 次！
    buy_trades = [t for t in trades if t["action"] == "BUY"]
    assert len(buy_trades) == 2, f"买入笔数应精确为2笔，实际为{len(buy_trades)}"
    assert buy_trades[0]["price"] == 0.314
    assert buy_trades[1]["price"] == 0.297


def test_rebound_sell_profit_calculation(mock_composite_grid):
    """测试探底反弹时成功触发卖出平仓，且逐笔卖出均产生正向利润"""
    engine = GridBacktestEngine()
    k_lines = [
        {"date": "2026-06-01", "open": 0.330, "high": 0.330, "low": 0.310, "close": 0.312},  # 买1 (0.314)
        {"date": "2026-06-02", "open": 0.312, "high": 0.313, "low": 0.295, "close": 0.296},  # 买2 (0.297)
        {"date": "2026-06-03", "open": 0.296, "high": 0.320, "low": 0.295, "close": 0.318},  # 反弹至0.320，冲过0.314触发买2的平仓
        {"date": "2026-06-04", "open": 0.318, "high": 0.335, "low": 0.316, "close": 0.332},  # 继续反弹至0.335，冲过0.330触发买1的平仓
        {"date": "2026-06-05", "open": 0.332, "high": 0.335, "low": 0.330, "close": 0.333},  # 高位震荡
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(df, total_capital=100000, composite_grid=mock_composite_grid)
    trades = res["total_trades_all"]
    
    sell_trades = [t for t in trades if t["action"] == "SELL"]
    assert len(sell_trades) >= 1, "反弹走势中必须成功撮合卖出！"
    
    for st in sell_trades:
        assert st["profit"] > 0, f"做T卖出必须有正向净利润: {st}"
        assert "14:" in st["trade_time"], "卖出时间戳应为午后时间"


def test_mode_b_free_shares_transfer(mock_composite_grid):
    """测试模式B留利润攒免费份额"""
    engine = GridBacktestEngine()
    k_lines = [
        {"date": "2026-06-01", "open": 0.330, "high": 0.330, "low": 0.310, "close": 0.312},
        {"date": "2026-06-02", "open": 0.312, "high": 0.313, "low": 0.295, "close": 0.296},
        {"date": "2026-06-03", "open": 0.296, "high": 0.325, "low": 0.295, "close": 0.320},
        {"date": "2026-06-04", "open": 0.320, "high": 0.335, "low": 0.318, "close": 0.333},
        {"date": "2026-06-05", "open": 0.333, "high": 0.338, "low": 0.330, "close": 0.335},
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(
        df, total_capital=100000, composite_grid=mock_composite_grid, reinvest_mode="pool_shares"
    )
    
    summary = res["summary"]
    pool_info = summary["profit_pool"]
    assert pool_info["enabled"] is True
    assert pool_info["total_profit_accumulated"] > 0


def test_fee_eaten_sell_is_loss_and_excluded_from_win_rate():
    """手续费吃掉价差时记亏损，且不计入做T胜率。"""
    engine = GridBacktestEngine()
    thin_grid = {
        "rails": {
            "small": {
                "name": "小网 (高频做T)",
                "tag": "小网",
                "step_ratio": 0.001,
                "buy_levels": [],
                "sell_levels": [
                    {"level_index": 1, "price": 1.001, "shares": 100},
                ],
            }
        }
    }
    k_lines = [
        {"date": f"2026-06-0{i}", "open": 1.000, "high": 1.002, "low": 1.0005, "close": 1.001}
        for i in range(1, 6)
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(df, total_capital=100000, composite_grid=thin_grid)
    sells = [t for t in res["total_trades_all"] if t["action"] == "SELL"]

    assert len(sells) == 1
    assert sells[0]["profit"] < 0
    assert res["summary"]["win_rate"] == 0.0

    small_rail = next(r for r in res["rail_attribution"] if r["rail"] == "small")
    assert small_rail["profit"] < 0
    assert small_rail["profit_ratio"] != 33.3
    assert small_rail["profit_ratio"] == 0.0


def test_win_rate_is_null_when_no_sells(mock_composite_grid):
    """没有任何卖出时，胜率必须为空，不得显示 100%。"""
    engine = GridBacktestEngine()
    k_lines = [
        {"date": f"2026-06-0{i}", "open": 0.330, "high": 0.332, "low": 0.328, "close": 0.330}
        for i in range(1, 6)
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(df, total_capital=100000, composite_grid=mock_composite_grid)
    sells = [t for t in res["total_trades_all"] if t["action"] == "SELL"]

    assert sells == []
    assert res["summary"]["win_rate"] is None


def test_same_slot_cannot_sell_and_buy_on_one_bar():
    """一根日 K 同时刺破卖价和买价时，同一档不能当天先卖后买。"""
    engine = GridBacktestEngine()
    grid = {
        "rails": {
            "small": {
                "name": "小网 (高频做T)",
                "tag": "小网",
                "step_ratio": 0.05,
                "buy_levels": [],
                "sell_levels": [
                    {"level_index": 1, "price": 1.05, "shares": 100},
                ],
            }
        }
    }
    k_lines = [
        {"date": "2026-06-01", "open": 1.00, "high": 1.10, "low": 0.90, "close": 1.00},
        {"date": "2026-06-02", "open": 1.00, "high": 1.01, "low": 0.90, "close": 0.95},
        {"date": "2026-06-03", "open": 0.95, "high": 0.96, "low": 0.94, "close": 0.95},
        {"date": "2026-06-04", "open": 0.95, "high": 0.97, "low": 0.94, "close": 0.96},
        {"date": "2026-06-05", "open": 0.96, "high": 0.98, "low": 0.95, "close": 0.97},
    ]
    res = engine.run_backtest(
        pd.DataFrame(k_lines), total_capital=100000, composite_grid=grid, trade_mode="t0"
    )
    trades = res["total_trades_all"]
    slot_id = "small_sell_slot_1"
    by_day = {}
    for trade in trades:
        if trade["slot_id"] != slot_id:
            continue
        by_day.setdefault(trade["date"], set()).add(trade["action"])

    assert "SELL" in by_day["2026-06-01"]
    assert "BUY" not in by_day["2026-06-01"]
    assert "BUY" in by_day["2026-06-02"]


def test_t1_lock_protection(mock_composite_grid):
    """测试T+1保护规则：当日买入的同一槽位当日不可卖出"""
    engine = GridBacktestEngine()
    # 当日既探底到0.290又冲高到0.340
    k_lines = [
        {"date": "2026-06-01", "open": 0.330, "high": 0.340, "low": 0.290, "close": 0.310},
        {"date": "2026-06-02", "open": 0.310, "high": 0.335, "low": 0.305, "close": 0.320},
        {"date": "2026-06-03", "open": 0.320, "high": 0.325, "low": 0.315, "close": 0.318},
        {"date": "2026-06-04", "open": 0.318, "high": 0.322, "low": 0.314, "close": 0.316},
        {"date": "2026-06-05", "open": 0.316, "high": 0.320, "low": 0.312, "close": 0.315},
    ]
    df = pd.DataFrame(k_lines)
    res = engine.run_backtest(df, total_capital=100000, composite_grid=mock_composite_grid, trade_mode="t1")
    trades = res["total_trades_all"]
    
    # 2026-06-01 这一天买入的，绝不能在 2026-06-01 当天被卖出
    day1_sells = [t for t in trades if t["date"] == "2026-06-01" and t["action"] == "SELL" and "buy_slot" in t.get("rail_name", "")]
    assert len(day1_sells) == 0, "T+1制度下当日买入的份额当日严禁卖出！"
