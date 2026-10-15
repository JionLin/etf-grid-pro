/**
 * API服务配置
 * 处理与后端的所有HTTP通信
 */

const API_BASE_URL = "/api";

class ApiService {
  constructor() {
    this.baseURL = API_BASE_URL;
  }

  /**
   * 通用请求方法
   */
  async request(endpoint, options = {}) {
    const url = `${this.baseURL}${endpoint}`;

    const config = {
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
      ...options,
    };

    try {
      const response = await fetch(url, config);

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          errorData.message || `HTTP error! status: ${response.status}`,
        );
      }

      return await response.json();
    } catch (error) {
      if (error?.name === "AbortError" || error?.code === "ERR_CANCELED") {
        // 良性取消，静默抛出以便调用方捕获判定，不向控制台记录红字
        throw error;
      }
      console.error(`API请求失败 [${endpoint}]:`, error);
      throw error;
    }
  }

  /**
   * GET请求
   */
  async get(endpoint, params = {}, options = {}) {
    const queryString = new URLSearchParams(params).toString();
    const url = queryString ? `${endpoint}?${queryString}` : endpoint;

    return this.request(url, {
      method: "GET",
      signal: options.signal,
    });
  }

  /**
   * POST请求
   */
  async post(endpoint, data = {}, options = {}) {
    return this.request(endpoint, {
      method: "POST",
      body: JSON.stringify(data),
      signal: options.signal,
    });
  }

  /**
   * DELETE请求
   */
  async delete(endpoint) {
    return this.request(endpoint, {
      method: "DELETE",
    });
  }

  /**
   * ETF分析主接口
   */
  async analyzeETF(parameters, options = {}) {
    return this.post("/analyze", parameters, options);
  }

  /**
   * 策略真实历史回测接口
   */
  async runBacktest(parameters, options = {}) {
    return this.post("/backtest", parameters, options);
  }

  /**
   * 获取 E大网格实战三篇经典文献
   */
  async getEdaLiterature() {
    return this.get("/literature/eda-grid");
  }

  /**
   * 获取ETF基础信息
   */
  async getETFBasicInfo(etfCode, options = {}) {
    return this.get(`/etf/basic-info/${etfCode}`, {}, options);
  }

  /**
   * 兼容旧版方法
   */
  async getETFInfo(etfCode, options = {}) {
    return this.getETFBasicInfo(etfCode, options);
  }

  /**
   * 获取热门ETF列表
   */
  async getPopularETFs() {
    return this.get("/etf/popular");
  }

  /**
   * 验证ETF代码
   */
  async validateETFCode(etfCode) {
    return this.get("/etf/validate", { code: etfCode });
  }

  /**
   * 获取历史数据
   */
  async getHistoricalData(etfCode, startDate, endDate) {
    return this.get("/etf/historical", {
      code: etfCode,
      start_date: startDate,
      end_date: endDate,
    });
  }

  /**
   * 健康检查
   */
  async healthCheck() {
    return this.get("/health");
  }

  /**
   * 获取系统版本号
   */
  async getVersion() {
    return this.get("/version");
  }

  /**
   * 获取回测档案列表
   */
  async getBacktestRecords(params = {}, options = {}) {
    return this.get("/backtest/records", params, options);
  }

  /**
   * 获取单次回测档案快照详情
   */
  async getBacktestRecordDetail(runId) {
    return this.get(`/backtest/records/${runId}`);
  }

  /**
   * 删除某次回测档案
   */
  async deleteBacktestRecord(runId) {
    return this.delete(`/backtest/records/${runId}`);
  }

  /**
   * 获取档案库已测试标的列表
   */
  async getBacktestDistinctETFs(options = {}) {
    return this.get("/backtest/distinct-etfs", {}, options);
  }

  /**
   * 适合度榜。与个人回测档案不是同一份列表。
   */
  async getGridFitBoard(params = {}, options = {}) {
    return this.get("/grid-fit/board", params, options);
  }

  async refreshGridFit() {
    return this.post("/grid-fit/refresh", {});
  }

  /**
   * 获取本地库里的成熟 ETF 多周期回测矩阵
   */
  async getUniverseBacktestMatrix(params = {}, options = {}) {
    return this.get("/backtest/matrix", params, options);
  }

  /**
   * 获取首页 11 大赛道胜率与收益横评
   */
  async getSectorsRanking(params = {}, options = {}) {
    return this.get("/backtest/sectors-ranking", params, options);
  }
}

// 创建单例实例
const apiService = new ApiService();

// 导出常用方法
export const analyzeETF = (parameters, options) => apiService.analyzeETF(parameters, options);
export const runBacktest = (parameters, options) => apiService.runBacktest(parameters, options);

export function isAbortError(error) {
  return error?.name === "AbortError";
}
export const getEdaLiterature = () => apiService.getEdaLiterature();
export const getETFBasicInfo = (etfCode, options) => apiService.getETFBasicInfo(etfCode, options);
export const getETFInfo = (etfCode, options) => apiService.getETFInfo(etfCode, options);
export const getPopularETFs = () => apiService.getPopularETFs();
export const validateETFCode = (etfCode) => apiService.validateETFCode(etfCode);
export const getHistoricalData = (etfCode, startDate, endDate) =>
  apiService.getHistoricalData(etfCode, startDate, endDate);
export const healthCheck = () => apiService.healthCheck();
export const getVersion = () => apiService.getVersion();
export const getBacktestRecords = (params, options) => apiService.getBacktestRecords(params, options);
export const getBacktestRecordDetail = (runId) => apiService.getBacktestRecordDetail(runId);
export const deleteBacktestRecord = (runId) => apiService.deleteBacktestRecord(runId);
export const getBacktestDistinctETFs = (options) => apiService.getBacktestDistinctETFs(options);
export const getGridFitBoard = (params, options) => apiService.getGridFitBoard(params, options);
export const refreshGridFit = () => apiService.refreshGridFit();
export const getUniverseBacktestMatrix = (params, options) => apiService.getUniverseBacktestMatrix(params, options);
export const getSectorsRanking = (params, options) => apiService.getSectorsRanking(params, options);

export default apiService;
