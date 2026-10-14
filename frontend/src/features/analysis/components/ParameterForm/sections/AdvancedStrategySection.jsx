import React, { memo } from "react";
import { PiggyBank, Layers, Sparkles, Clock } from "lucide-react";
import GridTypeSelector from "../../GridTypeSelector";
import RiskSelector from "../../RiskSelector";
import AdjustmentCoefficientSlider from "../../AdjustmentCoefficientSlider";

/**
 * 极客进阶策略配置区组件
 * 包含：做T收益留存模式(模式B/A)、逢跌倒金字塔加码、网格等比/等差、偏好调节与回测天数
 */
const AdvancedStrategySection = memo(function AdvancedStrategySection({
  reinvestMode = "pool_shares",
  onReinvestModeChange,
  scalingRatio = 0.1,
  onScalingRatioChange,
  enableScaling = true,
  onEnableScalingChange,
  analysisDays = 180,
  onAnalysisDaysChange,
  gridType = "等比",
  onGridTypeChange,
  riskPreference = "均衡",
  onRiskPreferenceChange,
  adjustmentCoefficient = 1.0,
  onAdjustmentCoefficientChange,
}) {
  return (
    <div className="space-y-4 pt-1">
      {/* 1. 做 T 收益处理机制 (E大 2.1 留利润) */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <PiggyBank className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
            做 T 收益留存机制 (E大 2.1)
          </label>
          <span className="text-xs text-emerald-700 dark:text-emerald-400 font-medium">
            {reinvestMode === "pool_shares" ? "★ 聚沙成塔 · 滚存0成本份额" : "落袋为安 · 全现金"}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onReinvestModeChange && onReinvestModeChange("pool_shares")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              reinvestMode === "pool_shares"
                ? "bg-emerald-50/90 border-emerald-500 text-emerald-800 ring-2 ring-emerald-400/40 font-bold shadow-xs dark:bg-emerald-950/60 dark:text-emerald-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="flex items-center gap-1.5 font-semibold text-xs text-emerald-900 dark:text-emerald-300">
              <Sparkles className="w-3.5 h-3.5 text-emerald-600 dark:text-emerald-400" />
              智能利润滚存 (推荐)
            </div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              每攒满100股自动沉淀为0成本锁仓份额
            </div>
          </button>
          <button
            type="button"
            onClick={() => onReinvestModeChange && onReinvestModeChange("cash")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              reinvestMode === "cash"
                ? "bg-blue-50/90 border-blue-500 text-blue-800 ring-2 ring-blue-400/40 font-bold shadow-xs dark:bg-blue-950/60 dark:text-blue-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs text-gray-900 dark:text-gray-200">
              💰 全额落袋现金
            </div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              经典1.0模式，差价利润全额收回为可用现金
            </div>
          </button>
        </div>
      </div>

      {/* 2. 逢跌买入节奏 (E大 2.2 逐格加码) */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Layers className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            逢跌买入节奏 (E大 2.2 逐格加码)
          </label>
          <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
            {enableScaling ? `倒金字塔递增 +${Math.round(scalingRatio * 100)}%` : "各档等额买入 (0%)"}
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2 mb-2">
          <button
            type="button"
            onClick={() => {
              if (onEnableScalingChange) onEnableScalingChange(false);
              if (onScalingRatioChange) onScalingRatioChange(0.0);
            }}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-center transition-all ${
              !enableScaling
                ? "bg-blue-50/90 border-blue-500 text-blue-700 ring-2 ring-blue-400/40 font-bold shadow-xs dark:bg-blue-950/60 dark:text-blue-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs">⚖️ 各档等额 (默认 0%)</div>
            <div className="text-[10px] text-gray-400 mt-0.5">平分流动资金，风险均匀分布</div>
          </button>
          <button
            type="button"
            onClick={() => {
              if (onEnableScalingChange) onEnableScalingChange(true);
              if (Number(scalingRatio) === 0 && onScalingRatioChange) {
                onScalingRatioChange(0.10);
              }
            }}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-center transition-all ${
              enableScaling
                ? "bg-purple-50/90 border-purple-500 text-purple-800 ring-2 ring-purple-400/40 font-bold shadow-xs dark:bg-purple-950/60 dark:text-purple-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs">📐 逐格加码 (倒金字塔)</div>
            <div className="text-[10px] text-gray-400 mt-0.5">越跌买越多，极速摊薄持仓成本</div>
          </button>
        </div>

        {enableScaling && (
          <div className="p-3 bg-purple-50/50 dark:bg-purple-950/40 rounded-xl border border-purple-200 dark:border-purple-800 space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-purple-900 dark:text-purple-200 font-medium">每格递增资金比例：</span>
              <span className="font-mono font-bold text-purple-700 dark:text-purple-300">
                +{Math.round(scalingRatio * 100)}%
              </span>
            </div>
            <input
              type="range"
              min="0.05"
              max="0.20"
              step="0.01"
              value={scalingRatio}
              onChange={(e) => onScalingRatioChange && onScalingRatioChange(parseFloat(e.target.value))}
              className="w-full h-2 bg-purple-200 rounded-lg appearance-none cursor-pointer accent-purple-600"
            />
            <div className="flex items-center justify-between gap-1.5 text-[11px]">
              {[
                { val: 0.05, label: "5% (温和)" },
                { val: 0.10, label: "★ 10% (推荐)" },
                { val: 0.20, label: "20% (激进大底)" },
              ].map(({ val, label }) => (
                <button
                  key={val}
                  type="button"
                  onClick={() => onScalingRatioChange && onScalingRatioChange(val)}
                  className={`px-2 py-0.5 rounded border transition-all ${
                    scalingRatio === val
                      ? "bg-purple-600 text-white font-bold"
                      : "bg-white dark:bg-gray-750 text-purple-700 dark:text-purple-300 border-purple-200 dark:border-purple-800"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* 3. 网格类型与风险偏好 */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <GridTypeSelector value={gridType} onChange={onGridTypeChange} />
        <RiskSelector value={riskPreference} onChange={onRiskPreferenceChange} />
      </div>

      {/* 4. 调节系数 */}
      <AdjustmentCoefficientSlider
        value={adjustmentCoefficient}
        onChange={onAdjustmentCoefficientChange}
      />

      {/* 5. 历史分析周期选择器 */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Clock className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            历史分析周期
          </label>
          <span className="text-xs text-gray-500 dark:text-gray-400 font-normal">
            {analysisDays === 1825
              ? "5 年全量"
              : analysisDays === 180
              ? "★ 推荐黄金平衡 (半年)"
              : analysisDays === 90
              ? "⚡ 短线高频波动"
              : analysisDays === 365
              ? "🛡️ 52周大箱体"
              : `${analysisDays} 天`}
          </span>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
          {[
            { days: 90, label: "90 天", sub: "高频做T · 灵敏" },
            { days: 180, label: "180 天 (默认)", sub: "★ 黄金平衡 · 半年" },
            { days: 365, label: "365 天", sub: "年度大箱体 · 防守" },
            { days: 1825, label: "1825 天", sub: "5 年全量" },
          ].map(({ days, label, sub }) => (
            <button
              key={days}
              type="button"
              onClick={() => onAnalysisDaysChange && onAnalysisDaysChange(days)}
              className={`py-2 px-3 text-xs font-medium rounded-lg border text-center transition-all ${
                analysisDays === days
                  ? "bg-blue-50/90 border-blue-500 text-blue-700 ring-2 ring-blue-400/50 font-bold shadow-xs dark:bg-blue-950/60 dark:text-blue-200"
                  : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
              }`}
            >
              <div className="font-semibold text-xs">{label}</div>
              <div className="text-[10px] opacity-75 mt-0.5">{sub}</div>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
});

export default AdvancedStrategySection;
