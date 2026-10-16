"""日 K 拉取限速、源暂停，以及失败日志不再按代码刷屏。"""
import logging
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

from backend.services.data.akshare_client import (
    AkShareClient,
    _kline_pacer,
    _tencent_gate,
    kline_batch_note,
    note_tencent_failure,
    reset_kline_transport,
    tencent_circuit_open,
)
from backend.services.data.universe_bar_sync_service import UniverseBarSyncService


def _quiet_pacer():
    reset_kline_transport()
    _kline_pacer.interval = 0
    _kline_pacer.jitter = 0


def test_tencent_pauses_after_three_failures_then_resumes():
    _quiet_pacer()
    clock = {"now": 1000.0}
    _tencent_gate._clock = lambda: clock["now"]
    try:
        assert note_tencent_failure() is False
        assert note_tencent_failure() is False
        assert note_tencent_failure() is True
        assert tencent_circuit_open()
        assert kline_batch_note(1, 2, 1) == "初始化 1/2，本批失败 1，腾讯源暂停 60s"
        clock["now"] = 1060.0
        assert tencent_circuit_open() is False
    finally:
        reset_kline_transport()


def test_paused_tencent_uses_eastmoney_then_resumes():
    _quiet_pacer()
    clock = {"now": 100.0}
    _tencent_gate._clock = lambda: clock["now"]
    for _ in range(3):
        note_tencent_failure()
    client = AkShareClient.__new__(AkShareClient)
    converted = pd.DataFrame({"close": [1.0]})
    try:
        with patch("backend.services.data.akshare_client.ak.fund_etf_hist_em", return_value=pd.DataFrame({"日期": ["2026-10-14"]})), \
             patch.object(client, "_convert_akshare_daily_to_tushare_format", return_value=converted), \
             patch.object(client, "_get_fallback_kline") as tencent, \
             patch("backend.services.data.akshare_client.time.sleep"):
            result = client.fetch_history_kline("510300", "20200101", "20261014")
        assert result is converted
        tencent.assert_not_called()

        clock["now"] = 160.0
        assert tencent_circuit_open() is False
        with patch("backend.services.data.akshare_client.ak.fund_etf_hist_em", side_effect=ConnectionError("eastmoney ssl")), \
             patch.object(client, "_get_fallback_kline", return_value=converted) as resumed, \
             patch("backend.services.data.akshare_client.time.sleep"):
            again = client.fetch_history_kline("510300", "20200101", "20261014")
        assert again is converted
        resumed.assert_called()
    finally:
        reset_kline_transport()


def test_fallback_ssl_is_debug_and_reraised(caplog):
    _quiet_pacer()
    client = AkShareClient.__new__(AkShareClient)

    def boom(url, timeout=8):
        raise requests.exceptions.SSLError("UNEXPECTED_EOF_WHILE_READING")

    try:
        with patch("requests.Session") as session_cls, \
             patch("backend.services.data.akshare_client.time.sleep"):
            session = MagicMock()
            session.get.side_effect = boom
            session_cls.return_value = session
            with caplog.at_level(logging.DEBUG, logger="backend.services.data.akshare_client"):
                with pytest.raises(requests.exceptions.SSLError):
                    client._get_fallback_kline("510760", start_date="2020-01-01", end_date="2026-10-14")
        warnings = [record for record in caplog.records if record.levelno >= logging.WARNING and "备用K线" in record.message]
        assert warnings == []
        assert any(record.levelno == logging.DEBUG and "备用K线" in record.message for record in caplog.records)
    finally:
        reset_kline_transport()


