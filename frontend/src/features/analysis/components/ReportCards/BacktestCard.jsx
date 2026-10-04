import React, { useState, useEffect, useMemo } from "react";
import {
  TrendingUp,
  Award,
  ShieldAlert,
  Activity,
  Calendar,
  CheckCircle2,
  Clock,
  ArrowUpRight,
  ArrowDownRight,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Sparkles,
  Sliders,
  PiggyBank,
  Download,
  Filter,
  Layers,
  Target,
  Info,
  Coins,
  Scale,
  ShieldCheck,
  HelpCircle,
  X,
} from "lucide-react";
import CrisisReplayModal from "./CrisisReplayModal";
import { isAbortError, runBacktest } from "@shared/services/api";

function calculateProfitAttribution(summary, profitPool) {
  if (!summary) return null;
  const initialCapital = Number(summary.initial_capital) || 0;
  const finalEquity = Number(summary.final_equity) || 0;
  const totalProfit = Number((finalEquity - initialCapital).toFixed(2));

  const pool = profitPool || summary.profit_pool;
  const gridProfit = Number((summary.grid_cash_profit ?? pool?.total_profit_accumulated ?? 0).toFixed(2));
  const poolRemainder = Number((pool?.profit_pool_remainder ?? 0).toFixed(2));
  const costSpent = Number(Math.max(0, gridProfit - poolRemainder).toFixed(2));
  const freeSharesValue = Number((pool?.free_shares_value ?? 0).toFixed(2));
  const freeSharesGain = Number((freeSharesValue - costSpent).toFixed(2));

  // 底仓高抛变现溢价及未卖完底仓余值 (严密平账: totalProfit = gridProfit + freeSharesGain + basePositionGain)
  const basePositionGain = Number((totalProfit - gridProfit - freeSharesGain).toFixed(2));

  // 比例条安全百分比计算 (防止除以 0、负数宽度以及确保三者相加为 100%)
  let gridPct = 0;
  let freeSharesPct = 0;
  let basePct = 0;

  if (totalProfit > 0) {
    const posTotal = Math.max(0, gridProfit) + Math.max(0, freeSharesGain) + Math.max(0, basePositionGain);
    if (posTotal > 0) {
      gridPct = Number(((Math.max(0, gridProfit) / posTotal) * 100).toFixed(1));
      freeSharesPct = Number(((Math.max(0, freeSharesGain) / posTotal) * 100).toFixed(1));
      basePct = Number(Math.max(0, 100 - gridPct - freeSharesPct).toFixed(1));
    }
  }

  return {
    initialCapital,
    finalEquity,
    totalProfit,
    gridProfit,
    costSpent,
    poolRemainder,
    freeShares: pool?.free_shares || 0,
    freeSharesValue,
    freeSharesGain,
    basePositionGain,
    gridPct,
    freeSharesPct,
    basePct,
  };
}

