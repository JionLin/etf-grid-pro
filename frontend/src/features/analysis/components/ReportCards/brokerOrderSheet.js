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

export function brokerOrderRecords({ orders, basePosition, anchorPrice } = {}) {
  const records = [];
  const baseShares = Math.round(Number(basePosition?.shares) || 0);
  if (baseShares > 0) {
    records.push({
      side: "买入",
      trigger_price: Number(priceText(basePosition.current_price || basePosition.price || anchorPrice)),
      shares: baseShares,
      note: "底仓，单独下单，不是网格条件单",
    });
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
    records.push({
      side: sideLabel(order),
      trigger_price: Number(priceText(order.price)),
      shares,
      note,
    });
  });
  return records;
}

export function ledgerOrderRecords({ orders, basePosition, anchorPrice } = {}) {
  const records = [];
  const baseShares = Math.round(Number(basePosition?.shares) || 0);
  if (baseShares > 0) {
    records.push({
      side: "买入",
      role: "base",
      rail: "底仓",
      trigger_price: Number(priceText(basePosition.current_price || basePosition.price || anchorPrice)),
      shares: baseShares,
      note: "底仓，单独下单，不是网格条件单",
    });
  }
  (orders || []).forEach((order) => {
    const shares = Math.round(Number(order.shares) || 0);
    const price = Number(priceText(order.price));
    if (shares <= 0 || !(price > 0)) return;
    const rail = railLabel(order);
    records.push({
      side: sideLabel(order),
      role: "grid",
      rail,
      trigger_price: price,
      shares,
      note: rail,
    });
  });
  return records;
}

export function buildBrokerOrderSheet({ code, orders, basePosition, anchorPrice } = {}) {
  const symbol = String(code || "").trim();
  const rows = [["代码", "方向", "触发价", "股数", "备注"]];
  brokerOrderRecords({ orders, basePosition, anchorPrice }).forEach((record) => {
    rows.push([
      symbol,
      record.side,
      Number(record.trigger_price).toFixed(3),
      String(record.shares),
      record.note,
    ]);
  });

  const table = rows.map((row) => row.join("\t")).join("\n");
  return `${table}\n说明\t留利润不会自动执行，卖出后的留股需要自行处理。`;
}

function csvCell(value) {
  const text = String(value ?? "");
  if (/[",\n\r]/.test(text)) return `"${text.replaceAll('"', '""')}"`;
  return text;
}

export function buildBrokerOrderCsv({ code, orders, basePosition, anchorPrice } = {}) {
  const symbol = String(code || "").trim();
  const rows = [["代码", "方向", "触发价", "股数", "备注"]];
  brokerOrderRecords({ orders, basePosition, anchorPrice }).forEach((record) => {
    rows.push([
      symbol,
      record.side,
      Number(record.trigger_price).toFixed(3),
      String(record.shares),
      record.note,
    ]);
  });
  rows.push(["说明", "留利润不会自动执行，卖出后的留股需要自行处理。", "", "", ""]);
  const body = rows.map((row) => row.map(csvCell).join(",")).join("\r\n");
  return `\uFEFF${body}`;
}

export function downloadBrokerOrderCsv(args) {
  const text = buildBrokerOrderCsv(args);
  if (typeof document === "undefined") return text;
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${String(args.code || "etf").trim() || "etf"}-条件单.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  return text;
}
