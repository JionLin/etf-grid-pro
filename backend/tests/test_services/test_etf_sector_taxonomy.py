import pytest

from backend.repositories.etf_pool_repository import SHOPPABLE_SECTORS, ETFPoolRepository
from backend.services.data.akshare_client import AkShareClient


class TestEtfSectorTaxonomy:
    @pytest.mark.parametrize(
        "name,sector",
        [
            ("纳指ETF广发", "跨境全球"),
            ("道琼斯ETF鹏华", "跨境全球"),
            ("巴西ETF易方达", "跨境全球"),
            ("日本东证指数ETF南方", "跨境全球"),
            ("金ETF富国", "大宗商品"),
            ("上海金ETF中银", "大宗商品"),
            ("机器人ETF易方达", "科技芯片"),
            ("卫星ETF永赢", "科技芯片"),
            ("云计算ETF华夏", "科技芯片"),
            ("集成电路ETF国泰", "科技芯片"),
            ("科技ETF华宝", "科技芯片"),
            ("5GETF博时", "科技芯片"),
            ("影视ETF国泰", "科技芯片"),
            ("石油ETF国泰", "周期资源"),
            ("石化ETF华夏", "周期资源"),
            ("矿业ETF国泰", "周期资源"),
            ("建材ETF国泰", "周期资源"),
            ("机床ETF华夏", "新能源制造"),
            ("电网设备ETF华夏", "新能源制造"),
            ("船舶ETF富国", "新能源制造"),
            ("上证指数ETF富国", "核心宽基"),
            ("深证100ETF易方达", "核心宽基"),
            ("中证800ETF汇添富", "核心宽基"),
            ("科创200ETF华泰柏瑞", "核心宽基"),
            ("科创创业ETF易方达", "核心宽基"),
            ("价值ETF富国", "核心宽基"),
            ("成长ETF易方达", "核心宽基"),
            ("自由现金流ETF华夏", "核心宽基"),
            ("金融ETF国泰", "大金融"),
            ("粮食ETF鹏华", "大消费"),
        ],
    )
    def test_leaked_names_land_in_shoppable_sectors(self, name, sector):
        classified = AkShareClient.classify_etf_item(name, "000000")
        assert classified["excluded"] is False
        assert classified["sector"] == sector
        assert sector in SHOPPABLE_SECTORS

    @pytest.mark.parametrize(
        "name",
        ["银华日利ETF", "华宝添益ETF", "货币ETF易方达", "快钱ETF汇添富", "招商快线ETF", "招商财富宝ETF"],
    )
    def test_cash_products_are_excluded_before_atr(self, name):
        classified = AkShareClient.classify_etf_item(name, "511880")
        assert classified["excluded"] is True
        assert classified["sector"] not in SHOPPABLE_SECTORS
        assert classified["atr_pct"] < 1.5

    def test_unmapped_names_are_unclassified_not_other_theme(self):
        for name in ("成渝经济圈ETF博时", "上海国企ETF汇添富"):
            classified = AkShareClient.classify_etf_item(name, "159623")
            assert classified["sector"] == "未归类"
            assert classified["sector"] != "其他主题"

    def test_summary_total_equals_eleven_sectors_and_excludes_cash(self):
        from backend.repositories.mysql_connection import TEST_DATABASE
        from backend.repositories.mysql_schema import reset_business_tables
        from backend.tests.mysql_gate import skip_without_mysql
        skip_without_mysql()
        reset_business_tables(TEST_DATABASE)
        repo = ETFPoolRepository(database=TEST_DATABASE)
        repo.save_pool([
            _row("515220", "煤炭ETF国泰", "其他主题"),
            _row("159941", "纳指ETF广发", "其他主题"),
            _row("511880", "银华日利ETF", "其他主题"),
            _row("159623", "成渝经济圈ETF博时", "其他主题"),
            _row("510810", "上海国企ETF汇添富", "其他主题"),
        ])
        repo.reclassify_persisted(AkShareClient.classify_etf_item)

        summary = repo.get_sectors_summary()
        sector_sum = sum(item["count"] for item in summary["sectors"])
        assert summary["total_count"] == sector_sum
        assert "其他主题" not in {item["name"] for item in summary["sectors"]}
        assert summary["unclassified_count"] == 2
        pooled_codes = {item["etf_code"] for item in repo.get_pool(limit=50)}
        assert "511880" not in pooled_codes
        assert "159623" not in pooled_codes
        assert "159941" in pooled_codes


def _row(code, name, sector):
    return {
        "etf_code": code,
        "name": name,
        "sector": sector,
        "is_t0": False,
        "list_date": "2020-01-01",
        "latest_price": 1.0,
        "pct_change": 0.0,
        "amount_10k": 10000.0,
        "amount_ma20_10k": 9000.0,
        "atr_pct": 2.0,
        "elasticity": "稳健型",
        "score": 80.0,
    }
