import assert from "node:assert/strict";
import test from "node:test";
import { ADVANCED_PANEL_LINK } from "./quickPanelCopy.js";

test("the cockpit link no longer calls the equal-size default a pyramid", () => {
  assert.equal(ADVANCED_PANEL_LINK, "三轨乘数 / 锚点");
  assert.equal(ADVANCED_PANEL_LINK.includes("倒金字塔"), false);
});
