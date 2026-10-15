"""全市场日 K 引导可中断续传。完成标记代替「池子满 20 只」。"""

from unittest.mock import MagicMock, patch

from repositories.market_data_repository import MarketDataRepository
from repositories.universe_bootstrap_repository import UniverseBootstrapRepository
from services.data.startup_sync_service import (
    StartupSyncService,
    pool_is_backfilling,
    resume_universe_bootstrap,
)


def _wipe(repo: UniverseBootstrapRepository) -> None:
    repo.reset()


def _bars(code: str) -> None:
    MarketDataRepository().save_bars(code, [
        {
            "trade_date": "2026-09-01",
            "open": 1.0,
            "close": 1.1,
            "high": 1.2,
            "low": 0.9,
            "vol": 1000,
            "amount": 110000,
            "pct_chg": 1.0,
        }
    ])


def _universe():
    return [
        {"etf_code": "990301", "etf_name": "甲"},
        {"etf_code": "990302", "etf_name": "乙"},
        {"etf_code": "990303", "etf_name": "丙"},
    ]


def test_interrupted_bootstrap_resumes_only_missing_codes_then_rebuilds_pool():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    market = MarketDataRepository()
    _bars("990301")
    repo.prepare(_universe(), {"990301"})
    assert [row["etf_code"] for row in repo.pending_instruments()] == ["990302", "990303"]
    assert repo.progress() == {"active": True, "done": 1, "total": 3}

    synced = []

    def sync_universe(instruments=None, **kwargs):
        synced.append([row["etf_code"] for row in instruments])
        callback = kwargs.get("progress_callback")
        results = []
        for index, row in enumerate(instruments, start=1):
            result = {"etf_code": row["etf_code"], "status": "synced", "rows_added": 20}
            results.append(result)
            if callback:
                callback(result, index, len(instruments))
        return {"synced": len(results), "skipped": 0, "results": results}

    sync_service = MagicMock()
    sync_service.sync_universe.side_effect = sync_universe
    pool_builder = MagicMock()
    outcome = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=market,
        sync_service=sync_service,
        list_loader=lambda: _universe(),
        pool_builder=pool_builder,
    )

    assert synced == [["990302", "990303"]]
    assert outcome["complete"] is True
    assert repo.progress()["active"] is False
    assert repo.progress()["done"] == 3
    pool_builder.assert_called_once_with(force_refresh=True)

    sync_service.sync_universe.reset_mock()
    pool_builder.reset_mock()
    again = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=market,
        sync_service=sync_service,
        list_loader=lambda: _universe(),
        pool_builder=pool_builder,
    )
    assert again["complete"] is True
    sync_service.sync_universe.assert_not_called()
    pool_builder.assert_not_called()
    _wipe(repo)


def test_existing_partial_bars_without_a_flag_resume_and_a_full_archive_does_not():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    market = MarketDataRepository()
    _bars("990311")
    sync_service = MagicMock()
    sync_service.sync_universe.return_value = {
        "synced": 1,
        "skipped": 0,
        "results": [{"etf_code": "990312", "status": "synced", "rows_added": 8}],
    }
    pool_builder = MagicMock()
    instruments = [
        {"etf_code": "990311", "etf_name": "已有"},
        {"etf_code": "990312", "etf_name": "缺失"},
    ]
    outcome = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=market,
        sync_service=sync_service,
        list_loader=lambda: instruments,
        pool_builder=pool_builder,
    )
    assert outcome["complete"] is True
    called = [row["etf_code"] for row in sync_service.sync_universe.call_args.kwargs["instruments"]]
    assert called == ["990312"]
    pool_builder.assert_called_once_with(force_refresh=True)

    _wipe(repo)
    _bars("990321")
    _bars("990322")
    sync_service.sync_universe.reset_mock()
    pool_builder.reset_mock()
    covered = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=market,
        sync_service=sync_service,
        list_loader=lambda: [
            {"etf_code": "990321", "etf_name": "甲"},
            {"etf_code": "990322", "etf_name": "乙"},
        ],
        pool_builder=pool_builder,
    )
    assert covered["complete"] is True
    sync_service.sync_universe.assert_not_called()
    pool_builder.assert_not_called()
    assert repo.progress()["active"] is False
    _wipe(repo)


