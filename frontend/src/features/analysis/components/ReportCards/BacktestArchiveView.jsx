import React, { useState, useEffect, useMemo, useCallback } from "react";
import {
  Database,
  RefreshCw,
  Trash2,
  ChevronDown,
  ChevronUp,
  Layers,
  Sparkles,
  Search,
  Award,
  BarChart3,
  FileSpreadsheet,
  HelpCircle,
} from "lucide-react";
import MethodologyModal from "./MethodologyModal";
import {
  getBacktestRecords,
  getBacktestRecordDetail,
  deleteBacktestRecord,
  getBacktestDistinctETFs,
  getUniverseBacktestMatrix,
  isAbortError,
} from "@shared/services/api";
import {
  ARCHIVE_SECTORS,
  ARCHIVE_STEP_FILTERS,
  archiveStepLabel,
  buildArchiveListParams,
} from "./archiveFilters";
import MatrixTableRow from "./MatrixTableRow";

export default function BacktestArchiveView({ onApplyParams, isEmbedded = false }) {
  // 当前活动的主视图: 'matrix' (多周期矩阵) | 'sectors' (11大赛道横评) | 'records' (明细流水账)
  const [activeView, setActiveView] = useState("matrix");

  // 收益显示模式: 'annual' (年化收益率) | 'total' (累计总收益率)
  const [yieldDisplayMode, setYieldDisplayMode] = useState("annual");

  // 提示信息
  const [appliedNotice, setAppliedNotice] = useState(null);
  const [showMethodologyModal, setShowMethodologyModal] = useState(false);

  // ================= 1. 矩阵看板状态 =================
  const [matrixLoading, setMatrixLoading] = useState(false);
  const [matrixError, setMatrixError] = useState(null);
  const [matrixData, setMatrixData] = useState({ records: [], sectors: [] });
  const [matrixSearch, setMatrixSearch] = useState("");
  const [matrixSector, setMatrixSector] = useState("全部");
  const [matrixSortField, setMatrixSortField] = useState("5y"); // '5y' | '3y' | '1y' | '180d' | '90d'
  const [matrixSortOrder, setMatrixSortOrder] = useState("desc");
  const [onlyValid5y, setOnlyValid5y] = useState(false);
  const [matrixPage, setMatrixPage] = useState(1);
  const matrixPageSize = 25;

  // ================= 2. 个人流水账状态 =================
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsError, setRecordsError] = useState(null);
  const [records, setRecords] = useState([]);
  const [distinctEtfs, setDistinctEtfs] = useState([]);
  const [selectedEtf, setSelectedEtf] = useState("");
  const [selectedDays, setSelectedDays] = useState("");
  const [selectedSector, setSelectedSector] = useState("全部");
  const [selectedStepMode, setSelectedStepMode] = useState("");
  const [latestOnly, setLatestOnly] = useState(true);
  const [recordsPage, setRecordsPage] = useState(1);
  const recordsPageSize = 10;

  // 展开流水详情
  const [expandedRunId, setExpandedRunId] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailData, setDetailData] = useState({});
  const [, setDetailRail] = useState("all");
  const [, setDetailPage] = useState(1);

  // 格式化测算时间
  const formatRecordTime = (timeStr) => {
    if (!timeStr) return "-";
    if (typeof timeStr === "string") {
      return timeStr.replace("T", " ").replace(/\.\d+.*$/, "").slice(0, 19);
    }
    return String(timeStr);
  };

  // 1. 加载矩阵数据
  const loadMatrix = async (signal) => {
    setMatrixLoading(true);
    setMatrixError(null);
    try {
      const res = await getUniverseBacktestMatrix({}, { signal });
      if (signal?.aborted) return;
      if (res?.success && res.data) {
        setMatrixData(res.data);
      } else {
        setMatrixError(res?.error || "加载回测矩阵失败");
      }
    } catch (err) {
      if (isAbortError(err) || signal?.aborted) return;
      setMatrixError(err?.message || "网络请求异常");
    } finally {
      if (!signal?.aborted) setMatrixLoading(false);
    }
  };

  // 2. 加载流水账与已测标的
  const loadDistinctEtfs = async () => {
    try {
      const etfRes = await getBacktestDistinctETFs();
      if (etfRes?.success && etfRes.data) {
        setDistinctEtfs(etfRes.data || []);
      }
    } catch (err) {
      console.error("读取已测标的失败:", err);
    }
  };

  const loadRecords = useCallback(async (signal) => {
    setRecordsLoading(true);
    setRecordsError(null);
    try {
      const params = buildArchiveListParams({
        etfCode: selectedEtf,
        days: selectedDays,
        latestOnly,
        sector: selectedSector,
        stepMode: selectedStepMode,
      });
      const res = await getBacktestRecords(params, { signal });
      if (signal?.aborted) return;

      if (res?.success && res.data) {
        const rawList = res.data.records || [];
        const sortedList = rawList
          .slice()
          .sort((a, b) => (Number(b.backtest_days) || 0) - (Number(a.backtest_days) || 0));
        setRecords(sortedList);
      } else {
        setRecordsError(res?.error || "读取回测档案失败");
      }
    } catch (err) {
      if (isAbortError(err) || signal?.aborted) return;
      setRecordsError(err?.message || "网络请求异常");
    } finally {
      if (!signal?.aborted) setRecordsLoading(false);
    }
  }, [selectedEtf, selectedDays, latestOnly, selectedSector, selectedStepMode]);

  useEffect(() => {
    const controller = new AbortController();
    loadMatrix(controller.signal);
    loadDistinctEtfs();
    return () => controller.abort();
  }, []);

  useEffect(() => {
    if (activeView === "records") {
      const controller = new AbortController();
      loadRecords(controller.signal);
      return () => controller.abort();
    }
  }, [activeView, loadRecords]);

  // 筛选变动时流水账页码重置
  useEffect(() => {
    setRecordsPage(1);
  }, [selectedEtf, selectedDays, latestOnly, selectedSector, selectedStepMode]);

  // 预热矩阵多周期数值索引，大幅减少排序与过滤时的深层嵌套寻址
  const preprocessedMatrixRecords = useMemo(() => {
    return (matrixData.records || []).map((item) => {
      const p = item.periods || {};
      return {
        ...item,
        _val_90d: p["90d"]?.annual_return ?? -9999,
        _val_180d: p["180d"]?.annual_return ?? -9999,
        _val_1y: p["1y"]?.annual_return ?? -9999,
        _val_2y: p["2y"]?.annual_return ?? -9999,
        _val_3y: p["3y"]?.annual_return ?? -9999,
        _val_5y: p["5y"]?.annual_return ?? -9999,
      };
    });
  }, [matrixData.records]);

  // 矩阵过滤与排序
  const filteredMatrixRecords = useMemo(() => {
    let list = preprocessedMatrixRecords.filter((item) => {
      // 搜索代码或名称
      if (matrixSearch.trim()) {
        const q = matrixSearch.trim().toLowerCase();
        const codeMatch = item.etf_code?.toLowerCase().includes(q);
        const nameMatch = item.etf_name?.toLowerCase().includes(q);
        if (!codeMatch && !nameMatch) return false;
      }
      // 赛道过滤
      if (matrixSector !== "全部" && item.sector !== matrixSector) {
        return false;
      }
      // 仅看满期标的 (优先遵循当前排序列或 5 年成熟度)
      if (onlyValid5y) {
        const targetPeriod = matrixSortField || "5y";
        const periodObj = item.periods?.[targetPeriod];
        if (!periodObj || !periodObj.is_valid || periodObj.annual_return === null) return false;
      }
      return true;
    });

    // 扁平数值高效排序
    const sortKey = `_val_${matrixSortField}`;
    list.sort((a, b) => {
      const valA = a[sortKey] ?? -9999;
      const valB = b[sortKey] ?? -9999;
      return matrixSortOrder === "desc" ? valB - valA : valA - valB;
    });

    return list;
  }, [preprocessedMatrixRecords, matrixSearch, matrixSector, matrixSortField, matrixSortOrder, onlyValid5y]);

  const totalMatrixPages = Math.ceil(filteredMatrixRecords.length / matrixPageSize) || 1;
  const currentMatrixList = useMemo(() => {
    const start = (matrixPage - 1) * matrixPageSize;
    return filteredMatrixRecords.slice(start, start + matrixPageSize);
  }, [filteredMatrixRecords, matrixPage, matrixPageSize]);

  // 流水账分页数据受控切片，避免无节制平铺几千 DOM 节点
  const totalRecordsPages = Math.ceil(records.length / recordsPageSize) || 1;
  const currentRecordsList = useMemo(() => {
    const start = (recordsPage - 1) * recordsPageSize;
    return records.slice(start, start + recordsPageSize);
  }, [records, recordsPage, recordsPageSize]);

  // 切换展开/收起详情 (流水账)
  const toggleDetail = async (runId) => {
    if (expandedRunId === runId) {
      setExpandedRunId(null);
      return;
    }
    setExpandedRunId(runId);
    setDetailRail("all");
    setDetailPage(1);

    if (!detailData[runId]) {
      setDetailLoading(true);
      try {
        const res = await getBacktestRecordDetail(runId);
        if (res?.success && res.data) {
          setDetailData((prev) => ({ ...prev, [runId]: res.data }));
        }
      } catch (err) {
        console.error("加载档案详情失败:", err);
      } finally {
        setDetailLoading(false);
      }
    }
  };

  // 删除流水档案
  const handleDelete = async (runId, e) => {
    e.stopPropagation();
    if (!window.confirm("确定要删除这条回测档案记录吗？")) return;
    try {
      const res = await deleteBacktestRecord(runId);
      if (res?.success) {
        setRecords((prev) => prev.filter((r) => r.run_id !== runId));
        if (expandedRunId === runId) setExpandedRunId(null);
        loadDistinctEtfs();
      } else {
        alert(res?.error || "删除失败");
      }
    } catch (err) {
      alert("删除异常: " + err.message);
    }
  };

  // 一键回填参数
  const handleApplyMatrixParams = (item, e) => {
    e?.stopPropagation();
    if (onApplyParams) {
      onApplyParams(
        {
          etfCode: item.etf_code,
          totalCapital: 30000,
          scalingRatio: 0.1,
          reinvestMode: "pool_shares",
          stepMode: "atr",
          analysisDays: 180,
        },
        item
      );
    }
    setAppliedNotice(`已成功将【${item.etf_code} ${item.etf_name}】参数与代码回填至策略设计器！`);
    setTimeout(() => setAppliedNotice(null), 3500);
  };

  const handleApplyRecordParams = (record, e) => {
    e?.stopPropagation();
    if (onApplyParams) {
      onApplyParams(record.params || {}, record);
    }
    setAppliedNotice(`已成功将【${record.etf_code} ${record.etf_name}】历史回测参数回填！`);
    setTimeout(() => setAppliedNotice(null), 3500);
  };

  // 导出矩阵 CSV
  const handleExportMatrixCsv = () => {
    const rows = filteredMatrixRecords;
    if (!rows.length) return;
    const headers = [
      "ETF代码",
      "ETF名称",
      "所属赛道",
      "90天年化",
      "90天回撤",
      "半年年化",
      "半年回撤",
      "1年年化",
      "1年回撤",
      "2年年化",
      "2年回撤",
      "3年年化",
      "3年回撤",
      "5年年化",
      "5年回撤",
      "5年留存股数",
    ];
    const csvContent = [
      headers.join(","),
      ...rows.map((r) => {
        const p = r.periods || {};
        return [
          r.etf_code,
          `"${r.etf_name || ""}"`,
          `"${r.sector || ""}"`,
          p["90d"]?.annual_return ?? "",
          p["90d"]?.max_drawdown ?? "",
          p["180d"]?.annual_return ?? "",
          p["180d"]?.max_drawdown ?? "",
          p["1y"]?.annual_return ?? "",
          p["1y"]?.max_drawdown ?? "",
          p["2y"]?.annual_return ?? "",
          p["2y"]?.max_drawdown ?? "",
          p["3y"]?.annual_return ?? "",
          p["3y"]?.max_drawdown ?? "",
          p["5y"]?.annual_return ?? "",
          p["5y"]?.max_drawdown ?? "",
          p["5y"]?.free_shares ?? "",
        ].join(",");
      }),
    ].join("\n");

    const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `ETF多周期网格回测矩阵_${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
  };

  return (
    <div className="space-y-4">
      {/* 顶部总标题与视图切换导航 */}
      <div className={`flex flex-col md:flex-row md:items-center justify-between gap-3 ${isEmbedded ? "" : "border-b border-gray-100 pb-3"}`}>
        {!isEmbedded ? (
          <div>
            <h3 className="text-base font-bold text-gray-900 flex items-center gap-2">
              <Database className="w-5 h-5 text-indigo-600" />
              历史网格回测档案库
            </h3>
            <p className="text-xs text-gray-500 mt-0.5">
              {matrixData.total_etfs ?? filteredMatrixRecords.length} 只成熟标的的日线在本地库直出，包含多周期矩阵对比、11 大赛道胜率横评及历史快照
            </p>
          </div>
        ) : (
          <div className="text-xs text-gray-500 flex items-center gap-2">
            <Award className="w-4 h-4 text-indigo-600" />
            <span>
              {matrixData.total_etfs ?? filteredMatrixRecords.length} 只标的多周期长跑回测大宽表
              （{matrixData.storage_label || "本地数据库"}直出）
            </span>
          </div>
        )}

        {/* 视图切换按钮组 */}
        <div className="flex items-center bg-gray-100 p-1 rounded-xl shrink-0">
          <button
            onClick={() => setActiveView("matrix")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "matrix"
                ? "bg-white text-indigo-600 shadow-2xs font-bold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <Award className="w-3.5 h-3.5" />
            🏆 多周期矩阵看板 ({filteredMatrixRecords.length})
          </button>
          <button
            onClick={() => setActiveView("sectors")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "sectors"
                ? "bg-white text-indigo-600 shadow-2xs font-bold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            📊 11 大赛道胜率横评
          </button>
          <button
            onClick={() => setActiveView("records")}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all ${
              activeView === "records"
                ? "bg-white text-indigo-600 shadow-2xs font-bold"
                : "text-gray-600 hover:text-gray-900"
            }`}
          >
            <Layers className="w-3.5 h-3.5" />
            📜 单测明细流水 ({records.length})
          </button>
        </div>
      </div>

      {/* 回填成功提示浮条 */}
      {appliedNotice && (
        <div className="p-3 bg-emerald-50 text-emerald-800 rounded-xl text-xs border border-emerald-200 flex items-center gap-2 animate-fade-in">
          <Sparkles className="w-4 h-4 text-emerald-600 shrink-0" />
          <span className="font-medium">{appliedNotice}</span>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 视图 1: 多周期矩阵看板                                                   */}
      {/* ========================================================================= */}
      {activeView === "matrix" && (
        <div className="space-y-4">
          {/* 常驻评测基准与口径说明横幅 */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 px-3.5 py-2.5 bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/50 rounded-xl text-xs">
            <div className="flex flex-wrap items-center gap-2 text-indigo-950 dark:text-indigo-200">
              <span className="flex items-center gap-1 font-bold text-indigo-700 dark:text-indigo-400 shrink-0">
                <Sparkles className="w-3.5 h-3.5" />
                <span>评测基准:</span>
              </span>
              <span className="text-gray-700 dark:text-gray-300">
                本金 3w · 180d动态ATR · 模式B留免费股 · 倒金字塔加码10% · 首日真实开盘价P0
              </span>
            </div>
            <button
              type="button"
              onClick={() => setShowMethodologyModal(true)}
              className="flex items-center gap-1 text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 font-semibold hover:underline shrink-0 self-start sm:self-auto cursor-pointer"
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>收益算法与口径说明</span>
            </button>
          </div>

          {/* 筛选与检索控制条 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-6 gap-2.5 bg-gray-50/70 p-3 rounded-xl border border-gray-100 text-xs items-center">
            {/* 搜索 */}
            <div className="relative">
              <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="搜索代码或名称..."
                value={matrixSearch}
                onChange={(e) => {
                  setMatrixSearch(e.target.value);
                  setMatrixPage(1);
                }}
                className="w-full pl-8 pr-3 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs"
              />
            </div>

            {/* 赛道筛选 */}
            <div>
              <select
                value={matrixSector}
                onChange={(e) => {
                  setMatrixSector(e.target.value);
                  setMatrixPage(1);
                }}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs"
              >
                {ARCHIVE_SECTORS.map((s) => (
                  <option key={s} value={s}>
                    {s === "全部" ? "全部赛道" : s}
                  </option>
                ))}
              </select>
            </div>

            {/* 排序周期选择 */}
            <div className="flex items-center gap-1.5">
              <select
                value={matrixSortField}
                onChange={(e) => {
                  setMatrixSortField(e.target.value);
                  setMatrixPage(1);
                }}
                className="w-full px-3 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500 text-xs font-sans"
              >
                <option value="5y">按 5年年化 排序</option>
                <option value="3y">按 3年年化 排序</option>
                <option value="1y">按 1年年化 排序</option>
                <option value="180d">按 半年年化 排序</option>
                <option value="90d">按 90天年化 排序</option>
              </select>
              <button
                type="button"
                onClick={() => setMatrixSortOrder((prev) => (prev === "desc" ? "asc" : "desc"))}
                className="px-2 py-1.5 bg-white border border-gray-200 hover:border-indigo-300 hover:text-indigo-600 rounded-lg text-xs font-mono font-medium text-gray-700 shrink-0 transition-colors shadow-2xs"
                title={matrixSortOrder === "desc" ? "当前为降序（高收益在前），点击切换为升序" : "当前为升序（低收益在前），点击切换为降序"}
              >
                {matrixSortOrder === "desc" ? "↓ 降序" : "↑ 升序"}
              </button>
            </div>

            {/* 收益显示模式切换单选胶囊 (用户指定要求) */}
            <div className="flex items-center bg-white p-0.5 rounded-lg border border-gray-200 shrink-0">
              <span className="text-[11px] text-gray-500 font-medium px-1.5">口径:</span>
              <button
                type="button"
                onClick={() => setYieldDisplayMode("total")}
                className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                  yieldDisplayMode === "total"
                    ? "bg-indigo-600 text-white font-bold shadow-2xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                title="展示回测周期内真实累计总赚幅"
              >
                累计总收益
              </button>
              <button
                type="button"
                onClick={() => setYieldDisplayMode("annual")}
                className={`px-2 py-1 rounded text-[11px] font-medium transition-all ${
                  yieldDisplayMode === "annual"
                    ? "bg-indigo-600 text-white font-bold shadow-2xs"
                    : "text-gray-600 hover:text-gray-900"
                }`}
                title="折算为统一标准年化复合收益率"
              >
                年化收益率
              </button>
            </div>

            {/* 仅看满期成熟标的快速开关 */}
            <div className="flex items-center gap-1.5 px-2 py-1 bg-slate-100 dark:bg-slate-800 rounded-lg border border-slate-200 dark:border-slate-700">
              <input
                type="checkbox"
                id="onlyValid5y"
                checked={onlyValid5y}
                onChange={(e) => {
                  setOnlyValid5y(e.target.checked);
                  setMatrixPage(1);
                }}
                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
              />
              <label htmlFor="onlyValid5y" className="text-gray-700 dark:text-gray-200 cursor-pointer font-semibold text-[11px] flex items-center gap-1">
                <span>仅看满期标的</span>
                <span className="text-[10px] text-indigo-600 dark:text-indigo-400 font-mono">
                  ({matrixSortField === "5y" ? "满5年" : matrixSortField === "3y" ? "满3年" : matrixSortField})
                </span>
              </label>
            </div>

            {/* 导出 CSV 按钮 */}
            <div className="flex justify-end">
              <button
                onClick={handleExportMatrixCsv}
                className="flex items-center gap-1.5 px-2.5 py-1.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 rounded-lg font-medium transition-colors text-[11px]"
              >
                <FileSpreadsheet className="w-3.5 h-3.5" />
                导出 CSV
              </button>
            </div>
          </div>

          {/* 矩阵大宽表 */}
          {matrixLoading ? (
            <div className="py-20 text-center text-gray-400 text-xs">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500 mb-2" />
              正在加载全市场多周期回测矩阵...
            </div>
          ) : matrixError ? (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-xs border border-red-200">
              {matrixError}
            </div>
          ) : filteredMatrixRecords.length === 0 ? (
            <div className="py-16 text-center text-gray-400 text-xs bg-gray-50/50 rounded-xl border border-dashed border-gray-200">
              暂无匹配的标的，请调整筛选条件。
            </div>
          ) : (
            <div className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-2xs">
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse text-xs">
                  <thead>
                    <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-600 font-semibold">
                      <th className="py-2.5 px-3 w-12 text-center">序号</th>
                      <th className="py-2.5 px-3 w-20">代码</th>
                      <th className="py-2.5 px-3 w-36">标的简称</th>
                      <th className="py-2.5 px-3 w-24">赛道</th>
                      <th className="py-2.5 px-3 text-right group cursor-help" title={yieldDisplayMode === 'total' ? "策略累计总收益率 = (期末总资产 - 初始本金) / 初始本金" : "90天折算年化 = 累计总收益 × (365 / 自然日历天数)"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>90天 ({yieldDisplayMode === 'total' ? '累计' : '年化'})</span>
                          <HelpCircle className="w-3 h-3 text-gray-400" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 text-right group cursor-help" title={yieldDisplayMode === 'total' ? "策略累计总收益率 = (期末总资产 - 初始本金) / 初始本金" : "半年折算年化 = 累计总收益 × (365 / 自然日历天数)"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>半年 ({yieldDisplayMode === 'total' ? '累计' : '年化'})</span>
                          <HelpCircle className="w-3 h-3 text-gray-400" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 text-right group cursor-help" title={yieldDisplayMode === 'total' ? "策略累计总收益率 = (期末总资产 - 初始本金) / 初始本金" : "1年折算年化 = 累计总收益 × (365 / 自然日历天数)"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>1年 ({yieldDisplayMode === 'total' ? '累计' : '年化'})</span>
                          <HelpCircle className="w-3 h-3 text-gray-400" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 text-right group cursor-help" title={yieldDisplayMode === 'total' ? "策略累计总收益率 = (期末总资产 - 初始本金) / 初始本金" : "2年折算年化 = 累计总收益 × (365 / 自然日历天数)"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>2年 ({yieldDisplayMode === 'total' ? '累计' : '年化'})</span>
                          <HelpCircle className="w-3 h-3 text-gray-400" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 text-right group cursor-help" title={yieldDisplayMode === 'total' ? "策略累计总收益率 = (期末总资产 - 初始本金) / 初始本金" : "3年折算年化 = 累计总收益 × (365 / 自然日历天数)"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>3年 ({yieldDisplayMode === 'total' ? '累计' : '年化'})</span>
                          <HelpCircle className="w-3 h-3 text-gray-400" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 text-right bg-indigo-50/30 text-indigo-950 font-bold group cursor-help" title={yieldDisplayMode === 'total' ? "累计总收益率 = (期末总资产 - 初始本金) / 初始本金，含0成本免费股票现值" : "5年折算年化 = 累计总收益 × (365 / 自然日历天数)，含0成本免费股票现值"}>
                        <div className="inline-flex items-center gap-1 justify-end">
                          <span>5年 ({yieldDisplayMode === 'total' ? '累计' : '年化'}) / 留存股</span>
                          <HelpCircle className="w-3 h-3 text-indigo-500" />
                        </div>
                      </th>
                      <th className="py-2.5 px-3 w-28 text-center">快捷操作</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 font-mono">
                    {currentMatrixList.map((item, idx) => {
                      const rowNum = (matrixPage - 1) * matrixPageSize + idx + 1;
                      return (
                        <MatrixTableRow
                          key={item.etf_code}
                          item={item}
                          rowNum={rowNum}
                          yieldDisplayMode={yieldDisplayMode}
                          onApply={handleApplyMatrixParams}
                        />
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* 分页控制栏 */}
              <div className="p-3 bg-gray-50/50 border-t border-gray-100 flex items-center justify-between text-xs text-gray-500 font-sans">
                <div>
                  显示 {(matrixPage - 1) * matrixPageSize + 1} 至{" "}
                  {Math.min(matrixPage * matrixPageSize, filteredMatrixRecords.length)} 条，共{" "}
                  {filteredMatrixRecords.length} 只标的
                </div>
                <div className="flex items-center gap-2">
                  <button
                    disabled={matrixPage <= 1}
                    onClick={() => setMatrixPage((p) => Math.max(1, p - 1))}
                    className="px-3 py-1 bg-white border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
                  >
                    上一页
                  </button>
                  <span className="font-mono">
                    {matrixPage} / {totalMatrixPages}
                  </span>
                  <button
                    disabled={matrixPage >= totalMatrixPages}
                    onClick={() => setMatrixPage((p) => Math.min(totalMatrixPages, p + 1))}
                    className="px-3 py-1 bg-white border border-gray-200 rounded disabled:opacity-40 hover:bg-gray-50"
                  >
                    下一页
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* 视图 2: 11 大赛道胜率横评                                                 */}
      {/* ========================================================================= */}
      {activeView === "sectors" && (
        <div className="space-y-4">
          <div className="bg-indigo-50/50 border border-indigo-100 rounded-xl p-3.5 text-xs text-indigo-900 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="w-4 h-4 text-indigo-600" />
              <span>
                基于 E 大网格 2.0（3w本金、自适应ATR、模式B留股、倒金字塔加码10%）评测 11 大赛道综合表现
              </span>
            </div>
            <span className="text-gray-500 font-mono text-[11px]">
              点击任一行可快速筛选该赛道标的
            </span>
          </div>

          <div className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-2xs">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-gray-50/80 border-b border-gray-200 text-gray-600 font-semibold">
                  <th className="py-3 px-4">赛道名称</th>
                  <th className="py-3 px-4">标的规模 (5年有效)</th>
                  <th className="py-3 px-4 text-right">5年正收益率 (胜率)</th>
                  <th className="py-3 px-4 text-right">5年均年化收益</th>
                  <th className="py-3 px-4 text-right">5年平均最大回撤</th>
                  <th className="py-3 px-4 text-right">3年胜率</th>
                  <th className="py-3 px-4">赛道标杆 Top Pick</th>
                  <th className="py-3 px-4 text-center">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {(matrixData.sectors || []).map((sec) => {
                  const s5 = sec.stat_5y || {};
                  const s3 = sec.stat_3y || {};
                  const tp = sec.top_pick;

                  return (
                    <tr
                      key={sec.sector}
                      onClick={() => {
                        setMatrixSector(sec.sector);
                        setActiveView("matrix");
                      }}
                      className="hover:bg-indigo-50/40 cursor-pointer transition-colors"
                    >
                      <td className="py-3 px-4 font-bold text-gray-900 flex items-center gap-2">
                        <span>{sec.sector}</span>
                      </td>
                      <td className="py-3 px-4 text-gray-600 font-mono">
                        {sec.total_etfs} 只{" "}
                        <span className="text-gray-400 text-[11px]">
                          ({s5.valid_count || 0}只满5年)
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold">
                        {s5.win_rate !== null ? (
                          <span
                            className={
                              s5.win_rate >= 80 ? "text-red-600" : "text-gray-700"
                            }
                          >
                            {s5.win_rate}%
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono font-bold">
                        {s5.avg_annual_return !== null ? (
                          <span
                            className={
                              s5.avg_annual_return >= 0 ? "text-red-600" : "text-emerald-600"
                            }
                          >
                            {s5.avg_annual_return >= 0 ? `+${s5.avg_annual_return}%` : `${s5.avg_annual_return}%`}
                          </span>
                        ) : (
                          "-"
                        )}
                      </td>
                      <td className="py-3 px-4 text-right font-mono text-gray-500">
                        {s5.avg_max_drawdown !== null ? `-${s5.avg_max_drawdown}%` : "-"}
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        {s3.win_rate !== null ? `${s3.win_rate}%` : "-"}
                      </td>
                      <td className="py-3 px-4 font-mono">
                        {tp ? (
                          <div className="flex items-center gap-1.5">
                            <span className="font-bold text-indigo-600">{tp.etf_code}</span>
                            <span className="text-gray-700 truncate max-w-[90px] font-sans">
                              {tp.etf_name}
                            </span>
                            <span className="text-red-600 font-bold text-[11px]">
                              (+{tp.annual_return}%)
                            </span>
                          </div>
                        ) : (
                          <span className="text-gray-400">暂无</span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-center">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setMatrixSector(sec.sector);
                            setActiveView("matrix");
                          }}
                          className="px-2 py-1 text-xs text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded font-medium transition-colors"
                        >
                          查看标的
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* 视图 3: 单测明细流水账 (保留原有完整功能)                                 */}
      {/* ========================================================================= */}
      {activeView === "records" && (
        <div className="space-y-4">
          {/* 筛选面板 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3 bg-gray-50/70 p-3 rounded-xl border border-gray-100 text-xs">
            <div>
              <label className="text-gray-500 mb-1 block">标的筛选</label>
              <select
                value={selectedEtf}
                onChange={(e) => setSelectedEtf(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">全部已测标的</option>
                {distinctEtfs.map((item) => (
                  <option key={item.etf_code} value={item.etf_code}>
                    {item.etf_code} {item.etf_name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-gray-500 mb-1 block">回测周期</label>
              <select
                value={selectedDays}
                onChange={(e) => setSelectedDays(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              >
                <option value="">全部周期</option>
                <option value="90">90 天</option>
                <option value="180">180 天 (半年)</option>
                <option value="365">365 天 (1年)</option>
                <option value="730">730 天 (2年)</option>
                <option value="1095">1095 天 (3年)</option>
                <option value="1825">1825 天 (5年)</option>
              </select>
            </div>

            <div>
              <label className="text-gray-500 mb-1 block">所属赛道</label>
              <select
                value={selectedSector}
                onChange={(e) => setSelectedSector(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              >
                {ARCHIVE_SECTORS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-gray-500 mb-1 block">步长模式</label>
              <select
                value={selectedStepMode}
                onChange={(e) => setSelectedStepMode(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-white border border-gray-200 rounded-lg focus:outline-hidden focus:ring-1 focus:ring-indigo-500"
              >
                {ARCHIVE_STEP_FILTERS.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.label}
                  </option>
                ))}
              </select>
            </div>

            <div className="flex items-end pb-1">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="checkbox"
                  checked={latestOnly}
                  onChange={(e) => setLatestOnly(e.target.checked)}
                  className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                />
                <span className="text-gray-700 font-medium">仅看同条件最新记录</span>
              </label>
            </div>
          </div>

          {recordsError && (
            <div className="p-4 bg-red-50 text-red-700 rounded-xl text-xs border border-red-200">
              {recordsError}
            </div>
          )}

          {recordsLoading ? (
            <div className="py-16 text-center text-gray-400 text-xs">
              <RefreshCw className="w-6 h-6 animate-spin mx-auto text-indigo-500 mb-2" />
              正在加载回测明细流水...
            </div>
          ) : records.length === 0 ? (
            <div className="py-16 text-center text-gray-400 text-xs bg-gray-50/50 rounded-xl border border-dashed border-gray-200">
              暂无匹配的单测历史快照。可在【历史策略回测】运行单次回测后自动归档。
            </div>
          ) : (
            <div className="space-y-4">
              {currentRecordsList.map((rec) => {
                const isExpanded = expandedRunId === rec.run_id;
                const currentDetail = detailData[rec.run_id];

                return (
                  <div
                    key={rec.run_id}
                    className="border border-gray-200 rounded-xl overflow-hidden bg-white shadow-2xs transition-all hover:border-indigo-300"
                  >
                    <div
                      onClick={() => toggleDetail(rec.run_id)}
                      className="p-4 bg-gray-50/50 hover:bg-gray-50 cursor-pointer flex flex-col md:flex-row md:items-center justify-between gap-4 transition-colors"
                    >
                      <div className="flex items-start gap-3">
                        <div className="p-2 rounded-lg bg-white border border-gray-200 text-indigo-600 font-mono font-bold text-xs">
                          {rec.etf_code}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-bold text-gray-900 text-sm">
                              {rec.etf_name}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-50 text-blue-700 border border-blue-200 font-medium">
                              {rec.backtest_days} 天 ({rec.actual_days} 交易日)
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-slate-50 text-slate-700 border border-slate-200 font-medium">
                              {rec.sector || "未入池"}
                            </span>
                            <span className="text-xs px-2 py-0.5 rounded-full bg-purple-50 text-purple-700 border border-purple-200 font-mono">
                              {archiveStepLabel(rec)}
                            </span>
                            {rec.reinvest_mode === "pool_shares" && (
                              <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-800 border border-amber-300 font-medium">
                                🪙 模式B留股 ({rec.free_shares}股)
                              </span>
                            )}
                          </div>
                          <div className="flex items-center gap-4 text-xs text-gray-500 mt-1.5 font-mono">
                            <span>测算时间: {formatRecordTime(rec.created_at)}</span>
                            <span>初始本金: ¥{Number(rec.total_capital).toLocaleString()}</span>
                          </div>
                        </div>
                      </div>

                      <div className="flex items-center gap-6 font-mono text-xs">
                        <div>
                          <div className="text-gray-400 text-[11px]">年化收益率</div>
                          <div
                            className={`font-bold text-sm ${
                              rec.annual_return >= 0 ? "text-red-600" : "text-emerald-600"
                            }`}
                          >
                            {rec.annual_return >= 0 ? `+${rec.annual_return}%` : `${rec.annual_return}%`}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-400 text-[11px]">做 T 纯利润</div>
                          <div className="font-bold text-sm text-red-600">
                            ¥{Number(rec.total_profit).toLocaleString()}
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-400 text-[11px]">最大回撤</div>
                          <div className="font-bold text-sm text-gray-700">
                            -{rec.max_drawdown}%
                          </div>
                        </div>
                        <div>
                          <div className="text-gray-400 text-[11px]">成交次数</div>
                          <div className="font-bold text-sm text-gray-700">
                            {rec.total_trades} 次
                          </div>
                        </div>

                        <div className="flex items-center gap-2 ml-2">
                          <button
                            onClick={(e) => handleApplyRecordParams(rec, e)}
                            className="p-1.5 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                            title="回填此历史参数"
                          >
                            <Sparkles className="w-4 h-4" />
                          </button>
                          <button
                            onClick={(e) => handleDelete(rec.run_id, e)}
                            className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="删除此档案"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                          <div className="text-gray-400">
                            {isExpanded ? (
                              <ChevronUp className="w-4 h-4" />
                            ) : (
                              <ChevronDown className="w-4 h-4" />
                            )}
                          </div>
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="border-t border-gray-200 p-4 bg-white">
                        {detailLoading && !currentDetail ? (
                          <div className="py-8 text-center text-gray-400 text-xs">
                            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-indigo-500 mb-2" />
                            加载详情明细中...
                          </div>
                        ) : currentDetail ? (
                          <div className="space-y-4">
                            <div className="p-3 bg-gray-50 rounded-lg text-xs text-gray-600 font-mono">
                              <div>档案 ID: {rec.run_id}</div>
                              <div>
                                价格基准: ¥{currentDetail.summary?.history_meta?.backtest_base_price} | 
                                起止日期: {currentDetail.summary?.start_date} ~ {currentDetail.summary?.end_date}
                              </div>
                            </div>
                          </div>
                        ) : (
                          <div className="text-center text-gray-400 py-4 text-xs">
                            无明细数据
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* 流水账受控分页导航 */}
              {totalRecordsPages > 1 && (
                <div className="flex items-center justify-between pt-3 text-xs text-gray-500 font-sans border-t border-gray-200">
                  <div>
                    共 <span className="font-mono font-bold text-gray-700">{records.length}</span> 条历史回测记录
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      disabled={recordsPage <= 1}
                      onClick={() => setRecordsPage((p) => Math.max(1, p - 1))}
                      className="px-2.5 py-1 bg-white border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium transition-colors shadow-2xs"
                    >
                      上一页
                    </button>
                    <span className="font-mono px-1">
                      {recordsPage} / {totalRecordsPages}
                    </span>
                    <button
                      disabled={recordsPage >= totalRecordsPages}
                      onClick={() => setRecordsPage((p) => Math.min(totalRecordsPages, p + 1))}
                      className="px-2.5 py-1 bg-white border border-gray-200 rounded hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed font-medium transition-colors shadow-2xs"
                    >
                      下一页
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
      {/* 算法口径与评测说明弹窗 */}
      <MethodologyModal
        isOpen={showMethodologyModal}
        onClose={() => setShowMethodologyModal(false)}
      />
    </div>
  );
}
