"""标的池已落库后，首页最新价必须改用实时行情，不能停在建池当日。"""
from unittest.mock import MagicMock, patch

from backend.services.data.akshare_client import AkShareClient


def _stale_pool():
    items = []
    for index in range(20):
        code = "515220" if index == 0 else f"{510000 + index:06d}"
        items.append({
            "etf_code": code,
            "name": "煤炭ETF国泰" if code == "515220" else f"ETF{code}",
            "sector": "周期资源",
            "latest_price": 1.292 if code == "515220" else 1.0,
            "pct_change": -2.05 if code == "515220" else 0.1,
            "amount_10k": 10000.0,
            "amount_ma20_10k": 9000.0,
            "atr_pct": 2.0,
        })
    return items


def test_cached_pool_replaces_previous_close_with_live_quote():
    """515220 建池快照是 1.292 / -2.05%，实时最新价是 1.303 / +0.85%，昨收不得再当现价。"""
    client = AkShareClient.__new__(AkShareClient)
    client.pool_repo = MagicMock()
    client.pool_repo.get_pool.return_value = _stale_pool()
    spot_rows = [{
        "代码": "sh515220",
        "名称": "煤炭ETF国泰",
        "最新价": 1.303,
        "涨跌幅": 0.851,
        "昨收": 1.292,
    }]

    with patch.object(client, "_load_category_spot_rows", return_value=spot_rows):
        refreshed = client.build_or_get_etf_pool()

    coal = next(item for item in refreshed if item["etf_code"] == "515220")
    assert coal["latest_price"] == 1.303
    assert coal["pct_change"] == 0.851
    client.pool_repo.update_quotes.assert_called_once()
    saved = client.pool_repo.update_quotes.call_args.args[0]
    assert ("515220", 1.303, 0.851) in saved


def test_extract_spot_quote_ignores_previous_close_when_latest_missing():
    assert AkShareClient.extract_spot_quote({"代码": "515220", "昨收": 1.292, "涨跌幅": -2.05}) is None
