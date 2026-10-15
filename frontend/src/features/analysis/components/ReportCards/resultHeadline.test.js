import assert from "node:assert/strict";
import test from "node:test";
import { cashYieldPct, formatSignedPercent, winRateDetail } from "./resultHeadline.js";

test("headline uses annualized grid cash yield and keeps win rate in the detail", () => {
  const summary = {
    cash_yield_pct: 8.9,
    max_drawdown: 18.2,
    win_rate: 100,
    closed_loop_count: 4,
  };
  assert.equal(formatSignedPercent(cashYieldPct(summary)), "+8.9%");
  assert.equal(formatSignedPercent(summary.max_drawdown), "+18.2%");
  const detail = winRateDetail(summary);
  assert.match(detail, /闭环胜率 100%（4 笔先买后卖）/);
  assert.match(detail, /底仓高抛不算/);
  assert.match(detail, /不代表这只 ETF 适合开网格/);
});

test("cash yield can be derived when an older summary has no stored percent", () => {
  const derived = cashYieldPct({
    grid_cash_profit: 3000,
    initial_capital: 30000,
    history_meta: { actual_calendar_days: 365 },
  });
  assert.equal(derived, 10);
});
