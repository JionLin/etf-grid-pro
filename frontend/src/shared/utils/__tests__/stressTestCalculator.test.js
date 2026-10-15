import {
  calculateOrderCommission,
  calculateRallyScenario,
  calculateStressTestScenario,
  deepestGridDropLabel,
  defaultStressDrop,
} from "../stressTestCalculator.js";

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

const grid = {
  base_position: { shares: 200, actual_capital: 2000 },
  merged_ladder: [
    { action: "BUY", rail: "small", price: 9, shares: 100, amount: 900 },
    { action: "BUY", rail: "small", price: 8, shares: 100, amount: 800 },
    { action: "BUY", rail: "small", price: 7, shares: 100, amount: 700 },
    { action: "SELL", rail: "small", price: 11, shares: 100, amount: 1100, est_profit: 50 },
    { action: "SELL", rail: "small", price: 12, shares: 200, amount: 2400, est_profit: 80 },
  ],
};

const fee = calculateOrderCommission(100);
assert(fee === 0.2, `100 元成交佣金应为 0.2 元，实际 ${fee}`);

const drop = calculateStressTestScenario(grid, 3000, 10, 40);
assert(drop.triggeredOrdersCount === 1, `现金只够第一档，实际成交 ${drop.triggeredOrdersCount} 档`);
assert(drop.stoppedByCash === true, "现金不够时必须停");
assert(drop.consumedCash <= drop.liquidCapital + 0.01, "买入金额不能超过可用现金");
assert(drop.safetyLevel === "exhausted", "买不下下一档时应标记子弹耗尽");

const rally = calculateRallyScenario(grid, 3000, 10, 30);
assert(rally.triggeredSellShares === 100, `底仓只够卖 100 股，实际 ${rally.triggeredSellShares}`);
assert(rally.stoppedByShares === true, "底仓不够时必须停");
assert(rally.remainingShares === 100, "卖出后应留下不够下一档的底仓");
assert(rally.returnedCash === 1099.8, `回笼现金应扣除 0.2 元最低佣金，实际 ${rally.returnedCash}`);

assert(
  deepestGridDropLabel(10, grid.merged_ladder) === "当前最深网格 -30.0%",
  "最深买单应显示为相对现价的跌幅"
);
assert(deepestGridDropLabel(10, []) === "", "没有买单时不显示最深网格");
assert(defaultStressDrop(10, grid.merged_ladder) === 30, "默认跌幅应落到当前最深买单");
assert(defaultStressDrop(10, []) === 10, "没有买单时默认跌幅为 -10%");

console.log("stressTestCalculator 测试通过");
