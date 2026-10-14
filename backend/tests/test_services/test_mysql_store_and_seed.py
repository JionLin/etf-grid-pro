import inspect
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from backend.repositories.backtest_repository import BacktestRepository
from backend.repositories.etf_pool_repository import ETFPoolRepository
from backend.repositories.etf_taxonomy import assign_subsector
from backend.repositories.grid_fit_repository import GridFitRepository
from backend.repositories.market_data_repository import MarketDataRepository
from backend.repositories.mysql_connection import (
    TEST_DATABASE,
    MysqlConnectionError,
    connect,
)
from backend.repositories.mysql_schema import reset_business_tables, show_create_table
from backend.services.analysis.grid_fit_service import GridFitBoardService, PROTOCOL_VERSION
from backend.services.analysis.subsector_seed import run_subsector_seed
from backend.services.data.akshare_client import AkShareClient
from backend.services.data.sqlite_mysql_importer import import_existing_sqlite
from backend.tests.mysql_gate import skip_without_mysql


class TestMysqlStoreAndSeed(unittest.TestCase):
    def setUp(self):
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)

    def test_wrong_password_does_not_create_sqlite(self):
        data_dir = Path(__file__).resolve().parents[2] / "data"
        before = set(data_dir.glob("*.db"))
        with self.assertRaises(MysqlConnectionError):
            connect(TEST_DATABASE, password="definitely-wrong-password")
        self.assertEqual(set(data_dir.glob("*.db")), before)

    def test_schema_uses_double_and_splits_payload(self):
        bars = show_create_table(TEST_DATABASE, "etf_daily_bar")
        payload = show_create_table(TEST_DATABASE, "backtest_run_payload")
        run = show_create_table(TEST_DATABASE, "backtest_run")
        self.assertIn("double", bars.lower())
        compact = bars.replace(" ", "").replace("`", "")
        self.assertIn("PRIMARYKEY(etf_code,trade_date)", compact)
        self.assertIn("run_id", payload)
        self.assertNotIn("equity_curve", run)

    def test_subsector_rules_are_exclusive(self):
        self.assertEqual(assign_subsector("科创50ETF华夏", "核心宽基"), "双创成长")
        self.assertEqual(assign_subsector("中药ETF汇添富", "医药健康"), "中药")
        self.assertNotEqual(assign_subsector("生物医药ETF天弘", "医药健康"), "生物疫苗")
        self.assertIsNone(assign_subsector("恒生ETF华夏", "跨境全球"))
        self.assertEqual(assign_subsector("恒生ETF华夏", "跨境全球") or "跨境全球", "跨境全球")

    def test_seed_marks_highest_liquidity_only(self):
        repo = ETFPoolRepository(database=TEST_DATABASE)
        repo.save_pool([
            _instrument("159001", "中药A", "医药健康", 1000),
            _instrument("159002", "中药B", "医药健康", 9000),
            _instrument("159003", "中药C", "医药健康", 4000),
            _instrument("159004", "生物医药ETF", "医药健康", 8000),
        ])
        repo.reclassify_persisted(AkShareClient.classify_etf_item)
        seeds = {item["subsector"]: item["etf_code"] for item in repo.mark_seed_representatives()}
        self.assertEqual(seeds.get("中药"), "159002")
        self.assertNotIn("生物疫苗", seeds)
        self.assertTrue(all(item["subsector"] for item in repo.list_seeds()))

    def test_seed_does_not_write_archive_or_curve(self):
        source = inspect.getsource(run_subsector_seed)
        self.assertNotIn("save_run", source)
        pool = ETFPoolRepository(database=TEST_DATABASE)
        archive = BacktestRepository(database=TEST_DATABASE)
        board = GridFitBoardService(GridFitRepository(database=TEST_DATABASE))
        pool.save_pool([_instrument("159010", "中药ETF", "医药健康", 5000)])
        pool.reclassify_persisted(AkShareClient.classify_etf_item)
        before = archive.count_runs()

        def sync_fn(_code):
            return {"calendar_days": 1825, "fingerprint": "2026-09-01"}

        def backtest_fn(_code, step_mode):
            return {
                "summary": {
                    "grid_cash_profit": 100,
                    "sell_trades_count": 20,
                    "max_drawdown": 5,
                    "annualized_return": 2,
                },
                "history_meta": {"actual_calendar_days": 1825},
            }

        run_subsector_seed(pool, board, sync_fn, backtest_fn)
        self.assertEqual(archive.count_runs(), before)
        cell = board.repo.find_run("159010", "atr", PROTOCOL_VERSION)
        self.assertIsNotNone(cell)
        self.assertNotIn("equity_curve_json", cell)
        self.assertNotIn("trades_json", cell)

    def test_seed_failure_continues_and_short_sample_is_not_ready(self):
        pool = ETFPoolRepository(database=TEST_DATABASE)
        board = GridFitBoardService(GridFitRepository(database=TEST_DATABASE))
        pool.save_pool([
            _instrument("159011", "煤炭ETF", "周期资源", 8000),
            _instrument("159012", "银行ETF", "大金融", 7000),
        ])
        pool.reclassify_persisted(AkShareClient.classify_etf_item)

        def sync_fn(code):
            if code == "159011":
                raise RuntimeError("行情中断")
            return {"calendar_days": 400, "fingerprint": "short"}

        def backtest_fn(_code, _step):
            raise AssertionError("短样本不应进入回测")

        run_subsector_seed(pool, board, sync_fn, backtest_fn)
        failed = board.repo.find_run("159011", "atr", PROTOCOL_VERSION)
        short = board.repo.find_run("159012", "atr", PROTOCOL_VERSION)
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(short["status"], "not_ready")

    def test_non_seed_can_read_lake_without_grid_fit(self):
        market = MarketDataRepository(database=TEST_DATABASE)
        market.save_bars("510300", [
            {"trade_date": "2026-09-10", "open": 1, "close": 1.1, "high": 1.2, "low": 0.9, "vol": 1, "amount": 1, "pct_chg": 1},
            {"trade_date": "2026-09-11", "open": 1.1, "close": 1.2, "high": 1.3, "low": 1.0, "vol": 1, "amount": 1, "pct_chg": 1},
        ])
        client = AkShareClient()
        client.market_repo = market
        frame = client.get_etf_daily_data("510300", "20260910", "20260911", days=10)
        self.assertFalse(frame.empty)
        self.assertIsNone(GridFitRepository(database=TEST_DATABASE).find_run("510300", "atr", PROTOCOL_VERSION))

    def test_import_is_reentrant_and_skips_valuations(self):
        folder = tempfile.mkdtemp()
        _write_fixture_sqlite(folder)
        first = import_existing_sqlite(TEST_DATABASE, folder)
        second_runs = BacktestRepository(database=TEST_DATABASE).count_runs()
        import_existing_sqlite(TEST_DATABASE, folder)
        self.assertEqual(first["bars"], 1)
        self.assertEqual(first["instruments"], 1)
        self.assertEqual(first["runs"], 1)
        self.assertEqual(BacktestRepository(database=TEST_DATABASE).count_runs(), second_runs)
        detail = BacktestRepository(database=TEST_DATABASE).get_run_detail("run_fixture")
        self.assertEqual(detail["equity_curve"][0]["nav"], 1.0)
        self.assertNotIn("equity_curve", BacktestRepository(database=TEST_DATABASE).list_runs()["records"][0])


