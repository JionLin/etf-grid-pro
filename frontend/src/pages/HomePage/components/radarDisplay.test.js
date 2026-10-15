import assert from "node:assert/strict";
import test from "node:test";
import {
  CARD_RENDER_LIMIT,
  DEFAULT_COLLAPSE_LIMIT,
  PRIMARY_SECTORS,
  buildTruncationLabel,
  filterByStoredSubsector,
  subsectorsForSector,
  aggregateSectorCounts,
  maturityCounts,
  backfillHint,
  storageBadge,
  poolAtrParams,
  atrFloorLabel,
  rankBadge,
  rankPoolItems,
} from "./radarDisplay.js";

test("default collapse limit is 6 items", () => {
  assert.equal(DEFAULT_COLLAPSE_LIMIT, 6);
});

test("primary capsules do not include 其他主题", () => {
  assert.equal(PRIMARY_SECTORS.includes("其他主题"), false);
  assert.equal(PRIMARY_SECTORS.includes("未归类"), false);
  assert.equal(PRIMARY_SECTORS.filter((name) => name !== "全部").length, 11);
});

test("truncation label uses hit total instead of rendered count", () => {
  assert.equal(buildTruncationLabel(537, CARD_RENDER_LIMIT), "展示前 48 / 共 537");
  assert.equal(buildTruncationLabel(12, 12), "");
});

test("drill-down uses stored subsector and does not treat 科创50 as mega-cap", () => {
  const items = [
    { name: "科创50ETF华夏", subsector: "双创成长" },
    { name: "沪深300ETF", subsector: "超大盘(300/50)" },
  ];
  const growth = filterByStoredSubsector(items, "双创成长");
  const mega = filterByStoredSubsector(items, "超大盘(300/50)");
  assert.deepEqual(growth.map((item) => item.name), ["科创50ETF华夏"]);
  assert.deepEqual(mega.map((item) => item.name), ["沪深300ETF"]);
});

test("subsector counts come from the catalog, including zeros", () => {
  const summary = [
    { sector: "医药健康", name: "中药", count: 1 },
    { sector: "医药健康", name: "生物疫苗", count: 0 },
    { sector: "核心宽基", name: "双创成长", count: 4 },
  ];
  assert.deepEqual(
    subsectorsForSector(summary, "医药健康").map((item) => item.count),
    [1, 0]
  );
});

test("cash yield and spread stay on separate ranking scales", () => {
  const ordered = rankPoolItems([
    { etf_code: "588000", score: 42, score_kind: "spread" },
    { etf_code: "515220", score: 8.9, score_kind: "cash_yield" },
    { etf_code: "512400", score: 12.6, score_kind: "cash_yield" },
  ]);
  assert.deepEqual(ordered.map((item) => item.etf_code), ["512400", "515220", "588000"]);
});

test("rank badge uses cash yield and drawdown instead of a saturated score", () => {
  assert.equal(
    rankBadge({ score: 12.6, score_kind: "cash_yield", max_drawdown: 18.2 }),
    "年化做T 12.6% · 回撤 18.2%"
  );
  assert.equal(rankBadge({ score: 24.4, score_kind: "spread" }), "价差分 24.4");
});

test("atr floor can drop to 1.0 and labels the commodity exemption", () => {
  assert.deepEqual(poolAtrParams("1.5", false), { min_atr: "1.5", commodity_exempt: "0" });
  assert.deepEqual(poolAtrParams("1.0", true), { min_atr: "1.0", commodity_exempt: "1" });
  assert.equal(atrFloorLabel("1.0", true), "波幅门槛 1.0%，黄金/大宗商品按 1.0% 豁免");
});

test("storage badge follows the configured database", () => {
  assert.equal(storageBadge("本机 SQLite"), "本机 SQLite 直出");
  assert.equal(storageBadge("本机 MySQL"), "本机 MySQL 直出");
  assert.equal(storageBadge(undefined), "本地数据库直出");
});

test("maturity badges stay at zero while the pool is empty", () => {
  assert.deepEqual(maturityCounts([]), { y5: 0, y3: 0, all: 0 });
  assert.deepEqual(maturityCounts(undefined), { y5: 0, y3: 0, all: 0 });
  assert.equal(backfillHint(true, 0), "正在回补日K，完成后会自动出现标的");
  assert.equal(backfillHint(false, 0), "");
  assert.equal(backfillHint(true, 3), "");
});

test("maturity badges count the loaded rows", () => {
  const counts = maturityCounts([
    { is_valid_5y: true, is_valid_3y: true },
    { is_valid_5y: false, is_valid_3y: true },
    { is_valid_5y: false, is_valid_3y: false },
  ]);
  assert.deepEqual(counts, { y5: 1, y3: 2, all: 3 });
});

test("aggregateSectorCounts dynamically computes counts matching mature pool", () => {
  const items = [
    { name: "煤炭ETF", sector: "周期资源" },
    { name: "有色金属ETF", sector: "周期资源" },
    { name: "半导体ETF", sector: "科技芯片" },
  ];
  const map = aggregateSectorCounts(items);
  assert.equal(map["周期资源"], 2);
  assert.equal(map["科技芯片"], 1);
  assert.equal(map["医药健康"], undefined);
  assert.equal(Object.values(map).reduce((a, b) => a + b, 0), items.length);
});

test("drill-down other subsector matches null, undefined, empty, or explicit 其他", () => {
  const items = [
    { name: "建材ETF国泰", subsector: null },
    { name: "矿业ETF国泰", subsector: undefined },
    { name: "未命中小类ETF", subsector: "" },
    { name: "显式其他ETF", subsector: "其他" },
    { name: "有色金属ETF南方", subsector: "有色金属" },
  ];
  const otherItems = filterByStoredSubsector(items, "其他");
  assert.deepEqual(
    otherItems.map((item) => item.name),
    ["建材ETF国泰", "矿业ETF国泰", "未命中小类ETF", "显式其他ETF"]
  );
  const metalItems = filterByStoredSubsector(items, "有色金属");
  assert.deepEqual(
    metalItems.map((item) => item.name),
    ["有色金属ETF南方"]
  );
});


