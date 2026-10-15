import pytest

from backend.algorithms.grid.optimizer import GridOptimizer
from backend.services.analysis.anchor_price import resolve_grid_anchor


def test_percentile_anchor_uses_the_close_distribution():
    price, label = resolve_grid_anchor("percentile", live_price=9, closes=[1, 2, 3, 4, 5], percentile=50)
    assert price == 3
    assert label == "收盘价分位"
    assert resolve_grid_anchor("percentile", live_price=9, closes=[1, 2, 3, 4, 5], percentile=0)[0] == 1
    assert resolve_grid_anchor("percentile", live_price=9, closes=[1, 2, 3, 4, 5], percentile=100)[0] == 5


def test_dual_ma_prefers_a_manual_price():
    price, label = resolve_grid_anchor("dual_ma", live_price=1.2, closes=[1] * 80, dual_ma_price=1.8)
    assert price == 1.8
    assert label == "手填双均价"


def test_dual_ma_averages_the_short_and_long_windows():
    closes = [1.0] * 40 + [2.0] * 20
    price, label = resolve_grid_anchor("dual_ma", live_price=9, closes=closes)
    assert label == "双均价"
    assert price == 1.667


def test_missing_history_rejects_a_percentile_anchor():
    with pytest.raises(ValueError, match="分位锚点"):
        resolve_grid_anchor("percentile", live_price=1.2, closes=[])


def test_large_rail_name_does_not_claim_valuation():
    steps = GridOptimizer().calculate_composite_steps(1.25, 0.02, step_mode="fixed_eda")
    assert steps["large"]["name"] == "大网 (深档防守)"
    assert "估值" not in steps["large"]["name"]
