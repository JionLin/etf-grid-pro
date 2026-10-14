import React, { useState, useEffect } from "react";
import { ArrowRight, Sliders, X, Check } from "lucide-react";

/**
 * 桌面端快速策略驾驶舱 (QuickConfigPanel)
 * 作用：在 PC 桌面端提供选品后的即时原地调参能力，实现 0 像素滚动即刻启动回测
 */
export default function QuickConfigPanel({
  selectedEtf,
  onClose,
  onLaunch,
  onOpenFullForm,
}) {
  // 核心微调参数状态
  const [capital, setCapital] = useState(30000);
  const [stepMode, setStepMode] = useState("atr"); // 'atr' | 'fixed_eda'
  const [reinvestMode, setReinvestMode] = useState("pool_shares"); // 'pool_shares' | 'cash'

  // 当外部选中的标的改变时，同步内部显示
  useEffect(() => {
    if (selectedEtf?.code || selectedEtf?.etf_code) {
      // 保持当前用户调整的资金与模式设置，仅更新标的
    }
  }, [selectedEtf]);

  if (!selectedEtf) {
    return (
      <div className="h-full min-h-[380px] bg-slate-50/80 dark:bg-gray-800/50 border-2 border-dashed border-gray-200 dark:border-gray-700 rounded-2xl p-6 flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-2xl bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 flex items-center justify-center mb-3">
          <Sliders className="w-6 h-6" />
        </div>
        <h3 className="font-bold text-gray-800 dark:text-gray-200 text-sm mb-1">
          桌面快速策略驾驶舱
        </h3>
        <p className="text-xs text-gray-400 dark:text-gray-500 max-w-[220px]">
          在左侧选品雷达点击任意标的卡片，即刻在此处微调参数并一键启动回测
        </p>
      </div>
    );
  }

  const code = selectedEtf.etf_code || selectedEtf.code;
  const name = selectedEtf.name || code;
  const price = selectedEtf.latest_price ? Number(selectedEtf.latest_price).toFixed(3) : "--";
  const pct = selectedEtf.pct_change !== undefined ? Number(selectedEtf.pct_change).toFixed(2) : null;
  const isUp = pct !== null ? Number(pct) >= 0 : true;

  const handleStartBacktest = () => {
    if (!onLaunch) return;
    onLaunch({
      etfCode: code,
      totalCapital: capital,
      stepMode,
      reinvestMode: reinvestMode || "pool_shares",
      scalingRatio: 0.1, // 与回测矩阵倒金字塔加码 10% 对齐
      gridType: "等比",
      riskPreference: "均衡",
      adjustmentCoefficient: 1.0,
      analysisDays: 1825, // 默认5年全量回测
    });
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-blue-200/80 dark:border-blue-900/60 p-5 space-y-4 flex flex-col justify-between h-full animate-in fade-in duration-200">
      <div className="space-y-4">
        {/* 顶部标的行情区 */}
        <div className="flex items-start justify-between border-b border-gray-100 dark:border-gray-700 pb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-black text-gray-900 dark:text-gray-100 text-lg">
                {code}
              </span>
              <span className="font-bold text-gray-800 dark:text-gray-200 text-sm">
                {name}
              </span>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs font-mono font-semibold text-gray-700 dark:text-gray-300">
                最新: ¥{price}
                {selectedEtf.quote_date ? ` (${selectedEtf.quote_date})` : ""}
              </span>
              {pct !== null && (
                <span
                  className={`text-xs font-mono font-bold ${
                    isUp ? "text-rose-500" : "text-emerald-500"
                  }`}
                >
                  {isUp ? "+" : ""}{pct}%
                </span>
              )}
              {selectedEtf.sector && (
                <span className="text-[10px] px-1.5 py-0.2 bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400 rounded font-medium">
                  {selectedEtf.sector}
                </span>
              )}
            </div>
          </div>

          {onClose && (
            <button
              type="button"
              onClick={onClose}
              className="p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              title="收起驾驶舱"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* 1. 计划总投入本金 */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs font-bold text-gray-700 dark:text-gray-300">
            <span>💰 计划总本金</span>
            <span className="font-mono text-blue-600 dark:text-blue-400">
              ¥{capital.toLocaleString()}
            </span>
          </div>

          <div className="grid grid-cols-4 gap-1.5">
            {[30000, 50000, 100000, 200000].map((val) => (
              <button
                key={val}
                type="button"
                onClick={() => setCapital(val)}
                className={`py-1.5 text-xs font-mono font-semibold rounded-lg border transition-all ${
                  capital === val
                    ? "bg-blue-600 text-white border-blue-600 shadow-xs"
                    : "bg-gray-50 dark:bg-gray-700/60 text-gray-700 dark:text-gray-300 border-gray-200 dark:border-gray-600 hover:bg-gray-100"
                }`}
              >
                {val / 10000}万
              </button>
            ))}
          </div>
        </div>

        {/* 2. 网格步长生成模式 */}
        <div className="space-y-1.5">
          <span className="text-xs font-bold text-gray-700 dark:text-gray-300 block">
            📐 网格步长模式
          </span>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setStepMode("atr")}
              className={`p-2.5 rounded-xl border text-left transition-all relative ${
                stepMode === "atr"
                  ? "bg-indigo-50/80 dark:bg-indigo-950/40 border-indigo-400 text-indigo-900 dark:text-indigo-200 shadow-2xs"
                  : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between font-bold text-xs">
                <span>ATR 自适应</span>
                {stepMode === "atr" && <Check className="w-3.5 h-3.5 text-indigo-600" />}
              </div>
              <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                日频波动率动态挂单
              </p>
            </button>

            <button
              type="button"
              onClick={() => setStepMode("fixed_eda")}
              className={`p-2.5 rounded-xl border text-left transition-all relative ${
                stepMode === "fixed_eda"
                  ? "bg-amber-50/80 dark:bg-amber-950/40 border-amber-400 text-amber-950 dark:text-amber-200 shadow-2xs"
                  : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between font-bold text-xs">
                <span>E大经典步长</span>
                {stepMode === "fixed_eda" && <Check className="w-3.5 h-3.5 text-amber-600" />}
              </div>
              <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                5% / 15% / 30% 三轨
              </p>
            </button>
          </div>
        </div>

        {/* 3. 差价收益留存模式 */}
        <div className="space-y-1.5">
          <span className="text-xs font-bold text-gray-700 dark:text-gray-300 block">
            🛡️ 做 T 收益处置
          </span>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setReinvestMode("pool_shares")}
              className={`p-2.5 rounded-xl border text-left transition-all ${
                reinvestMode === "pool_shares"
                  ? "bg-blue-50/80 dark:bg-blue-950/40 border-blue-400 text-blue-900 dark:text-blue-200 shadow-2xs"
                  : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between font-bold text-xs">
                <span>模式 B (留股)</span>
                {reinvestMode === "pool_shares" && (
                  <Check className="w-3.5 h-3.5 text-blue-600" />
                )}
              </div>
              <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                自动滚存 0 成本股票池
              </p>
            </button>

            <button
              type="button"
              onClick={() => setReinvestMode("cash")}
              className={`p-2.5 rounded-xl border text-left transition-all ${
                reinvestMode === "cash"
                  ? "bg-slate-100 dark:bg-slate-700 border-slate-400 text-slate-900 dark:text-slate-100 shadow-2xs"
                  : "border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between font-bold text-xs">
                <span>模式 A (现金)</span>
                {reinvestMode === "cash" && <Check className="w-3.5 h-3.5 text-slate-700" />}
              </div>
              <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                差价纯利润全留现金
              </p>
            </button>
          </div>
        </div>
      </div>

      {/* 底部启动按钮与辅助入口 */}
      <div className="space-y-2 pt-2 border-t border-gray-100 dark:border-gray-700">
        <button
          type="button"
          onClick={handleStartBacktest}
          className="w-full py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-bold text-sm rounded-xl shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 group cursor-pointer"
        >
          <span>🚀 立即启动 5 年牛熊回测</span>
          <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-1" />
        </button>

        {onOpenFullForm && (
          <button
            type="button"
            onClick={onOpenFullForm}
            className="w-full py-1 text-center text-[11px] text-gray-400 hover:text-blue-600 dark:hover:text-blue-400 font-medium transition-colors"
          >
            高级策略微调 (倒金字塔加码 / 三轨乘数) ▼
          </button>
        )}
      </div>
    </div>
  );
}
