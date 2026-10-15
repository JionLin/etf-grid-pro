import React, { useState, useEffect, useRef, useImperativeHandle, forwardRef, useCallback } from "react";
import { Settings, ChevronDown, ChevronUp, Sliders, Play } from "lucide-react";
import { usePersistedState } from "@shared/hooks";
import { validateETFCode, validateCapital } from "@shared/utils/validation";
import { checkDisclaimerStatus, acceptDisclaimer } from "@shared/utils/disclaimer";
import { getETFBasicInfo } from "@shared/services/api";
import DisclaimerModal from "../DisclaimerModal";

import BasicInstrumentSection from "./sections/BasicInstrumentSection";
import CapitalAnchorSection from "./sections/CapitalAnchorSection";
import StepModeSection from "./sections/StepModeSection";
import AdvancedStrategySection from "./sections/AdvancedStrategySection";
import StrategyPresetBar from "./StrategyPresetBar";
import {
  loadDraftSnapshot,
  saveDraftSnapshot,
  saveCustomPreset,
  deleteCustomPreset,
  resetToSystemDefault,
  DEFAULT_STRATEGY_PARAMS,
} from "@shared/utils/strategyDraftStorage";

/**
 * 参数表单容器组件 (支持渐进式披露与子组件解耦)
 */
