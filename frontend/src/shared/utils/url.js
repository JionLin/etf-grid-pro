/**
 * URL参数管理工具
 * 处理分析页面的URL参数编码、解码和验证
 */
import { validateETFCode } from "./validation.js";

// 参数映射表 - 中文到英文的映射
export const PARAM_MAPPINGS = {
  gridType: {
    等比: "geometric",
    等差: "arithmetic",
  },
  riskPreference: {
    低频: "conservative",
    均衡: "balanced",
    高频: "aggressive",
  },
};

// 反向映射表 - 英文到中文的映射
export const REVERSE_PARAM_MAPPINGS = {
  gridType: {
    geometric: "等比",
    arithmetic: "等差",
  },
  riskPreference: {
    conservative: "低频",
    balanced: "均衡",
    aggressive: "高频",
  },
};

// 默认参数值
export const DEFAULT_PARAMS = {
  capital: "30000",
  grid: "geometric", // 对应"等比"
  risk: "balanced", // 对应"均衡"
  adjustment: "1.0", // 调节系数默认值
  stepMode: "fixed_eda", // 出厂默认：E大守株 5/15/30
  days: "1825", // 历史分析周期：出厂 5 年
  scaling: "0", // 出厂等额，加码比例由面板传入
  reinvest: "pool_shares", // 做T收益留存模式：'pool_shares' | 'cash'
  edaSteps: "5,15,30", // E大原版自定义各轨步长比例：默认 5,15,30
  atrMultipliers: "0.6,1.2,2.5", // ATR自适应自定义各轨乘数：默认 0.6,1.2,2.5
};

/**
 * 将分析参数编码为URL查询参数
 * @param {Object} params - 分析参数对象
 * @returns {URLSearchParams} URL查询参数对象
 */
export const encodeAnalysisParams = (params) => {
  const searchParams = new URLSearchParams();

  // 资金参数
  if (params.totalCapital !== undefined && params.totalCapital !== null) {
    searchParams.set("capital", params.totalCapital.toString());
  }

  // 网格类型参数
  if (params.gridType) {
    const encodedGrid =
      PARAM_MAPPINGS.gridType[params.gridType] || params.gridType;
    searchParams.set("grid", encodedGrid);
  }

  // 频率偏好参数
  if (params.riskPreference) {
    const encodedRisk =
      PARAM_MAPPINGS.riskPreference[params.riskPreference] ||
      params.riskPreference;
    searchParams.set("risk", encodedRisk);
  }

  // 调节系数参数
  if (params.adjustmentCoefficient !== undefined && params.adjustmentCoefficient !== null) {
    searchParams.set("adjustment", params.adjustmentCoefficient.toString());
  }

  // 步长生成模式 (ATR动态自适应 vs E大原版5%/15%/30%)
  if (params.stepMode) {
    searchParams.set("stepMode", params.stepMode);
  }

  // E大原版自定义各轨步长比例 (仅当为 fixed_eda 且非默认 5,15,30 时记录)
  if (params.stepMode === "fixed_eda" && params.edaSteps) {
    const s = params.edaSteps.small;
    const m = params.edaSteps.medium;
    const l = params.edaSteps.large;
    if (s !== undefined && m !== undefined && l !== undefined) {
      if (!(Number(s) === 5 && Number(m) === 15 && Number(l) === 30)) {
        searchParams.set("eda_steps", `${s},${m},${l}`);
      }
    }
  }

  // ATR模式自定义各轨乘数 (仅当为 atr 且非默认 0.6,1.2,2.5 时记录)
  if (params.stepMode !== "fixed_eda" && params.atrMultipliers) {
    const s = params.atrMultipliers.small;
    const m = params.atrMultipliers.medium;
    const l = params.atrMultipliers.large;
    if (s !== undefined && m !== undefined && l !== undefined) {
      if (!(Number(s) === 0.6 && Number(m) === 1.2 && Number(l) === 2.5)) {
        searchParams.set("atr_mults", `${s},${m},${l}`);
      }
    }
  }

  // 历史分析周期
  if (params.analysisDays !== undefined && params.analysisDays !== null) {
    searchParams.set("days", params.analysisDays.toString());
  }

  // 逐格加码比例
  if (params.scalingRatio !== undefined && params.scalingRatio !== null) {
    searchParams.set("scaling", params.scalingRatio.toString());
  }

  // 做T收益留存机制
  if (params.reinvestMode) {
    searchParams.set("reinvest", params.reinvestMode);
  }

  // 自定义基准价格参数
  if (params.benchmarkPrice !== undefined && params.benchmarkPrice !== null && params.benchmarkPrice !== "") {
    const p = parseFloat(params.benchmarkPrice);
    if (!isNaN(p) && p > 0) {
      searchParams.set("price", p.toString());
    }
  }

  return searchParams;
};

/**
 * 从URL查询参数解码分析参数
 * @param {URLSearchParams} searchParams - URL查询参数对象
 * @returns {Object} 解码后的分析参数对象
 */
