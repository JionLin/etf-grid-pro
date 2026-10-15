function sideLabel(order) {
  return order?.action === "SELL" ? "卖出" : "买入";
}

function priceText(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "";
  return number.toFixed(3);
}

function railLabel(order) {
  return order?.tag || order?.rail_name || order?.rail || "网格";
}

export function buildBrokerOrderSheet({ code, orders, basePosition, anchorPrice } = {}) {
  const symbol = String(code || "").trim();
  const rows = [["代码", "方向", "触发价", "股数", "备注"]];

  const baseShares = Math.round(Number(basePosition?.shares) || 0);
  if (baseShares > 0) {
    rows.push([
      symbol,
      "买入",
      priceText(basePosition.current_price || basePosition.price || anchorPrice),
      String(baseShares),
      "底仓，单独下单，不是网格条件单",
    ]);
  }

  const groups = new Map();
  (orders || []).forEach((order) => {
    const key = `${sideLabel(order)}|${priceText(order.price)}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(order);
  });

  const seen = new Set();
  (orders || []).forEach((order) => {
    const key = `${sideLabel(order)}|${priceText(order.price)}`;
    if (seen.has(key)) return;
    seen.add(key);
    const group = groups.get(key);
    const shares = group.reduce((sum, item) => sum + Number(item.shares || 0), 0);
    const note = group.length > 1
      ? `同价${group.length}笔已合并（${group.map((item) => `${railLabel(item)}${item.shares}股`).join("，")}）`
      : railLabel(order);
    rows.push([symbol, sideLabel(order), priceText(order.price), String(shares), note]);
  });

  const table = rows.map((row) => row.join("\t")).join("\n");
  return `${table}\n说明\t留利润不会自动执行，卖出后的留股需要自行处理。`;
}
