import React, { useEffect, useMemo, useRef, useState, useCallback } from "react";
import { Link } from "react-router-dom";
import { RefreshCw, Search, X, Trophy } from "lucide-react";
import { getGridFitBoard, isAbortError, refreshGridFit } from "@shared/services/api";
import {
  ANNUAL_RETURN_LABEL,
  CASH_YIELD_LABEL,
  GRID_FIT_SECTORS,
  buildGridFitQuery,
  formatCashYield,
  sortByAtrCashYield,
} from "./gridFitDisplay";

function formatPercentPoint(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "—";
  const number = Number(value);
  return `${number > 0 ? "+" : ""}${number.toFixed(2)}%`;
}

function ProtocolCell({ cell }) {
  if (!cell) return <span className="text-gray-400 font-mono">未计算</span>;
  if (cell.status !== "ranked") {
    return <span className="text-amber-700 text-[11px]">{cell.status_reason || "未入榜"}</span>;
  }

  const isPositive = Number(cell.cash_yield) >= 0;

  return (
    <div>
      <div className="text-[10px] text-gray-400 font-mono">第 {cell.rank} 名</div>
      <div className={`font-mono font-bold text-xs ${isPositive ? "text-red-600" : "text-emerald-700"}`}>
        {formatCashYield(cell.cash_yield)}
      </div>
    </div>
  );
}

