export function loadingAnalysisCopy(days) {
  const count = Number(days);
  const span = Number.isFinite(count) && count > 0 ? `${count}天` : "本次请求的";
  return `系统正在基于${span}历史数据进行分析，通常需要10-30秒完成。分析结果仅供参考，不构成投资建议。`;
}
