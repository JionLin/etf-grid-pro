import assert from "node:assert/strict";
import test from "node:test";
import { ATR_STEP_BUTTON_LABEL, EDA_STEP_BUTTON_LABEL } from "./stepModeLabels.js";

test("the factory default mark sits on the E-da button", () => {
  assert.equal(EDA_STEP_BUTTON_LABEL.includes("(默认)"), true);
  assert.equal(ATR_STEP_BUTTON_LABEL.includes("(默认)"), false);
});
