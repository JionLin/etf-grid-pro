"""回测步长必须用锚点当日已经知道的 ATR，不能用窗口最后一天。"""
import os
import sys
from pathlib import Path

os.environ.setdefault("TUSHARE_TOKEN", "test_token_12345678901234567890123456")
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pandas as pd
from unittest.mock import MagicMock

from algorithms.atr.analyzer import ATRAnalyzer
from algorithms.atr.calculator import ATRCalculator
from backend.services.analysis.etf_analysis_service import ETFAnalysisService


def _service():
    service = ETFAnalysisService.__new__(ETFAnalysisService)
    service.atr_analyzer = ATRAnalyzer(ATRCalculator(period=14))
    service.resolve_etf_name = lambda code: code
    service.grid_optimizer = MagicMock()
    service.grid_optimizer.calculate_composite_steps.return_value = {}
    service.composite_grid_calculator = MagicMock()
    service.composite_grid_calculator.calculate_composite_grid.return_value = {}
    service.backtest_engine = MagicMock()
    service.backtest_engine.run_backtest.return_value = {"summary": {}}
    return service


def _window():
    dates = pd.date_range("2024-01-01", periods=30, freq="B")
    high = [1.01] * 30
    low = [0.99] * 30
    high[-1] = 1.80
    low[-1] = 0.40
    return pd.DataFrame({
        "date": dates,
        "open": [1.0] * 30,
        "high": high,
        "low": low,
        "close": [1.0] * 30,
    })


def test_backtest_step_uses_anchor_atr_not_window_end():
    service = _service()
    frame = _window()
    service.get_historical_data = MagicMock(return_value=frame)
    anchor = service._anchor_atr_ratio(frame)
    latest = service._current_atr_ratio(frame)
    assert anchor < latest

    service.run_strategy_backtest("515220", 10000, backtest_days=180)
    used = service.grid_optimizer.calculate_composite_steps.call_args.args[1]
    assert used == anchor
    assert used != latest


def test_explicit_atr_ratio_is_kept():
    service = _service()
    service.get_historical_data = MagicMock(return_value=_window())
    service.run_strategy_backtest("515220", 10000, backtest_days=180, atr_ratio=0.03)
    used = service.grid_optimizer.calculate_composite_steps.call_args.args[1]
    assert used == 0.03
