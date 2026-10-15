"""etf_grid 表结构。价格列用 DOUBLE，档案曲线与摘要分表。"""
import logging
from typing import Optional

from .db_config import is_sqlite
from .mysql_connection import (
    DEFAULT_DATABASE,
    TEST_DATABASE,
    connect,
    connect_server,
)
from .sqlite_dialect import adapt_ddl

logger = logging.getLogger(__name__)

BUSINESS_TABLES = (
    "universe_bootstrap_code",
    "universe_bootstrap",
    "universe_matrix_backtest",
    "backtest_run_payload",
    "backtest_run",
    "grid_fit_cell",
    "etf_daily_bar",
    "etf_instrument",
)

_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS etf_sector (
        sector_code VARCHAR(32) NOT NULL COMMENT '赛道编码，与名称相同',
        name VARCHAR(64) NOT NULL COMMENT '赛道名称',
        PRIMARY KEY (sector_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='可购赛道目录'
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_subsector (
        subsector_code VARCHAR(64) NOT NULL COMMENT '小类编码，与名称相同，全库互斥',
        sector_code VARCHAR(32) NOT NULL COMMENT '所属赛道编码',
        name VARCHAR(64) NOT NULL COMMENT '小类名称',
        sort_order INT NOT NULL COMMENT '同一赛道内的展示顺序，从小到大',
        PRIMARY KEY (subsector_code),
        KEY idx_subsector_sector (sector_code, sort_order)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='互斥小类目录'
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_instrument (
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码，不含交易所前缀',
        name VARCHAR(128) NOT NULL COMMENT 'ETF名称',
        sector VARCHAR(32) NOT NULL COMMENT '所属赛道。未命中可购赛道时为未归类',
        subsector_code VARCHAR(64) NULL COMMENT '互斥小类编码。未命中小类时为空，首页按此下钻',
        is_t0 TINYINT NOT NULL DEFAULT 0 COMMENT '是否支持日内回转。1是，0否',
        list_date VARCHAR(64) NULL COMMENT '上市说明文本，不一定是日期',
        latest_price DOUBLE NOT NULL DEFAULT 0 COMMENT '最新价',
        pct_change DOUBLE NOT NULL DEFAULT 0 COMMENT '最新涨跌幅，百分比',
        amount_10k DOUBLE NOT NULL DEFAULT 0 COMMENT '最新成交额，单位万元',
        amount_ma20_10k DOUBLE NOT NULL DEFAULT 0 COMMENT '近20日均成交额，单位万元。雷达门槛3000',
        atr_pct DOUBLE NOT NULL DEFAULT 0 COMMENT 'ATR波幅，百分比。雷达门槛1.5',
        elasticity VARCHAR(32) NOT NULL DEFAULT '稳健型' COMMENT '弹性档位：高弹性、稳健型、低波防守',
        score DOUBLE NOT NULL DEFAULT 80 COMMENT '做T评分',
        is_seed TINYINT NOT NULL DEFAULT 0 COMMENT '是否为该小类流动性最高的种子。1是，0否',
        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',
        PRIMARY KEY (etf_code),
        KEY idx_instrument_sector (sector),
        KEY idx_instrument_subsector (subsector_code),
        KEY idx_instrument_ma20 (amount_ma20_10k)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='做T标的池。首页雷达读这张表'
    """,
    """
    CREATE TABLE IF NOT EXISTS etf_daily_bar (
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        trade_date CHAR(10) NOT NULL COMMENT '交易日，格式YYYY-MM-DD',
        open DOUBLE NOT NULL COMMENT '前复权开盘价',
        close DOUBLE NOT NULL COMMENT '前复权收盘价',
        high DOUBLE NOT NULL COMMENT '前复权最高价',
        low DOUBLE NOT NULL COMMENT '前复权最低价',
        vol DOUBLE NOT NULL COMMENT '成交量，单位手',
        amount DOUBLE NOT NULL COMMENT '成交额，单位元',
        pct_chg DOUBLE NOT NULL COMMENT '当日涨跌幅，百分比',
        created_at VARCHAR(32) NULL COMMENT '入库时间，东八区本地时间字符串',
        PRIMARY KEY (etf_code, trade_date)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='日K线'
    """,
    """
    CREATE TABLE IF NOT EXISTS universe_bootstrap (
        id INTEGER NOT NULL PRIMARY KEY COMMENT '固定为 1 的引导状态行',
        list_fetched_at VARCHAR(32) NULL COMMENT '最近一次拿到全市场名单的时间',
        completed_at VARCHAR(32) NULL COMMENT '全市场日K引导完成时间。空表示尚未完成，启动时要续传',
        total_codes INT NOT NULL DEFAULT 0 COMMENT '当前名单上的代码数',
        done_codes INT NOT NULL DEFAULT 0 COMMENT '已有日K或确认源站无行情的代码数',
        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',
        empty_recheck_at VARCHAR(32) NULL COMMENT '误记空行情的回查标记。空表示还没做过这次修复'
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全市场日K引导进度。完成前不把标的池当成已经建完'
    """,
    """
    CREATE TABLE IF NOT EXISTS universe_bootstrap_code (
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码，不含交易所前缀',
        etf_name VARCHAR(128) NOT NULL COMMENT '名单上的名称',
        status VARCHAR(16) NOT NULL COMMENT 'pending待拉取，synced已有日K，empty源站无行情',
        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',
        PRIMARY KEY (etf_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全市场日K引导的逐代码进度'
    """,
    """
    CREATE TABLE IF NOT EXISTS grid_fit_cell (
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        etf_name VARCHAR(128) NULL COMMENT '写入时的标的名称快照',
        sector VARCHAR(32) NULL COMMENT '写入时的赛道快照',
        step_mode VARCHAR(32) NOT NULL COMMENT '步长模式。atr为ATR自适应，fixed_eda为自定义网格',
        protocol_version VARCHAR(16) NOT NULL COMMENT '适合度协议版本，当前为v1',
        calendar_days INT NULL COMMENT '实际回看日历天数',
        sell_count INT NULL COMMENT '卖出次数',
        grid_cash_profit DOUBLE NULL COMMENT '网格现金收益',
        cash_yield DOUBLE NULL COMMENT '现金收益率',
        annual_return DOUBLE NULL COMMENT '年化收益率',
        alpha DOUBLE NULL COMMENT '相对买入持有的超额收益',
        max_drawdown DOUBLE NULL COMMENT '最大回撤',
        status VARCHAR(32) NOT NULL COMMENT '入榜状态',
        status_reason VARCHAR(255) NULL COMMENT '状态说明，如已入榜、成交过稀、回撤超线、样本短于五年、未就绪',
        source_fingerprint VARCHAR(64) NULL COMMENT '行情窗口指纹。相同则不重算',
        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',
        PRIMARY KEY (etf_code, step_mode, protocol_version)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='网格适合度结果。不含权益曲线和成交明细'
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_run (
        id BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
        run_id VARCHAR(64) NOT NULL COMMENT '档案业务主键',
        created_at VARCHAR(32) NULL COMMENT '创建时间，东八区本地时间字符串',
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        etf_name VARCHAR(128) NOT NULL COMMENT '写入时的标的名称快照',
        backtest_days INT NOT NULL COMMENT '请求回看天数',
        actual_days INT NOT NULL COMMENT '实际可用交易日数',
        total_capital DOUBLE NOT NULL COMMENT '回测本金',
        step_mode VARCHAR(32) NOT NULL COMMENT '步长模式。atr为ATR自适应，fixed_eda为自定义网格',
        step_bucket VARCHAR(32) NOT NULL COMMENT '最新标记分组。atr与fixed_eda各自一组，其余为unknown',
        reinvest_mode VARCHAR(32) NOT NULL COMMENT '收益处理。cash为留现金，pool_shares为利润池滚存留股',
        annual_return DOUBLE NOT NULL DEFAULT 0 COMMENT '年化收益率',
        max_drawdown DOUBLE NOT NULL DEFAULT 0 COMMENT '最大回撤',
        total_profit DOUBLE NOT NULL DEFAULT 0 COMMENT '总收益',
        total_trades INT NOT NULL DEFAULT 0 COMMENT '成交次数',
        free_shares INT NOT NULL DEFAULT 0 COMMENT '做T后剩余股数',
        is_partial_history TINYINT NOT NULL DEFAULT 0 COMMENT '历史是否短于请求窗口。1是，已用全部可用历史',
        partial_reason VARCHAR(255) NULL COMMENT '历史不足说明',
        params_json MEDIUMTEXT NULL COMMENT '请求参数快照，不含曲线',
        summary_json MEDIUMTEXT NULL COMMENT '指标摘要，不含权益曲线和成交明细',
        is_latest TINYINT NOT NULL DEFAULT 0 COMMENT '是否为同一标的、同一回看天数、同一步长分组下的最新档案。1是',
        PRIMARY KEY (id),
        UNIQUE KEY uk_backtest_run_id (run_id),
        KEY idx_backtest_latest (etf_code, backtest_days, step_bucket, is_latest)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个人回测档案摘要'
    """,
    """
    CREATE TABLE IF NOT EXISTS backtest_run_payload (
        run_id VARCHAR(64) NOT NULL COMMENT '对应backtest_run.run_id',
        equity_curve_json MEDIUMTEXT NULL COMMENT '权益曲线JSON',
        trades_json MEDIUMTEXT NULL COMMENT '成交明细JSON',
        PRIMARY KEY (run_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='个人回测档案的权益曲线和成交明细'
    """,
    """
    CREATE TABLE IF NOT EXISTS universe_matrix_backtest (
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF 6位代码，如 510300',
        config_key VARCHAR(64) NOT NULL COMMENT '策略参数指纹，如 atr_0.6_1.2_2.5 或 fixed_0.05_0.15_0.30',
        config_label VARCHAR(64) NOT NULL COMMENT '参数人类可读标签，如 ATR自适应 (0.6/1.2/2.5)',
        etf_name VARCHAR(128) NOT NULL COMMENT '标的简称快照，如 沪深300ETF',
        sector VARCHAR(32) NOT NULL COMMENT '所属11大赛道，如 科技芯片、公用红利',
        is_default_preset TINYINT NOT NULL DEFAULT 1 COMMENT '是否为系统默认推荐配置: 1是, 0否',
        
        step_mode VARCHAR(16) NOT NULL DEFAULT 'atr' COMMENT '步长模式: atr(动态自适应) | fixed_eda(固定步长)',
        atr_small_mult DOUBLE NULL COMMENT '小网ATR乘数(自适应模式)',
        atr_mid_mult DOUBLE NULL COMMENT '中网ATR乘数(自适应模式)',
        atr_large_mult DOUBLE NULL COMMENT '大网ATR乘数(自适应模式)',
        step_small_ratio DOUBLE NULL COMMENT '小网固定步长比例(固定步长模式)',
        step_mid_ratio DOUBLE NULL COMMENT '中网固定步长比例(固定步长模式)',
        step_large_ratio DOUBLE NULL COMMENT '大网固定步长比例(固定步长模式)',

        total_capital DOUBLE NOT NULL DEFAULT 30000.0 COMMENT '回测初始总投资资金量(元)',
        scaling_ratio DOUBLE NOT NULL DEFAULT 0.10 COMMENT '逢跌买入节奏逐格加码比例: 0.10为倒金字塔递增10%',
        reinvest_mode VARCHAR(16) NOT NULL DEFAULT 'pool_shares' COMMENT '做T收益留存模式: pool_shares留股(推荐) | cash留现金',
        total_bars INT NOT NULL DEFAULT 0 COMMENT '本地数据库累计日K线总数',

        is_valid_90d TINYINT NOT NULL DEFAULT 1 COMMENT '90天回测是否有效(交易日不足45天为0)',
        ret_90d DOUBLE NULL COMMENT '90天年化收益率(%)',
        mdd_90d DOUBLE NULL COMMENT '90天最大回撤(%)',
        calmar_90d DOUBLE NULL COMMENT '90天卡玛比率(年化收益/最大回撤)',
        trades_90d INT NULL DEFAULT 0 COMMENT '90天网格成交总次数',
        free_shares_90d INT NULL DEFAULT 0 COMMENT '90天做T免费滚存沉淀总股数',
        base_price_90d DOUBLE NULL COMMENT '90天基准锚点开盘价P0(元)',

        is_valid_180d TINYINT NOT NULL DEFAULT 1 COMMENT '半年回测是否有效(交易日不足90天为0)',
        ret_180d DOUBLE NULL COMMENT '半年年化收益率(%)',
        mdd_180d DOUBLE NULL COMMENT '半年最大回撤(%)',
        calmar_180d DOUBLE NULL COMMENT '半年卡玛比率(年化收益/最大回撤)',
        trades_180d INT NULL DEFAULT 0 COMMENT '半年网格成交总次数',
        free_shares_180d INT NULL DEFAULT 0 COMMENT '半年做T免费滚存沉淀总股数',
        base_price_180d DOUBLE NULL COMMENT '半年基准锚点开盘价P0(元)',

        is_valid_1y TINYINT NOT NULL DEFAULT 1 COMMENT '1年回测是否有效(交易日不足180天为0)',
        ret_1y DOUBLE NULL COMMENT '1年年化收益率(%)',
        mdd_1y DOUBLE NULL COMMENT '1年最大回撤(%)',
        calmar_1y DOUBLE NULL COMMENT '1年卡玛比率(年化收益/最大回撤)',
        trades_1y INT NULL DEFAULT 0 COMMENT '1年网格成交总次数',
        free_shares_1y INT NULL DEFAULT 0 COMMENT '1年做T免费滚存沉淀总股数',
        base_price_1y DOUBLE NULL COMMENT '1年基准锚点开盘价P0(元)',

        is_valid_2y TINYINT NOT NULL DEFAULT 1 COMMENT '2年回测是否有效(交易日不足365天为0)',
        ret_2y DOUBLE NULL COMMENT '2年年化收益率(%)',
        mdd_2y DOUBLE NULL COMMENT '2年最大回撤(%)',
        calmar_2y DOUBLE NULL COMMENT '2年卡玛比率(年化收益/最大回撤)',
        trades_2y INT NULL DEFAULT 0 COMMENT '2年网格成交总次数',
        free_shares_2y INT NULL DEFAULT 0 COMMENT '2年做T免费滚存沉淀总股数',
        base_price_2y DOUBLE NULL COMMENT '2年基准锚点开盘价P0(元)',

        is_valid_3y TINYINT NOT NULL DEFAULT 1 COMMENT '3年回测是否有效(交易日不足550天为0)',
        ret_3y DOUBLE NULL COMMENT '3年年化收益率(%)',
        mdd_3y DOUBLE NULL COMMENT '3年最大回撤(%)',
        calmar_3y DOUBLE NULL COMMENT '3年卡玛比率(年化收益/最大回撤)',
        trades_3y INT NULL DEFAULT 0 COMMENT '3年网格成交总次数',
        free_shares_3y INT NULL DEFAULT 0 COMMENT '3年做T免费滚存沉淀总股数',
        base_price_3y DOUBLE NULL COMMENT '3年基准锚点开盘价P0(元)',

        is_valid_5y TINYINT NOT NULL DEFAULT 1 COMMENT '5年回测是否有效(交易日不足915天为0)',
        ret_5y DOUBLE NULL COMMENT '5年年化收益率(%)，次新为NULL',
        mdd_5y DOUBLE NULL COMMENT '5年最大回撤(%)，次新为NULL',
        calmar_5y DOUBLE NULL COMMENT '5年卡玛比率(年化收益/最大回撤)，次新为NULL',
        trades_5y INT NULL DEFAULT 0 COMMENT '5年网格成交总次数，次新为NULL',
        free_shares_5y INT NULL DEFAULT 0 COMMENT '5年做T免费滚存沉淀总股数，次新为NULL',
        base_price_5y DOUBLE NULL COMMENT '5年前基准锚点开盘价P0(元)，次新为NULL',

        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',

        PRIMARY KEY (etf_code, config_key),
        KEY idx_default_sector_ret (is_default_preset, sector, is_valid_5y, ret_5y),
        KEY idx_matrix_ret_5y (ret_5y),
        KEY idx_matrix_ret_3y (ret_3y),
        KEY idx_matrix_ret_1y (ret_1y),
        KEY idx_matrix_code (etf_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全市场做T成熟ETF多周期回测矩阵大宽表'
    """,
    """
    CREATE TABLE IF NOT EXISTS grid_ledger_plan (
        id BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
        etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码，一只标的一份账本',
        etf_name VARCHAR(128) NOT NULL DEFAULT '' COMMENT '名称快照',
        anchor_price DOUBLE NOT NULL DEFAULT 0 COMMENT '开网锚点',
        base_shares INT NOT NULL DEFAULT 0 COMMENT '底仓股数',
        base_price DOUBLE NOT NULL DEFAULT 0 COMMENT '底仓参考价',
        created_at VARCHAR(32) NULL COMMENT '创建时间，东八区本地时间字符串',
        updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串',
        PRIMARY KEY (id),
        UNIQUE KEY uk_ledger_plan_code (etf_code)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='本地网格账本。一只标的保留当前方案'
    """,
    """
    CREATE TABLE IF NOT EXISTS grid_ledger_order (
        id BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
        plan_id BIGINT NOT NULL COMMENT '所属方案',
        side VARCHAR(8) NOT NULL COMMENT '买入或卖出',
        trigger_price DOUBLE NOT NULL COMMENT '触发价',
        shares INT NOT NULL COMMENT '股数',
        note VARCHAR(255) NOT NULL DEFAULT '' COMMENT '备注，如同价合并或底仓',
        rail VARCHAR(32) NOT NULL DEFAULT '' COMMENT '所属网格。账本按网各占一行，底仓为底仓',
        status VARCHAR(8) NOT NULL DEFAULT '未挂' COMMENT '未挂、已挂、已成、作废、待买入',
        updated_at VARCHAR(32) NULL COMMENT '最近状态时间，东八区本地时间字符串',
        PRIMARY KEY (id),
        KEY idx_ledger_order_plan (plan_id)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账本里的每一笔委托'
    """,
)

_COMMENT_ALTERS = (
    """
    ALTER TABLE etf_sector
        COMMENT = '可购赛道目录',
        MODIFY COLUMN sector_code VARCHAR(32) NOT NULL COMMENT '赛道编码，与名称相同',
        MODIFY COLUMN name VARCHAR(64) NOT NULL COMMENT '赛道名称'
    """,
    """
    ALTER TABLE etf_subsector
        COMMENT = '互斥小类目录',
        MODIFY COLUMN subsector_code VARCHAR(64) NOT NULL COMMENT '小类编码，与名称相同，全库互斥',
        MODIFY COLUMN sector_code VARCHAR(32) NOT NULL COMMENT '所属赛道编码',
        MODIFY COLUMN name VARCHAR(64) NOT NULL COMMENT '小类名称',
        MODIFY COLUMN sort_order INT NOT NULL COMMENT '同一赛道内的展示顺序，从小到大'
    """,
    """
    ALTER TABLE etf_instrument
        COMMENT = '做T标的池。首页雷达读这张表',
        MODIFY COLUMN etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码，不含交易所前缀',
        MODIFY COLUMN name VARCHAR(128) NOT NULL COMMENT 'ETF名称',
        MODIFY COLUMN sector VARCHAR(32) NOT NULL COMMENT '所属赛道。未命中可购赛道时为未归类',
        MODIFY COLUMN subsector_code VARCHAR(64) NULL COMMENT '互斥小类编码。未命中小类时为空，首页按此下钻',
        MODIFY COLUMN is_t0 TINYINT NOT NULL DEFAULT 0 COMMENT '是否支持日内回转。1是，0否',
        MODIFY COLUMN list_date VARCHAR(64) NULL COMMENT '上市说明文本，不一定是日期',
        MODIFY COLUMN latest_price DOUBLE NOT NULL DEFAULT 0 COMMENT '最新价',
        MODIFY COLUMN pct_change DOUBLE NOT NULL DEFAULT 0 COMMENT '最新涨跌幅，百分比',
        MODIFY COLUMN amount_10k DOUBLE NOT NULL DEFAULT 0 COMMENT '最新成交额，单位万元',
        MODIFY COLUMN amount_ma20_10k DOUBLE NOT NULL DEFAULT 0 COMMENT '近20日均成交额，单位万元。雷达门槛3000',
        MODIFY COLUMN atr_pct DOUBLE NOT NULL DEFAULT 0 COMMENT 'ATR波幅，百分比。雷达门槛1.5',
        MODIFY COLUMN elasticity VARCHAR(32) NOT NULL DEFAULT '稳健型' COMMENT '弹性档位：高弹性、稳健型、低波防守',
        MODIFY COLUMN score DOUBLE NOT NULL DEFAULT 80 COMMENT '做T评分',
        MODIFY COLUMN is_seed TINYINT NOT NULL DEFAULT 0 COMMENT '是否为该小类流动性最高的种子。1是，0否',
        MODIFY COLUMN updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串'
    """,
    """
    ALTER TABLE etf_daily_bar
        COMMENT = '日K线',
        MODIFY COLUMN etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        MODIFY COLUMN trade_date CHAR(10) NOT NULL COMMENT '交易日，格式YYYY-MM-DD',
        MODIFY COLUMN open DOUBLE NOT NULL COMMENT '前复权开盘价',
        MODIFY COLUMN close DOUBLE NOT NULL COMMENT '前复权收盘价',
        MODIFY COLUMN high DOUBLE NOT NULL COMMENT '前复权最高价',
        MODIFY COLUMN low DOUBLE NOT NULL COMMENT '前复权最低价',
        MODIFY COLUMN vol DOUBLE NOT NULL COMMENT '成交量，单位手',
        MODIFY COLUMN amount DOUBLE NOT NULL COMMENT '成交额，单位元',
        MODIFY COLUMN pct_chg DOUBLE NOT NULL COMMENT '当日涨跌幅，百分比',
        MODIFY COLUMN created_at VARCHAR(32) NULL COMMENT '入库时间，东八区本地时间字符串'
    """,
    """
    ALTER TABLE grid_fit_cell
        COMMENT = '网格适合度结果。不含权益曲线和成交明细',
        MODIFY COLUMN etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        MODIFY COLUMN etf_name VARCHAR(128) NULL COMMENT '写入时的标的名称快照',
        MODIFY COLUMN sector VARCHAR(32) NULL COMMENT '写入时的赛道快照',
        MODIFY COLUMN step_mode VARCHAR(32) NOT NULL COMMENT '步长模式。atr为ATR自适应，fixed_eda为自定义网格',
        MODIFY COLUMN protocol_version VARCHAR(16) NOT NULL COMMENT '适合度协议版本，当前为v1',
        MODIFY COLUMN calendar_days INT NULL COMMENT '实际回看日历天数',
        MODIFY COLUMN sell_count INT NULL COMMENT '卖出次数',
        MODIFY COLUMN grid_cash_profit DOUBLE NULL COMMENT '网格现金收益',
        MODIFY COLUMN cash_yield DOUBLE NULL COMMENT '现金收益率',
        MODIFY COLUMN annual_return DOUBLE NULL COMMENT '年化收益率',
        MODIFY COLUMN alpha DOUBLE NULL COMMENT '相对买入持有的超额收益',
        MODIFY COLUMN max_drawdown DOUBLE NULL COMMENT '最大回撤',
        MODIFY COLUMN status VARCHAR(32) NOT NULL COMMENT '入榜状态',
        MODIFY COLUMN status_reason VARCHAR(255) NULL COMMENT '状态说明，如已入榜、成交过稀、回撤超线、样本短于五年、未就绪',
        MODIFY COLUMN source_fingerprint VARCHAR(64) NULL COMMENT '行情窗口指纹。相同则不重算',
        MODIFY COLUMN updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串'
    """,
    """
    ALTER TABLE backtest_run
        COMMENT = '个人回测档案摘要',
        MODIFY COLUMN id BIGINT NOT NULL AUTO_INCREMENT COMMENT '自增主键',
        MODIFY COLUMN run_id VARCHAR(64) NOT NULL COMMENT '档案业务主键',
        MODIFY COLUMN created_at VARCHAR(32) NULL COMMENT '创建时间，东八区本地时间字符串',
        MODIFY COLUMN etf_code VARCHAR(16) NOT NULL COMMENT 'ETF代码',
        MODIFY COLUMN etf_name VARCHAR(128) NOT NULL COMMENT '写入时的标的名称快照',
        MODIFY COLUMN backtest_days INT NOT NULL COMMENT '请求回看天数',
        MODIFY COLUMN actual_days INT NOT NULL COMMENT '实际可用交易日数',
        MODIFY COLUMN total_capital DOUBLE NOT NULL COMMENT '回测本金',
        MODIFY COLUMN step_mode VARCHAR(32) NOT NULL COMMENT '步长模式。atr为ATR自适应，fixed_eda为自定义网格',
        MODIFY COLUMN step_bucket VARCHAR(32) NOT NULL COMMENT '最新标记分组。atr与fixed_eda各自一组，其余为unknown',
        MODIFY COLUMN reinvest_mode VARCHAR(32) NOT NULL COMMENT '收益处理。cash为留现金，pool_shares为利润池滚存留股',
        MODIFY COLUMN annual_return DOUBLE NOT NULL DEFAULT 0 COMMENT '年化收益率',
        MODIFY COLUMN max_drawdown DOUBLE NOT NULL DEFAULT 0 COMMENT '最大回撤',
        MODIFY COLUMN total_profit DOUBLE NOT NULL DEFAULT 0 COMMENT '总收益',
        MODIFY COLUMN total_trades INT NOT NULL DEFAULT 0 COMMENT '成交次数',
        MODIFY COLUMN free_shares INT NOT NULL DEFAULT 0 COMMENT '做T后剩余股数',
        MODIFY COLUMN is_partial_history TINYINT NOT NULL DEFAULT 0 COMMENT '历史是否短于请求窗口。1是，已用全部可用历史',
        MODIFY COLUMN partial_reason VARCHAR(255) NULL COMMENT '历史不足说明',
        MODIFY COLUMN params_json MEDIUMTEXT NULL COMMENT '请求参数快照，不含曲线',
        MODIFY COLUMN summary_json MEDIUMTEXT NULL COMMENT '指标摘要，不含权益曲线和成交明细',
        MODIFY COLUMN is_latest TINYINT NOT NULL DEFAULT 0 COMMENT '是否为同一标的、同一回看天数、同一步长分组下的最新档案。1是'
    """,
    """
    ALTER TABLE backtest_run_payload
        COMMENT = '个人回测档案的权益曲线和成交明细',
        MODIFY COLUMN run_id VARCHAR(64) NOT NULL COMMENT '对应backtest_run.run_id',
        MODIFY COLUMN equity_curve_json MEDIUMTEXT NULL COMMENT '权益曲线JSON',
        MODIFY COLUMN trades_json MEDIUMTEXT NULL COMMENT '成交明细JSON'
    """,
    """
    ALTER TABLE universe_matrix_backtest
        COMMENT = '全市场做T成熟ETF多周期回测矩阵大宽表',
        MODIFY COLUMN etf_code VARCHAR(16) NOT NULL COMMENT 'ETF 6位代码，如 510300',
        MODIFY COLUMN config_key VARCHAR(64) NOT NULL COMMENT '策略参数指纹，如 atr_0.6_1.2_2.5 或 fixed_0.05_0.15_0.30',
        MODIFY COLUMN config_label VARCHAR(64) NOT NULL COMMENT '参数人类可读标签，如 ATR自适应 (0.6/1.2/2.5)',
        MODIFY COLUMN etf_name VARCHAR(128) NOT NULL COMMENT '标的简称快照，如 沪深300ETF',
        MODIFY COLUMN sector VARCHAR(32) NOT NULL COMMENT '所属11大赛道，如 科技芯片、公用红利',
        MODIFY COLUMN is_default_preset TINYINT NOT NULL DEFAULT 1 COMMENT '是否为系统默认推荐配置: 1是, 0否',
        MODIFY COLUMN step_mode VARCHAR(16) NOT NULL DEFAULT 'atr' COMMENT '步长模式: atr(动态自适应) | fixed_eda(固定步长)',
        MODIFY COLUMN atr_small_mult DOUBLE NULL COMMENT '小网ATR乘数(自适应模式)',
        MODIFY COLUMN atr_mid_mult DOUBLE NULL COMMENT '中网ATR乘数(自适应模式)',
        MODIFY COLUMN atr_large_mult DOUBLE NULL COMMENT '大网ATR乘数(自适应模式)',
        MODIFY COLUMN step_small_ratio DOUBLE NULL COMMENT '小网固定步长比例(固定步长模式)',
        MODIFY COLUMN step_mid_ratio DOUBLE NULL COMMENT '中网固定步长比例(固定步长模式)',
        MODIFY COLUMN step_large_ratio DOUBLE NULL COMMENT '大网固定步长比例(固定步长模式)',
        MODIFY COLUMN total_capital DOUBLE NOT NULL DEFAULT 30000.0 COMMENT '回测初始总投资资金量(元)',
        MODIFY COLUMN scaling_ratio DOUBLE NOT NULL DEFAULT 0.10 COMMENT '逢跌买入节奏逐格加码比例: 0.10为倒金字塔递增10%',
        MODIFY COLUMN reinvest_mode VARCHAR(16) NOT NULL DEFAULT 'pool_shares' COMMENT '做T收益留存模式: pool_shares留股(推荐) | cash留现金',
        MODIFY COLUMN total_bars INT NOT NULL DEFAULT 0 COMMENT '本地数据库累计日K线总数',
        MODIFY COLUMN is_valid_90d TINYINT NOT NULL DEFAULT 1 COMMENT '90天回测是否有效(交易日不足45天为0)',
        MODIFY COLUMN ret_90d DOUBLE NULL COMMENT '90天年化收益率(%)',
        MODIFY COLUMN mdd_90d DOUBLE NULL COMMENT '90天最大回撤(%)',
        MODIFY COLUMN calmar_90d DOUBLE NULL COMMENT '90天卡玛比率(年化收益/最大回撤)',
        MODIFY COLUMN trades_90d INT NULL DEFAULT 0 COMMENT '90天网格成交总次数',
        MODIFY COLUMN free_shares_90d INT NULL DEFAULT 0 COMMENT '90天做T免费滚存沉淀总股数',
        MODIFY COLUMN base_price_90d DOUBLE NULL COMMENT '90天基准锚点开盘价P0(元)',
        MODIFY COLUMN is_valid_180d TINYINT NOT NULL DEFAULT 1 COMMENT '半年回测是否有效(交易日不足90天为0)',
        MODIFY COLUMN ret_180d DOUBLE NULL COMMENT '半年年化收益率(%)',
        MODIFY COLUMN mdd_180d DOUBLE NULL COMMENT '半年最大回撤(%)',
        MODIFY COLUMN calmar_180d DOUBLE NULL COMMENT '半年卡玛比率(年化收益/最大回撤)',
        MODIFY COLUMN trades_180d INT NULL DEFAULT 0 COMMENT '半年网格成交总次数',
        MODIFY COLUMN free_shares_180d INT NULL DEFAULT 0 COMMENT '半年做T免费滚存沉淀总股数',
        MODIFY COLUMN base_price_180d DOUBLE NULL COMMENT '半年基准锚点开盘价P0(元)',
        MODIFY COLUMN is_valid_1y TINYINT NOT NULL DEFAULT 1 COMMENT '1年回测是否有效(交易日不足180天为0)',
        MODIFY COLUMN ret_1y DOUBLE NULL COMMENT '1年年化收益率(%)',
        MODIFY COLUMN mdd_1y DOUBLE NULL COMMENT '1年最大回撤(%)',
        MODIFY COLUMN calmar_1y DOUBLE NULL COMMENT '1年卡玛比率(年化收益/最大回撤)',
        MODIFY COLUMN trades_1y INT NULL DEFAULT 0 COMMENT '1年网格成交总次数',
        MODIFY COLUMN free_shares_1y INT NULL DEFAULT 0 COMMENT '1年做T免费滚存沉淀总股数',
        MODIFY COLUMN base_price_1y DOUBLE NULL COMMENT '1年基准锚点开盘价P0(元)',
        MODIFY COLUMN is_valid_2y TINYINT NOT NULL DEFAULT 1 COMMENT '2年回测是否有效(交易日不足365天为0)',
        MODIFY COLUMN ret_2y DOUBLE NULL COMMENT '2年年化收益率(%)',
        MODIFY COLUMN mdd_2y DOUBLE NULL COMMENT '2年最大回撤(%)',
        MODIFY COLUMN calmar_2y DOUBLE NULL COMMENT '2年卡玛比率(年化收益/最大回撤)',
        MODIFY COLUMN trades_2y INT NULL DEFAULT 0 COMMENT '2年网格成交总次数',
        MODIFY COLUMN free_shares_2y INT NULL DEFAULT 0 COMMENT '2年做T免费滚存沉淀总股数',
        MODIFY COLUMN base_price_2y DOUBLE NULL COMMENT '2年基准锚点开盘价P0(元)',
        MODIFY COLUMN is_valid_3y TINYINT NOT NULL DEFAULT 1 COMMENT '3年回测是否有效(交易日不足550天为0)',
        MODIFY COLUMN ret_3y DOUBLE NULL COMMENT '3年年化收益率(%)',
        MODIFY COLUMN mdd_3y DOUBLE NULL COMMENT '3年最大回撤(%)',
        MODIFY COLUMN calmar_3y DOUBLE NULL COMMENT '3年卡玛比率(年化收益/最大回撤)',
        MODIFY COLUMN trades_3y INT NULL DEFAULT 0 COMMENT '3年网格成交总次数',
        MODIFY COLUMN free_shares_3y INT NULL DEFAULT 0 COMMENT '3年做T免费滚存沉淀总股数',
        MODIFY COLUMN base_price_3y DOUBLE NULL COMMENT '3年基准锚点开盘价P0(元)',
        MODIFY COLUMN is_valid_5y TINYINT NOT NULL DEFAULT 1 COMMENT '5年回测是否有效(交易日不足915天为0)',
        MODIFY COLUMN ret_5y DOUBLE NULL COMMENT '5年年化收益率(%)，次新为NULL',
        MODIFY COLUMN mdd_5y DOUBLE NULL COMMENT '5年最大回撤(%)，次新为NULL',
        MODIFY COLUMN calmar_5y DOUBLE NULL COMMENT '5年卡玛比率(年化收益/最大回撤)，次新为NULL',
        MODIFY COLUMN trades_5y INT NULL DEFAULT 0 COMMENT '5年网格成交总次数，次新为NULL',
        MODIFY COLUMN free_shares_5y INT NULL DEFAULT 0 COMMENT '5年做T免费滚存沉淀总股数，次新为NULL',
        MODIFY COLUMN base_price_5y DOUBLE NULL COMMENT '5年前基准锚点开盘价P0(元)，次新为NULL',
        MODIFY COLUMN updated_at VARCHAR(32) NULL COMMENT '最近写入时间，东八区本地时间字符串'
    """,
)


def ensure_database(name: str) -> None:
    """建库并建表。库名只允许本项目的两个固定库。"""
    if name not in (DEFAULT_DATABASE, TEST_DATABASE):
        raise ValueError(f"拒绝创建未登记的库: {name}")
    if not is_sqlite():
        server = connect_server()
        try:
            with server.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            server.commit()
        finally:
            server.close()
    ensure_tables(name)


def ensure_bootstrap_recheck_column(cursor, database: Optional[str] = None) -> None:
    """旧库补上误记空行情的回查时间。已有这一列时不改数据。"""
    if is_sqlite():
        cursor.execute("PRAGMA table_info(universe_bootstrap)")
        names = {row["name"] for row in cursor.fetchall()}
        if "empty_recheck_at" not in names:
            cursor.execute(
                "ALTER TABLE universe_bootstrap ADD COLUMN empty_recheck_at TEXT NULL"
            )
        return
    cursor.execute(
        """
        SELECT COLUMN_NAME AS name FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'universe_bootstrap'
          AND COLUMN_NAME = 'empty_recheck_at'
        """,
        (database or DEFAULT_DATABASE,),
    )
    if cursor.fetchone() is None:
        cursor.execute(
            """
            ALTER TABLE universe_bootstrap
            ADD COLUMN empty_recheck_at VARCHAR(32) NULL
            COMMENT '误记空行情的回查标记。空表示还没做过这次修复'
            """
        )


def ensure_tables(database: Optional[str] = None) -> None:
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            for statement in _STATEMENTS:
                if is_sqlite():
                    create_sql, indexes = adapt_ddl(statement)
                    cursor.execute(create_sql)
                    for index_sql in indexes:
                        cursor.execute(index_sql)
                else:
                    cursor.execute(statement)
            ensure_bootstrap_recheck_column(cursor, database)
        conn.commit()
    finally:
        conn.close()


def apply_table_comments(database: Optional[str] = None) -> None:
    """给已存在的 MySQL 表补上表备注和列备注。不改数据，可重复执行。"""
    if is_sqlite():
        return
    target = database or DEFAULT_DATABASE
    if target not in (DEFAULT_DATABASE, TEST_DATABASE):
        raise ValueError(f"拒绝修改未登记的库: {target}")
    conn = connect(target)
    try:
        with conn.cursor() as cursor:
            for statement in _COMMENT_ALTERS:
                cursor.execute(statement)
        conn.commit()
    finally:
        conn.close()


def reset_business_tables(database: str) -> None:
    """清空业务表，保留小类目录。仅允许测试库。"""
    if database != TEST_DATABASE:
        raise ValueError("只能清空测试库")
    ensure_database(database)
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            if is_sqlite():
                for table in BUSINESS_TABLES:
                    cursor.execute(f"DELETE FROM {table}")
            else:
                cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
                for table in BUSINESS_TABLES:
                    cursor.execute(f"TRUNCATE TABLE {table}")
                cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
    finally:
        conn.close()


def show_create_table(database: str, table: str) -> str:
    conn = connect(database)
    try:
        with conn.cursor() as cursor:
            if is_sqlite():
                cursor.execute(
                    "SELECT sql AS create_sql FROM sqlite_master WHERE type = 'table' AND name = %s",
                    (table,),
                )
                row = cursor.fetchone()
                return row["create_sql"] if row else ""
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            row = cursor.fetchone()
            return row["Create Table"]
    finally:
        conn.close()
