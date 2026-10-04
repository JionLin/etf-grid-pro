import React, { useState, useEffect, useRef } from "react";
import { LoadingSpinner } from "@shared/components/ui";
import { useShare } from "@shared/hooks";
import ReportTabs from "./ReportTabs";
import OverviewTab from "./OverviewTab";
import ErrorState from "./ErrorState";
import Disclaimer from "./Disclaimer";
import SuitabilityCard from "./ReportCards/SuitabilityCard";
import GridParametersCard from "./ReportCards/GridParametersCard";
import BacktestCard from "./ReportCards/BacktestCard";
import BacktestArchiveView from "./ReportCards/BacktestArchiveView";

/**
 * 分析报告容器组件
 * 负责协调各个报告子组件和状态管理
 */
const BACKTEST_TABS = new Set(["overview", "strategy", "backtest"]);

function buildBacktestProps(backtestParams, derived) {
  const source = backtestParams?.etfCode ? backtestParams : derived;
  if (!source?.etfCode && !source?.etf_code) return null;
  return {
    etfCode: source.etfCode || source.etf_code,
    totalCapital: source.totalCapital ?? source.total_capital,
    initialDays: source.analysisDays ?? source.analysis_days ?? source.initialDays,
    reinvestMode: source.reinvestMode || source.reinvest_mode,
    scalingRatio: source.scalingRatio ?? source.scaling_ratio,
    stepMode: source.stepMode || source.step_mode,
    edaStepRatios: source.edaStepRatios || source.eda_step_ratios || null,
    edaSteps: source.edaSteps || null,
    atrMultipliers: source.atrMultipliers || source.atr_multipliers || null,
  };
}

