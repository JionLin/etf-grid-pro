"""
ETF分析服务 - 业务流程协调
重构后的服务层，专注于业务流程协调，算法逻辑已抽离到算法模块
"""

import pandas as pd
from typing import Dict, List, Optional, Tuple, Any
import logging
from datetime import datetime, timedelta

from ..data.akshare_client import AkShareClient
from algorithms.atr.analyzer import ATRAnalyzer
from algorithms.atr.calculator import ATRCalculator
from algorithms.grid.arithmetic_grid import ArithmeticGridCalculator
from algorithms.grid.geometric_grid import GeometricGridCalculator
from algorithms.grid.optimizer import GridOptimizer
from .suitability_analyzer import SuitabilityAnalyzer
from .grid_calculator import CompositeGridCalculator
from .backtest_engine import GridBacktestEngine
from config.constants import ETFConstants


logger = logging.getLogger(__name__)

class ETFAnalysisService:
    """ETF分析服务主类 - 专注于业务流程协调"""
    
    def __init__(self, 
                 atr_analyzer: ATRAnalyzer = None,
                 arithmetic_calculator: ArithmeticGridCalculator = None,
                 geometric_calculator: GeometricGridCalculator = None,
                 grid_optimizer: GridOptimizer = None,
                 suitability_analyzer: SuitabilityAnalyzer = None):
        """
        初始化分析服务 - 使用依赖注入
        
        Args:
            atr_analyzer: ATR分析器实例
            arithmetic_calculator: 等差网格计算器实例
            geometric_calculator: 等比网格计算器实例
            grid_optimizer: 网格优化器实例
            suitability_analyzer: 适宜度分析器实例
        """
        self.akshare_client = AkShareClient()
        
        # 使用依赖注入或创建默认实例
        self.atr_analyzer = atr_analyzer or ATRAnalyzer(ATRCalculator())
        self.arithmetic_calculator = arithmetic_calculator or ArithmeticGridCalculator()
        self.geometric_calculator = geometric_calculator or GeometricGridCalculator()
        self.grid_optimizer = grid_optimizer or GridOptimizer()
        self.suitability_analyzer = suitability_analyzer or SuitabilityAnalyzer()
        self.composite_grid_calculator = CompositeGridCalculator()
        self.backtest_engine = GridBacktestEngine()
        
        # 热门ETF列表 (涵盖宽基指数、稳定行业与景气行业核心标的)
        self.popular_etfs = [
            {'code': '510300', 'name': '沪深300ETF (华泰柏瑞)'},
            {'code': '510500', 'name': '中证500ETF (南方)'},
            {'code': '512100', 'name': '中证1000ETF (南方)'},
            {'code': '560510', 'name': '中证A500ETF (国泰)'},
            {'code': '159915', 'name': '创业板ETF (易方达)'},
            {'code': '588000', 'name': '科创50ETF (华夏)'},
            {'code': '513130', 'name': '恒生科技ETF (华泰柏瑞)'},
            {'code': '513100', 'name': '纳指100ETF (国泰)'},
            {'code': '515220', 'name': '煤炭ETF (国泰)'},
            {'code': '512890', 'name': '红利低波ETF (华泰柏瑞)'},
            {'code': '512800', 'name': '银行ETF (华宝)'},
            {'code': '159301', 'name': '公用事业ETF (华夏)'},
            {'code': '159666', 'name': '交通运输ETF (华夏)'},
            {'code': '159995', 'name': '芯片ETF (华夏)'},
            {'code': '512480', 'name': '半导体ETF (国联安)'},
            {'code': '588200', 'name': '科创芯片ETF (嘉实)'},
            {'code': '159819', 'name': '人工智能ETF (易方达)'},
            {'code': '515070', 'name': '人工智能ETF (华夏)'},
            {'code': '515790', 'name': '光伏ETF'},
            {'code': '159755', 'name': '电池ETF'},
            {'code': '516160', 'name': '新能源ETF (南方)'},
            {'code': '512010', 'name': '医药ETF (易方达)'},
            {'code': '516080', 'name': '创新药ETF (易方达)'},
            {'code': '159770', 'name': '机器人ETF'},
            {'code': '562570', 'name': '信创ETF (华夏)'},
            {'code': '515050', 'name': '5G通信ETF (华夏)'},
            {'code': '159241', 'name': '航空航天ETF (天弘)'}
        ]
    
    def get_popular_etfs(self) -> List[Dict]:
        """获取热门ETF列表"""
        return self.popular_etfs

    def get_etf_pool(
        self,
        sector: Optional[str] = None,
        is_t0: Optional[bool] = None,
        elasticity: Optional[str] = None,
        subsector: Optional[str] = None,
        min_amount_10k: float = 0.0,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
        commodity_exempt: bool = False,
        force_refresh: bool = False
    ) -> Dict[str, Any]:
        """获取全市场做 T ETF 标的池及赛道分布统计（默认月均成交额 >= 3000 万元，ATR >= 1.5%）"""
        if not getattr(self.akshare_client, "_pool_taxonomy_refreshed", False):
            self.akshare_client.pool_repo.reclassify_persisted(
                self.akshare_client.classify_etf_item
            )
            self.akshare_client._pool_taxonomy_refreshed = True
        # 确保标的池已构建
        self.akshare_client.build_or_get_etf_pool(
            min_amount_10k=min_amount_10k,
            min_ma20_amount_10k=min_ma20_amount_10k,
            min_atr_pct=min_atr_pct,
            force_refresh=force_refresh
        )
        items = self.akshare_client.pool_repo.get_pool(
            sector=sector,
            is_t0=is_t0,
            elasticity=elasticity,
            subsector=subsector,
            min_amount_10k=min_amount_10k,
            min_ma20_amount_10k=min_ma20_amount_10k,
            min_atr_pct=min_atr_pct,
            commodity_exempt=commodity_exempt,
            limit=600
        )
        self.akshare_client.attach_quote_dates(items)

        # 补齐多周期回测大宽表沉淀的真实物理上市成熟度 (is_valid_5y, is_valid_3y, is_valid_1y)
        try:
            from repositories.universe_matrix_repository import UniverseMatrixRepository
            matrix_repo = UniverseMatrixRepository()
            validity_map = matrix_repo.get_validity_map()
            for it in items:
                v = validity_map.get(str(it.get("etf_code", "")), {})
                it["is_valid_5y"] = v.get("is_valid_5y", False)
                it["is_valid_3y"] = v.get("is_valid_3y", False)
                it["is_valid_1y"] = v.get("is_valid_1y", False)
        except Exception as e:
            logger.warning(f"补齐标的成熟度标记失败: {e}")

        self._attach_rank_scores(items)
        items.sort(key=lambda item: float(item.get("score") or 0), reverse=True)

        summary = self.akshare_client.pool_repo.get_sectors_summary(
            min_ma20_amount_10k=min_ma20_amount_10k,
            min_atr_pct=min_atr_pct
        )
        return {
            "total": summary.get("total_count", len(items)),
            "t0_total": summary.get("t0_count", 0),
            "valid_5y_total": sum(1 for it in items if it.get("is_valid_5y")),
            "valid_3y_total": sum(1 for it in items if it.get("is_valid_3y")),
            "unclassified_count": summary.get("unclassified_count", 0),
            "sectors_summary": summary.get("sectors", []),
            "subsectors_summary": self.akshare_client.pool_repo.list_subsector_summary(
                min_ma20_amount_10k=min_ma20_amount_10k,
                min_atr_pct=min_atr_pct,
            ),
            "items": items,
            "backfilling": self._pool_backfilling(len(items)),
            "storage_label": self._storage_label(),
        }

    @staticmethod
    def _storage_label() -> str:
        try:
            from repositories.db_config import storage_label

            return storage_label()
        except Exception:
            return "本地数据库"

    def _attach_rank_scores(self, items: List[Dict[str, Any]]) -> None:
        from services.data.bar_metrics import pool_rank_score

        fits: Dict[str, Dict[str, Any]] = {}
        try:
            from repositories.grid_fit_repository import GridFitRepository
            from services.analysis.grid_fit_service import PROTOCOL_VERSION

            for row in GridFitRepository().list_runs(PROTOCOL_VERSION):
                if row.get("step_mode") != "atr":
                    continue
                fits[str(row.get("etf_code"))] = row
        except Exception as exc:
            logger.warning("读取适合度年化收益失败: %s", exc)
        for item in items:
            fit = fits.get(str(item.get("etf_code")))
            cash_yield = None
            if fit and fit.get("status") == "ranked" and fit.get("cash_yield") is not None:
                cash_yield = fit.get("cash_yield")
            score, kind = pool_rank_score(item.get("atr_pct"), item.get("amount_ma20_10k"), cash_yield)
            item["score"] = score
            item["score_kind"] = kind
            if fit and fit.get("max_drawdown") is not None:
                item["max_drawdown"] = fit.get("max_drawdown")

    def _pool_backfilling(self, item_count: int) -> bool:
        try:
            from services.data.startup_sync_service import StartupSyncService, pool_is_backfilling

            return pool_is_backfilling(StartupSyncService().get_status(), item_count)
        except Exception as exc:
            logger.warning("读取日K回补状态失败: %s", exc)
            return False

    def get_etf_basic_info(self, etf_code: str) -> Dict:
        """
        获取ETF基础信息
        
        Args:
            etf_code: ETF代码
            
        Returns:
            ETF基础信息
        """
        try:
            # 获取基础信息（使用增强缓存）
            basic_info = self.akshare_client.get_etf_basic_info(etf_code)
            if not basic_info:
                raise ValueError(f"未找到ETF代码: {etf_code}")
            
            # 获取最新价格（使用增强缓存）
            price_data = self.akshare_client.get_latest_price(etf_code)
            if not price_data:
                raise ValueError(f"未获取到ETF价格数据: {etf_code}")
            
            # 获取ETF名称（使用增强缓存）
            etf_name = price_data.get('etf_name', '') or self.akshare_client.get_etf_name(etf_code)
            
            # 整合信息
            etf_info = {
                'code': etf_code,
                'name': etf_name or f'ETF {etf_code}',
                'management_company': basic_info.get('management', '未知'),
                'current_price': price_data.get('current_price', 0),
                'change_pct': price_data.get('pct_change', 0),
                'volume': price_data.get('volume', 0),
                'amount': price_data.get('amount', 0),
                'setup_date': basic_info.get('found_date', ''),
                'list_date': basic_info.get('list_date', ''),
                'fund_type': 'ETF',
                'trade_date': price_data.get('trade_date', ''),
                'trade_timestamp': price_data.get('timestamp', ''),
                'data_age_days': price_data.get('data_age_days', 0)
            }
            
            logger.info(f"获取ETF基础信息成功: {etf_code} - {etf_info['name']}")
            return etf_info
            
        except Exception as e:
            logger.error(f"获取ETF基础信息失败: {etf_code}, {str(e)}")
            raise

    def resolve_etf_name(self, etf_code: str) -> str:
        """归档和回测只取名称。先看标的池和名称缓存，不拉全市场现货。"""
        pool_repo = getattr(self.akshare_client, "pool_repo", None)
        if pool_repo is not None and hasattr(pool_repo, "find_name"):
            pooled = pool_repo.find_name(etf_code)
            if pooled:
                return pooled
        cache = getattr(self.akshare_client, "cache", None)
        if cache is not None:
            cached = cache.get_permanent_cache("etf_name", etf_code)
            if cached:
                return str(cached)
        return etf_code

    def _current_atr_ratio(self, df: pd.DataFrame) -> float:
        """窗口最后一根 K 线的 ATR。只给需要最新波动的调用方。"""
        processed = self.atr_analyzer.calculator.calculate_atr(df.copy())
        ratio = processed.iloc[-1].get("atr_ratio")
        if ratio is None or pd.isna(ratio):
            raise ValueError("无法从历史K线计算ATR比率")
        return float(ratio)

    def _anchor_atr_ratio(self, df: pd.DataFrame) -> float:
        """锚点当日已经能算出的 ATR。不用窗口末日，避免步长看见未来波动。"""
        processed = self.atr_analyzer.calculator.calculate_atr(df.copy())
        ratio = processed.iloc[0].get("atr_ratio")
        if ratio is None or pd.isna(ratio):
            valid = processed["atr_ratio"].dropna()
            if valid.empty:
                raise ValueError("无法从历史K线计算ATR比率")
            ratio = valid.iloc[0]
        return float(ratio)
    
    def get_historical_data(self, etf_code: str, days: int = 365) -> pd.DataFrame:
        """
        获取历史数据
        
        Args:
            etf_code: ETF代码
            days: 获取天数
            
        Returns:
            历史数据DataFrame
        """
        try:
            # 计算日期范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
            
            # 获取历史数据（使用增强缓存）
            df = self.akshare_client.get_etf_daily_data(etf_code, start_date, end_date, days=days)
            if df is None or len(df) == 0:
                raise ValueError(f"未获取到历史数据: {etf_code}")
            
            # 数据清洗和验证
            df = df.dropna()
            df = df.sort_values('trade_date')
            
            # 重命名列以匹配分析模块的期望格式
            if 'trade_date' in df.columns:
                df = df.rename(columns={'trade_date': 'date'})
            
            if len(df) < 30:
                logger.warning(f"历史数据不足30天: {etf_code}, 实际{len(df)}天")
            
            logger.info(f"获取历史数据成功: {etf_code}, {len(df)}条记录")
            return df
            
        except Exception as e:
            logger.error(f"获取历史数据失败: {etf_code}, {str(e)}")
            raise
    
    def analyze_etf_strategy(self, etf_code: str, total_capital: float,
                           grid_type: str, risk_preference: str,
                           adjustment_coefficient: float = 1.0,
                           analysis_days: int = 180,
                           scaling_ratio: float = 0.0,
                           step_mode: str = 'atr',
                           benchmark_price: Optional[float] = None,
                           eda_step_ratios: Optional[Dict[str, float]] = None,
                           atr_multipliers: Optional[Dict[str, float]] = None) -> Dict:
        """
        完整的ETF网格交易策略分析
        
        Args:
            etf_code: ETF代码
            total_capital: 总投资资金
            grid_type: 网格类型 ('等差' 或 '等比')
            risk_preference: 频率偏好 ('低频', '均衡', '高频')
            adjustment_coefficient: 调节系数 (默认1.0)
            analysis_days: 分析周期天数 (默认180天)
            
        Returns:
            完整的策略分析报告
        """
        try:
            logger.info(f"开始ETF策略分析: {etf_code}, 资金{total_capital}, "
                       f"{grid_type}网格, {risk_preference}, 调节系数{adjustment_coefficient}, 周期{analysis_days}天")
            
            # 1. 获取ETF基础信息（内部已取过一次最新价）
            etf_info = self.get_etf_basic_info(etf_code)
            latest_price_info = {
                "current_price": etf_info.get("current_price"),
                "timestamp": etf_info.get("trade_timestamp") or etf_info.get("trade_date") or "",
                "trade_date": etf_info.get("trade_date") or "",
            }
            if latest_price_info["current_price"] in (None, ""):
                raise ValueError(f"未获取到ETF最新价格: {etf_code}")
            
            # 2. 获取历史数据（根据指定天数，默认180天）
            df = self.get_historical_data(etf_code, days=analysis_days)
            
            # 4. 执行适宜度评估（只看网格体格，不引入估值）
            suitability_result = self.suitability_analyzer.comprehensive_evaluation(df, etf_info)
            
            # 6. 计算网格策略参数（使用算法模块）
            atr_analysis = suitability_result['atr_analysis']
            market_indicators = suitability_result['market_indicators']
            
            grid_params = self._calculate_grid_parameters(
                latest_price_info=latest_price_info,
                atr_analysis=atr_analysis,
                market_indicators=market_indicators,
                total_capital=total_capital,
                grid_type=grid_type,
                risk_preference=risk_preference,
                adjustment_coefficient=adjustment_coefficient,
                scaling_ratio=scaling_ratio,
                step_mode=step_mode,
                benchmark_price=benchmark_price,
                eda_step_ratios=eda_step_ratios,
                atr_multipliers=atr_multipliers,
            )
            
            # 5. 生成策略分析依据
            strategy_rationale = self._generate_strategy_rationale(
                suitability_result, grid_params, risk_preference, step_mode=step_mode
            )
            
            # 6. 生成调整建议
            adjustment_suggestions = self._generate_adjustment_suggestions(
                suitability_result, grid_params
            )
            
            # 7. 整合完整报告
            complete_report = {
                'etf_info': etf_info,
                'data_quality': suitability_result['data_quality'],
                'suitability_evaluation': suitability_result,
                'grid_strategy': grid_params,
                'strategy_rationale': strategy_rationale,
                'adjustment_suggestions': adjustment_suggestions,
                'analysis_timestamp': datetime.now().isoformat(),
                'input_parameters': {
                    'etf_code': etf_code,
                    'etfCode': etf_code,
                    'total_capital': total_capital,
                    'totalCapital': total_capital,
                    'grid_type': grid_type,
                    'gridType': grid_type,
                    'risk_preference': risk_preference,
                    'riskPreference': risk_preference,
                    'adjustment_coefficient': adjustment_coefficient,
                    'adjustmentCoefficient': adjustment_coefficient,
                    'analysis_days': analysis_days,
                    'analysisDays': analysis_days,
                    'scaling_ratio': scaling_ratio,
                    'scalingRatio': scaling_ratio,
                    'step_mode': step_mode,
                    'stepMode': step_mode,
                    'eda_step_ratios': eda_step_ratios,
                    'edaStepRatios': eda_step_ratios,
                    'atr_multipliers': atr_multipliers,
                    'atrMultipliers': atr_multipliers,
                    'benchmark_price': benchmark_price,
                    'benchmarkPrice': benchmark_price,
                }
            }
            
            logger.info(f"ETF策略分析完成: {etf_code}, 适宜度评分{suitability_result['total_score']}")
            return complete_report
            
        except Exception as e:
            logger.error(f"ETF策略分析失败: {etf_code}, {str(e)}")
            raise
    
    def _generate_strategy_rationale(self, suitability_result: Dict, 
                                   grid_params: Dict, risk_preference: str,
                                   step_mode: str = 'atr') -> Dict:
        """
        生成策略分析依据
        
        Args:
            suitability_result: 适宜度评估结果
            grid_params: 网格参数
            risk_preference: 频率偏好
            step_mode: 步长生成模式 ('atr' | 'fixed_eda')
            
        Returns:
            策略分析依据
        """
        try:
            atr_analysis = suitability_result['atr_analysis']
            market_indicators = suitability_result['market_indicators']
            
            # ATR算法优势说明
            atr_advantages = [
                "考虑跳空因素，比传统日振幅更准确",
                "动态适应市场波动特征，避免静态统计方法的滞后性",
                "标准化处理，便于不同标的间的比较",
                "能够捕捉市场波动模式的变化"
            ]
            
            if step_mode == 'fixed_eda':
                # E大原版/自定义立体三轨规划逻辑
                eda_step_pct = grid_params.get('grid_config', {}).get('step_ratio', 0.05) * 100
                parameter_logic = {
                    'price_range': f"基于E大立体三轨全域防守规划，上下覆盖极限防守区间 [{grid_params['price_range']['lower']:.3f} ~ {grid_params['price_range']['upper']:.3f}]",
                    'grid_count': f"复合多轨部署{grid_params['grid_config']['count']}个档位 (小网高频、中网巡航、大网防守)",
                    'fund_allocation': f"底仓比例{grid_params['fund_allocation']['base_position_ratio']:.1%}，现金采用多轨倒金字塔递增加码",
                    'grid_type': f"{grid_params['grid_config']['type']}网格适配立体三轨步长"
                }
                profit_basis = {
                    'parameter_optimization': f"基于E大原版价值网格体系（小网{eda_step_pct:.1f}%基础步长，中大网倍数递增防守）",
                    'trading_frequency': "小网负责日常震荡频繁收割，中大网负责深度回踩接力防守",
                    'risk_control': "大网步长深潜防守，底仓锁定防踏空，跌满熔断防爆仓",
                    'fund_allocation': "50%底仓锁定 + 50%多轨资金梯次配置"
                }
            else:
                # ATR算法选择逻辑
                parameter_logic = {
                    'price_range': f"基于ATR比率{atr_analysis['current_atr_pct']:.2f}%和{risk_preference}频率偏好计算",
                    'grid_count': f"基于ATR智能步长算法设定{grid_params['grid_config']['count']}个网格",
                    'fund_allocation': f"底仓比例{grid_params['fund_allocation']['base_position_ratio']:.1%}，"
                                     f"基于网格需求计算，确保买卖仓位充足",
                    'grid_type': f"{grid_params['grid_config']['type']}网格更适合当前市场特征"
                }
                profit_basis = {
                    'parameter_optimization': "基于ATR算法和历史波动率分析",
                    'trading_frequency': "根据网格密度和历史波动特征预估",
                    'risk_control': "基于ATR波动率和市场趋势指标设定",
                    'fund_allocation': "智能资金分配确保风险可控"
                }
            
            return {
                'atr_advantages': atr_advantages,
                'parameter_logic': parameter_logic,
                'profit_basis': profit_basis,
                'market_environment': {
                    'volatility': f"年化波动率{market_indicators['volatility']:.1%}",
                    'trend_characteristic': suitability_result['evaluations']['market_characteristics']['market_type'],
                    'liquidity': suitability_result['evaluations']['liquidity']['level']
                }
            }
            
        except Exception as e:
            logger.error(f"生成策略分析依据失败: {str(e)}")
            return {}
    
    def _generate_adjustment_suggestions(self, suitability_result: Dict,
                                       grid_params: Dict) -> Dict:
        """
        生成调整建议
        
        Args:
            suitability_result: 适宜度评估结果
            grid_params: 网格参数
            
        Returns:
            调整建议
        """
        try:
            suggestions = {
                'market_environment_changes': [],
                'parameter_optimization': [],
                'risk_control': [],
                'profit_enhancement': []
            }
            
            # 市场环境变化应对。ADX 为空时跳过，避免把缺失值当成震荡市去加密网格。
            adx_value = suitability_result['market_indicators'].get('adx_value')
            if adx_value is None:
                logger.debug("ADX不可用，跳过趋势建议")
            elif adx_value > 25:
                suggestions['market_environment_changes'].append(
                    "当前处于强趋势环境，建议增加底仓比例，减少网格交易频率"
                )
            elif adx_value < 15:
                suggestions['market_environment_changes'].append(
                    "震荡特征明显，可适当增加网格密度，提高交易频率"
                )
            
            # 参数优化建议
            volatility = suitability_result['market_indicators']['volatility']
            if volatility > 0.4:
                suggestions['parameter_optimization'].append(
                    "波动率较高，建议扩大网格间距，降低交易频率"
                )
            elif volatility < 0.15:
                suggestions['parameter_optimization'].append(
                    "波动率较低，可适当缩小网格间距，增加交易机会"
                )
            
            # 风险控制建议
            if volatility > 0.4:
                suggestions['risk_control'].append(
                    "波动率较高，建议设置止损线或减少网格密度"
                )
            
            # 收益增强建议
            grid_count = grid_params['grid_config']['count']
            if grid_count < 20:
                suggestions['profit_enhancement'].append(
                    "网格数量较少，可考虑增加网格密度提高交易机会"
                )
            
            # 资金效率建议
            grid_fund_utilization_rate = grid_params['fund_allocation']['grid_fund_utilization_rate']
            if grid_fund_utilization_rate < 0.8:
                suggestions['profit_enhancement'].append(
                    f"网格资金利用率{grid_fund_utilization_rate:.1%}偏低，可考虑调整网格配置"
                )
            
            return suggestions
            
        except Exception as e:
            logger.error(f"生成调整建议失败: {str(e)}")
            return {}
    
    def _calculate_grid_parameters(self, latest_price_info: Dict,
                                 atr_analysis: Dict, market_indicators: Dict,
                                 total_capital: float, grid_type: str,
                                 risk_preference: str, adjustment_coefficient: float = 1.0,
                                 scaling_ratio: float = 0.0,
                                 step_mode: str = 'atr',
                                 benchmark_price: Optional[float] = None,
                                 eda_step_ratios: Optional[Dict[str, float]] = None,
                                 atr_multipliers: Optional[Dict[str, float]] = None) -> Dict:
        """
        计算网格策略参数（使用算法模块）
        
        Args:
            latest_price_info: 最新价格信息（包含交易日期）
            atr_analysis: ATR分析结果
            market_indicators: 市场指标
            total_capital: 总投资资金
            grid_type: 网格类型
            risk_preference: 频率偏好
            benchmark_price: 用户自定义基准价格 (可选，指定时以此价格为中心锚点铺设网格)
            
        Returns:
            网格策略参数
        """
        try:
            atr_ratio = atr_analysis['current_atr_ratio']

            current_price = float(latest_price_info['current_price'])
            # 若用户指定了自定义基准价格且大于0，则使用自定义基准价格作为中心锚点 P0
            anchor_price = float(benchmark_price) if (benchmark_price is not None and float(benchmark_price) > 0) else current_price
            
            # 1. 先行计算大中小三层复合网格阶梯 (以 anchor_price 为中心铺设，尊重 step_mode 与自定义比例)
            composite_steps = self.grid_optimizer.calculate_composite_steps(
                anchor_price, atr_ratio, adjustment_coefficient, step_mode=step_mode,
                eda_step_ratios=eda_step_ratios, atr_multipliers=atr_multipliers,
                risk_preference=risk_preference,
            )
            composite_grid = self.composite_grid_calculator.calculate_composite_grid(
                total_capital, anchor_price, composite_steps, base_position_ratio=0.5,
                scaling_ratio=scaling_ratio
            )

            # 2. 收集复合多轨所有买入档位与卖出档位
            all_buy_levels = []
            all_sell_levels = []
            for rail_data in composite_grid.get('rails', {}).values():
                all_buy_levels.extend(rail_data.get('buy_levels', []))
                all_sell_levels.extend(rail_data.get('sell_levels', []))

            # 3. 价格区间完全基于真实复合阶梯极值统一派生 (方案一)
            if all_buy_levels:
                derived_lower = min(item['price'] for item in all_buy_levels)
            else:
                derived_lower = round(anchor_price * 0.85, 3)

            if all_sell_levels:
                derived_upper = max(item['price'] for item in all_sell_levels)
            else:
                derived_upper = round(anchor_price * 1.15, 3)

            derived_ratio = (derived_upper - derived_lower) / anchor_price

            # 4. 看板核心步长与小网 (高频做T) 实际步长动态对齐
            small_step = composite_steps.get('small', {})
            active_step_ratio = float(small_step.get('step_ratio') or (0.05 if step_mode == 'fixed_eda' else 0.02))
            active_step_size = float(small_step.get('step_size') or round(anchor_price * active_step_ratio, 3))
            total_levels_count = len(all_buy_levels) + len(all_sell_levels)

            # 5. 从 composite_grid 真实底层对象中提取量化资金账本
            base_info = composite_grid.get('base_position', {})
            base_actual = float(base_info.get('actual_capital', round(total_capital * 0.5, 2)))
            base_ratio = float(base_info.get('ratio', 0.5))
            liquid_capital = float(composite_grid.get('liquid_capital', round(total_capital * 0.5, 2)))

            total_buy_grid_fund = sum(item['amount'] for item in all_buy_levels)
            grid_fund_utilization_rate = round(total_buy_grid_fund / liquid_capital, 4) if liquid_capital > 0 else 1.0
            reserve_amount = max(0.0, round(total_capital - base_actual - total_buy_grid_fund, 2))
            reserve_ratio = round(reserve_amount / total_capital, 4) if total_capital > 0 else 0.0

            # 提取小网第 1 档的真实交易股数与单笔预期收益
            small_buy_levels = composite_grid.get('rails', {}).get('small', {}).get('buy_levels', [])
            single_trade_quantity = int(small_buy_levels[0]['shares']) if small_buy_levels else 100
            expected_profit_per_trade = float(small_buy_levels[0]['est_profit']) if small_buy_levels else 0.0

            fund_allocation = {
                'total_capital': total_capital,
                'base_position_ratio': base_ratio,
                'base_position_amount': base_actual,
                'grid_trading_amount': liquid_capital,
                'grid_funds_amount': liquid_capital,
                'grid_funds_ratio': round(liquid_capital / total_capital, 4) if total_capital > 0 else 0.5,
                'buy_funds_amount': round(total_buy_grid_fund, 2),
                'total_buy_grid_fund': round(total_buy_grid_fund, 2),
                'sell_funds_amount': base_actual,
                'reserve_amount': reserve_amount,
                'reserve_funds_amount': reserve_amount,
                'reserve_funds_ratio': reserve_ratio,
                'grid_fund_utilization_rate': grid_fund_utilization_rate,
                'single_trade_quantity': single_trade_quantity,
                'expected_profit_per_trade': round(expected_profit_per_trade, 2),
                'single_grid_amount': round(total_buy_grid_fund / max(len(all_buy_levels), 1), 2),
                'safety_buffer_ratio': reserve_ratio,
                'allocation_mode': '复合多轨阶梯资金分配' if step_mode == 'fixed_eda' else 'ATR智能资金分配'
            }

            # 6. 单层价格线兼顾兜底兼容
            price_levels = sorted([item['price'] for item in all_buy_levels + all_sell_levels] + [anchor_price])

            # 7. ATR评分
            atr_score, atr_description = self.atr_analyzer.get_atr_score(atr_ratio)
            
            is_eda = (step_mode == 'fixed_eda')
            calculation_method = 'E大原版三轨规划' if is_eda else 'ATR智能算法'
            if is_eda:
                calculation_logic = {
                    'step1': f'步长模式: E大原版/自定义立体三轨 (小网{active_step_ratio:.1%})',
                    'step2': f'小网核心做T步长: {active_step_size:.3f} ({active_step_ratio:.1%})',
                    'step3': f'复合三轨档位总数: {total_levels_count}个 (买{len(all_buy_levels)}+卖{len(all_sell_levels)})',
                    'step4': f'立体防守价格区间: [{derived_lower:.3f}, {derived_upper:.3f}]',
                    'step5': f'区间跨度覆盖率: {derived_ratio:.1%}'
                }
            else:
                calculation_logic = {
                    'step1': f'ATR比率: {atr_ratio:.1%}',
                    'step2': f'基于ATR和频率偏好计算小网步长: {active_step_size:.3f} ({active_step_ratio:.1%})',
                    'step3': f'复合三轨档位总数: {total_levels_count}个 (买{len(all_buy_levels)}+卖{len(all_sell_levels)})',
                    'step4': f'自适应动态价格区间: [{derived_lower:.3f}, {derived_upper:.3f}]',
                    'step5': f'区间跨度覆盖率: {derived_ratio:.1%}'
                }

            result = {
                'current_price': current_price,
                'benchmark_price': anchor_price,
                'is_custom_benchmark': round(anchor_price, 4) != round(current_price, 4),
                'price_date': latest_price_info.get('timestamp') or latest_price_info.get('trade_date') or '',
                'step_mode': step_mode,
                'price_range': {
                    'lower': round(derived_lower, 3),
                    'upper': round(derived_upper, 3),
                    'ratio': round(derived_ratio, 4)
                },
                'grid_config': {
                    'count': total_levels_count,
                    'type': grid_type,
                    'step_size': round(active_step_size, 3),
                    'step_ratio': round(active_step_ratio, 4)
                },
                'price_levels': [round(p, 3) for p in price_levels],
                'fund_allocation': fund_allocation,
                'composite_grid': composite_grid,
                'risk_preference': risk_preference,
                'atr_based': True,
                'atr_score': atr_score,
                'atr_description': atr_description,
                'calculation_method': calculation_method,
                'calculation_logic': calculation_logic
            }
            
            logger.info(f"{calculation_method}网格策略计算完成: 核心步长{active_step_size:.3f}({active_step_ratio:.1%}), "
                       f"{total_levels_count}个档位, 真实区间[{derived_lower:.3f}, {derived_upper:.3f}]")
            
            return result
            
        except Exception as e:
            logger.error(f"网格策略参数计算失败: {str(e)}")
            raise

    def run_strategy_backtest(
        self,
        etf_code: str,
        total_capital: float,
        backtest_days: int = 180,
        adjustment_coefficient: float = 1.0,
        scaling_ratio: float = 0.0,
        reinvest_mode: str = 'cash',
        step_mode: str = 'atr',
        eda_step_ratios: Optional[Dict[str, float]] = None,
        custom_base_price: Optional[float] = None,
        atr_multipliers: Optional[Dict[str, float]] = None,
        atr_ratio: Optional[float] = None,
        etf_name: Optional[str] = None,
        risk_preference: str = '均衡',
    ) -> Dict[str, Any]:
        """
        运行策略历史回测

        Args:
            etf_code: ETF代码
            total_capital: 资金量
            backtest_days: 回测天数 (默认 180 天)
            adjustment_coefficient: 调节系数
            scaling_ratio: 逐格加码比例 (默认 0.0)
            reinvest_mode: 做T收益模式 ('cash' 全额留现金, 'pool_shares' 利润池滚存留股)
            step_mode: 步长模式 ('atr' | 'fixed_eda')
            eda_step_ratios: E大自定义各轨步长
            custom_base_price: 自定义历史回测基准锚点价格 (可选，默认使用首日真实开盘价)

        Returns:
            回测报告
        """
        try:
            safe_days = max(30, min(1825, int(backtest_days)))
            df = self.get_historical_data(etf_code, days=safe_days)
            if df is None or df.empty:
                raise ValueError(f"无法获取 ETF {etf_code} 历史行情数据")

            actual_trading_days = len(df)
            date_col = 'date' if 'date' in df.columns else 'trade_date'
            first_date = pd.to_datetime(df.iloc[0][date_col])
            last_date = pd.to_datetime(df.iloc[-1][date_col])
            actual_calendar_days = (last_date - first_date).days
            start_date_str = first_date.strftime('%Y-%m-%d')
            end_date_str = last_date.strftime('%Y-%m-%d')

            # 次新标的自适应判定：标的上市跨度明显少于请求周期（首尾日历跨度不足 70% 且交易日数不足 50%）
            is_partial_history = (actual_calendar_days < int(safe_days * 0.70)) and (actual_trading_days < int(safe_days * 0.50))

            # 确定回测网格铺设基准价格 (消除未来函数偏差，优先自定义回测基准，默认首日开盘价)
            if custom_base_price is not None and float(custom_base_price) > 0:
                backtest_base_price = float(custom_base_price)
                anchor_mode = "custom"
            else:
                open_val = df.iloc[0].get('open')
                if pd.notna(open_val) and float(open_val) > 0:
                    backtest_base_price = float(open_val)
                else:
                    backtest_base_price = float(df.iloc[0]['close'])
                anchor_mode = "inception_open"

            current_price = float(df.iloc[-1]['close'])
            resolved_name = etf_name or self.resolve_etf_name(etf_code)
            if atr_ratio is None:
                atr_ratio = self._anchor_atr_ratio(df)

            # 以当年真实基准价格 backtest_base_price 展开回测网格阶梯
            composite_steps = self.grid_optimizer.calculate_composite_steps(
                backtest_base_price, atr_ratio, adjustment_coefficient, step_mode=step_mode,
                eda_step_ratios=eda_step_ratios, atr_multipliers=atr_multipliers,
                risk_preference=risk_preference,
            )
            composite_grid = self.composite_grid_calculator.calculate_composite_grid(
                total_capital, backtest_base_price, composite_steps, base_position_ratio=0.5,
                scaling_ratio=scaling_ratio
            )

            # 自动识别交易制度
            trade_mode = "t0" if ETFConstants.is_t0_etf(etf_code, resolved_name) else "t1"

            backtest_res = self.backtest_engine.run_backtest(
                daily_df=df,
                total_capital=total_capital,
                composite_grid=composite_grid,
                reinvest_mode=reinvest_mode,
                trade_mode=trade_mode,
            )

            history_meta = {
                'requested_days': safe_days,
                'actual_trading_days': actual_trading_days,
                'actual_calendar_days': actual_calendar_days,
                'start_date': start_date_str,
                'end_date': end_date_str,
                'is_partial_history': is_partial_history,
                'partial_reason': f"标的上市仅 {actual_calendar_days} 天（共 {actual_trading_days} 交易日），已自适应回测全量可用历史" if is_partial_history else None,
                'backtest_base_price': round(backtest_base_price, 3),
                'anchor_mode': anchor_mode,
                'latest_market_price': round(current_price, 3),
                'etf_name': resolved_name,
                'atr_ratio': atr_ratio,
            }
            backtest_res['history_meta'] = history_meta
            if 'summary' in backtest_res and isinstance(backtest_res['summary'], dict):
                backtest_res['summary']['history_meta'] = history_meta

            return backtest_res
        except Exception as e:
            logger.error(f"策略历史回测执行失败: {str(e)}")
            raise
