import React, { lazy, Suspense, useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Waypoints, Github, BookOpen, LayoutDashboard, Trophy } from "lucide-react";
import { getVersion } from "@shared/services/api";

const EdaLiteratureDrawer = lazy(() => import("@features/literature/components/EdaLiteratureDrawer"));

/**
 * 应用头部组件
 * 负责全局品牌回退、主导航切换胶囊、E大文献抽屉与版本信息
 */
export default function AppHeader() {
  const [version, setVersion] = useState("v1.0.0");
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [drawerMounted, setDrawerMounted] = useState(false);
  const location = useLocation();

  useEffect(() => {
    const fetchVersion = async () => {
      try {
        const response = await getVersion();
        if (response.success && response.data.version) {
          setVersion(`v${response.data.version}`);
        }
      } catch (error) {
        console.error("获取版本号失败:", error);
      }
    };

    fetchVersion();
  }, []);

  const isStrategyActive =
    location.pathname === "/" || location.pathname.startsWith("/analysis");
  const isGridFitActive = location.pathname.startsWith("/grid-fit");

  const auxActions = (
    <>
      <button
        type="button"
        onClick={() => {
          setDrawerMounted(true);
          setIsDrawerOpen(true);
        }}
        className="flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-xl text-xs font-bold text-amber-900 bg-gradient-to-r from-amber-100 to-amber-200/80 hover:from-amber-200 hover:to-amber-300 border border-amber-300/80 dark:from-amber-900/40 dark:to-amber-800/40 dark:text-amber-100 dark:border-amber-700/80 shadow-2xs transition-all cursor-pointer"
        title="点击阅读 E大（ETF拯救世界）网格三篇真迹"
      >
        <BookOpen className="w-3.5 h-3.5 text-amber-700 dark:text-amber-300" />
        <span className="hidden sm:inline">📚 E大网格文献</span>
        <span className="sm:hidden">文献</span>
      </button>
      <a
        href="https://github.com/jorben/etf-grid-design"
        target="_blank"
        rel="noopener noreferrer"
        className="flex items-center gap-1.5 px-2.5 py-1.5 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg transition-colors text-xs font-mono"
        title="查看开源仓库"
      >
        <Github className="w-4 h-4" />
        <span className="hidden lg:inline">{version}</span>
      </a>
    </>
  );

  const navLinkClass = (active) =>
    `flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-lg font-medium transition-all whitespace-nowrap ${
      active
        ? "bg-white dark:bg-gray-900 text-indigo-600 dark:text-indigo-300 font-bold shadow-xs"
        : "text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white hover:bg-gray-200/50 dark:hover:bg-gray-700/60"
    }`;

  return (
    <header className="bg-white/95 dark:bg-gray-900/95 backdrop-blur-md shadow-xs border-b border-gray-200/80 dark:border-gray-700 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8">
        <div className="flex flex-col gap-2 py-2 sm:h-16 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:py-0">
          <div className="flex items-center justify-between gap-2 min-w-0">
          <Link
            to="/"
            className="flex items-center gap-2 sm:gap-3 group min-w-0"
            title="返回首页策略设计器"
          >
            <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl shadow-xs group-hover:shadow-indigo-200 group-hover:scale-105 transition-all shrink-0">
              <Waypoints className="w-5 h-5 text-white" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <span className="text-base sm:text-xl font-black text-gray-900 dark:text-gray-100 tracking-tight group-hover:text-indigo-600 dark:group-hover:text-indigo-300 transition-colors truncate">
                  ETFer.Top
                </span>
                <span className="hidden sm:inline-block text-[10px] font-mono px-1.5 py-0.2 rounded bg-indigo-50 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-200 font-bold border border-indigo-200/60 dark:border-indigo-800">
                  QUANT
                </span>
              </div>
              <p className="text-[11px] text-gray-400 dark:text-gray-500 hidden md:block">
                基于ATR算法的智能网格交易策略设计工具
              </p>
            </div>
          </Link>
          <div className="flex items-center gap-2 shrink-0 sm:hidden">{auxActions}</div>
          </div>

          <nav className="flex items-center self-stretch sm:self-auto bg-gray-100/90 dark:bg-gray-800 p-1 rounded-xl border border-gray-200/60 dark:border-gray-700 text-xs shadow-2xs max-w-full overflow-x-auto">
            <Link to="/" className={navLinkClass(isStrategyActive)}>
              <LayoutDashboard className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
              <span>策略工作台</span>
            </Link>
            <Link to="/grid-fit" className={navLinkClass(isGridFitActive)}>
              <Trophy className="w-3.5 h-3.5 text-amber-500 shrink-0" />
              <span>网格适合度榜</span>
            </Link>
          </nav>

          <div className="hidden sm:flex items-center gap-2 sm:gap-3 shrink-0">{auxActions}</div>
        </div>
      </div>

      {/* E大实战文献阅读抽屉 */}
      {drawerMounted && (
        <Suspense fallback={null}>
          <EdaLiteratureDrawer
            isOpen={isDrawerOpen}
            onClose={() => setIsDrawerOpen(false)}
          />
        </Suspense>
      )}
    </header>
  );
}
