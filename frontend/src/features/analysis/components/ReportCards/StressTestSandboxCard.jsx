import React, { useState, useMemo } from "react";
import {
  ShieldAlert,
  ShieldCheck,
  Zap,
  TrendingDown,
  AlertTriangle,
  ArrowDown,
  ArrowUp,
  Sliders,
  Sparkles,
  Info,
  CheckCircle,
} from "lucide-react";
import {
  calculateStressTestScenario,
  STRESS_TEST_PRESETS,
  calculateRallyScenario,
  RALLY_TEST_PRESETS,
  deepestGridDropLabel,
} from "@shared/utils/stressTestCalculator";

/**
 * 极限行情压力测试沙盘组件（方案 A）
 * 紧接在网格阶梯表下方，为交易者提供面对极端暴跌的毫秒级抗风险推演
 */
const StressTestSandboxCard = ({
  compositeGrid,
  totalCapital = 30000,
  currentPrice = 1.0,
}) => {
  // 方向切换: "down" 下跌防穿透 | "up" 上涨防踏空
  const [direction, setDirection] = useState("down");

  // 当前推演跌幅百分比 (默认 20%)
  const [dropPct, setDropPct] = useState(20);

  // 当前推演涨幅百分比 (默认 20%)
  const [rallyPct, setRallyPct] = useState(20);

  // 毫秒级计算推演全量指标
  const result = useMemo(() => {
    return calculateStressTestScenario(
      compositeGrid,
      totalCapital,
      currentPrice,
      dropPct
    );
  }, [compositeGrid, totalCapital, currentPrice, dropPct]);

  // 上涨推演全量指标
  const rallyResult = useMemo(() => {
    return calculateRallyScenario(
      compositeGrid,
      totalCapital,
      currentPrice,
      rallyPct
    );
  }, [compositeGrid, totalCapital, currentPrice, rallyPct]);

  if (!compositeGrid || !result) {
    return null;
  }

  const buyOrders = (compositeGrid.merged_ladder || []).filter((item) => item.action === "BUY");
  const deepestBuyOrder = buyOrders.length > 0 ? buyOrders.reduce((min, o) => o.price < min.price ? o : min, buyOrders[0]) : null;
  const maxLadderDropPct = (deepestBuyOrder && currentPrice > 0)
    ? Number((((currentPrice - deepestBuyOrder.price) / currentPrice) * 100).toFixed(1))
    : null;
  const isDeepBreached = Boolean(maxLadderDropPct && dropPct > maxLadderDropPct);
  const deepestGridLabel = deepestGridDropLabel(currentPrice, compositeGrid.merged_ladder);

  const {
    targetPrice,
    consumedCash,
    remainingCash,
    liquidCapital,
    cashDrainRatio,
    cashBufferRatio,
    exhaustionDropPct,
    safetyLevel,
    safetyLabel,
    safetyBadgeColor,
    totalHoldingShares,
    avgCostPrice,
    costReductionPct,
    normalReboundNeeded,
    gridReboundNeeded,
    reboundAdvantage,
    railStats,
    triggeredOrdersCount,
    totalBuyOrdersCount,
  } = result;

  // 安全状态样式映射
  const badgeStyles = {
    emerald: "bg-emerald-100 text-emerald-800 border-emerald-300",
    amber: "bg-amber-100 text-amber-800 border-amber-300",
    orange: "bg-orange-100 text-orange-800 border-orange-300",
    red: "bg-red-100 text-red-800 border-red-300",
  }[safetyBadgeColor] || "bg-emerald-100 text-emerald-800 border-emerald-300";

  return (
    <div className="bg-gradient-to-b from-slate-50 to-white border border-slate-200 rounded-2xl p-6 shadow-xs space-y-6 mt-6">
      {/* 头部标题与 E大 理念背书 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-200/80 pb-5">
        <div className="flex items-center gap-3">
          <div className="p-2.5 bg-slate-900 rounded-xl text-white shadow-xs">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="text-lg font-bold text-gray-900">
                极限行情压力测试沙盘
                {deepestGridLabel ? (
                  <span className="ml-2 text-sm font-semibold text-slate-600">
                    {deepestGridLabel}
                  </span>
                ) : null}
              </h3>
              <span className="text-[11px] font-semibold bg-slate-100 text-slate-700 border border-slate-300 px-2 py-0.5 rounded-full">
                E大防穿透体系 · 毫秒级推演
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-0.5">
              模拟黑天鹅暴跌场景，测算流动资金抗风险底线、各轨击穿深度与绝地解套阈值
            </p>
          </div>
        </div>

        {/* 当前推演基准价 */}
        <div className="text-right self-start sm:self-auto font-mono text-xs text-gray-500 bg-white border border-gray-200 px-3 py-1.5 rounded-xl shadow-2xs">
          <span>基准现价: </span>
          <span className="font-bold text-gray-900 font-sans">
            ¥{Number(currentPrice).toFixed(3)}
          </span>
        </div>
      </div>

      {/* 方向切换 Tab */}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => setDirection("down")}
          className={`flex-1 py-2.5 px-4 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 border ${
            direction === "down"
              ? "bg-slate-900 text-white border-slate-900 shadow-xs"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
        >
          <ShieldAlert className="w-4 h-4" />
          🛡️ 下跌防穿透
        </button>
        <button
          type="button"
          onClick={() => setDirection("up")}
          className={`flex-1 py-2.5 px-4 rounded-xl text-sm font-bold transition-all flex items-center justify-center gap-2 border ${
            direction === "up"
              ? "bg-slate-900 text-white border-slate-900 shadow-xs"
              : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
          }`}
        >
          <ArrowUp className="w-4 h-4" />
          🚀 上涨防踏空
        </button>
      </div>

      {/* ========== 下跌防穿透面板 ========== */}
      {direction === "down" && (<>

      {/* 1. 交互推演控制区：情景预设胶囊 + 平滑跌幅滑块 */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-blue-600" />
            模拟标的自现价下挫幅度
          </span>
          <div className="flex items-baseline gap-1.5 font-mono">
            <span className="text-xs text-gray-500">推演目标价:</span>
            <span className="text-lg font-black text-red-600">
              ¥{targetPrice.toFixed(3)}
            </span>
            <span className="text-xs font-bold text-red-700">
              (-{dropPct}%)
            </span>
          </div>
        </div>

        {/* 5 大经典情景预设胶囊按钮 */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {STRESS_TEST_PRESETS.map((p) => {
            const isSelected = dropPct === p.drop;
            return (
              <button
                key={p.drop}
                type="button"
                onClick={() => setDropPct(p.drop)}
                title={p.desc}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium transition-all text-center flex flex-col items-center justify-center gap-0.5 border ${
                  isSelected
                    ? "bg-slate-900 text-white border-slate-900 shadow-xs ring-2 ring-slate-400/30 font-bold"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                <span>{p.label}</span>
                <span
                  className={`text-[10px] ${
                    isSelected ? "text-slate-300" : "text-gray-400"
                  }`}
                >
                  ¥{(currentPrice * (1 - p.drop / 100)).toFixed(3)}
                </span>
              </button>
            );
          })}
        </div>

        {/* 连续平滑滑块 */}
        <div className="pt-2">
          <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
            <span>0% (现价)</span>
            <span>-15%</span>
            <span>-30%</span>
            <span>-45%</span>
            <span>-60% (极限防守)</span>
          </div>
          <input
            type="range"
            min="0"
            max="60"
            step="1"
            value={dropPct}
            onChange={(e) => setDropPct(Number(e.target.value))}
            className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-slate-900 transition-all"
          />
        </div>

        {/* 超深筑底状态解释横幅 */}
        {isDeepBreached && (
          <div className="mt-3 p-3 bg-purple-50/90 border border-purple-200 rounded-xl flex items-start gap-2.5 text-xs text-purple-900 animate-fadeIn">
            <Info className="w-4 h-4 text-purple-600 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <div className="font-bold text-purple-950 flex items-center gap-2">
                <span>🛡️ 超深水淹满仓状态</span>
                <span className="text-[10px] bg-purple-100 text-purple-800 border border-purple-300 px-2 py-0.5 rounded-full font-mono">
                  网格最深防御: -{maxLadderDropPct}% (¥{deepestBuyOrder?.price?.toFixed(3)})
                </span>
              </div>
              <p className="text-[11px] text-purple-800 leading-relaxed">
                当前模拟跌幅（-{dropPct}%）已超出该网格预设的最深挂单（-{maxLadderDropPct}%）。系统已在 -{maxLadderDropPct}% 处将预留的流动资金全部转化为低价筹码完成满仓筑底，因此跌幅继续下挫至 -{dropPct}% 时<strong>无新增现金消耗</strong>，账户进入锁仓待机与均值回归反弹状态。
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 2. 四大核心安全态势仪表盘 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* 卡片 1: 资金消耗与余量 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>流动资金消耗 / 余量</span>
            <span className="text-[10px] text-gray-400">
              备用 ¥{liquidCapital.toLocaleString()}
            </span>
          </div>
          <div>
            <div className="text-xl font-black font-mono text-gray-900">
              ¥{consumedCash.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5 flex items-center justify-between">
              <span>尚余现金: ¥{remainingCash.toLocaleString()}</span>
              <span className="font-bold text-slate-700">
                {cashDrainRatio}% 已用
              </span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500 font-mono">
            {exhaustionDropPct !== null ? (
              <span>子弹耗尽临界: -{exhaustionDropPct}% (¥{result.exhaustionPrice})</span>
            ) : (
              <span className="text-emerald-700 font-medium">跌穿-60%资金依然安全</span>
            )}
          </div>
        </div>

        {/* 卡片 2: 综合持仓成本摊薄 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>加权持仓成本均价</span>
            <span className="text-[10px] text-emerald-600 font-bold">
              成本直降 -{costReductionPct}%
            </span>
          </div>
          <div>
            <div className="flex items-baseline gap-2">
              <span className="text-xl font-black font-mono text-emerald-700">
                ¥{avgCostPrice.toFixed(3)}
              </span>
              <span className="text-xs text-gray-400 line-through font-mono">
                ¥{Number(currentPrice).toFixed(3)}
              </span>
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5">
              累计持仓: {totalHoldingShares.toLocaleString()} 股
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500">
            底仓 {result.basePosition.shares}股 + 低吸 {totalHoldingShares - result.basePosition.shares}股
          </div>
        </div>

        {/* 卡片 3: 绝地脱困反弹阈值 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>自底部脱困所需涨幅</span>
            <Sparkles className="w-3.5 h-3.5 text-blue-600" />
          </div>
          <div>
            <div className="text-xl font-black font-mono text-blue-700">
              +{gridReboundNeeded}%
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5 flex items-center justify-between">
              <span>普通死拿需: +{normalReboundNeeded}%</span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-emerald-700 font-medium">
            网格优势: 少涨 +{reboundAdvantage}% 即可全盘解套
          </div>
        </div>

        {/* 卡片 4: 账户安全风控评级 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>账户风控安全评级</span>
            <span className="text-[10px] text-gray-400 font-mono">
              现金储备 {cashBufferRatio}%
            </span>
          </div>
          <div>
            <span
              className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold border ${badgeStyles}`}
            >
              {safetyLevel === "safe" && <CheckCircle className="w-3.5 h-3.5" />}
              {safetyLevel !== "safe" && <AlertTriangle className="w-3.5 h-3.5" />}
              {safetyLabel}
            </span>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500">
            已击穿买单: {triggeredOrdersCount} / {totalBuyOrdersCount} 档
          </div>
        </div>
      </div>

      {/* 3. 三轨水淹击穿热力图 (Liquid Depth Gauge) */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
            <span>三轨水淹击穿热力图</span>
            <span className="text-[11px] text-gray-500 font-normal">
              (水面下跌至 ¥{targetPrice.toFixed(3)} 时的各轨吸筹态势)
            </span>
          </h4>
          <span className="text-xs text-gray-500 font-mono">
            已吸收筹码: ¥{consumedCash.toLocaleString()}
          </span>
        </div>

        <div className="space-y-3">
          {/* 小网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-emerald-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                {railStats.small?.name}
              </span>
              <span className="font-mono text-gray-600">
                {railStats.small?.triggered} / {railStats.small?.total} 档击穿 ({railStats.small?.pct}%) · 投入 ¥{railStats.small?.cost?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${railStats.small?.pct}%` }}
              ></div>
            </div>
          </div>

          {/* 中网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-blue-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                {railStats.medium?.name}
              </span>
              <span className="font-mono text-gray-600">
                {railStats.medium?.triggered} / {railStats.medium?.total} 档击穿 ({railStats.medium?.pct}%) · 投入 ¥{railStats.medium?.cost?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${railStats.medium?.pct}%` }}
              ></div>
            </div>
          </div>

          {/* 大网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-purple-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                {railStats.large?.name}
              </span>
              <span className="font-mono text-gray-600">
                {railStats.large?.triggered} / {railStats.large?.total} 档击穿 ({railStats.large?.pct}%) · 投入 ¥{railStats.large?.cost?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-300"
                style={{ width: `${railStats.large?.pct}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      {/* 4. 脱困反弹阶梯标尺 (SVG 原生矢量渲染) */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs">
        <div className="flex items-center justify-between mb-3">
          <h4 className="font-bold text-gray-900 text-sm">
            绝地脱困反弹标尺对比
          </h4>
          <span className="text-xs text-gray-500">
            网格摊薄大幅缩短回本周期
          </span>
        </div>

        <div className="relative border border-slate-100 rounded-xl p-4 bg-slate-50/50">
          <div className="space-y-4 font-mono text-xs">
            {/* 顶线：现价 */}
            <div className="flex items-center justify-between text-gray-500 border-b border-gray-200 pb-1.5">
              <span>基准开网现价</span>
              <span className="font-bold text-gray-800 font-sans">
                ¥{Number(currentPrice).toFixed(3)}
              </span>
            </div>

            {/* 中线：网格摊薄均价 */}
            <div className="flex items-center justify-between text-emerald-800 bg-emerald-50/80 p-2 rounded-lg border border-emerald-200 font-sans">
              <span className="font-bold flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-600"></span>
                网格加权摊薄成本线 (只需反弹 +{gridReboundNeeded}%)
              </span>
              <span className="font-bold font-mono text-emerald-700">
                ¥{avgCostPrice.toFixed(3)}
              </span>
            </div>

            {/* 底线：模拟低点 */}
            <div className="flex items-center justify-between text-red-600 border-t border-gray-200 pt-1.5">
              <span className="flex items-center gap-1 font-sans">
                <ArrowDown className="w-3.5 h-3.5" />
                模拟暴跌极端低点 (-{dropPct}%)
              </span>
              <span className="font-bold font-mono">
                ¥{targetPrice.toFixed(3)}
              </span>
            </div>
          </div>

          <div className="mt-3 text-[11px] text-gray-500 bg-white p-2.5 rounded-lg border border-gray-200 flex items-center justify-between">
            <span>
              普通死拿回本需自低点反弹{" "}
              <strong className="text-gray-900 font-mono">+{normalReboundNeeded}%</strong>
            </span>
            <span className="text-emerald-700 font-bold">
              网格提前 +{reboundAdvantage}% 解套并启动大额纯盈利
            </span>
          </div>
        </div>
      </div>

      </>)}

      {/* ========== 上涨防踏空面板 ========== */}
      {direction === "up" && rallyResult && (<>

      {/* 1. 上涨交互推演控制区：情景预设胶囊 + 涨幅滑块 */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 space-y-4 shadow-2xs">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
            <Sliders className="w-3.5 h-3.5 text-emerald-600" />
            模拟标的自现价上涨幅度
          </span>
          <div className="flex items-baseline gap-1.5 font-mono">
            <span className="text-xs text-gray-500">推演目标价:</span>
            <span className="text-lg font-black text-emerald-600">
              ¥{rallyResult.targetPrice.toFixed(3)}
            </span>
            <span className="text-xs font-bold text-emerald-700">
              (+{rallyPct}%)
            </span>
          </div>
        </div>

        {/* 5 大上涨情景预设胶囊按钮 */}
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {RALLY_TEST_PRESETS.map((p) => {
            const isSelected = rallyPct === p.rally;
            return (
              <button
                key={p.rally}
                type="button"
                onClick={() => setRallyPct(p.rally)}
                title={p.desc}
                className={`py-2 px-2.5 rounded-xl text-xs font-medium transition-all text-center flex flex-col items-center justify-center gap-0.5 border ${
                  isSelected
                    ? "bg-slate-900 text-white border-slate-900 shadow-xs ring-2 ring-slate-400/30 font-bold"
                    : "bg-slate-50 text-slate-700 border-slate-200 hover:bg-slate-100"
                }`}
              >
                <span>{p.label}</span>
                <span
                  className={`text-[10px] ${
                    isSelected ? "text-slate-300" : "text-gray-400"
                  }`}
                >
                  ¥{(currentPrice * (1 + p.rally / 100)).toFixed(3)}
                </span>
              </button>
            );
          })}
        </div>

        {/* 连续平滑涨幅滑块 */}
        <div className="pt-2">
          <div className="flex items-center justify-between text-[11px] font-mono text-gray-400 mb-1">
            <span>0% (现价)</span>
            <span>+20%</span>
            <span>+40%</span>
            <span>+60%</span>
            <span>+80% (极限牛市)</span>
          </div>
          <input
            type="range"
            min="0"
            max="80"
            step="1"
            value={rallyPct}
            onChange={(e) => setRallyPct(Number(e.target.value))}
            className="w-full h-2.5 bg-slate-200 rounded-lg appearance-none cursor-pointer accent-emerald-700 transition-all"
          />
        </div>

        {/* 超轨休眠状态解释横幅 */}
        {rallyResult.isBeyondGrid && (
          <div className="mt-3 p-3 bg-amber-50/90 border border-amber-200 rounded-xl flex items-start gap-2.5 text-xs text-amber-900 animate-fadeIn">
            <Info className="w-4 h-4 text-amber-600 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              <div className="font-bold text-amber-950 flex items-center gap-2">
                <span>🏖️ 超轨休眠 · 全部止盈状态</span>
                <span className="text-[10px] bg-amber-100 text-amber-800 border border-amber-300 px-2 py-0.5 rounded-full font-mono">
                  网格最高卖出: +{rallyResult.soldOutRallyPct}% (¥{(() => { const so = (compositeGrid.merged_ladder || []).filter(i => i.action === "SELL").sort((a,b) => b.price - a.price); return so.length > 0 ? so[0].price.toFixed(3) : "—"; })()})
                </span>
              </div>
              <p className="text-[11px] text-amber-800 leading-relaxed">
                当前模拟涨幅（+{rallyPct}%）已超出该网格预设的最高卖单（+{rallyResult.soldOutRallyPct}%）。全套卖出网格已完成止盈，底仓筹码已全部变现为现金与利润池免费份额，网格进入休眠状态。如需捕获更高涨幅，可考虑加大网格区间或追设高位卖出轨。
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 2. 四大核心态势卡片 */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
        {/* 卡片 1: 筹码流失率 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>筹码流失率</span>
            <span className="text-[10px] text-gray-400">
              底仓 {rallyResult.basePosition.shares.toLocaleString()} 股
            </span>
          </div>
          <div>
            <div className="text-xl font-black font-mono text-gray-900">
              {rallyResult.chipLossRatio}%
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5 flex items-center justify-between">
              <span>已卖出: {rallyResult.triggeredSellShares.toLocaleString()} 股</span>
              <span className="font-bold text-slate-700">
                剩余 {rallyResult.remainingShares.toLocaleString()} 股
              </span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500 font-mono">
            {rallyResult.soldOutRallyPct !== null ? (
              <span>卖飞临界: +{rallyResult.soldOutRallyPct}%</span>
            ) : (
              <span className="text-emerald-700 font-medium">无卖出档位</span>
            )}
          </div>
        </div>

        {/* 卡片 2: 剩余持仓 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>剩余底仓持仓</span>
            {rallyResult.freeSharesFromProfit > 0 && (
              <span className="text-[10px] text-emerald-600 font-bold">
                +{rallyResult.freeSharesFromProfit} 免费股
              </span>
            )}
          </div>
          <div>
            <div className="text-xl font-black font-mono text-emerald-700">
              {rallyResult.remainingShares.toLocaleString()} 股
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5">
              {rallyResult.freeSharesFromProfit > 0 ? (
                <span>利润池可兑 {rallyResult.freeSharesFromProfit} 股免费份额 (模式B)</span>
              ) : (
                <span>利润池免费份额: 0 股</span>
              )}
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500">
            原始底仓 {rallyResult.basePosition.shares.toLocaleString()} 股 → 剩余 {(100 - rallyResult.chipLossRatio).toFixed(1)}%
          </div>
        </div>

        {/* 卡片 3: 累计做 T 利润 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>累计做 T 利润</span>
            <Sparkles className="w-3.5 h-3.5 text-emerald-600" />
          </div>
          <div>
            <div className="text-xl font-black font-mono text-emerald-700">
              ¥{rallyResult.totalProfit.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 font-mono mt-0.5">
              纯差价利润（卖高买低差额扣费后）
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500 font-mono">
            已触发卖单: {rallyResult.triggeredOrdersCount} / {rallyResult.totalSellOrdersCount} 档
          </div>
        </div>

        {/* 卡片 4: 回笼现金 & 安全评级 */}
        <div className="p-4 rounded-xl bg-white border border-slate-200 flex flex-col justify-between shadow-2xs">
          <div className="text-xs text-gray-500 flex items-center justify-between mb-1">
            <span>回笼现金 & 安全评级</span>
          </div>
          <div>
            <div className="text-xl font-black font-mono text-gray-900">
              ¥{rallyResult.returnedCash.toLocaleString()}
            </div>
            <div className="mt-1.5">
              <span
                className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-bold border ${
                  {
                    emerald: "bg-emerald-100 text-emerald-800 border-emerald-300",
                    sky: "bg-sky-100 text-sky-800 border-sky-300",
                    amber: "bg-amber-100 text-amber-800 border-amber-300",
                    red: "bg-red-100 text-red-800 border-red-300",
                  }[rallyResult.safetyBadgeColor] || "bg-emerald-100 text-emerald-800 border-emerald-300"
                }`}
              >
                {rallyResult.safetyLevel === "safe" && <CheckCircle className="w-3.5 h-3.5" />}
                {rallyResult.safetyLevel !== "safe" && <AlertTriangle className="w-3.5 h-3.5" />}
                {rallyResult.safetyLabel}
              </span>
            </div>
          </div>
          <div className="mt-2.5 pt-2 border-t border-gray-100 text-[11px] text-gray-500 font-mono">
            卖出金额: ¥{rallyResult.triggeredSellAmount.toLocaleString()}
          </div>
        </div>
      </div>

      {/* 3. 三轨卖出触发热力图 */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-2xs space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1">
          <h4 className="font-bold text-gray-900 text-sm flex items-center gap-2">
            <span>三轨卖出触发热力图</span>
            <span className="text-[11px] text-gray-500 font-normal">
              (涨至 ¥{rallyResult.targetPrice.toFixed(3)} 时的各轨止盈态势)
            </span>
          </h4>
          <span className="text-xs text-gray-500 font-mono">
            已止盈回笼: ¥{rallyResult.returnedCash.toLocaleString()}
          </span>
        </div>

        <div className="space-y-3">
          {/* 小网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-emerald-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                {rallyResult.railStats.small?.name}
              </span>
              <span className="font-mono text-gray-600">
                {rallyResult.railStats.small?.triggered} / {rallyResult.railStats.small?.total} 档止盈 ({rallyResult.railStats.small?.pct}%) · 利润 ¥{rallyResult.railStats.small?.profit?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-emerald-500 rounded-full transition-all duration-300"
                style={{ width: `${rallyResult.railStats.small?.pct}%` }}
              ></div>
            </div>
          </div>

          {/* 中网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-blue-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                {rallyResult.railStats.medium?.name}
              </span>
              <span className="font-mono text-gray-600">
                {rallyResult.railStats.medium?.triggered} / {rallyResult.railStats.medium?.total} 档止盈 ({rallyResult.railStats.medium?.pct}%) · 利润 ¥{rallyResult.railStats.medium?.profit?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-300"
                style={{ width: `${rallyResult.railStats.medium?.pct}%` }}
              ></div>
            </div>
          </div>

          {/* 大网 */}
          <div>
            <div className="flex items-center justify-between text-xs mb-1">
              <span className="font-semibold text-purple-800 flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                {rallyResult.railStats.large?.name}
              </span>
              <span className="font-mono text-gray-600">
                {rallyResult.railStats.large?.triggered} / {rallyResult.railStats.large?.total} 档止盈 ({rallyResult.railStats.large?.pct}%) · 利润 ¥{rallyResult.railStats.large?.profit?.toLocaleString()}
              </span>
            </div>
            <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-purple-500 rounded-full transition-all duration-300"
                style={{ width: `${rallyResult.railStats.large?.pct}%` }}
              ></div>
            </div>
          </div>
        </div>
      </div>

      </>)}

    </div>
  );
};

export default StressTestSandboxCard;
