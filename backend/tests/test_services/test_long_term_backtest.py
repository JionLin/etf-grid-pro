import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from datetime import datetime, timedelta
from backend.services.analysis.etf_analysis_service import ETFAnalysisService
from backend.tests.mysql_gate import skip_without_mysql


class TestLongTermBacktest(unittest.TestCase):
    """验证长周期回测 (最长5年1825天) 与次新 ETF 自适应机制"""

    def setUp(self):
        skip_without_mysql()
        self.service = ETFAnalysisService()
        self.service.akshare_client = MagicMock()
        self.service.suitability_analyzer = MagicMock()
        self.service.grid_optimizer = MagicMock()
        self.service.composite_grid_calculator = MagicMock()
        self.service.backtest_engine = MagicMock()
        self.service.get_etf_basic_info = MagicMock(return_value={'code': '512170', 'name': '医疗ETF'})

    def _generate_mock_df(self, num_days: int, span_days: int = None):
        total_span = span_days if span_days is not None else num_days
        dates = [datetime(2026, 1, 1) - timedelta(days=int(i * total_span / max(1, num_days - 1))) for i in range(num_days)]
        dates.reverse()
        return pd.DataFrame({
            'date': dates,
            'open': [1.0 + (i * 0.001) for i in range(num_days)],
            'high': [1.02 + (i * 0.001) for i in range(num_days)],
            'low': [0.98 + (i * 0.001) for i in range(num_days)],
            'close': [1.01 + (i * 0.001) for i in range(num_days)],
            'volume': [1000000] * num_days,
            'amount': [1000000.0] * num_days,
        })

    def test_long_term_1825_days_backtest_with_full_history(self):
        """测试 1825 天（5年）完整数据回测成功并输出完整 history_meta"""
        # 模拟 1250 个交易日（跨越 1825 日历日）
        mock_df = self._generate_mock_df(1250, span_days=1825)
        self.service.get_historical_data = MagicMock(return_value=mock_df)

        self.service.suitability_analyzer.comprehensive_evaluation.return_value = {
            'atr_analysis': {'current_atr_ratio': 0.025}
        }
        self.service.grid_optimizer.calculate_composite_steps.return_value = {}
        self.service.composite_grid_calculator.calculate_composite_grid.return_value = {}
        self.service.backtest_engine.run_backtest.return_value = {
            'summary': {'total_profit': 12000.0},
            'recent_trades': [],
            'total_trades_all': [],
        }

        res = self.service.run_strategy_backtest(
            etf_code='512170',
            total_capital=100000.0,
            backtest_days=1825,
        )

        self.assertIn('history_meta', res)
        meta = res['history_meta']
        self.assertEqual(meta['requested_days'], 1825)
        self.assertEqual(meta['actual_trading_days'], 1250)
        self.assertFalse(meta['is_partial_history'])
        self.assertIsNone(meta['partial_reason'])
        self.assertEqual(res['summary']['history_meta']['actual_trading_days'], 1250)
        self.assertEqual(meta['anchor_mode'], 'inception_open')
        self.assertAlmostEqual(meta['backtest_base_price'], 1.0, places=2)

    def test_backtest_custom_base_price_override(self):
        """测试指定自定义回测基准价格覆盖生效"""
        mock_df = self._generate_mock_df(365)
        self.service.get_historical_data = MagicMock(return_value=mock_df)
        self.service.suitability_analyzer.comprehensive_evaluation.return_value = {
            'atr_analysis': {'current_atr_ratio': 0.025}
        }
        self.service.grid_optimizer.calculate_composite_steps.return_value = {}
        self.service.composite_grid_calculator.calculate_composite_grid.return_value = {}
        self.service.backtest_engine.run_backtest.return_value = {'summary': {}}

        res = self.service.run_strategy_backtest(
            etf_code='512170',
            total_capital=100000.0,
            backtest_days=365,
            custom_base_price=1.25,
        )

        self.assertEqual(res['history_meta']['anchor_mode'], 'custom')
        self.assertEqual(res['history_meta']['backtest_base_price'], 1.25)
        # 验证传入 calculator 的价格正是 1.25
        self.service.composite_grid_calculator.calculate_composite_grid.assert_called_with(
            100000.0, 1.25, {}, base_position_ratio=0.5, scaling_ratio=0.0
        )

    def test_sub_new_etf_adaptive_handling(self):
        """测试次新 ETF（上市仅 150 天，请求 1095 天）自适应平滑处理，不抛出异常"""
        mock_df = self._generate_mock_df(150)
        self.service.get_historical_data = MagicMock(return_value=mock_df)

        self.service.suitability_analyzer.comprehensive_evaluation.return_value = {
            'atr_analysis': {'current_atr_ratio': 0.025}
        }
        self.service.grid_optimizer.calculate_composite_steps.return_value = {}
        self.service.composite_grid_calculator.calculate_composite_grid.return_value = {}
        self.service.backtest_engine.run_backtest.return_value = {
            'summary': {'total_profit': 2500.0},
            'recent_trades': [],
            'total_trades_all': [],
        }

        res = self.service.run_strategy_backtest(
            etf_code='159999',
            total_capital=50000.0,
            backtest_days=1095,
        )

        self.assertIn('history_meta', res)
        meta = res['history_meta']
        self.assertEqual(meta['requested_days'], 1095)
        self.assertEqual(meta['actual_trading_days'], 150)
        self.assertTrue(meta['is_partial_history'])
        self.assertIsNotNone(meta['partial_reason'])
        self.assertIn('自适应回测全量可用历史', meta['partial_reason'])


if __name__ == '__main__':
    unittest.main()
