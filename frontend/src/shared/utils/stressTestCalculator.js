/**
 * 极限行情压力测试沙盘纯函数计算模块
 * 贯彻 E大“压力测试最重要”哲学，毫秒级推演各跌幅情景下的资金消耗、持仓均价摊薄与绝地脱困反弹阈值
 */

/** 与回测引擎一致：万分之一，单笔最低 0.2 元。 */
export const STRESS_COMMISSION_RATE = 0.0001;
export const STRESS_MIN_COMMISSION = 0.2;

/**
 * 单笔佣金。费率按万分之一估算，再套上 0.2 元最低收费。
 *
 * @param {number} amount 成交金额
 * @param {number} commissionRate 佣金费率
 * @returns {number} 佣金
 */
export function calculateOrderCommission(amount, commissionRate = STRESS_COMMISSION_RATE) {
  const variableFee = Math.round(Number(amount) * commissionRate * 100) / 100;
  return Math.max(STRESS_MIN_COMMISSION, variableFee);
}

/**
 * 计算压力测试场景下的全套量化安全指标
 *
 * @param {Object} compositeGrid 复合网格数据 (包含 base_position, rails, merged_ladder)
 * @param {number} totalCapital 总资金 (如 100000)
 * @param {number} currentPrice 基准现价 (如 1.341)
 * @param {number} dropPct 模拟跌幅百分比 (如 10, 20, 35, 40, 50，代表下跌 10%、35% 等)
 * @param {number} commissionRate 佣金费率 (默认万分之一)
 * @returns {Object} 包含推演价、资金消耗、摊薄均价、脱困反弹、三轨水淹热力图等全量指标
 */