def test_twenty_instruments_do_not_skip_an_unfinished_universe():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    sync_service = MagicMock()
    sync_service.get_shoppable_universe.return_value = [
        {"etf_code": f"{index:06d}", "etf_name": "池内"} for index in range(25)
    ]
    sync_service.sync_universe.return_value = {
        "synced": 1,
        "skipped": 0,
        "results": [{"etf_code": "990331", "status": "synced", "rows_added": 4}],
    }
    client = MagicMock()
    client._load_category_spot_rows.return_value = [
        {"代码": "sh990331", "名称": "名单内"},
    ]
    client.build_or_get_etf_pool = MagicMock()
    service = StartupSyncService(
        market_repo=MarketDataRepository(),
        matrix_repo=MagicMock(),
        sync_service=sync_service,
        matrix_service=MagicMock(),
        akshare_client=client,
        bootstrap_repo=repo,
    )
    with patch.object(service, "acquire_distributed_lock", return_value=True), \
         patch.object(service, "release_distributed_lock"), \
         patch.object(service, "check_freshness", return_value={
             "expected_date": "2026-10-14",
             "local_max_date": "2026-10-14",
             "needs_bar_sync": False,
             "needs_matrix_refresh": False,
         }), \
         patch("services.data.startup_sync_service.connect"):
        result = service.run_sync_pipeline(workers=1, force=False)

    assert result["status"] == "skipped"
    assert result["reason"] == "already_up_to_date"
    instruments = sync_service.sync_universe.call_args.kwargs["instruments"]
    assert [row["etf_code"] for row in instruments] == ["990331"]
    client.build_or_get_etf_pool.assert_called_once_with(force_refresh=True)
    assert pool_is_backfilling(
        {"backfilling": True, "bootstrap_active": True, "last_error": None},
        53,
    ) is True
    _wipe(repo)


def test_transport_failure_stays_pending_and_empty_payload_is_done():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    repo.prepare([{"etf_code": "990401", "etf_name": "甲"}], set())
    repo.record_result({
        "etf_code": "990401",
        "status": "failed",
        "error": "SSLError(SSLEOFError(8, 'UNEXPECTED_EOF_WHILE_READING'))",
    })
    assert [row["etf_code"] for row in repo.pending_instruments()] == ["990401"]
    assert repo.progress()["done"] == 0

    repo.record_result({
        "etf_code": "990401",
        "status": "failed",
        "error": "拉取到的行情数据为空",
    })
    assert repo.pending_instruments() == []
    assert repo.progress()["done"] == 1
    assert repo.progress()["active"] is False
    _wipe(repo)


def test_bootstrap_uses_at_most_three_workers():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    sync_service = MagicMock()
    sync_service.sync_universe.return_value = {
        "synced": 0,
        "skipped": 0,
        "failed_count": 1,
        "results": [{
            "etf_code": "990361",
            "status": "failed",
            "error": "SSL: UNEXPECTED_EOF_WHILE_READING",
        }],
    }
    resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=MarketDataRepository(),
        sync_service=sync_service,
        list_loader=lambda: [{"etf_code": "990361", "etf_name": "甲"}],
        pool_builder=MagicMock(),
        workers=5,
    )
    assert sync_service.sync_universe.call_args.kwargs["workers"] == 3
    assert [row["etf_code"] for row in repo.pending_instruments()] == ["990361"]
    _wipe(repo)


def _mark_empty(repo: UniverseBootstrapRepository, code: str) -> None:
    repo.record_result({
        "etf_code": code,
        "status": "failed",
        "error": "拉取到的行情数据为空",
    })


def _backdate(repo: UniverseBootstrapRepository, code: str, stamp: str) -> None:
    conn = repo._connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE universe_bootstrap_code SET updated_at = %s WHERE etf_code = %s",
                (stamp, code),
            )
        conn.commit()
    finally:
        conn.close()


