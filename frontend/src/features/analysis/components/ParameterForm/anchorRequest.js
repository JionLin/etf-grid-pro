export function anchorRequestFields({ mode, customPrice, percentile, dualMaPrice } = {}) {
  if (mode === "percentile") {
    return {
      anchorSource: "percentile",
      valuationPercentile: Number(percentile),
      benchmarkPrice: null,
      dualMaPrice: null,
    };
  }
  if (mode === "dual_ma") {
    const typed = dualMaPrice === "" || dualMaPrice === undefined || dualMaPrice === null
      ? null
      : Number(dualMaPrice);
    return {
      anchorSource: "dual_ma",
      dualMaPrice: Number.isFinite(typed) && typed > 0 ? typed : null,
      benchmarkPrice: null,
      valuationPercentile: null,
    };
  }
  if (mode === "custom") {
    return {
      anchorSource: "custom",
      benchmarkPrice: Number(customPrice),
      valuationPercentile: null,
      dualMaPrice: null,
    };
  }
  return {
    anchorSource: "market",
    benchmarkPrice: null,
    valuationPercentile: null,
    dualMaPrice: null,
  };
}

export function anchorModeLabel(mode) {
  if (mode === "custom") return "手填价格";
  if (mode === "percentile") return "收盘价分位";
  if (mode === "dual_ma") return "双均价格";
  return "盘中最新价";
}

export function anchorSourceCaption({
  anchorSource,
  anchorLabel,
  valuationPercentile,
  dualMaPrice,
} = {}) {
  const source = anchorSource || "market";
  const label = anchorLabel || anchorModeLabel(source);
  if (source === "percentile") {
    const pct = Number(valuationPercentile);
    if (Number.isFinite(pct)) return `${label} ${pct}%`;
  }
  if (source === "dual_ma" && dualMaPrice) {
    const price = Number(dualMaPrice);
    if (Number.isFinite(price) && price > 0) return `${label} ¥${price.toFixed(3)}`;
  }
  return label;
}
