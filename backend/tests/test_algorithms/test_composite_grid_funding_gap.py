"""小资金不够一手时必须跳过档位，不能把 0 股抬成 100 股。"""
from backend.services.analysis.grid_calculator import CompositeGridCalculator


def _steps():
    return {
        "small": {
            "name": "小网",
            "tag": "小网",
            "capital_ratio": 0.20,
            "step_ratio": 0.02,
            "levels_per_side": 5,
        },
        "medium": {
            "name": "中网",
            "tag": "中网",
            "capital_ratio": 0.35,
            "step_ratio": 0.05,
            "levels_per_side": 3,
        },
        "large": {
            "name": "大网",
            "tag": "大网",
            "capital_ratio": 0.45,
            "step_ratio": 0.12,
            "levels_per_side": 2,
        },
    }


def test_ten_thousand_at_six_yuan_does_not_exceed_base_or_cash():
    result = CompositeGridCalculator().calculate_composite_grid(10000, 6.0, _steps())
    ladder = result["merged_ladder"]
    sells = [item for item in ladder if item["action"] == "SELL"]
    buys = [item for item in ladder if item["action"] == "BUY"]

    assert result["funding_gap"]["has_gap"] is True
    assert result["funding_gap"]["skipped_count"] > 0
    assert all(item["shares"] >= 100 and item["shares"] % 100 == 0 for item in ladder)
    assert sum(item["shares"] for item in sells) <= result["base_position"]["shares"]
    assert sum(item["amount"] for item in buys) <= result["liquid_capital"] + 0.01


def test_normal_capital_keeps_hundred_share_lots_without_gap():
    result = CompositeGridCalculator().calculate_composite_grid(100000, 1.3, _steps())
    assert result["funding_gap"]["has_gap"] is False
    assert result["total_levels"] == 20
    assert all(item["shares"] % 100 == 0 and item["shares"] > 0 for item in result["merged_ladder"])
