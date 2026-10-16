"""新拉到的长历史要让首页 3 年 / 5 年成熟数量增加。"""

from repositories.market_data_repository import MarketDataRepository
from repositories.universe_matrix_repository import UniverseMatrixRepository
from services.analysis.universe_matrix_backtest_service import UniverseMatrixBacktestService


def _bars(code: str, start: str, periods: int) -> None:
    import pandas as pd

    days = pd.bdate_range(start, periods=periods)
    rows = []
    price = 1.0
    for day in days:
        price = round(price * 1.001, 4)
        rows.append({
            "trade_date": day.strftime("%Y-%m-%d"),
            "open": price,
            "close": round(price * 1.002, 4),
            "high": round(price * 1.01, 4),
            "low": round(price * 0.99, 4),
            "vol": 10000,
            "amount": 10000 * price * 100,
            "pct_chg": 0.2,
        })
    MarketDataRepository().save_bars(code, rows)


def _cleanup(codes) -> None:
    market = MarketDataRepository()
    matrix = UniverseMatrixRepository()
    market_conn = market._connect()
    matrix_conn = matrix._connect()
    try:
        with market_conn.cursor() as cursor:
            for code in codes:
                cursor.execute("DELETE FROM etf_daily_bar WHERE etf_code = %s", (code,))
        market_conn.commit()
        with matrix_conn.cursor() as cursor:
            for code in codes:
                cursor.execute("DELETE FROM universe_matrix_backtest WHERE etf_code = %s", (code,))
        matrix_conn.commit()
    finally:
        market_conn.close()
        matrix_conn.close()


def test_five_year_bars_raise_maturity_counts_on_a_fresh_database():
    codes = ("990511", "990512", "990513")
    _cleanup(codes)
    matrix = UniverseMatrixRepository()
    seeded = {
        "etf_code": "990511",
        "etf_name": "旧的五年",
        "sector": "核心宽基",
        "total_bars": 1200,
        "step_mode": "atr",
        "periods": {
            "3y": {"is_valid": True, "annual_return": 8.0, "max_drawdown": 10.0, "calmar_ratio": 0.8, "trade_count": 20, "free_shares": 100, "base_price": 1.0},
            "5y": {"is_valid": True, "annual_return": 6.0, "max_drawdown": 12.0, "calmar_ratio": 0.5, "trade_count": 40, "free_shares": 100, "base_price": 1.0},
        },
    }
    matrix.batch_save([seeded])
    before = matrix.get_validity_map()
    assert before["990511"]["is_valid_5y"] is True
    assert before["990511"]["is_valid_3y"] is True
    before_count = sum(
        1 for code in codes if before.get(code, {}).get("is_valid_5y")
    )

    _bars("990512", "2021-01-04", 1400)
    _bars("990513", "2024-06-03", 120)
    service = UniverseMatrixBacktestService()
    fresh = service.run_universe_matrix(
        instruments=[
            {"etf_code": "990512", "etf_name": "新的长历史", "sector": "核心宽基"},
            {"etf_code": "990513", "etf_name": "只有一截", "sector": "核心宽基"},
        ],
        workers=1,
    )
    matrix.batch_save(fresh)
    after = matrix.get_validity_map()
    after_count = sum(1 for code in codes if after.get(code, {}).get("is_valid_5y"))
    after_3y = sum(1 for code in codes if after.get(code, {}).get("is_valid_3y"))
    assert after["990512"]["is_valid_5y"] is True
    assert after["990512"]["is_valid_3y"] is True
    assert after["990513"]["is_valid_5y"] is False
    assert after_count == before_count + 1
    assert after_3y >= after_count
    _cleanup(codes)
