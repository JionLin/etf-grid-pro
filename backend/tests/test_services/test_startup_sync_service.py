"""StartupSyncService 启动自检与分布式锁单元测试"""

from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from services.data.startup_sync_service import (
    LOCK_NAME,
    StartupSyncService,
    codes_from_spot_rows,
    pool_is_backfilling,
)


def test_settlement_date_calculation():
    """测试不同时段下 expected_settled_date 结算判定逻辑"""
    service = StartupSyncService()

    # 1. 周六、周日 -> 上周五
    sat = datetime(2026, 9, 19, 14, 0, 0)
    assert service.calculate_expected_settled_date(sat) == "2026-09-18"

    sun = datetime(2026, 9, 20, 20, 0, 0)
    assert service.calculate_expected_settled_date(sun) == "2026-09-18"

    # 2. 周三 10:00 (未收盘未结算) -> 前一日周二
    wed_morning = datetime(2026, 9, 16, 10, 0, 0)
    assert service.calculate_expected_settled_date(wed_morning) == "2026-09-15"

    # 3. 周三 15:20 (收盘但未过 15:30 结算阈值) -> 前一日周二
    wed_before_settle = datetime(2026, 9, 16, 15, 20, 0)
    assert service.calculate_expected_settled_date(wed_before_settle) == "2026-09-15"

    # 4. 周三 16:00 (结算后) -> 当日周三
    wed_after_settle = datetime(2026, 9, 16, 16, 0, 0)
    assert service.calculate_expected_settled_date(wed_after_settle) == "2026-09-16"

    # 5. 周一 09:30 (未收盘未结算) -> 上周五
    mon_morning = datetime(2026, 9, 14, 9, 30, 0)
    assert service.calculate_expected_settled_date(mon_morning) == "2026-09-11"


def test_distributed_lock_acquisition(monkeypatch):
    """测试 MySQL GET_LOCK 锁获取与释放"""
    monkeypatch.setenv("DB_TYPE", "sqlite")
    service = StartupSyncService()
    monkeypatch.setenv("DB_TYPE", "mysql")

    # 模拟获取锁成功
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    mock_cursor.fetchone.return_value = {"locked": 1}
    assert service.acquire_distributed_lock(mock_conn) is True
    mock_cursor.execute.assert_called_with(f"SELECT GET_LOCK('{LOCK_NAME}', 0) AS locked")

    # 模拟锁已被其他 worker 持有
    mock_cursor.fetchone.return_value = {"locked": 0}
    assert service.acquire_distributed_lock(mock_conn) is False

    # 释放锁
    service.release_distributed_lock(mock_conn)
    mock_cursor.execute.assert_called_with(f"SELECT RELEASE_LOCK('{LOCK_NAME}')")


def test_status_snapshot():
    """测试状态查询快照与状态更新"""
    service = StartupSyncService()
    status = service.get_status()
    assert "is_syncing" in status
    assert "current_stage" in status
    assert status["is_syncing"] is False


def test_two_phase_pipeline_success():
    """测试两阶段同步流水线 (增量日线拉取 -> 回测矩阵刷新) 执行顺利完成"""
    mock_market_repo = MagicMock()
    mock_matrix_repo = MagicMock()
    mock_sync_service = MagicMock()
    mock_matrix_service = MagicMock()

    service = StartupSyncService(
        market_repo=mock_market_repo,
        matrix_repo=mock_matrix_repo,
        sync_service=mock_sync_service,
        matrix_service=mock_matrix_service,
    )

    # 模拟需要更新
    with patch("services.data.startup_sync_service.resume_universe_bootstrap", return_value={
             "pending": [],
             "complete": True,
             "synced_now": False,
             "done": 0,
             "total": 0,
         }), \
         patch.object(service, "acquire_distributed_lock", return_value=True), \
         patch.object(service, "release_distributed_lock"), \
         patch.object(service, "check_freshness", return_value={
             "expected_date": "2026-09-18",
             "local_max_date": "2026-09-16",
             "needs_bar_sync": True,
             "needs_matrix_refresh": True,
         }), \
         patch("services.data.startup_sync_service.connect") as mock_connect:
        
        mock_sync_service.sync_universe.return_value = {
            "synced": 5,
            "skipped": 532,
            "results": [{"etf_code": "510300", "rows_added": 2}],
        }
        mock_matrix_service.run_universe_matrix.return_value = [{"etf_code": "510300"}]
        mock_matrix_repo.batch_save.return_value = 1

        result = service.run_sync_pipeline(workers=2, force=True)

        assert result["status"] == "success"
        assert result["synced_bars_count"] == 2
        assert result["matrix_count"] == 1
        mock_sync_service.sync_universe.assert_called_once()
        mock_matrix_service.run_universe_matrix.assert_called_once()
        mock_matrix_repo.batch_save.assert_called_once()