function ReasonList({ title, items }) {
  if (!items?.length) return null;
  return (
    <section className="space-y-2">
      <h4 className="text-xs font-bold text-gray-700">{title}</h4>
      <ul className="space-y-1 text-xs text-gray-500 font-mono">
        {items.map((item) => {
          const reason = item.atr?.status_reason || item.fixed_eda?.status_reason || "未入榜";
          return (
            <li key={`${title}-${item.etf_code}`} className="flex items-center gap-2">
              <Link
                to={`/analysis/${item.etf_code}`}
                className="font-bold text-indigo-600 hover:underline"
              >
                {item.etf_code}
              </Link>
              <span>{item.etf_name}</span>
              <span className="text-gray-400">· {reason}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export default function GridFitBoard() {
  const [sector, setSector] = useState("全部");
  const [searchQuery, setSearchQuery] = useState("");
  const [payload, setPayload] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const loadAbortRef = useRef(null);

  const loadBoard = useCallback(async (nextSector = sector, { silent = false } = {}) => {
    loadAbortRef.current?.abort();
    const controller = new AbortController();
    loadAbortRef.current = controller;
    const signal = controller.signal;
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const res = await getGridFitBoard(buildGridFitQuery(nextSector), { signal });
      if (signal?.aborted) return;
      if (!res?.success) {
        setError(res?.error || "读取适合度榜失败");
        return;
      }
      setPayload(res.data || null);
    } catch (err) {
      if (isAbortError(err) || signal?.aborted) return;
      setError(err?.message || "读取适合度榜失败");
    } finally {
      if (!signal?.aborted && !silent) setLoading(false);
    }
  }, [sector]);

  useEffect(() => {
    loadBoard(sector);
    return () => loadAbortRef.current?.abort();
  }, [loadBoard, sector]);

  useEffect(() => {
    if (payload?.job?.status !== "running") return undefined;
    const timer = setInterval(() => {
      loadBoard(sector, { silent: true });
    }, 5000);
    return () => {
      clearInterval(timer);
      loadAbortRef.current?.abort();
    };
  }, [loadBoard, payload?.job?.status, sector]);

  const handleRefresh = async () => {
    setError(null);
    try {
      const res = await refreshGridFit();
      if (!res?.success) {
        setError(res?.error || "启动补齐失败");
        return;
      }
      await loadBoard(sector);
    } catch (err) {
      setError(err?.message || "启动补齐失败");
    }
  };

  const progress = payload?.progress || {};
  const sortedBoard = useMemo(() => {
    return sortByAtrCashYield(payload?.board || []);
  }, [payload?.board]);

  const filteredBoard = useMemo(() => {
    if (!searchQuery.trim()) return sortedBoard;
    const q = searchQuery.trim().toLowerCase();
    return sortedBoard.filter(
      (r) =>
        r.etf_code?.toLowerCase().includes(q) ||
        r.etf_name?.toLowerCase().includes(q)
    );
  }, [sortedBoard, searchQuery]);

  return (
    <div className="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-2xl p-4 sm:p-6 shadow-xs space-y-5 min-w-0 max-w-full">
      {/* 顶部标题与快捷操作 */}
      <div className="flex flex-col gap-3 border-b border-gray-100 pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base sm:text-lg font-bold text-gray-900 dark:text-gray-100 flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500" />
            <span>全市场 ETF 网格适合度金榜</span>
          </h2>
          <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
            锁定标准化协议回测比较 11 个可购赛道，主排序列为【{CASH_YIELD_LABEL}】
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link
            to="/"
            className="text-xs text-indigo-600 hover:text-indigo-800 hover:underline font-medium"
          >
            ← 返回策略工作台
          </Link>
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/30 px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors shadow-2xs cursor-pointer"
          >
            <RefreshCw className={`h-3.5 w-3.5 text-indigo-600 ${loading ? "animate-spin" : ""}`} />
            补齐并重算
          </button>
        </div>
      </div>

      {/* 搜索与赛道双过滤栏 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        {/* 关键词实时搜索框 */}
        <div className="relative w-full sm:max-w-xs">
          <Search className="w-3.5 h-3.5 text-gray-400 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索代码或名称 (如 510300 / 芯片)..."
            className="w-full pl-8 pr-7 py-1.5 bg-gray-50 border border-gray-200 rounded-xl text-xs focus:outline-hidden focus:ring-1 focus:ring-indigo-500 focus:bg-white transition-all font-sans"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 p-0.5"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* 状态统计条 */}
        <div className="flex items-center gap-3 text-xs text-gray-500 font-mono shrink-0">
          <span>已入榜 <strong className="text-indigo-600">{progress.ranked || 0}</strong></span>
          <span>·</span>
          <span>短样本 <strong className="text-gray-700">{progress.short_sample || 0}</strong></span>
          <span>·</span>
          <span>未就绪 <strong className="text-gray-700">{progress.not_ready || 0}</strong></span>
        </div>
      </div>

      {/* 赛道快速切换胶囊 */}
      <div className="flex flex-wrap gap-1.5">
        {GRID_FIT_SECTORS.map((name) => (
          <button
            key={name}
            type="button"
            onClick={() => setSector(name)}
            className={`rounded-lg px-2.5 py-1 text-xs font-medium transition-all cursor-pointer ${
              sector === name
                ? "bg-indigo-600 text-white font-bold shadow-2xs"
                : "bg-gray-100 hover:bg-gray-200 text-gray-600"
            }`}
          >
            {name}
          </button>
        ))}
      </div>

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 p-3 text-xs text-red-700 font-medium">
          {error}
        </div>
      )}

      {/* 适合度排名表格 */}
      <div className="w-full max-w-full min-w-0 overflow-x-auto overscroll-x-contain border border-gray-100 dark:border-gray-700 rounded-xl">
        <table className="min-w-[44rem] w-full text-left text-xs">
          <thead className="bg-gray-50/80 dark:bg-gray-900/60 text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700 font-medium">
            <tr>
              <th className="py-2.5 px-3 w-12 text-center">排名</th>
              <th className="py-2.5 px-3">标的 (代码/名称)</th>
              <th className="py-2.5 px-3">ATR {CASH_YIELD_LABEL}</th>
              <th className="py-2.5 px-3">自定义网格 {CASH_YIELD_LABEL}</th>
              <th className="py-2.5 px-3">{ANNUAL_RETURN_LABEL}</th>
              <th className="py-2.5 px-3 w-28 text-center">策略流转</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100 font-sans">
            {filteredBoard.map((row, idx) => {
              const rankNum = idx + 1;
              const isTop1 = rankNum === 1;
              const isTop2 = rankNum === 2;
              const isTop3 = rankNum === 3;

              return (
                <tr
                  key={row.etf_code}
                  className="hover:bg-indigo-50/30 dark:hover:bg-gray-700/40 transition-colors"
                >
                  <td className="py-2.5 px-3 text-center font-mono font-bold">
                    {isTop1 ? (
                      <span className="text-amber-500 text-sm" title="榜首">🥇</span>
                    ) : isTop2 ? (
                      <span className="text-slate-400 text-sm" title="榜眼">🥈</span>
                    ) : isTop3 ? (
                      <span className="text-amber-700 text-sm" title="探花">🥉</span>
                    ) : (
                      <span className="text-gray-400 text-xs">{rankNum}</span>
                    )}
                  </td>
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-2">
                      <Link
                        to={`/analysis/${row.etf_code}`}
                        className="font-mono font-bold text-indigo-600 hover:text-indigo-800 hover:underline"
                        title="点击直接分析此标的"
                      >
                        {row.etf_code}
                      </Link>
                      <span className="font-medium text-gray-900 dark:text-gray-100 truncate max-w-[130px]">
                        {row.etf_name}
                      </span>
                      <span className="text-[10px] px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 hidden sm:inline-block">
                        {row.sector}
                      </span>
                    </div>
                  </td>
                  <td className="py-2.5 px-3">
                    <ProtocolCell cell={row.atr} />
                  </td>
                  <td className="py-2.5 px-3">
                    <ProtocolCell cell={row.fixed_eda} />
                  </td>
                  <td className="py-2.5 px-3 font-mono font-bold text-gray-900 dark:text-gray-100">
                    {formatPercentPoint(
                      row.atr?.annual_return ?? row.fixed_eda?.annual_return
                    )}
                  </td>
                  <td className="py-2.5 px-3 text-center">
                    <Link
                      to={`/analysis/${row.etf_code}`}
                      className="px-2.5 py-1 bg-white border border-indigo-200 hover:border-indigo-400 text-indigo-600 hover:bg-indigo-50 rounded text-[11px] font-medium transition-all shadow-2xs inline-flex items-center gap-1"
                      title={`立即针对 ${row.etf_name} 设计智能网格策略`}
                    >
                      <span>🎯 测算策略</span>
                    </Link>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        {!loading && filteredBoard.length === 0 && (
          <div className="py-12 text-center text-xs text-gray-400 space-y-1">
            <p>没有找到符合条件的入榜标的。</p>
            {searchQuery && (
              <button
                type="button"
                onClick={() => setSearchQuery("")}
                className="text-indigo-600 hover:underline"
              >
                清除搜索词重试
              </button>
            )}
          </div>
        )}
      </div>

      {/* 风险过滤与异常说明 */}
      <div className="border-t border-gray-100 pt-4 space-y-3">
        <ReasonList title="短样本区（上市不足 5 年，不参与总榜排序）" items={payload?.short_sample} />
        <ReasonList title="未就绪或待补齐标的" items={payload?.not_ready} />
        <ReasonList title="失败或历史行情不全" items={payload?.failed} />
        <ReasonList title="流动性过稀或最大回撤超标" items={payload?.blocked} />
      </div>
    </div>
  );
}
