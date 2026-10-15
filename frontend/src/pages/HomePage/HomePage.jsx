import React, { useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import HeroSection from "./components/HeroSection";
import ETFActivePoolRadar from "./components/ETFActivePoolRadar";
import QuickConfigPanel from "./components/QuickConfigPanel";
import BacktestArchiveView from "@features/analysis/components/ReportCards/BacktestArchiveView";
import ParameterForm from "@features/analysis/components/ParameterForm";
import AnalysisHistory from "@features/history/components/AnalysisHistory";
import { encodeAnalysisParams } from "@shared/utils/url";

/**
 * 首页组件
 * 负责展示首页内容和处理分析请求
 */
export default function HomePage() {
  const navigate = useNavigate();
  const formSectionRef = useRef(null);
  const parameterFormRef = useRef(null);
  const [selectionMode, setSelectionMode] = useState("radar"); // 'radar' | 'matrix'
  const [selectedEtfForQuick, setSelectedEtfForQuick] = useState(null);

  // 处理分析请求 - 使用 SPA 客户端路由平滑跳转到分析页面
  const handleAnalysis = async (parameters) => {
    const searchParams = encodeAnalysisParams(parameters);
    const queryString = searchParams.toString();
    navigate(`/analysis/${parameters.etfCode}${queryString ? `?${queryString}` : ""}`);
  };

  // 桌面端点选标的：原地激活右侧驾驶舱并静默同步代码，不发生纵向暴滚
  const handleSelectETF = (code, fullItem) => {
    const item = fullItem || { code, etf_code: code, name: `ETF ${code}` };
    setSelectedEtfForQuick(item);
    parameterFormRef.current?.selectEtf(code, { shouldScroll: false });
  };

  const handleApplyFromMatrix = (params) => {
    if (params?.etfCode) {
      handleSelectETF(params.etfCode, {
        code: params.etfCode,
        etf_code: params.etfCode,
        name: `ETF ${params.etfCode}`,
      });
    }
  };

  const scrollToParameterForm = () => {
    if (selectedEtfForQuick?.code) {
      parameterFormRef.current?.selectEtf(selectedEtfForQuick.code, { shouldScroll: true });
    } else if (formSectionRef.current) {
      formSectionRef.current.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  };

  return (
    <>
      <Helmet>
        <title>ETFer.Top - 基于ATR算法的智能网格交易策略设计工具</title>
        <meta
          name="description"
          content="专业的ETF网格交易策略分析系统，基于ATR算法动态计算最优网格参数，提供详细的收益预测和风险评估。"
        />
      </Helmet>

      <div className="space-y-8">
        <HeroSection onStartAnalysis={scrollToParameterForm} />

        {/* 全市场做 T 标的选品与策略决策中心 (双模式胶囊切换) */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-4 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-gray-100 pb-3.5">
            <div>
              <h2 className="text-base sm:text-lg font-bold text-gray-900 flex items-center gap-2">
                <span>🎯 全市场做 T 标的选品与策略决策中心</span>
              </h2>
              <p className="text-xs text-gray-500 mt-0.5">
                结合近期 20 日流动性与 5 年历史实证长跑战绩，挑出真正适合做网格的优质品种
              </p>
            </div>

            {/* 双模式切换胶囊按钮组 */}
            <div className="flex items-center bg-gray-100 p-1 rounded-xl self-start sm:self-auto text-xs shrink-0">
              <button
                type="button"
                onClick={() => setSelectionMode("radar")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  selectionMode === "radar"
                    ? "bg-white text-indigo-600 font-bold shadow-xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <span>🎯 20日活跃选品雷达</span>
              </button>
              <button
                type="button"
                onClick={() => setSelectionMode("matrix")}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  selectionMode === "matrix"
                    ? "bg-white text-indigo-600 font-bold shadow-xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
              >
                <span>🏆 5年多周期回测天梯</span>
              </button>
            </div>
          </div>

          {/* 桌面端高密布局：左侧选品决策中心 + 右侧即时策略驾驶舱 */}
          <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
            <div className="xl:col-span-8 2xl:col-span-9 min-w-0">
              {selectionMode === "radar" ? (
                <ETFActivePoolRadar onSelectETF={handleSelectETF} isEmbedded={true} />
              ) : (
                <BacktestArchiveView onApplyParams={handleApplyFromMatrix} isEmbedded={true} />
              )}
            </div>

            {/* 右侧快速策略驾驶舱 (桌面端常驻并吸顶跟随) */}
            <div className="xl:col-span-4 2xl:col-span-3 sticky top-4">
              <QuickConfigPanel
                selectedEtf={selectedEtfForQuick}
                onLaunch={handleAnalysis}
                onOpenFullForm={scrollToParameterForm}
              />
            </div>
          </div>
        </div>

        <div ref={formSectionRef}>
          <ParameterForm ref={parameterFormRef} onAnalysis={handleAnalysis} />
        </div>

        <AnalysisHistory />
      </div>
    </>
  );
}
