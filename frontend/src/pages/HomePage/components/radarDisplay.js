export const CARD_RENDER_LIMIT = 48;
export const DEFAULT_COLLAPSE_LIMIT = 6;

export const PRIMARY_SECTORS = [
  "全部",
  "科技芯片",
  "新能源制造",
  "医药健康",
  "大金融",
  "大消费",
  "周期资源",
  "公用红利",
  "国防军工",
  "跨境全球",
  "大宗商品",
  "核心宽基",
];

export function filterByStoredSubsector(items, subsectorName) {
  if (!subsectorName || subsectorName === "全部") {
    return items;
  }
  return items.filter((item) => (item.subsector || "其他") === subsectorName);
}

export function subsectorsForSector(summary, sector) {
  return (summary || []).filter((row) => row.sector === sector);
}

export function buildTruncationLabel(hitCount, renderedCount) {
  if (!hitCount || hitCount <= renderedCount) {
    return "";
  }
  return `展示前 ${renderedCount} / 共 ${hitCount}`;
}

export function aggregateSectorCounts(items) {
  const map = {};
  (items || []).forEach((item) => {
    const sec = item.sector || "未归类";
    map[sec] = (map[sec] || 0) + 1;
  });
  return map;
}

export function maturityCounts(items) {
  const list = items || [];
  return {
    y5: list.filter((item) => item.is_valid_5y).length,
    y3: list.filter((item) => item.is_valid_3y).length,
    all: list.length,
  };
}

export function rankBadge(item) {
  if (!item || item.score === undefined || item.score === null || item.score === "") {
    return "";
  }
  const drawdown = item.max_drawdown === undefined || item.max_drawdown === null
    ? ""
    : ` · 回撤 ${item.max_drawdown}%`;
  if (item.score_kind === "cash_yield") {
    return `年化做T ${item.score}%${drawdown}`;
  }
  return `价差分 ${item.score}${drawdown}`;
}

export function poolAtrParams(minAtr, commodityExempt) {
  const floor = String(minAtr) === "1.0" ? "1.0" : "1.5";
  return {
    min_atr: floor,
    commodity_exempt: commodityExempt ? "1" : "0",
  };
}

export function atrFloorLabel(minAtr, commodityExempt) {
  const floor = String(minAtr) === "1.0" ? "1.0%" : "1.5%";
  return commodityExempt ? `波幅门槛 ${floor}，黄金/大宗商品按 1.0% 豁免` : `波幅门槛 ${floor}`;
}

export function storageBadge(label) {
  if (label === "本机 SQLite" || label === "本机 MySQL") {
    return `${label} 直出`;
  }
  return "本地数据库直出";
}

export function backfillHint(backfilling, count) {
  if (backfilling && !count) {
    return "正在回补日K，完成后会自动出现标的";
  }
  return "";
}