export const decodeAnalysisParams = (searchParams) => {
  const params = {};

  // 解析资金参数
  const capital = searchParams.get("capital");
  if (capital) {
    const capitalNum = parseFloat(capital);
    if (!isNaN(capitalNum) && capitalNum >= 10000 && capitalNum <= 1000000) {
      params.totalCapital = capitalNum;
    }
  }

  // 解析网格类型参数
  const grid = searchParams.get("grid");
  if (grid) {
    params.gridType = REVERSE_PARAM_MAPPINGS.gridType[grid] || grid;
  }

  // 解析频率偏好参数
  const risk = searchParams.get("risk");
  if (risk) {
    params.riskPreference = REVERSE_PARAM_MAPPINGS.riskPreference[risk] || risk;
  }

  // 解析调节系数参数
  const adjustment = searchParams.get("adjustment");
  if (adjustment !== null) {
    const adjustmentNum = parseFloat(adjustment);
    if (!isNaN(adjustmentNum) && adjustmentNum >= 0.0 && adjustmentNum <= 2.0) {
      params.adjustmentCoefficient = adjustmentNum;
    }
  }

  // 解析步长生成模式
  const stepMode = searchParams.get("stepMode") || searchParams.get("step_mode");
  if (stepMode && ["atr", "fixed_eda"].includes(stepMode)) {
    params.stepMode = stepMode;
  }

  // 解析 E大原版自定义各轨步长比例
  const edaStepsRaw = searchParams.get("eda_steps") || searchParams.get("edaSteps");
  if (edaStepsRaw) {
    const parts = edaStepsRaw.split(",").map((p) => parseInt(p.trim(), 10));
    if (parts.length === 3 && parts.every((n) => !isNaN(n))) {
      const [s, m, l] = parts;
      if (s >= 1 && s < m && m < l && l <= 50) {
        params.edaSteps = { small: s, medium: m, large: l };
      }
    }
  }

  // 解析 ATR模式自定义各轨乘数
  const atrMultsRaw = searchParams.get("atr_mults") || searchParams.get("atrMultipliers");
  if (atrMultsRaw) {
    const parts = atrMultsRaw.split(",").map((p) => parseFloat(p.trim()));
    if (parts.length === 3 && parts.every((n) => !isNaN(n))) {
      const [s, m, l] = parts;
      if (s >= 0.1 && s < m && m < l && l <= 10.0) {
        params.atrMultipliers = { small: s, medium: m, large: l };
      }
    }
  }

  // 解析历史分析周期
  const days = searchParams.get("days") || searchParams.get("analysisDays");
  if (days) {
    const daysNum = parseInt(days, 10);
    if (!isNaN(daysNum) && daysNum > 0) {
      params.analysisDays = daysNum;
    }
  }

  // 解析逐格加码比例
  const scaling = searchParams.get("scaling") || searchParams.get("scalingRatio");
  if (scaling !== null && scaling !== undefined) {
    const scalingNum = parseFloat(scaling);
    if (!isNaN(scalingNum) && scalingNum >= 0.0 && scalingNum <= 0.5) {
      params.scalingRatio = scalingNum;
    }
  }

  // 解析做T收益留存模式
  const reinvest = searchParams.get("reinvest") || searchParams.get("reinvestMode");
  if (reinvest && ["pool_shares", "cash"].includes(reinvest)) {
    params.reinvestMode = reinvest;
  }

  // 解析自定义基准价格参数
  const price = searchParams.get("price") || searchParams.get("benchmarkPrice");
  if (price !== null && price !== undefined && price !== "") {
    const priceNum = parseFloat(price);
    if (!isNaN(priceNum) && priceNum > 0) {
      params.benchmarkPrice = priceNum;
    }
  }

  return params;
};

/**
 * 验证分析参数完整性
 * @param {Object} params - 分析参数对象
 * @returns {Object} 验证结果和补全后的参数
 */
