"""
单元测试：价格区间与核心参数随步长生成模式 (step_mode) 动态联动测试
覆盖 E大原版模式 (fixed_eda) 与 ATR 自适应模式下的价格区间极值对齐、主步长对齐与文案自适应
"""

import pytest
from backend.services.analysis.etf_analysis_service import ETFAnalysisService
from backend.tests.mysql_gate import skip_without_mysql


@pytest.fixture
def analysis_service():
    skip_without_mysql()
    return ETFAnalysisService()


@pytest.fixture
def mock_market_context():
    return {
        'latest_price_info': {'current_price': 1.000, 'timestamp': '2026-09-11'},
        'atr_analysis': {'current_atr_ratio': 0.02, 'current_atr_pct': 2.0},
        'market_indicators': {
            'volatility': 0.25,
            'adx_value': 18.0
        }
    }


def test_fixed_eda_price_range_and_params_sync(analysis_service, mock_market_context):
    """验证 E大原版模式下价格区间、主步长、总档位与挂单阶梯极值100%对齐"""
    res = analysis_service._calculate_grid_parameters(
        latest_price_info=mock_market_context['latest_price_info'],
        atr_analysis=mock_market_context['atr_analysis'],
        market_indicators=mock_market_context['market_indicators'],
        total_capital=100000,
        grid_type='等差',
        risk_preference='平衡型',
        step_mode='fixed_eda',
        eda_step_ratios={'small': 0.05, 'medium': 0.15, 'large': 0.30}
    )

    composite_grid = res['composite_grid']
    all_buys = []
    all_sells = []
    for r in composite_grid['rails'].values():
        all_buys.extend(r['buy_levels'])
        all_sells.extend(r['sell_levels'])

    # 1. 验证价格区间严格对齐最低买入单与最高卖出单
    assert res['price_range']['lower'] == min(x['price'] for x in all_buys)
    assert res['price_range']['upper'] == max(x['price'] for x in all_sells)
    expected_ratio = (res['price_range']['upper'] - res['price_range']['lower']) / 1.000
    assert abs(res['price_range']['ratio'] - expected_ratio) < 1e-4

    # 2. 验证看板主步长对齐小网步长 5%
    assert res['grid_config']['step_ratio'] == 0.05
    assert res['grid_config']['step_size'] == 0.05

    # 3. 验证总档位数对齐有效买卖档位总和
    assert res['grid_config']['count'] == len(all_buys) + len(all_sells)

    # 4. 验证推导文本包含 E大步长说明
    assert "E大原版" in res['calculation_method']
    assert "E大原版/自定义立体三轨" in res['calculation_logic']['step1']


def test_atr_mode_price_range_and_params_sync(analysis_service, mock_market_context):
    """验证 ATR 自适应模式下价格区间与挂单阶梯同样自适应对齐"""
    res = analysis_service._calculate_grid_parameters(
        latest_price_info=mock_market_context['latest_price_info'],
        atr_analysis=mock_market_context['atr_analysis'],
        market_indicators=mock_market_context['market_indicators'],
        total_capital=100000,
        grid_type='等差',
        risk_preference='平衡型',
        step_mode='atr'
    )

    composite_grid = res['composite_grid']
    all_buys = []
    all_sells = []
    for r in composite_grid['rails'].values():
        all_buys.extend(r['buy_levels'])
        all_sells.extend(r['sell_levels'])

    assert res['price_range']['lower'] == min(x['price'] for x in all_buys)
    assert res['price_range']['upper'] == max(x['price'] for x in all_sells)
    assert res['grid_config']['count'] == len(all_buys) + len(all_sells)
    assert res['calculation_method'] == "ATR智能算法"


def test_strategy_rationale_step_mode_adaptation(analysis_service, mock_market_context):
    """验证策略分析依据卡片针对 step_mode 自适应文案"""
    suitability_result = {
        'atr_analysis': mock_market_context['atr_analysis'],
        'market_indicators': mock_market_context['market_indicators'],
        'evaluations': {
            'market_characteristics': {'market_type': '震荡市'},
            'liquidity': {'level': '充沛'}
        }
    }
    grid_params = {
        'price_range': {'lower': 0.400, 'upper': 1.600},
        'grid_config': {'count': 20, 'type': '等差', 'step_ratio': 0.05},
        'fund_allocation': {'base_position_ratio': 0.5}
    }

    # 测试 E大模式
    rationale_eda = analysis_service._generate_strategy_rationale(
        suitability_result, grid_params, '平衡型', step_mode='fixed_eda'
    )
    assert "E大立体三轨" in rationale_eda['parameter_logic']['price_range']
    assert "小网5.0%基础步长" in rationale_eda['profit_basis']['parameter_optimization']

    # 测试 ATR 模式
    rationale_atr = analysis_service._generate_strategy_rationale(
        suitability_result, grid_params, '平衡型', step_mode='atr'
    )
    assert "基于ATR比率" in rationale_atr['parameter_logic']['price_range']
    assert "基于ATR算法" in rationale_atr['profit_basis']['parameter_optimization']


def test_fund_allocation_real_quant_metrics(analysis_service, mock_market_context):
    """验证 fund_allocation 全量包含来自复合多轨底层的真实量化指标，杜绝假数据"""
    res = analysis_service._calculate_grid_parameters(
        latest_price_info=mock_market_context['latest_price_info'],
        atr_analysis=mock_market_context['atr_analysis'],
        market_indicators=mock_market_context['market_indicators'],
        total_capital=100000,
        grid_type='等差',
        risk_preference='平衡型',
        step_mode='fixed_eda',
        eda_step_ratios={'small': 0.05, 'medium': 0.15, 'large': 0.30}
    )

    fa = res['fund_allocation']
    comp = res['composite_grid']

    # 1. 底仓资金与比例来自 base_position 真实对象
    assert fa['base_position_amount'] == comp['base_position']['actual_capital']
    assert fa['base_position_ratio'] == comp['base_position']['ratio']

    # 2. 网格交易资金来自 liquid_capital 真实对象
    assert fa['grid_trading_amount'] == comp['liquid_capital']
    assert fa['grid_funds_amount'] == comp['liquid_capital']

    # 3. 预留机动资金与资金利用率实打实推算
    all_buys = []
    for r in comp['rails'].values():
        all_buys.extend(r['buy_levels'])
    expected_buy_sum = sum(b['amount'] for b in all_buys)
    expected_reserve = round(100000 - comp['base_position']['actual_capital'] - expected_buy_sum, 2)
    expected_utilization = round(expected_buy_sum / comp['liquid_capital'], 4)

    assert fa['reserve_amount'] == expected_reserve
    assert fa['grid_fund_utilization_rate'] == expected_utilization

    # 4. 单笔股数与预期净利来自小网真实档位
    small_buy_1 = comp['rails']['small']['buy_levels'][0]
    assert fa['single_trade_quantity'] == small_buy_1['shares']
    assert fa['expected_profit_per_trade'] == small_buy_1['est_profit']

