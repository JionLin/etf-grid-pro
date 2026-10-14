"""
分析相关路由模块
包含ETF网格交易策略分析接口
"""

from flask import Blueprint, request, jsonify
import traceback
from services.analysis.etf_analysis_service import ETFAnalysisService
from services.analysis.grid_fit_service import (
    GridFitBoardService,
    build_protocol_callbacks,
    start_background_batch,
)
from repositories.backtest_repository import BacktestRepository
from repositories.etf_pool_repository import ETFPoolRepository
from services.analysis.analysis_days import resolve_analysis_days

# 创建分析蓝图
analysis_bp = Blueprint('analysis', __name__)
etf_service = ETFAnalysisService()
backtest_repo = BacktestRepository()
pool_repo = ETFPoolRepository()
grid_fit_service = GridFitBoardService()

@analysis_bp.route('/api/analyze', methods=['POST'])
def analyze_etf_strategy():
    """ETF网格交易策略分析"""
    try:
        # 获取请求参数
        data = request.get_json()
        if not data:
            return jsonify({
                'success': False,
                'error': '请求参数不能为空'
            }), 400
        
        # 验证必需参数
        required_fields = ['etfCode', 'totalCapital', 'gridType', 'riskPreference']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'缺少必需参数: {field}'
                }), 400
        
        # 参数验证
        etf_code = data['etfCode'].strip()
        if not etf_code or len(etf_code) != 6 or not etf_code.isdigit():
            return jsonify({
                'success': False,
                'error': 'ETF代码格式错误，请输入6位数字'
            }), 400
        
        total_capital = float(data['totalCapital'])
        if total_capital < 10000 or total_capital > 1000000:
            return jsonify({
                'success': False,
                'error': '投资金额应在1万-100万之间'
            }), 400
        
        grid_type = data['gridType']
        if grid_type not in ['等差', '等比']:
            return jsonify({
                'success': False,
                'error': '网格类型只能是"等差"或"等比"'
            }), 400
        
        risk_preference = data['riskPreference']
        if risk_preference not in ['低频', '均衡', '高频']:
            return jsonify({
                'success': False,
                'error': '频率偏好只能是"低频"、"均衡"或"高频"'
            }), 400
        
        # 获取调节系数（可选参数，默认1.0）
        adjustment_coefficient = float(data.get('adjustmentCoefficient', 1.0))
        if adjustment_coefficient < 0.0 or adjustment_coefficient > 2.0:
            return jsonify({
                'success': False,
                'error': '调节系数应在0.0-2.0之间'
            }), 400
        
        # 支持 90/180/365/1825。名单外返回 400，不再静默退回 180。
        analysis_days = resolve_analysis_days(data.get('analysisDays', 180))

        # 获取逐格加码比例（可选参数，默认0.0，范围0.0-0.20）
        scaling_ratio = float(data.get('scalingRatio', data.get('scaling_ratio', 0.0)))
        if scaling_ratio < 0.0 or scaling_ratio > 0.50:
            scaling_ratio = 0.0

        # 获取步长生成模式（可选参数，默认'atr'，支持'atr'或'fixed_eda'）
        step_mode = str(data.get('stepMode', data.get('step_mode', 'atr')))
        if step_mode not in ['atr', 'fixed_eda']:
            step_mode = 'atr'

        # 获取自定义基准价格（可选参数，默认None）
        raw_price = data.get('benchmarkPrice', data.get('benchmark_price'))
        try:
            benchmark_price = float(raw_price) if raw_price not in [None, '', 'null'] else None
            if benchmark_price is not None and benchmark_price <= 0:
                benchmark_price = None
        except (ValueError, TypeError):
            benchmark_price = None

        # 获取 E大原版自定义各轨步长比例 (可选参数)
        eda_step_ratios = None
        raw_eda = data.get('edaStepRatios', data.get('eda_step_ratios', data.get('edaSteps', data.get('eda_steps'))))
        if raw_eda and step_mode == 'fixed_eda':
            ratios = {}
            if isinstance(raw_eda, str):
                parts = [p.strip() for p in raw_eda.split(',') if p.strip()]
                if len(parts) == 3:
                    try:
                        vals = [float(p) for p in parts]
                        v_small = vals[0] / 100.0 if vals[0] >= 1.0 else vals[0]
                        v_medium = vals[1] / 100.0 if vals[1] >= 1.0 else vals[1]
                        v_large = vals[2] / 100.0 if vals[2] >= 1.0 else vals[2]
                        ratios = {'small': v_small, 'medium': v_medium, 'large': v_large}
                    except (ValueError, TypeError):
                        pass
            elif isinstance(raw_eda, dict):
                for rail in ['small', 'medium', 'large']:
                    if rail in raw_eda and raw_eda[rail] is not None:
                        try:
                            val = float(raw_eda[rail])
                            ratios[rail] = val / 100.0 if val >= 1.0 else val
                        except (ValueError, TypeError):
                            pass
            if len(ratios) == 3:
                s, m, l = ratios['small'], ratios['medium'], ratios['large']
                if 0.005 <= s < m < l <= 0.55:
                    eda_step_ratios = {
                        'small': round(s, 4),
                        'medium': round(m, 4),
                        'large': round(l, 4),
                    }

        # 获取 ATR 模式下自定义各轨乘数 (可选参数)
        atr_multipliers = None
        raw_atr_m = data.get('atrMultipliers', data.get('atr_multipliers'))
        if raw_atr_m and step_mode == 'atr':
            mults = {}
            if isinstance(raw_atr_m, str):
                parts = [p.strip() for p in raw_atr_m.split(',') if p.strip()]
                if len(parts) == 3:
                    try:
                        vals = [float(p) for p in parts]
                        mults = {'small': vals[0], 'medium': vals[1], 'large': vals[2]}
                    except (ValueError, TypeError):
                        pass
            elif isinstance(raw_atr_m, dict):
                for rail in ['small', 'medium', 'large']:
                    if rail in raw_atr_m and raw_atr_m[rail] is not None:
                        try:
                            mults[rail] = float(raw_atr_m[rail])
                        except (ValueError, TypeError):
                            pass
            if len(mults) == 3:
                s, m, l = mults['small'], mults['medium'], mults['large']
                if 0.1 <= s < m < l <= 10.0:
                    atr_multipliers = {
                        'small': round(s, 2),
                        'medium': round(m, 2),
                        'large': round(l, 2),
                    }
        
        from flask import current_app
        current_app.logger.info(f"开始分析ETF策略: {etf_code}, 资金{total_capital}, "
                   f"{grid_type}网格, {risk_preference}, 加码{scaling_ratio}, 步长模式{step_mode}, 基准价{benchmark_price}, 自定义步长{eda_step_ratios}, 自定义乘数{atr_multipliers}, 周期{analysis_days}天")
        
        # 执行分析
        analysis_result = etf_service.analyze_etf_strategy(
            etf_code=etf_code,
            total_capital=total_capital,
            grid_type=grid_type,
            risk_preference=risk_preference,
            adjustment_coefficient=adjustment_coefficient,
            analysis_days=analysis_days,
            scaling_ratio=scaling_ratio,
            step_mode=step_mode,
            benchmark_price=benchmark_price,
            eda_step_ratios=eda_step_ratios,
            atr_multipliers=atr_multipliers,
        )
        
        current_app.logger.info(f"ETF策略分析完成: {etf_code}, "
                   f"适宜度评分{analysis_result['suitability_evaluation']['total_score']}")
        
        return jsonify({
            'success': True,
            'data': analysis_result
        })
        
    except ValueError as e:
        from flask import current_app
        current_app.logger.error(f"参数验证失败: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"ETF策略分析失败: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': '分析失败，请稍后重试或检查ETF代码是否正确'
        }), 500

