export const CLOSED_LOOP_WIN_RATE_DEFINITION =
  "闭环胜率只统计先买后卖、扣完双边费用后仍盈利的笔数，底仓高抛不算。它不代表这只 ETF 适合开网格。";

export function cashYieldPct(summary) {
  if (!summary) return null;
  if (summary.cash_yield_pct !== undefined && summary.cash_yield_pct !== null && summary.cash_yield_pct !== "") {
    return Number(summary.cash_yield_pct);
  }
  const profit = Number(summary.grid_cash_profit);
  const capital = Number(summary.initial_capital);
  const days = Number(summary.history_meta?.actual_calendar_days);
  if (!Number.isFinite(profit) || !capital || !days) return null;
  return Number(((profit / capital) * 365 / days * 100).toFixed(2));
}

export function formatSignedPercent(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) return "—";
  const number = Number(value);
  return `${number >= 0 ? "+" : ""}${number}%`;
}

export function winRateDetail(summary) {
  if (!summary || summary.win_rate === undefined || summary.win_rate === null) {
    return `闭环胜率 —。${CLOSED_LOOP_WIN_RATE_DEFINITION}`;
  }
  const count = Number(summary.closed_loop_count);
  const countText = count > 0 ? `（${count} 笔先买后卖）` : "";
  return `闭环胜率 ${summary.win_rate}%${countText}。${CLOSED_LOOP_WIN_RATE_DEFINITION}`;
}
