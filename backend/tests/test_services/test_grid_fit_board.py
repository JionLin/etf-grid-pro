import inspect
import unittest

from backend.repositories.backtest_repository import BacktestRepository
from backend.repositories.etf_pool_repository import ETFPoolRepository
from backend.repositories.grid_fit_repository import GridFitRepository
from backend.repositories.mysql_connection import TEST_DATABASE
from backend.repositories.mysql_schema import reset_business_tables
from backend.tests.mysql_gate import skip_without_mysql
from backend.services.analysis.grid_fit_service import (
    PROTOCOL_VERSION,
    GridFitBoardService,
    annualized_grid_cash_yield,
    build_protocol_callbacks,
    protocol_runner_avoids_archive,
)


def _result(profit, calendar_days, sells, drawdown, annual_return):
    return {
        "summary": {
            "grid_cash_profit": profit,
            "sell_trades_count": sells,
            "max_drawdown": drawdown,
            "annualized_return": annual_return,
            "alpha": 1.2,
        },
        "history_meta": {"actual_calendar_days": calendar_days},
    }


class TestGridFitBoard(unittest.TestCase):
    def setUp(self):
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)
        self.repo = GridFitRepository(database=TEST_DATABASE)
        self.archive = BacktestRepository(database=TEST_DATABASE)
        self.service = GridFitBoardService(self.repo)

    def test_negative_profit_stays_negative_and_thresholds_have_no_rank(self):
        self.assertEqual(annualized_grid_cash_yield(-1500, 1825), -0.01)
        self.assertLess(annualized_grid_cash_yield(-1500, 1825), 0)

        calls = {"n": 0}

        def sync_fn(_code):
            return {"calendar_days": 1825, "fingerprint": "2026-09-01"}

        def backtest_fn(_code, step_mode):
            calls["n"] += 1
            sells = 80 if step_mode == "atr" else 20
            return _result(-1500, 1825, sells, 10, -3.0)

        self.service.run_batch(
            [{"etf_code": "515220", "etf_name": "煤炭ETF", "sector": "周期资源"}],
            sync_fn,
            backtest_fn,
        )
        board = self.service.list_board(sector="周期资源")["board"]
        self.assertEqual(board[0]["atr"]["cash_yield"], -0.01)
        self.assertEqual(board[0]["atr"]["rank"], 1)

        sparse = _result(100, 1825, 5, 10, 8.0)
        self.service._store_result("512480", "芯片ETF", "科技芯片", "atr", sparse, "fp")
        drawdown = _result(100, 1825, 80, 36, 9.0)
        self.service._store_result("512480", "芯片ETF", "科技芯片", "fixed_eda", drawdown, "fp")
        blocked = self.service.list_board(sector="科技芯片")
        chip = next(item for item in blocked["blocked"] if item["etf_code"] == "512480")
        self.assertIsNone(chip["atr"]["rank"])
        self.assertEqual(chip["atr"]["status_reason"], "成交过稀")
        self.assertEqual(chip["fixed_eda"]["status_reason"], "回撤超线")
        self.assertIsNone(chip["fixed_eda"]["rank"])

    def test_short_sample_does_not_enter_main_board(self):
        self.service._store_result(
            "159915", "创业板ETF", "核心宽基", "atr",
            _result(900, 1200, 50, 8, 20.0), "short",
        )
        self.service._store_result(
            "159915", "创业板ETF", "核心宽基", "fixed_eda",
            _result(900, 1200, 20, 8, 20.0), "short",
        )
        self.service._store_result(
            "510300", "沪深300", "核心宽基", "atr",
            _result(300, 1825, 80, 8, 4.0), "full",
        )
        self.service._store_result(
            "510300", "沪深300", "核心宽基", "fixed_eda",
            _result(200, 1825, 20, 8, 3.0), "full",
        )
        payload = self.service.list_board(sector="核心宽基")
        self.assertEqual([item["etf_code"] for item in payload["board"]], ["510300"])
        self.assertEqual(payload["short_sample"][0]["etf_code"], "159915")
        self.assertIsNone(payload["short_sample"][0]["atr"]["rank"])
        self.assertEqual(payload["board"][0]["atr"]["rank"], 1)

    def test_sector_rank_ignores_other_sectors_and_sorts_by_cash_yield(self):
        self.service._store_result(
            "512480", "芯片ETF", "科技芯片", "atr",
            _result(600, 1825, 80, 8, 1.0), "a",
        )
        self.service._store_result(
            "512760", "芯片龙头", "科技芯片", "atr",
            _result(200, 1825, 80, 8, 30.0), "a",
        )
        self.service._store_result(
            "515220", "煤炭ETF", "周期资源", "atr",
            _result(2000, 1825, 80, 8, 40.0), "a",
        )
        tech = self.service.list_board(sector="科技芯片")["board"]
        cycle = self.service.list_board(sector="周期资源")["board"]
        self.assertEqual([item["etf_code"] for item in tech], ["512480", "512760"])
        self.assertEqual(tech[0]["atr"]["rank"], 1)
        self.assertEqual(tech[1]["atr"]["rank"], 2)
        self.assertGreater(tech[1]["atr"]["annual_return"], tech[0]["atr"]["annual_return"])
        self.assertEqual(cycle[0]["atr"]["rank"], 1)
        self.assertEqual(cycle[0]["etf_code"], "515220")

    def test_archive_untouched_and_protocol_does_not_auto_archive(self):
        self.archive.save_run(
            "515220", "煤炭ETF", 180, 30000, "atr", "pool_shares",
            {"summary": {"annualized_return": 1.0, "grid_cash_profit": 10}, "history_meta": {}},
        )
        before = self.archive.list_runs(latest_only=False)["total"]

        def sync_fn(_code):
            return {"calendar_days": 1825, "fingerprint": "covered"}

        def backtest_fn(_code, step_mode):
            sells = 80 if step_mode == "atr" else 20
            return _result(300, 1825, sells, 8, 5.0)

        self.service.run_batch(
            [{"etf_code": "159941", "etf_name": "纳指ETF", "sector": "跨境全球"}],
            sync_fn,
            backtest_fn,
        )
        after = self.archive.list_runs(latest_only=False)["total"]
        self.assertEqual(before, after)
        self.assertEqual(len(self.repo.list_runs(PROTOCOL_VERSION)), 2)
        self.assertTrue(protocol_runner_avoids_archive())
        from backend.api.routes.analysis_routes import refresh_grid_fit
        self.assertNotIn("save_run", inspect.getsource(refresh_grid_fit))
        callback_source = inspect.getsource(build_protocol_callbacks)
        self.assertIn("sync_window_history", callback_source)
        self.assertNotIn("sync_full_history", callback_source)

    def test_sync_failure_does_not_hide_completed_rows(self):
        def sync_fn(code):
            if code == "511360":
                raise RuntimeError("源站超时")
            if code == "159915":
                return {"calendar_days": 1200, "fingerprint": "short"}
            if code == "510050":
                return {"calendar_days": 400, "fingerprint": "cold"}
            return {"calendar_days": 1825, "fingerprint": "ready"}

        def backtest_fn(code, step_mode):
            days = 1200 if code == "159915" else 1825
            sells = 80 if step_mode == "atr" else 20
            return _result(400, days, sells, 8, 6.0)

        universe = [
            {"etf_code": "515220", "etf_name": "煤炭ETF", "sector": "周期资源"},
            {"etf_code": "159915", "etf_name": "创业板ETF", "sector": "核心宽基"},
            {"etf_code": "510050", "etf_name": "上证50", "sector": "核心宽基"},
            {"etf_code": "511360", "etf_name": "短融ETF", "sector": "大金融"},
            {"etf_code": "511880", "etf_name": "银华日利ETF", "sector": "大金融"},
            {"etf_code": "159623", "etf_name": "成渝经济圈ETF", "sector": "未归类"},
        ]
        self.service.run_batch(universe, sync_fn, backtest_fn)
        payload = self.service.list_board()
        self.assertEqual(payload["board"][0]["etf_code"], "515220")
        self.assertEqual(payload["failed"][0]["etf_code"], "511360")
        self.assertEqual(payload["failed"][0]["atr"]["status_reason"], "行情同步失败")
        self.assertNotIn("源站超时", payload["failed"][0]["atr"]["status_reason"])
        self.assertEqual(payload["progress"], {
            "ranked": 1,
            "short_sample": 1,
            "not_ready": 1,
            "failed": 1,
        })
        codes = {item["etf_code"] for item in payload["board"] + payload["failed"] + payload["short_sample"] + payload["not_ready"]}
        self.assertNotIn("511880", codes)
        self.assertNotIn("159623", codes)

    def test_unchanged_fingerprint_skips_backtest(self):
        calls = []

        def sync_fn(_code):
            return {"calendar_days": 1825, "fingerprint": "same-bars"}

        def backtest_fn(code, step_mode):
            calls.append((code, step_mode))
            sells = 80 if step_mode == "atr" else 20
            return _result(100, 1825, sells, 5, 2.0)

        universe = [{"etf_code": "512800", "etf_name": "银行ETF", "sector": "大金融"}]
        self.service.run_batch(universe, sync_fn, backtest_fn)
        self.assertEqual(len(calls), 2)
        calls.clear()
        self.service.run_batch(universe, sync_fn, backtest_fn)
        self.assertEqual(calls, [])

    def test_universe_excludes_unclassified(self):
        pool = ETFPoolRepository(database=TEST_DATABASE)
        pool.save_pool([
            {
                "etf_code": "515220",
                "name": "煤炭ETF",
                "sector": "周期资源",
                "is_t0": False,
                "amount_ma20_10k": 8000,
                "atr_pct": 2.1,
            },
            {
                "etf_code": "159623",
                "name": "成渝经济圈ETF",
                "sector": "未归类",
                "is_t0": False,
                "amount_ma20_10k": 8000,
                "atr_pct": 2.1,
            },
        ])
        codes = {item["etf_code"] for item in pool.list_shoppable_universe()}
        self.assertEqual(codes, {"515220"})


if __name__ == "__main__":
    unittest.main()