@analysis_bp.route('/api/backtest', methods=['POST'])
def run_backtest():
    """网格策略真实历史回测"""
    try:
        data = request.get_json() or {}
        etf_code = data.get('etfCode') or data.get('etf_code')
        if not etf_code:
            return jsonify({'success': False, 'error': 'ETF代码不能为空'}), 400

        total_capital = float(data.get('totalCapital', data.get('total_capital', 100000)))
        backtest_days = int(data.get('backtestDays', data.get('backtest_days', 180)))
        backtest_days = max(30, min(1825, backtest_days))
        adjustment_coefficient = float(data.get('adjustmentCoefficient', 1.0))
        scaling_ratio = float(data.get('scalingRatio', data.get('scaling_ratio', 0.0)))
        risk_preference = str(data.get('riskPreference', data.get('risk_preference', '均衡')))
        if risk_preference not in ['低频', '均衡', '高频']:
            risk_preference = '均衡'
        reinvest_mode = str(data.get('reinvestMode', data.get('reinvest_mode', 'cash')))
        step_mode = str(data.get('stepMode', data.get('step_mode', 'atr')))
        if step_mode not in ['atr', 'fixed_eda']:
            step_mode = 'atr'

        # 获取 E大原版自定义各轨步长比例 (可选参数)
        eda_step_ratios = None
        raw_eda = data.get('edaStepRatios', data.get('eda_step_ratios', data.get('edaSteps', data.get('eda_steps'))))
        if raw_eda and step_mode == 'fixed_eda':
            ratios = {}
            if isinstance(raw_eda, str):
                parts = [p.strip() for p in raw_eda.split(',') if p.strip()]
                if len(parts) == 3:
                    try:
                        vals = [float(p) for p in parts]
                        v_small = vals[0] / 100.0 if vals[0] >= 1.0 else vals[0]
                        v_medium = vals[1] / 100.0 if vals[1] >= 1.0 else vals[1]
                        v_large = vals[2] / 100.0 if vals[2] >= 1.0 else vals[2]
                        ratios = {'small': v_small, 'medium': v_medium, 'large': v_large}
                    except (ValueError, TypeError):
                        pass
            elif isinstance(raw_eda, dict):
                for rail in ['small', 'medium', 'large']:
                    if rail in raw_eda and raw_eda[rail] is not None:
                        try:
                            val = float(raw_eda[rail])
                            ratios[rail] = val / 100.0 if val >= 1.0 else val
                        except (ValueError, TypeError):
                            pass
            if len(ratios) == 3:
                s, m, l = ratios['small'], ratios['medium'], ratios['large']
                if 0.005 <= s < m < l <= 0.55:
                    eda_step_ratios = {
                        'small': round(s, 4),
                        'medium': round(m, 4),
                        'large': round(l, 4),
                    }

        # 获取 ATR 模式下自定义各轨乘数 (可选参数)
        atr_multipliers = None
        raw_atr_m = data.get('atrMultipliers', data.get('atr_multipliers'))
        if raw_atr_m and step_mode == 'atr':
            mults = {}
            if isinstance(raw_atr_m, str):
                parts = [p.strip() for p in raw_atr_m.split(',') if p.strip()]
                if len(parts) == 3:
                    try:
                        vals = [float(p) for p in parts]
                        mults = {'small': vals[0], 'medium': vals[1], 'large': vals[2]}
                    except (ValueError, TypeError):
                        pass
            elif isinstance(raw_atr_m, dict):
                for rail in ['small', 'medium', 'large']:
                    if rail in raw_atr_m and raw_atr_m[rail] is not None:
                        try:
                            mults[rail] = float(raw_atr_m[rail])
                        except (ValueError, TypeError):
                            pass
            if len(mults) == 3:
                s, m, l = mults['small'], mults['medium'], mults['large']
                if 0.1 <= s < m < l <= 10.0:
                    atr_multipliers = {
                        'small': round(s, 2),
                        'medium': round(m, 2),
                        'large': round(l, 2),
                    }

        # 接收可选的自定义回测基准锚点价格
        custom_base_price = data.get('customBasePrice', data.get('custom_base_price'))
        if custom_base_price is not None:
            try:
                custom_base_price = float(custom_base_price)
                if custom_base_price <= 0:
                    custom_base_price = None
            except (ValueError, TypeError):
                custom_base_price = None

        result = etf_service.run_strategy_backtest(
            etf_code=etf_code,
            total_capital=total_capital,
            backtest_days=backtest_days,
            adjustment_coefficient=adjustment_coefficient,
            scaling_ratio=scaling_ratio,
            reinvest_mode=reinvest_mode,
            step_mode=step_mode,
            eda_step_ratios=eda_step_ratios,
            custom_base_price=custom_base_price,
            atr_multipliers=atr_multipliers,
            risk_preference=risk_preference,
        )

        # 自动归档至本地 SQLite 回测档案库
        try:
            etf_name = etf_service.resolve_etf_name(etf_code)
            run_id = backtest_repo.save_run(
                etf_code=etf_code,
                etf_name=etf_name,
                backtest_days=backtest_days,
                total_capital=total_capital,
                step_mode=step_mode,
                reinvest_mode=reinvest_mode,
                backtest_result=result,
                params=data,
            )
            result['run_id'] = run_id
            if 'summary' in result and isinstance(result['summary'], dict):
                result['summary']['run_id'] = run_id
        except Exception as repo_err:
            from flask import current_app
            current_app.logger.warning(f"自动保存回测档案失败 (非阻塞): {str(repo_err)}")

        return jsonify({'success': True, 'data': result})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"策略回测失败: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({'success': False, 'error': f"回测计算异常: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/records', methods=['GET'])