def test_two_phase_pipeline_error_handling():
    """测试当同步抛出异常时的容错与状态重置"""
    service = StartupSyncService()

    with patch("services.data.startup_sync_service.resume_universe_bootstrap", return_value={
             "pending": [],
             "complete": True,
             "synced_now": False,
             "done": 0,
             "total": 0,
         }), \
         patch.object(service, "acquire_distributed_lock", return_value=True), \
         patch.object(service, "release_distributed_lock"), \
         patch.object(service, "check_freshness", side_effect=RuntimeError("数据库网络超时")), \
         patch("services.data.startup_sync_service.connect"):

        result = service.run_sync_pipeline(force=True)
        assert result["status"] == "failed"
        assert result["error"] == "启动同步失败，请查看服务端日志"
        assert "数据库网络超时" not in result["error"]

        status = service.get_status()
        assert status["is_syncing"] is False
        assert status["current_stage"] == "failed"
        assert status["last_error"] == "启动同步失败，请查看服务端日志"
        assert "数据库网络超时" not in status["last_error"]


def test_empty_universe_backfills_daily_bars_from_market_list():
    """空池不能只扫已有标的。即使 510300 已是最新，也要先拉市场列表再回补日 K。"""
    mock_sync_service = MagicMock()
    mock_sync_service.get_shoppable_universe.return_value = []
    mock_matrix_service = MagicMock()
    mock_matrix_repo = MagicMock()
    mock_client = MagicMock()
    mock_client._load_category_spot_rows.return_value = [
        {"代码": "sh990401", "名称": "沪深300ETF"},
        {"代码": "SZ990402", "名称": "创业板ETF"},
        {"代码": "not-a-code", "名称": "无效"},
        {"代码": "sh990401", "名称": "重复"},
    ]
    service = StartupSyncService(
        market_repo=MagicMock(),
        matrix_repo=mock_matrix_repo,
        sync_service=mock_sync_service,
        matrix_service=mock_matrix_service,
        akshare_client=mock_client,
    )
    mock_sync_service.sync_universe.return_value = {
        "synced": 2,
        "skipped": 0,
        "results": [
            {"etf_code": "990401", "status": "synced", "rows_added": 10},
            {"etf_code": "990402", "status": "synced", "rows_added": 10},
        ],
    }
    mock_matrix_service.run_universe_matrix.return_value = []
    mock_matrix_repo.batch_save.return_value = 0

    with patch.object(service, "acquire_distributed_lock", return_value=True), \
         patch.object(service, "release_distributed_lock"), \
         patch.object(service, "check_freshness", return_value={
             "expected_date": "2026-10-14",
             "local_max_date": "2026-10-14",
             "needs_bar_sync": False,
             "needs_matrix_refresh": False,
         }), \
         patch("services.data.startup_sync_service.connect"):
        result = service.run_sync_pipeline(workers=2, force=False)

    assert result["status"] == "skipped"
    assert result["reason"] == "already_up_to_date"
    instruments = mock_sync_service.sync_universe.call_args.kwargs["instruments"]
    assert [row["etf_code"] for row in instruments] == ["990401", "990402"]
    assert instruments[0]["etf_name"] == "沪深300ETF"
    mock_client.build_or_get_etf_pool.assert_called_once_with(force_refresh=True)
    assert service.get_status()["backfilling"] is False


def test_fresh_dates_still_refresh_matrix_when_pool_codes_are_missing():
    from services.data.market_clock import SHANGHAI

    market = MagicMock()
    market.get_date_range.return_value = {"max_date": "2026-10-14", "min_date": "2020-01-02", "total_count": 1200}
    matrix = MagicMock()
    matrix.codes_for_default_preset.return_value = {"510300"}
    sync = MagicMock()
    sync.get_shoppable_universe.return_value = [
        {"etf_code": "510300", "etf_name": "旧"},
        {"etf_code": "510500", "etf_name": "新"},
    ]
    service = StartupSyncService(
        market_repo=market,
        matrix_repo=matrix,
        sync_service=sync,
        matrix_service=MagicMock(),
        akshare_client=MagicMock(),
        bootstrap_repo=MagicMock(),
    )
    connection = MagicMock()
    cursor = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    cursor.fetchone.return_value = {"total": 53, "last_up": "2026-10-14 18:00:00"}
    moment = datetime(2026, 10, 14, 16, 0, tzinfo=SHANGHAI)
    with patch("services.data.startup_sync_service.connect", return_value=connection):
        freshness = service.check_freshness(moment)
    assert freshness["needs_bar_sync"] is False
    assert freshness["needs_matrix_refresh"] is True


def test_codes_from_spot_rows_and_backfill_hint_flag():
    assert codes_from_spot_rows([{"代码": "sh512010", "名称": "医药ETF"}]) == [
        {"etf_code": "512010", "etf_name": "医药ETF"}
    ]
    assert codes_from_spot_rows([]) == []
    assert pool_is_backfilling({"backfilling": True, "last_error": None}, 0) is True
    assert pool_is_backfilling({"backfilling": True, "last_error": None}, 4) is False
    assert pool_is_backfilling({"backfilling": True, "last_error": "失败"}, 0) is False
    assert pool_is_backfilling({"backfilling": False}, 0) is False


def test_sync_status_api_endpoint():
    """测试 /api/system/sync-status 接口返回正确的数据结构"""
    from flask import Flask
    from api.routes.health_routes import health_bp

    app = Flask(__name__)
    app.register_blueprint(health_bp)
    client = app.test_client()

    res = client.get("/api/system/sync-status")
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "is_syncing" in data["data"]
    assert "current_stage" in data["data"]