const ParameterFormContainer = forwardRef(function ParameterFormContainer(
  { onAnalysis, loading, initialValues },
  ref,
) {
  // 1. 状态管理
  const [etfCode, setEtfCode] = usePersistedState("etfCode", initialValues?.etfCode || DEFAULT_STRATEGY_PARAMS.etfCode);
  const [totalCapital, setTotalCapital] = usePersistedState("totalCapital", initialValues?.totalCapital?.toString() || DEFAULT_STRATEGY_PARAMS.totalCapital);
  const [gridType, setGridType] = usePersistedState("gridType", initialValues?.gridType || DEFAULT_STRATEGY_PARAMS.gridType);
  const [riskPreference, setRiskPreference] = usePersistedState("riskPreference", initialValues?.riskPreference || DEFAULT_STRATEGY_PARAMS.riskPreference);
  const [adjustmentCoefficient, setAdjustmentCoefficient] = usePersistedState("adjustmentCoefficient", initialValues?.adjustmentCoefficient || DEFAULT_STRATEGY_PARAMS.adjustmentCoefficient);
  const [analysisDays, setAnalysisDays] = usePersistedState("analysisDays", initialValues?.analysisDays || DEFAULT_STRATEGY_PARAMS.analysisDays);
  const [reinvestMode, setReinvestMode] = usePersistedState("reinvestMode", initialValues?.reinvestMode || DEFAULT_STRATEGY_PARAMS.reinvestMode);
  const [scalingRatio, setScalingRatio] = usePersistedState("scalingRatio", initialValues?.scalingRatio !== undefined ? Number(initialValues.scalingRatio) : DEFAULT_STRATEGY_PARAMS.scalingRatio);
  const [enableScaling, setEnableScaling] = useState(initialValues?.enableScaling !== undefined ? Boolean(initialValues.enableScaling) : Boolean(DEFAULT_STRATEGY_PARAMS.enableScaling));
  const [stepMode, setStepMode] = usePersistedState("stepMode", initialValues?.stepMode || DEFAULT_STRATEGY_PARAMS.stepMode);
  const [edaSteps, setEdaSteps] = usePersistedState("edaSteps", initialValues?.edaSteps || { small: 5, medium: 15, large: 30 });
  const [atrMultipliers, setAtrMultipliers] = usePersistedState("atrMultipliers", initialValues?.atrMultipliers || { small: 0.6, medium: 1.2, large: 2.5 });
  const [benchmarkMode, setBenchmarkMode] = useState(initialValues?.benchmarkPrice ? "custom" : "market");
  const [customPrice, setCustomPrice] = useState(initialValues?.benchmarkPrice ? initialValues.benchmarkPrice.toString() : "");

  // 极客微调面板渐进式折叠状态
  const [isAdvancedExpanded, setIsAdvancedExpanded] = useState(false);
  const [draftSnapshot, setDraftSnapshot] = useState(() => loadDraftSnapshot());

  const handleApplyPreset = (preset) => {
    if (!preset?.params) return;
    const p = preset.params;
    if (p.totalCapital !== undefined) setTotalCapital(p.totalCapital.toString());
    if (p.stepMode !== undefined) setStepMode(p.stepMode);
    if (p.edaSteps !== undefined) setEdaSteps(p.edaSteps);
    if (p.atrMultipliers !== undefined) setAtrMultipliers(p.atrMultipliers);
    if (p.reinvestMode !== undefined) setReinvestMode(p.reinvestMode);
    if (p.scalingRatio !== undefined) {
      setScalingRatio(p.scalingRatio);
      setEnableScaling(Boolean(p.enableScaling || p.scalingRatio > 0));
    }
    if (p.analysisDays !== undefined) setAnalysisDays(p.analysisDays);
    if (p.gridType !== undefined) setGridType(p.gridType);
    if (p.riskPreference !== undefined) setRiskPreference(p.riskPreference);
    if (p.adjustmentCoefficient !== undefined) setAdjustmentCoefficient(p.adjustmentCoefficient);
    if (p.benchmarkMode !== undefined) setBenchmarkMode(p.benchmarkMode);
    if (p.customPrice !== undefined) setCustomPrice(p.customPrice);

    const updated = saveDraftSnapshot(p, preset.id);
    if (updated) setDraftSnapshot(updated);
  };

  const handleSaveCustomPreset = (name) => {
    const currentParams = {
      etfCode,
      totalCapital,
      stepMode,
      edaSteps,
      atrMultipliers,
      reinvestMode,
      scalingRatio,
      enableScaling,
      analysisDays,
      gridType,
      riskPreference,
      adjustmentCoefficient,
      benchmarkMode,
      customPrice,
    };
    const updated = saveCustomPreset(name, currentParams);
    if (updated) setDraftSnapshot(updated);
  };

  const handleDeleteCustomPreset = (id) => {
    const updated = deleteCustomPreset(id);
    if (updated) setDraftSnapshot(updated);
  };

  const handleResetDefault = () => {
    const reset = resetToSystemDefault();
    if (reset) {
      setDraftSnapshot(reset);
      setEtfCode("");
      handleApplyPreset({ id: "eda_classic", params: reset.current });
    }
  };

  const [capitalPresets, setCapitalPresets] = useState([]);
  const codeInputRef = useRef(null);
  const [etfInfo, setEtfInfo] = useState(null);
  const [etfLoading, setEtfLoading] = useState(false);
  const [errors, setErrors] = useState({});
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [pendingFormData, setPendingFormData] = useState(null);

  // 初始值同步
  useEffect(() => {
    if (initialValues) {
      if (initialValues.etfCode && initialValues.etfCode !== etfCode) setEtfCode(initialValues.etfCode);
      if (initialValues.totalCapital && initialValues.totalCapital.toString() !== totalCapital) setTotalCapital(initialValues.totalCapital.toString());
      if (initialValues.gridType && initialValues.gridType !== gridType) setGridType(initialValues.gridType);
      if (initialValues.riskPreference && initialValues.riskPreference !== riskPreference) setRiskPreference(initialValues.riskPreference);
      if (initialValues.adjustmentCoefficient && initialValues.adjustmentCoefficient !== adjustmentCoefficient) setAdjustmentCoefficient(initialValues.adjustmentCoefficient);
      if (initialValues.edaSteps) setEdaSteps(initialValues.edaSteps);
    }
  }, [initialValues]);

  // 暴露给外部调用者的 ref
  useImperativeHandle(ref, () => ({
    selectEtf(code, { shouldScroll = false } = {}) {
      const normalizedCode = String(code ?? "").replace(/\D/g, "").slice(0, 6);
      setEtfCode(normalizedCode);
      if (shouldScroll) {
        window.requestAnimationFrame(() => {
          const input = codeInputRef.current;
          if (!input) return;
          input.scrollIntoView({ behavior: "smooth", block: "center" });
          input.focus();
        });
      }
    },
  }), [setEtfCode]);

  // 资金预设拉取
  useEffect(() => {
    fetch("/api/capital-presets")
      .then((res) => res.json())
      .then((data) => {
        if (data.success) setCapitalPresets(data.data);
      })
      .catch((err) => console.warn("获取资金预设失败:", err));
  }, []);

  // 标的信息拉取
  const fetchETFInfo = useCallback(async (code) => {
    if (!validateETFCode(code)) {
      setEtfInfo(null);
      return;
    }
    setEtfLoading(true);
    try {
      const data = await getETFBasicInfo(code);
      if (data && data.success) {
        setEtfInfo(data.data);
      } else {
        setEtfInfo(null);
      }
    } catch (err) {
      if (err?.name !== "AbortError") {
        console.warn("获取ETF信息失败:", err);
      }
      setEtfInfo(null);
    } finally {
      setEtfLoading(false);
    }
  }, []);

  useEffect(() => {
    if (etfCode) fetchETFInfo(etfCode);
  }, [etfCode, fetchETFInfo]);

  // 表单验证
  const validateForm = () => {
    const newErrors = {};
    if (!etfCode) {
      newErrors.etfCode = "请输入ETF代码";
    } else if (!validateETFCode(etfCode)) {
      newErrors.etfCode = "请输入正确的6位ETF代码";
    }

    const capitalValidation = validateCapital(totalCapital);
    if (!capitalValidation.isValid) {
      newErrors.totalCapital = capitalValidation.message;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!validateForm()) return;

    const formData = {
      etfCode,
      totalCapital: parseFloat(totalCapital),
      gridType,
      riskPreference,
      adjustmentCoefficient: parseFloat(adjustmentCoefficient),
      analysisDays: parseInt(analysisDays, 10) || 180,
      scalingRatio: enableScaling ? parseFloat(scalingRatio) : 0.0,
      reinvestMode,
      stepMode,
      edaSteps: stepMode === "fixed_eda" ? edaSteps : undefined,
      edaStepRatios: stepMode === "fixed_eda" ? {
        small: Number(edaSteps?.small || 5) / 100,
        medium: Number(edaSteps?.medium || 15) / 100,
        large: Number(edaSteps?.large || 30) / 100,
      } : undefined,
      atrMultipliers: stepMode === "atr" ? atrMultipliers : undefined,
      benchmarkPrice: (benchmarkMode === "custom" && customPrice) ? parseFloat(customPrice) : null,
    };

    if (!checkDisclaimerStatus()) {
      setPendingFormData(formData);
      setShowDisclaimer(true);
      return;
    }

    onAnalysis(formData);
  };

  const handleDisclaimerAccept = () => {
    acceptDisclaimer();
    setShowDisclaimer(false);
    if (pendingFormData) {
      onAnalysis(pendingFormData);
      setPendingFormData(null);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-sm border border-gray-100 dark:border-gray-700 p-6 sm:p-8 space-y-6">
      {/* 头部标题区 */}
      <div className="flex items-center justify-between border-b border-gray-100 dark:border-gray-700 pb-4">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Settings className="w-5 h-5 text-blue-600" />
            <span>网格策略深度参数设计器</span>
          </h2>
          <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            支持 50:50 现金与底仓配比、ATR 自适应 / E大经典步长双模式与模式 B 免费股票池滚存
          </p>
        </div>
      </div>

      {/* 常用策略方案预设操作栏 (一键换档 / 另存为自定义 / 恢复默认) */}
      <StrategyPresetBar
        activePresetId={draftSnapshot?.activePresetId}
        customPresets={draftSnapshot?.customPresets || []}
        onSelectPreset={handleApplyPreset}
        onSaveCustomPreset={handleSaveCustomPreset}
        onDeleteCustomPreset={handleDeleteCustomPreset}
        onResetDefault={handleResetDefault}
      />

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 1. 常用基础层：标的识别区 */}
        <BasicInstrumentSection
          etfCode={etfCode}
          onChange={setEtfCode}
          error={errors.etfCode}
          etfInfo={etfInfo}
          loading={etfLoading}
          inputRef={codeInputRef}
        />

        {/* 2. 常用基础层：资金与价格锚点区 */}
        <CapitalAnchorSection
          totalCapital={totalCapital}
          onCapitalChange={setTotalCapital}
          capitalError={errors.totalCapital}
          capitalPresets={capitalPresets}
          benchmarkMode={benchmarkMode}
          onBenchmarkModeChange={setBenchmarkMode}
          customPrice={customPrice}
          onCustomPriceChange={setCustomPrice}
          etfInfo={etfInfo}
        />

        {/* 3. 渐进式披露控制条 (折叠 / 展开极客微调层) */}
        <div className="pt-2 border-t border-gray-100 dark:border-gray-700">
          <button
            type="button"
            onClick={() => setIsAdvancedExpanded(!isAdvancedExpanded)}
            className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-gray-750 hover:bg-slate-100 dark:hover:bg-gray-700 border border-slate-200/80 dark:border-gray-600 transition-all cursor-pointer group"
          >
            <div className="flex items-center gap-2">
              <div className="p-1.5 rounded-lg bg-blue-100 dark:bg-blue-950/80 text-blue-600 dark:text-blue-400">
                <Sliders className="w-4 h-4" />
              </div>
              <div className="text-left">
                <span className="text-xs font-bold text-gray-800 dark:text-gray-200">
                  {isAdvancedExpanded ? "收起高级极客策略微调" : "展开高级极客策略微调"}
                </span>
                {!isAdvancedExpanded && (
                  <div className="flex flex-wrap items-center gap-1.5 mt-1 text-[11px] text-gray-500 dark:text-gray-400">
                    <span className="bg-white dark:bg-gray-700 px-1.5 py-0.2 rounded border border-gray-200 dark:border-gray-600 font-mono">
                      {stepMode === "atr" ? "ATR自适应" : "E大原版大步长"}
                    </span>
                    <span className="bg-white dark:bg-gray-700 px-1.5 py-0.2 rounded border border-gray-200 dark:border-gray-600">
                      {reinvestMode === "pool_shares" ? "模式B留股" : "模式A留现金"}
                    </span>
                    <span className="bg-white dark:bg-gray-700 px-1.5 py-0.2 rounded border border-gray-200 dark:border-gray-600">
                      {enableScaling ? `倒金字塔+${Math.round(scalingRatio * 100)}%` : "各档等额"}
                    </span>
                    <span className="bg-white dark:bg-gray-700 px-1.5 py-0.2 rounded border border-gray-200 dark:border-gray-600 font-mono">
                      {analysisDays}天周期
                    </span>
                  </div>
                )}
              </div>
            </div>

            <div className="flex items-center gap-1 text-xs font-semibold text-blue-600 dark:text-blue-400 shrink-0">
              <span>{isAdvancedExpanded ? "收起" : "展开微调"}</span>
              {isAdvancedExpanded ? (
                <ChevronUp className="w-4 h-4" />
              ) : (
                <ChevronDown className="w-4 h-4" />
              )}
            </div>
          </button>
        </div>

        {/* 4. 极客高级策略微调区 (折叠面板展开时呈现) */}
        {isAdvancedExpanded && (
          <div className="space-y-6 pt-2 animate-in fade-in zoom-in-98 duration-200">
            <StepModeSection
              stepMode={stepMode}
              onStepModeChange={setStepMode}
              atrMultipliers={atrMultipliers}
              onAtrMultipliersChange={setAtrMultipliers}
              edaSteps={edaSteps}
              onEdaStepsChange={setEdaSteps}
            />

            <AdvancedStrategySection
              reinvestMode={reinvestMode}
              onReinvestModeChange={setReinvestMode}
              scalingRatio={scalingRatio}
              onScalingRatioChange={setScalingRatio}
              enableScaling={enableScaling}
              onEnableScalingChange={setEnableScaling}
              analysisDays={analysisDays}
              onAnalysisDaysChange={setAnalysisDays}
              gridType={gridType}
              onGridTypeChange={setGridType}
              riskPreference={riskPreference}
              onRiskPreferenceChange={setRiskPreference}
              adjustmentCoefficient={adjustmentCoefficient}
              onAdjustmentCoefficientChange={setAdjustmentCoefficient}
            />
          </div>
        )}

        {/* 5. 提交按钮 */}
        <div className="pt-4">
          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 bg-gradient-to-r from-blue-600 via-indigo-600 to-blue-700 hover:from-blue-700 hover:to-indigo-800 text-white font-bold text-sm rounded-xl shadow-md hover:shadow-lg transition-all flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50"
          >
            {loading ? (
              <span className="animate-spin mr-2">⏳</span>
            ) : (
              <Play className="w-4 h-4 fill-white" />
            )}
            <span>{loading ? "正在运行 5 年牛熊穿梭回测..." : "开始测算分析"}</span>
          </button>
        </div>
      </form>

      {/* 免责声明弹窗 */}
      <DisclaimerModal
        isOpen={showDisclaimer}
        onClose={() => setShowDisclaimer(false)}
        onAccept={handleDisclaimerAccept}
      />
    </div>
  );
});

export default ParameterFormContainer;
