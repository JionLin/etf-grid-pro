import assert from "node:assert/strict";
import test from "node:test";
import { formatPriceDate } from "./format.js";

test("shanghai timestamp string is the anchor date", () => {
  assert.equal(formatPriceDate("2026-10-15 11:20:00"), "2026-10-15 11:20:00");
  assert.equal(formatPriceDate(""), "");
  assert.equal(formatPriceDate(null), "");
});

test("numeric timestamps still format", () => {
  const formatted = formatPriceDate(1_760_500_800_000);
  assert.match(formatted, /^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$/);
});
