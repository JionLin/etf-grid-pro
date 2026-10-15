"""频率偏好要改变 ATR 步长，等额和倒金字塔要改变各档买入股数。"""
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from algorithms.grid.optimizer import GridOptimizer
from backend.services.analysis.grid_calculator import CompositeGridCalculator


def _steps():
    return {
        "small": {
            "name": "小网",
            "tag": "小网",
            "capital_ratio": 1.0,
            "step_ratio": 0.02,
            "levels_per_side": 3,
        }
    }


def test_frequency_changes_atr_step_and_balanced_stays_default():
    optimizer = GridOptimizer()
    balanced = optimizer.calculate_composite_steps(10.0, 0.02, risk_preference="均衡")
    slow = optimizer.calculate_composite_steps(10.0, 0.02, risk_preference="低频")
    fast = optimizer.calculate_composite_steps(10.0, 0.02, risk_preference="高频")

    assert balanced["small"]["step_ratio"] == 0.012
    assert slow["small"]["step_ratio"] > balanced["small"]["step_ratio"]
    assert fast["small"]["step_ratio"] < balanced["small"]["step_ratio"]


def test_equal_amount_keeps_buy_shares_flat_and_scaling_widens_them():
    calculator = CompositeGridCalculator()
    equal = calculator.calculate_composite_grid(1_000_000, 10.0, _steps(), scaling_ratio=0.0)
    scaled = calculator.calculate_composite_grid(1_000_000, 10.0, _steps(), scaling_ratio=0.5)
    equal_amounts = [item["amount"] for item in equal["rails"]["small"]["buy_levels"]]
    scaled_amounts = [item["amount"] for item in scaled["rails"]["small"]["buy_levels"]]

    assert max(equal_amounts) - min(equal_amounts) < 10 * 100
    assert scaled_amounts[-1] > scaled_amounts[0] * 1.5