const BacktestCard = ({
  etfCode,
  totalCapital = 30000,
  initialDays = 180,
  reinvestMode = "pool_shares",
  scalingRatio = 0.1,
  stepMode = "atr",
  edaStepRatios = null,
  edaSteps = null,
  atrMultipliers = null,
  onHistoryMeta,
}) => {
  const safeTotalCapital = Number(totalCapital || 30000);
  const [backtestDays, setBacktestDays] = useState(initialDays);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [backtestData, setBacktestData] = useState(null);
  const [showAllTrades, setShowAllTrades] = useState(false);
  const [selectedRail, setSelectedRail] = useState("all");
  const [pageSize, setPageSize] = useState(20);
  const [currentPage, setCurrentPage] = useState(1);
  const [anchorMode, setAnchorMode] = useState("auto"); // "auto" | "custom"
  const [customBasePrice, setCustomBasePrice] = useState("");
  const [hoverIndex, setHoverIndex] = useState(null);
  const [selectedCrisis, setSelectedCrisis] = useState(null);
  const [isCrisisModalOpen, setIsCrisisModalOpen] = useState(false);
  const [showSortinoPopover, setShowSortinoPopover] = useState(false);

  // 加载回测数据
  const fetchBacktest = async (days, forcedCustomPrice = null, signal) => {
    if (!etfCode) return;
    setLoading(true);
    setError(null);
    try {
      const activeCustomPrice = forcedCustomPrice !== null 
        ? forcedCustomPrice 
        : (anchorMode === "custom" && customBasePrice ? Number(customBasePrice) : null);

      const res = await runBacktest({
        etfCode,
        totalCapital: safeTotalCapital,
        backtestDays: days,
        reinvestMode,
        scalingRatio,
        stepMode,
        edaStepRatios,
        edaSteps,
        atrMultipliers,
        customBasePrice: activeCustomPrice,
      }, { signal });
      if (signal?.aborted) return;
      if (res?.success && res.data) {
        setBacktestData(res.data);
        const meta = res.data.summary?.history_meta || res.data.history_meta || null;
        if (onHistoryMeta) onHistoryMeta(meta);
      } else {
        setError(res?.error || "回测数据获取失败");
      }
    } catch (err) {
      if (isAbortError(err) || signal?.aborted) return;
      setError(err?.message || "回测请求异常，请稍后重试");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  useEffect(() => {
    if (!etfCode) return undefined;
    const controller = new AbortController();
    fetchBacktest(backtestDays, null, controller.signal);
    return () => controller.abort();
  }, [etfCode, safeTotalCapital, backtestDays, reinvestMode, scalingRatio, stepMode, edaStepRatios, edaSteps, atrMultipliers, anchorMode]);

  const summary = backtestData?.summary;
  const profitPool = backtestData?.profit_pool || summary?.profit_pool;
  const railAttribution = backtestData?.rail_attribution || [];
  const equityCurve = backtestData?.equity_curve || [];
  const allTrades = backtestData?.total_trades_all || backtestData?.recent_trades || [];

  const profitAttribution = useMemo(() => {
    return calculateProfitAttribution(summary, profitPool);
  }, [summary, profitPool]);

  // 分轨过滤与时间倒序排序 (最新成交优先置顶)
  const filteredTrades = useMemo(() => {
    const list = selectedRail === "all" ? allTrades : allTrades.filter((t) => t.rail === selectedRail);
    return [...list].sort((a, b) => (b.trade_time || "").localeCompare(a.trade_time || ""));
  }, [allTrades, selectedRail]);

  // 分轨专项统计
  const railStatsSummary = useMemo(() => {
    const totalCount = filteredTrades.length;
    const buyCount = filteredTrades.filter((t) => t.action === "BUY").length;
    const sellCount = filteredTrades.filter((t) => t.action === "SELL").length;
    const totalProfit = filteredTrades.reduce((acc, t) => acc + (Number(t.profit) || 0), 0);
    const avgProfitPerSell = sellCount > 0 ? (totalProfit / sellCount).toFixed(2) : "0.00";
    return {
      totalCount,
      buyCount,
      sellCount,
      totalProfit: totalProfit.toFixed(2),
      avgProfitPerSell,
    };
  }, [filteredTrades]);

  // 分页计算
  const totalPages = Math.max(1, Math.ceil(filteredTrades.length / pageSize));
  const paginatedTrades = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filteredTrades.slice(start, start + pageSize);
  }, [filteredTrades, currentPage, pageSize]);

  // 轨道切换时重置当前页码
  useEffect(() => {
    setCurrentPage(1);
  }, [selectedRail, backtestDays]);

  // 导出 CSV
  const handleExportCsv = () => {
    if (!filteredTrades.length) return;
    const headers = [
      "成交时间",
      "动作",
      "轨道",
      "成交价格(元)",
      "成交股数",
      "成交金额(元)",
      "持有天数",
      "对冲进价(元)",
      "单笔收益率",
      "手续费(元)",
      "扣费净利(元)",
    ];
    const rows = filteredTrades.map((t) => [
      t.trade_time,
      t.action_label || (t.action === "SELL" ? "卖出" : "买入"),
      t.rail_name || t.rail,
      Number(t.price).toFixed(3),
      t.shares,
      t.amount,
      t.action === "SELL" ? (t.holding_days != null ? `${t.holding_days}天` : "0天") : "-",
      t.action === "SELL" ? (t.entry_price != null ? Number(t.entry_price).toFixed(3) : "-") : "-",
      t.action === "SELL" ? (t.trade_return_pct != null ? `${t.trade_return_pct}%` : "-") : "-",
      t.fee,
      t.action === "SELL" ? t.profit : "0.00",
    ]);
    const csvContent = "\uFEFF" + [headers.join(","), ...rows.map((r) => r.join(","))].join("\n");
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.setAttribute("href", url);
    link.setAttribute("download", `ETF_${etfCode}_回测流水_${selectedRail}_${backtestDays}天.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  // 计算 SVG 净值与水下深度图表坐标点
  const chartPoints = useMemo(() => {
    if (!equityCurve || equityCurve.length < 2) return null;

    const width = 800;
    const height = 220;
    const uwHeight = 110;
    const padding = { top: 20, right: 30, bottom: 25, left: 55 };

    const innerWidth = width - padding.left - padding.right;
    const innerHeight = height - padding.top - padding.bottom;
    const uwInnerHeight = uwHeight - padding.top - padding.bottom;

    // 1. 获取净值极值
    let minNav = 0.8;
    let maxNav = 1.2;

    // 2. 获取水下深度极值 (负百分比，例如 -26.56%)
    let minDd = 0.0;

    equityCurve.forEach((d) => {
      if (d.strategy_nav < minNav) minNav = d.strategy_nav;
      if (d.strategy_nav > maxNav) maxNav = d.strategy_nav;
      if (d.benchmark_nav < minNav) minNav = d.benchmark_nav;
      if (d.benchmark_nav > maxNav) maxNav = d.benchmark_nav;

      const sDd = Number(d.strategy_dd_pct ?? 0);
      const bDd = Number(d.benchmark_dd_pct ?? 0);
      if (sDd < minDd) minDd = sDd;
      if (bDd < minDd) minDd = bDd;
    });

    minNav = Math.floor((minNav - 0.05) * 10) / 10;
    maxNav = Math.ceil((maxNav + 0.05) * 10) / 10;
    const navRange = maxNav - minNav || 1;

    // 水下深度 Y 轴范围：从 0% 向下到 minDd
    const floorDd = Math.floor((minDd - 2) / 5) * 5;
    const ddRange = Math.abs(floorDd) || 10;

    const getX = (index) => padding.left + (index / (equityCurve.length - 1)) * innerWidth;
    const getY = (nav) => padding.top + innerHeight - ((nav - minNav) / navRange) * innerHeight;
    const getUwY = (ddPct) => padding.top + (Math.abs(Number(ddPct) || 0) / ddRange) * uwInnerHeight;

    const strategyPoints = equityCurve.map((d, i) => `${getX(i)},${getY(d.strategy_nav)}`).join(" ");
    const benchmarkPoints = equityCurve.map((d, i) => `${getX(i)},${getY(d.benchmark_nav)}`).join(" ");

    // 区域填充闭合路径
    const baselineY = getY(minNav);
    const strategyArea = `${padding.left},${baselineY} ` + strategyPoints + ` ${padding.left + innerWidth},${baselineY}`;

    // 水下曲线坐标
    const strategyUwPoints = equityCurve.map((d, i) => `${getX(i)},${getUwY(d.strategy_dd_pct)}`).join(" ");
    const benchmarkUwPoints = equityCurve.map((d, i) => `${getX(i)},${getUwY(d.benchmark_dd_pct)}`).join(" ");

    const uwZeroY = getUwY(0);
    const strategyUwArea = `${padding.left},${uwZeroY} ` + strategyUwPoints + ` ${padding.left + innerWidth},${uwZeroY}`;

    // 横轴刻度采样 (取 5 个日期点)
    const xTicks = [];
    const step = Math.floor(equityCurve.length / 4);
    for (let i = 0; i < equityCurve.length; i += step) {
      xTicks.push({
        x: getX(i),
        label: equityCurve[i].date.slice(5), // MM-DD
      });
    }
    if (xTicks[xTicks.length - 1].x < padding.left + innerWidth - 40) {
      xTicks.push({
        x: getX(equityCurve.length - 1),
        label: equityCurve[equityCurve.length - 1].date.slice(5),
      });
    }

    // 净值纵轴刻度 (3 个点)
    const yTicks = [
      { y: getY(minNav), label: minNav.toFixed(2) },
      { y: getY((minNav + maxNav) / 2), label: ((minNav + maxNav) / 2).toFixed(2) },
      { y: getY(maxNav), label: maxNav.toFixed(2) },
    ];

    // 水下纵轴刻度 (3 个点)
    const uwYTicks = [
      { y: getUwY(0), label: "0%" },
      { y: getUwY(floorDd / 2), label: `${(floorDd / 2).toFixed(0)}%` },
      { y: getUwY(floorDd), label: `${floorDd.toFixed(0)}%` },
    ];

    return {
      width,
      height,
      uwHeight,
      padding,
      innerWidth,
      innerHeight,
      uwInnerHeight,
      getX,
      getY,
      getUwY,
      strategyPoints,
      benchmarkPoints,
      strategyArea,
      strategyUwPoints,
      benchmarkUwPoints,
      strategyUwArea,
      xTicks,
      yTicks,
      uwYTicks,
    };
  }, [equityCurve]);

  // 鼠标在 SVG 上滑动交互
  const handleSvgMouseMove = (e) => {
    if (!chartPoints || !equityCurve.length) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const svgX = (mouseX / rect.width) * chartPoints.width;
    if (svgX < chartPoints.padding.left || svgX > chartPoints.width - chartPoints.padding.right) {
      setHoverIndex(null);
      return;
    }
    const ratio = (svgX - chartPoints.padding.left) / (chartPoints.width - chartPoints.padding.left - chartPoints.padding.right);
    const idx = Math.min(equityCurve.length - 1, Math.max(0, Math.round(ratio * (equityCurve.length - 1))));
    setHoverIndex(idx);
  };

  const handleSvgMouseLeave = () => {
    setHoverIndex(null);
  };

  return (
    <div className="bg-white border border-gray-200 rounded-xl p-6 shadow-xs space-y-6">
      {/* 头部标题与周期切换 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-gray-100 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-blue-100/80 rounded-xl text-blue-700">
            <TrendingUp className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-gray-900">真实历史策略回测验证</h3>
              <span className="text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded-full">
                {summary?.trade_mode === "t0" ? "50% 底仓 · T+0 日内回转模拟" : "50% 底仓 · T+1 严格模拟"}
              </span>
              {summary?.trade_mode === "t0" && (
                <span className="text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full">
                  ★ T+0 跨境标的 · 支持日内回转交易
                </span>
              )}
              {stepMode === "fixed_eda" ? (
                <span className="text-xs font-semibold bg-amber-50 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full font-mono">
                  🏛️ E大原版步长 ({
                    edaStepRatios
                      ? `${Math.round(edaStepRatios.small * 100)}%/${Math.round(edaStepRatios.medium * 100)}%/${Math.round(edaStepRatios.large * 100)}%`
                      : edaSteps
                      ? `${edaSteps.small}%/${edaSteps.medium}%/${edaSteps.large}%`
                      : "5%/15%/30%"
                  })
                </span>
              ) : (
                <span className="text-xs font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200 px-2 py-0.5 rounded-full font-mono">
                  🌊 ATR 自适应步长 ({atrMultipliers ? `${atrMultipliers.small}x/${atrMultipliers.medium}x/${atrMultipliers.large}x` : "0.6x/1.2x/2.5x"})
                </span>
              )}
            </div>
            <p className="text-xs text-gray-500 mt-0.5 flex items-center gap-2">
              <span>回测期间：{summary?.start_date || "..."} 至 {summary?.end_date || "..."}（共 {summary?.backtest_days || 0} 个有效交易日）</span>
              {summary?.history_meta?.is_partial_history && (
                <span className="inline-flex items-center px-2 py-0.5 rounded text-[11px] font-semibold bg-amber-100 text-amber-800 border border-amber-300">
                  ⚠️ {summary.history_meta.partial_reason}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* 周期切换胶囊 */}
        <div className="flex flex-wrap items-center gap-1.5 bg-gray-100/90 p-1 rounded-xl self-start sm:self-auto text-xs">
          {[
            { days: 90, label: "90 天" },
            { days: 180, label: "180 天 (默认)" },
            { days: 365, label: "1 年" },
            { days: 730, label: "2 年" },
            { days: 1095, label: "3 年" },
            { days: 1825, label: "5 年 (牛熊)" },
          ].map((item) => (
            <button
              key={item.days}
              type="button"
              disabled={loading}
              onClick={() => setBacktestDays(item.days)}
              className={`px-2.5 py-1.5 rounded-lg font-medium transition-all ${
                backtestDays === item.days
                  ? "bg-white text-blue-700 font-bold shadow-xs"
                  : "text-gray-600 hover:text-gray-900"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {/* 回测基准锚点控制栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-slate-50 p-3 rounded-xl border border-slate-200 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-bold text-slate-700 flex items-center gap-1.5">
            <Target className="w-4 h-4 text-blue-600" />
            回测基准锚点 (P₀):
          </span>
          <div className="inline-flex items-center gap-2 bg-white px-2 py-1 rounded-lg border border-slate-200">
            <label className="flex items-center gap-1 cursor-pointer">
              <input
                type="radio"
                name="anchorMode"
                value="auto"
                checked={anchorMode === "auto"}
                onChange={() => setAnchorMode("auto")}
                className="text-blue-600 focus:ring-blue-500"
              />
              <span className="font-medium text-slate-800">⚡ 自动首日开盘价 (推荐)</span>
            </label>
            <label className="flex items-center gap-1 cursor-pointer ml-2">
              <input
                type="radio"
                name="anchorMode"
                value="custom"
                checked={anchorMode === "custom"}
                onChange={() => setAnchorMode("custom")}
                className="text-blue-600 focus:ring-blue-500"
              />
              <span className="font-medium text-slate-800">✏️ 自定义回测点位</span>
            </label>
          </div>
        </div>

        {anchorMode === "auto" ? (
          <div className="text-slate-500 font-mono flex flex-wrap items-center gap-1.5">
            <span>回测铺网:</span>
            <span className="font-bold text-blue-700 bg-blue-50 border border-blue-200 px-2 py-0.5 rounded">
              ¥{summary?.history_meta?.backtest_base_price ? Number(summary.history_meta.backtest_base_price).toFixed(3) : "..."}
            </span>
            <span className="text-slate-300">|</span>
            <span>最新市价:</span>
            <span className="font-bold text-slate-800 bg-white border border-slate-200 px-2 py-0.5 rounded">
              ¥{summary?.history_meta?.latest_market_price ? Number(summary.history_meta.latest_market_price).toFixed(3) : "..."}
            </span>
            <span className="text-[11px] text-slate-400 font-sans">(铺网用窗口首日开盘，消除未来函数，不是现价)</span>
          </div>
        ) : (
          <div className="flex items-center gap-1.5">
            <input
              type="number"
              step="0.001"
              placeholder="输入基准价(元)"
              value={customBasePrice}
              onChange={(e) => setCustomBasePrice(e.target.value)}
              className="w-28 px-2 py-1 bg-white border border-slate-300 rounded-lg text-slate-900 font-mono text-xs focus:ring-1 focus:ring-blue-500"
            />
            <button
              type="button"
              onClick={() => fetchBacktest(backtestDays)}
              className="px-2.5 py-1 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 shadow-2xs transition-colors"
            >
              应用
            </button>
          </div>
        )}
      </div>

      {/* 加载或报错状态 */}
      {loading && (
        <div className="py-12 flex flex-col items-center justify-center gap-3 text-gray-500">
          <RefreshCw className="w-6 h-6 animate-spin text-blue-600" />
          <span className="text-xs font-medium">正在执行历史行情逐日 T+1 撮合回测...</span>
        </div>
      )}

      {error && !loading && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700 flex items-center justify-between">
          <span>回测异常: {error}</span>
          <button
            type="button"
            onClick={() => fetchBacktest(backtestDays)}
            className="px-3 py-1 bg-white border border-red-300 rounded text-red-700 font-medium hover:bg-red-100"
          >
            重试
          </button>
        </div>
      )}

      {!loading && !error && summary && (() => {
        const calDays = summary?.history_meta?.actual_calendar_days || (summary?.backtest_days ? Math.round(summary.backtest_days * 1.45) : 365);
        const annualizedReturn = summary?.annualized_return != null 
          ? summary.annualized_return 
          : (summary?.strategy_return != null && calDays > 0 
              ? Number((summary.strategy_return * (365.0 / calDays)).toFixed(2)) 
              : 0);

        return (
        <>
          {/* 1. 核心战绩 KPI 跑道 (5 格对齐设计) */}
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
            {/* 1. 策略累计总收益率 */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-blue-50/80 to-white border border-blue-100">
              <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
                <span className="flex items-center gap-1.5">
                  <span>策略累计总收益率</span>
                  {(summary?.reinvest_mode || reinvestMode) === "pool_shares" && (
                    <span className="text-[10px] text-indigo-700 bg-indigo-100 px-1.5 py-0.2 rounded font-sans font-medium">
                      留利润
                    </span>
                  )}
                </span>
                <Sparkles className="w-3.5 h-3.5 text-blue-600" />
              </div>
              <div className={`text-2xl font-black font-mono ${summary.strategy_return >= 0 ? "text-red-600" : "text-green-600"}`}>
                {summary.strategy_return >= 0 ? `+${summary.strategy_return}%` : `${summary.strategy_return}%`}
              </div>
              <div className="text-[11px] text-gray-500 mt-1 font-mono truncate" title={`期末总资产: ¥${summary.final_equity?.toLocaleString()}`}>
                期末资产: ¥{summary.final_equity?.toLocaleString()}
              </div>
            </div>

            {/* 2. 策略折算年化收益率 (新增！与多周期天梯大宽表 100% 对齐) */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-indigo-50/80 to-white border border-indigo-100">
              <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
                <span className="flex items-center gap-1.5">
                  <span>策略折算年化收益率</span>
                  {(summary?.reinvest_mode || reinvestMode) === "cash" && (
                    <span className="text-[10px] text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded font-sans font-medium" title="当前为落袋全现金模式，天梯榜基准采用模式B留股">
                      全现金
                    </span>
                  )}
                </span>
                <TrendingUp className="w-3.5 h-3.5 text-indigo-600" />
              </div>
              <div className={`text-2xl font-black font-mono ${annualizedReturn >= 0 ? "text-red-600" : "text-green-600"}`}>
                {annualizedReturn >= 0 ? `+${annualizedReturn}%` : `${annualizedReturn}%`}
              </div>
              <div className="text-[11px] text-indigo-600 mt-1 font-medium truncate">
                跨度: {summary.backtest_days}交易日 ({calDays}天)
              </div>
              {(summary?.reinvest_mode || reinvestMode) === "cash" && (
                <div className="text-[10px] text-amber-600 dark:text-amber-400 mt-0.5 font-sans truncate" title="当前为全现金模式，若切换为模式B留利润，细碎差价将转增为0成本股票随标的复利增值，天梯大宽表基准采用模式B">
                  💡 当前为留现金模式（天梯榜基准为留股）
                </div>
              )}
            </div>

            {/* 3. 标的基准收益 */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-gray-50 to-white border border-gray-200">
              <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
                <span>标的持有同期涨跌</span>
                <Calendar className="w-3.5 h-3.5 text-gray-500" />
              </div>
              <div className={`text-2xl font-black font-mono ${summary.benchmark_return >= 0 ? "text-red-600" : "text-green-600"}`}>
                {summary.benchmark_return >= 0 ? `+${summary.benchmark_return}%` : `${summary.benchmark_return}%`}
              </div>
              <div className="text-[11px] text-gray-500 mt-1 truncate">
                买入并持有基准对照
              </div>
            </div>

            {/* 4. 跑赢超额 (Alpha) */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-emerald-50/80 to-white border border-emerald-100">
              <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
                <span>跑赢标的超额 (Alpha)</span>
                <Award className="w-3.5 h-3.5 text-emerald-600" />
              </div>
              <div className={`text-2xl font-black font-mono ${summary.alpha >= 0 ? "text-emerald-700" : "text-gray-700"}`}>
                {summary.alpha >= 0 ? `+${summary.alpha}%` : `${summary.alpha}%`}
              </div>
              <div className="text-[11px] text-emerald-700 mt-1 font-medium truncate" title={`纯做T利润: +¥${summary.grid_cash_profit?.toLocaleString()}`}>
                做T利润: +¥{summary.grid_cash_profit?.toLocaleString()}
              </div>
            </div>

            {/* 5. 胜率与风控 */}
            <div className="p-4 rounded-xl bg-gradient-to-br from-purple-50/80 to-white border border-purple-100">
              <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
                <span>做T胜率 / 最大回撤</span>
                <ShieldAlert className="w-3.5 h-3.5 text-purple-600" />
              </div>
              <div className="flex items-baseline gap-2">
                <span className="text-2xl font-black text-purple-900 font-mono">
                  {summary.win_rate == null ? "—" : `${summary.win_rate}%`}
                </span>
                <span className="text-xs text-gray-500 font-mono">回撤 {summary.max_drawdown}%</span>
              </div>
              <div className="text-[11px] text-gray-500 mt-1 truncate" title={`总成交 ${summary.total_trades_count} 笔 (买${summary.buy_trades_count}/卖${summary.sell_trades_count})`}>
                总成交 {summary.total_trades_count} 笔
              </div>
              {summary.unclosed_profit > 0 && (
                <div className="text-[11px] text-amber-600 mt-0.5 truncate" title="底仓高抛后未按设计回调价买回的卖出，该部分利润为预估未实现">
                  其中未闭环 +¥{Number(summary.unclosed_profit).toLocaleString()}
                </div>
              )}
            </div>
          </div>

          {/* 策略韧性与资金画像看板 (Sortino / 最长解套周期 / 资金利用率与安全垫) */}
          <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-50 via-gray-50/50 to-white border border-gray-200/80 shadow-2xs space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ShieldCheck className="w-4 h-4 text-indigo-600" />
                <span className="text-xs font-bold text-gray-800 tracking-wide">
                  策略韧性与资金画像 (量化下行风险与资金效率)
                </span>
              </div>
              <span className="text-[11px] text-gray-400">下行风险收益比 & 水下持续周期</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {/* 1. 索提诺比率 (Sortino) - 方案3：常驻4段色阶槽位 + 0延迟Hover/Click Popover */}
              <div className="p-3.5 bg-white rounded-xl border border-gray-100 shadow-2xs space-y-2 relative">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-1.5">
                    <span className="font-semibold text-gray-700 text-[11px]">索提诺比率 (Sortino)</span>
                    <button
                      type="button"
                      onClick={() => setShowSortinoPopover((prev) => !prev)}
                      onMouseEnter={() => setShowSortinoPopover(true)}
                      onMouseLeave={() => setShowSortinoPopover(false)}
                      className="text-gray-400 hover:text-indigo-600 transition-colors p-0.5 cursor-pointer"
                      aria-label="索提诺比率解释"
                    >
                      <HelpCircle className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <Scale className="w-3.5 h-3.5 text-indigo-500" />
                </div>

                <div className="flex items-baseline justify-between">
                  <span className="text-xl font-black font-mono text-gray-900">
                    {summary.sortino_ratio != null ? summary.sortino_ratio : "—"}
                  </span>
                  <span
                    className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      summary.sortino_ratio >= 2.0
                        ? "bg-purple-50 text-purple-700 border border-purple-200"
                        : summary.sortino_ratio >= 1.4
                        ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                        : summary.sortino_ratio >= 0.8
                        ? "bg-blue-50 text-blue-700 border border-blue-200"
                        : "bg-gray-100 text-gray-600 border border-gray-200"
                    }`}
                  >
                    {summary.sortino_ratio >= 2.0
                      ? "⭐ 极佳造血"
                      : summary.sortino_ratio >= 1.4
                      ? "🚀 优秀抗跌"
                      : summary.sortino_ratio >= 0.8
                      ? "✓ 风险均衡"
                      : "偏弱防守"}
                  </span>
                </div>

                {/* 常驻 4 段微型色阶槽位 */}
                <div
                  className="grid grid-cols-4 gap-1 p-0.5 bg-gray-50 rounded-lg text-center font-mono text-[9px] cursor-pointer"
                  onMouseEnter={() => setShowSortinoPopover(true)}
                  onMouseLeave={() => setShowSortinoPopover(false)}
                  onClick={() => setShowSortinoPopover((prev) => !prev)}
                  title="点击或悬浮查看索提诺4档段位详解"
                >
                  <div
                    className={`py-0.5 rounded transition-all ${
                      summary.sortino_ratio < 0.8
                        ? "bg-amber-100 text-amber-900 font-bold ring-1 ring-amber-400 shadow-2xs"
                        : "text-gray-400 bg-gray-100/60"
                    }`}
                  >
                    &lt;0.8 偏弱
                  </div>
                  <div
                    className={`py-0.5 rounded transition-all ${
                      summary.sortino_ratio >= 0.8 && summary.sortino_ratio < 1.4
                        ? "bg-blue-100 text-blue-900 font-bold ring-1 ring-blue-400 shadow-2xs"
                        : "text-gray-400 bg-gray-100/60"
                    }`}
                  >
                    0.8-1.4 均衡
                  </div>
                  <div
                    className={`py-0.5 rounded transition-all ${
                      summary.sortino_ratio >= 1.4 && summary.sortino_ratio < 2.0
                        ? "bg-emerald-100 text-emerald-900 font-bold ring-1 ring-emerald-400 shadow-2xs"
                        : "text-gray-400 bg-gray-100/60"
                    }`}
                  >
                    1.4-2.0 优秀
                  </div>
                  <div
                    className={`py-0.5 rounded transition-all ${
                      summary.sortino_ratio >= 2.0
                        ? "bg-purple-100 text-purple-900 font-bold ring-1 ring-purple-400 shadow-2xs"
                        : "text-gray-400 bg-gray-100/60"
                    }`}
                  >
                    &gt;2.0 极佳
                  </div>
                </div>

                <div className="text-[10px] text-indigo-600 font-sans leading-tight">
                  💡 每承受 1 份暴跌风险，换回 {summary.sortino_ratio ?? "—"} 份超额做T收益
                </div>

                {/* 0 延迟即时 Hover / Click 浮动详解卡片 (Popover) */}
                {showSortinoPopover && (
                  <div
                    className="absolute left-0 top-full mt-2 w-76 sm:w-80 bg-white dark:bg-gray-900 rounded-xl shadow-2xl border border-indigo-100 dark:border-gray-700 p-4 z-40 space-y-2.5 text-xs text-gray-700 dark:text-gray-200 animate-in fade-in duration-150"
                    onMouseEnter={() => setShowSortinoPopover(true)}
                    onMouseLeave={() => setShowSortinoPopover(false)}
                  >
                    <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-800 pb-2">
                      <div className="font-bold text-gray-900 dark:text-gray-100 flex items-center gap-1.5">
                        <Scale className="w-4 h-4 text-indigo-600" />
                        <span>索提诺比率 (Sortino) 段位标尺</span>
                      </div>
                      <button
                        type="button"
                        onClick={() => setShowSortinoPopover(false)}
                        className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 p-1"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    <p className="text-[11px] text-gray-500 dark:text-gray-400 leading-relaxed">
                      <strong>💡 通俗比喻：</strong>只考核下跌挨打（下行半方差），不惩罚暴涨冲高。当前标的每承受 1 元下跌浮亏风险，网格逆势做 T 换回 <strong className="text-indigo-600 dark:text-indigo-400 font-mono">{summary.sortino_ratio ?? "—"}</strong> 元超额收益。
                    </p>

                    {/* 4 档段位细解 */}
                    <div className="space-y-1 pt-1 font-sans">
                      <div
                        className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                          summary.sortino_ratio >= 2.0
                            ? "bg-purple-50 border-purple-300 text-purple-900 font-bold dark:bg-purple-950/40 dark:text-purple-200"
                            : "border-gray-100 text-gray-500 dark:border-gray-800 dark:text-gray-400"
                        }`}
                      >
                        <span>⭐ &gt; 2.0 · 极佳造血</span>
                        <span className="text-[10px] font-normal">
                          {summary.sortino_ratio >= 2.0 ? "← 当前所处段位" : "长线网格圣杯"}
                        </span>
                      </div>
                      <div
                        className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                          summary.sortino_ratio >= 1.4 && summary.sortino_ratio < 2.0
                            ? "bg-emerald-50 border-emerald-300 text-emerald-900 font-bold dark:bg-emerald-950/40 dark:text-emerald-200"
                            : "border-gray-100 text-gray-500 dark:border-gray-800 dark:text-gray-400"
                        }`}
                      >
                        <span>🚀 1.4 ~ 2.0 · 优秀抗跌</span>
                        <span className="text-[10px] font-normal">
                          {summary.sortino_ratio >= 1.4 && summary.sortino_ratio < 2.0 ? "← 当前所处段位" : "对冲效率高，修复迅速"}
                        </span>
                      </div>
                      <div
                        className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                          summary.sortino_ratio >= 0.8 && summary.sortino_ratio < 1.4
                            ? "bg-blue-50 border-blue-300 text-blue-900 font-bold dark:bg-blue-950/40 dark:text-blue-200"
                            : "border-gray-100 text-gray-500 dark:border-gray-800 dark:text-gray-400"
                        }`}
                      >
                        <span>✓ 0.8 ~ 1.4 · 风险均衡</span>
                        <span className="text-[10px] font-normal">
                          {summary.sortino_ratio >= 0.8 && summary.sortino_ratio < 1.4 ? "← 当前所处段位" : "合格网格，抵消大部分下跌"}
                        </span>
                      </div>
                      <div
                        className={`p-2 rounded-lg border text-[11px] flex items-center justify-between ${
                          summary.sortino_ratio < 0.8
                            ? "bg-amber-50 border-amber-300 text-amber-900 font-bold dark:bg-amber-950/40 dark:text-amber-200"
                            : "border-gray-100 text-gray-500 dark:border-gray-800 dark:text-gray-400"
                        }`}
                      >
                        <span>⚠️ &lt; 0.8 · 偏弱防守</span>
                        <span className="text-[10px] font-normal">
                          {summary.sortino_ratio < 0.8 ? "← 当前所处段位" : "挨打跌幅大，做T收益没跟上"}
                        </span>
                      </div>
                    </div>
                  </div>
                )}
              </div>

              {/* 2. 回撤修复与解套韧性 (双维度拆解：最深暴跌自愈 vs 漫长水下横盘) */}
              <div
                className="p-3.5 bg-white rounded-xl border border-gray-100 shadow-2xs space-y-1.5"
                title="最深回撤修复天数：最大浮亏谷底到爬坑解套；最长水下磨底天数：未破历史新高的最长横盘滞留"
              >
                <div className="text-[11px] text-gray-500 flex items-center justify-between">
                  <span className="font-semibold text-gray-700">回撤修复与解套韧性</span>
                  <Clock className="w-3.5 h-3.5 text-rose-500" />
                </div>
                <div className="flex items-baseline justify-between font-mono">
                  <div className="space-y-0.5">
                    <span className="text-[10px] text-gray-400 block font-sans">最深回撤修复</span>
                    <span className="text-lg font-black text-rose-600">
                      {summary.max_dd_recovery_days != null ? `${summary.max_dd_recovery_days} 天` : "—"}
                    </span>
                  </div>
                  <div className="text-right space-y-0.5">
                    <span className="text-[10px] text-gray-400 block font-sans">最长水下磨底</span>
                    <span className="text-lg font-black text-amber-600">
                      {summary.longest_underwater_days != null ? `${summary.longest_underwater_days} 天` : "—"}
                    </span>
                  </div>
                </div>
                <div className="text-[10px] text-gray-500 font-sans leading-relaxed truncate">
                  最深危机回撤 {summary.max_drawdown}% · 磨底为横盘不创新高期
                </div>
              </div>

              {/* 3. 平均资金占用与防爆仓垫 */}
              <div
                className="p-3.5 bg-white rounded-xl border border-gray-100 shadow-2xs space-y-1.5"
                title="资金暴露度：持仓常规市值与免费股现值占总资产比例。余量为防暴跌深水补仓流动性底垫"
              >
                <div className="text-[11px] text-gray-500 flex items-center justify-between">
                  <span className="font-semibold text-gray-700">资金利用率与安全垫</span>
                  <Coins className="w-3.5 h-3.5 text-emerald-500" />
                </div>
                <div className="text-xl font-black font-mono text-gray-900">
                  均仓 {summary.avg_exposure ?? 50.0}%
                </div>
                <div className="text-[10px] text-emerald-700 font-sans truncate">
                  峰值吃刀 {summary.max_exposure ?? 50.0}% (余 {(100 - (summary.max_exposure ?? 50.0)).toFixed(1)}% 防爆仓现金垫)
                </div>
              </div>
            </div>
          </div>

          {/* 留利润模式专属：收益穿透桥梁与归因分解 (做T造血 ➔ 滚存股本 ➔ 享受主升浪) */}
          {profitAttribution && (summary?.reinvest_mode || reinvestMode) === "pool_shares" && (
            <div className="p-4 sm:p-5 rounded-2xl bg-gradient-to-br from-indigo-50/80 via-blue-50/40 to-white border border-indigo-200 shadow-2xs space-y-3.5">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-indigo-100 pb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-indigo-600 rounded-lg text-white">
                    <Layers className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-gray-900 flex items-center gap-2">
                      <span>留利润模式收益穿透全景 (资金全链路平账)</span>
                      <span className="text-[10px] bg-indigo-100 text-indigo-800 px-2 py-0.5 rounded-full font-mono font-bold">
                        对账闭环 100%
                      </span>
                    </h4>
                  </div>
                </div>
                <div className="text-xs text-gray-600 font-mono">
                  本金 ¥{profitAttribution.initialCapital.toLocaleString()} ➔ 期末总资产{" "}
                  <span className="font-bold text-indigo-950">¥{profitAttribution.finalEquity.toLocaleString()}</span>{" "}
                  (净利{" "}
                  <span className={`font-bold ${profitAttribution.totalProfit >= 0 ? "text-red-600" : "text-green-700"}`}>
                    {profitAttribution.totalProfit >= 0 ? `+¥${profitAttribution.totalProfit.toLocaleString()}` : `-¥${Math.abs(profitAttribution.totalProfit).toLocaleString()}`}
                  </span>
                  )
                </div>
              </div>

              {/* 三大资金归因分解卡片 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-xs">
                {/* 1. 做T价差本金 */}
                <div className="bg-white/95 p-3.5 rounded-xl border border-blue-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-gray-500 mb-1">
                    <span className="flex items-center gap-1.5 font-bold text-blue-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-blue-500 inline-block"></span>
                      ① 网格做T落袋净利
                    </span>
                    <span className="font-mono font-bold text-blue-700 bg-blue-50 px-1.5 py-0.5 rounded">
                      {profitAttribution.gridPct}% 贡献
                    </span>
                  </div>
                  <div className="text-xl font-black font-mono text-blue-700 mt-1">
                    +¥{profitAttribution.gridProfit.toLocaleString()}
                  </div>
                  <div className="text-[11px] text-gray-500 mt-1.5 leading-relaxed">
                    流水做T累积纯价差，已 100% 汇入蓄水池充当购股成本 (池内零钱 ¥{profitAttribution.poolRemainder})
                  </div>
                </div>

                {/* 2. 免费份额牛市浮盈 */}
                <div className="bg-white/95 p-3.5 rounded-xl border border-purple-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-gray-500 mb-1">
                    <span className="flex items-center gap-1.5 font-bold text-purple-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-purple-500 inline-block"></span>
                      ② 免费份额持仓浮盈
                    </span>
                    <span className="font-mono font-bold text-purple-700 bg-purple-50 px-1.5 py-0.5 rounded">
                      {profitAttribution.freeSharesPct}% 贡献
                    </span>
                  </div>
                  <div className="text-xl font-black font-mono text-purple-700 mt-1">
                    {profitAttribution.freeSharesGain >= 0 ? `+¥${profitAttribution.freeSharesGain.toLocaleString()}` : `-¥${Math.abs(profitAttribution.freeSharesGain).toLocaleString()}`}
                  </div>
                  <div className="text-[11px] text-gray-500 mt-1.5 leading-relaxed">
                    {profitAttribution.freeShares.toLocaleString()} 股免费份额随标的大涨增值至现值 ¥{profitAttribution.freeSharesValue.toLocaleString()}，享受长牛复利
                  </div>
                </div>

                {/* 3. 底仓高抛变现溢价 */}
                <div className="bg-white/95 p-3.5 rounded-xl border border-emerald-200/90 shadow-xs">
                  <div className="flex items-center justify-between text-gray-500 mb-1">
                    <span className="flex items-center gap-1.5 font-bold text-emerald-900">
                      <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 inline-block"></span>
                      ③ 底仓高抛变现与余值
                    </span>
                    <span className="font-mono font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.5 rounded">
                      {profitAttribution.basePct}% 贡献
                    </span>
                  </div>
                  <div className="text-xl font-black font-mono text-emerald-700 mt-1">
                    {profitAttribution.basePositionGain >= 0 ? `+¥${profitAttribution.basePositionGain.toLocaleString()}` : `-¥${Math.abs(profitAttribution.basePositionGain).toLocaleString()}`}
                  </div>
                  <div className="text-[11px] text-gray-500 mt-1.5 leading-relaxed">
                    开网 50% 底仓高位分批止盈回流现金，以及期末未平仓余股现值
                  </div>
                </div>
              </div>

              {/* 堆叠比例分布条 */}
              <div className="space-y-1.5 pt-1">
                <div className="w-full h-3 bg-gray-100 rounded-full overflow-hidden flex shadow-inner border border-gray-200/50">
                  <div
                    style={{ width: `${profitAttribution.gridPct}%` }}
                    className="bg-blue-500 transition-all hover:opacity-90"
                    title={`做T价差本金贡献: ${profitAttribution.gridPct}%`}
                  />
                  <div
                    style={{ width: `${profitAttribution.freeSharesPct}%` }}
                    className="bg-purple-500 transition-all hover:opacity-90"
                    title={`免费份额持仓浮盈贡献: ${profitAttribution.freeSharesPct}%`}
                  />
                  <div
                    style={{ width: `${profitAttribution.basePct}%` }}
                    className="bg-emerald-500 transition-all hover:opacity-90"
                    title={`底仓高抛变现与余值贡献: ${profitAttribution.basePct}%`}
                  />
                </div>
                <div className="flex items-center justify-between text-[11px] text-gray-500 font-mono px-1">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-blue-500 inline-block"></span>
                    做T差价初始积累: {profitAttribution.gridPct}%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-purple-500 inline-block"></span>
                    牛市持股浮盈: {profitAttribution.freeSharesPct}%
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 inline-block"></span>
                    底仓变现: {profitAttribution.basePct}%
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* 模式 B 专属：0 成本免费份额沉淀库卡片 */}
          {profitPool?.enabled && (
            <div className="p-5 rounded-2xl bg-gradient-to-r from-emerald-500/10 via-teal-500/5 to-white border border-emerald-300 shadow-2xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-emerald-200/60 pb-3 mb-3">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-emerald-600 rounded-lg text-white">
                    <PiggyBank className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-emerald-950 flex items-center gap-2">
                      <span>0 成本免费份额沉淀库 (E大 2.1 留股模式)</span>
                      <span className="text-[10px] bg-emerald-100 text-emerald-800 px-2 py-0.5 rounded-full font-sans font-semibold">
                        自动转增 {profitPool.transfer_count} 次
                      </span>
                    </h4>
                  </div>
                </div>
                <span className="text-xs text-emerald-700 font-medium font-sans">
                  做 T 纯差价利润全额换股 · 终身免受牛市踏空之苦
                </span>
              </div>

              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                <div className="bg-white/90 p-3 rounded-xl border border-emerald-200">
                  <div className="text-[11px] text-gray-500">已沉淀免费份额</div>
                  <div className="text-xl font-black font-mono text-emerald-800 mt-0.5">
                    +{profitPool.free_shares?.toLocaleString()} 股
                  </div>
                  <div className="text-[10px] text-emerald-700 mt-1 font-sans">
                    持仓综合成本: ¥0.000 / 股
                  </div>
                </div>

                <div className="bg-white/90 p-3 rounded-xl border border-emerald-200">
                  <div className="text-[11px] text-gray-500">免费份额当前市值</div>
                  <div className="text-xl font-black font-mono text-gray-900 mt-0.5">
                    ¥{profitPool.free_shares_value?.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-gray-400 mt-1 font-sans">
                    永不卖飞，享受长牛复利
                  </div>
                </div>

                <div className="bg-white/90 p-3 rounded-xl border border-emerald-200">
                  <div className="text-[11px] text-gray-500">蓄水池现金余额 (零头)</div>
                  <div className="text-xl font-black font-mono text-blue-700 mt-0.5">
                    ¥{profitPool.profit_pool_remainder}
                  </div>
                  <div className="text-[10px] text-gray-500 mt-1 font-sans">
                    再攒 ¥{profitPool.next_lot_needed} 可再转100股
                  </div>
                </div>

                <div className="bg-white/90 p-3 rounded-xl border border-emerald-200">
                  <div className="text-[11px] text-gray-500">累计做T纯差价毛利润</div>
                  <div className="text-xl font-black font-mono text-gray-900 mt-0.5">
                    ¥{profitPool.total_profit_accumulated?.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-emerald-700 mt-1 font-sans">
                    100% 榨干波动，化为真实股份
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* 2. 净值与水下深度双联对决图 (轻量纯 SVG 矢量渲染 + 十字光标联动) */}
          <div className="border border-gray-200 rounded-xl p-5 bg-white space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
              <div>
                <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
                  <span>策略净值走势对决</span>
                  <span className="text-[10px] text-gray-500 font-normal">（单位净值从 1.00 起步）</span>
                </h4>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-1 bg-blue-600 rounded-full inline-block"></span>
                  <span className="text-gray-700 font-medium">网格做T策略净值 (平滑稳健)</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="w-3 h-1 border-t-2 border-dashed border-gray-400 inline-block"></span>
                  <span className="text-gray-500">标的持有基准 (波动剧烈)</span>
                </div>
              </div>
            </div>

            {/* 十字光标动态探针卡片 */}
            {hoverIndex !== null && equityCurve[hoverIndex] && (
              <div className="flex flex-wrap items-center justify-between gap-3 px-3.5 py-2 bg-indigo-50/80 rounded-xl text-xs font-mono border border-indigo-200/70 shadow-2xs animate-in fade-in duration-150">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-indigo-950">📅 {equityCurve[hoverIndex].date}</span>
                  <span className="text-gray-300">|</span>
                  <span className="text-blue-700 font-bold">
                    策略净值: {equityCurve[hoverIndex].strategy_nav}
                  </span>
                  <span className="text-gray-500">
                    (总资产: ¥{Number(equityCurve[hoverIndex].strategy_equity).toLocaleString()})
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-gray-600">标的: {equityCurve[hoverIndex].benchmark_nav}</span>
                  <span className="text-rose-600 font-bold">
                    策略回撤: {equityCurve[hoverIndex].strategy_dd_pct ?? 0}%
                  </span>
                  <span className="text-gray-500">
                    标的回撤: {equityCurve[hoverIndex].benchmark_dd_pct ?? 0}%
                  </span>
                  <span className="text-emerald-700 font-medium">
                    仓位: {((equityCurve[hoverIndex].exposure ?? 0.5) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}

            {chartPoints && (
              <div className="space-y-4">
                {/* 1. 净值曲线图 */}
                <div className="w-full overflow-x-auto">
                  <svg
                    viewBox={`0 0 ${chartPoints.width} ${chartPoints.height}`}
                    className="w-full h-48 select-none cursor-crosshair"
                    onMouseMove={handleSvgMouseMove}
                    onMouseLeave={handleSvgMouseLeave}
                  >
                    <defs>
                      <linearGradient id="strategyGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                        <stop offset="0%" stopColor="#3b82f6" stopOpacity="0.18" />
                        <stop offset="100%" stopColor="#3b82f6" stopOpacity="0.0" />
                      </linearGradient>
                    </defs>

                    {/* 背景参考线 */}
                    {chartPoints.yTicks.map((tick, idx) => (
                      <g key={idx}>
                        <line
                          x1={chartPoints.padding.left}
                          y1={tick.y}
                          x2={chartPoints.width - chartPoints.padding.right}
                          y2={tick.y}
                          stroke="#f1f5f9"
                          strokeDasharray="3 3"
                        />
                        <text
                          x={chartPoints.padding.left - 8}
                          y={tick.y + 4}
                          fontSize="10"
                          fill="#94a3b8"
                          textAnchor="end"
                          fontFamily="monospace"
                        >
                          {tick.label}
                        </text>
                      </g>
                    ))}

                    {/* 策略净值阴影面积 */}
                    <polygon points={chartPoints.strategyArea} fill="url(#strategyGrad)" />

                    {/* 标的持有走势曲线 (灰色虚线) */}
                    <polyline
                      fill="none"
                      stroke="#94a3b8"
                      strokeWidth="1.5"
                      strokeDasharray="4 3"
                      points={chartPoints.benchmarkPoints}
                    />

                    {/* 网格策略净值曲线 (蓝色实线) */}
                    <polyline
                      fill="none"
                      stroke="#2563eb"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      points={chartPoints.strategyPoints}
                    />

                    {/* 十字光标竖线 */}
                    {hoverIndex !== null && (
                      <line
                        x1={chartPoints.getX(hoverIndex)}
                        y1={chartPoints.padding.top}
                        x2={chartPoints.getX(hoverIndex)}
                        y2={chartPoints.height - chartPoints.padding.bottom}
                        stroke="#6366f1"
                        strokeWidth="1.2"
                        strokeDasharray="3 2"
                      />
                    )}
                  </svg>
                </div>

                {/* 2. 水下深度与回撤全景图 */}
                <div className="pt-2 border-t border-gray-100 space-y-2">
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="font-bold text-gray-800 flex items-center gap-1">
                        <span>🌊 水下深度与解套全景</span>
                        <span className="text-[10px] text-gray-500 font-normal font-sans">(0% 轴朝下染色)</span>
                      </span>
                    </div>
                    <div className="flex items-center gap-3 text-[11px] text-gray-500">
                      <span className="flex items-center gap-1">
                        <span className="w-2.5 h-2.5 bg-rose-400/50 border border-rose-500 rounded-2xs inline-block"></span>
                        <span>网格水下深度</span>
                      </span>
                      <span className="flex items-center gap-1">
                        <span className="w-3 h-0.5 border-t border-dashed border-gray-400 inline-block"></span>
                        <span>标的水下轮廓</span>
                      </span>
                    </div>
                  </div>

                  <div className="w-full overflow-x-auto">
                    <svg
                      viewBox={`0 0 ${chartPoints.width} ${chartPoints.uwHeight}`}
                      className="w-full h-28 select-none cursor-crosshair"
                      onMouseMove={handleSvgMouseMove}
                      onMouseLeave={handleSvgMouseLeave}
                    >
                      <defs>
                        <linearGradient id="underwaterGrad" x1="0%" y1="0%" x2="0%" y2="100%">
                          <stop offset="0%" stopColor="#f43f5e" stopOpacity="0.10" />
                          <stop offset="100%" stopColor="#e11d48" stopOpacity="0.45" />
                        </linearGradient>
                      </defs>

                      {/* 水下 Y 刻度与参考线 */}
                      {chartPoints.uwYTicks.map((tick, idx) => (
                        <g key={idx}>
                          <line
                            x1={chartPoints.padding.left}
                            y1={tick.y}
                            x2={chartPoints.width - chartPoints.padding.right}
                            y2={tick.y}
                            stroke="#f1f5f9"
                            strokeDasharray="2 2"
                          />
                          <text
                            x={chartPoints.padding.left - 8}
                            y={tick.y + 4}
                            fontSize="9"
                            fill="#94a3b8"
                            textAnchor="end"
                            fontFamily="monospace"
                          >
                            {tick.label}
                          </text>
                        </g>
                      ))}

                      {/* 0% 顶峰基准线 */}
                      <line
                        x1={chartPoints.padding.left}
                        y1={chartPoints.getUwY(0)}
                        x2={chartPoints.width - chartPoints.padding.right}
                        y2={chartPoints.getUwY(0)}
                        stroke="#cbd5e1"
                        strokeWidth="1"
                      />

                      {/* 水下时间横轴刻度 */}
                      {chartPoints.xTicks.map((tick, idx) => (
                        <text
                          key={idx}
                          x={tick.x}
                          y={chartPoints.uwHeight - 4}
                          fontSize="9"
                          fill="#94a3b8"
                          textAnchor="middle"
                          fontFamily="monospace"
                        >
                          {tick.label}
                        </text>
                      ))}

                      {/* 网格水下深度面积 */}
                      <polygon points={chartPoints.strategyUwArea} fill="url(#underwaterGrad)" />

                      {/* 标的水下虚线轮廓 */}
                      <polyline
                        fill="none"
                        stroke="#94a3b8"
                        strokeWidth="1.2"
                        strokeDasharray="3 2"
                        points={chartPoints.benchmarkUwPoints}
                      />

                      {/* 网格水下前沿实线 */}
                      <polyline
                        fill="none"
                        stroke="#e11d48"
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        points={chartPoints.strategyUwPoints}
                      />

                      {/* 十字光标竖线 */}
                      {hoverIndex !== null && (
                        <line
                          x1={chartPoints.getX(hoverIndex)}
                          y1={chartPoints.padding.top}
                          x2={chartPoints.getX(hoverIndex)}
                          y2={chartPoints.uwHeight - chartPoints.padding.bottom}
                          stroke="#6366f1"
                          strokeWidth="1.2"
                          strokeDasharray="3 2"
                        />
                      )}
                    </svg>
                  </div>
                </div>

                {/* 3. 历史重大回撤危机复盘快捷诊断入口 */}
                {summary.top_drawdown_spells && summary.top_drawdown_spells.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-gray-100">
                    <span className="text-[11px] font-bold text-gray-600 flex items-center gap-1">
                      <ShieldAlert className="w-3.5 h-3.5 text-rose-500" />
                      <span>重大危机复盘诊断:</span>
                    </span>
                    {summary.top_drawdown_spells.map((spell, sIdx) => {
                      const isGrind = spell.spell_type === "longest_grind";
                      return (
                        <button
                          key={sIdx}
                          type="button"
                          onClick={() => {
                            setSelectedCrisis(spell);
                            setIsCrisisModalOpen(true);
                          }}
                          className={`px-2.5 py-1 rounded-lg text-xs font-mono font-medium transition-colors flex items-center gap-1.5 cursor-pointer shadow-2xs ${
                            isGrind
                              ? "bg-amber-50 hover:bg-amber-100 border border-amber-200 text-amber-800"
                              : "bg-rose-50 hover:bg-rose-100 border border-rose-200 text-rose-700"
                          }`}
                          title="点击展开该次危机中网格倒金字塔加码低吸与做T差价现金流复盘"
                        >
                          <span>
                            {spell.tag_label || `#${spell.rank}`} 回撤 -{Math.abs(spell.max_dd_pct)}% ({spell.peak_date} ~ {spell.recovered_date || "至今"} 历时{spell.underwater_days}天)
                          </span>
                          <span className={`text-[10px] underline font-sans ${isGrind ? "text-amber-700" : "text-rose-600"}`}>
                            复盘 ➔
                          </span>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 3. 三色彩虹利润归因条 */}
          {railAttribution && railAttribution.length > 0 && (
            <div className="border border-gray-200 rounded-xl p-5 bg-white">
              <h4 className="font-bold text-gray-900 text-sm mb-3 flex items-center justify-between">
                <span>三轨做 T 利润贡献归因</span>
                <span className="text-xs text-gray-500 font-normal">多轨协同吸收不同波段振幅</span>
              </h4>

              {/* 彩虹比例条 */}
              <div className="w-full h-3.5 bg-gray-100 rounded-full overflow-hidden flex mb-3 shadow-inner">
                {railAttribution.map((r) => {
                  const widthPct = Number(r.profit_ratio) > 0 ? Number(r.profit_ratio) : 0;
                  const color =
                    r.rail === "large"
                      ? "bg-purple-500"
                      : r.rail === "medium"
                      ? "bg-blue-500"
                      : "bg-emerald-500";
                  return (
                    <div
                      key={r.rail}
                      style={{ width: `${widthPct}%` }}
                      className={`${color} transition-all`}
                      title={`${r.name}: ${r.profit_ratio}%`}
                    ></div>
                  );
                })}
              </div>

              {/* 三轨统计卡片 */}
              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                {railAttribution.map((r) => {
                  const isSmall = r.rail === "small";
                  const isMed = r.rail === "medium";
                  const border = isSmall
                    ? "border-emerald-200 bg-emerald-50/40"
                    : isMed
                    ? "border-blue-200 bg-blue-50/40"
                    : "border-purple-200 bg-purple-50/40";
                  const dotColor = isSmall ? "bg-emerald-500" : isMed ? "bg-blue-500" : "bg-purple-500";

                  return (
                    <div key={r.rail} className={`p-3 rounded-lg border ${border} text-xs`}>
                      <div className="flex items-center justify-between font-bold mb-1 text-gray-900">
                        <span className="flex items-center gap-1.5">
                          <span className={`w-2 h-2 rounded-full ${dotColor}`}></span>
                          {r.name}
                        </span>
                        <span className="font-mono text-gray-700">利润占比 {r.profit_ratio}%</span>
                      </div>
                      <div className="flex items-center justify-between text-gray-600 mt-2 font-mono">
                        <span>成交: {r.trades_count} 次</span>
                        <span className={`font-bold ${Number(r.profit) < 0 ? "text-green-700" : "text-gray-900"}`}>
                          贡献利润: {Number(r.profit) > 0 ? `+¥${r.profit}` : Number(r.profit) < 0 ? `-¥${Math.abs(Number(r.profit))}` : `¥${r.profit}`}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* 4. 可折叠逐笔交易明细流水 */}
          <div className="border border-gray-200 rounded-xl overflow-hidden bg-white">
            <button
              type="button"
              onClick={() => setShowAllTrades(!showAllTrades)}
              className="w-full py-3 px-5 bg-gray-50 flex items-center justify-between text-xs font-bold text-gray-700 hover:bg-gray-100 transition-colors"
            >
              <span className="flex items-center gap-2">
                <span>回测撮合交易流水明细</span>
                <span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 font-mono">
                  共 {allTrades.length} 笔
                </span>
                {selectedRail !== "all" && (
                  <span className="text-gray-400 font-normal">
                    (当前筛选: {filteredTrades.length} 笔)
                  </span>
                )}
              </span>
              <span className="flex items-center gap-1 text-blue-600">
                {showAllTrades ? "收起明细" : "展开明细"}
                {showAllTrades ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
              </span>
            </button>

            {showAllTrades && (
              <div className="p-4 space-y-3 bg-white">
                {/* 筛选与操作控制条 */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-gray-50/80 p-3 rounded-xl border border-gray-100">
                  {/* 分轨选择胶囊 */}
                  <div className="flex items-center gap-1.5 text-xs">
                    <span className="text-gray-500 font-medium mr-1 flex items-center gap-1">
                      <Filter className="w-3.5 h-3.5" /> 轨道筛选:
                    </span>
                    {[
                      { id: "all", label: `全部 (${allTrades.length})` },
                      { id: "small", label: `小网 (${allTrades.filter((t) => t.rail === "small").length})` },
                      { id: "medium", label: `中网 (${allTrades.filter((t) => t.rail === "medium").length})` },
                      { id: "large", label: `大网 (${allTrades.filter((t) => t.rail === "large").length})` },
                    ].map((rail) => (
                      <button
                        key={rail.id}
                        type="button"
                        onClick={() => setSelectedRail(rail.id)}
                        className={`px-2.5 py-1 rounded-lg font-medium transition-all ${
                          selectedRail === rail.id
                            ? "bg-white text-blue-700 font-bold shadow-xs border border-gray-200"
                            : "text-gray-600 hover:text-gray-900"
                        }`}
                      >
                        {rail.label}
                      </button>
                    ))}
                  </div>

                  {/* 导出与分页容量控制 */}
                  <div className="flex items-center gap-2 self-end sm:self-auto text-xs">
                    <select
                      value={pageSize}
                      onChange={(e) => {
                        setPageSize(Number(e.target.value));
                        setCurrentPage(1);
                      }}
                      className="px-2 py-1 bg-white border border-gray-200 rounded-lg text-gray-700 text-xs focus:ring-1 focus:ring-blue-500"
                    >
                      <option value={20}>每页 20 笔</option>
                      <option value={50}>每页 50 笔</option>
                      <option value={100}>每页 100 笔</option>
                    </select>

                    <button
                      type="button"
                      onClick={handleExportCsv}
                      className="inline-flex items-center gap-1 px-3 py-1 bg-white border border-gray-300 text-gray-700 rounded-lg font-medium hover:bg-gray-100 transition-colors shadow-2xs"
                    >
                      <Download className="w-3.5 h-3.5 text-gray-600" />
                      导出 CSV
                    </button>
                  </div>
                </div>

                {/* 选中轨道专属统计面板 */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 bg-blue-50/40 p-3 rounded-lg border border-blue-100 text-xs font-mono">
                  <div>
                    <span className="text-gray-500">轨道成交: </span>
                    <span className="font-bold text-gray-900">{railStatsSummary.totalCount} 笔</span>
                  </div>
                  <div>
                    <span className="text-gray-500">买入/卖出: </span>
                    <span className="text-emerald-700 font-semibold">{railStatsSummary.buyCount}买</span>
                    <span className="text-gray-400"> / </span>
                    <span className="text-red-700 font-semibold">{railStatsSummary.sellCount}卖</span>
                  </div>
                  <div>
                    <span className="text-gray-500">贡献净利: </span>
                    <span className="font-bold text-red-600">+¥{railStatsSummary.totalProfit}</span>
                  </div>
                  <div>
                    <span className="text-gray-500">单笔均利: </span>
                    <span className="font-bold text-gray-900">+¥{railStatsSummary.avgProfitPerSell}</span>
                  </div>
                </div>

                {/* 模式 B 专属：交易流水与留利润对账联动提示 */}
                {(summary?.reinvest_mode || reinvestMode) === "pool_shares" && (
                  <div className="flex items-start sm:items-center gap-2 px-3.5 py-2.5 rounded-lg bg-amber-50/90 border border-amber-200/80 text-xs text-amber-900">
                    <Info className="w-4 h-4 text-amber-600 shrink-0 mt-0.5 sm:mt-0" />
                    <div className="leading-relaxed">
                      <span className="font-bold">流水对账说明：</span>
                      当前启用了【留利润模式】，此处交易流水明细所列“落袋净利”为纯网格做 T 的<strong>价差收益</strong>（全轨做T净利累计 +¥{summary?.grid_cash_profit || summary?.profit_pool?.total_profit_accumulated || "0.00"}）。该笔利润已 100% 汇入蓄水池购入 {profitPool?.free_shares?.toLocaleString() || 0} 股免费份额（期末现值 ¥{profitPool?.free_shares_value?.toLocaleString() || "0.00"}），产生的持仓浮盈已全部计入顶部总资产与策略总收益率中。
                    </div>
                  </div>
                )}

                {/* 交易流水表格 */}
                <div className="overflow-x-auto max-h-80 border border-gray-200 rounded-lg">
                  <table className="w-full text-left text-xs border-collapse font-mono">
                    <thead className="bg-gray-50/90 sticky top-0 border-b border-gray-200 text-gray-500">
                      <tr>
                        <th className="py-2.5 px-4 font-semibold">成交时间</th>
                        <th className="py-2.5 px-4 font-semibold">动作</th>
                        <th className="py-2.5 px-4 font-semibold">轨道</th>
                        <th className="py-2.5 px-4 font-semibold">成交价格</th>
                        <th className="py-2.5 px-4 font-semibold">股数</th>
                        <th className="py-2.5 px-4 font-semibold">成交金额</th>
                        <th className="py-2.5 px-4 font-semibold">持有周期</th>
                        <th className="py-2.5 px-4 font-semibold">手续费</th>
                        <th className="py-2.5 px-4 font-semibold">落袋净利</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {paginatedTrades.length === 0 ? (
                        <tr>
                          <td colSpan={9} className="py-6 text-center text-gray-400">
                            该轨道暂无成交记录
                          </td>
                        </tr>
                      ) : (
                        paginatedTrades.map((t, idx) => (
                          <tr key={idx} className="hover:bg-gray-50 transition-colors">
                            <td className="py-2 px-4 text-gray-500">{t.trade_time}</td>
                            <td className="py-2 px-4">
                              <span
                                className={`inline-flex items-center gap-0.5 px-2 py-0.5 rounded text-[11px] font-bold font-sans ${
                                  t.action === "SELL"
                                    ? "bg-red-100 text-red-800"
                                    : "bg-emerald-100 text-emerald-800"
                                }`}
                              >
                                {t.action === "SELL" ? (
                                  <ArrowUpRight className="w-3 h-3" />
                                ) : (
                                  <ArrowDownRight className="w-3 h-3" />
                                )}
                                {t.action_label}
                              </span>
                            </td>
                            <td className="py-2 px-4">
                              <span className="text-gray-700 font-sans font-medium">{t.rail_name}</span>
                            </td>
                            <td className="py-2 px-4 font-bold text-gray-900">¥{Number(t.price).toFixed(3)}</td>
                            <td className="py-2 px-4">{t.shares?.toLocaleString()} 股</td>
                            <td className="py-2 px-4">¥{t.amount?.toLocaleString()}</td>
                            <td className="py-2 px-4 relative group">
                              {t.action === "BUY" ? (
                                <span className="text-gray-400 font-sans text-[11px]">— (待抛)</span>
                              ) : (() => {
                                const days = t.holding_days != null ? t.holding_days : 0;
                                const isBase = !!t.is_base_position;
                                const returnPct = t.trade_return_pct;
                                const entryPrice = t.entry_price;
                                const entryDate = t.entry_date;

                                let badgeClass = "bg-gray-100 text-gray-700 border-gray-200";
                                let badgeIcon = "⏳";
                                let badgeText = `${days}天`;

                                if (isBase) {
                                  badgeClass = "bg-amber-50 text-amber-800 border-amber-300";
                                  badgeIcon = "⏳";
                                  badgeText = days === 0 ? "0天 (底仓)" : `${days}天 (底仓)`;
                                } else if (days <= 2) {
                                  badgeClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
                                  badgeIcon = "⚡";
                                  badgeText = days === 0 ? "0天 (日内)" : `${days}天`;
                                } else if (days <= 7) {
                                  badgeClass = "bg-blue-50 text-blue-700 border-blue-200";
                                  badgeIcon = "🌊";
                                  badgeText = `${days}天`;
                                } else if (days <= 20) {
                                  badgeClass = "bg-indigo-50 text-indigo-700 border-indigo-200";
                                  badgeIcon = "⚓";
                                  badgeText = `${days}天`;
                                } else {
                                  badgeClass = "bg-amber-50 text-amber-800 border-amber-300";
                                  badgeIcon = "⏳";
                                  badgeText = `${days}天 (长波段)`;
                                }

                                const isTopRows = idx < 3;
                                const popoverPosition = isTopRows ? "top-full mt-2" : "bottom-full mb-2";

                                return (
                                  <>
                                    <div className="inline-flex items-center cursor-pointer">
                                      <span
                                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-sans font-semibold border ${badgeClass}`}
                                      >
                                        <span>{badgeIcon}</span>
                                        <span>{badgeText}</span>
                                      </span>
                                    </div>
                                    {/* 悬停浮动对账卡片 */}
                                    <div className={`absolute left-1/2 -translate-x-1/2 ${popoverPosition} hidden group-hover:block z-50 w-60 p-3 bg-gray-900/95 backdrop-blur-xs text-white text-xs rounded-xl shadow-2xl pointer-events-none transition-all border border-gray-700`}>
                                      <div className="font-bold border-b border-gray-700 pb-1 mb-1.5 flex items-center justify-between text-indigo-300 font-sans">
                                        <span>做 T 撮合配对详情</span>
                                        <span className="text-[10px] text-gray-400 font-mono">{t.slot_id || t.rail}</span>
                                      </div>
                                      <div className="space-y-1 font-mono text-[11px]">
                                        <div className="flex justify-between text-gray-300">
                                          <span className="font-sans text-gray-400">买入建仓:</span>
                                          <span>{entryDate || "..."} @ ¥{entryPrice != null ? Number(entryPrice).toFixed(3) : "—"}</span>
                                        </div>
                                        <div className="flex justify-between text-gray-300">
                                          <span className="font-sans text-gray-400">卖出平仓:</span>
                                          <span className="text-white font-bold">{t.trade_time.slice(0, 10)} @ ¥{Number(t.price).toFixed(3)}</span>
                                        </div>
                                        <div className="border-t border-gray-800 pt-1 mt-1 flex justify-between">
                                          <span className="font-sans text-gray-400">资金占用:</span>
                                          <span className="text-amber-300 font-bold">{days} 天 {isBase ? "(开网底仓)" : "(波段做T)"}</span>
                                        </div>
                                        <div className="flex justify-between">
                                          <span className="font-sans text-gray-400">价差净利:</span>
                                          <span className="text-emerald-400 font-bold">+¥{t.profit} {returnPct != null ? `(${returnPct > 0 ? "+" : ""}${returnPct}%)` : ""}</span>
                                        </div>
                                      </div>
                                    </div>
                                  </>
                                );
                              })()}
                            </td>
                            <td className="py-2 px-4 text-gray-400">¥{t.fee}</td>
                            <td className="py-2 px-4 font-bold text-red-600 font-sans">
                              {t.action === "SELL" ? `+¥${t.profit}` : "-"}
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* 分页控制栏 */}
                <div className="flex items-center justify-between text-xs text-gray-500 pt-1">
                  <div>
                    显示第 {(currentPage - 1) * pageSize + 1} -{" "}
                    {Math.min(currentPage * pageSize, filteredTrades.length)} 笔，共 {filteredTrades.length} 笔
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={currentPage <= 1}
                      onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                      className="px-2.5 py-1 rounded border border-gray-200 bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 font-medium"
                    >
                      上一页
                    </button>
                    <span className="font-mono">
                      {currentPage} / {totalPages}
                    </span>
                    <button
                      type="button"
                      disabled={currentPage >= totalPages}
                      onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                      className="px-2.5 py-1 rounded border border-gray-200 bg-white disabled:opacity-40 disabled:cursor-not-allowed hover:bg-gray-50 font-medium"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </>
        );
      })()}

      {/* 历史重大危机复盘诊断弹窗 */}
      <CrisisReplayModal
        isOpen={isCrisisModalOpen}
        onClose={() => setIsCrisisModalOpen(false)}
        crisisData={selectedCrisis}
        etfCode={etfCode}
        etfName={summary?.etf_name || etfCode}
      />
    </div>
  );
};

export default BacktestCard;
