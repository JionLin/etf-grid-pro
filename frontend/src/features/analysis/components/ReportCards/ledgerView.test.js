import assert from "node:assert/strict";
import test from "node:test";
import { visibleLedgerOrders, voidedLedgerCount } from "./ledgerView.js";

test("voided ledger rows stay behind the history toggle", () => {
  const orders = [
    { id: 1, status: "未挂" },
    { id: 2, status: "已挂" },
    { id: 3, status: "已成" },
    { id: 4, status: "作废" },
    { id: 5, status: "待买入" },
  ];
  assert.deepEqual(visibleLedgerOrders(orders, false).map((row) => row.id), [1, 2, 3, 5]);
  assert.equal(visibleLedgerOrders(orders, true).length, 5);
  assert.equal(voidedLedgerCount(orders), 1);
});