export function calculateStressTestScenario(
  compositeGrid,
  totalCapital = 100000,
  currentPrice = 1.0,
  dropPct = 20,
  commissionRate = STRESS_COMMISSION_RATE
) {
  if (!compositeGrid || !currentPrice) {
    return null;
  }

  const basePos = compositeGrid.base_position || {};
  const baseShares = basePos.shares || 0;
  const baseCost = basePos.actual_capital || baseShares * currentPrice;
  const liquidCapital = Math.max(0, totalCapital - baseCost);

  // 1. 模拟目标极端价格
  const safeDropPct = Math.max(0, Math.min(60, dropPct));
  const targetPrice = Math.max(0.001, Number((currentPrice * (1 - safeDropPct / 100)).toFixed(3)));

  // 2. 筛选并按价格从高到低排列所有买入档位
  const buyOrders = (compositeGrid.merged_ladder || [])
    .filter((item) => item.action === "BUY")
    .sort((a, b) => b.price - a.price);

  // 3. 统计已击穿档位、吸筹股数与资金消耗
  let triggeredBuyShares = 0;
  let triggeredBuyCost = 0;
  let triggeredBuyFee = 0;
  const triggeredOrders = [];

  // 各轨击穿情况统计
  const railStats = {
    small: { name: "小网 (高频做T)", tag: "小网", total: 0, triggered: 0, shares: 0, cost: 0, color: "emerald" },
    medium: { name: "中网 (波段巡航)", tag: "中网", total: 0, triggered: 0, shares: 0, cost: 0, color: "blue" },
    large: { name: "大网 (深档防守)", tag: "大网", total: 0, triggered: 0, shares: 0, cost: 0, color: "purple" },
  };

  let cashLeft = liquidCapital;
  let stoppedByCash = false;
  buyOrders.forEach((order) => {
    const railKey = order.rail || "small";
    if (railStats[railKey]) {
      railStats[railKey].total += 1;
    }
    if (stoppedByCash || targetPrice > order.price) {
      return;
    }

    const fee = calculateOrderCommission(order.amount, commissionRate);
    const needed = order.amount + fee;
    if (cashLeft + 1e-9 < needed) {
      stoppedByCash = true;
      return;
    }
    cashLeft -= needed;
    triggeredBuyShares += order.shares;
    triggeredBuyCost += order.amount;
    triggeredBuyFee += fee;
    triggeredOrders.push(order);

    if (railStats[railKey]) {
      railStats[railKey].triggered += 1;
      railStats[railKey].shares += order.shares;
      railStats[railKey].cost += order.amount;
    }
  });

  // 计算各轨击穿百分比
  Object.keys(railStats).forEach((k) => {
    const r = railStats[k];
    r.cost = Number(r.cost.toFixed(2));
    r.pct = r.total > 0 ? Number(((r.triggered / r.total) * 100).toFixed(1)) : 0;
  });

  // 4. 现金消耗与子弹剩余测算
  const consumedCash = Number((triggeredBuyCost + triggeredBuyFee).toFixed(2));
  const remainingCash = Number(Math.max(0, liquidCapital - consumedCash).toFixed(2));
  const cashDrainRatio = liquidCapital > 0 ? Number(Math.min(100, (consumedCash / liquidCapital) * 100).toFixed(1)) : 0;
  const cashBufferRatio = Number((100 - cashDrainRatio).toFixed(1));

  // 5. 测算资金耗尽临界跌幅点 (Exhaustion Drop Point)
  let cumulativeCost = 0;
  let exhaustionDropPct = null;
  let exhaustionPrice = null;

  for (const order of buyOrders) {
    cumulativeCost += order.amount + calculateOrderCommission(order.amount, commissionRate);
    if (cumulativeCost >= liquidCapital && exhaustionDropPct === null) {
      exhaustionPrice = order.price;
      exhaustionDropPct = Number((((currentPrice - order.price) / currentPrice) * 100).toFixed(1));
      break;
    }
  }

  // 6. 安全风控等级判定
  let safetyLevel = "safe";
  let safetyLabel = "资金安全 · 储备充裕";
  let safetyBadgeColor = "emerald";

  if (stoppedByCash || consumedCash >= liquidCapital) {
    safetyLevel = "exhausted";
    safetyLabel = "子弹耗尽 · 底仓锁仓";
    safetyBadgeColor = "red";
  } else if (cashDrainRatio >= 80) {
    safetyLevel = "danger";
    safetyLabel = "重度击穿 · 临界警戒";
    safetyBadgeColor = "orange";
  } else if (cashDrainRatio >= 50) {
    safetyLevel = "warning";
    safetyLabel = "中度消耗 · 子弹待命";
    safetyBadgeColor = "amber";
  }

  // 7. 综合持仓成本加权摊薄 (Breakeven Average Price)
  const totalHoldingShares = baseShares + triggeredBuyShares;
  const totalHoldingCost = baseCost + triggeredBuyCost;
  const avgCostPrice = totalHoldingShares > 0 ? Number((totalHoldingCost / totalHoldingShares).toFixed(3)) : currentPrice;
  const costReductionPct = Number((((currentPrice - avgCostPrice) / currentPrice) * 100).toFixed(2));

  // 8. 绝地脱困反弹阈值 (Breakeven Rebound Gap)
  // 普通死拿标的回本所需涨幅: (P0 - Target) / Target
  const normalReboundNeeded = targetPrice > 0 ? Number((((currentPrice - targetPrice) / targetPrice) * 100).toFixed(1)) : 0;

  // 网格摊薄后回本脱困所需反弹涨幅: (AvgPrice - Target) / Target
  const gridReboundNeeded = targetPrice > 0 ? Number((((avgCostPrice - targetPrice) / targetPrice) * 100).toFixed(1)) : 0;

  // 脱困超额优势 (少涨了多少百分比即可回本)
  const reboundAdvantage = Number(Math.max(0, normalReboundNeeded - gridReboundNeeded).toFixed(1));

  return {
    currentPrice,
    dropPct: safeDropPct,
    targetPrice,
    basePosition: {
      shares: baseShares,
      cost: Number(baseCost.toFixed(2)),
    },
    liquidCapital: Number(liquidCapital.toFixed(2)),
    consumedCash,
    remainingCash,
    cashDrainRatio,
    cashBufferRatio,
    exhaustionDropPct,
    exhaustionPrice,
    safetyLevel,
    safetyLabel,
    safetyBadgeColor,
    totalHoldingShares,
    totalHoldingCost: Number(totalHoldingCost.toFixed(2)),
    avgCostPrice,
    costReductionPct,
    normalReboundNeeded,
    gridReboundNeeded,
    reboundAdvantage,
    railStats,
    triggeredOrdersCount: triggeredOrders.length,
    totalBuyOrdersCount: buyOrders.length,
    stoppedByCash,
  };
}

/**
 * 5 大经典历史暴跌情景预设配置
 */
/**
 * 上涨方向压力测试推演 —— 量化上涨场景下的筹码流失、做 T 利润与踏空风险
 *
 * @param {Object} compositeGrid 复合网格数据 (包含 base_position, rails, merged_ladder)
 * @param {number} totalCapital 总资金
 * @param {number} currentPrice 基准现价
 * @param {number} rallyPct 模拟涨幅百分比 (如 10, 20, 50，代表上涨 10%、50% 等)
 * @param {number} commissionRate 佣金费率 (默认万分之一)
 * @returns {Object} 包含推演价、筹码流失率、回笼现金、做 T 利润、三轨卖出热力图等全量指标
 */
