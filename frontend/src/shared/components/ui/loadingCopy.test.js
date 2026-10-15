import assert from "node:assert/strict";
import test from "node:test";
import { loadingAnalysisCopy } from "./loadingCopy.js";

test("loading copy uses the requested day count", () => {
  assert.match(loadingAnalysisCopy(1825), /基于1825天历史数据/);
  assert.match(loadingAnalysisCopy(90), /基于90天历史数据/);
  assert.equal(loadingAnalysisCopy(1825).includes("1年"), false);
  assert.match(loadingAnalysisCopy(undefined), /基于本次请求的历史数据/);
});
