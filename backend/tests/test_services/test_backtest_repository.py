import unittest
from backend.repositories.backtest_repository import BacktestRepository
from backend.repositories.mysql_connection import TEST_DATABASE
from backend.repositories.mysql_schema import reset_business_tables
from backend.tests.mysql_gate import skip_without_mysql


class TestBacktestRepository(unittest.TestCase):
    """验证回测档案的存储、列表筛选、详情还原与删除功能"""

    def setUp(self):
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)
        self.repo = BacktestRepository(database=TEST_DATABASE)

    def test_save_and_get_detail_and_list(self):
        mock_result = {
            'summary': {
                'annualized_return': 24.5,
                'max_drawdown': 9.2,
                'total_profit': 15800.5,
                'total_trades': 88,
            },
            'profit_pool': {
                'free_shares': 500,
            },
            'equity_curve': [{'date': '2025-01-01', 'nav': 1.0}],
            'total_trades_all': [
                {'trade_time': '2025-01-02 10:15', 'action': 'BUY', 'rail': 'small', 'profit': 0.0},
                {'trade_time': '2025-01-03 14:12', 'action': 'SELL', 'rail': 'small', 'profit': 150.0},
            ],
            'history_meta': {
                'requested_days': 365,
                'actual_trading_days': 242,
                'is_partial_history': False,
            }
        }

        # 1. 保存记录
        run_id = self.repo.save_run(
            etf_code='512170',
            etf_name='医疗ETF',
            backtest_days=365,
            total_capital=100000.0,
            step_mode='atr',
            reinvest_mode='pool_shares',
            backtest_result=mock_result,
            params={'reinvestMode': 'pool_shares'},
        )
        self.assertTrue(run_id.startswith('run_'))

        # 2. 列表查询
        list_res = self.repo.list_runs(etf_code='512170')
        self.assertEqual(list_res['total'], 1)
        self.assertEqual(len(list_res['records']), 1)
        rec = list_res['records'][0]
        self.assertNotIn('equity_curve', rec)
        self.assertNotIn('trades', rec)
        self.assertEqual(rec['run_id'], run_id)
        self.assertEqual(rec['annual_return'], 24.5)
        self.assertEqual(rec['free_shares'], 500)
        self.assertEqual(rec['total_trades'], 88)

        # 3. 详情获取与无损还原
        detail = self.repo.get_run_detail(run_id)
        self.assertIsNotNone(detail)
        self.assertEqual(detail['etf_code'], '512170')
        self.assertEqual(len(detail['trades']), 2)
        self.assertEqual(detail['trades'][1]['profit'], 150.0)
        self.assertEqual(detail['equity_curve'][0]['nav'], 1.0)
        self.assertEqual(detail['params']['reinvestMode'], 'pool_shares')

        # 4. 去重标的查询
        etfs = self.repo.get_distinct_etfs()
        self.assertEqual(len(etfs), 1)
        self.assertEqual(etfs[0]['etf_code'], '512170')

        # 5. 删除记录
        deleted = self.repo.delete_run(run_id)
        self.assertTrue(deleted)
        self.assertIsNone(self.repo.get_run_detail(run_id))
        self.assertEqual(self.repo.list_runs()['total'], 0)

    def test_deduplication_latest_only(self):
        """测试同一标的同一周期去重仅展示最新一条"""
        mock_result_1 = {
            'summary': {'annualized_return': 10.0, 'total_profit': 1000.0},
            'profit_pool': {'free_shares': 0},
            'equity_curve': [],
            'total_trades_all': []
        }
        mock_result_2 = {
            'summary': {'annualized_return': 15.0, 'total_profit': 1500.0},
            'profit_pool': {'free_shares': 0},
            'equity_curve': [],
            'total_trades_all': []
        }

        # 插入两条同标的、同周期(180天)的记录
        id_1 = self.repo.save_run('512170', '医疗ETF', 180, 50000.0, 'atr', 'cash', mock_result_1)
        id_2 = self.repo.save_run('512170', '医疗ETF', 180, 50000.0, 'atr', 'cash', mock_result_2)

        # 1. 默认去重 (latest_only=True)
        res_dedup = self.repo.list_runs(etf_code='512170', latest_only=True)
        self.assertEqual(res_dedup['total'], 1)
        self.assertEqual(len(res_dedup['records']), 1)
        self.assertEqual(res_dedup['records'][0]['run_id'], id_2)
        self.assertEqual(res_dedup['records'][0]['annual_return'], 15.0)

        # 2. 全量查看 (latest_only=False)
        res_all = self.repo.list_runs(etf_code='512170', latest_only=False)
        self.assertEqual(res_all['total'], 2)
        self.assertEqual(len(res_all['records']), 2)

    def test_save_run_grid_cash_profit_and_strategy_return(self):
        """测试使用真实回测引擎的 grid_cash_profit 与 strategy_return 正常入库非 0"""
        mock_engine_result = {
            'summary': {
                'strategy_return': 12.5,
                'grid_cash_profit': 2888.50,
                'max_drawdown': 5.2,
                'total_trades_count': 50
            },
            'history_meta': {
                'actual_calendar_days': 182,
                'actual_trading_days': 120
            },
            'profit_pool': {'free_shares': 200},
            'equity_curve': [],
            'total_trades_all': []
        }
        run_id = self.repo.save_run('510300', '沪深300ETF', 180, 100000.0, 'atr', 'cash', mock_engine_result)
        rec = self.repo.list_runs(etf_code='510300', latest_only=False)['records'][0]
        
        # 验证做 T 纯利润准确提取
        self.assertEqual(rec['total_profit'], 2888.50)
        # 验证复利年化收益率折算 CAGR ((1+0.125)^(365/182)-1) ≈ 26.64
        self.assertAlmostEqual(rec['annual_return'], 26.6, places=1)
        self.assertEqual(rec['total_trades'], 50)

    def test_save_run_dedup_same_result_skips_insert(self):
        """测试同参数同结果的重复回测保存被幂等跳过，不再产生新档案行"""
        mock_result = {
            'summary': {
                'annualized_return': 10.0,
                'total_profit': 1000.0,
                'max_drawdown': 3.2,
                'total_trades_count': 12,
            },
            'profit_pool': {'free_shares': 0},
            'equity_curve': [{'date': '2025-01-01', 'nav': 1.0}],
            'total_trades_all': [],
            'history_meta': {'actual_calendar_days': 180},
        }

        id_1 = self.repo.save_run('515880', '通信ETF', 180, 50000.0, 'atr', 'cash', mock_result)
        id_2 = self.repo.save_run('515880', '通信ETF', 180, 50000.0, 'atr', 'cash', mock_result)

        # 同结果重复保存应返回同一 run_id，且库中仅 1 条
        self.assertEqual(id_1, id_2)
        runs = self.repo.list_runs(etf_code='515880', latest_only=False)
        self.assertEqual(runs['total'], 1)
        self.assertEqual(runs['records'][0]['run_id'], id_1)

        # 不同结果（参数变化导致结果不同）仍应新增
        mock_other = dict(mock_result)
        mock_other['summary'] = dict(mock_result['summary'], total_profit=2000.0)
        id_3 = self.repo.save_run('515880', '通信ETF', 180, 50000.0, 'atr', 'cash', mock_other)
        self.assertNotEqual(id_1, id_3)
        self.assertEqual(self.repo.list_runs(etf_code='515880', latest_only=False)['total'], 2)

    def test_list_runs_sorted_by_longest_period_desc(self):
        """测试档案库列表严格按照回测周期最长(backtest_days DESC)倒序排列"""
        dummy_result = {
            'summary': {'annualized_return': 10.0, 'total_profit': 1000.0},
            'profit_pool': {'free_shares': 0},
            'equity_curve': [],
            'total_trades_all': []
        }
        # 故意打乱顺序插入：90天、1825天(5年)、365天(1年)、1095天(3年)
        self.repo.save_run('515220', '煤炭ETF', 90, 50000.0, 'atr', 'cash', dummy_result)
        self.repo.save_run('515220', '煤炭ETF', 1825, 50000.0, 'atr', 'cash', dummy_result)
        self.repo.save_run('515220', '煤炭ETF', 365, 50000.0, 'atr', 'cash', dummy_result)
        self.repo.save_run('515220', '煤炭ETF', 1095, 50000.0, 'atr', 'cash', dummy_result)

        # 1. 验证 latest_only=True 时的倒序规则
        runs_latest = self.repo.list_runs(etf_code='515220', latest_only=True)['records']
        days_seq = [r['backtest_days'] for r in runs_latest]
        self.assertEqual(days_seq, [1825, 1095, 365, 90])

        # 2. 验证 latest_only=False 时的倒序规则
        runs_all = self.repo.list_runs(etf_code='515220', latest_only=False)['records']
        days_all_seq = [r['backtest_days'] for r in runs_all]
        self.assertEqual(days_all_seq, [1825, 1095, 365, 90])

    def test_save_run_created_at_is_local_time_and_migration(self):
        """测试新保存记录的时间戳为当前本地时间，且迁移自愈能自动修复UTC偏差旧记录"""
        from datetime import datetime
        dummy_result = {
            'summary': {'strategy_return': 8.0, 'grid_cash_profit': 800.0},
            'profit_pool': {'free_shares': 0},
            'equity_curve': [],
            'total_trades_all': []
        }
        now_local = datetime.now()
        run_id = self.repo.save_run('510300', '沪深300', 180, 50000.0, 'atr', 'cash', dummy_result)
        rec = self.repo.get_run_detail(run_id)
        self.assertIsNotNone(rec)
        assert rec is not None
        # 验证包含当前本地日期和小时
        self.assertIn(now_local.strftime('%Y-%m-%d'), rec['created_at'])
        self.assertIn(f"{now_local.hour:02d}:", rec['created_at'])

        # 模拟一条因历史 SQLite 导致落后 8 小时的记录
        fake_run_id = "run_20260912_200000_123456"
        utc_created_at = "2026-09-12 12:00:00"  # 落后 8 小时
        conn = self.repo._connect()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO backtest_run (
                        run_id, etf_code, etf_name, backtest_days, actual_days,
                        total_capital, step_mode, step_bucket, reinvest_mode,
                        annual_return, max_drawdown, total_profit, total_trades, free_shares,
                        is_partial_history, params_json, summary_json, created_at, is_latest
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    fake_run_id, '510300', '沪深300', 180, 180,
                    50000.0, 'atr', 'atr', 'cash',
                    8.0, 5.0, 800.0, 10, 0,
                    0, '{}', '{}', utc_created_at, 0
                ))
            conn.commit()
        finally:
            conn.close()

        # 触发时区自愈迁移
        self.repo.migrate_fix_timezone_offset()

        # 验证修复后的小时被校正为 20 点
        rec_fixed = self.repo.get_run_detail(fake_run_id)
        self.assertIsNotNone(rec_fixed)
        assert rec_fixed is not None
        self.assertEqual(rec_fixed['created_at'], "2026-09-12 20:00:00")

    def test_sector_filter_keeps_unpooled_out_of_shoppable(self):
        mock = {'summary': {'annualized_return': 1.0, 'grid_cash_profit': 10}, 'history_meta': {'actual_calendar_days': 180}}
        self.repo.save_run('515220', '煤炭ETF', 180, 30000, 'atr', 'pool_shares', mock)
        self.repo.save_run('511360', '短融ETF', 180, 30000, 'atr', 'pool_shares', mock)
        sector_map = {'515220': '周期资源'}

        coal = self.repo.list_runs(sector='周期资源', sector_map=sector_map, latest_only=False)
        self.assertEqual([item['etf_code'] for item in coal['records']], ['515220'])

        unpooled = self.repo.list_runs(sector='未入池', sector_map=sector_map, latest_only=False)
        self.assertEqual([item['etf_code'] for item in unpooled['records']], ['511360'])
        self.assertNotIn('511360', [item['etf_code'] for item in coal['records']])

    def test_latest_only_keeps_both_step_modes_and_hides_unknown_from_atr(self):
        mock = {'summary': {'annualized_return': 1.0, 'grid_cash_profit': 10}, 'history_meta': {'actual_calendar_days': 180}}
        self.repo.save_run('515220', '煤炭ETF', 1825, 30000, 'atr', 'pool_shares', mock)
        self.repo.save_run('515220', '煤炭ETF', 180, 30000, 'atr', 'pool_shares', mock)
        self.repo.save_run('515220', '煤炭ETF', 180, 30000, 'atr', 'pool_shares', mock)
        self.repo.save_run('515220', '煤炭ETF', 180, 30000, 'fixed_eda', 'pool_shares', mock)
        self.repo.save_run('515220', '煤炭ETF', 180, 30000, 'composite', 'pool_shares', mock)

        both = self.repo.list_runs(etf_code='515220', latest_only=True)
        modes = {(item['backtest_days'], item['step_mode']) for item in both['records']}
        self.assertIn((180, 'atr'), modes)
        self.assertIn((180, 'fixed_eda'), modes)
        self.assertEqual(both['records'][0]['backtest_days'], 1825)

        atr_only = self.repo.list_runs(etf_code='515220', step_mode='atr', latest_only=True)
        self.assertTrue(all(item['step_mode'] == 'atr' for item in atr_only['records']))
        self.assertTrue(all(item['step_label'] != '未知' for item in atr_only['records']))


if __name__ == '__main__':
    unittest.main()
