/**
 * 策略草稿原子快照与多方案预设管理模块
 * 架构特性：
 * 1. 原子持久化：将分散的 11 个孤立 key 收敛至单一版本化键名 etf_grid_strategy_draft_v1
 * 2. 平滑自动迁移：自动探测用户浏览器中残留的旧 keys 并合入新快照，随后清理旧 key
 * 3. 官方出厂经典预设：内置 E大经典守株版、ATR动态套利版、宽网极限防守版
 * 4. 自定义方案管理：支持用户另存为命名预设，以及一键重置回出厂默认
 */

export const STRATEGY_DRAFT_STORAGE_KEY = "etf_grid_strategy_draft_v1";

export const LEGACY_KEYS = [
  "etfCode",
  "totalCapital",
  "gridType",
  "riskPreference",
  "adjustmentCoefficient",
  "analysisDays",
  "reinvestMode",
  "scalingRatio",
  "stepMode",
  "edaSteps",
  "atrMultipliers",
];

export const DEFAULT_STRATEGY_PARAMS = {
  etfCode: "510300",
  totalCapital: "30000",
  benchmarkMode: "market",
  customPrice: "",
  gridType: "等比",
  riskPreference: "均衡",
  adjustmentCoefficient: 1.0,
  analysisDays: 180,
  stepMode: "atr",
  edaSteps: { small: 5, medium: 15, large: 30 },
  atrMultipliers: { small: 0.6, medium: 1.2, large: 2.5 },
  reinvestMode: "pool_shares",
  scalingRatio: 0.1,
  enableScaling: true,
};

export const SYSTEM_PRESETS = [
  {
    id: "eda_classic",
    name: "🏆 E大经典守株版",
    badge: "推荐",
    description: "5%/15%/30% 经典大步长 · 模式B留股票池 · 倒金字塔加码10% · 5年牛熊",
    params: {
      ...DEFAULT_STRATEGY_PARAMS,
      totalCapital: "30000",
      stepMode: "fixed_eda",
      edaSteps: { small: 5, medium: 15, large: 30 },
      reinvestMode: "pool_shares",
      scalingRatio: 0.10,
      enableScaling: true,
      analysisDays: 1825,
    },
  },
  {
    id: "atr_high_freq",
    name: "⚡ ATR动态套利版",
    badge: "高频",
    description: "14日ATR自适应(0.6/1.2/2.5) · 模式A全额现金 · 各档等额 · 180天周期",
    params: {
      ...DEFAULT_STRATEGY_PARAMS,
      totalCapital: "30000",
      stepMode: "atr",
      atrMultipliers: { small: 0.6, medium: 1.2, large: 2.5 },
      reinvestMode: "cash",
      scalingRatio: 0.0,
      enableScaling: false,
      analysisDays: 180,
    },
  },
  {
    id: "wechat_repro",
    name: "📰 公众号实测复现",
    badge: "等额",
    description: "10万 · ATR(0.6/1.2/2.5) · 模式B留股 · 各档等额 · 5年。对齐公众号三轨案例，不是首页默认加码10%",
    params: {
      ...DEFAULT_STRATEGY_PARAMS,
      totalCapital: "100000",
      gridType: "等比",
      riskPreference: "均衡",
      stepMode: "atr",
      atrMultipliers: { small: 0.6, medium: 1.2, large: 2.5 },
      reinvestMode: "pool_shares",
      scalingRatio: 0.0,
      enableScaling: false,
      analysisDays: 1825,
      benchmarkMode: "market",
      customPrice: "",
    },
  },
  {
    id: "deep_defense",
    name: "🛡️ 宽网极限防守版",
    badge: "大波段",
    description: "ATR宽网乘数(0.8/1.5/3.2) · 模式B留股 · 倒金字塔加码15% · 5年周期",
    params: {
      ...DEFAULT_STRATEGY_PARAMS,
      totalCapital: "50000",
      stepMode: "atr",
      atrMultipliers: { small: 0.8, medium: 1.5, large: 3.2 },
      reinvestMode: "pool_shares",
      scalingRatio: 0.15,
      enableScaling: true,
      analysisDays: 1825,
    },
  },
];

/**
 * 从浏览器 localStorage 探测并迁移旧散落键
 */
function migrateLegacyKeysIfPresent() {
  if (typeof window === "undefined" || !window.localStorage) return null;

  try {
    let hasLegacy = false;
    const migrated = { ...DEFAULT_STRATEGY_PARAMS };

    for (const key of LEGACY_KEYS) {
      const raw = window.localStorage.getItem(key);
      if (raw !== null) {
        hasLegacy = true;
        try {
          const parsed = JSON.parse(raw);
          if (parsed !== undefined && parsed !== null) {
            migrated[key] = parsed;
          }
        } catch {
          migrated[key] = raw;
        }
      }
    }

    if (hasLegacy) {
      // 成功提取旧数据，构造 v1 快照
      const snapshot = {
        version: 1,
        updatedAt: Date.now(),
        activePresetId: "custom",
        current: migrated,
        customPresets: [],
      };
      window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(snapshot));

      // 清理已迁移的旧键
      for (const key of LEGACY_KEYS) {
        window.localStorage.removeItem(key);
      }
      return snapshot;
    }
  } catch (err) {
    console.warn("探测或迁移旧策略草稿失败:", err);
  }
  return null;
}

