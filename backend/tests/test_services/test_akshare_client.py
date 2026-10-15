import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch
import pandas as pd
from backend.services.data.cache_service import resolve_akshare_cache_dir
from backend.services.data.akshare_client import AkShareClient
from backend.repositories.market_data_repository import MarketDataRepository
from backend.repositories.mysql_connection import TEST_DATABASE
from backend.repositories.mysql_schema import reset_business_tables
from backend.tests.mysql_gate import skip_without_mysql


class TestAKShareClientFallbackPagination(unittest.TestCase):
    def setUp(self):
        skip_without_mysql()
        from backend.services.data.akshare_client import _kline_pacer, reset_kline_transport

        reset_kline_transport()
        _kline_pacer.interval = 0
        _kline_pacer.jitter = 0
        reset_business_tables(TEST_DATABASE)
        self.client = AkShareClient()
        self.client.market_repo = MarketDataRepository(database=TEST_DATABASE)

    def tearDown(self):
        from backend.services.data.akshare_client import reset_kline_transport

        reset_kline_transport()

    def test_get_fallback_kline_multi_page(self):
        """测试备用K线源分段循环拉取与去重合并"""
        batch1 = [
            ["2024-01-22", "1.0", "1.1", "1.15", "0.95", "10000"]
        ] + [
            [f"2024-0{i%9+1}-{(i%28)+1:02d}", "1.0", "1.1", "1.15", "0.95", "10000"]
            for i in range(638)
        ] + [
            ["2026-09-11", "1.2", "1.25", "1.3", "1.18", "20000"]
        ]
        
        batch2 = [
            ["2021-06-08", "0.7", "0.75", "0.8", "0.68", "8000"]
        ] + [
            [f"2022-0{i%9+1}-{(i%28)+1:02d}", "0.8", "0.85", "0.9", "0.78", "8000"]
            for i in range(638)
        ] + [
            ["2024-01-22", "1.0", "1.1", "1.15", "0.95", "10000"]
        ]

        def fake_get(url, timeout=6):
            mock_resp = MagicMock()
            if "2024-01-22" in url:
                mock_resp.json.return_value = {
                    "data": {"sh515220": {"qfqday": batch2}}
                }
            else:
                mock_resp.json.return_value = {
                    "data": {"sh515220": {"qfqday": batch1}}
                }
            return mock_resp

        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.side_effect = fake_get
            mock_session_cls.return_value = mock_session

            df = self.client._get_fallback_kline(
                "515220", days=1825, start_date="2021-06-08", end_date="2026-09-11"
            )
            self.assertIsNotNone(df)
            assert df is not None
            estimated_trading_days = int(1825 * 250 / 365)
            self.assertGreater(len(df), estimated_trading_days)
            self.assertEqual(df.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2021-06-08")
            self.assertEqual(df.iloc[-1]["trade_date"].strftime("%Y-%m-%d"), "2026-09-11")
            self.assertIn("open", df.columns)
            self.assertIn("close", df.columns)
            self.assertIn("trade_date", df.columns)

    def test_fallback_kline_keeps_calendar_window_beyond_estimate(self):
        """备用源不得把日历窗口裁成最近的估算交易日数。"""
        early = [["2026-06-01", "1.0", "1.1", "1.15", "0.95", "10000"]]
        middle = [
            [f"2026-06-{(i % 27) + 2:02d}", "1.0", "1.1", "1.15", "0.95", "10000"]
            for i in range(70)
        ]
        latest = [["2026-09-11", "1.2", "1.25", "1.3", "1.18", "20000"]]
        batch = early + middle + latest

        def fake_get(url, timeout=6):
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"data": {"sh515220": {"qfqday": batch}}}
            return mock_resp

        with patch("requests.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.get.side_effect = fake_get
            mock_session_cls.return_value = mock_session
            df = self.client._get_fallback_kline(
                "515220", days=90, start_date="2026-06-01", end_date="2026-09-11"
            )

        self.assertIsNotNone(df)
        assert df is not None
        self.assertEqual(df.iloc[0]["trade_date"].strftime("%Y-%m-%d"), "2026-06-01")
        self.assertGreater(len(df), int(90 * 250 / 365))

    def test_lake_slice_keeps_calendar_start_for_multi_cycle(self):
        """本地湖直出时，90/180/1825 天起点必须是日历起点后的首个已存交易日。"""
        cases = [
            ("2026-06-14", "2026-09-11", 90, 64),
            ("2026-03-16", "2026-09-11", 180, 125),
            ("2021-09-13", "2026-09-11", 1825, 1211),
        ]
        for start, end, days, bar_count in cases:
            with self.subTest(days=days):
                reset_business_tables(TEST_DATABASE)
                self.client.market_repo = MarketDataRepository(database=TEST_DATABASE)
                start_dt = pd.Timestamp(start)
                records = []
                for offset in range(bar_count):
                    trade_day = (start_dt + pd.Timedelta(days=offset)).strftime("%Y-%m-%d")
                    records.append({
                        "trade_date": trade_day,
                        "open": 1.0,
                        "close": 1.1,
                        "high": 1.2,
                        "low": 0.9,
                        "vol": 100,
                        "amount": 1000,
                        "pct_chg": 0.1,
                    })
                records[-1]["trade_date"] = end
                self.client.market_repo.save_bars("515220", records)

                with patch.object(self.client, "_fetch_raw_kline_network") as mock_fetch, \
                     patch.object(self.client, "_get_fallback_kline") as mock_fallback:
                    df = self.client.get_etf_daily_data(
                        "515220", start.replace("-", ""), end.replace("-", ""), days=days
                    )

                mock_fetch.assert_not_called()
                mock_fallback.assert_not_called()
                self.assertIsNotNone(df)
                assert df is not None
                self.assertEqual(df.iloc[0]["trade_date"].strftime("%Y-%m-%d"), start)
                self.assertEqual(len(df), bar_count)
                self.assertGreater(len(df), int(days * 242 / 365))

    def test_incremental_forward_fill_when_latest_gap_detected(self):
        """测试检测到最新端缺口时的定向增量补齐"""
        # 1. 模拟本地已有数据截止到 2026-09-09 (共 500 条)
        base_records = [
            {"trade_date": f"2024-01-{(i%28)+1:02d}", "open": 1.0, "close": 1.02, "high": 1.05, "low": 0.98, "vol": 100, "amount": 1000, "pct_chg": 0.5}
            for i in range(499)
        ] + [
            {"trade_date": "2026-09-09", "open": 1.10, "close": 1.12, "high": 1.13, "low": 1.09, "vol": 200, "amount": 2000, "pct_chg": 1.8}
        ]
        self.client.market_repo.save_bars("515220", base_records)
        self.assertEqual(self.client.market_repo.get_date_range("515220")["max_date"], "2026-09-09")

        # 2. 模拟增量请求返回 2026-09-10 与 2026-09-11 缺失的两天
        inc_df = pd.DataFrame([
            {"trade_date": pd.to_datetime("2026-09-10"), "open": 1.12, "close": 1.14, "high": 1.15, "low": 1.11, "vol": 220, "amount": 2200, "pct_chg": 1.7},
            {"trade_date": pd.to_datetime("2026-09-11"), "open": 1.14, "close": 1.16, "high": 1.17, "low": 1.13, "vol": 250, "amount": 2500, "pct_chg": 1.75}
        ])

        with patch.object(self.client, "_fetch_raw_kline_network", return_value=inc_df) as mock_fetch:
            res_df = self.client.get_etf_daily_data("515220", "20240101", "20260911", days=180)
            
            # 验证触发了定向增量拉取
            mock_fetch.assert_called_once()
            self.assertIsNotNone(res_df)
            assert res_df is not None
            # 本地数据库中的最新水位线被自动推进到 2026-09-11
            updated_range = self.client.market_repo.get_date_range("515220")
            self.assertEqual(updated_range["max_date"], "2026-09-11")

    def test_zero_network_when_lake_is_up_to_date(self):
        """测试本地数据已是最新且满足周期时，完全不调用网络接口直出"""
        full_records = [
            {"trade_date": f"2026-0{i%9+1}-{(i%28)+1:02d}", "open": 1.0, "close": 1.02, "high": 1.05, "low": 0.98, "vol": 100, "amount": 1000, "pct_chg": 0.5}
            for i in range(120)
        ] + [
            {"trade_date": "2026-09-11", "open": 1.14, "close": 1.16, "high": 1.17, "low": 1.13, "vol": 250, "amount": 2500, "pct_chg": 1.75}
        ]
        self.client.market_repo.save_bars("515220", full_records)

        with patch.object(self.client, "_fetch_raw_kline_network") as mock_fetch, \
             patch.object(self.client, "_get_fallback_kline") as mock_fallback:
            res_df = self.client.get_etf_daily_data("515220", "20260301", "20260911", days=90)
            
            # 验证网络方法完全未被调用 (零网络等待直出)
            mock_fetch.assert_not_called()
            mock_fallback.assert_not_called()
            self.assertIsNotNone(res_df)
            assert res_df is not None
            self.assertTrue(len(res_df) > 0)

    def test_spot_frame_is_reused_within_ttl(self):
        """盘中同一份现货表只拉一次，单代码查询走短缓存。"""
        frame = pd.DataFrame([{
            "代码": "515220",
            "名称": "煤炭ETF",
            "最新价": 1.23,
            "昨收": 1.20,
            "涨跌幅": 2.5,
            "成交量": 1000,
            "成交额": 2000,
            "开盘价": 1.21,
            "最高价": 1.24,
            "最低价": 1.19,
            "涨跌额": 0.03,
            "振幅": 4.0,
            "换手率": 1.2,
            "量比": 1.0,
            "IOPV实时估值": 1.23,
            "基金折价率": 0.1,
            "数据日期": "20260913",
            "更新时间": 1,
        }])
        self.client.cache.get_daily_cache = MagicMock(return_value=None)
        self.client.cache.set_daily_cache = MagicMock()
        self.client.get_latest_trading_date = MagicMock(return_value="20260912")
        self.client._is_market_closed = MagicMock(return_value=False)

        with patch("backend.services.data.akshare_client.ak.fund_etf_spot_em", return_value=frame) as mock_spot:
            first = self.client.get_latest_price("515220")
            second = self.client.get_latest_price("515220")

        self.assertEqual(first["current_price"], 1.23)
        self.assertEqual(second["etf_name"], "煤炭ETF")
        mock_spot.assert_called_once()

    def test_tencent_fallback_quote_carries_shanghai_timestamp(self):
        """盘中腾讯现价的锚点日期是今天，不能再落到上一交易日。"""
        parts = [""] * 45
        parts[1] = "煤炭ETF"
        parts[3] = "1.303"
        parts[4] = "1.292"
        parts[5] = "1.300"
        parts[6] = "1000"
        parts[31] = "0.011"
        parts[32] = "0.85"
        parts[33] = "1.310"
        parts[34] = "1.290"
        parts[37] = "6804.765"
        parts[38] = "1.2"
        parts[43] = "1.5"
        with patch.object(self.client, "cached_trading_days", return_value=None):
            during = self.client._quote_from_tencent_parts(parts, datetime(2026, 10, 15, 11, 20))
            before_open = self.client._quote_from_tencent_parts(parts, datetime(2026, 10, 15, 9, 0))
        self.assertEqual(during["timestamp"], "2026-10-15 11:20:00")
        self.assertEqual(during["trade_date"], "20261015")
        self.assertEqual(during["current_price"], 1.303)
        self.assertEqual(before_open["trade_date"], "20261014")
        self.assertEqual(before_open["timestamp"], "2026-10-15 09:00:00")


def test_akshare_cache_dir_is_under_repo_root(monkeypatch, tmp_path):
    """从仓库根目录启动时，不能再去写上一级的 ../cache。"""
    monkeypatch.delenv("AKSHARE_CACHE_DIR", raising=False)
    previous = os.getcwd()
    os.chdir(tmp_path)
    try:
        resolved = Path(resolve_akshare_cache_dir())
        client = AkShareClient()
    finally:
        os.chdir(previous)
    assert resolved.parts[-2:] == ("cache", "akshare")
    assert resolved.is_absolute()
    assert Path(client.cache.cache_dir) == resolved
    monkeypatch.setenv("AKSHARE_CACHE_DIR", "custom-cache/akshare")
    custom = Path(resolve_akshare_cache_dir())
    assert custom.parts[-2:] == ("custom-cache", "akshare")
    assert custom.is_absolute()


if __name__ == "__main__":
    unittest.main()
