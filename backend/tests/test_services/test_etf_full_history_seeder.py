import pytest
from backend.services.data.akshare_client import AkShareClient
from backend.repositories.market_data_repository import MarketDataRepository
from backend.tests.mysql_gate import skip_without_mysql


class TestETFFullHistorySeeder:
    """ETF 上市以来全生命周期数据初始化与落盘测试套件"""

    @pytest.fixture
    def client(self):
        skip_without_mysql()
        return AkShareClient()

    @pytest.fixture
    def market_repo(self):
        return MarketDataRepository()

    def test_seed_515220_full_history_to_sqlite(self, client, market_repo):
        """测试并初始化 515220 煤炭ETF自上市以来的全生命周期数据落盘"""
        # 1. 触发全量历史同步
        df = client.sync_full_history("515220")

        # 2. 校验返回结果
        assert df is not None
        assert not df.empty
        assert len(df) >= 1250, f"515220 上市至今 K 线数量应 >= 1250 根，实际为 {len(df)}"

        # 3. 校验历史起点可追溯到 2021 或更早
        first_date = str(df.iloc[0]["trade_date"])[:10]
        latest_date = str(df.iloc[-1]["trade_date"])[:10]
        print(f"\n✓ 515220 历史起点: {first_date}, 最新日期: {latest_date}, 总根数: {len(df)}")
        assert first_date <= "2021-08-01"

        # 4. 从本地 SQLite 数据库中直接读取断言
        db_bars = market_repo.get_all_bars("515220")
        assert len(db_bars) == len(df)
        assert not db_bars[["open", "close", "high", "low"]].isna().any().any()

        # 5. 校验字段完整性
        required_cols = {"open", "close", "high", "low", "vol", "amount", "pct_chg"}
        assert required_cols.issubset(set(db_bars.columns))

    def test_seed_core_active_etfs_batch(self, client, market_repo):
        """批量测试并初始化全市场核心做 T 龙头标的 (证券512880, 半导体512760, 恒生科技513180)"""
        core_targets = [
            ("512880", "证券ETF", "2017-01-01"),
            ("512760", "半导体ETF", "2020-01-01"),
            ("513180", "恒生科技ETF", "2021-06-01")
        ]
        
        for code, name, max_first_date in core_targets:
            df = client.sync_full_history(code)
            assert df is not None and not df.empty
            first_date = str(df.iloc[0]["trade_date"])[:10]
            latest_date = str(df.iloc[-1]["trade_date"])[:10]
            print(f"\n✓ 成功批量初始化 {code} {name}: 历史起点 {first_date} 至 {latest_date}, 累计 {len(df)} 根 K 线已落盘")
            assert first_date <= max_first_date
            
            # 校验 SQLite 数据库直出
            db_bars = market_repo.get_all_bars(code)
            assert len(db_bars) == len(df)
            assert not db_bars[["open", "close", "high", "low"]].isna().any().any()