def _instrument(code, name, sector, ma20):
    return {
        "etf_code": code,
        "name": name,
        "sector": sector,
        "is_t0": False,
        "amount_10k": ma20,
        "amount_ma20_10k": ma20,
        "atr_pct": 2.0,
        "elasticity": "稳健型",
    }


def _write_fixture_sqlite(folder: str) -> None:
    market = sqlite3.connect(os.path.join(folder, "market_data.db"))
    market.execute(
        """
        CREATE TABLE etf_daily_bars (
            etf_code TEXT, trade_date TEXT, open REAL, close REAL, high REAL, low REAL,
            vol REAL, amount REAL, pct_chg REAL
        )
        """
    )
    market.execute(
        "INSERT INTO etf_daily_bars VALUES ('515220','2024-01-02',1,1.1,1.2,0.9,10,100,1)"
    )
    market.commit()
    market.close()

    cache = sqlite3.connect(os.path.join(folder, "market_cache.db"))
    cache.execute(
        """
        CREATE TABLE etf_pool_metadata (
            etf_code TEXT, name TEXT, sector TEXT, is_t0 INT, list_date TEXT,
            latest_price REAL, pct_change REAL, amount_10k REAL, amount_ma20_10k REAL,
            atr_pct REAL, elasticity TEXT, score REAL, updated_at TEXT
        )
        """
    )
    cache.execute(
        """
        CREATE TABLE etf_daily_valuations (etf_code TEXT, trade_date TEXT)
        """
    )
    cache.execute("INSERT INTO etf_daily_valuations VALUES ('515220','2024-01-02')")
    cache.execute(
        """
        INSERT INTO etf_pool_metadata VALUES (
            '515220','煤炭ETF','周期资源',0,'',1.2,0.1,1000,9000,2.1,'稳健型',80,'2026-09-13 10:00:00'
        )
        """
    )
    cache.commit()
    cache.close()

    archive = sqlite3.connect(os.path.join(folder, "backtest_records.db"))
    archive.execute(
        """
        CREATE TABLE backtest_runs (
            run_id TEXT, created_at TEXT, etf_code TEXT, etf_name TEXT, backtest_days INT,
            actual_days INT, total_capital REAL, step_mode TEXT, reinvest_mode TEXT,
            annual_return REAL, max_drawdown REAL, total_profit REAL, total_trades INT,
            free_shares INT, is_partial_history INT, partial_reason TEXT, params_json TEXT,
            summary_json TEXT, equity_curve_json TEXT, trades_json TEXT
        )
        """
    )
    archive.execute(
        """
        INSERT INTO backtest_runs VALUES (
            'run_fixture','2026-09-13 10:00:00','515220','煤炭ETF',180,120,30000,'atr','pool_shares',
            1,2,3,4,0,0,NULL,'{}','{}','[{"nav":1.0}]','[]'
        )
        """
    )
    archive.commit()
    archive.close()