def test_barless_empty_is_reopened_once_and_completed_flag_clears():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    _bars("990482")
    _bars("990483")
    repo.prepare([
        {"etf_code": "990481", "etf_name": "误空"},
        {"etf_code": "990482", "etf_name": "有K的空"},
        {"etf_code": "990483", "etf_name": "已同步"},
    ], {"990482", "990483"})
    _mark_empty(repo, "990481")
    _mark_empty(repo, "990482")
    repo.record_result({"etf_code": "990483", "status": "synced"})
    assert repo.is_complete() is True

    reopened = repo.recheck_barless_empties({"990482", "990483"})
    assert reopened == ["990481"]
    assert [row["etf_code"] for row in repo.pending_instruments()] == ["990481"]
    assert repo.is_complete() is False
    assert repo.progress()["active"] is True

    _mark_empty(repo, "990481")
    assert repo.recheck_barless_empties({"990482", "990483"}) == []
    assert repo.pending_instruments() == []
    assert repo.is_complete() is True

    _backdate(repo, "990481", "2020-01-01 00:00:00")
    assert repo.recheck_barless_empties({"990482", "990483"}) == ["990481"]
    assert repo.is_complete() is False
    _mark_empty(repo, "990481")
    assert repo.recheck_barless_empties({"990482", "990483"}) == []
    _wipe(repo)


def test_startup_reopens_false_empties_then_leaves_a_fresh_empty_alone():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    _bars("990492")
    repo.prepare([
        {"etf_code": "990491", "etf_name": "误空"},
        {"etf_code": "990492", "etf_name": "已有"},
    ], {"990492"})
    _mark_empty(repo, "990491")
    repo.record_result({"etf_code": "990492", "status": "synced"})
    assert repo.is_complete() is True

    sync_service = MagicMock()
    sync_service.sync_universe.return_value = {
        "synced": 0,
        "skipped": 0,
        "failed_count": 0,
        "results": [{
            "etf_code": "990491",
            "status": "failed",
            "error": "拉取到的行情数据为空",
        }],
    }
    instruments = [
        {"etf_code": "990491", "etf_name": "误空"},
        {"etf_code": "990492", "etf_name": "已有"},
    ]
    outcome = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=MarketDataRepository(),
        sync_service=sync_service,
        list_loader=lambda: instruments,
        pool_builder=MagicMock(),
    )
    called = [row["etf_code"] for row in sync_service.sync_universe.call_args.kwargs["instruments"]]
    assert called == ["990491"]
    assert outcome["complete"] is True
    assert repo.pending_instruments() == []

    sync_service.sync_universe.reset_mock()
    again = resume_universe_bootstrap(
        bootstrap_repo=repo,
        market_repo=MarketDataRepository(),
        sync_service=sync_service,
        list_loader=lambda: instruments,
        pool_builder=MagicMock(),
    )
    assert again["complete"] is True
    sync_service.sync_universe.assert_not_called()
    _wipe(repo)


def test_full_universe_sync_uses_the_market_list_not_the_current_pool():
    repo = UniverseBootstrapRepository()
    _wipe(repo)
    sync_service = MagicMock()
    sync_service.get_shoppable_universe.return_value = [
        {"etf_code": "510300", "etf_name": "池内"}
    ]
    sync_service.sync_universe.return_value = {
        "synced": 1,
        "skipped": 0,
        "results": [{"etf_code": "990351", "status": "synced", "rows_added": 3}],
    }
    client = MagicMock()
    client._load_category_spot_rows.return_value = [{"代码": "sh990351", "名称": "名单内"}]
    service = StartupSyncService(
        market_repo=MarketDataRepository(),
        matrix_repo=MagicMock(),
        sync_service=sync_service,
        matrix_service=MagicMock(),
        akshare_client=client,
        bootstrap_repo=repo,
    )
    with patch.object(service, "acquire_distributed_lock", return_value=True), \
         patch.object(service, "release_distributed_lock"), \
         patch("services.data.startup_sync_service.connect"):
        result = service.run_full_universe_sync(workers=1)

    assert result["status"] == "success"
    codes = [row["etf_code"] for row in sync_service.sync_universe.call_args.kwargs["instruments"]]
    assert codes == ["990351"]
    assert "510300" not in codes
    client.build_or_get_etf_pool.assert_called_once_with(force_refresh=True)
    _wipe(repo)
