import assert from "node:assert/strict";
import test from "node:test";
import { brokerOrderRecords, buildBrokerOrderCsv, buildBrokerOrderSheet, ledgerOrderRecords } from "./brokerOrderSheet.js";

test("broker sheet keeps the base position on its own row and merges same-price orders", () => {
  const sheet = buildBrokerOrderSheet({
    code: "515220",
    anchorPrice: 1.25,
    basePosition: { shares: 12000, current_price: 1.25 },
    orders: [
      { action: "SELL", price: 1.317, shares: 400, tag: "小网" },
      { action: "SELL", price: 1.317, shares: 300, tag: "中网" },
      { action: "BUY", price: 1.28, shares: 500, tag: "小网" },
      { action: "BUY", price: 1.28, shares: 500, tag: "大网" },
      { action: "BUY", price: 1.1, shares: 800, tag: "大网" },
    ],
  });
  const lines = sheet.split("\n");
  assert.equal(lines[0], "代码\t方向\t触发价\t股数\t备注");
  assert.equal(lines[1], "515220\t买入\t1.250\t12000\t底仓，单独下单，不是网格条件单");
  assert.equal(lines[2], "515220\t卖出\t1.317\t700\t同价2笔已合并（小网400股，中网300股）");
  assert.equal(lines[3], "515220\t买入\t1.280\t1000\t同价2笔已合并（小网500股，大网500股）");
  assert.equal(lines[4], "515220\t买入\t1.100\t800\t大网");
  assert.match(lines[5], /留利润不会自动执行/);
  const records = brokerOrderRecords({
    anchorPrice: 1.25,
    basePosition: { shares: 12000, current_price: 1.25 },
    orders: [
      { action: "SELL", price: 1.317, shares: 400, tag: "小网" },
      { action: "SELL", price: 1.317, shares: 300, tag: "中网" },
    ],
  });
  assert.equal(records[0].note.includes("底仓"), true);
  assert.equal(records[1].shares, 700);
});

test("ledger keeps one row per track while the broker sheet still merges", () => {
  const orders = [
    { action: "BUY", price: 1.28, shares: 500, tag: "中网" },
    { action: "BUY", price: 1.28, shares: 500, tag: "大网" },
  ];
  const broker = brokerOrderRecords({ orders });
  assert.equal(broker.length, 1);
  assert.equal(broker[0].shares, 1000);
  const ledger = ledgerOrderRecords({
    orders,
    basePosition: { shares: 12000, current_price: 1.25 },
  });
  assert.equal(ledger.length, 3);
  assert.equal(ledger[0].rail, "底仓");
  assert.equal(ledger[0].role, "base");
  assert.deepEqual(ledger.slice(1).map((row) => row.rail), ["中网", "大网"]);
  assert.equal(ledger[1].shares, 500);
  assert.equal(ledger[2].shares, 500);
});
