import React, { useEffect } from "react";
import PropTypes from "prop-types";
import {
  X,
  HelpCircle,
  TrendingUp,
  Scale,
  ShieldCheck,
  Coins,
  Sparkles,
  Calendar,
} from "lucide-react";

/**
 * 多周期回测天梯算法与评测口径详细说明弹窗
 */
export default function MethodologyModal({ isOpen, onClose }) {
  // 监听 ESC 键关闭弹窗
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto animate-in fade-in duration-150">
      {/* 遮罩层 */}
      <div
        className="fixed inset-0 bg-slate-900/60 backdrop-blur-xs transition-opacity"
        onClick={onClose}
      />

      {/* 弹窗容器 */}
      <div className="flex min-h-full items-center justify-center p-3 sm:p-4 text-left">
        <div className="relative bg-white dark:bg-gray-850 rounded-2xl shadow-2xl border border-gray-100 dark:border-gray-700 max-w-2xl w-full p-5 sm:p-7 space-y-6 transform transition-all max-h-[90vh] overflow-y-auto">
          {/* 头部标题 */}
          <div className="flex items-start justify-between border-b border-gray-100 dark:border-gray-700 pb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-indigo-50 dark:bg-indigo-950/80 text-indigo-600 dark:text-indigo-400 flex items-center justify-center shrink-0">
                <TrendingUp className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base sm:text-lg font-black text-gray-900 dark:text-gray-100 flex items-center gap-2">
                  <span>多周期网格回测天梯 · 评测口径与算法说明</span>
                </h3>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">
                  当前库里成熟做 T 标的的统一量化基准与数学推导标准
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
              title="关闭说明"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* 1. 评测基准说明 */}
          <div className="p-3.5 bg-indigo-50/70 dark:bg-indigo-950/40 border border-indigo-100 dark:border-indigo-900/50 rounded-xl space-y-2">
            <div className="flex items-center gap-2 text-xs font-bold text-indigo-900 dark:text-indigo-300">
              <Sparkles className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
              <span>统一天梯评测基准（消除横向比较偏见）</span>
            </div>
            <p className="text-xs text-indigo-800 dark:text-indigo-300 leading-relaxed">
              为了让当前库里的做 T 标的在同一尺度下公平竞技，多周期回测天梯大宽表固定采用 <strong>E 大网格 2.0 / 3.0 经典成熟基准</strong>：
              <strong>初始本金 30,000 元</strong>（50% 底仓 + 50% 现金流动池）、
              <strong>180日动态 ATR 三轨</strong>（小轨 0.6x / 中轨 1.2x / 大轨 2.5x）、
              <strong>倒金字塔加码 10%</strong>（越跌越买以平抑成本）、以及
              <strong>模式 B 利润池滚存留股</strong>。
            </p>
          </div>

          {/* 2. 模式 B (留股) vs 模式 A (全现金) 对照表 */}
          <div className="space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-bold text-gray-900 dark:text-gray-100">
              <Coins className="w-4 h-4 text-amber-500" />
              <span>模式 B（留利润）vs 模式 A（全现金）机制差异</span>
            </div>
            <div className="border border-gray-200 dark:border-gray-700 rounded-xl overflow-hidden text-xs">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300 font-semibold">
                    <th className="p-2.5">对比维度</th>
                    <th className="p-2.5 text-indigo-700 dark:text-indigo-400 bg-indigo-50/50 dark:bg-indigo-950/30">模式 B：聚沙成塔 · 滚存留股（天梯基准）</th>
                    <th className="p-2.5 text-gray-700 dark:text-gray-300">模式 A：落袋为安 · 全现金</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700 text-gray-700 dark:text-gray-300">
                  <tr>
                    <td className="p-2.5 font-medium bg-gray-50/40 dark:bg-gray-800/40">做T差价去向</td>
                    <td className="p-2.5 bg-indigo-50/20 dark:bg-indigo-950/10 font-medium">汇入利润蓄水池，每满当前价 100 股自动转增为永久 0 成本股票</td>
                    <td className="p-2.5">差价利润直接保留为可用现金，躺在现金池</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-medium bg-gray-50/40 dark:bg-gray-800/40">总市值核算</td>
                    <td className="p-2.5 bg-indigo-50/20 dark:bg-indigo-950/10 font-medium">现金 + 常规持仓市值 + <strong>0成本免费股票现值</strong> + 零钱</td>
                    <td className="p-2.5">现金 + 常规持仓市值</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-medium bg-gray-50/40 dark:bg-gray-800/40">主升浪表现</td>
                    <td className="p-2.5 bg-indigo-50/20 dark:bg-indigo-950/10 text-rose-600 dark:text-rose-400 font-bold">★ 免费股享受标的长期上涨复利，大幅增厚收益率</td>
                    <td className="p-2.5 text-gray-500">仅赚取固定差价，现金不享受标的资本利得</td>
                  </tr>
                  <tr>
                    <td className="p-2.5 font-medium bg-gray-50/40 dark:bg-gray-800/40">515220 5年实测</td>
                    <td className="p-2.5 bg-indigo-50/20 dark:bg-indigo-950/10 font-mono font-bold text-rose-600">年化 +18.13%（积攒 21,200 股免费股）</td>
                    <td className="p-2.5 font-mono text-gray-600">年化 +15.46%（纯现金留存）</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          {/* 3. 核心数学计算公式 */}
          <div className="space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-bold text-gray-900 dark:text-gray-100">
              <Scale className="w-4 h-4 text-emerald-600" />
              <span>收益率计算数学公式</span>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
              <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 space-y-1">
                <span className="font-bold text-gray-900 dark:text-gray-100">① 策略累计总收益率 (Total Return)</span>
                <p className="font-mono text-[11px] text-gray-600 dark:text-gray-300">
                  总收益率 = (期末总资产 - 初始本金) / 初始本金 × 100%
                </p>
                <p className="text-[11px] text-gray-400">衡量从回测首日投入至终点日期的绝对资本总增长。</p>
              </div>

              <div className="p-3 bg-gray-50 dark:bg-gray-800 rounded-xl border border-gray-100 dark:border-gray-700 space-y-1">
                <span className="font-bold text-gray-900 dark:text-gray-100">② 策略折算年化收益率 (Annualized Return)</span>
                <p className="font-mono text-[11px] text-gray-600 dark:text-gray-300">
                  折算年化 = 累计总收益率 × (365 / 实际日历跨度天数)
                </p>
                <p className="text-[11px] text-gray-400">时间归一化单利公式，消除不同标的自然日跨度差异，保证全市场可比性。</p>
              </div>
            </div>
          </div>

          {/* 4. 索提诺比率与水下韧性全解 (给小白的量化真相) */}
          <div className="space-y-2.5">
            <div className="flex items-center gap-2 text-xs font-bold text-gray-900 dark:text-gray-100">
              <ShieldCheck className="w-4 h-4 text-purple-600" />
              <span>为什么网格交易必须看索提诺（Sortino）？——给小白的波动率真相</span>
            </div>
            <div className="p-3.5 bg-purple-50/50 dark:bg-purple-950/20 rounded-xl border border-purple-100 dark:border-purple-900/40 text-xs space-y-2.5">
              <div className="space-y-1">
                <span className="font-bold text-purple-950 dark:text-purple-200">
                  通俗比喻：只看挨打时的性价比，不惩罚赚钱时的狂飙
                </span>
                <p className="text-gray-600 dark:text-gray-300 leading-relaxed text-[11px]">
                  传统<strong>夏普比率（Sharpe）</strong>把所有的价格波动都算作“风险”——哪怕某天标的脉冲暴涨让网格大笔高抛落袋，夏普也会将其视为“不稳定波动”而扣分；
                  而<strong>索提诺比率（Sortino）</strong>仅统计负收益的下行半方差。
                  <strong>它只考核策略在挨打下跌时承受了多少浮亏，而完全不惩罚暴涨冲高时的获利狂欢</strong>。
                </p>
              </div>

              {/* 段位对照表 */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 font-mono text-center">
                <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                  <div className="text-[11px] font-bold text-gray-500">&lt; 0.8</div>
                  <div className="text-[10px] text-gray-400 font-sans">偏弱防守</div>
                </div>
                <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-blue-200 dark:border-blue-900">
                  <div className="text-[11px] font-bold text-blue-600">0.8 ~ 1.4</div>
                  <div className="text-[10px] text-blue-500 font-sans">✓ 风险均衡</div>
                </div>
                <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-emerald-200 dark:border-emerald-900">
                  <div className="text-[11px] font-bold text-emerald-600">1.4 ~ 2.0</div>
                  <div className="text-[10px] text-emerald-500 font-sans">🚀 优秀抗跌</div>
                </div>
                <div className="p-2 bg-white dark:bg-gray-800 rounded-lg border border-purple-200 dark:border-purple-900">
                  <div className="text-[11px] font-bold text-purple-600">&gt; 2.0</div>
                  <div className="text-[10px] text-purple-500 font-sans">⭐ 极佳造血</div>
                </div>
              </div>
            </div>
          </div>

          {/* 4. 为什么会有横杠 "-" (物理上市风控说明) */}
          <div className="p-3 bg-slate-50 dark:bg-gray-800/60 rounded-xl border border-slate-200 dark:border-slate-700 space-y-1.5 text-xs">
            <div className="flex items-center gap-2 font-bold text-slate-800 dark:text-slate-200">
              <Calendar className="w-4 h-4 text-blue-500" />
              <span>为什么部分标的显示横杠 “-”？（上市未满风控保护）</span>
            </div>
            <p className="text-slate-600 dark:text-slate-400 leading-relaxed text-[11px]">
              系统采用<strong>严格的物理上市合规风控机制</strong>，杜绝“未来函数”或无中生有的虚假回测拼接。
              如果某只 ETF 上市仅 1~2 年（例如 2023 年新上市标的），其 5 年与 3 年历史数据在物理上真实缺失，系统坚决判定为“上市未满”并以横杠留空，鼠标悬停时会明确标注其历史交易日总数。
            </p>
          </div>

          {/* 底部按钮 */}
          <div className="flex justify-end pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-xs"
            >
              我知道了
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

MethodologyModal.propTypes = {
  isOpen: PropTypes.bool.isRequired,
  onClose: PropTypes.func.isRequired,
};
