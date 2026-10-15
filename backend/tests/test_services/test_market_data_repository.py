import unittest
from datetime import datetime
from unittest.mock import patch

import pandas as pd
from backend.repositories.market_data_repository import MarketDataRepository
from backend.repositories.mysql_connection import TEST_DATABASE
from backend.repositories.mysql_schema import reset_business_tables
from backend.tests.mysql_gate import skip_without_mysql


class TestMarketDataRepository(unittest.TestCase):
    def setUp(self):
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)
        self.repo = MarketDataRepository(database=TEST_DATABASE)

    def test_save_and_query_bars(self):
        """测试日 K 线的保存与按区间切片查询"""
        records = [
            {"trade_date": "2024-01-02", "open": 1.0, "close": 1.02, "high": 1.03, "low": 0.99, "vol": 1000, "amount": 10000, "pct_chg": 2.0},
            {"trade_date": "2024-01-03", "open": 1.02, "close": 1.01, "high": 1.04, "low": 1.00, "vol": 1200, "amount": 12000, "pct_chg": -0.98},
            {"trade_date": "2024-01-04", "open": 1.01, "close": 1.05, "high": 1.06, "low": 1.01, "vol": 1500, "amount": 15500, "pct_chg": 3.96},
        ]
        saved = self.repo.save_bars("515220", records)
        self.assertEqual(saved, 3)

        # 查询全量
        df_all = self.repo.get_bars("515220")
        self.assertEqual(len(df_all), 3)
        self.assertEqual(df_all.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2024-01-02")
        self.assertEqual(df_all.iloc[-1]["trade_date"].strftime("%Y-%m-%d"), "2024-01-04")

        # 测试区间切片
        df_slice = self.repo.get_bars("515220", start_date="20240103", end_date="20240104")
        self.assertEqual(len(df_slice), 2)
        self.assertEqual(df_slice.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2024-01-03")

    def test_date_range_ignores_trading_day_limit(self):
        """已给定起止日期时，不得用 limit 截掉区间内更早的 K 线。"""
        records = [
            {"trade_date": "2024-01-02", "open": 1.0, "close": 1.02},
            {"trade_date": "2024-01-03", "open": 1.02, "close": 1.01},
            {"trade_date": "2024-01-04", "open": 1.01, "close": 1.05},
        ]
        self.repo.save_bars("515220", records)

        df_slice = self.repo.get_bars(
            "515220", start_date="2024-01-02", end_date="2024-01-04", limit=1
        )
        self.assertEqual(len(df_slice), 3)
        self.assertEqual(df_slice.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2024-01-02")

    def test_idempotent_replace_and_range(self):
        """测试相同交易日幂等覆盖与起止范围获取"""
        # 第一次写入
        self.repo.save_bars("515220", [
            {"trade_date": "2024-01-02", "open": 1.0, "close": 1.02}
        ])
        
        # 重复写入同一天但更新价格
        self.repo.save_bars("515220", [
            {"trade_date": "2024-01-02", "open": 1.0, "close": 1.08}
        ])

        df = self.repo.get_bars("515220")
        self.assertEqual(len(df), 1)
        self.assertEqual(float(df.iloc[0]["close"]), 1.08)

        # 增加后续日期
        self.repo.save_bars("515220", [
            {"trade_date": "2024-06-15", "open": 1.2, "close": 1.25}
        ])
        date_range = self.repo.get_date_range("515220")
        self.assertEqual(date_range["min_date"], "2024-01-02")
        self.assertEqual(date_range["max_date"], "2024-06-15")
        self.assertEqual(date_range["total_count"], 2)

    def test_save_skips_unfinished_session_bar(self):
        """收盘前的当天日 K 不入库。"""
        noon = datetime(2026, 10, 15, 11, 0)
        with patch("services.data.market_clock.shanghai_now", return_value=noon):
            saved = self.repo.save_bars("515220", [
                {"trade_date": "2026-10-14", "open": 1.0, "close": 1.30, "amount": 100.0},
                {"trade_date": "2026-10-15", "open": 1.3, "close": 1.10, "amount": 9_000_000.0},
            ])
        self.assertEqual(saved, 1)
        df = self.repo.get_bars("515220")
        self.assertEqual(len(df), 1)
        self.assertEqual(df.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2026-10-14")


if __name__ == "__main__":
    unittest.main()
