import React, { useState } from "react";
import {
  Grid3X3,
  DollarSign,
  Target,
  TrendingUp,
  BarChart3,
  PieChart,
  Calculator,
  Settings,
  Info,
  Percent,
  Hash,
  Lightbulb,
  CheckCircle,
  Zap,
  Activity,
  Shield,
  AlertTriangle,
  Copy,
  Check,
  ArrowUpRight,
  ArrowDownRight,
  ListOrdered,
  LayoutGrid
} from "lucide-react";
import { formatCurrency, formatPercent, formatDate, formatTimestamp } from "@shared/utils";
import StressTestSandboxCard from "./StressTestSandboxCard";
import { ETF_CATEGORIES } from "@shared/constants/etfCategories";

const GridParametersCard = ({
  gridStrategy,
  inputParameters,
  totalCapital,
  stepMode,
  strategyRationale,
  adjustmentSuggestions,
  showDetailed = false,
  dataQuality,
}) => {
  // 挂单视图模式：'ladder' 阶梯挂单清单（推荐）| 'matrix' 方块矩阵
  const [viewMode, setViewMode] = useState("ladder");
  // 复合轨道筛选：'all' 全部合并 | 'small' 小网 | 'medium' 中网 | 'large' 大网
  const [selectedRail, setSelectedRail] = useState("all");
  // 复制反馈状态
  const [copiedKey, setCopiedKey] = useState(null);

  if (!gridStrategy) return null;

  const effectiveTotalCapital = Number(
    totalCapital ??
    inputParameters?.total_capital ??
    inputParameters?.totalCapital ??
    gridStrategy?.composite_grid?.total_capital ??
    gridStrategy?.fund_allocation?.total_capital ??
    30000
  );

  const currentStepMode = stepMode || gridStrategy?.step_mode || inputParameters?.step_mode || "atr";
  const isEdaMode = currentStepMode === "fixed_eda";

  const {
    current_price,
    price_range,
    grid_config,
    fund_allocation,
    risk_preference,
    calculation_method,
  } = gridStrategy;

  const ladderItems = gridStrategy?.composite_grid?.merged_ladder || [];
  const sellOrders = ladderItems.filter((item) => item.action === "SELL");
  const buyOrders = ladderItems.filter((item) => item.action === "BUY");
  const maxSellPrice = sellOrders.length > 0 ? Math.max(...sellOrders.map((o) => o.price)) : null;
  const minBuyPrice = buyOrders.length > 0 ? Math.min(...buyOrders.map((o) => o.price)) : null;

  const benchmarkPrice = gridStrategy?.benchmark_price ?? inputParameters?.benchmarkPrice ?? inputParameters?.benchmark_price ?? current_price;
  const isCustomBenchmark = Boolean(gridStrategy?.is_custom_benchmark || (benchmarkPrice && Math.abs(benchmarkPrice - current_price) > 0.0001));

  let sentinelTitle = "🟢 网格正常巡航中";
  let sentinelDesc = "当前标的现价处于挂单安全区间内，买卖单保持活跃待命，随时捕捉差价。";
  let sentinelBg = "bg-emerald-50/90 border-emerald-300 text-emerald-900";
  let sentinelBadge = "bg-emerald-100 text-emerald-800 border-emerald-300";

  if (maxSellPrice && current_price > maxSellPrice) {
    sentinelTitle = "🌤️ 向上突破超轨 · 获利清仓休眠";
    sentinelDesc = `当前市场现价 (¥${current_price}) 已高于最高卖单 (¥${maxSellPrice})。网格波段筹码已全部止盈出局，保持克制严禁追高，耐心等待均值回归。`;
    sentinelBg = "bg-sky-50/90 border-sky-300 text-sky-900";
    sentinelBadge = "bg-sky-100 text-sky-800 border-sky-300";
  } else if (minBuyPrice && current_price < minBuyPrice) {
    sentinelTitle = "🛡️ 深度击穿筑底 · 满仓锁仓待机";
    sentinelDesc = `当前市场现价 (¥${current_price}) 已跌穿最低买单 (¥${minBuyPrice})。全套网格已在底部完成满仓吸筹，严守纪律停止无序补仓，安心锁仓等待反弹。`;
    sentinelBg = "bg-purple-50/90 border-purple-300 text-purple-900";
    sentinelBadge = "bg-purple-100 text-purple-800 border-purple-300";
  }

  const handleCopyOrder = (key, text) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const handleCopyAllOrders = (orders, baseInfo) => {
    if (!orders || orders.length === 0) return;
    const symbolCode = inputParameters?.etfCode || "ETF";
    const lines = [
      `=== ${symbolCode} 复合网格挂单清单 ===`,
      `基准价格: ¥${Number(benchmarkPrice || current_price).toFixed(3)}${isCustomBenchmark ? " (自定义锚点)" : ""} | 底仓: ${baseInfo?.shares?.toLocaleString() || 0} 股 (约 ¥${baseInfo?.actual_capital?.toLocaleString() || 0})`,
      `----------------------------------------------------`,
    ];
    orders.forEach((o) => {
      lines.push(
        `[${o.tag || "网格"}] ${o.level_label || ""} ${o.action_label} | 价格: ¥${Number(o.price).toFixed(3)} | 委托: ${o.shares} 股 | 资金: ¥${o.amount} | 单网预估净利: +¥${o.est_profit}`
      );
    });
    lines.push(`----------------------------------------------------`);
    lines.push(`* 请在券商 APP (华宝智投/银河/同花顺等) 条件单中直接按上述价格与股数设置。`);
    navigator.clipboard.writeText(lines.join("\n"));
    setCopiedKey("copy_all_orders");
    setTimeout(() => setCopiedKey(null), 2500);
  };

  // 获取价格日期显示文本
  const getPriceDateText = () => {
    // 优先使用gridStrategy中的price_date（来自TushareClient::get_latest_price）
    const priceDate = gridStrategy?.price_date;
    if (priceDate) {
      const formattedDate = formatTimestamp(priceDate);
      if (formattedDate) {
        return `更新时间 ${formattedDate}`;
      }
    }

    // 回退到dataQuality中的latest_date
    const latestDate = dataQuality?.latest_date;
    if (latestDate) {
      const formattedDate = formatDate(latestDate);
      if (formattedDate) {
        return `更新时间 ${formattedDate}`;
      }
    }

    return "最近交易日收盘价";
  };

  return (
    <div className="space-y-6">
      {/* 资金分配策略 */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-orange-100 rounded-lg">
            <PieChart className="w-5 h-5 text-orange-600" />
          </div>
          <div>
            <h4 className="font-semibold text-gray-900">智能资金分配</h4>
            <p className="text-sm text-gray-600">底仓与网格资金的优化配置</p>
          </div>
        </div>

        {/* 资金分配概览 */}
        <div className="grid grid-cols-1 md:grid-cols-5 gap-6 mb-6">
          <div className="text-center p-4 bg-orange-50 rounded-lg">
            <div className="text-2xl font-bold text-orange-600 mb-1">
              {formatCurrency(
                inputParameters?.total_capital ||
                  inputParameters?.totalCapital ||
                  0,
              )}
            </div>
            <div className="text-sm text-orange-700 font-medium">投资资金</div>
            <div className="text-xs text-gray-600 mt-1">总投资资金量</div>
          </div>

          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600 mb-1">
              {formatCurrency(fund_allocation.base_position_amount)}
            </div>
            <div className="text-sm text-blue-700 font-medium">底仓资金</div>
            <div className="text-xs text-gray-600 mt-1">
              {formatPercent(fund_allocation.base_position_ratio)} 稳定仓位
            </div>
          </div>

          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600 mb-1">
              {formatCurrency(fund_allocation.grid_trading_amount)}
            </div>
            <div className="text-sm text-green-700 font-medium">网格资金</div>
            <div className="text-xs text-gray-600 mt-1">用于网格交易</div>
          </div>

          <div className="text-center p-4 bg-rose-50 rounded-lg">
            <div className="text-2xl font-bold text-rose-600 mb-1">
              {formatCurrency(fund_allocation.reserve_amount)}
            </div>
            <div className="text-sm text-rose-700 font-medium">预留资金</div>
            <div className="text-xs text-gray-600 mt-1">预留5%保障流动性</div>
          </div>

          <div className="text-center p-4 bg-purple-50 rounded-lg">
            <div className="text-2xl font-bold text-purple-600 mb-1">
              {formatPercent(fund_allocation.grid_fund_utilization_rate)}
            </div>
            <div className="text-sm text-purple-700 font-medium">
              网格资金利用率
            </div>
            <div className="text-xs text-gray-600 mt-1">
              最大买入时占比网格资金
            </div>
          </div>
        </div>
      </div>

      {/* 价格区间设置 */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-blue-100 rounded-lg">
            <TrendingUp className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h4 className="font-semibold text-gray-900">价格区间设置</h4>
            <p className="text-sm text-gray-600">
              {isEdaMode
                ? "基于E大原版三轨步长规划的立体防守区间"
                : "基于ATR算法动态计算的交易区间"}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600 mb-1">
              ¥{price_range.lower.toFixed(3)}
            </div>
            <div className="text-sm text-green-700 font-medium">下边界</div>
            <div className="text-xs text-gray-600 mt-1">买入区间下限</div>
          </div>

          <div className="text-center p-4 bg-gray-50 rounded-lg">
            <div className="text-2xl font-bold text-gray-900 mb-1 font-mono">
              ¥{Number(benchmarkPrice || current_price).toFixed(3)}
            </div>
            <div className="text-sm text-gray-700 font-medium">
              {isCustomBenchmark ? "基准锚点 (自定义)" : "实盘挂单锚点"}
            </div>
            <div className="text-xs text-gray-600 mt-1">
              {isCustomBenchmark ? `当前市场现价: ¥${current_price.toFixed(3)}` : getPriceDateText()}
            </div>
            <p className="text-[11px] text-gray-500 mt-2 leading-relaxed">
              这是现在要挂的价，不是五年回测铺网价。回测铺网价见下方回测卡（窗口首日开盘，可与现价不同）。挂单步长来自近端 ATR（分析周期可能被夹成 180 天），五年战绩以回测卡为准。
            </p>
          </div>

          <div className="text-center p-4 bg-red-50 rounded-lg">
            <div className="text-2xl font-bold text-red-600 mb-1">
              ¥{price_range.upper.toFixed(3)}
            </div>
            <div className="text-sm text-red-700 font-medium">上边界</div>
            <div className="text-xs text-gray-600 mt-1">卖出区间上限</div>
          </div>
        </div>

        {/* 价格区间比例可视化Bar */}
        <div className="mt-6 mb-4">
          <div className="relative h-12 rounded-lg overflow-hidden bg-gradient-to-r from-green-400 via-yellow-400 to-red-400">
            {/* 当前价格位置指示器 */}
            <div
              className="absolute top-0 bottom-0 w-0.5 shadow-lg"
              style={{
                left: `${((Number(benchmarkPrice || current_price) - price_range.lower) / (price_range.upper - price_range.lower)) * 100}%`,
              }}
            >
              <div className="absolute -top-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-white rounded-full shadow-md"></div>
              <div className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-2 h-2 bg-white rounded-full shadow-md"></div>
            </div>

            {/* 中央显示价格区间比例 */}
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="bg-white bg-opacity-50 px-4 py-1 rounded-full shadow-sm">
                <span className="text-sm text-gray-900">
                  区间跨度 {formatPercent(price_range.ratio)}
                </span>
              </div>
            </div>

            {/* 左侧标签 */}
            <div className="absolute left-2 top-1/2 transform -translate-y-1/2">
              <span className="text-xs font-medium text-white drop-shadow pl-2">
                ¥{price_range.lower.toFixed(3)}
              </span>
            </div>

            {/* 右侧标签 */}
            <div className="absolute right-2 top-1/2 transform -translate-y-1/2">
              <span className="text-xs font-medium text-white drop-shadow pr-2">
                ¥{price_range.upper.toFixed(3)}
              </span>
            </div>
          </div>

          {/* Bar下方说明 */}
          <div className="flex justify-between items-center pl-2 pr-2 mt-2 text-xs text-gray-600">
            <span>下边界</span>
            <span>基准位置</span>
            <span>上边界</span>
          </div>
        </div>
      </div>

      {/* 网格配置详情 */}
      <div className="bg-white border border-gray-200 rounded-lg p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-green-100 rounded-lg">
            <Grid3X3 className="w-5 h-5 text-green-600" />
          </div>
          <div>
            <h4 className="font-semibold text-gray-900">网格配置详情</h4>
            <p className="text-sm text-gray-600">网格数量、步长和类型设置</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Hash className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">
                网格数量
              </span>
            </div>
            <div className="text-xl font-bold text-gray-900">
              {grid_config.count}个
            </div>
            <div className="text-xs text-gray-600">
              {isEdaMode ? "复合三轨有效档位总数" : "基于ATR算法计算"}
            </div>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Settings className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">
                网格类型
              </span>
            </div>
            <div className="text-xl font-bold text-gray-900">
              {grid_config.type}
            </div>
            <div className="text-xs text-gray-600">
              {grid_config.type === "等比" ? "推荐配置" : "简单配置"}
            </div>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Activity className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">
                网格步长
              </span>
            </div>
            {/* 根据网格类型动态展示重点 */}
            {grid_config.type === "等比" ? (
              <>
                <div className="text-xl font-bold text-gray-900">
                  {formatPercent(grid_config.step_ratio)}
                </div>
                <div className="text-xs text-gray-600">
                  步长比例 · ¥{grid_config.step_size.toFixed(3)}
                </div>
              </>
            ) : (
              <>
                <div className="text-xl font-bold text-gray-900">
                  ¥{grid_config.step_size.toFixed(3)}
                </div>
                <div className="text-xs text-gray-600">
                  步长价格 · {formatPercent(grid_config.step_ratio)}
                </div>
              </>
            )}
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <Calculator className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">
                单笔数量
              </span>
            </div>
            <div className="text-xl font-bold text-gray-900">
              {fund_allocation.single_trade_quantity || 0}股
            </div>
            <div className="text-xs text-gray-600">100股整数倍</div>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <div className="flex items-center gap-2 mb-2">
              <DollarSign className="w-4 h-4 text-gray-600" />
              <span className="text-sm font-medium text-gray-700">
                预估单笔收益
              </span>
            </div>
            <div className="text-xl font-bold text-gray-900">
              {formatCurrency(fund_allocation.expected_profit_per_trade)}
            </div>
            <div className="text-xs text-gray-600">
              按网格间距和单笔数量计算
            </div>
          </div>
        </div>

        {/* 网格运行状态哨兵横幅 */}
        <div className={`p-4 rounded-xl border flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${sentinelBg} shadow-xs my-6`}>
          <div className="flex items-center gap-3">
            <span className={`text-xs font-bold px-2.5 py-1 rounded-full border ${sentinelBadge} shrink-0`}>
              {sentinelTitle}
            </span>
            <span className="text-xs font-medium">
              {sentinelDesc}
            </span>
          </div>
          {isCustomBenchmark && (
            <div className="shrink-0 flex items-center gap-1.5 text-xs font-mono font-semibold bg-white/80 px-2.5 py-1 rounded-lg border border-amber-300 text-amber-900">
              <span>⚓ 中心锚点: ¥{Number(benchmarkPrice).toFixed(3)}</span>
              <span className="text-[10px] text-gray-500 font-sans">(现价: ¥{current_price})</span>
            </div>
          )}
        </div>

        {/* T+0 交易制度提示横幅 */}
        {(() => {
          const etfCode = inputParameters?.etfCode || "";
          const isT0 = ETF_CATEGORIES.some(cat =>
            (cat.items || []).some(item => item.code === etfCode && item.tag && item.tag.includes("T+0"))
          );
          if (!isT0) return null;
          return (
            <div className="p-3 rounded-xl border flex items-center gap-3 bg-amber-50/90 border-amber-300 text-amber-900 shadow-xs mt-2">
              <span className="text-xs font-bold px-2.5 py-1 rounded-full border bg-amber-100 text-amber-800 border-amber-300 shrink-0">
                ★ T+0 跨境标的
              </span>
              <span className="text-xs font-medium">
                该标的支持日内回转交易（T+0），买入后当日即可卖出。回测引擎将自动采用 T+0 撮合模式，精确模拟日内做 T 的资金循环效率。
              </span>
            </div>
          );
        })()}

        {/* 网格价格水平与做T挂单阶梯 */}
        {(gridStrategy.composite_grid || gridStrategy.price_levels) && (
          <>
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4 mt-6">
              <div className="flex items-center gap-3">
                <div className="p-2 bg-blue-100 rounded-lg">
                  <ListOrdered className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h4 className="font-semibold text-gray-900 text-base">立体网格挂单执行阶梯</h4>
                    <span className="text-[11px] font-semibold bg-blue-50 text-blue-700 border border-blue-200 px-2 py-0.5 rounded-full">
                      大中小三轨合一
                    </span>
                    {(stepMode === "fixed_eda" || inputParameters?.stepMode === "fixed_eda") ? (
                      <span className="text-[11px] font-semibold bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full font-mono">
                        🏛️ E大原版 {
                          gridStrategy?.composite_grid?.rails?.small
                            ? `${Math.round(gridStrategy.composite_grid.rails.small.step_ratio * 100)}%/${Math.round(gridStrategy.composite_grid.rails.medium.step_ratio * 100)}%/${Math.round(gridStrategy.composite_grid.rails.large.step_ratio * 100)}%`
                            : inputParameters?.edaSteps
                            ? `${inputParameters.edaSteps.small}%/${inputParameters.edaSteps.medium}%/${inputParameters.edaSteps.large}%`
                            : "5%/15%/30%"
                        }
                      </span>
                    ) : (
                      <span className="text-[11px] font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full font-mono">
                        🌊 ATR 动态自适应 {
                          gridStrategy?.composite_grid?.rails?.small?.multiplier
                            ? `(${gridStrategy.composite_grid.rails.small.multiplier}x/${gridStrategy.composite_grid.rails.medium.multiplier}x/${gridStrategy.composite_grid.rails.large.multiplier}x)`
                            : inputParameters?.atrMultipliers
                            ? `(${inputParameters.atrMultipliers.small}x/${inputParameters.atrMultipliers.medium}x/${inputParameters.atrMultipliers.large}x)`
                            : "(0.6x/1.2x/2.5x)"
                        }
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-500">已按整百股数对齐，可直接对照在证券交易软件中设置条件单</p>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                {/* 一键复制全部条件单 */}
                <button
                  type="button"
                  onClick={() => {
                    const comp = gridStrategy.composite_grid;
                    const list = comp?.merged_ladder
                      ? comp.merged_ladder.filter((o) => selectedRail === "all" || o.rail === selectedRail)
                      : [];
                    handleCopyAllOrders(list, comp?.base_position);
                  }}
                  className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-blue-50 text-blue-700 border border-blue-200 hover:bg-blue-100 transition-colors shadow-2xs"
                  title="一键复制当前筛选的全部条件单挂单参数"
                >
                  {copiedKey === "copy_all_orders" ? (
                    <>
                      <Check className="w-3.5 h-3.5 text-green-600" />
                      <span className="text-green-700 font-bold">已复制全部条件单</span>
                    </>
                  ) : (
                    <>
                      <Copy className="w-3.5 h-3.5" />
                      <span>一键复制条件单</span>
                    </>
                  )}
                </button>

                {/* 视图切换按钮 */}
                <div className="flex items-center bg-gray-100 p-1 rounded-lg self-start sm:self-auto text-xs">
                  <button
                    type="button"
                    onClick={() => setViewMode("ladder")}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                      viewMode === "ladder"
                        ? "bg-white text-blue-700 shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <ListOrdered className="w-3.5 h-3.5" />
                    阶梯挂单表
                  </button>
                  <button
                    type="button"
                    onClick={() => setViewMode("matrix")}
                    className={`flex items-center gap-1.5 px-3 py-1 rounded-md font-medium transition-all ${
                      viewMode === "matrix"
                        ? "bg-white text-blue-700 shadow-xs"
                        : "text-gray-600 hover:text-gray-900"
                    }`}
                  >
                    <LayoutGrid className="w-3.5 h-3.5" />
                    矩阵方块
                  </button>
                </div>
              </div>
            </div>

            {/* 大中小三轨概览胶囊卡 */}
            {gridStrategy.composite_grid?.rails && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                {/* 🟢 小网 */}
                <div className="p-3.5 rounded-xl border border-emerald-200 bg-emerald-50/70 shadow-2xs flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-emerald-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500"></span>
                      {gridStrategy.composite_grid.rails.small?.name}
                    </span>
                    <span className="text-[10px] font-bold text-emerald-800 bg-emerald-100 px-2 py-0.5 rounded-full border border-emerald-300">
                      流动金 20%
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-center font-sans text-xs">
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-emerald-100">
                      <div className="text-[10px] text-gray-500">分配金额</div>
                      <div className="font-bold text-gray-900">
                        ¥{gridStrategy.composite_grid.rails.small?.capital?.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-emerald-100">
                      <div className="text-[10px] text-gray-500">步长比例</div>
                      <div className="font-bold text-emerald-700">
                        {(gridStrategy.composite_grid.rails.small?.step_ratio * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-emerald-100">
                      <div className="text-[10px] text-gray-500">单边档位</div>
                      <div className="font-bold text-gray-900">
                        {gridStrategy.composite_grid.rails.small?.levels_count} 档
                      </div>
                    </div>
                  </div>
                </div>

                {/* 🔵 中网 */}
                <div className="p-3.5 rounded-xl border border-blue-200 bg-blue-50/70 shadow-2xs flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-blue-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-blue-500"></span>
                      {gridStrategy.composite_grid.rails.medium?.name}
                    </span>
                    <span className="text-[10px] font-bold text-blue-800 bg-blue-100 px-2 py-0.5 rounded-full border border-blue-300">
                      流动金 35%
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-center font-sans text-xs">
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-blue-100">
                      <div className="text-[10px] text-gray-500">分配金额</div>
                      <div className="font-bold text-gray-900">
                        ¥{gridStrategy.composite_grid.rails.medium?.capital?.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-blue-100">
                      <div className="text-[10px] text-gray-500">步长比例</div>
                      <div className="font-bold text-blue-700">
                        {(gridStrategy.composite_grid.rails.medium?.step_ratio * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-blue-100">
                      <div className="text-[10px] text-gray-500">单边档位</div>
                      <div className="font-bold text-gray-900">
                        {gridStrategy.composite_grid.rails.medium?.levels_count} 档
                      </div>
                    </div>
                  </div>
                </div>

                {/* 🟣 大网 */}
                <div className="p-3.5 rounded-xl border border-purple-200 bg-purple-50/70 shadow-2xs flex flex-col justify-between">
                  <div className="flex items-center justify-between mb-2">
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-purple-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-purple-500"></span>
                      {gridStrategy.composite_grid.rails.large?.name}
                    </span>
                    <span className="text-[10px] font-bold text-purple-800 bg-purple-100 px-2 py-0.5 rounded-full border border-purple-300">
                      流动金 45%
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-1 text-center font-sans text-xs">
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-purple-100">
                      <div className="text-[10px] text-gray-500">分配金额</div>
                      <div className="font-bold text-gray-900">
                        ¥{gridStrategy.composite_grid.rails.large?.capital?.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-purple-100">
                      <div className="text-[10px] text-gray-500">步长比例</div>
                      <div className="font-bold text-purple-700">
                        {(gridStrategy.composite_grid.rails.large?.step_ratio * 100).toFixed(2)}%
                      </div>
                    </div>
                    <div className="bg-white/70 py-1.5 px-1 rounded-lg border border-purple-100">
                      <div className="text-[10px] text-gray-500">单边档位</div>
                      <div className="font-bold text-gray-900">
                        {gridStrategy.composite_grid.rails.large?.levels_count} 档
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* 分轨快速筛选标签 */}
            {gridStrategy.composite_grid?.merged_ladder && (
              <div className="flex flex-wrap items-center gap-1.5 mb-3">
                <span className="text-xs text-gray-500 mr-1 font-medium">轨道筛选:</span>
                <button
                  type="button"
                  onClick={() => setSelectedRail("all")}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    selectedRail === "all"
                      ? "bg-gray-900 text-white shadow-xs font-bold"
                      : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                  }`}
                >
                  ★ 全部多轨合并 ({gridStrategy.composite_grid.merged_ladder.length} 档)
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedRail("small")}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    selectedRail === "small"
                      ? "bg-emerald-600 text-white shadow-xs font-bold"
                      : "bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200"
                  }`}
                >
                  🟢 仅看小网
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedRail("medium")}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    selectedRail === "medium"
                      ? "bg-blue-600 text-white shadow-xs font-bold"
                      : "bg-blue-50 text-blue-700 hover:bg-blue-100 border border-blue-200"
                  }`}
                >
                  🔵 仅看中网
                </button>
                <button
                  type="button"
                  onClick={() => setSelectedRail("large")}
                  className={`px-3 py-1 rounded-lg text-xs font-medium transition-all ${
                    selectedRail === "large"
                      ? "bg-purple-600 text-white shadow-xs font-bold"
                      : "bg-purple-50 text-purple-700 hover:bg-purple-100 border border-purple-200"
                  }`}
                >
                  🟣 仅看大网
                </button>
              </div>
            )}

            {/* 模式一：纵向订单簿阶梯清单 */}
            {viewMode === "ladder" && (
              <div className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-xs">
                <div className="overflow-x-auto max-h-96">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead className="bg-gray-50 text-gray-600 sticky top-0 z-10 border-b border-gray-200">
                      <tr>
                        <th className="py-2.5 px-3 font-semibold">档位</th>
                        <th className="py-2.5 px-3 font-semibold">触发价格</th>
                        <th className="py-2.5 px-3 font-semibold">轨道</th>
                        <th className="py-2.5 px-3 font-semibold">交易动作</th>
                        <th className="py-2.5 px-3 font-semibold">委托数量</th>
                        <th className="py-2.5 px-3 font-semibold">资金占用</th>
                        <th className="py-2.5 px-3 font-semibold">单网预估净利</th>
                        <th className="py-2.5 px-3 font-semibold">资金深度</th>
                        <th className="py-2.5 px-3 font-semibold text-center">快捷操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 font-mono">
                      {(() => {
                        const comp = gridStrategy.composite_grid;
                        const symbolCode = inputParameters?.etfCode || "";

                        // 如果有复合网格数据，使用复合网格阶梯
                        if (comp?.merged_ladder) {
                          const baseInfo = comp.base_position || {};
                          const allOrders = comp.merged_ladder;
                          const filteredOrders = allOrders.filter(
                            (o) => selectedRail === "all" || o.rail === selectedRail
                          );

                          const sellOrders = filteredOrders.filter((o) => o.action === "SELL");
                          const buyOrders = filteredOrders.filter((o) => o.action === "BUY");

                          const rows = [];

                          // 1. 卖出档位 (由高到低)
                          sellOrders.forEach((o) => {
                            const copyText = `${symbolCode} 卖出 价格:${o.price.toFixed(3)} 数量:${o.shares}股`;
                            const rowKey = o.id;

                            // 轨道徽章样式
                            const railBadge =
                              o.rail === "large" ? (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200 font-sans">
                                  🟣 大网
                                </span>
                              ) : o.rail === "medium" ? (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200 font-sans">
                                  🔵 中网
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 font-sans">
                                  🟢 小网
                                </span>
                              );

                            // 深度条宽度
                            const depthWidth = Math.min(100, Math.max(15, o.depth_ratio || 25));

                            rows.push(
                              <tr key={rowKey} className="hover:bg-amber-50/50 transition-colors">
                                <td className="py-2 px-3 font-semibold text-amber-700">
                                  {o.level_label}
                                </td>
                                <td className="py-2 px-3 text-sm font-bold text-gray-900">
                                  ¥{o.price.toFixed(3)}
                                </td>
                                <td className="py-2 px-3">{railBadge}</td>
                                <td className="py-2 px-3">
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-800 font-sans">
                                    <ArrowUpRight className="w-3 h-3" /> 卖出做T
                                  </span>
                                </td>
                                <td className="py-2 px-3 text-gray-800 font-bold">
                                  {o.shares.toLocaleString()} 股
                                </td>
                                <td className="py-2 px-3 text-gray-600">
                                  ¥{o.amount.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                                </td>
                                <td className="py-2 px-3 text-red-600 font-semibold font-sans">
                                  +¥{o.est_profit.toFixed(1)}
                                </td>
                                <td className="py-2 px-3">
                                  <div className="flex items-center gap-1.5">
                                    <div className="w-14 bg-gray-100 h-1.5 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full rounded-full ${
                                          o.rail === "large"
                                            ? "bg-purple-500"
                                            : o.rail === "medium"
                                            ? "bg-blue-500"
                                            : "bg-emerald-500"
                                        }`}
                                        style={{ width: `${depthWidth}%` }}
                                      ></div>
                                    </div>
                                    <span className="text-[10px] text-gray-500 font-sans">{o.depth_ratio}%</span>
                                  </div>
                                </td>
                                <td className="py-2 px-3 text-center">
                                  <button
                                    type="button"
                                    onClick={() => handleCopyOrder(rowKey, copyText)}
                                    className="inline-flex items-center gap-1 text-[11px] font-sans px-2 py-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                                    title="复制挂单参数"
                                  >
                                    {copiedKey === rowKey ? (
                                      <span className="text-green-600 flex items-center gap-0.5">
                                        <Check className="w-3 h-3" /> 已复制
                                      </span>
                                    ) : (
                                      <span className="flex items-center gap-0.5">
                                        <Copy className="w-3 h-3" /> 复制
                                      </span>
                                    )}
                                  </button>
                                </td>
                              </tr>
                            );
                          });

                          // 2. 基准价格锚点行
                          rows.push(
                            <tr key="current_anchor" className="bg-blue-50/90 border-y-2 border-blue-300 font-sans">
                              <td className="py-2.5 px-3 font-bold text-blue-900 flex items-center gap-1.5">
                                <span className="inline-block w-2 h-2 rounded-full bg-blue-600 animate-pulse"></span>
                                {isCustomBenchmark ? "【基准锚点】" : "【实盘挂单】"}
                              </td>
                              <td className="py-2.5 px-3 text-base font-bold text-blue-900 font-mono">
                                ¥{Number(benchmarkPrice || current_price).toFixed(3)}
                              </td>
                              <td className="py-2.5 px-3">
                                <span className="text-[10px] font-bold text-blue-800 bg-blue-200/80 px-1.5 py-0.5 rounded">
                                  {isCustomBenchmark ? "自定义锚点" : "基准轴心"}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 font-medium text-blue-800 text-xs">
                                {isCustomBenchmark ? `现价 ¥${current_price.toFixed(3)}` : "现价持仓水温"}
                              </td>
                              <td className="py-2.5 px-3 font-bold text-blue-900 font-mono">
                                底仓 {(baseInfo.shares || 0).toLocaleString()} 股
                              </td>
                              <td className="py-2.5 px-3 font-bold text-blue-900 font-mono">
                                底仓 ¥{(baseInfo.actual_capital || 0).toLocaleString(undefined, { maximumFractionDigits: 1 })}
                              </td>
                              <td className="py-2.5 px-3 text-blue-600 font-medium">
                                50% 底仓轮动
                              </td>
                              <td className="py-2.5 px-3">
                                <span className="text-[10px] text-blue-700 font-bold">50% 底仓池</span>
                              </td>
                              <td className="py-2.5 px-3 text-center text-blue-700 text-xs font-semibold">
                                轴心基准
                              </td>
                            </tr>
                          );

                          // 3. 买入档位 (由高到低)
                          buyOrders.forEach((o) => {
                            const copyText = `${symbolCode} 买入 价格:${o.price.toFixed(3)} 数量:${o.shares}股`;
                            const rowKey = o.id;

                            const railBadge =
                              o.rail === "large" ? (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-purple-100 text-purple-800 border border-purple-200 font-sans">
                                  🟣 大网
                                </span>
                              ) : o.rail === "medium" ? (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-blue-100 text-blue-800 border border-blue-200 font-sans">
                                  🔵 中网
                                </span>
                              ) : (
                                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800 border border-emerald-200 font-sans">
                                  🟢 小网
                                </span>
                              );

                            const depthWidth = Math.min(100, Math.max(15, o.depth_ratio || 25));

                            rows.push(
                              <tr key={rowKey} className="hover:bg-emerald-50/50 transition-colors">
                                <td className="py-2 px-3 font-semibold text-emerald-700">
                                  {o.level_label}
                                </td>
                                <td className="py-2 px-3 text-sm font-bold text-gray-900">
                                  ¥{o.price.toFixed(3)}
                                </td>
                                <td className="py-2 px-3">{railBadge}</td>
                                <td className="py-2 px-3">
                                  <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-800 font-sans">
                                    <ArrowDownRight className="w-3 h-3" /> 买入低吸
                                  </span>
                                </td>
                                <td className="py-2 px-3 text-gray-800 font-bold">
                                  {o.shares.toLocaleString()} 股
                                </td>
                                <td className="py-2 px-3 text-gray-600">
                                  ¥{o.amount.toLocaleString(undefined, { maximumFractionDigits: 1 })}
                                </td>
                                <td className="py-2 px-3 text-emerald-600 font-semibold font-sans">
                                  <div>+¥{o.est_profit.toFixed(1)}</div>
                                  {inputParameters?.reinvestMode === "pool_shares" && (
                                    <div className="text-[9px] text-emerald-700 font-normal">
                                      → 汇入留股池
                                    </div>
                                  )}
                                </td>
                                <td className="py-2 px-3">
                                  <div className="flex items-center gap-1.5">
                                    <div className="w-14 bg-gray-100 h-1.5 rounded-full overflow-hidden">
                                      <div
                                        className={`h-full rounded-full ${
                                          o.rail === "large"
                                            ? "bg-purple-500"
                                            : o.rail === "medium"
                                            ? "bg-blue-500"
                                            : "bg-emerald-500"
                                        }`}
                                        style={{ width: `${depthWidth}%` }}
                                      ></div>
                                    </div>
                                    <span className="text-[10px] text-gray-500 font-sans">{o.depth_ratio}%</span>
                                  </div>
                                </td>
                                <td className="py-2 px-3 text-center">
                                  <button
                                    type="button"
                                    onClick={() => handleCopyOrder(rowKey, copyText)}
                                    className="inline-flex items-center gap-1 text-[11px] font-sans px-2 py-0.5 rounded border border-gray-200 text-gray-600 hover:bg-gray-100 hover:text-gray-900 transition-colors"
                                    title="复制挂单参数"
                                  >
                                    {copiedKey === rowKey ? (
                                      <span className="text-green-600 flex items-center gap-0.5">
                                        <Check className="w-3 h-3" /> 已复制
                                      </span>
                                    ) : (
                                      <span className="flex items-center gap-0.5">
                                        <Copy className="w-3 h-3" /> 复制
                                      </span>
                                    )}
                                  </button>
                                </td>
                              </tr>
                            );
                          });

                          return rows;
                        }

                        // 回退旧版单一网格
                        const priceLevels = gridStrategy.price_levels || [];
                        const singleQty = fund_allocation?.single_trade_quantity || 1000;
                        const expectedProfit = fund_allocation?.expected_profit_per_trade || (singleQty * current_price * 0.03);
                        const baseShares = Math.round((fund_allocation?.base_position_amount || 50000) / current_price / 100) * 100;
                        const baseAmount = baseShares * current_price;

                        const sellLevels = priceLevels.filter((p) => p > current_price).sort((a, b) => b - a);
                        const buyLevels = priceLevels.filter((p) => p < current_price).sort((a, b) => b - a);
                        const rows = [];

                        sellLevels.forEach((price, idx) => {
                          const levelNum = sellLevels.length - idx;
                          const fundAmount = singleQty * price;
                          const copyText = `${symbolCode} 卖出 价格:${price.toFixed(3)} 数量:${singleQty}股`;
                          const rowKey = `sell_${levelNum}`;
                          rows.push(
                            <tr key={rowKey} className="hover:bg-amber-50/50 transition-colors">
                              <td className="py-2.5 px-4 font-semibold text-amber-700">卖出 第+{levelNum}档</td>
                              <td className="py-2.5 px-4 text-sm font-bold text-gray-900">¥{price.toFixed(3)}</td>
                              <td className="py-2.5 px-4"><span className="text-gray-500">基础</span></td>
                              <td className="py-2.5 px-4">
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-amber-100 text-amber-800 font-sans">
                                  <ArrowUpRight className="w-3 h-3" /> 卖出做T
                                </span>
                              </td>
                              <td className="py-2.5 px-4 text-gray-800">{singleQty.toLocaleString()} 股</td>
                              <td className="py-2.5 px-4 text-gray-600">¥{fundAmount.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                              <td className="py-2.5 px-4 text-red-600 font-semibold font-sans">+¥{expectedProfit.toFixed(1)}</td>
                              <td className="py-2.5 px-4"><span className="text-[10px] text-gray-400">-</span></td>
                              <td className="py-2.5 px-4 text-center">
                                <button
                                  type="button"
                                  onClick={() => handleCopyOrder(rowKey, copyText)}
                                  className="inline-flex items-center gap-1 text-[11px] font-sans px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100"
                                >
                                  {copiedKey === rowKey ? <span className="text-green-600 flex items-center"><Check className="w-3 h-3" /> 已复制</span> : <span className="flex items-center"><Copy className="w-3 h-3" /> 复制</span>}
                                </button>
                              </td>
                            </tr>
                          );
                        });

                        rows.push(
                          <tr key="current_anchor_legacy" className="bg-blue-50/90 border-y-2 border-blue-300 font-sans">
                            <td className="py-3 px-4 font-bold text-blue-900 flex items-center gap-1.5">【现价锚点】</td>
                            <td className="py-3 px-4 text-base font-bold text-blue-900 font-mono">¥{current_price.toFixed(3)}</td>
                            <td className="py-3 px-4"><span className="text-xs text-blue-800">基准</span></td>
                            <td className="py-3 px-4 font-medium text-blue-800">持仓观察</td>
                            <td className="py-3 px-4 font-bold text-blue-900 font-mono">底仓 {baseShares.toLocaleString()} 股</td>
                            <td className="py-3 px-4 font-bold text-blue-900 font-mono">底仓 ¥{baseAmount.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                            <td className="py-3 px-4 text-blue-600 font-medium">T+1 轮动</td>
                            <td className="py-3 px-4 text-blue-700 text-xs">50% 底仓</td>
                            <td className="py-3 px-4 text-center text-blue-700 text-xs">基准</td>
                          </tr>
                        );

                        buyLevels.forEach((price, idx) => {
                          const levelNum = idx + 1;
                          const fundAmount = singleQty * price;
                          const copyText = `${symbolCode} 买入 价格:${price.toFixed(3)} 数量:${singleQty}股`;
                          const rowKey = `buy_${levelNum}`;
                          rows.push(
                            <tr key={rowKey} className="hover:bg-emerald-50/50 transition-colors">
                              <td className="py-2.5 px-4 font-semibold text-emerald-700">买入 第-{levelNum}档</td>
                              <td className="py-2.5 px-4 text-sm font-bold text-gray-900">¥{price.toFixed(3)}</td>
                              <td className="py-2.5 px-4"><span className="text-gray-500">基础</span></td>
                              <td className="py-2.5 px-4">
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-100 text-emerald-800 font-sans">
                                  <ArrowDownRight className="w-3 h-3" /> 买入建仓
                                </span>
                              </td>
                              <td className="py-2.5 px-4 text-gray-800">{singleQty.toLocaleString()} 股</td>
                              <td className="py-2.5 px-4 text-gray-600">¥{fundAmount.toLocaleString(undefined, { maximumFractionDigits: 1 })}</td>
                              <td className="py-2.5 px-4 text-gray-500 font-sans">等待低吸</td>
                              <td className="py-2.5 px-4"><span className="text-[10px] text-gray-400">-</span></td>
                              <td className="py-2.5 px-4 text-center">
                                <button
                                  type="button"
                                  onClick={() => handleCopyOrder(rowKey, copyText)}
                                  className="inline-flex items-center gap-1 text-[11px] font-sans px-2.5 py-1 rounded border border-gray-200 text-gray-600 hover:bg-gray-100"
                                >
                                  {copiedKey === rowKey ? <span className="text-green-600 flex items-center"><Check className="w-3 h-3" /> 已复制</span> : <span className="flex items-center"><Copy className="w-3 h-3" /> 复制</span>}
                                </button>
                              </td>
                            </tr>
                          );
                        });

                        return rows;
                      })()}
                    </tbody>
                  </table>
                </div>
                <div className="p-3 bg-gray-50 border-t border-gray-200 text-xs text-gray-500 flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <span>💡 提示：所有挂单股数已自动按整百股数（100股整数倍）对齐，点击单笔“复制”或右上角“一键复制条件单”可快速在券商 APP 设置</span>
                  <span className="font-semibold text-gray-700">
                    当前视图: {gridStrategy.composite_grid?.merged_ladder?.filter((o) => selectedRail === "all" || o.rail === selectedRail).length || gridStrategy.price_levels?.length || 0} 档
                  </span>
                </div>
              </div>
            )}

            {/* 模式二：方块矩阵紧凑视图 */}
            {viewMode === "matrix" && (
              <div className="max-h-64 overflow-y-auto">
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-2">
                  {gridStrategy.price_levels.map((price, index) => (
                    <div
                      key={index}
                      className={`p-2 text-center rounded text-sm ${
                        price < current_price
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : price > current_price
                            ? "bg-amber-50 text-amber-700 border border-amber-200"
                            : "bg-blue-50 text-blue-700 border border-blue-200"
                      }`}
                    >
                      <div className="font-medium font-mono">¥{price.toFixed(3)}</div>
                      <div className="text-xs opacity-75">
                        {price < current_price
                          ? "买入"
                          : price > current_price
                            ? "卖出"
                            : "基准"}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}

        {/* 方案 A：极限行情压力测试沙盘（原位挂载于挂单阶梯表下方） */}
        {gridStrategy.composite_grid && (
          <StressTestSandboxCard
            compositeGrid={gridStrategy.composite_grid}
            totalCapital={effectiveTotalCapital}
            currentPrice={Number(benchmarkPrice || current_price)}
          />
        )}
      </div>

      {/* 策略分析依据 */}
      {strategyRationale && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-100 rounded-lg">
              <Lightbulb className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h4 className="font-semibold text-gray-900">策略分析依据</h4>
              <p className="text-sm text-gray-600">
                参数选择逻辑和算法优势说明
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* ATR算法优势 */}
            <div>
              <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-blue-600" />
                ATR算法优势
              </h5>
              <ul className="space-y-2 text-sm text-gray-700">
                {strategyRationale.atr_advantages?.map((advantage, index) => (
                  <li
                    key={index}
                    className="flex items-start gap-2 bg-gray-50 rounded p-2"
                  >
                    <CheckCircle className="w-4 h-4 text-green-600 mt-0.5 flex-shrink-0" />
                    {advantage}
                  </li>
                ))}
              </ul>
            </div>

            {/* 参数选择逻辑 */}
            <div>
              <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                <Info className="w-4 h-4 text-purple-600" />
                参数选择逻辑
              </h5>
              <div className="space-y-2 text-sm text-gray-700">
                {strategyRationale.parameter_logic &&
                  Object.entries(strategyRationale.parameter_logic).map(
                    ([key, value]) => (
                      <div key={key} className="p-2 bg-gray-50 rounded">
                        <span className="font-medium capitalize">
                          {key.replace("_", " ")}:{" "}
                        </span>
                        {value}
                      </div>
                    ),
                  )}
              </div>
            </div>
          </div>

          {/* 市场环境分析 */}
          {strategyRationale.market_environment && (
            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
              <h5 className="font-medium text-blue-900 mb-2">市场环境分析</h5>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <span className="text-blue-700 font-medium">波动率: </span>
                  <span className="text-blue-800">
                    {strategyRationale.market_environment.volatility}
                  </span>
                </div>
                <div>
                  <span className="text-blue-700 font-medium">趋势特征: </span>
                  <span className="text-blue-800">
                    {strategyRationale.market_environment.trend_characteristic}
                  </span>
                </div>
                <div>
                  <span className="text-blue-700 font-medium">流动性: </span>
                  <span className="text-blue-800">
                    {strategyRationale.market_environment.liquidity}
                  </span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* 调整建议 */}
      {adjustmentSuggestions && (
        <div className="bg-white border border-gray-200 rounded-lg p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-yellow-100 rounded-lg">
              <Zap className="w-5 h-5 text-yellow-600" />
            </div>
            <div>
              <h4 className="font-semibold text-gray-900">策略调整建议</h4>
              <p className="text-sm text-gray-600">市场环境变化时的优化方案</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {Object.entries(adjustmentSuggestions).map(
              ([category, suggestions]) => {
                if (!suggestions || suggestions.length === 0) return null;

                const categoryNames = {
                  market_environment_changes: "市场环境应对",
                  parameter_optimization: "参数优化",
                  risk_control: "风险控制",
                  profit_enhancement: "收益增强",
                };

                const categoryIcons = {
                  market_environment_changes: <Activity className="w-4 h-4" />,
                  parameter_optimization: <Target className="w-4 h-4" />,
                  risk_control: <Shield className="w-4 h-4" />,
                  profit_enhancement: <TrendingUp className="w-4 h-4" />,
                };

                return (
                  <div key={category}>
                    <h5 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
                      {categoryIcons[category]}
                      {categoryNames[category]}
                    </h5>
                    <ul className="space-y-2 text-sm text-gray-700">
                      {suggestions.map((suggestion, index) => (
                        <li key={index} className="flex items-start gap-2">
                          <AlertTriangle className="w-4 h-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                          {suggestion}
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              },
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default GridParametersCard;
