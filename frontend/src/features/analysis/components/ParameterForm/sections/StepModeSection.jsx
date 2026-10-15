import React, { memo } from "react";
import { TrendingUp, Sliders, RotateCcw, Plus, Minus, AlertTriangle } from "lucide-react";
import { ATR_STEP_BUTTON_LABEL, EDA_STEP_BUTTON_LABEL } from "./stepModeLabels";

/**
 * 步长生成模式微调区组件
 * 包含：ATR 自适应乘数微调 与 E大原版经典大步长自定义微调
 */
const StepModeSection = memo(function StepModeSection({
  stepMode = "atr",
  onStepModeChange,
  atrMultipliers = { small: 0.6, medium: 1.2, large: 2.5 },
  onAtrMultipliersChange,
  edaSteps = { small: 5, medium: 15, large: 30 },
  onEdaStepsChange,
}) {
  // 1. 校验 ATR 乘数
  const getAtrMultiplierError = () => {
    if (stepMode !== "atr") return null;
    const s = Number(atrMultipliers?.small);
    const m = Number(atrMultipliers?.medium);
    const l = Number(atrMultipliers?.large);
    if (isNaN(s) || isNaN(m) || isNaN(l)) {
      return "请输入完整的乘数数值";
    }
    if (s < 0.2) return "小网乘数最低为 0.2x";
    if (s >= m) return `小网乘数 (${s}x) 必须小于中网乘数 (${m}x)`;
    if (m >= l) return `中网乘数 (${m}x) 必须小于大网乘数 (${l}x)`;
    if (l > 5.0) return "大网乘数最高为 5.0x";
    return null;
  };

  const atrMultiplierError = getAtrMultiplierError();

  const handleAtrMultiplierChange = (rail, delta) => {
    if (!onAtrMultipliersChange) return;
    const current = { ...(atrMultipliers || { small: 0.6, medium: 1.2, large: 2.5 }) };
    const currentVal = Number(current[rail]);
    const nextVal = Math.round((currentVal + delta) * 10) / 10;

    if (rail === "small") {
      if (delta > 0 && nextVal >= Number(current.medium)) return;
      if (delta < 0 && nextVal < 0.2) return;
    } else if (rail === "medium") {
      if (delta > 0 && nextVal >= Number(current.large)) return;
      if (delta < 0 && nextVal <= Number(current.small)) return;
    } else if (rail === "large") {
      if (delta > 0 && nextVal > 5.0) return;
      if (delta < 0 && nextVal <= Number(current.medium)) return;
    }

    onAtrMultipliersChange({
      ...current,
      [rail]: nextVal,
    });
  };

  // 2. 校验 E大步长
  const getEdaStepError = () => {
    if (stepMode !== "fixed_eda") return null;
    const s = Number(edaSteps?.small);
    const m = Number(edaSteps?.medium);
    const l = Number(edaSteps?.large);
    if (isNaN(s) || isNaN(m) || isNaN(l)) {
      return "请输入完整的步长百分比";
    }
    if (s >= m) return `小网步长 (${s}%) 必须小于中网步长 (${m}%)`;
    if (m >= l) return `中网步长 (${m}%) 必须小于大网步长 (${l}%)`;
    if (s < 1) return "小网步长最低为 1%";
    if (l > 50) return "大网步长最高为 50%";
    return null;
  };

  const edaStepError = getEdaStepError();

  const handleStepChange = (rail, delta) => {
    if (!onEdaStepsChange) return;
    const current = { ...(edaSteps || { small: 5, medium: 15, large: 30 }) };
    const nextVal = Math.max(1, Math.min(50, (Number(current[rail]) || 0) + delta));

    if (rail === "small" && nextVal >= Number(current.medium)) return;
    if (rail === "medium") {
      if (nextVal <= Number(current.small) || nextVal >= Number(current.large)) return;
    }
    if (rail === "large" && nextVal <= Number(current.medium)) return;

    onEdaStepsChange({
      ...current,
      [rail]: nextVal,
    });
  };

  const handleStepInput = (rail, rawVal) => {
    if (!onEdaStepsChange) return;
    const val = rawVal === "" ? "" : parseInt(rawVal, 10);
    onEdaStepsChange({
      ...(edaSteps || { small: 5, medium: 15, large: 30 }),
      [rail]: isNaN(val) ? "" : val,
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex justify-between items-center mb-1">
        <label className="flex items-center gap-2 text-sm font-medium text-gray-700 dark:text-gray-300">
          <TrendingUp className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
          步长生成模式
        </label>
        <span className="text-xs text-indigo-700 dark:text-indigo-400 font-medium">
          {stepMode === "fixed_eda"
            ? `🏛️ E大原版 ${edaSteps?.small || 5}%/${edaSteps?.medium || 15}%/${edaSteps?.large || 30}%`
            : `★ 🌊 ATR ${Number(atrMultipliers?.small ?? 0.6).toFixed(1)}x/${Number(atrMultipliers?.medium ?? 1.2).toFixed(1)}x/${Number(atrMultipliers?.large ?? 2.5).toFixed(1)}x`}
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={() => onStepModeChange && onStepModeChange("atr")}
          className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
            stepMode === "atr"
              ? "bg-indigo-50/90 border-indigo-500 text-indigo-900 ring-2 ring-indigo-400/40 font-bold shadow-xs dark:bg-indigo-950/60 dark:text-indigo-200"
              : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
          }`}
        >
          <div className="font-semibold text-xs text-indigo-950 dark:text-indigo-300 flex items-center gap-1">
            <span>{ATR_STEP_BUTTON_LABEL}</span>
          </div>
          <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
            基于14日波幅自适应计算(小网~1.9%/中网~3.8%/大网~7.9%)，适合高频做T现金流
          </div>
        </button>

        <button
          type="button"
          onClick={() => onStepModeChange && onStepModeChange("fixed_eda")}
          className={`py-2 px-3 text-xs font-medium rounded-lg border text-left transition-all ${
            stepMode === "fixed_eda"
              ? "bg-amber-50/90 border-amber-500 text-amber-900 ring-2 ring-amber-400/40 font-bold shadow-xs dark:bg-amber-950/60 dark:text-amber-200"
              : "bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:bg-gray-50"
          }`}
        >
          <div className="font-semibold text-xs text-amber-950 dark:text-amber-300 flex items-center gap-1">
            <span>{EDA_STEP_BUTTON_LABEL}</span>
          </div>
          <div className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
            默认小网 5% / 中网 15% / 大网 30%，跨度宏大、适合长周期守株待兔
          </div>
        </button>
      </div>

      {/* ATR 模式展开区 */}
      {stepMode === "atr" && (
        <div className="p-3 bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-200/90 dark:border-indigo-800/80 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between border-b border-indigo-200/70 dark:border-indigo-800/70 pb-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-indigo-950 dark:text-indigo-200">
              <Sliders className="w-3.5 h-3.5 text-indigo-700 dark:text-indigo-400" />
              <span>自定义三轨 ATR 波动率乘数</span>
              <span className="text-[10px] text-indigo-700/80 dark:text-indigo-400 font-normal">
                (小网 &lt; 中网 &lt; 大网)
              </span>
            </div>
            <button
              type="button"
              onClick={() => onAtrMultipliersChange && onAtrMultipliersChange({ small: 0.6, medium: 1.2, large: 2.5 })}
              className="inline-flex items-center gap-1 text-[11px] text-indigo-800 dark:text-indigo-300 hover:text-indigo-950 font-medium px-2 py-0.5 rounded bg-white dark:bg-gray-700 border border-indigo-300 dark:border-gray-600 transition-colors"
            >
              <RotateCcw className="w-3 h-3 text-indigo-700 dark:text-indigo-400" />
              <span>恢复默认</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {[
              { key: "small", label: "小网 (高频)", color: "bg-emerald-500", min: 0.2 },
              { key: "medium", label: "中网 (波段)", color: "bg-blue-500", min: 0.5 },
              { key: "large", label: "大网 (防守)", color: "bg-purple-500", min: 1.0 },
            ].map(({ key, label, color, min }) => (
              <div key={key} className="bg-white/90 dark:bg-gray-800 border border-indigo-200/80 dark:border-gray-700 rounded-lg p-2">
                <div className="flex items-center justify-between text-[11px] font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  <span className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${color}`}></span>
                    {label}
                  </span>
                  <span className="text-[10px] text-gray-400">底线 {min}x</span>
                </div>
                <div className="flex items-center justify-between gap-1">
                  <button
                    type="button"
                    onClick={() => handleAtrMultiplierChange(key, -0.1)}
                    className="w-7 h-7 flex items-center justify-center rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <span className="font-bold text-sm font-mono text-gray-900 dark:text-gray-100">
                    {Number(atrMultipliers?.[key] ?? 1.0).toFixed(1)}x
                  </span>
                  <button
                    type="button"
                    onClick={() => handleAtrMultiplierChange(key, 0.1)}
                    className="w-7 h-7 flex items-center justify-center rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {atrMultiplierError && (
            <div className="flex items-center gap-1 text-[11px] text-rose-600 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded px-2 py-1">
              <AlertTriangle className="w-3 h-3 shrink-0" />
              <span>{atrMultiplierError}</span>
            </div>
          )}
        </div>
      )}

      {/* E大模式展开区 */}
      {stepMode === "fixed_eda" && (
        <div className="p-3 bg-amber-50/70 dark:bg-amber-950/40 border border-amber-200/90 dark:border-amber-800/80 rounded-xl space-y-2.5">
          <div className="flex items-center justify-between border-b border-amber-200/70 dark:border-amber-800/70 pb-2">
            <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-950 dark:text-amber-200">
              <Sliders className="w-3.5 h-3.5 text-amber-700 dark:text-amber-400" />
              <span>自定义三轨大步长比例</span>
              <span className="text-[10px] text-amber-700/80 dark:text-amber-400 font-normal">
                (小网 &lt; 中网 &lt; 大网)
              </span>
            </div>
            <button
              type="button"
              onClick={() => onEdaStepsChange && onEdaStepsChange({ small: 5, medium: 15, large: 30 })}
              className="inline-flex items-center gap-1 text-[11px] text-amber-800 dark:text-amber-300 hover:text-amber-950 font-medium px-2 py-0.5 rounded bg-white dark:bg-gray-700 border border-amber-300 dark:border-gray-600 transition-colors"
            >
              <RotateCcw className="w-3 h-3 text-amber-700 dark:text-amber-400" />
              <span>恢复默认</span>
            </button>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
            {[
              { key: "small", label: "小网 (高频)", color: "bg-emerald-500", min: 1 },
              { key: "medium", label: "中网 (波段)", color: "bg-blue-500", min: 3 },
              { key: "large", label: "大网 (防守)", color: "bg-purple-500", min: 5 },
            ].map(({ key, label, color, min }) => (
              <div key={key} className="bg-white/90 dark:bg-gray-800 border border-amber-200/80 dark:border-gray-700 rounded-lg p-2">
                <div className="flex items-center justify-between text-[11px] font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  <span className="flex items-center gap-1">
                    <span className={`w-2 h-2 rounded-full ${color}`}></span>
                    {label}
                  </span>
                  <span className="text-[10px] text-gray-400">下限 {min}%</span>
                </div>
                <div className="flex items-center justify-between gap-1">
                  <button
                    type="button"
                    onClick={() => handleStepChange(key, -1)}
                    disabled={Number(edaSteps?.[key]) <= min}
                    className="w-7 h-7 flex items-center justify-center rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 disabled:opacity-30"
                  >
                    <Minus className="w-3.5 h-3.5" />
                  </button>
                  <div className="flex items-center justify-center flex-1">
                    <input
                      type="number"
                      value={edaSteps?.[key] ?? min}
                      onChange={(e) => handleStepInput(key, e.target.value)}
                      className="w-12 text-center font-bold text-sm text-gray-900 dark:text-gray-100 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded py-0.5"
                    />
                    <span className="text-xs text-gray-500 font-semibold ml-1">%</span>
                  </div>
                  <button
                    type="button"
                    onClick={() => handleStepChange(key, 1)}
                    className="w-7 h-7 flex items-center justify-center rounded border border-gray-200 dark:border-gray-600 bg-gray-50 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100"
                  >
                    <Plus className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))}
          </div>

          {edaStepError && (
            <div className="flex items-center gap-1 text-[11px] text-rose-600 bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 rounded px-2 py-1">
              <AlertTriangle className="w-3 h-3 shrink-0" />
              <span>{edaStepError}</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

export default StepModeSection;