export function calculateRallyScenario(
  compositeGrid,
  totalCapital = 100000,
  currentPrice = 1.0,
  rallyPct = 20,
  commissionRate = STRESS_COMMISSION_RATE
) {
  if (!compositeGrid || !currentPrice) {
    return null;
  }

  const basePos = compositeGrid.base_position || {};
  const baseShares = basePos.shares || 0;

  // 1. 模拟目标上涨价格
  const safeRallyPct = Math.max(0, Math.min(80, rallyPct));
  const targetPrice = Number((currentPrice * (1 + safeRallyPct / 100)).toFixed(3));

  // 2. 筛选并按价格从低到高排列所有卖出档位
  const sellOrders = (compositeGrid.merged_ladder || [])
    .filter((item) => item.action === "SELL")
    .sort((a, b) => a.price - b.price);

  // 3. 统计已触发卖出档位、卖出份额与回笼现金
  let triggeredSellShares = 0;
  let triggeredSellAmount = 0;
  let triggeredSellFee = 0;
  let triggeredSellProfit = 0;
  const triggeredOrders = [];

  // 各轨卖出触发情况统计
  const railStats = {
    small: { name: "小网 (高频止盈)", tag: "小网", total: 0, triggered: 0, shares: 0, amount: 0, profit: 0, color: "emerald" },
    medium: { name: "中网 (波段止盈)", tag: "中网", total: 0, triggered: 0, shares: 0, amount: 0, profit: 0, color: "blue" },
    large: { name: "大网 (趋势止盈)", tag: "大网", total: 0, triggered: 0, shares: 0, amount: 0, profit: 0, color: "purple" },
  };

  let sharesLeft = baseShares;
  let stoppedByShares = false;
  sellOrders.forEach((order) => {
    const railKey = order.rail || "small";
    if (railStats[railKey]) {
      railStats[railKey].total += 1;
    }
    if (stoppedByShares || targetPrice < order.price) {
      return;
    }

    if (sharesLeft < order.shares) {
      stoppedByShares = true;
      return;
    }
    sharesLeft -= order.shares;
    const fee = calculateOrderCommission(order.amount, commissionRate);
    triggeredSellShares += order.shares;
    triggeredSellAmount += order.amount;
    triggeredSellFee += fee;
    triggeredSellProfit += (order.est_profit || 0);
    triggeredOrders.push(order);

    if (railStats[railKey]) {
      railStats[railKey].triggered += 1;
      railStats[railKey].shares += order.shares;
      railStats[railKey].amount += order.amount;
      railStats[railKey].profit += (order.est_profit || 0);
    }
  });

  // 计算各轨卖出百分比
  Object.keys(railStats).forEach((k) => {
    const r = railStats[k];
    r.amount = Number(r.amount.toFixed(2));
    r.profit = Number(r.profit.toFixed(2));
    r.pct = r.total > 0 ? Number(((r.triggered / r.total) * 100).toFixed(1)) : 0;
  });

  // 4. 筹码流失率与剩余持仓
  const chipLossRatio = baseShares > 0 ? Number(Math.min(100, (triggeredSellShares / baseShares) * 100).toFixed(1)) : 0;
  const remainingShares = Math.max(0, baseShares - triggeredSellShares);

  // 5. 回笼现金
  const returnedCash = Number((triggeredSellAmount - triggeredSellFee).toFixed(2));

  // 6. 累计做 T 利润
  const totalProfit = Number(triggeredSellProfit.toFixed(2));

  // 7. 利润池模式 B 联动：计算可兑换免费份额数
  const freeSharesFromProfit = targetPrice > 0
    ? Math.floor(totalProfit / targetPrice / 100) * 100
    : 0;

  // 8. 卖飞临界涨幅 (最高卖出档位对应的涨幅)
  const highestSellOrder = sellOrders.length > 0 ? sellOrders[sellOrders.length - 1] : null;
  const soldOutRallyPct = (highestSellOrder && currentPrice > 0)
    ? Number((((highestSellOrder.price - currentPrice) / currentPrice) * 100).toFixed(1))
    : null;
  const isBeyondGrid = Boolean(soldOutRallyPct && safeRallyPct > soldOutRallyPct);

  // 9. 安全状态分级判定 (基于筹码流失率)
  let safetyLevel = "safe";
  let safetyLabel = "持仓充裕";
  let safetyBadgeColor = "emerald";

  if (chipLossRatio > 90) {
    safetyLevel = "critical";
    safetyLabel = "近乎空仓 · 踏空风险";
    safetyBadgeColor = "red";
  } else if (chipLossRatio > 60) {
    safetyLevel = "warning";
    safetyLabel = "筹码稀薄";
    safetyBadgeColor = "amber";
  } else if (chipLossRatio > 30) {
    safetyLevel = "moderate";
    safetyLabel = "稳步止盈";
    safetyBadgeColor = "sky";
  }

  return {
    currentPrice,
    rallyPct: safeRallyPct,
    targetPrice,
    basePosition: {
      shares: baseShares,
    },
    triggeredSellShares,
    triggeredSellAmount: Number(triggeredSellAmount.toFixed(2)),
    chipLossRatio,
    remainingShares,
    returnedCash,
    totalProfit,
    freeSharesFromProfit,
    soldOutRallyPct,
    isBeyondGrid,
    safetyLevel,
    safetyLabel,
    safetyBadgeColor,
    railStats,
    triggeredOrdersCount: triggeredOrders.length,
    totalSellOrdersCount: sellOrders.length,
    stoppedByShares,
  };
}

