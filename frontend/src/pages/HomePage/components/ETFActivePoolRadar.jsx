import React, { useState, useEffect, useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import SearchHistoryDropdown from "./SearchHistoryDropdown";
import {
  getSearchHistory,
  saveSearchHistoryItem,
  removeSearchHistoryItem,
  clearSearchHistory,
} from "@shared/utils/searchHistoryStorage";
import {
  CARD_RENDER_LIMIT,
  DEFAULT_COLLAPSE_LIMIT,
  PRIMARY_SECTORS,
  buildTruncationLabel,
  filterByStoredSubsector,
  subsectorsForSector,
  aggregateSectorCounts,
  maturityCounts,
  backfillHint,
  storageBadge,
  poolAtrParams,
  atrFloorLabel,
  rankBadge,
} from "./radarDisplay";

export default function ETFActivePoolRadar({ onSelectETF }) {
  const [loading, setLoading] = useState(true);
  const [poolData, setPoolData] = useState({
    total: 0,
    t0_total: 0,
    sectors_summary: [],
    items: [],
  });
  const [selectedSector, setSelectedSector] = useState("全部");
  const [selectedSubSector, setSelectedSubSector] = useState("全部");
  const [onlyT0, setOnlyT0] = useState(false);
  const [selectedElasticity, setSelectedElasticity] = useState("全部");
  const [searchKeyword, setSearchKeyword] = useState("");
  const [showUnclassified, setShowUnclassified] = useState(false);
  const [unclassifiedItems, setUnclassifiedItems] = useState([]);
  const [maturityFilter, setMaturityFilter] = useState("5y"); // 默认展示满 5 年期 (历经完整牛熊)
  const [minAtr, setMinAtr] = useState("1.5");
  const [commodityExempt, setCommodityExempt] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false); // 默认收拢，仅展示前 6 只精选

  // 搜索历史状态
  const [searchHistory, setSearchHistory] = useState([]);
  const [isHistoryOpen, setIsHistoryOpen] = useState(false);
  const searchContainerRef = useRef(null);
  const searchInputRef = useRef(null);

  useEffect(() => {
    setSearchHistory(getSearchHistory());
  }, []);

  // 全局快捷键：/ 或 Cmd+K / Ctrl+K 聚焦搜索框
  useEffect(() => {
    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName;
      const isTyping = activeTag === "INPUT" || activeTag === "TEXTAREA";

      if (
        (e.key === "/" && !isTyping) ||
        ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k")
      ) {
        e.preventDefault();
        searchInputRef.current?.focus();
        searchInputRef.current?.select();
        setIsHistoryOpen(true);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  const handleRecordHistory = (item) => {
    if (!item?.etf_code && !item?.code) return;
    const updated = saveSearchHistoryItem({
      code: item.etf_code || item.code,
      name: item.name,
      sector: item.sector,
    });
    setSearchHistory(updated);
  };

  const handleSelectFromHistory = (historyItem) => {
    setSearchKeyword(historyItem.code);
    setIsHistoryOpen(false);
    handleRecordHistory(historyItem);
    if (onSelectETF) {
      onSelectETF(historyItem.code);
    }
  };

  const handleRemoveHistory = (code) => {
    const updated = removeSearchHistoryItem(code);
    setSearchHistory(updated);
  };

  const handleClearHistory = () => {
    clearSearchHistory();
    setSearchHistory([]);
  };

  const renderScoreBadge = (item) => {
    const text = rankBadge(item);
    if (!text) return null;
    return (
      <span className="bg-slate-100 dark:bg-gray-700 text-slate-600 dark:text-slate-300 text-[10px] font-bold px-1.5 py-0.5 rounded shrink-0">
        {text}
      </span>
    );
  };

  // 当一级分类变更时，重置二级分类为“全部”且重置展开状态
  const handlePrimarySectorChange = (sector) => {
    setSelectedSector(sector);
    setSelectedSubSector("全部");
    setIsExpanded(false);
  };

  // 加载全市场做 T 标的池 (首屏拉取全量，后续所有成熟度/赛道/弹性/搜索切片纯本地 0ms 纯函数响应)
  useEffect(() => {
    const controller = new AbortController();
    fetchPoolData(controller.signal);
    return () => controller.abort();
  }, [minAtr, commodityExempt]);

  useEffect(() => {
    if (!poolData.backfilling) return undefined;
    const timer = setInterval(() => {
      fetchPoolData(undefined, { quiet: true });
    }, 12000);
    return () => clearInterval(timer);
  }, [poolData.backfilling]);

  const fetchUnclassified = async (signal) => {
    try {
      const params = new URLSearchParams();
      params.append("sector", "未归类");
      params.append("min_ma20_amount", "3000");
      const atr = poolAtrParams(minAtr, commodityExempt);
      params.append("min_atr", atr.min_atr);
      params.append("commodity_exempt", atr.commodity_exempt);
      const res = await fetch(`/api/etf/pool?${params.toString()}`, { signal });
      const json = await res.json();
      if (signal?.aborted) return;
      if (json.success && json.data) {
        setUnclassifiedItems(json.data.items || []);
      }
    } catch (e) {
      if (e?.name === "AbortError") return;
      console.error("加载未归类标的失败:", e);
    }
  };

  const fetchPoolData = async (signal, options = {}) => {
    if (!options.quiet) setLoading(true);
    try {
      const params = new URLSearchParams();
      params.append("min_ma20_amount", "3000");
      const atr = poolAtrParams(minAtr, commodityExempt);
      params.append("min_atr", atr.min_atr);
      params.append("commodity_exempt", atr.commodity_exempt);
      if (options.refresh) params.append("refresh", "1");

      const res = await fetch(`/api/etf/pool?${params.toString()}`, { signal });
      const json = await res.json();
      if (signal?.aborted) return;
      if (json.success && json.data) {
        setPoolData(json.data);
      }
    } catch (e) {
      if (e?.name === "AbortError") return;
      console.error("加载标的池失败:", e);
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  };

  const maturePoolItems = useMemo(() => {
    const rawItems = poolData.items || [];
    if (maturityFilter === "5y") {
      return rawItems.filter((item) => item.is_valid_5y);
    }
    if (maturityFilter === "3y") {
      return rawItems.filter((item) => item.is_valid_3y);
    }
    return rawItems;
  }, [poolData.items, maturityFilter]);

  const maturity = useMemo(() => maturityCounts(poolData.items), [poolData.items]);
  const maturity5yCount = maturity.y5;
  const maturity3yCount = maturity.y3;
  const maturityAllCount = maturity.all;
  const poolBackfillHint = backfillHint(poolData.backfilling, maturityAllCount);

  // 当前成熟度基准池总数与 T+0 动态计数
  const currentMaturityTotal = maturePoolItems.length;
  const currentT0Count = useMemo(() => {
    return maturePoolItems.filter((item) => item.is_t0).length;
  }, [maturePoolItems]);

  // 2. 基于当前成熟度基准池动态自适应聚合赛道徽标数字 (相加严格等于当前成熟池总数)
  const sectorCountMap = useMemo(() => aggregateSectorCounts(maturePoolItems), [maturePoolItems]);

  // 3. 当前一级赛道下的二级细分列表配置 (动态自适应)
  const currentSubSectors = useMemo(() => {
    if (selectedSector === "全部") {
      return [];
    }
    const subMap = {};
    maturePoolItems
      .filter((item) => item.sector === selectedSector)
      .forEach((item) => {
        const sub = item.subsector || "其他";
        subMap[sub] = (subMap[sub] || 0) + 1;
      });

    const subs = Object.entries(subMap)
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }));

    const sectorCount = sectorCountMap[selectedSector] ?? 0;
    return [{ name: "全部", count: sectorCount }, ...subs];
  }, [selectedSector, maturePoolItems, sectorCountMap]);

  // 4. 第二级派生：赛道 + 二级分类 + 交易机制 + 弹性 + 搜索关键字级联过滤
  const filteredItems = useMemo(() => {
    let result = maturePoolItems;

    // 赛道过滤
    if (selectedSector !== "全部") {
      result = result.filter((item) => item.sector === selectedSector);
    }

    // 二级分类过滤
    result = filterByStoredSubsector(result, selectedSubSector);

    // T+0 过滤
    if (onlyT0) {
      result = result.filter((item) => item.is_t0);
    }

    // ATR 弹性过滤
    if (selectedElasticity !== "全部") {
      result = result.filter((item) => item.elasticity === selectedElasticity);
    }

    // 搜索关键字过滤
    if (searchKeyword.trim()) {
      const kw = searchKeyword.trim().toLowerCase();
      result = result.filter(
        (item) =>
          item.etf_code.toLowerCase().includes(kw) ||
          item.name.toLowerCase().includes(kw)
      );
    }

    return result;
  }, [
    maturePoolItems,
    selectedSector,
    selectedSubSector,
    onlyT0,
    selectedElasticity,
    searchKeyword,
  ]);

  const isSearching = Boolean(searchKeyword.trim());
  const shouldShowAll = isSearching || isExpanded;
  const visibleLimit = shouldShowAll ? CARD_RENDER_LIMIT : DEFAULT_COLLAPSE_LIMIT;
  const renderedItems = filteredItems.slice(0, visibleLimit);
  const hiddenCount = Math.max(0, filteredItems.length - renderedItems.length);
  const sectorHitCount =
    selectedSector === "全部"
      ? currentMaturityTotal
      : sectorCountMap[selectedSector] ?? filteredItems.length;
  const selectedSubCount = currentSubSectors.find((item) => item.name === selectedSubSector)?.count;
  const usesClientFilter = Boolean(searchKeyword.trim());
  const hitCount = usesClientFilter
    ? filteredItems.length
    : selectedSubSector !== "全部"
      ? selectedSubCount ?? filteredItems.length
      : sectorHitCount;
  const truncationLabel = buildTruncationLabel(hitCount, shouldShowAll ? renderedItems.length : filteredItems.length);

  return (
    <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-xl border border-gray-100 dark:border-gray-700 p-6 sm:p-8 space-y-6">
      {/* 标题栏与双重护城河介绍 */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-gray-100 dark:border-gray-700 pb-5">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-2xl">🎯</span>
            <h2 className="text-xl sm:text-2xl font-black text-gray-900 dark:text-gray-100 tracking-tight">
              全市场做 T 核心 ETF 选品雷达
            </h2>
            <span className="bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300 text-xs px-2.5 py-1 rounded-full font-bold border border-emerald-200 dark:border-emerald-800">
              {storageBadge(poolData.storage_label)}
            </span>
            <Link
              to="/grid-fit"
              className="text-xs font-semibold text-indigo-700 underline"
            >
              网格适合度榜
            </Link>
          </div>
          <p className="text-xs sm:text-sm text-gray-500 dark:text-gray-400 mt-1.5 flex items-center gap-1.5">
            <span>🛡️</span>
            <span>
              三重品质护城河：已过滤上市未满 3 年次新、月均成交低于 3,000 万元的标的。{atrFloorLabel(minAtr, commodityExempt)}。
            </span>
          </p>
        </div>

        {/* 快捷搜索框 (带历史下拉) */}
        <div ref={searchContainerRef} className="relative w-full sm:w-72">
          <input
            ref={searchInputRef}
            type="text"
            placeholder="搜索代码 / 名称... (按 / 聚焦)"
            value={searchKeyword}
            onFocus={() => setIsHistoryOpen(true)}
            onBlur={() => {
              // 延迟关闭，确保点击下拉项能被触发
              setTimeout(() => setIsHistoryOpen(false), 200);
            }}
            onChange={(e) => setSearchKeyword(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && filteredItems.length > 0) {
                const target = filteredItems[0];
                handleRecordHistory(target);
                if (onSelectETF) onSelectETF(target.etf_code);
                setIsHistoryOpen(false);
              }
            }}
            className="w-full pl-9 pr-4 py-2 bg-gray-50 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600 rounded-xl text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-900 dark:text-gray-100"
          />
          <span className="absolute left-3 top-2.5 text-gray-400 text-sm">🔍</span>

          <SearchHistoryDropdown
            history={searchHistory}
            isOpen={isHistoryOpen && !searchKeyword.trim()}
            onSelect={handleSelectFromHistory}
            onRemove={handleRemoveHistory}
            onClear={handleClearHistory}
          />
        </div>
      </div>

      {/* 核心成熟度梯队切换：默认展示历经 5 年牛熊标的 */}
      <div className="flex flex-wrap items-center justify-between gap-2.5 p-2.5 bg-slate-50/80 dark:bg-slate-800/60 rounded-xl border border-slate-200/80 dark:border-slate-700/60">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-slate-700 dark:text-slate-300 flex items-center gap-1">
            <span>🛡️</span>
            <span>上市成熟度:</span>
          </span>
          <div className="inline-flex rounded-lg bg-slate-200/80 dark:bg-slate-700/80 p-0.5 text-xs font-semibold">
            <button
              type="button"
              onClick={() => {
                setMaturityFilter("5y");
                setIsExpanded(false);
              }}
              className={`px-3 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                maturityFilter === "5y"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-bold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <span>★ 历经5年牛熊</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300 font-mono">
                {maturity5yCount}
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMaturityFilter("3y");
                setIsExpanded(false);
              }}
              className={`px-3 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                maturityFilter === "3y"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-bold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <span>满3年成熟</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-300/80 dark:bg-slate-600 text-slate-700 dark:text-slate-300 font-mono">
                {maturity3yCount}
              </span>
            </button>
            <button
              type="button"
              onClick={() => {
                setMaturityFilter("all");
                setIsExpanded(false);
              }}
              className={`px-3 py-1 rounded-md transition-all flex items-center gap-1.5 ${
                maturityFilter === "all"
                  ? "bg-white dark:bg-slate-900 text-blue-600 dark:text-blue-400 shadow-sm font-bold"
                  : "text-slate-600 dark:text-slate-400 hover:text-slate-900"
              }`}
            >
              <span>全量活跃池</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded-full bg-slate-300/80 dark:bg-slate-600 text-slate-700 dark:text-slate-300 font-mono">
                {maturityAllCount}
              </span>
            </button>
          </div>
        </div>
        <span className="text-[11px] text-slate-500 dark:text-slate-400 hidden sm:inline">
          {poolBackfillHint
            ? poolBackfillHint
            : maturityFilter === "5y"
            ? "已精选历经完整牛熊大考的元老标的，历史回测扎实"
            : maturityFilter === "3y"
            ? "涵盖满3年的高流动细分ETF，兼顾弹性与周期稳定性"
            : "当前库里的高流动做T标的，含近两年上市的高弹性次新"}
        </span>
      </div>

      {/* 第一层：8 大产业链赛道胶囊切换 (带动态真实总数) */}
      <div className="space-y-2.5">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            产业与资产赛道 (互斥主分类)
          </span>
          <span className="text-xs font-semibold text-gray-400">
            共精选出 {currentMaturityTotal} 只成熟标的
          </span>
        </div>
        <div className="flex flex-wrap gap-2">
          {PRIMARY_SECTORS.map((sector) => {
            const isSelected = selectedSector === sector;
            const count =
              sector === "全部"
                ? currentMaturityTotal
                : sectorCountMap[sector] ?? 0;

            return (
              <button
                key={sector}
                onClick={() => handlePrimarySectorChange(sector)}
                className={`px-3.5 py-1.5 rounded-xl text-xs sm:text-sm font-semibold transition-all duration-200 flex items-center gap-1.5 ${
                  isSelected
                    ? "bg-blue-600 text-white shadow-md shadow-blue-500/20 scale-105"
                    : "bg-gray-100 dark:bg-gray-700/60 text-gray-600 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600"
                }`}
              >
                <span>{sector}</span>
                <span
                  className={`text-[11px] px-1.5 py-0.2 rounded-full font-mono ${
                    isSelected
                      ? "bg-blue-700 text-blue-100"
                      : "bg-gray-200 dark:bg-gray-600 text-gray-500 dark:text-gray-300"
                  }`}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 第二层：选定赛道后的二级产业链细分下钻展开 (带数量标记) */}
      {currentSubSectors.length > 0 && (
        <div className="p-3.5 bg-blue-50/60 dark:bg-blue-950/30 rounded-xl border border-blue-100 dark:border-blue-900/50 space-y-2 animate-fadeIn">
          <div className="flex items-center gap-1.5 text-xs font-bold text-blue-800 dark:text-blue-300">
            <span>▼</span>
            <span>{selectedSector} 产业链细分下钻:</span>
          </div>
          <div className="flex flex-wrap gap-2">
            {currentSubSectors.map((sub) => {
              const isSubSelected = selectedSubSector === sub.name;
              return (
                <button
                  key={sub.name}
                  onClick={() => setSelectedSubSector(sub.name)}
                  className={`px-3 py-1 rounded-lg text-xs font-semibold transition-all flex items-center gap-1.5 ${
                    isSubSelected
                      ? "bg-blue-600 text-white shadow-sm scale-105"
                      : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-blue-200/60 dark:border-gray-700 hover:bg-blue-100/50"
                  }`}
                >
                  <span>{sub.name}</span>
                  <span
                    className={`text-[10px] font-mono px-1 rounded ${
                      isSubSelected
                        ? "bg-blue-700 text-white"
                        : "bg-gray-100 dark:bg-gray-700 text-gray-500"
                    }`}
                  >
                    {sub.count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* 第三层：正交量化特征过滤器 */}
      <div className="flex flex-wrap items-center justify-between gap-4 p-4 bg-gray-50 dark:bg-gray-900/40 rounded-xl border border-gray-100 dark:border-gray-700">
        {/* T+0 开关 */}
        <div className="flex items-center gap-3">
          <span className="text-xs font-bold text-gray-500 dark:text-gray-400">交易机制:</span>
          <button
            onClick={() => setOnlyT0(!onlyT0)}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 transition-all ${
              onlyT0
                ? "bg-amber-500 text-white shadow-sm"
                : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-600 hover:border-amber-500"
            }`}
          >
            <span>⚡</span>
            <span>仅看日内 T+0 ({currentT0Count}只)</span>
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-bold text-gray-500 dark:text-gray-400">ATR 门槛:</span>
          {[
            ["1.5", "1.5% 默认"],
            ["1.0", "放宽到 1.0%"],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setMinAtr(value)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium ${
                minAtr === value
                  ? "bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-bold"
                  : "text-gray-600 dark:text-gray-400"
              }`}
            >
              {label}
            </button>
          ))}
          <label className="flex items-center gap-1.5 text-xs text-gray-600 dark:text-gray-300">
            <input
              type="checkbox"
              checked={commodityExempt}
              onChange={(event) => setCommodityExempt(event.target.checked)}
            />
            黄金/大宗商品豁免到 1.0%
          </label>
        </div>

        {/* ATR 弹性档位 */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-gray-500 dark:text-gray-400">ATR 弹性:</span>
          {["全部", "高弹性", "稳健型", "低波防守"].map((elast) => (
            <button
              key={elast}
              onClick={() => setSelectedElasticity(elast)}
              className={`px-2.5 py-1 rounded-lg text-xs font-medium transition-all ${
                selectedElasticity === elast
                  ? "bg-blue-100 dark:bg-blue-900/60 text-blue-700 dark:text-blue-300 font-bold"
                  : "text-gray-600 dark:text-gray-400 hover:text-gray-900"
              }`}
            >
              {elast}
            </button>
          ))}
        </div>
      </div>

      {poolData.unclassified_count > 0 && (
        <div className="rounded-xl border border-dashed border-gray-200 dark:border-gray-700 px-4 py-3">
          <button
            type="button"
            onClick={() => {
              const next = !showUnclassified;
              setShowUnclassified(next);
              if (next && unclassifiedItems.length === 0) {
                fetchUnclassified();
              }
            }}
            className="text-xs font-semibold text-gray-500 dark:text-gray-400"
          >
            {showUnclassified ? "收起" : "展开"}未归类（{poolData.unclassified_count}）· 不进入选品与回测宇宙
          </button>
          {showUnclassified && (
            <p className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              这些名称无法归入 11 个可购赛道，默认不出现在主列表。它们不计入「全部」，也不进入网格适合度榜。
              {unclassifiedItems.length > 0
                ? ` ${unclassifiedItems.map((item) => item.name).slice(0, 8).join("、")}${unclassifiedItems.length > 8 ? "…" : ""}`
                : ""}
            </p>
          )}
        </div>
      )}

      {/* 标的卡片网格列表 */}
      {loading ? (
        <div className="py-12 flex flex-col items-center justify-center space-y-3">
          <div className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
          <span className="text-xs text-gray-500">正在从本地数据库提取标的池...</span>
        </div>
      ) : filteredItems.length === 0 ? (
        <div className="py-12 text-center text-gray-400 text-sm">
          {poolBackfillHint || "未匹配到符合条件的标的，可尝试切换其他细分赛道"}
        </div>
      ) : (
        <div className="space-y-3">
          {truncationLabel && (
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {truncationLabel}
              。标题中的总数是当前赛道命中数，不是本页已画出的卡片数。
              {searchKeyword.trim() ? " 搜索只作用于已返回列表，不是全宇宙。" : ""}
            </p>
          )}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {renderedItems.map((item) => {
            const isUp = item.pct_change >= 0;
            return (
              <div
                key={item.etf_code}
                onClick={() => {
                  handleRecordHistory(item);
                  if (onSelectETF) onSelectETF(item.etf_code, item);
                }}
                className="bg-white dark:bg-gray-800/90 border border-gray-100 dark:border-gray-700/80 rounded-xl p-4 hover:shadow-lg hover:border-blue-400 dark:hover:border-blue-500 transition-all duration-200 group flex flex-col justify-between cursor-pointer"
              >
                <div>
                  {/* 第一行：代码、名称与徽章 */}
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-1.5 min-w-0 pr-1">
                      {item.is_seed && (
                        <span
                          className="bg-amber-100 dark:bg-amber-950/80 text-amber-800 dark:text-amber-200 text-[10px] font-black px-1.5 py-0.5 rounded border border-amber-300 dark:border-amber-700 shrink-0 flex items-center gap-0.5"
                          title="该细分赛道代表性种子标的"
                        >
                          <span>👑</span>
                          <span>种子</span>
                        </span>
                      )}
                      <span className="font-mono font-black text-gray-900 dark:text-gray-100 text-base">
                        {item.etf_code}
                      </span>
                      <span className="font-bold text-gray-800 dark:text-gray-200 text-sm truncate">
                        {item.name}
                      </span>
                    </div>

                    <div className="flex items-center gap-1 shrink-0">
                      {item.is_t0 && (
                        <span className="bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300 text-[10px] font-black px-1.5 py-0.5 rounded border border-amber-300 dark:border-amber-800">
                          T+0
                        </span>
                      )}
                      {renderScoreBadge(item)}
                    </div>
                  </div>

                  {/* 第二行：赛道分类与弹性标签 */}
                  <div className="flex items-center gap-2 mb-3">
                    <span className="bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs px-2 py-0.5 rounded">
                      {item.sector}
                    </span>
                    {Number(item.atr_pct) >= 1.8 && Number(item.atr_pct) <= 4.0 ? (
                      <span className="bg-emerald-50 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-300 border border-emerald-200/80 dark:border-emerald-800/80 text-xs px-2 py-0.5 rounded font-bold flex items-center gap-1">
                        <span>🟢 黄金做T区</span>
                        <span className="font-mono font-normal text-[11px]">(ATR {item.atr_pct}%)</span>
                      </span>
                    ) : (
                      <span
                        className={`text-xs px-2 py-0.5 rounded font-medium ${
                          item.elasticity === "高弹性"
                            ? "bg-rose-50 dark:bg-rose-950/60 text-rose-600 dark:text-rose-400"
                            : item.elasticity === "稳健型"
                            ? "bg-blue-50 dark:bg-blue-950/60 text-blue-600 dark:text-blue-400"
                            : "bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400"
                        }`}
                      >
                        {item.elasticity} (ATR {item.atr_pct}%)
                      </span>
                    )}
                  </div>

                  {/* 第三行：行情与流动性指标 */}
                  <div className="grid grid-cols-2 gap-2 py-2 border-t border-b border-gray-50 dark:border-gray-700/50 text-xs mb-3">
                    <div>
                      <span className="text-gray-400 block text-[11px]">
                        最新价格{item.quote_date ? ` · ${item.quote_date}` : ""}
                      </span>
                      <span className="font-bold font-mono text-gray-800 dark:text-gray-200">
                        ¥{Number(item.latest_price).toFixed(3)}
                      </span>
                      <span
                        className={`ml-1.5 font-semibold font-mono ${
                          isUp ? "text-rose-500" : "text-emerald-500"
                        }`}
                      >
                        {isUp ? "+" : ""}
                        {Number(item.pct_change).toFixed(2)}%
                      </span>
                    </div>
                    <div className="text-right">
                      <span className="text-gray-400 block text-[10px]">
                        今日: {item.amount_10k >= 10000 ? `${(item.amount_10k / 10000).toFixed(2)}亿` : `${Number(item.amount_10k).toFixed(0)}万`}
                      </span>
                      <span className="font-bold font-mono text-blue-600 dark:text-blue-400 block text-[11px]">
                        月均: {item.amount_ma20_10k >= 10000 ? `${(item.amount_ma20_10k / 10000).toFixed(2)} 亿元` : `${Number(item.amount_ma20_10k).toFixed(0)} 万元`}
                      </span>
                    </div>
                  </div>
                </div>

                {/* 底部一键带入按钮 */}
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    handleRecordHistory(item);
                    if (onSelectETF) {
                      onSelectETF(item.etf_code, item);
                    }
                  }}
                  className="w-full mt-1 py-1.5 bg-blue-50 hover:bg-blue-600 text-blue-600 hover:text-white dark:bg-blue-950/50 dark:hover:bg-blue-600 dark:text-blue-300 dark:hover:text-white text-xs font-bold rounded-lg transition-all flex items-center justify-center gap-1 group-hover:scale-[1.02]"
                >
                  <span>⚡</span>
                  <span>快速测算 (载入右侧)</span>
                </button>
              </div>
            );
          })}
        </div>

        {/* 底部渐进式展开 / 收起控制条 */}
        {!isSearching && filteredItems.length > DEFAULT_COLLAPSE_LIMIT && (
          <div className="pt-2 flex flex-col items-center gap-2">
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="w-full sm:w-auto px-6 py-2.5 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-gray-700 dark:to-gray-750 hover:from-blue-100 hover:to-indigo-100 text-blue-700 dark:text-blue-300 font-bold text-xs rounded-xl border border-blue-200/80 dark:border-gray-600 shadow-2xs hover:shadow-xs transition-all flex items-center justify-center gap-2 group cursor-pointer"
            >
              {isExpanded ? (
                <>
                  <span>收起标的列表 (回到前 6 只精选)</span>
                  <span className="text-sm transition-transform group-hover:-translate-y-0.5">▴</span>
                </>
              ) : (
                <>
                  <span>展开当前分类其余标的 (共 {filteredItems.length} 只，{hiddenCount} 只已收拢)</span>
                  <span className="text-sm transition-transform group-hover:translate-y-0.5">▾</span>
                </>
              )}
            </button>
            <span className="text-[11px] text-gray-400">
              💡 提示：在上方搜索框直接输入代码或拼音/名称，可自动全显所有匹配标的
            </span>
          </div>
        )}
        </div>
      )}
    </div>
  );
}
