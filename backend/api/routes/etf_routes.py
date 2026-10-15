"""
ETF相关路由模块
包含ETF信息查询、热门ETF列表、资金预设等接口
"""

from flask import Blueprint, jsonify
from services.analysis.etf_analysis_service import ETFAnalysisService

# 创建ETF蓝图
etf_bp = Blueprint('etf', __name__)
etf_service = ETFAnalysisService()

@etf_bp.route('/api/popular-etfs', methods=['GET'])
def get_popular_etfs():
    """获取热门ETF列表"""
    try:
        popular_etfs = etf_service.get_popular_etfs()
        return jsonify({
            'success': True,
            'data': popular_etfs
        })
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"获取热门ETF列表失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取热门ETF列表失败'
        }), 500

@etf_bp.route('/api/etf/basic-info/<etf_code>', methods=['GET'])
@etf_bp.route('/api/etf/info/<etf_code>', methods=['GET'])
def get_etf_basic_info(etf_code):
    """获取ETF基础信息"""
    try:
        # 验证ETF代码格式
        if not etf_code or len(etf_code) != 6 or not etf_code.isdigit():
            return jsonify({
                'success': False,
                'error': 'ETF代码格式错误，请输入6位数字'
            }), 400
        
        etf_info = etf_service.get_etf_basic_info(etf_code)
        return jsonify({
            'success': True,
            'data': etf_info
        })
        
    except ValueError as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 404
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"获取ETF基础信息失败: {etf_code}, {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取ETF信息失败，请检查代码是否正确'
        }), 500

@etf_bp.route('/api/capital-presets', methods=['GET'])
def get_capital_presets():
    """获取预设资金选项"""
    try:
        capital_presets = [
            {'value': 30000, 'label': '3万', 'popular': True},
            {'value': 50000, 'label': '5万', 'popular': True},
            {'value': 100000, 'label': '10万', 'popular': True},
            {'value': 200000, 'label': '20万', 'popular': True},
            {'value': 300000, 'label': '30万', 'popular': False},
            {'value': 500000, 'label': '50万', 'popular': True},
            {'value': 800000, 'label': '80万', 'popular': False},
            {'value': 1000000, 'label': '100万', 'popular': True}
        ]
        
        return jsonify({
            'success': True,
            'data': capital_presets
        })
        
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"获取预设资金选项失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取预设资金选项失败'
        }), 500


@etf_bp.route('/api/etf/pool', methods=['GET'])
def get_etf_pool():
    """获取全市场做 T ETF 标的池及正交赛道统计"""
    try:
        from flask import request
        sector = request.args.get('sector')
        is_t0_param = request.args.get('is_t0')
        is_t0 = True if is_t0_param in ('true', '1', 'True') else (False if is_t0_param in ('false', '0', 'False') else None)
        elasticity = request.args.get('elasticity')
        subsector = request.args.get('subsector')
        min_amount = float(request.args.get('min_amount', 0.0))
        min_ma20_amount = float(request.args.get('min_ma20_amount', 3000.0))
        min_atr = float(request.args.get('min_atr', 1.5))
        if min_atr < 1.0:
            min_atr = 1.0
        commodity_exempt = request.args.get('commodity_exempt') in ('1', 'true', 'True')
        force_refresh = request.args.get('refresh') in ('true', '1')

        pool_data = etf_service.get_etf_pool(
            sector=sector,
            is_t0=is_t0,
            elasticity=elasticity,
            subsector=subsector,
            min_amount_10k=min_amount,
            min_ma20_amount_10k=min_ma20_amount,
            min_atr_pct=min_atr,
            commodity_exempt=commodity_exempt,
            force_refresh=force_refresh
        )
        return jsonify({
            'success': True,
            'data': pool_data
        })
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"获取ETF做T标的池失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': '获取标的池失败，请稍后重试'
        }), 500