const AnalysisReport = ({
  data,
  loading,
  backtestParams,
  onBackToInput,
  onReAnalysis,
  onApplyArchiveParams,
  onHistoryMeta,
}) => {
  const [activeTab, setActiveTab] = useState("overview");
  const { shareContent } = useShare();
  const giscusRef = useRef(null);

  // 加载 Giscus 评论组件
  useEffect(() => {
    if (data && !data.error && giscusRef.current) {
      // 清除之前的 Giscus 实例
      giscusRef.current.innerHTML = '';
      
      // 创建 Giscus 脚本
      const script = document.createElement('script');
      script.src = 'https://giscus.app/client.js';
      script.setAttribute('data-repo', 'jorben/etf-grid-design');
      script.setAttribute('data-repo-id', 'R_kgDOPzq5AA');
      script.setAttribute('data-category', 'General');
      script.setAttribute('data-category-id', 'DIC_kwDOPzq5AM4Cv-y9');
      script.setAttribute('data-mapping', 'title');
      script.setAttribute('data-strict', '0');
      script.setAttribute('data-reactions-enabled', '1');
      script.setAttribute('data-emit-metadata', '0');
      script.setAttribute('data-input-position', 'top');
      script.setAttribute('data-theme', 'preferred_color_scheme');
      script.setAttribute('data-lang', 'zh-CN');
      script.setAttribute('data-loading', 'lazy');
      script.setAttribute('crossorigin', 'anonymous');
      script.async = true;
      
      giscusRef.current.appendChild(script);
    }
  }, [data]);


  const analysis = data && !data.error ? data : null;
  const etfInfo = analysis?.etf_info;
  const suitabilityEvaluation = analysis?.suitability_evaluation;
  const gridStrategy = analysis?.grid_strategy;
  const inputParameters = analysis?.input_parameters;
  const analysisComplete = Boolean(
    suitabilityEvaluation?.total_score !== undefined
    && suitabilityEvaluation?.conclusion
    && gridStrategy?.grid_config
    && gridStrategy?.fund_allocation
    && etfInfo?.code
    && etfInfo?.name
    && etfInfo?.current_price !== undefined
    && etfInfo?.current_price !== null,
  );

  const userTotalCapital = Number(
    inputParameters?.total_capital
    ?? inputParameters?.totalCapital
    ?? gridStrategy?.composite_grid?.total_capital
    ?? gridStrategy?.fund_allocation?.total_capital
    ?? backtestParams?.totalCapital
    ?? 30000,
  );
  const derivedBacktest = {
    etfCode: inputParameters?.etf_code || inputParameters?.etfCode || etfInfo?.code,
    totalCapital: userTotalCapital,
    analysisDays: Number(inputParameters?.analysis_days || inputParameters?.analysisDays || 180),
    reinvestMode: inputParameters?.reinvest_mode || inputParameters?.reinvestMode || "pool_shares",
    scalingRatio: Number(inputParameters?.scaling_ratio ?? inputParameters?.scalingRatio ?? 0.1),
    stepMode: inputParameters?.step_mode || inputParameters?.stepMode || "atr",
    edaStepRatios: inputParameters?.eda_step_ratios || inputParameters?.edaStepRatios || null,
    edaSteps: inputParameters?.edaSteps || null,
    atrMultipliers: inputParameters?.atr_multipliers || inputParameters?.atrMultipliers || null,
  };
  const backtestProps = buildBacktestProps(backtestParams, derivedBacktest);
  const showBacktest = loading || BACKTEST_TABS.has(activeTab);

  const normalizedInputParams = {
    ...inputParameters,
    total_capital: userTotalCapital,
    totalCapital: userTotalCapital,
    etf_code: derivedBacktest.etfCode,
    etfCode: derivedBacktest.etfCode,
    analysis_days: derivedBacktest.analysisDays,
    analysisDays: derivedBacktest.analysisDays,
    reinvest_mode: derivedBacktest.reinvestMode,
    reinvestMode: derivedBacktest.reinvestMode,
    scaling_ratio: derivedBacktest.scalingRatio,
    scalingRatio: derivedBacktest.scalingRatio,
    step_mode: derivedBacktest.stepMode,
    stepMode: derivedBacktest.stepMode,
    eda_step_ratios: derivedBacktest.edaStepRatios,
    edaStepRatios: derivedBacktest.edaStepRatios,
    edaSteps: derivedBacktest.edaSteps,
    atr_multipliers: derivedBacktest.atrMultipliers,
    atrMultipliers: derivedBacktest.atrMultipliers,
  };

  return (
    <div className="space-y-6">
      {loading && (
        <LoadingSpinner
          message="正在分析ETF数据..."
          showProgress={true}
          progress={75}
        />
      )}

      {!loading && data?.error && (
        <ErrorState
          type="error"
          message={data.message}
          onBackToInput={onBackToInput}
          onReAnalysis={onReAnalysis}
        />
      )}

      {!loading && analysis && !analysisComplete && (
        <ErrorState
          type="data_incomplete"
          message="分析数据不完整，请重新分析"
          onBackToInput={onBackToInput}
          onReAnalysis={onReAnalysis}
        />
      )}

      {!loading && analysisComplete && (
        <div className="bg-white rounded-xl shadow-lg">
          <ReportTabs activeTab={activeTab} onTabChange={setActiveTab} />

          <div className="p-6">
            {activeTab === "overview" && (
              <OverviewTab
                etfInfo={etfInfo}
                suitabilityEvaluation={suitabilityEvaluation}
                gridStrategy={gridStrategy}
                dataQuality={analysis.data_quality}
                inputParameters={normalizedInputParams}
              />
            )}

            {activeTab === "strategy" && (
              <GridParametersCard
                gridStrategy={gridStrategy}
                inputParameters={normalizedInputParams}
                totalCapital={userTotalCapital}
                stepMode={derivedBacktest.stepMode}
                strategyRationale={analysis.strategy_rationale}
                adjustmentSuggestions={analysis.adjustment_suggestions}
                showDetailed={true}
                dataQuality={analysis.data_quality}
              />
            )}

            {activeTab === "suitability" && (
              <SuitabilityCard
                evaluation={suitabilityEvaluation}
                dataQuality={analysis.data_quality}
                showDetailed={true}
              />
            )}

            {activeTab === "archive" && (
              <BacktestArchiveView
                onApplyParams={(params, record) => {
                  if (onApplyArchiveParams) {
                    onApplyArchiveParams(params, record);
                  } else if (onReAnalysis && params?.etfCode) {
                    onReAnalysis(params);
                  }
                  setActiveTab("backtest");
                }}
              />
            )}
          </div>
        </div>
      )}

      {backtestProps && (
        <div className={showBacktest ? undefined : "hidden"}>
          <BacktestCard {...backtestProps} onHistoryMeta={onHistoryMeta} />
        </div>
      )}

      {!loading && analysisComplete && (
        <>
          <div className="bg-white rounded-xl shadow-lg p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">讨论与反馈</h3>
            <div ref={giscusRef} className="giscus-container"></div>
          </div>
          <Disclaimer />
        </>
      )}
    </div>
  );
};

export default AnalysisReport;
