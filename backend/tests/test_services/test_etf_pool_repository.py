import pytest
from backend.repositories.etf_pool_repository import ETFPoolRepository
from backend.repositories.mysql_connection import TEST_DATABASE
from backend.repositories.mysql_schema import reset_business_tables
from backend.tests.mysql_gate import skip_without_mysql


class TestETFPoolRepository:
    """测试 ETF 做 T 核心标的池仓库与持久化"""

    @pytest.fixture
    def temp_repo(self):
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)
        yield ETFPoolRepository(database=TEST_DATABASE)

    def test_save_and_query_pool(self, temp_repo):
        sample_data = [
            {
                "etf_code": "515220",
                "name": "煤炭ETF国泰",
                "sector": "周期资源",
                "is_t0": False,
                "list_date": "2020-01-20",
                "latest_price": 1.285,
                "pct_change": 1.26,
                "amount_10k": 14200.0,
                "amount_ma20_10k": 13500.0,
                "atr_pct": 2.35,
                "elasticity": "稳健型",
                "score": 85.0,
            },
            {
                "etf_code": "513180",
                "name": "恒生科技ETF",
                "sector": "科技芯片",
                "is_t0": True,
                "list_date": "2021-05-18",
                "latest_price": 0.582,
                "pct_change": -0.85,
                "amount_10k": 38500.0,
                "amount_ma20_10k": 36000.0,
                "atr_pct": 3.42,
                "elasticity": "高弹性",
                "score": 92.0,
            },
            {
                "etf_code": "510300",
                "name": "300ETF",
                "sector": "核心宽基",
                "is_t0": False,
                "list_date": "2012-05-04",
                "latest_price": 3.820,
                "pct_change": 0.15,
                "amount_10k": 95000.0,
                "amount_ma20_10k": 92000.0,
                "atr_pct": 1.65,
                "elasticity": "低波防守",
                "score": 88.0,
            },
            {
                "etf_code": "511360",
                "name": "短融ETF",
                "sector": "债券与固收",
                "is_t0": True,
                "list_date": "2020-03-02",
                "latest_price": 100.25,
                "pct_change": 0.01,
                "amount_10k": 500000.0,
                "amount_ma20_10k": 490000.0,
                "atr_pct": 0.40,
                "elasticity": "超低波死水",
                "score": 60.0,
            },
        ]

        count = temp_repo.save_pool(sample_data)
        assert count == 4
        assert temp_repo.get_count() == 4

        # 1. 默认查询全部（月均 >= 3000 万且 ATR >= 1.5%）
        all_items = temp_repo.get_pool(min_ma20_amount_10k=3000.0, min_atr_pct=1.5)
        # 短融 ETF (ATR 0.4%) 必须被完全过滤剔除
        assert len(all_items) == 3
        codes = [it["etf_code"] for it in all_items]
        assert "511360" not in codes
        assert all_items[0]["etf_code"] == "510300"  # 按月均成交额降序
        assert all_items[0]["amount_ma20_10k"] == 92000.0

        temp_repo.save_pool([
            {
                "etf_code": "518880",
                "name": "黄金ETF",
                "sector": "大宗商品",
                "is_t0": True,
                "amount_10k": 8000.0,
                "amount_ma20_10k": 8000.0,
                "atr_pct": 1.2,
                "elasticity": "低波防守",
                "score": 70.0,
            },
            {
                "etf_code": "512010",
                "name": "医药ETF",
                "sector": "医药健康",
                "is_t0": False,
                "amount_10k": 8000.0,
                "amount_ma20_10k": 8000.0,
                "atr_pct": 1.2,
                "elasticity": "低波防守",
                "score": 70.0,
            },
        ])
        strict = {item["etf_code"] for item in temp_repo.get_pool(min_ma20_amount_10k=3000.0, min_atr_pct=1.5)}
        assert "518880" not in strict
        assert "512010" not in strict
        widened = {item["etf_code"] for item in temp_repo.get_pool(min_ma20_amount_10k=3000.0, min_atr_pct=1.0)}
        assert "518880" in widened and "512010" in widened
        exempt = {
            item["etf_code"]
            for item in temp_repo.get_pool(min_ma20_amount_10k=3000.0, min_atr_pct=1.5, commodity_exempt=True)
        }
        assert "518880" in exempt
        assert "512010" not in exempt

        # 2. 筛选 T+0 标的
        t0_items = temp_repo.get_pool(is_t0=True)
        assert len(t0_items) == 1
        assert t0_items[0]["etf_code"] == "513180"

        # 3. 筛选赛道
        tech_items = temp_repo.get_pool(sector="科技芯片")
        assert len(tech_items) == 1
        assert tech_items[0]["name"] == "恒生科技ETF"

        # 4. 统计汇总
        summary = temp_repo.get_sectors_summary()
        assert summary["total_count"] == 3
        assert summary["t0_count"] == 1
        assert len(summary["sectors"]) == 3
