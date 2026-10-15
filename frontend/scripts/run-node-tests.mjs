import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const nodeTests = [
  "src/pages/HomePage/components/radarDisplay.test.js",
  "src/shared/utils/format.test.js",
  "src/features/analysis/components/ReportCards/gridFitDisplay.test.js",
  "src/features/analysis/components/ReportCards/archiveFilters.test.js",
];

const scriptTests = [
  "src/shared/utils/__tests__/stressTestCalculator.test.js",
  "src/shared/utils/__tests__/strategyDraftStorage.test.js",
  "src/shared/utils/__tests__/searchHistoryStorage.test.js",
  "src/shared/utils/__tests__/urlDefaults.test.js",
];

function run(args) {
  const result = spawnSync(process.execPath, args, { cwd: root, stdio: "inherit" });
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(["--test", ...nodeTests]);
for (const file of scriptTests) {
  run([file]);
}