def get_backtest_records():
    """获取历史回测档案列表 (支持按标的和周期筛选，支持最新去重)"""
    try:
        etf_code = request.args.get('etfCode') or request.args.get('etf_code')
        days = request.args.get('days')
        days_int = int(days) if days and days.isdigit() else None
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        latest_only_param = request.args.get('latestOnly', request.args.get('latest_only', 'true'))
        latest_only = str(latest_only_param).lower() in ['true', '1', 'yes']
        step_mode = request.args.get('stepMode') or request.args.get('step_mode')
        sector = request.args.get('sector')

        records_data = backtest_repo.list_runs(
            etf_code=etf_code,
            days=days_int,
            limit=limit,
            offset=offset,
            latest_only=latest_only,
            step_mode=step_mode,
            sector=sector,
            sector_map=pool_repo.list_sector_map(),
        )
        return jsonify({'success': True, 'data': records_data})
    except Exception as e:
        return jsonify({'success': False, 'error': f"获取回测档案列表失败: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/records/<run_id>', methods=['GET'])
def get_backtest_record_detail(run_id: str):
    """获取单次回测档案完整快照 (无需重算即时还原)"""
    try:
        record = backtest_repo.get_run_detail(run_id)
        if not record:
            return jsonify({'success': False, 'error': '未找到该回测档案'}), 404
        return jsonify({'success': True, 'data': record})
    except Exception as e:
        return jsonify({'success': False, 'error': f"读取回测明细失败: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/records/<run_id>', methods=['DELETE'])
def delete_backtest_record(run_id: str):
    """删除指定回测档案"""
    try:
        success = backtest_repo.delete_run(run_id)
        if not success:
            return jsonify({'success': False, 'error': '回测记录不存在或已删除'}), 404
        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': f"删除回测档案失败: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/distinct-etfs', methods=['GET'])
def get_distinct_etfs_in_records():
    """获取回测档案库中所有测试过的 ETF 标的列表"""
    try:
        etfs = backtest_repo.get_distinct_etfs()
        return jsonify({'success': True, 'data': etfs})
    except Exception as e:
        return jsonify({'success': False, 'error': f"获取标的列表失败: {str(e)}"}), 500


@analysis_bp.route('/api/grid-fit/board', methods=['GET'])
def get_grid_fit_board():
    """适合度榜。读取独立榜表，不读个人回测档案。"""
    try:
        sector = request.args.get('sector')
        payload = grid_fit_service.list_board(
            sector=sector,
            sector_map=pool_repo.list_sector_map(),
        )
        return jsonify({'success': True, 'data': payload})
    except Exception as e:
        return jsonify({'success': False, 'error': f"读取适合度榜失败: {str(e)}"}), 500


@analysis_bp.route('/api/grid-fit/progress', methods=['GET'])
def get_grid_fit_progress():
    """查询本轮补齐进度。单只失败不让查询整体失败。"""
    try:
        payload = grid_fit_service.list_board(sector_map=pool_repo.list_sector_map())
        return jsonify({
            'success': True,
            'data': {
                'progress': payload['progress'],
                'job': payload['job'],
                'failed': payload['failed'],
            },
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f"读取适合度榜进度失败: {str(e)}"}), 500


@analysis_bp.route('/api/grid-fit/refresh', methods=['POST'])
def refresh_grid_fit():
    """按锁定协议补行情并写榜。不调用个人档案自动归档。"""
    try:
        pool_repo.mark_seed_representatives()
        universe = [
            {
                "etf_code": item["etf_code"],
                "etf_name": item["etf_name"],
                "sector": item["sector"],
            }
            for item in pool_repo.list_seeds()
        ]
        sync_fn, backtest_fn = build_protocol_callbacks(
            etf_service,
            etf_service.akshare_client,
        )
        started = start_background_batch(
            universe,
            sync_fn,
            backtest_fn,
            grid_fit_service.repo,
        )
        return jsonify({'success': True, 'data': started})
    except Exception as e:
        return jsonify({'success': False, 'error': f"启动适合度榜补齐失败: {str(e)}"}), 500


@analysis_bp.route('/api/literature/eda-grid', methods=['GET'])
def get_eda_literature():
    """获取 E大网格实战三篇经典文献"""
    try:
        import os
        possible_paths = [
            os.path.join(os.path.dirname(__file__), '..', '..', '..', 'E大', '网格3篇.md'),
            os.path.join(os.getcwd(), 'E大', '网格3篇.md'),
            '/Users/johnny/Desktop/github/etf-grid-design/E大/网格3篇.md',
        ]
        file_path = None
        for p in possible_paths:
            if os.path.exists(p):
                file_path = p
                break

        if not file_path:
            return jsonify({'success': False, 'error': '未找到文献文件'}), 404

        with open(file_path, 'r', encoding='utf-8') as f:
            full_text = f.read()

        # 分割三篇
        parts = full_text.split('# 网格')
        articles = []
        for part in parts:
            part = part.strip()
            if not part:
                continue
            lines = part.split('\n')
            title = lines[0].strip()
            content = '\n'.join(lines[1:]).strip()
            articles.append({
                'id': len(articles) + 1,
                'title': f'网格{title}',
                'content': content,
            })

        return jsonify({
            'success': True,
            'data': {
                'title': 'E大（ETF拯救世界）网格策略全集',
                'author': 'ETF拯救世界',
                'description': '历经十余年实证检验的经典波段与情绪收割系统：1.0基础与压力测试、2.0留利润/逐格加码/一网打尽',
                'articles': articles,
                'total_articles': len(articles),
            }
        })
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"读取文献失败: {str(e)}")
        return jsonify({'success': False, 'error': f"读取文献失败: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/matrix', methods=['GET'])
def get_universe_backtest_matrix():
    """获取全市场 537 只成熟 ETF 多周期回测矩阵大宽表 (纯 MySQL 索引直出)"""
    from repositories.universe_matrix_repository import UniverseMatrixRepository
    import time
    try:
        matrix_repo = UniverseMatrixRepository()
        sector = request.args.get('sector')
        search = request.args.get('search') or request.args.get('q')
        sort_by = request.args.get('sortBy', '5y')
        sort_order = request.args.get('sortOrder', 'desc')
        only_valid_5y = request.args.get('onlyValid5y', 'false').lower() in ('1', 'true')
        config_key = request.args.get('configKey')
        
        # 默认取全量供前端自由快速分页与筛选
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('pageSize', 1000))

        res = matrix_repo.query_matrix(
            sector=sector,
            search=search,
            sort_by=sort_by,
            sort_order=sort_order,
            only_valid_5y=only_valid_5y,
            config_key=config_key,
            is_default_only=(config_key is None),
            page=page,
            page_size=page_size,
        )

        sectors = matrix_repo.aggregate_sectors(config_key=config_key, is_default_only=(config_key is None))

        payload = {
            'updated_at': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_etfs': res['total'],
            'sectors': sectors,
            'records': res['records'],
        }
        return jsonify({'success': True, 'data': payload})
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"从 MySQL 获取回测矩阵失败: {str(e)}")
        return jsonify({'success': False, 'error': f"从 MySQL 获取回测矩阵失败: {str(e)}"}), 500


@analysis_bp.route('/api/backtest/sectors-ranking', methods=['GET'])
def get_sectors_ranking():
    """获取首页 11 大赛道胜率与收益横评矩阵 (纯 MySQL 动态聚合)"""
    from repositories.universe_matrix_repository import UniverseMatrixRepository
    try:
        matrix_repo = UniverseMatrixRepository()
        config_key = request.args.get('configKey')
        sectors = matrix_repo.aggregate_sectors(config_key=config_key, is_default_only=(config_key is None))
        return jsonify({'success': True, 'data': sectors})
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"从 MySQL 获取赛道横评失败: {str(e)}")
        return jsonify({'success': False, 'error': f"从 MySQL 获取赛道横评失败: {str(e)}"}), 500

