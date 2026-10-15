import assert from "node:assert/strict";
import test from "node:test";
import { anchorModeLabel, anchorRequestFields, anchorSourceCaption } from "./anchorRequest.js";

test("percentile and dual moving average are separate anchor sources", () => {
  assert.deepEqual(anchorRequestFields({ mode: "percentile", percentile: 20 }), {
    anchorSource: "percentile",
    valuationPercentile: 20,
    benchmarkPrice: null,
    dualMaPrice: null,
  });
  assert.deepEqual(anchorRequestFields({ mode: "dual_ma", dualMaPrice: "1.318" }), {
    anchorSource: "dual_ma",
    dualMaPrice: 1.318,
    benchmarkPrice: null,
    valuationPercentile: null,
  });
  assert.equal(anchorRequestFields({ mode: "dual_ma", dualMaPrice: "" }).dualMaPrice, null);
  assert.equal(anchorModeLabel("market"), "盘中最新价");
  assert.equal(anchorModeLabel("percentile"), "收盘价分位");
});

test("result caption names the anchor source that was requested", () => {
  assert.equal(
    anchorSourceCaption({ anchorSource: "percentile", anchorLabel: "收盘价分位", valuationPercentile: 20 }),
    "收盘价分位 20%",
  );
  assert.equal(anchorSourceCaption({ anchorSource: "dual_ma", anchorLabel: "双均价" }), "双均价");
  assert.equal(anchorSourceCaption({ anchorSource: "market" }), "盘中最新价");
});
