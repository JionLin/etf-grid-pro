import React, { useState, useEffect, useRef } from "react";
import {
  X,
  BookOpen,
  Quote,
  Sparkles,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { getEdaLiterature } from "@shared/services/api";

// 三篇经典金句摘录
const GOLDEN_QUOTES = {
  1: {
    title: "E大体系箴言：长短结合",
    quote:
      "投资体系包括观察金融世界的体系与一套操作系统。网格策略是一个中短期波段策略，它要吃的并不是长牛利润，而是情绪与波动的钱。网格是整个体系中不可或缺的配角，用以消除长期持仓频繁坐过山车的焦虑感。",
    badge: "体系构建 · 长期与短期结合",
  },
  2: {
    title: "E大风控箴言：压力测试",
    quote:
      "压力测试是最重要的。做网格的品种，一定是有底的、不会死的品种。能不淡定吗？我在买入前都已经无数次沙盘推演现在情况出现后的情形，真发生了只是预料之中，有什么不淡定的？",
    badge: "风控铁律 · 压力测试最重要",
  },
  3: {
    title: "E大升级箴言：破局牛市卖飞",
    quote:
      "在一波强势上涨中，赚得不够多？赚少了没关系，我们升级。留利润（留股不留钱，0成本永久锁仓）、逐格加码（越跌买越多）、大中小网一网打尽（大网第一格43%利润，第二格75%！）。",
    badge: "2.0升级 · 留利润与一网打尽",
  },
};

/**
 * E大网格实战文献阅读抽屉组件
 */
const EdaLiteratureDrawer = ({ isOpen, onClose }) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState(null);
  const [activeId, setActiveId] = useState(1);
  const [error, setError] = useState(null);
  const contentContainerRef = useRef(null);

  // 监听 ESC 键关闭抽屉
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  // 打开抽屉时加载数据
  useEffect(() => {
    if (isOpen && !data) {
      setLoading(true);
      setError(null);
      getEdaLiterature()
        .then((res) => {
          if (res?.success && res.data) {
            setData(res.data);
          } else {
            setError(res?.error || "文献内容获取失败");
          }
        })
        .catch((err) => {
          setError(err?.message || "网络请求异常，请稍后重试");
        })
        .finally(() => setLoading(false));
    }
  }, [isOpen, data]);

  // 切换篇章时平滑滚回顶部
  useEffect(() => {
    if (contentContainerRef.current) {
      contentContainerRef.current.scrollTop = 0;
    }
  }, [activeId]);

  if (!isOpen) return null;

  const currentArticle = data?.articles?.find((a) => a.id === activeId) || data?.articles?.[0];
  const quoteInfo = GOLDEN_QUOTES[activeId] || GOLDEN_QUOTES[1];

  // 格式化渲染 Markdown 文本行
  const renderFormattedContent = (content) => {
    if (!content) return null;
    const lines = content.split("\n");

    return lines.map((line, idx) => {
      const trimmed = line.trim();

      // 空行
      if (!trimmed) {
        return <div key={idx} className="h-4"></div>;
      }

      // 二级标题
      if (trimmed.startsWith("## ")) {
        return (
          <h3
            key={idx}
            className="text-lg font-bold text-gray-900 mt-6 mb-3 flex items-center gap-2 border-b border-gray-100 pb-2"
          >
            <span className="w-1.5 h-4 bg-amber-500 rounded-full inline-block"></span>
            {trimmed.replace(/^##\s*/, "")}
          </h3>
        );
      }

      // 三级标题
      if (trimmed.startsWith("### ")) {
        return (
          <h4 key={idx} className="text-base font-bold text-gray-800 mt-5 mb-2 text-indigo-950">
            {trimmed.replace(/^###\s*/, "")}
          </h4>
        );
      }

      // 强调粗体段落或标注
      if (trimmed.startsWith("*   ") || trimmed.startsWith("- ")) {
        return (
          <li key={idx} className="ml-5 list-disc text-sm text-gray-700 my-1 leading-relaxed">
            {renderInlineMarkdown(trimmed.replace(/^(\*\s+|-\s+)/, ""))}
          </li>
        );
      }

      // 引用块
      if (trimmed.startsWith("> ")) {
        return (
          <blockquote
            key={idx}
            className="border-l-4 border-amber-400 bg-amber-50/60 px-4 py-2 my-3 rounded-r text-xs text-amber-900 italic"
          >
            {renderInlineMarkdown(trimmed.replace(/^>\s*/, ""))}
          </blockquote>
        );
      }

      // 图片或图表示意占位
      if (trimmed.startsWith("*[图片") || trimmed.startsWith("*(注：")) {
        return (
          <div
            key={idx}
            className="my-3 p-3 bg-slate-50 border border-dashed border-slate-300 rounded-xl text-xs text-slate-500 text-center font-mono"
          >
            📊 {trimmed.replace(/^[*(\]]+|[*)\\]]+$/g, "")}
          </div>
        );
      }

      // 常规正文段落
      return (
        <p key={idx} className="text-sm text-gray-700 leading-relaxed my-2 text-justify">
          {renderInlineMarkdown(trimmed)}
        </p>
      );
    });
  };

  // 行内粗体格式化
  const renderInlineMarkdown = (text) => {
    const parts = text.split(/(\*\*.*?\*\*)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return (
          <strong key={i} className="text-gray-900 font-bold bg-amber-100/50 px-1 rounded">
            {part.slice(2, -2)}
          </strong>
        );
      }
      return part;
    });
  };

  return (
    <div className="fixed inset-0 z-50 overflow-hidden select-none">
      {/* 背景深色模糊遮罩 */}
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      <div className="fixed inset-y-0 right-0 max-w-4xl w-full flex pl-10">
        <div className="w-full bg-white shadow-2xl flex flex-col transform transition-transform duration-300 ease-in-out">
          {/* 抽屉顶部头部 */}
          <div className="px-6 py-4 border-b border-gray-200 bg-slate-900 text-white flex items-center justify-between shadow-sm">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-amber-500/20 text-amber-400 rounded-xl border border-amber-500/30">
                <BookOpen className="w-5 h-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-white tracking-wide">
                    E大（ETF拯救世界）网格策略实战全集
                  </h2>
                  <span className="text-[10px] bg-amber-400/20 text-amber-300 border border-amber-400/40 px-2 py-0.5 rounded-full font-mono">
                    经典真迹 · 完整收录
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  凝结整整十余年实践与失误反思的波段交易与情绪收割系统
                </p>
              </div>
            </div>

            {/* 关闭按钮 */}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="按 ESC 键或点击关闭"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 篇章切换标签栏 */}
          <div className="px-6 py-3 bg-slate-50 border-b border-gray-200 flex flex-wrap items-center gap-2">
            {[
              { id: 1, label: "篇章一：体系与策略", desc: "写在前面 · 体系构建 · 波段定位" },
              { id: 2, label: "篇章二：1.0与压力测试", desc: "不死品种 · 压力测试极值" },
              { id: 3, label: "篇章三：2.0升级终极大招", desc: "留利润破卖飞 · 逐格加码 · 一网打尽" },
            ].map((tab) => {
              const isSelected = activeId === tab.id;
              return (
                <button
                  key={tab.id}
                  type="button"
                  onClick={() => setActiveId(tab.id)}
                  className={`py-2 px-3 rounded-xl text-xs font-medium transition-all text-left flex flex-col gap-0.5 border ${
                    isSelected
                      ? "bg-amber-500 text-slate-950 border-amber-500 font-bold shadow-xs ring-2 ring-amber-400/40"
                      : "bg-white text-gray-700 border-gray-200 hover:bg-gray-100"
                  }`}
                >
                  <span className="flex items-center gap-1.5">
                    <span className={`w-1.5 h-1.5 rounded-full ${isSelected ? "bg-slate-950" : "bg-amber-500"}`}></span>
                    {tab.label}
                  </span>
                  <span className={`text-[10px] ${isSelected ? "text-slate-800" : "text-gray-400"}`}>
                    {tab.desc}
                  </span>
                </button>
              );
            })}
          </div>

          {/* 正文阅读滚动区域 */}
          <div
            ref={contentContainerRef}
            className="flex-1 overflow-y-auto px-8 py-6 select-text space-y-5 font-sans"
          >
            {loading && (
              <div className="py-24 flex flex-col items-center justify-center gap-3 text-gray-400">
                <RefreshCw className="w-6 h-6 animate-spin text-amber-500" />
                <span className="text-xs">正在调取经典实战文献...</span>
              </div>
            )}

            {error && !loading && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl text-xs text-red-700">
                文献加载异常: {error}
              </div>
            )}

            {!loading && !error && currentArticle && (
              <>
                {/* 篇章醒目名牌 */}
                <div className="border-b border-gray-200 pb-4">
                  <span className="text-xs font-bold text-amber-600 uppercase tracking-wider">
                    E大长赢指数实战心血 · 篇章 {activeId}
                  </span>
                  <h1 className="text-xl font-black text-gray-900 mt-1">
                    {currentArticle.title}
                  </h1>
                </div>

                {/* 黄金金句领读卡片 */}
                {quoteInfo && (
                  <div className="p-4 rounded-2xl bg-gradient-to-r from-amber-50 to-orange-50/50 border border-amber-200 shadow-2xs">
                    <div className="flex items-center justify-between mb-2">
                      <span className="inline-flex items-center gap-1.5 text-xs font-bold text-amber-900">
                        <Quote className="w-4 h-4 text-amber-600" />
                        {quoteInfo.title}
                      </span>
                      <span className="text-[10px] bg-amber-200/60 text-amber-900 px-2 py-0.5 rounded-full font-semibold">
                        {quoteInfo.badge}
                      </span>
                    </div>
                    <p className="text-xs text-amber-950/90 leading-relaxed font-serif italic">
                      &ldquo;{quoteInfo.quote}&rdquo;
                    </p>
                  </div>
                )}

                {/* 正文格式化排版 */}
                <div className="pt-2">
                  {renderFormattedContent(currentArticle.content)}
                </div>

                {/* 文末收尾鼓励卡片 */}
                <div className="mt-8 p-4 bg-slate-50 border border-slate-200 rounded-xl text-center text-xs text-slate-600">
                  <Sparkles className="w-4 h-4 text-amber-500 mx-auto mb-1.5" />
                  <span>“所有的持有或卖出计划，早在买入前就已经制定好。真发生了只是预料之中，有什么不淡定的？”</span>
                </div>
              </>
            )}
          </div>

          {/* 抽屉底部导航条 */}
          <div className="px-6 py-3 border-t border-gray-200 bg-gray-50 flex items-center justify-between text-xs text-gray-500">
            <span>按 ESC 或点击遮罩退出阅读</span>
            <div className="flex items-center gap-3">
              {activeId > 1 && (
                <button
                  type="button"
                  onClick={() => setActiveId(activeId - 1)}
                  className="px-3 py-1 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-100 font-medium transition-colors"
                >
                  上一篇
                </button>
              )}
              {activeId < 3 && (
                <button
                  type="button"
                  onClick={() => setActiveId(activeId + 1)}
                  className="px-3 py-1 bg-amber-500 text-slate-950 font-bold rounded-lg hover:bg-amber-400 transition-colors flex items-center gap-1"
                >
                  下一篇
                  <ChevronRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default EdaLiteratureDrawer;
