import React from "react";
import { Eye, ThermometerSun, Grid3X3, TrendingUp, Database } from "lucide-react";

/**
 * 报告标签页导航组件
 * 负责标签页的导航和切换
 */
export default function ReportTabs({ activeTab, onTabChange }) {
  const tabs = [
    { id: "overview", label: "概览看板", icon: <Eye className="w-4 h-4" /> },
    {
      id: "strategy",
      label: "立体网格策略",
      icon: <Grid3X3 className="w-4 h-4" />,
    },
    {
      id: "backtest",
      label: "历史策略回测",
      icon: <TrendingUp className="w-4 h-4" />,
    },
    {
      id: "suitability",
      label: "标的体检报告",
      icon: <ThermometerSun className="w-4 h-4" />,
    },
    {
      id: "archive",
      label: "回测档案库",
      icon: <Database className="w-4 h-4" />,
    },
  ];

  return (
    <div className="border-b border-gray-200 dark:border-gray-700 overflow-x-auto max-w-full">
      <nav className="flex gap-4 sm:gap-8 px-4 sm:px-6 w-max min-w-full">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => onTabChange(tab.id)}
            className={`flex items-center gap-2 py-4 px-2 border-b-2 font-medium text-sm transition-colors ${
              activeTab === tab.id
                ? "border-blue-500 text-blue-600 dark:text-blue-300"
                : "border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 hover:border-gray-300"
            }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </nav>
    </div>
  );
}
