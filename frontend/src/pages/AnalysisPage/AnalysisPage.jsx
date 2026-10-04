import React, { useState, useEffect, useRef } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Helmet } from "react-helmet-async";
import { Share2, ArrowLeft, AlertTriangle } from "lucide-react";
import AnalysisReport from "@features/analysis/components/AnalysisReport";
import DisclaimerModal from "@features/analysis/components/DisclaimerModal";
import { analyzeETF, isAbortError } from "@shared/services/api";
import {
  parseAnalysisURL,
  validateAndCompleteParams,
  generateAnalysisURL,
  encodeAnalysisParams,
} from "@shared/utils/url";
import { checkDisclaimerStatus, acceptDisclaimer } from "@shared/utils/disclaimer";
import { useShare } from "@shared/hooks/useShare";

/**
 * 分析页面组件
 * 负责处理URL参数解析、分析请求和结果展示
 */
const AnalysisPage = () => {
  const { etfCode } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();
  const { shareContent } = useShare();

  // 状态管理
  const [analysisData, setAnalysisData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [currentParams, setCurrentParams] = useState(null);
  const [paramErrors, setParamErrors] = useState([]);
  const [showParameterForm, setShowParameterForm] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [disclaimerChecked, setDisclaimerChecked] = useState(false);
  const [backtestMeta, setBacktestMeta] = useState(null);

  // 引用
  const parameterFormRef = useRef(null);
  const analysisAbortRef = useRef(null);

  // 初始化和URL参数解析
  useEffect(() => {
    const urlResult = parseAnalysisURL(
      `/analysis/${etfCode}`,
      `?${searchParams.toString()}`,
    );

    if (!urlResult.isValid) {
      // ETF代码无效，跳转到首页
      navigate("/", { replace: true });
      return;
    }

    // 验证和补全参数
    const validation = validateAndCompleteParams({
      etfCode: urlResult.etfCode,
      ...urlResult.params,
    });

    setParamErrors(validation.errors);
    setCurrentParams(validation.params);
    setBacktestMeta(null);

    // 参数被修正时先改 URL，下一轮再分析，避免同一份请求打两次
    if (validation.errors.length > 0) {
      const newSearchParams = encodeAnalysisParams(validation.params);
      setSearchParams(newSearchParams, { replace: true });
      return;
    }

    // 检查免责声明状态
    if (!checkDisclaimerStatus()) {
      // 用户未同意免责声明或已过期，显示弹窗
      setShowDisclaimer(true);
      setDisclaimerChecked(false);
    } else {
      // 已同意免责声明且未过期，直接执行分析
      handleAnalysis(validation.params);
    }
  }, [etfCode, searchParams, navigate, setSearchParams]);

  // 执行分析
  const handleAnalysis = async (parameters) => {
    analysisAbortRef.current?.abort();
    const controller = new AbortController();
    analysisAbortRef.current = controller;
    setLoading(true);

    try {
      const response = await analyzeETF(parameters, { signal: controller.signal });
      if (controller.signal.aborted) return;

      if (response.success) {
        setAnalysisData(response.data);

        // 保存分析历史记录
        saveAnalysisHistory({
          etfCode: parameters.etfCode,
          etfName: response.data?.etf_info?.name || `ETF ${parameters.etfCode}`,
          params: parameters,
          timestamp: Date.now(),
          url: generateAnalysisURL(parameters.etfCode, parameters),
        });
      } else {
        throw new Error(response.error || "分析失败");
      }
    } catch (error) {
      if (isAbortError(error) || controller.signal.aborted) return;
      console.error("分析请求失败:", error);
      setAnalysisData({
        error: true,
        message: error.message || "分析请求失败，请稍后重试",
      });
    } finally {
      if (analysisAbortRef.current === controller) {
        setLoading(false);
      }
    }
  };

  // 保存分析历史记录
  const saveAnalysisHistory = (record) => {
    try {
      const history = JSON.parse(
        localStorage.getItem("analysisHistory") || "[]",
      );

      // 避免重复记录
      const existingIndex = history.findIndex(
        (item) =>
          item.etfCode === record.etfCode &&
          JSON.stringify(item.params) === JSON.stringify(record.params),
      );

      if (existingIndex >= 0) {
        history[existingIndex] = record; // 更新时间戳
      } else {
        history.unshift(record); // 添加到开头
      }

      // 限制历史记录数量
      const limitedHistory = history.slice(0, 50);
      localStorage.setItem("analysisHistory", JSON.stringify(limitedHistory));
    } catch (error) {
      console.error("保存分析历史失败:", error);
    }
  };

  // 参数变更处理
  const handleParameterChange = (newParams) => {
    const fullParams = {
      etfCode,
      ...newParams,
    };

    // 更新URL
    const newSearchParams = encodeAnalysisParams(fullParams);
    setSearchParams(newSearchParams);

    // 隐藏参数表单
    setShowParameterForm(false);
  };

  // 重新分析
  const handleReAnalysis = () => {
    if (currentParams) {
      handleAnalysis(currentParams);
    }
  };

  // 处理从档案库或大宽表回填策略参数
  const handleApplyArchiveParams = (newParams, record) => {
    const targetCode = newParams?.etfCode || record?.etf_code;
    if (targetCode && targetCode !== etfCode) {
      // 跨标的：通过 navigate 切换到目标标的分析页面
      const fullParams = {
        ...currentParams,
        ...newParams,
        etfCode: targetCode,
      };
      navigate(generateAnalysisURL(targetCode, fullParams));
    } else {
      // 同标的：更新参数并直接重新分析
      handleParameterChange(newParams);
      handleAnalysis({
        ...currentParams,
        ...newParams,
      });
    }
  };

  // 分享功能
  const handleShare = async () => {
    const shareData = {
      title: `${analysisData?.etf_info?.name || etfCode} - ETF网格交易策略分析`,
      text: `查看 ${analysisData?.etf_info?.name || etfCode} 的智能网格交易策略分析结果`,
      url: window.location.href,
    };

    await shareContent(shareData);
  };

  // 返回首页
  const handleBackToHome = () => {
    navigate("/");
  };

  // 切换参数表单显示
  const toggleParameterForm = () => {
    setShowParameterForm(!showParameterForm);

    // 滚动到参数表单
    if (!showParameterForm && parameterFormRef.current) {
      setTimeout(() => {
        parameterFormRef.current.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 100);
    }
  };

  // 处理免责声明同意
  const handleDisclaimerAccept = () => {
    // 记录用户已同意免责声明
    acceptDisclaimer();
    setShowDisclaimer(false);
    setDisclaimerChecked(true);
    
    // 执行分析
    if (currentParams) {
      handleAnalysis(currentParams);
    }
  };

  // 处理免责声明取消 - 返回首页
  const handleDisclaimerCancel = () => {
    setShowDisclaimer(false);
    navigate("/", { replace: true });
  };

  // 生成SEO元数据
  const generateSEOData = () => {
    const etfName = analysisData?.etf_info?.name || `ETF ${etfCode}`;
    const title = `${etfName} - 智能网格交易策略分析 | ETFer.Top`;
    const description = `${etfName}的专业网格交易策略分析，基于ATR算法计算最优网格参数，提供详细的收益预测和风险评估。投资金额：${currentParams?.totalCapital?.toLocaleString()}元，网格类型：${currentParams?.gridType}，频率偏好：${currentParams?.riskPreference}，调节系数：${currentParams?.adjustmentCoefficient}。`;

    return { title, description };
  };

  const seoData = generateSEOData();

  return (
    <>
      {/* SEO优化 */}
      <Helmet>
        <title>{seoData.title}</title>
        <meta name="description" content={seoData.description} />
        <meta property="og:title" content={seoData.title} />
        <meta property="og:description" content={seoData.description} />
        <meta property="og:type" content="website" />
        <meta property="og:url" content={window.location.href} />
        <meta name="twitter:card" content="summary_large_image" />
        <meta name="twitter:title" content={seoData.title} />
        <meta name="twitter:description" content={seoData.description} />

        {/* 结构化数据 */}
        <script type="application/ld+json">
          {JSON.stringify({
            "@context": "https://schema.org",
            "@type": "FinancialProduct",
            name: analysisData?.etf_info?.name || `ETF ${etfCode}`,
            identifier: etfCode,
            description: seoData.description,
            provider: {
              "@type": "Organization",
              name: "ETFer.Top",
              url: window.location.origin,
            },
            url: window.location.href,
          })}
        </script>
      </Helmet>

      <div className="space-y-6">
        {/* 页面头部 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div className="flex items-center gap-4">
              <button
                onClick={handleBackToHome}
                className="flex items-center gap-2 px-3 py-2 text-gray-600 hover:text-gray-900 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <ArrowLeft className="w-4 h-4" />
                返回首页
              </button>

              <div>
                <h1 className="text-xl font-bold text-gray-900">
                  {analysisData?.etf_info?.name || `ETF`}({etfCode})
                  网格策略分析
                </h1>
                <div className="text-sm text-gray-600 flex flex-wrap items-center gap-x-2 gap-y-1 mt-1">
                  <span>投资金额：{currentParams?.totalCapital?.toLocaleString()}元</span>
                  <span>|</span>
                  <span>网格类型：{currentParams?.gridType}</span>
                  <span>|</span>
                  <span>
                    步长模式：
                    {currentParams?.stepMode === "fixed_eda" ? (
                      <span className="text-amber-700 font-semibold bg-amber-50 px-1.5 py-0.5 rounded border border-amber-200 font-mono text-xs">
                        🏛️ E大原版({currentParams?.edaSteps?.small || 5}%/{currentParams?.edaSteps?.medium || 15}%/{currentParams?.edaSteps?.large || 30}%)
                      </span>
                    ) : (
                      <span className="text-indigo-700 font-semibold bg-indigo-50 px-1.5 py-0.5 rounded border border-indigo-200 font-mono text-xs">
                        ★ 🌊 ATR自适应({currentParams?.atrMultipliers?.small || 0.6}x/{currentParams?.atrMultipliers?.medium || 1.2}x/{currentParams?.atrMultipliers?.large || 2.5}x)
                      </span>
                    )}
                  </span>
                  <span>|</span>
                  <span>周期：{currentParams?.analysisDays || 180}天</span>
                  {currentParams?.benchmarkPrice && (
                    <>
                      <span>|</span>
                      <span>
                        实盘自定义：
                        <span className="text-blue-700 font-semibold font-mono">
                          ¥{currentParams.benchmarkPrice}
                        </span>
                      </span>
                    </>
                  )}
                  {backtestMeta?.backtest_base_price != null && (
                    <>
                      <span>|</span>
                      <span>
                        回测铺网：
                        <span className="text-blue-700 font-semibold font-mono">
                          ¥{Number(backtestMeta.backtest_base_price).toFixed(3)}
                        </span>
                        {backtestMeta.latest_market_price != null && (
                          <span className="text-[10px] text-gray-500 ml-0.5">
                            (现价 ¥{Number(backtestMeta.latest_market_price).toFixed(3)})
                          </span>
                        )}
                      </span>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={handleShare}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Share2 className="w-4 h-4" />
                分享报告
              </button>
            </div>
          </div>

          {/* 参数错误提示 */}
          {paramErrors.length > 0 && (
            <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-4 h-4 text-yellow-600 mt-0.5" />
                <div>
                  <p className="text-sm font-medium text-yellow-800">
                    参数已自动修正
                  </p>
                  <ul className="text-sm text-yellow-700 mt-1">
                    {paramErrors.map((error, index) => (
                      <li key={index}>• {error}</li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 分析报告 - 只有在同意免责声明后才显示 */}
        {(disclaimerChecked || checkDisclaimerStatus()) && (
          <AnalysisReport
            data={analysisData}
            loading={loading}
            backtestParams={currentParams}
            onBackToInput={handleBackToHome}
            onReAnalysis={handleReAnalysis}
            onApplyArchiveParams={handleApplyArchiveParams}
            onHistoryMeta={setBacktestMeta}
            showShareButton={true}
          />
        )}

        {/* 免责声明弹窗 */}
        <DisclaimerModal
          isOpen={showDisclaimer}
          onAccept={handleDisclaimerAccept}
          onCancel={handleDisclaimerCancel}
        />
      </div>
    </>
  );
};

export default AnalysisPage;
