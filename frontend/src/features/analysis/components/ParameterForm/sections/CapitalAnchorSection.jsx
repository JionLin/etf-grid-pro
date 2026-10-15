import React, { memo } from "react";
import { Anchor } from "lucide-react";
import CapitalInput from "../../CapitalInput";
import { anchorModeLabel } from "../anchorRequest";

/**
 * 资金与价格锚点设置区组件
 */
const CapitalAnchorSection = memo(function CapitalAnchorSection({
  totalCapital,
  onCapitalChange,
  capitalError,
  capitalPresets = [],
  benchmarkMode = "market",
  onBenchmarkModeChange,
  customPrice = "",
  onCustomPriceChange,
  valuationPercentile = "50",
  onValuationPercentileChange,
  dualMaPrice = "",
  onDualMaPriceChange,
  etfInfo,
}) {
  return (
    <div className="space-y-4">
      {/* 1. 基准价格锚点设置 (最新市价 vs 自定义持仓成本价) */}
      <div>
        <div className="flex justify-between items-center mb-2">
          <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
            <Anchor className="w-4 h-4 text-blue-600 dark:text-blue-400" />
            网格基准价格 (P₀ 锚点)
          </label>
          <span className="text-xs text-blue-700 dark:text-blue-400 font-medium">
            {anchorModeLabel(benchmarkMode)}
          </span>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onBenchmarkModeChange && onBenchmarkModeChange("market")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              benchmarkMode === "market"
                ? "bg-blue-50/90 border-blue-500 text-blue-900 ring-2 ring-blue-400/40 font-bold shadow-xs dark:bg-blue-950/60 dark:text-blue-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs text-blue-950 dark:text-blue-300 flex items-center gap-1">
              <span>⚡ 盘中最新价 (默认)</span>
            </div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              {etfInfo?.current_price ? `当前现价约 ¥${etfInfo.current_price}` : "自动获取当日最新市场价格"}
            </div>
          </button>

          <button
            type="button"
            onClick={() => onBenchmarkModeChange && onBenchmarkModeChange("custom")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              benchmarkMode === "custom"
                ? "bg-amber-50/90 border-amber-500 text-amber-900 ring-2 ring-amber-400/40 font-bold shadow-xs dark:bg-amber-950/60 dark:text-amber-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs text-amber-950 dark:text-amber-300 flex items-center gap-1">
              <span>✏️ 自定义成本/心理价</span>
            </div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              按自有持仓成本或心仪点位铺设网格
            </div>
          </button>
          <button
            type="button"
            onClick={() => onBenchmarkModeChange && onBenchmarkModeChange("percentile")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              benchmarkMode === "percentile"
                ? "bg-violet-50/90 border-violet-500 text-violet-900 ring-2 ring-violet-400/40 font-bold shadow-xs dark:bg-violet-950/60 dark:text-violet-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs">手填估值分位</div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              用本次区间收盘价的分位做锚点，不是指数估值
            </div>
          </button>
          <button
            type="button"
            onClick={() => onBenchmarkModeChange && onBenchmarkModeChange("dual_ma")}
            className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
              benchmarkMode === "dual_ma"
                ? "bg-teal-50/90 border-teal-500 text-teal-900 ring-2 ring-teal-400/40 font-bold shadow-xs dark:bg-teal-950/60 dark:text-teal-200"
                : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
            }`}
          >
            <div className="font-semibold text-xs">双均价格</div>
            <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
              手填双均价；留空则用 20 日与 60 日均价的平均
            </div>
          </button>
        </div>

        {benchmarkMode === "custom" && (
          <div className="mt-2.5 p-2.5 bg-amber-50/70 dark:bg-amber-950/40 border border-amber-300 dark:border-amber-700 rounded-lg flex items-center gap-3">
            <span className="text-xs font-medium text-amber-900 dark:text-amber-200 shrink-0">
              自定义基准价 (元):
            </span>
            <input
              type="number"
              step="0.001"
              min="0.01"
              placeholder={etfInfo?.current_price ? etfInfo.current_price.toString() : "例如 1.250"}
              value={customPrice}
              onChange={(e) => onCustomPriceChange && onCustomPriceChange(e.target.value)}
              className="w-36 px-2.5 py-1 text-xs font-mono font-bold bg-white dark:bg-gray-700 border border-amber-400 dark:border-amber-600 rounded focus:ring-1 focus:ring-amber-500 focus:outline-none text-gray-900 dark:text-gray-100"
            />
            <span className="text-[11px] text-amber-800 dark:text-amber-300">
              以该价格为中心向上挂卖单、向下挂买单
            </span>
          </div>
        )}
        {benchmarkMode === "percentile" && (
          <div className="mt-2.5 p-2.5 bg-violet-50/70 dark:bg-violet-950/40 border border-violet-300 dark:border-violet-700 rounded-lg flex items-center gap-3">
            <span className="text-xs font-medium text-violet-900 dark:text-violet-200 shrink-0">
              收盘价分位 (0-100):
            </span>
            <input
              type="number"
              step="1"
              min="0"
              max="100"
              value={valuationPercentile}
              onChange={(e) => onValuationPercentileChange && onValuationPercentileChange(e.target.value)}
              className="w-24 px-2.5 py-1 text-xs font-mono font-bold bg-white dark:bg-gray-700 border border-violet-400 rounded text-gray-900 dark:text-gray-100"
            />
            <span className="text-[11px] text-violet-800 dark:text-violet-300">
              0 是区间最低收盘，100 是最高收盘
            </span>
          </div>
        )}
        {benchmarkMode === "dual_ma" && (
          <div className="mt-2.5 p-2.5 bg-teal-50/70 dark:bg-teal-950/40 border border-teal-300 dark:border-teal-700 rounded-lg flex items-center gap-3">
            <span className="text-xs font-medium text-teal-900 dark:text-teal-200 shrink-0">
              双均价格 (元):
            </span>
            <input
              type="number"
              step="0.001"
              min="0.01"
              placeholder="留空自动计算"
              value={dualMaPrice}
              onChange={(e) => onDualMaPriceChange && onDualMaPriceChange(e.target.value)}
              className="w-36 px-2.5 py-1 text-xs font-mono font-bold bg-white dark:bg-gray-700 border border-teal-400 rounded text-gray-900 dark:text-gray-100"
            />
          </div>
        )}
      </div>

      {/* 2. 资金输入 */}
      <CapitalInput
        value={totalCapital}
        onChange={onCapitalChange}
        error={capitalError}
        presets={capitalPresets}
      />
    </div>
  );
});

export default CapitalAnchorSection;