def test_tencent_paginates_newest_first_pages_back_to_five_years():
    _quiet_pacer()
    client = AkShareClient.__new__(AkShareClient)
    recent = list(pd.bdate_range("2024-01-02", periods=640))
    older = list(pd.bdate_range("2021-06-01", periods=200))
    page_new = [[day.strftime("%Y-%m-%d"), "1", "1.1", "1.2", "0.9", "100"] for day in reversed(recent)]
    page_old = [[day.strftime("%Y-%m-%d"), "1", "1.1", "1.2", "0.9", "100"] for day in reversed(older)]

    def fake_get(url, timeout=8):
        response = MagicMock()
        page = page_old if ",2015-01-01," in url else page_new
        response.json.return_value = {"data": {"sh510300": {"qfqday": page}}}
        return response

    try:
        with patch("requests.Session") as session_cls:
            session = MagicMock()
            session.get.side_effect = fake_get
            session_cls.return_value = session
            frame = client._get_fallback_kline(
                "510300",
                start_date="2021-06-01",
                end_date="2026-10-14",
            )
        assert frame is not None
        assert frame.iloc[0]["trade_date"].strftime("%Y-%m-%d") == "2021-06-01"
        assert len(frame) > 640
        assert frame.attrs["history_saturated"] is True
        assert session.get.call_count == 2
    finally:
        reset_kline_transport()


def test_capped_eastmoney_page_continues_to_tencent():
    _quiet_pacer()
    client = AkShareClient.__new__(AkShareClient)
    capped = pd.DataFrame({
        "trade_date": pd.bdate_range("2024-01-02", periods=640),
        "open": 1.0,
        "close": 1.0,
        "high": 1.0,
        "low": 1.0,
        "vol": 1.0,
        "amount": 1.0,
    })
    older = capped.iloc[:30].copy()
    older["trade_date"] = pd.bdate_range("2021-01-04", periods=30)
    older.attrs["history_saturated"] = True
    try:
        with patch("backend.services.data.akshare_client.ak.fund_etf_hist_em", return_value=pd.DataFrame({"日期": ["2024-01-02"]})), \
             patch.object(client, "_convert_akshare_daily_to_tushare_format", return_value=capped), \
             patch.object(client, "_get_fallback_kline", return_value=older) as tencent, \
             patch("backend.services.data.akshare_client.time.sleep"):
            result = client.fetch_history_kline("510300", "2021-01-01", "2026-10-14")
        assert result is older
        tencent.assert_called()
    finally:
        reset_kline_transport()


def test_complete_eastmoney_history_skips_tencent():
    _quiet_pacer()
    client = AkShareClient.__new__(AkShareClient)
    full = pd.DataFrame({
        "trade_date": pd.bdate_range("2020-06-01", periods=40),
        "open": 1.0,
        "close": 1.0,
        "high": 1.0,
        "low": 1.0,
        "vol": 1.0,
        "amount": 1.0,
    })
    try:
        with patch("backend.services.data.akshare_client.ak.fund_etf_hist_em", return_value=pd.DataFrame({"日期": ["2020-06-01"]})), \
             patch.object(client, "_convert_akshare_daily_to_tushare_format", return_value=full), \
             patch.object(client, "_get_fallback_kline") as tencent, \
             patch("backend.services.data.akshare_client.time.sleep"):
            result = client.fetch_history_kline("510300", "2021-01-01", "2026-10-14")
        assert result is full
        assert result.attrs["history_saturated"] is True
        tencent.assert_not_called()
    finally:
        reset_kline_transport()


def test_sync_keeps_ssl_error_instead_of_empty_payload():
    client = MagicMock()
    client.fetch_history_kline.side_effect = requests.exceptions.SSLError("UNEXPECTED_EOF_WHILE_READING")
    market_repo = MagicMock()
    market_repo.get_date_range.return_value = {
        "total_count": 0,
        "min_date": None,
        "max_date": None,
    }
    service = UniverseBarSyncService(market_repo=market_repo, pool_repo=MagicMock(), client=client)
    result = service.sync_single_etf("510760", start_date="2020-01-01", end_date="2026-10-14")
    assert result["status"] == "failed"
    assert "为空" not in (result["error"] or "")
    assert "EOF" in result["error"]