export const STRESS_TEST_PRESETS = [
  { drop: 10, label: "-10% 日常回调", desc: "日常正常波段下挫，小网逐步吸收筹码" },
  { drop: 20, label: "-20% 技术熊市", desc: "技术性熊市分水岭，小网吃满，中网启动" },
  { drop: 30, label: "-30% 深度黄金坑", desc: "行业中级深度调整，中网大部分被击穿" },
  { drop: 40, label: "★ -40% 极值回撤", desc: "E大经典极值铁底，大网大口吞进巨鲸筹码" },
  { drop: 50, label: "-50% 世纪极值", desc: "罕见历史极端测试，检验最后底线安全垫" },
];

/**
 * 5 大经典上涨情景预设配置
 */
function roundedDrop(currentPrice, orderPrice) {
  const price = Number(currentPrice);
  const level = Number(orderPrice);
  if (!price || !(level > 0) || !(price > level)) return null;
  const drop = ((price - level) / price) * 100;
  if (!(drop > 0)) return null;
  return Math.max(1, Math.min(60, Math.round(drop)));
}

export function deepestStressDrop(currentPrice, ladder) {
  const price = Number(currentPrice);
  const buys = (ladder || []).filter((item) => item.action === "BUY" && Number(item.price) > 0);
  if (!price || buys.length === 0) return null;
  const deepest = buys.reduce((min, item) => (Number(item.price) < Number(min.price) ? item : min));
  return roundedDrop(price, deepest.price);
}

export function defaultStressDrop(currentPrice, ladder) {
  const price = Number(currentPrice);
  const buys = (ladder || []).filter((item) => item.action === "BUY" && Number(item.price) > 0 && Number(item.price) < price);
  if (!price || buys.length === 0) return 10;
  const nearest = buys.reduce((max, item) => (Number(item.price) > Number(max.price) ? item : max));
  return roundedDrop(price, nearest.price) ?? 10;
}

export function stressCashNote(result) {
  if (!result) return "";
  const drained = result.safetyLevel === "exhausted" || result.stoppedByCash;
  if (drained && result.exhaustionDropPct != null) {
    return `子弹耗尽临界: -${result.exhaustionDropPct}%`;
  }
  if (result.safetyLevel === "danger" || result.safetyLevel === "warning" || result.safetyLevel === "exhausted") {
    return `现金尚未耗尽，已消耗 ${result.cashDrainRatio}%`;
  }
  if (result.exhaustionDropPct != null) {
    return `子弹耗尽临界: -${result.exhaustionDropPct}%`;
  }
  return "按当前网格买完，现金仍有余";
}

export function deepestGridDropLabel(currentPrice, ladder) {
  const price = Number(currentPrice);
  const buys = (ladder || []).filter((item) => item.action === "BUY" && Number(item.price) > 0);
  if (!price || buys.length === 0) {
    return "";
  }
  const deepest = buys.reduce((min, item) => (Number(item.price) < Number(min.price) ? item : min));
  const drop = ((price - Number(deepest.price)) / price) * 100;
  if (drop <= 0) {
    return "";
  }
  return `当前最深网格 -${drop.toFixed(1)}%`;
}

export const RALLY_TEST_PRESETS = [
  { rally: 10, label: "+10% 日常反弹", desc: "日常正常波段反弹，小网逐步卖出止盈" },
  { rally: 20, label: "+20% 波段牛市", desc: "波段牛市区间，小网全部出清，中网开始止盈" },
  { rally: 30, label: "+30% 行业景气", desc: "行业中级上涨，中网大部分止盈" },
  { rally: 50, label: "★ +50% 牛市主升浪", desc: "E大经典牛市场景，检验留利润能力" },
  { rally: 80, label: "+80% 历史级牛市", desc: "极端上涨测试，底仓几乎全部卖出" },
];