/**
 * 加载当前完整的策略快照
 * @returns {{version: number, updatedAt: number, activePresetId: string, current: Object, customPresets: Array}}
 */
export function loadDraftSnapshot() {
  if (typeof window === "undefined" || !window.localStorage) {
    return {
      version: 1,
      updatedAt: Date.now(),
      activePresetId: "eda_classic",
      current: { ...DEFAULT_STRATEGY_PARAMS },
      customPresets: [],
    };
  }

  try {
    const raw = window.localStorage.getItem(STRATEGY_DRAFT_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed && typeof parsed === "object" && parsed.current) {
        return {
          version: parsed.version || 1,
          updatedAt: parsed.updatedAt || Date.now(),
          activePresetId: parsed.activePresetId || "custom",
          current: { ...DEFAULT_STRATEGY_PARAMS, ...parsed.current },
          customPresets: Array.isArray(parsed.customPresets) ? parsed.customPresets : [],
        };
      }
    }

    // 若无新快照，尝试平滑迁移旧散落键
    const migrated = migrateLegacyKeysIfPresent();
    if (migrated) return migrated;

    // 均不存在，初始化出厂默认快照
    const initialSnapshot = {
      version: 1,
      updatedAt: Date.now(),
      activePresetId: "eda_classic",
      current: { ...DEFAULT_STRATEGY_PARAMS },
      customPresets: [],
    };
    window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(initialSnapshot));
    return initialSnapshot;
  } catch (err) {
    console.warn("加载策略草稿快照失败:", err);
    return {
      version: 1,
      updatedAt: Date.now(),
      activePresetId: "eda_classic",
      current: { ...DEFAULT_STRATEGY_PARAMS },
      customPresets: [],
    };
  }
}

/**
 * 保存或更新当前草稿
 * @param {Object} currentParams 
 * @param {string} [presetId] 
 */
export function saveDraftSnapshot(currentParams, presetId) {
  if (!currentParams || typeof window === "undefined" || !window.localStorage) return;

  try {
    const snapshot = loadDraftSnapshot();
    const updated = {
      ...snapshot,
      updatedAt: Date.now(),
      activePresetId: presetId !== undefined ? presetId : snapshot.activePresetId,
      current: { ...snapshot.current, ...currentParams },
    };
    window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (err) {
    console.warn("持久化保存策略草稿失败:", err);
  }
}

/**
 * 保存当前参数为新的自定义预设
 * @param {string} name 预设名称
 * @param {Object} params 参数包
 */
export function saveCustomPreset(name, params) {
  if (!name || !params || typeof window === "undefined" || !window.localStorage) return;

  try {
    const snapshot = loadDraftSnapshot();
    const newPreset = {
      id: `custom_${Date.now()}`,
      name: String(name).trim(),
      createdAt: Date.now(),
      params: { ...params },
    };
    const updated = {
      ...snapshot,
      activePresetId: newPreset.id,
      current: { ...params },
      customPresets: [...snapshot.customPresets.filter((p) => p.name !== newPreset.name), newPreset],
    };
    window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (err) {
    console.warn("保存自定义预设失败:", err);
  }
}

/**
 * 删除某项自定义预设
 * @param {string} presetId 
 */
export function deleteCustomPreset(presetId) {
  if (!presetId || typeof window === "undefined" || !window.localStorage) return;

  try {
    const snapshot = loadDraftSnapshot();
    const updated = {
      ...snapshot,
      customPresets: snapshot.customPresets.filter((p) => p.id !== presetId),
    };
    window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(updated));
    return updated;
  } catch (err) {
    console.warn("删除自定义预设失败:", err);
  }
}

/**
 * 彻底重置为出厂默认官方推荐状态
 */
export function resetToSystemDefault() {
  if (typeof window === "undefined" || !window.localStorage) return;

  try {
    const snapshot = loadDraftSnapshot();
    const resetSnapshot = {
      ...snapshot,
      updatedAt: Date.now(),
      activePresetId: "eda_classic",
      current: { ...DEFAULT_STRATEGY_PARAMS },
    };
    window.localStorage.setItem(STRATEGY_DRAFT_STORAGE_KEY, JSON.stringify(resetSnapshot));
    return resetSnapshot;
  } catch (err) {
    console.warn("重置出厂默认配置失败:", err);
  }
}
