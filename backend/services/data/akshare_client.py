import akshare as ak
import pandas as pd
import logging
import threading
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from .bar_metrics import INSUFFICIENT_DATA_LABEL, measure_local_metrics
from .t0_rules import is_t0_instrument
from .cache_service import EnhancedCache
try:
    from repositories.market_data_repository import MarketDataRepository
    from repositories.etf_pool_repository import ETFPoolRepository, UNCLASSIFIED_SECTOR
except ImportError:
    from backend.repositories.market_data_repository import MarketDataRepository
    from backend.repositories.etf_pool_repository import ETFPoolRepository, UNCLASSIFIED_SECTOR

logger = logging.getLogger(__name__)

SPOT_QUOTE_TTL_SECONDS = 45


class AkShareClient:
    """AkShare数据客户端 - 与TushareClient接口完全兼容"""
    
    def __init__(self, cache_dir: str = "../cache/akshare"):
        """初始化AkShare客户端"""
        # 初始化缓存管理器（保持与TushareClient相同的逻辑）
        self.cache = EnhancedCache(cache_dir)
        self.market_repo = MarketDataRepository()
        self.pool_repo = ETFPoolRepository()
        
        # A股交易时间配置
        self.market_open_time = "09:30"
        self.market_close_time = "15:00"
        self._spot_lock = threading.Lock()
        self._spot_frame = None
        self._spot_fetched_at = 0.0
        self._quote_cache: Dict[str, tuple] = {}
        
        logger.info("AkShare客户端初始化成功（集成 SQLite 时序行情湖版本）")

    def _fresh_quote(self, etf_code: str) -> Optional[Dict]:
        """盘中短缓存。收盘后的日缓存仍走原有交易日缓存。"""
        now = time.monotonic()
        with self._spot_lock:
            cached = self._quote_cache.get(etf_code)
            if not cached:
                return None
            fetched_at, payload = cached
            if now - fetched_at >= SPOT_QUOTE_TTL_SECONDS:
                return None
            return payload

    def _remember_quote(self, etf_code: str, payload: Dict) -> None:
        with self._spot_lock:
            self._quote_cache[etf_code] = (time.monotonic(), payload)

    def _load_spot_frame(self) -> pd.DataFrame:
        """全市场现货表 45 秒内只拉一次，单代码查询共用这一份。"""
        now = time.monotonic()
        with self._spot_lock:
            if self._spot_frame is not None and now - self._spot_fetched_at < SPOT_QUOTE_TTL_SECONDS:
                return self._spot_frame
        frame = ak.fund_etf_spot_em()
        with self._spot_lock:
            self._spot_frame = frame
            self._spot_fetched_at = time.monotonic()
        return frame
    
    def _fetch_raw_kline_network(self, etf_code: str, start_date: str, end_date: str, days: int = 180) -> Optional[pd.DataFrame]:
        """向网络接口请求原始日 K 线（优先 AkShare，网络受阻时走备用分段源）"""
        clean_code = etf_code.split(".")[0]
        s_date = start_date.replace("-", "")
        e_date = end_date.replace("-", "")
        try:
            df = ak.fund_etf_hist_em(
                symbol=clean_code,
                period="daily",
                start_date=s_date,
                end_date=e_date,
                adjust="qfq"
            )
            if df is not None and not df.empty:
                return self._convert_akshare_daily_to_tushare_format(df)
        except Exception as e:
            logger.warning(f"AkShare 接口网络异常，切换备用分段源 ({clean_code}): {e}")

        return self._get_fallback_kline(clean_code, days=days, start_date=start_date, end_date=end_date)

    def _sync_and_fill_kline_lake(self, etf_code: str, start_date: str, end_date: str, days: int = 180) -> Optional[pd.DataFrame]:
        """
        本地日 K 时序数据湖同步与增量自愈管理
        1. 检查最新端缺口 (Incremental Forward Fill)
        2. 检查历史端缺口 (Backfill Backward)
        3. 从本地 SQLite 直出切片
        """
        clean_code = etf_code.split(".")[0]
        norm_start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}" if len(start_date) == 8 else start_date
        norm_end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}" if len(end_date) == 8 else end_date
        est_target_days = int(days * 242 / 365) if days > 30 else days

        local_range = self.market_repo.get_date_range(clean_code)
        local_min = local_range["min_date"]
        local_max = local_range["max_date"]
        local_count = local_range["total_count"]

        # 场景 A: 本地完全无数据 -> 全量拉取
        if local_count == 0 or not local_max:
            logger.info(f"→ 本地日 K 时序库无 {clean_code} 历史，触发初次拉取入库")
            df = self._fetch_raw_kline_network(clean_code, start_date, end_date, days=days)
            if df is not None and not df.empty:
                self.market_repo.save_bars(clean_code, df)
            return self.market_repo.get_bars(clean_code, start_date=norm_start, end_date=norm_end)

        # 场景 B: 最新端缺口比对 (local_max < norm_end)
        gap_days = (datetime.strptime(norm_end, "%Y-%m-%d") - datetime.strptime(local_max, "%Y-%m-%d")).days
        is_weekend = datetime.strptime(norm_end, "%Y-%m-%d").weekday() >= 5
        if local_max < norm_end and not (is_weekend and gap_days <= 3):
            try:
                next_day = (datetime.strptime(local_max, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y%m%d")
                target_end = end_date.replace("-", "")
                if next_day <= target_end:
                    inc_days = (datetime.strptime(norm_end, "%Y-%m-%d") - datetime.strptime(local_max, "%Y-%m-%d")).days
                    logger.info(f"→ 检测到最新端缺口: {clean_code} 本地最新 {local_max} < 目标 {norm_end}，定向增量补齐 ({next_day}~{target_end})")
                    inc_df = self._fetch_raw_kline_network(clean_code, next_day, target_end, days=max(10, inc_days))
                    if inc_df is not None and not inc_df.empty:
                        self.market_repo.save_bars(clean_code, inc_df)
                        logger.info(f"✓ 成功增量补齐 {len(inc_df)} 条最新日 K 线至本地数据库")
            except Exception as e:
                logger.warning(f"增量补齐最新日 K 线失败 ({clean_code}): {e}")

        # 场景 C: 历史端缺口比对 (请求天数超出本地已有历史记录跨度)
        local_range_now = self.market_repo.get_date_range(clean_code)
        curr_count = local_range_now["total_count"]
        curr_min = local_range_now["min_date"]
        if est_target_days > curr_count and curr_min and curr_min > norm_start:
            logger.info(f"→ 检测到历史端跨度缺口: 需要 {est_target_days} 交易日，本地仅 {curr_count} 交易日，向前回溯补齐")
            hist_df = self._get_fallback_kline(
                clean_code, days=days, start_date=start_date, end_date=end_date
            )
            if hist_df is not None and not hist_df.empty:
                self.market_repo.save_bars(clean_code, hist_df)

        # 从本地 SQLite 毫秒级直出最终切片
        res_df = self.market_repo.get_bars(clean_code, start_date=norm_start, end_date=norm_end)
        return res_df

    def get_etf_daily_data(self, etf_code: str, start_date: str, end_date: str, days: int = 180) -> Optional[pd.DataFrame]:
        """
        获取ETF日线数据（优先通过本地 SQLite 时序库毫秒级直出，并自动执行双向增量补齐）
        
        Args:
            etf_code: ETF代码（不含市场后缀）
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式)
            
        Returns:
            DataFrame: ETF日线数据
        """
        # 0. 检查是否需要调整结束日期（如果包含当天且未收盘）
        adjusted_end_date = self._adjust_end_date_if_needed(end_date)
        if adjusted_end_date != end_date:
            logger.info(f"→ 调整结束日期: {end_date} -> {adjusted_end_date} (当天未收盘)")
            end_date = adjusted_end_date
        
        try:
            # 1. 优先通过本地 SQLite 时序数据湖同步并提取
            lake_df = self._sync_and_fill_kline_lake(etf_code, start_date, end_date, days=days)
            if lake_df is not None and not lake_df.empty:
                return lake_df
        except Exception as e:
            logger.warning(f"时序库处理异常，回退传统链路 ({etf_code}): {e}")

        # 2. 兜底回退：备用分段源
        fallback_df = self._get_fallback_kline(etf_code, days=days, start_date=start_date, end_date=end_date)
        if fallback_df is not None and not fallback_df.empty:
            try:
                self.market_repo.save_bars(etf_code, fallback_df)
            except Exception:
                pass
            return fallback_df

        return None
    
    def get_etf_basic_info(self, etf_code: str) -> Optional[Dict]:
        """
        获取ETF基本信息（永久缓存）
        
        Args:
            etf_code: ETF代码（不含市场后缀）
            
        Returns:
            Dict: ETF基本信息
        """
        # 1. 先检查永久缓存
        cached_data = self.cache.get_permanent_cache("etf_basic", etf_code)
        if cached_data:
            logger.info(f"✓ 从永久缓存获取ETF {etf_code} 基本信息")
            return cached_data
        
        # 2. 缓存未命中，调用接口
        logger.info(f"→ 永久缓存未命中，请求AkShare接口获取ETF {etf_code} 基本信息")
        
        try:
            # 使用AkShare获取ETF详细信息
            df = ak.fund_overview_em(symbol=etf_code)
            
            if df.empty:
                logger.warning(f"✗ 未找到ETF {etf_code} 的基本信息")
                return None
            
            # 提取基本信息并转换为Tushare格式
            row = df.iloc[0]
            basic_info = {
                'ts_code': f"{etf_code}.{self._get_market_suffix(etf_code)}",
                'name': row['基金简称'],
                'management': row.get('基金管理人', '未知')
            }
            
            # 3. 成功获取数据，保存到永久缓存
            self.cache.set_permanent_cache("etf_basic", etf_code, basic_info)
            logger.info(f"✓ ETF {etf_code} 基本信息获取成功并已永久缓存")
            
            return basic_info
            
        except Exception as e:
            logger.error(f"✗ 请求AkShare接口失败，ETF {etf_code} 基本信息获取失败: {str(e)}")
            fallback = self._get_fallback_quote(etf_code)
            if fallback:
                basic_info = {
                    'ts_code': f"{etf_code}.{self._get_market_suffix(etf_code)}",
                    'name': fallback['name'],
                    'management': '公募基金'
                }
                self.cache.set_permanent_cache("etf_basic", etf_code, basic_info)
                return basic_info
            return None
    
    def get_latest_price(self, etf_code: str) -> Optional[Dict]:
        """
        获取ETF最新价格（智能交易日缓存）
        
        Args:
            etf_code: ETF代码（不含市场后缀）
            
        Returns:
            Dict: 最新价格信息
        """
        fresh_quote = self._fresh_quote(etf_code)
        if fresh_quote:
            logger.info(f"✓ 从短缓存获取ETF {etf_code} 最新价格")
            return fresh_quote

        # 1. 获取最近收盘的交易日
        latest_trading_date = self.get_latest_trading_date()
        
        # 2. 仅在已收盘时读取交易日缓存。盘中缓存是上一笔快照，不能当成最新价。
        cached_data = None
        if self._day_cache_is_closed(latest_trading_date):
            cached_data = self.cache.get_daily_cache(latest_trading_date, "price", etf_code)
        if cached_data:
            logger.info(f"✓ 从交易日缓存获取ETF {etf_code} 最新价格 (交易日: {latest_trading_date})")
            self._remember_quote(etf_code, cached_data)
            return cached_data
        
        # 3. 缓存未命中，调用接口
        logger.info(f"→ 交易日缓存未命中，请求AkShare接口获取ETF {etf_code} 最新价格")
        
        try:
            df = self._load_spot_frame()
            
            # 查找指定ETF
            etf_data = df[df['代码'] == etf_code]
            if etf_data.empty:
                logger.warning(f"✗ 未找到ETF {etf_code} 的实时数据")
                return None
            
            # 提取价格信息
            row = etf_data.iloc[0]
            
            # 安全转换数值
            def safe_float(value, default=0.0):
                try:
                    if pd.isna(value) or value == '-' or value == '':
                        return default
                    return float(str(value).replace('%', '').replace(',', ''))
                except:
                    return default
            
            def safe_int(value, default=0):
                try:
                    if pd.isna(value) or value == '-' or value == '':
                        return default
                    return int(float(str(value).replace(',', '')))
                except:
                    return default
            
            def safe_timestamp(value, default=0):
                """专门处理时间戳字段，处理Timestamp对象和数值时间戳"""
                try:
                    if pd.isna(value) or value == '-' or value == '':
                        return default
                    
                    # 检查是否是pandas Timestamp对象
                    if hasattr(value, 'timestamp'):
                        # 如果是Timestamp对象，转换为毫秒级时间戳
                        return int(value.timestamp() * 1000)
                    else:
                        # 如果是数值，直接转换为整数
                        return int(str(value).replace(',', ''))
                except:
                    return default
            
            def safe_date_str(value, default=""):
                """将Timestamp对象转换为YYYYMMDD格式字符串"""
                try:
                    if pd.isna(value) or value == '-' or value == '':
                        return default
                    
                    # 检查是否是pandas Timestamp对象
                    if hasattr(value, 'strftime'):
                        return value.strftime('%Y%m%d')
                    else:
                        # 如果是字符串或数值，尝试解析
                        from datetime import datetime
                        if isinstance(value, (int, float)) and value > 0:
                            # 如果是数值时间戳（毫秒级）
                            dt = datetime.fromtimestamp(value / 1000)
                            return dt.strftime('%Y%m%d')
                        else:
                            # 尝试解析字符串
                            return str(value).replace('-', '')[:8]
                except:
                    return default
            
            # 根据接口返回的"数据日期"字段确定实际交易日
            data_date_str = safe_date_str(row['数据日期'])
            if data_date_str and len(data_date_str) == 8:
                actual_trading_date = data_date_str
                logger.info(f"→ 使用接口数据日期作为交易日: {actual_trading_date}")
            else:
                # 如果数据日期无效，使用预计算的交易日
                actual_trading_date = latest_trading_date
                logger.warning(f"⚠️ 接口数据日期无效，使用预计算交易日: {actual_trading_date}")
            
            # 获取更新时间戳
            update_timestamp = safe_timestamp(row['更新时间'])
            data_timestamp = safe_timestamp(row['数据日期'])
            
            # 根据示例数据修正字段名和添加缺失字段
            price_info = {
                'current_price': safe_float(row['最新价']),
                'pre_close': safe_float(row['昨收']),
                'pct_change': safe_float(row['涨跌幅']),
                'volume': safe_int(row['成交量']),
                'amount': safe_float(row['成交额']),
                'open_price': safe_float(row['开盘价']),
                'high_price': safe_float(row['最高价']),
                'low_price': safe_float(row['最低价']),
                'change_amount': safe_float(row['涨跌额']),
                'amplitude': safe_float(row['振幅']),
                'turnover_rate': safe_float(row['换手率']),
                'volume_ratio': safe_float(row['量比']),
                'iopv': safe_float(row['IOPV实时估值']),
                'discount_rate': safe_float(row['基金折价率']),
                'trade_date': actual_trading_date,  # 使用接口返回的数据日期
                'data_age_days': 0,  # 实时数据
                'etf_name': str(row['名称']) if not pd.isna(row['名称']) else '',
                'etf_code': str(etf_code),
                'timestamp': update_timestamp,  # 使用接口返回的更新时间戳
                'data_timestamp': data_timestamp  # 保存原始数据日期时间戳
            }
            
            # 4. 检查是否需要缓存（如果是当日数据且还未收盘，则不缓存）
            current_date = datetime.now().strftime('%Y%m%d')
            if actual_trading_date == current_date and not self._is_market_closed(datetime.now()):
                logger.info(f"→ 当日数据且未收盘，跳过缓存 (交易日: {actual_trading_date})")
            else:
                self.cache.set_daily_cache(actual_trading_date, "price", etf_code, price_info)
            self._remember_quote(etf_code, price_info)
            logger.info(f"✓ ETF {etf_code} 最新价格获取成功 (交易日: {actual_trading_date})")
            
            return price_info
            
        except Exception as e:
            logger.error(f"✗ 请求AkShare接口失败，ETF {etf_code} 最新价格获取失败: {str(e)}")
            fallback = self._get_fallback_quote(etf_code)
            if fallback:
                if self._day_cache_is_closed(latest_trading_date):
                    self.cache.set_daily_cache(latest_trading_date, "price", etf_code, fallback)
                else:
                    logger.info("备用行情尚未收盘，不写入交易日缓存: %s", etf_code)
                self._remember_quote(etf_code, fallback)
                logger.info(f"✓ 通过备用行情源获取ETF {etf_code} 最新价格成功")
                return fallback
            return None

    def _day_cache_is_closed(self, trading_date: str, now: Optional[datetime] = None) -> bool:
        """当天未到 15:00 时，交易日缓存既不能读也不能当收盘价写入。"""
        current = now or datetime.now()
        if str(trading_date) == current.strftime("%Y%m%d") and not self._is_market_closed(current):
            return False
        return True

    @staticmethod
    def quote_date_label(now: datetime) -> str:
        """行情所属交易日。开盘前和周末沿用上一工作日，节假日留到交易日历修正。"""
        day = now
        before_open = now.strftime("%H:%M") < "09:30"
        if now.weekday() >= 5 or before_open:
            if now.weekday() < 5 and before_open:
                day = now - timedelta(days=1)
            while day.weekday() >= 5:
                day = day - timedelta(days=1)
        return day.strftime("%Y-%m-%d")

    def sync_window_history(self, etf_code: str, window_days: int = 1825) -> pd.DataFrame:
        """按协议窗口增量补齐本地日 K。覆盖够时不打 HTTP。"""
        safe_days = max(30, int(window_days))
        end = datetime.now()
        start = end - timedelta(days=safe_days)
        frame = self._sync_and_fill_kline_lake(
            etf_code,
            start.strftime("%Y%m%d"),
            end.strftime("%Y%m%d"),
            days=safe_days,
        )
        if frame is None or frame.empty:
            return pd.DataFrame()
        return frame
    
    
    def get_trading_calendar(self, start_date: str, end_date: str) -> List[str]:
        """
        获取交易日历
        
        Args:
            start_date: 开始日期 (YYYYMMDD格式)
            end_date: 结束日期 (YYYYMMDD格式)
            
        Returns:
            List[str]: 交易日列表
        """
        try:
            # 解析年份范围
            start_year = int(start_date[:4])
            end_year = int(end_date[:4])
            
            all_trading_days = []
            
            # 按年获取交易日历
            for year in range(start_year, end_year + 1):
                year_calendar = self._get_trading_calendar_from_akshare(year)
                all_trading_days.extend(year_calendar)
            
            # 过滤指定日期范围
            filtered_days = [day for day in all_trading_days if start_date <= day <= end_date]
            
            logger.info(f"✓ 获取交易日历成功 ({start_date}~{end_date})，共{len(filtered_days)}个交易日")
            return filtered_days
            
        except Exception as e:
            logger.error(f"✗ 获取交易日历失败: {str(e)}")
            return []
    
    def get_etf_name(self, etf_code: str) -> Optional[str]:
        """
        轻量级获取ETF名称（永久缓存）
        
        Args:
            etf_code: ETF代码（不含市场后缀）
            
        Returns:
            str: ETF名称，如果获取失败返回None
        """
        # 1. 先检查永久缓存
        cached_data = self.cache.get_permanent_cache("etf_name", etf_code)
        if cached_data:
            logger.info(f"✓ 从永久缓存获取ETF {etf_code} 名称")
            return cached_data
        
        # 2. 缓存未命中，调用接口
        logger.info(f"→ 永久缓存未命中，请求AkShare接口获取ETF {etf_code} 名称")
        
        try:
            # 获取ETF基本信息
            basic_info = self.get_etf_basic_info(etf_code)
            if not basic_info:
                return None
            
            etf_name = basic_info['name']
            
            # 3. 成功获取数据，保存到永久缓存
            self.cache.set_permanent_cache("etf_name", etf_code, etf_name)
            logger.info(f"✓ ETF {etf_code} 名称获取成功并已永久缓存: {etf_name}")
            
            return etf_name
            
        except Exception as e:
            logger.error(f"✗ 请求AkShare接口失败，ETF {etf_code} 名称获取失败: {str(e)}")
            return None
    
    def get_cache_info(self) -> Dict:
        """
        获取缓存统计信息
        
        Returns:
            Dict: 缓存统计信息
        """
        return self.cache.get_cache_info()
    
    def get_latest_trading_date(self) -> str:
        """
        获取最近的交易日

        Returns:
            str: 最近的交易日 (YYYYMMDD格式)
        """
        current_time = datetime.now()
        current_date = current_time.strftime('%Y%m%d')
        
        # 获取当前年份的交易日历
        trading_calendar = self.get_trading_calendar(
            f"{current_time.year}0101",
            f"{current_time.year}1231"
        )
        
        if not trading_calendar:
            # 如果获取交易日历失败，使用简单逻辑
            logger.warning("获取交易日历失败，使用简单逻辑判断交易日")
            return self._get_simple_trading_date(current_time)
        
        # 判断当前日期是否为交易日
        if current_date in trading_calendar:
            # 当前是交易日
            return current_date
        else:
            # 当前不是交易日，获取上一个交易日
            return self.get_previous_trading_date(current_date)
    
    # =================== 辅助方法 ===================
    
    def _convert_akshare_daily_to_tushare_format(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        将AkShare日线数据格式转换为Tushare格式
        
        Args:
            df: AkShare原始数据
            
        Returns:
            DataFrame: 转换后的数据
        """
        # 列名映射
        column_mapping = {
            '日期': 'trade_date',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'vol',
            '成交额': 'amount',
            "振幅": 'amplitude',
            "涨跌幅": 'change',
            "涨跌额": 'change_amount',
            "换手率": 'turnover_rate',
        }
        
        # 重命名列
        df = df.rename(columns=column_mapping)
        
        # 处理日期格式 (YYYY-MM-DD -> YYYYMMDD)
        if 'trade_date' in df.columns:
            df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y%m%d')
            df['trade_date'] = pd.to_datetime(df['trade_date'])
        
        # 排序
        df = df.sort_values('trade_date')
        
        # 计算衍生字段
        df['pre_close'] = df['close'].shift(1)
        df['change'] = (df['close'] - df['pre_close']).round(4)
        df['pct_chg'] = ((df['close'] - df['pre_close']) / df['pre_close'] * 100).round(2)
        df['amplitude'] = ((df['high'] - df['low']) / df['pre_close'] * 100).round(2)
        
        # 处理第一行的NaN值
        df = df.fillna(0)
        
        return df.reset_index(drop=True)
    
    def _get_market_suffix(self, etf_code: str) -> str:
        """
        获取市场后缀
        
        Args:
            etf_code: ETF代码
            
        Returns:
            str: 市场后缀 (SH/SZ)
        """
        if etf_code.startswith(('15', '16', '18')):
            return 'SZ'  # 深交所
        else:
            return 'SH'  # 上交所
    
    def _adjust_end_date_if_needed(self, end_date: str, current_time: Optional[datetime] = None) -> str:
        """
        检查是否需要调整结束日期（如果包含当天且未收盘）
        
        Args:
            end_date: 原始结束日期 (YYYYMMDD格式)
            current_time: 当前时间（用于测试，默认为None时使用当前系统时间）
            
        Returns:
            str: 调整后的结束日期
        """
        try:
            # 获取当前日期和时间
            if current_time is None:
                current_time = datetime.now()
            current_date = current_time.strftime('%Y%m%d')
            
            # 如果结束日期不是当天，不需要调整
            if end_date != current_date:
                return end_date
            
            # 检查当前时间是否在交易时间内（15:00前）
            if not self._is_market_closed(current_time):
                # 未收盘，需要获取上一个交易日
                previous_trading_date = self.get_previous_trading_date(current_date)
                if previous_trading_date:
                    logger.info(f"→ 当天未收盘，将结束日期调整为上一个交易日: {previous_trading_date}")
                    return previous_trading_date
                else:
                    logger.warning(f"无法获取{current_date}的上一个交易日，使用原始日期")
                    return end_date
            else:
                # 已收盘，不需要调整
                logger.info(f"→ 当天已收盘，使用原始结束日期: {end_date}")
                return end_date
                
        except Exception as e:
            logger.error(f"调整结束日期时发生错误: {str(e)}")
            return end_date
    
    def _is_market_closed(self, current_time: datetime) -> bool:
        """
        判断市场是否已收盘（15:00后）
        
        Args:
            current_time: 当前时间
            
        Returns:
            bool: 是否已收盘
        """
        current_time_str = current_time.strftime('%H:%M')
        market_close_time = "15:00"
        return current_time_str >= market_close_time
    
    def get_previous_trading_date(self, current_date: str) -> Optional[str]:
        """
        获取指定日期的上一个交易日

        Args:
            current_date: 当前日期 (YYYYMMDD格式)

        Returns:
            str: 上一个交易日，如果获取失败返回None
        """
        try:
            # 解析年份
            year = int(current_date[:4])
            
            # 获取当前年份的交易日历
            trading_calendar = self.get_trading_calendar(
                f"{year}0101",
                f"{year}1231"
            )
            
            if not trading_calendar:
                # 如果获取失败，尝试获取前一年的交易日历
                trading_calendar = self.get_trading_calendar(
                    f"{year-1}0101",
                    f"{year-1}1231"
                )
                if not trading_calendar:
                    logger.warning(f"无法获取{year}年和{year-1}年的交易日历")
                    return None
            
            # 找到小于当前日期的最大交易日
            previous_dates = [date for date in trading_calendar if date < current_date]
            
            if previous_dates:
                previous_date = max(previous_dates)
                logger.debug(f"找到{current_date}的上一个交易日: {previous_date}")
                return previous_date
            else:
                # 如果没有找到，可能是年初，尝试获取前一年的最后一个交易日
                logger.debug(f"在当前年份未找到{current_date}之前的交易日，尝试前一年")
                previous_year_calendar = self.get_trading_calendar(
                    f"{year-1}0101",
                    f"{year-1}1231"
                )
                if previous_year_calendar:
                    previous_date = max(previous_year_calendar)
                    logger.debug(f"找到前一年的最后一个交易日: {previous_date}")
                    return previous_date
                else:
                    logger.warning(f"无法获取{current_date}的上一个交易日")
                    return None
                    
        except Exception as e:
            logger.error(f"获取上一个交易日时发生错误: {str(e)}")
            return None

    def _get_trading_calendar_from_akshare(self, year: int) -> List[str]:
        """
        从AkShare获取指定年份的交易日历
        
        Args:
            year: 年份
            
        Returns:
            List[str]: 交易日列表
        """
        try:
            # 先检查缓存
            cached_calendar = self.cache.get_permanent_cache("trading_cal", str(year))
            if cached_calendar:
                return cached_calendar
            
            # 调用AkShare交易日历接口
            df = ak.tool_trade_date_hist_sina()
            
            if df.empty:
                logger.warning(f"✗ AkShare交易日历接口返回空数据")
                return []
            
            # 处理日期格式
            df['trade_date'] = df['trade_date'].astype(str).str.replace('-', '')
            
            # 筛选年份
            year_filter = df['trade_date'].str.startswith(str(year))
            year_data = df[year_filter]['trade_date'].tolist()
            
            # 缓存结果
            self.cache.set_permanent_cache("trading_cal", str(year), year_data)
            
            logger.info(f"✓ 从AkShare获取{year}年交易日历成功，共{len(year_data)}个交易日")
            return year_data
            
        except Exception as e:
            logger.error(f"✗ 从AkShare获取{year}年交易日历失败: {str(e)}")
            return []
    
    def _complete_etf_code(self, etf_code: str) -> str:
        """
        自动补全ETF代码的市场后缀（兼容方法）

        Args:
            etf_code: ETF代码（不含市场后缀）

        Returns:
            str: 完整的ETF代码（含市场后缀）
        """
        etf_code = etf_code.split('.')[0]
        return f"{etf_code}.{self._get_market_suffix(etf_code)}"
    
    def _get_simple_trading_date(self, current_time: datetime) -> str:
        """
        简单的交易日判断逻辑（当交易日历获取失败时使用）

        Args:
            current_time: 当前时间

        Returns:
            str: 估算的交易日
        """
        # 简单逻辑：排除周末，不考虑节假日
        date = current_time
        
        # 如果是交易时间内，且是工作日，返回当天
        if (date.weekday() < 5 and  # 周一到周五
            self._is_market_closed(current_time)):
            return date.strftime('%Y%m%d')
        
        # 否则往前找最近的工作日
        while date.weekday() >= 5:  # 周末
            date = date - timedelta(days=1)
        
        return date.strftime('%Y%m%d')

    def _get_fallback_quote(self, etf_code: str) -> Optional[Dict]:
        """备用实时行情源 (腾讯财经)"""
        try:
            import requests
            code = etf_code.split('.')[0]
            prefix = 'sh' if code.startswith(('5', '6')) else 'sz'
            resp = requests.get(f'http://qt.gtimg.cn/q={prefix}{code}', timeout=5)
            resp.encoding = 'gbk'
            if '~' not in resp.text:
                return None
            parts = resp.text.split('~')
            if len(parts) < 45:
                return None
            return {
                'name': parts[1],
                'etf_name': parts[1],
                'current_price': float(parts[3]),
                'pre_close': float(parts[4]),
                'open_price': float(parts[5]),
                'high_price': float(parts[33]),
                'low_price': float(parts[34]),
                'change_amount': float(parts[31]),
                'pct_change': float(parts[32]),
                'amplitude': float(parts[43]),
                'volume': int(float(parts[6])),
                'amount': float(parts[37]) * 10000,
                'turnover_rate': float(parts[38]) if parts[38] else 0.0,
                'volume_ratio': 1.0,
                'iopv': float(parts[3]),
                'trading_date': self.get_latest_trading_date()
            }
        except Exception as e:
            logger.warning(f"备用行情获取失败: {str(e)}")
            return None

    def _normalize_calendar_date(self, value: Optional[str]) -> Optional[str]:
        """把 YYYYMMDD 或 YYYY-MM-DD 归一成 YYYY-MM-DD。"""
        if not value:
            return None
        text = str(value).replace("-", "")
        if len(text) == 8 and text.isdigit():
            return f"{text[:4]}-{text[4:6]}-{text[6:]}"
        return str(value)[:10]

    def _get_fallback_kline(
        self,
        etf_code: str,
        days: int = 180,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Optional[pd.DataFrame]:
        """备用K线源 (腾讯财经) - 按日历起止分段拉取，禁止按估算交易日截尾。"""
        try:
            import requests
            code = etf_code.split('.')[0]
            prefix = 'sh' if code.startswith(('5', '6')) else 'sz'
            bound_start = self._normalize_calendar_date(start_date)
            bound_end = self._normalize_calendar_date(end_date)
            if bound_start is None:
                bound_start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
            if bound_end is None:
                bound_end = datetime.now().strftime("%Y-%m-%d")

            session = requests.Session()
            session.trust_env = False  # 避免本地代理环境干扰
            
            all_raw_data = []
            current_end = ""
            chunk_size = 640
            max_loops = 8  # 最多拉取8轮，覆盖 5 年日历跨度
            
            for _ in range(max_loops):
                if not current_end:
                    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,,,{chunk_size},qfq'
                else:
                    url = f'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={prefix}{code},day,2015-01-01,{current_end},{chunk_size},qfq'
                
                res = session.get(url, timeout=6).json()
                item = res.get('data', {}).get(f'{prefix}{code}', {})
                raw_data = item.get('qfqday', item.get('day', []))
                if not raw_data:
                    break
                
                # 若是向前拉取，raw_data 的最后一条与 current_end 日期重合，去重
                if current_end and raw_data and raw_data[-1][0] == current_end:
                    raw_data = raw_data[:-1]
                
                if not raw_data:
                    break
                
                all_raw_data = raw_data + all_raw_data
                earliest_date = raw_data[0][0]
                if earliest_date == current_end:
                    break
                current_end = earliest_date
                
                # 单批明显不足 640 表示触及上市首日；已覆盖日历起点则停止
                if len(raw_data) < chunk_size - 10 or earliest_date <= bound_start:
                    break
            
            if not all_raw_data:
                return None

            all_raw_data = [
                row for row in all_raw_data
                if bound_start <= str(row[0])[:10] <= bound_end
            ]
            if not all_raw_data:
                return None
            
            records = []
            for row in all_raw_data:
                o_price = float(row[1])
                c_price = float(row[2])
                h_price = float(row[3])
                l_price = float(row[4])
                vol_val = float(row[5])
                # 估算成交额 (vol_val以手为单位，1手=100股，折算为成交金额元)
                avg_p = (o_price + c_price) / 2.0 if (o_price + c_price) > 0 else c_price
                calc_amount = vol_val * 100.0 * avg_p
                records.append({
                    'trade_date': pd.to_datetime(row[0]),
                    'open': o_price,
                    'close': c_price,
                    'high': h_price,
                    'low': l_price,
                    'vol': vol_val,
                    'amount': calc_amount,
                })
            records = self.pct_change_versus_previous_close(records)
            return pd.DataFrame(records).reset_index(drop=True)
        except Exception as e:
            logger.warning(f"备用K线获取失败: {str(e)}")
            return None

    _CASH_MARKERS = ('货币', '日利', '添益', '快钱', '快线', '财富宝')

    @staticmethod
    def classify_etf_item(name: str, code: str) -> Dict[str, Any]:
        """按名称互斥归入 11 个可购赛道。货币类在赋波幅之前剔除，漏网记为未归类。"""
        if any(marker in name for marker in AkShareClient._CASH_MARKERS):
            return {
                'excluded': True,
                'sector': None,
                'is_t0': False,
                'atr_pct': 0.0,
                'elasticity': None,
            }

        is_t0 = is_t0_instrument(code, name)

        if any(k in name for k in ['债', '短融', '存单']):
            sector = '债券与固收'
        elif any(k in name for k in ['黄金', '豆粕', '能源化工', '白银', '有色期货', '金ETF', '上海金']):
            sector = '大宗商品'
        elif any(k in name for k in [
            '恒生', '港股', '纳斯达克', '纳指', '标普', '日经', '德国', '法国',
            '中概', '亚太', '道琼斯', '巴西', '日本东证',
        ]):
            sector = '跨境全球'
        elif any(k in name for k in [
            '半导体', '芯片', '电子', '计算机', '软件', '通信', '人工智能', 'AI',
            '信创', '大数据', '传媒', '游戏', '物联网', '机器人', '卫星', '云计算',
            '集成电路', '科技ETF', '5G', '影视',
        ]):
            sector = '科技芯片'
        elif any(k in name for k in [
            '光伏', '新能源', '电池', '锂电', '风电', '储能', '汽车', '智能网联',
            '机械', '装备', '工业母机', '机床', '电网设备', '船舶',
        ]):
            sector = '新能源制造'
        elif any(k in name for k in ['医药', '医疗', '创新药', '中药', '生物', '疫苗']):
            sector = '医药健康'
        elif any(k in name for k in ['证券', '券商', '银行', '保险', '地产', '金融科技', '金融ETF']):
            sector = '大金融'
        elif any(k in name for k in ['消费', '白酒', '酒', '食品', '饮料', '家电', '农业', '养殖', '畜牧', '旅游', '粮食']):
            sector = '大消费'
        elif any(k in name for k in [
            '煤炭', '钢铁', '有色', '化工', '稀土', '金属', '油气', '能源', '资源',
            '石油', '石化', '矿业', '建材',
        ]):
            sector = '周期资源'
        elif any(k in name for k in ['电力', '绿电', '公用', '基建', '水务', '红利', '高股息', '低波']):
            sector = '公用红利'
        elif any(k in name for k in ['军工', '航天', '国防', '航空']):
            sector = '国防军工'
        elif any(k in name for k in [
            '300', '500', '1000', '2000', '50', '创业板', '科创50', '科创100',
            'A50', 'A500', '中证A', '综指', '上证', '深证', '中证800',
            '科创200', '科创创业', '价值', '成长', '现金流',
        ]):
            sector = '核心宽基'
        else:
            sector = UNCLASSIFIED_SECTOR

        return {
            'excluded': False,
            'sector': sector,
            'is_t0': is_t0,
            'atr_pct': None,
            'elasticity': INSUFFICIENT_DATA_LABEL,
            'metrics_status': INSUFFICIENT_DATA_LABEL,
        }

    @staticmethod
    def pct_change_versus_previous_close(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """涨跌幅相对前一日收盘。首日没有前收，记 0，不用开盘价代替。"""
        ordered = sorted(records, key=lambda item: str(item.get("trade_date")))
        previous_close = None
        for item in ordered:
            close_price = float(item.get("close") or 0.0)
            if previous_close is None or previous_close == 0:
                item["pct_chg"] = 0.0
            else:
                item["pct_chg"] = round((close_price - previous_close) / previous_close * 100, 2)
            previous_close = close_price
        return ordered

    def _local_bar_metrics(self, etf_code: str) -> Dict[str, Any]:
        """读取本地日 K 并计算 ATR 与 20 日均额。读不到就标数据不足。"""
        frame = None
        market_repo = getattr(self, "market_repo", None)
        if market_repo is not None and hasattr(market_repo, "get_bars"):
            try:
                frame = market_repo.get_bars(etf_code, limit=60)
            except Exception as exc:
                logger.debug("读取本地日 K 失败 %s: %s", etf_code, exc)
        return measure_local_metrics(frame)

    @staticmethod
    def extract_spot_quote(row: Dict[str, Any]) -> Optional[tuple]:
        """从行情行取出代码、最新价、涨跌幅。缺最新价时不用昨收顶替。"""
        raw_code = str(row.get("代码") or row.get("code") or "")
        code = raw_code.replace("sh", "").replace("sz", "").strip()
        if len(code) != 6 or not code.isdigit():
            return None
        if row.get("最新价") not in (None, ""):
            price = row.get("最新价")
        elif row.get("trade") not in (None, ""):
            price = row.get("trade")
        else:
            return None
        if row.get("涨跌幅") not in (None, ""):
            pct = row.get("涨跌幅")
        elif row.get("changepercent") not in (None, ""):
            pct = row.get("changepercent")
        else:
            pct = 0.0
        try:
            price_value = float(price)
            pct_value = float(pct)
        except (TypeError, ValueError):
            return None
        if price_value != price_value or pct_value != pct_value:
            return None
        return code, price_value, pct_value

    def _load_category_spot_rows(self) -> List[Dict[str, Any]]:
        """新浪 ETF 分类行情。列名由数据源给出，调用方按最新价读取。"""
        frame = ak.fund_etf_category_sina(symbol="ETF基金")
        return frame.to_dict(orient="records")

    def _overlay_live_quotes(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """用实时最新价覆盖已落库标的。行情失败时保留原快照。"""
        try:
            rows = self._load_category_spot_rows()
        except Exception as exc:
            logger.warning("刷新标的池行情失败，继续使用已落库价格: %s", exc)
            return records
        quotes: Dict[str, tuple] = {}
        for row in rows:
            parsed = self.extract_spot_quote(row)
            if parsed is None:
                continue
            code, price, pct = parsed
            quotes[code] = (price, pct)
        if not quotes:
            return records
        quote_date = self.quote_date_label(datetime.now())
        updates = []
        refreshed: List[Dict[str, Any]] = []
        for record in records:
            code = str(record.get("etf_code") or "")
            quote = quotes.get(code)
            if quote is None:
                refreshed.append(record)
                continue
            price, pct = quote
            updated = dict(record)
            updated["latest_price"] = price
            updated["pct_change"] = pct
            updated["quote_date"] = quote_date
            refreshed.append(updated)
            updates.append((code, price, pct))
        if updates:
            try:
                self.pool_repo.update_quotes(updates)
            except Exception as exc:
                logger.warning("落库最新行情失败: %s", exc)
        return refreshed

    def build_or_get_etf_pool(
        self,
        min_amount_10k: float = 0.0,
        min_ma20_amount_10k: float = 3000.0,
        min_atr_pct: float = 1.5,
        force_refresh: bool = False
    ) -> List[Dict[str, Any]]:
        """
        获取或构建全市场做 T 标的池（带月均 >= 3000 万、上市满 3 年、ATR >= 1.5% 三重品质护城河清洗，本地持久化）
        """
        if not force_refresh:
            existing = self.pool_repo.get_pool(
                min_amount_10k=min_amount_10k,
                min_ma20_amount_10k=min_ma20_amount_10k,
                min_atr_pct=min_atr_pct,
                limit=500
            )
            if existing and len(existing) >= 20:
                refreshed = self._overlay_live_quotes(existing)
                logger.info(f"✓ 从本地标的池直出 {len(refreshed)} 只，并覆盖实时最新价")
                return refreshed

        logger.info("→ 触发全市场做 T 标的池全量构建与三重护城河清洗...")
        try:
            df_spot = ak.fund_etf_category_sina(symbol="ETF基金")
            # 过滤未满 3 年次新 ETF 规则
            excluded_code_prefixes = ('1591', '1592', '1593', '551', '563', '5881')
            cleaned_records = []
            
            for row in df_spot.to_dict(orient='records'):
                raw_amt = float(row.get('成交额') or 0.0)
                amt_10k = raw_amt / 10000.0
                raw_code = str(row.get('代码', ''))
                clean_code = raw_code.replace('sh', '').replace('sz', '')
                metrics = self._local_bar_metrics(clean_code)
                ma20_amt_10k = metrics["amount_ma20_10k"] if metrics["turnover_sufficient"] else None

                # 1. 第一重护城河：近 20 日均成交额必须来自本地日 K，不够不放行
                if ma20_amt_10k is None or ma20_amt_10k < min_ma20_amount_10k or amt_10k < min_amount_10k:
                    continue

                name = str(row.get('名称', ''))

                # 2. 第二重护城河：排除未满 3 年次新标的
                if clean_code.startswith(excluded_code_prefixes) and any(k in name for k in ['A500', 'A50', '科创债', '公司债']):
                    continue

                classification = self.classify_etf_item(name, clean_code)
                if classification.get('excluded'):
                    continue

                # 3. 第三重护城河：14 日 ATR 来自本地日 K。样本不够不借用名称波幅。
                if not metrics["atr_sufficient"] or metrics["atr_pct"] < min_atr_pct:
                    continue

                p_val = float(row.get('最新价') or 0.0)
                pct_val = float(row.get('涨跌幅') or 0.0)
                cleaned_records.append({
                    'etf_code': clean_code,
                    'name': name,
                    'sector': classification['sector'],
                    'is_t0': classification['is_t0'],
                    'list_date': INSUFFICIENT_DATA_LABEL,
                    'latest_price': p_val,
                    'pct_change': pct_val,
                    'amount_10k': round(amt_10k, 2),
                    'amount_ma20_10k': ma20_amt_10k,
                    'atr_pct': metrics['atr_pct'],
                    'elasticity': metrics['elasticity'],
                    'metrics_status': 'local_bars',
                    'score': round(min(98.0, 70.0 + (ma20_amt_10k / 5000.0) * 5 + metrics['atr_pct'] * 4), 1)
                })

            # 4. 持久化落盘本地 SQLite 与 JSON 镜像
            self.pool_repo.save_pool(cleaned_records)
            logger.info(f"✓ 全市场做 T 标的池成功持久化至本地文件，共入库 {len(cleaned_records)} 只高胜率做 T 标的")
            return self.pool_repo.get_pool(
                min_amount_10k=min_amount_10k,
                min_ma20_amount_10k=min_ma20_amount_10k,
                min_atr_pct=min_atr_pct,
                limit=500
            )
        except Exception as e:
            logger.error(f"构建标的池失败: {e}")
            return self.pool_repo.get_pool(
                min_amount_10k=min_amount_10k,
                min_ma20_amount_10k=min_ma20_amount_10k,
                min_atr_pct=min_atr_pct,
                limit=500
            )

    def sync_full_history(self, etf_code: str) -> pd.DataFrame:
        """
        上市以来全生命周期日 K 线递归分段向前同步并幂等持久化至本地 SQLite
        """
        clean_code = etf_code.split('.')[0]
        prefix = 'sh' if clean_code.startswith(('5', '6')) else 'sz'
        tencent_code = f"{prefix}{clean_code}"

        all_raw_data = []
        chunk_size = 640
        latest_date = ""

        logger.info(f"→ 开始全生命周期向前递归拉取 {tencent_code} (上市首日至今)...")
        # 最多向前拉取 25 次（约 16,000 个交易日，足以覆盖 60 年）
        for _ in range(25):
            if not latest_date:
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,,,640,qfq"
            else:
                url = f"http://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param={tencent_code},day,,{latest_date},640,qfq"

            try:
                import requests
                resp = requests.get(url, timeout=6).json()
                stock_data = resp.get("data", {}).get(tencent_code, {})
                bars = stock_data.get("qfqday", stock_data.get("day", []))
                if not bars:
                    break

                all_raw_data = bars + all_raw_data
                earliest_date = str(bars[0][0])[:10]

                if earliest_date == latest_date or len(bars) < chunk_size - 10:
                    break
                latest_date = earliest_date
            except Exception as e:
                logger.warning(f"分段向前拉取异常: {e}")
                break

        if not all_raw_data:
            cached = self.market_repo.get_all_bars(clean_code)
            if not cached.empty:
                logger.info(f"✓ 外部网络接口拉取为空或异常，使用本地时序库已存 {len(cached)} 根 K 线兜底")
                return cached
            return pd.DataFrame()

        # 去重合并
        seen_dates = set()
        records = []
        for row in all_raw_data:
            d_str = str(row[0])[:10]
            if d_str in seen_dates:
                continue
            seen_dates.add(d_str)

            o_price = float(row[1])
            c_price = float(row[2])
            h_price = float(row[3])
            l_price = float(row[4])
            vol_val = float(row[5])
            avg_p = (o_price + c_price) / 2.0 if (o_price + c_price) > 0 else c_price
            calc_amount = vol_val * 100.0 * avg_p

            records.append({
                'trade_date': d_str,
                'open': o_price,
                'close': c_price,
                'high': h_price,
                'low': l_price,
                'vol': vol_val,
                'amount': calc_amount,
            })

        records = self.pct_change_versus_previous_close(records)
        df = pd.DataFrame(records).reset_index(drop=True)
        # 幂等全量落盘至本地 SQLite 时序库
        self.market_repo.save_bars(clean_code, df)
        logger.info(f"✓ {clean_code} 上市以来全生命周期共 {len(df)} 根 K 线成功同步并持久化到本地 SQLite！")
        return df