export const validateAndCompleteParams = (params) => {
  const result = {
    isValid: true,
    errors: [],
    params: { ...params },
  };

  // 验证并补全资金参数
  if (params.totalCapital === undefined || params.totalCapital === null) {
    result.params.totalCapital = parseFloat(DEFAULT_PARAMS.capital);
  } else {
    const capital = parseFloat(params.totalCapital);
    if (isNaN(capital) || capital < 10000 || capital > 1000000) {
      result.errors.push("投资金额应在1万-100万之间");
      result.params.totalCapital = parseFloat(DEFAULT_PARAMS.capital);
    }
  }

  // 验证并补全网格类型参数
  if (!params.gridType) {
    result.params.gridType =
      REVERSE_PARAM_MAPPINGS.gridType[DEFAULT_PARAMS.grid];
  } else if (!["等比", "等差"].includes(params.gridType)) {
    result.errors.push("网格类型参数无效");
    result.params.gridType =
      REVERSE_PARAM_MAPPINGS.gridType[DEFAULT_PARAMS.grid];
  }

  // 验证并补全频率偏好参数
  if (!params.riskPreference) {
    result.params.riskPreference =
      REVERSE_PARAM_MAPPINGS.riskPreference[DEFAULT_PARAMS.risk];
  } else if (!["低频", "均衡", "高频"].includes(params.riskPreference)) {
    result.errors.push("频率偏好参数无效");
    result.params.riskPreference =
      REVERSE_PARAM_MAPPINGS.riskPreference[DEFAULT_PARAMS.risk];
  }

  // 验证并补全调节系数参数
  if (params.adjustmentCoefficient === undefined || params.adjustmentCoefficient === null) {
    result.params.adjustmentCoefficient = parseFloat(DEFAULT_PARAMS.adjustment);
  } else {
    const adjustment = parseFloat(params.adjustmentCoefficient);
    if (isNaN(adjustment) || adjustment < 0.0 || adjustment > 2.0) {
      result.errors.push("调节系数应在0.0-2.0之间");
      result.params.adjustmentCoefficient = parseFloat(DEFAULT_PARAMS.adjustment);
    }
  }

  // 验证并补全步长模式
  if (!params.stepMode || !["atr", "fixed_eda"].includes(params.stepMode)) {
    result.params.stepMode = DEFAULT_PARAMS.stepMode;
  } else {
    result.params.stepMode = params.stepMode;
  }

  // 验证并补全 E大原版自定义步长
  if (result.params.stepMode === "fixed_eda") {
    if (params.edaSteps) {
      const s = parseInt(params.edaSteps.small, 10);
      const m = parseInt(params.edaSteps.medium, 10);
      const l = parseInt(params.edaSteps.large, 10);
      if (!isNaN(s) && !isNaN(m) && !isNaN(l) && s >= 1 && s < m && m < l && l <= 50) {
        result.params.edaSteps = { small: s, medium: m, large: l };
      } else {
        result.params.edaSteps = { small: 5, medium: 15, large: 30 };
      }
    } else {
      result.params.edaSteps = { small: 5, medium: 15, large: 30 };
    }
  }

  // 验证并补全 ATR 模式乘数
  if (params.atrMultipliers) {
    const s = parseFloat(params.atrMultipliers.small);
    const m = parseFloat(params.atrMultipliers.medium);
    const l = parseFloat(params.atrMultipliers.large);
    if (!isNaN(s) && !isNaN(m) && !isNaN(l) && s >= 0.1 && s < m && m < l && l <= 10.0) {
      result.params.atrMultipliers = {
        small: Math.round(s * 100) / 100,
        medium: Math.round(m * 100) / 100,
        large: Math.round(l * 100) / 100,
      };
    } else {
      result.params.atrMultipliers = { small: 0.6, medium: 1.2, large: 2.5 };
    }
  } else {
    result.params.atrMultipliers = { small: 0.6, medium: 1.2, large: 2.5 };
  }

  // 验证并补全历史分析周期
  const days = parseInt(params.analysisDays, 10);
  if (isNaN(days) || days <= 0) {
    result.params.analysisDays = parseInt(DEFAULT_PARAMS.days, 10);
  } else {
    result.params.analysisDays = days;
  }

  // 验证并补全逐格加码比例
  const scaling = parseFloat(params.scalingRatio);
  if (isNaN(scaling) || scaling < 0.0 || scaling > 0.5) {
    result.params.scalingRatio = parseFloat(DEFAULT_PARAMS.scaling);
  } else {
    result.params.scalingRatio = scaling;
  }

  // 验证并补全做T收益留存模式
  if (!params.reinvestMode || !["pool_shares", "cash"].includes(params.reinvestMode)) {
    result.params.reinvestMode = DEFAULT_PARAMS.reinvest;
  } else {
    result.params.reinvestMode = params.reinvestMode;
  }

  // 验证并补全自定义基准价格 (可选)
  if (params.benchmarkPrice !== undefined && params.benchmarkPrice !== null && params.benchmarkPrice !== "") {
    const p = parseFloat(params.benchmarkPrice);
    if (!isNaN(p) && p > 0) {
      result.params.benchmarkPrice = p;
    }
  }

  return result;
};

/**
 * 生成分析页面URL
 * @param {string} etfCode - ETF代码
 * @param {Object} params - 分析参数
 * @returns {string} 完整的分析页面URL
 */
export const generateAnalysisURL = (etfCode, params) => {
  const searchParams = encodeAnalysisParams(params);
  const baseUrl = `${window.location.origin}/analysis/${etfCode}`;
  return `${baseUrl}?${searchParams.toString()}`;
};

/**
 * 解析当前URL获取分析参数
 * @param {string} pathname - 路径名
 * @param {string} search - 查询字符串
 * @returns {Object} 解析结果
 */
export const parseAnalysisURL = (pathname, search) => {
  const result = {
    etfCode: null,
    params: {},
    isValid: false,
  };

  // 解析ETF代码
  const pathMatch = pathname.match(/^\/analysis\/(\d{6})$/);
  if (pathMatch) {
    result.etfCode = pathMatch[1];
  }

  // 解析查询参数
  const searchParams = new URLSearchParams(search);
  result.params = decodeAnalysisParams(searchParams);

  // 验证ETF代码
  if (validateETFCode(result.etfCode)) {
    result.isValid = true;
  }

  return result;
};
