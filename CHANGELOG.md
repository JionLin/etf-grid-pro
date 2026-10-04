# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]
### Changed
- **双锚点口径披露**: 分析报告把实盘挂单锚点（默认最新收盘）与回测铺网锚点（窗口首日开盘）并排写出。回测仍按首日开盘铺网，这次只澄清展示，不改撮合定价。
- **公众号实测复现预设**: 增加 10 万 / ATR / 模式 B / 等额加码 0 / 1825 天的官方预设。首页驾驶舱默认加码 10% 与矩阵 3 万协议不变。

## [0.5.0] - 2026-09-12
### :sparkles: Major Features (5年大周期长时序回测与本地 SQLite 策略档案库)
- **5年跨牛熊大周期回测**: 将回测历史跨度从原本的 90/180/365 天扩展至 730天（2年）、1095天（3年）与 1825天（5年康波/牛熊大周期），并支持次新 ETF 上市时间平滑自适应与审计元数据回传。
- **首日开盘价基准锚点修正**: 默认以回测首个交易日的真实开盘价作为基准中枢展开三轨，彻底根除未来函数偏差，解决多周期成交笔数死锁在 87 笔的失真问题，并在回测面板内提供独立的基准锚点自定义微调功能。
- **多轨全量撮合流水透视**: 废除前端 `trades[-50:]` 50 笔生硬截断，基于 `total_trades_all` 展现选定周期内全部做 T 明细；首创【全部 / 小网 / 中网 / 大网】分轨独立筛选，动态联动成交笔数、落袋净利与单笔均利统计。
- **本地 SQLite 策略档案库**: 后端基于 Python 原生 `sqlite3`（WAL 读写分离模式）实现零依赖存储库 `BacktestRepository`，自动归档每次回测快照，支持同一标的同一周期最新去重与一键删除。
- **前端首页第 5 个 Tab【回测档案库】**: 在 `ReportTabs` 新增档案库标签页，支持按标的与周期筛选历史测算，支持【仅看各周期最新】开关与【⚡ 回填参数】一键同步至策略面板，免重算即时还原当次净值曲线与交易流水明细。
- **交易流水 CSV 本地导出**: 流水表格支持每页 20/50/100 笔客户端无卡顿分页，并支持一键将当前筛选轨道及周期的全量流水导出为 CSV 文件。
- **参数严密同步**: 修复 `AnalysisReport` 在直接点击切换至回测 Tab 时遗漏透传自定义 E大步长参数的问题。

## [0.4.0] - 2026-09-12
### :sparkles: Major Features (量化状态机回测与 10 年官方估值标尺)
- **10年官方估值标尺**: 建立全市场核心基准指数 10 年滚动 PE-TTM、PB 与股息率 (D/P) 历史百分位标尺与五档安全边际温度计，将跟踪池扩充至 117+ 只高流动性主流宽基与高景气行业 ETF。
- **三级级联降级架构**: 研发“腾讯实时行情 ➜ 中证官方 REST ➜ 10年高精度离线底表”三级高可用级联体系，实现秒级响应与零阻断高可用。
- **GridSlot 槽位状态机回测**: 在 `GridBacktestEngine` 中全面落地 `GridSlot` 二值有状态撮合（IDLE/HOLDING），彻底根除同档位重复买入；实现单边暴跌“小网 5 格上限硬熔断”防御哨兵；打通买卖逐笔对冲闭环净利润计算，告别破折号 `-` 占位，输出真实做 T 胜率。

### :zap: Architecture & Enhancements
- **复合阶梯唯一事实源**: 彻底废除顶层独立 ATR 计算逻辑，重构以 `composite_grid` 为唯一事实源（Single Source of Truth），实现价格区间上下界、看板核心主步长、总档位数与用户所选“步长生成模式”100% 动态自洽联动。
- **真实量化资金账本**: 坚决杜绝死板假兜底，实打实输出底仓实际建仓占用、网格流动现金池、100股向下取整机动零钱结余（`reserve_amount`）、99%+ 真实资金利用率、以及小网第 1 档单笔委托股数与单笔预期收益。
- **多层文档体系同步**: 系统性同步 `README.md` 门面亮点卡片与架构清单、在 `docs/STRATEGY_MANUAL.md` 策略白皮书中新增【第八章：标的量化体检与 4 维适宜度评估模型】（形式化推导 15%~45% 黄金年化波动率与 ADX < 20 震荡市判据）、以及本版本发布流水。

### :bug: Bug Fixes
- **白屏异常修复**: 修复因 `fund_allocation` 字段缺失导致前端调用 `formatCurrency(undefined)` 抛出未捕获异常引发的整页白屏崩溃。
- **估值阻断修复**: 解决中证指数官方历史文件遭遇 403 阻断导致标的（如 512170）估值无法展示的缺陷。

## [0.3.0] - 2026-09-10
### :sparkles: Major Features (E大网格 2.0 体系代际重构)
- **复合网格**: 引入 E大 2.3 大中小三层多轨复合网格体系（20% 小网高频做T / 35% 中网波段巡航 / 45% 大网极值防守），支持 14 日 ATR 动态自适应步长折算与 A 股 100 股向下对齐。
- **自定义基准价**: 支持解耦市场收盘市价与网格中心锚点 $P_0$，用户可按自有持仓成本价或心理点位铺设网格，买卖档位由该锚点精准展开。
- **状态机哨兵**: 构建网格运行三态空间边界哨兵（正常巡航 / 向上超轨获利休眠 / 深度击穿满仓待机），并在沙盘中引入超深水淹满仓解释横幅。
- **双步长模式**: 支持一键切换【★ 🌊 ATR 动态自适应（默认）】与【🏛️ E大原版经典大步长（小网5%/中网15%/大网30%）】，放宽步长截断上限至 35%，最深下潜直达 -60% 历史绝望大底。
- **留股模式**: 推出 E大 2.1 模式 B 智能利润池滚存留股机制，建立 0 成本利润蓄水池，每满 100 股自动转增免费锁仓份额，彻底攻克牛市卖飞踏空痛点。
- **逐格加码**: 推出 E大 2.2 倒金字塔递增加码算法（支持 5%~20% 调节），采用指数加权归一化分配，深水区重兵合围，极速摊薄持仓成本。
- **真实回测**: 构建严谨的 A 股 T+1 账户隔夜持仓解冻与日内高低点撮合模型，默认采用买卖各万 1、最低 0.20 元保底（免 5）实盘费率，支持 90/180/365 天周期切换、Alpha 超额收益、原生 SVG 走势对决与三轨彩虹利润归因。
- **极限沙盘**: 研发极限行情暴跌压力测试沙盘（方案 A 阶梯下原位挂载），支持 0%~-60% 自由滑块与 5 大经典情景，毫秒级推演资金耗尽点与脱困反弹阈值。
- **参数全同步**: 改造前端 URL 编解码引擎（`url.js`），支持步长模式、历史周期、加码比例与留存机制的全量双向同步，实现一键分享 100% 完整复现策略。
- **数据源增强**: 引入腾讯财经免密免 Token 日线行情降级引擎，扩充 91 只核心宽基与高景气行业 ETF 资产矩阵。
- **全链路一致**: 归一化修复前后端资金量传递，确保 3w、5w、10w 等任意资金规模在挂单、沙盘与回测中严格对齐。
- **文档体系**: 新增量化白皮书 `docs/STRATEGY_MANUAL.md`，重构 `README.md` 项目主门面。

## [0.2.5] - 2025-09-28
### :sparkles: New Features
- [`2ee17d5`](https://github.com/jorben/etf-grid-design/commit/2ee17d50171a2e8de2d8e6ac66524573d815e419) - **analysis**: add disclaimer modal for first-time users *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`b5f12a7`](https://github.com/jorben/etf-grid-design/commit/b5f12a7178a77cab726699f4a621a95d5dab892a) - bump version to 0.2.5 *(commit by [@jorben](https://github.com/jorben))*


## [0.2.4] - 2025-09-28
### :boom: BREAKING CHANGES
- due to [`dbb644a`](https://github.com/jorben/etf-grid-design/commit/dbb644a38b720a28cebe784bd237fac7caa30e5d) - 调整投资金额验证范围为1万-100万 *(commit by [@jorben](https://github.com/jorben))*:

  投资金额范围从10万-500万调整为1万-100万，可能影响现有用户的参数设置


### :sparkles: New Features
- [`dbb644a`](https://github.com/jorben/etf-grid-design/commit/dbb644a38b720a28cebe784bd237fac7caa30e5d) - **config**: 调整投资金额验证范围为1万-100万 *(commit by [@jorben](https://github.com/jorben))*
- [`399e989`](https://github.com/jorben/etf-grid-design/commit/399e989a2b8a49225b832ff5a8da8f159995769a) - **analysis**: add giscus comments integration *(commit by [@jorben](https://github.com/jorben))*


## [0.2.3] - 2025-09-27
### :bug: Bug Fixes
- [`5f3e71b`](https://github.com/jorben/etf-grid-design/commit/5f3e71b8c3b9138b804988a69e8961f0b097c546) - **algorithms**: 调整网格优化器步长参数和频率系数，扩大不同频率方案差异 *(commit by [@jorben](https://github.com/jorben))*


## [0.2.2] - 2025-09-27
### :sparkles: New Features
- [`81d666a`](https://github.com/jorben/etf-grid-design/commit/81d666a6396240a0cd214470853292a5587a64a9) - **analytics**: 添加 Cloudflare Web Analytics 集成 *(commit by [@jorben](https://github.com/jorben))*


## [0.2.1] - 2025-09-27
### :boom: BREAKING CHANGES
- due to [`d5de171`](https://github.com/jorben/etf-grid-design/commit/d5de171bf4679075a05ae508728971c8ce91c902) - 添加调节系数参数支持网格策略定制化 *(commit by [@jorben](https://github.com/jorben))*:

  风险偏好参数更名为频率偏好，原有保守/稳健/激进改为低频/均衡/高频

- due to [`fa0fa17`](https://github.com/jorben/etf-grid-design/commit/fa0fa1726e40b43999a88bb33bcb32c044bae9d7) - 增强分析历史记录兼容性和测试覆盖 *(commit by [@jorben](https://github.com/jorben))*:

  历史记录URL现在包含adjustment参数，需要前端路由相应更新


### :sparkles: New Features
- [`d5de171`](https://github.com/jorben/etf-grid-design/commit/d5de171bf4679075a05ae508728971c8ce91c902) - **algorithms**: 添加调节系数参数支持网格策略定制化 *(commit by [@jorben](https://github.com/jorben))*
- [`fa0fa17`](https://github.com/jorben/etf-grid-design/commit/fa0fa1726e40b43999a88bb33bcb32c044bae9d7) - **history**: 增强分析历史记录兼容性和测试覆盖 *(commit by [@jorben](https://github.com/jorben))*
- [`9d6aa1a`](https://github.com/jorben/etf-grid-design/commit/9d6aa1a24b915f0833764fdda7372efb88f4bbb5) - **ui**: 优化网格类型和资金分配描述文案 *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`a891ed2`](https://github.com/jorben/etf-grid-design/commit/a891ed2066d33ece5422b38f84a80acfffa12abc) - **release**: bump version to 0.2.1 *(commit by [@jorben](https://github.com/jorben))*


## [0.2.0] - 2025-09-27
### :boom: BREAKING CHANGES
- due to [`d6d4e0c`](https://github.com/jorben/etf-grid-design/commit/d6d4e0c7244cfa08ba78a35358e274f04262f610) - implement grid demand-based fund allocation algorithm *(commit by [@jorben](https://github.com/jorben))*:

  Removes base_position_ratio parameter from calculate_fund_allocation method in favor of internal calculation. Existing calls will continue to work through compatibility layer but should migrate to new V2 interface.


### :sparkles: New Features
- [`d6d4e0c`](https://github.com/jorben/etf-grid-design/commit/d6d4e0c7244cfa08ba78a35358e274f04262f610) - **algorithms**: implement grid demand-based fund allocation algorithm *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`27b2bef`](https://github.com/jorben/etf-grid-design/commit/27b2bef5cdd52c3e011f658f200552ff9409bac0) - **release**: bump version to 0.2.0 *(commit by [@jorben](https://github.com/jorben))*


## [0.1.7] - 2025-09-26
### :bug: Bug Fixes
- [`8ec69a2`](https://github.com/jorben/etf-grid-design/commit/8ec69a2ca817f93ef7e132e4d7c0891d566956eb) - **analysis**: adjust volatility threshold criteria in suitability evaluation *(commit by [@jorben](https://github.com/jorben))*


## [0.1.6] - 2025-09-26
### :boom: BREAKING CHANGES
- due to [`45f0322`](https://github.com/jorben/etf-grid-design/commit/45f032222956b3ad11f13258ffa6232f588dd585) - restructure frontend application with modular architecture *(commit by [@jorben](https://github.com/jorben))*:

  Frontend application structure has been completely reorganized from monolithic to modular architecture. Import paths have changed to use alias-based imports (@shared, @features, @pages). Existing component references may need to be updated to use new module paths.

- due to [`1643e60`](https://github.com/jorben/etf-grid-design/commit/1643e60b30e496b5e887e80cc504d925455f4e14) - restructure project with modular architecture and path aliases *(commit by [@jorben](https://github.com/jorben))*:

  All component imports have been updated to use new path aliases. Existing relative imports will no longer work. Developers must update import statements to use @shared, @features, @pages, and @app aliases.

- due to [`53a6f0c`](https://github.com/jorben/etf-grid-design/commit/53a6f0c83500fae59afa3d66f28cbd333f23ba53) - restructure project with modular architecture and path aliases *(commit by [@jorben](https://github.com/jorben))*:

  项目目录结构发生重大变更，所有相对路径导入已更新为别名路径。需要更新开发环境配置以支持新的路径映射。


### :recycle: Refactors
- [`45f0322`](https://github.com/jorben/etf-grid-design/commit/45f032222956b3ad11f13258ffa6232f588dd585) - **frontend**: restructure frontend application with modular architecture *(commit by [@jorben](https://github.com/jorben))*
- [`1643e60`](https://github.com/jorben/etf-grid-design/commit/1643e60b30e496b5e887e80cc504d925455f4e14) - **frontend**: restructure project with modular architecture and path aliases *(commit by [@jorben](https://github.com/jorben))*
- [`53a6f0c`](https://github.com/jorben/etf-grid-design/commit/53a6f0c83500fae59afa3d66f28cbd333f23ba53) - **frontend**: restructure project with modular architecture and path aliases *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`5019ad7`](https://github.com/jorben/etf-grid-design/commit/5019ad703890004236e1ac91be52e867593f7c37) - **release**: bump version to 0.1.6 *(commit by [@jorben](https://github.com/jorben))*


## [0.1.5] - 2025-09-25
### :sparkles: New Features
- [`43df8e9`](https://github.com/jorben/etf-grid-design/commit/43df8e91810d46204ce3b27d50be425e7850e4e4) - **report**: display latest price date in grid parameters card *(commit by [@jorben](https://github.com/jorben))*
- [`5c9674e`](https://github.com/jorben/etf-grid-design/commit/5c9674e77f15f60913c2256bdc67401ae802feaa) - use real-time price from Tushare for grid parameter calculation *(commit by [@jorben](https://github.com/jorben))*
- [`738add0`](https://github.com/jorben/etf-grid-design/commit/738add0fd9bee2ecc66fc491b35b93bd468387b9) - improve ETF name display format in analysis header *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`fc9d44d`](https://github.com/jorben/etf-grid-design/commit/fc9d44dddb13439ef7a9cf1bfa81667ee06eed90) - bump version to 0.1.5 and add version-sync script *(commit by [@jorben](https://github.com/jorben))*


## [0.1.4] - 2025-09-25
### :bug: Bug Fixes
- [`15592e6`](https://github.com/jorben/etf-grid-design/commit/15592e66d0d5e818d63507c82aa805a1d3e8c971) - **ui**: append version to GitHub link label for clarity *(commit by [@jorben](https://github.com/jorben))*

### :recycle: Refactors
- [`5171c64`](https://github.com/jorben/etf-grid-design/commit/5171c6463f9e6de635ab5bdb1f36c0e70097ac53) - **grid**: switch from grid-count to fixed step-size for arithmetic & geometric grids *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`cd236c3`](https://github.com/jorben/etf-grid-design/commit/cd236c3e9130ada52f1ab306bea83f79429fde1d) - bump version to 0.1.4 across all components *(commit by [@jorben](https://github.com/jorben))*


## [0.1.3] - 2025-09-25
### :sparkles: New Features
- [`7f0f512`](https://github.com/jorben/etf-grid-design/commit/7f0f512b2e002f913cce8cce7035eb96c15981f5) - centralize version management in config module *(commit by [@jorben](https://github.com/jorben))*

### :wrench: Chores
- [`1d536b4`](https://github.com/jorben/etf-grid-design/commit/1d536b43859ec9a68784c43ed8961cb7c0a5ade9) - bump version to 0.1.3 and add unified version updater script *(commit by [@jorben](https://github.com/jorben))*


## [0.1.2] - 2025-09-24
### :sparkles: New Features
- [`efd8940`](https://github.com/jorben/etf-grid-design/commit/efd894053b1ac3843ac49722229cb27263d4bef2) - restructure backend services and algorithms directories *(commit by [@jorben](https://github.com/jorben))*
- [`4e8f5fa`](https://github.com/jorben/etf-grid-design/commit/4e8f5fa10a4c72d68d36966c017209f0d3e71e40) - **api**: add middleware and refactor application structure *(commit by [@jorben](https://github.com/jorben))*
- [`5410cc4`](https://github.com/jorben/etf-grid-design/commit/5410cc471b747230ad0554b5c072f6e937e72be3) - extract ATR algorithms from service layer to dedicated module *(commit by [@jorben](https://github.com/jorben))*
- [`079cac3`](https://github.com/jorben/etf-grid-design/commit/079cac3d2e742caa69402f90c1c33912c6e6a658) - add configuration management module and update documentation *(commit by [@jorben](https://github.com/jorben))*
- [`f89d9ef`](https://github.com/jorben/etf-grid-design/commit/f89d9ef224ad1a4e8caf1e7ee5ffbd237a40327e) - add backend architecture documentation and update app configuration *(commit by [@jorben](https://github.com/jorben))*


## [0.1.1] - 2025-09-24
### :sparkles: New Features
- [`3a4f2cd`](https://github.com/jorben/etf-grid-design/commit/3a4f2cdd7a187c51dc2922cb786d82ca23dd40c1) - add global watermark component with responsive design *(commit by [@jorben](https://github.com/jorben))*


## [0.1.0] - 2025-09-24
### :sparkles: New Features
- [`6d98067`](https://github.com/jorben/etf-grid-design/commit/6d980673836476063c48c73eab401ec38c7f5b65) - add GitHub repository link to header navigation *(commit by [@jorben](https://github.com/jorben))*
- [`c65750d`](https://github.com/jorben/etf-grid-design/commit/c65750db7b77e17fd9f4a192e8a232169b6c14cc) - refactor ETF analysis system with comprehensive strategy framework *(commit by [@jorben](https://github.com/jorben))*
- [`3710a10`](https://github.com/jorben/etf-grid-design/commit/3710a1010cd28e6d2589e0c28aaed60f5ff79b27) - enhance ETF trading volume simulation and grid trading suitability analysis *(commit by [@jorben](https://github.com/jorben))*
- [`5161faf`](https://github.com/jorben/etf-grid-design/commit/5161fafe0567bb3865467e3cb5f82d667a6e1909) - require valid Tushare token and add environment configuration *(commit by [@jorben](https://github.com/jorben))*
- [`43b5364`](https://github.com/jorben/etf-grid-design/commit/43b53640f216955e9928d938f3b6e5e52f3db5b9) - **grid**: Optimize grid strategy fund allocation algorithm *(commit by [@jorben](https://github.com/jorben))*
- [`f464cbf`](https://github.com/jorben/etf-grid-design/commit/f464cbf8fa44a9142e6861b7accbca16342cbaf2) - **grid**: Implement ATR-based intelligent grid step strategy *(commit by [@jorben](https://github.com/jorben))*
- [`564813f`](https://github.com/jorben/etf-grid-design/commit/564813ffd54e8c76d9dbb19918ee2ce691c3f0c5) - **ui**: Optimize the display effect of suitability evaluation cards *(commit by [@jorben](https://github.com/jorben))*
- [`8386355`](https://github.com/jorben/etf-grid-design/commit/83863553d4f290ece776b7f41bf39a361ec14895) - **report**: Optimize Analysis Report Card Styles and Content *(commit by [@jorben](https://github.com/jorben))*
- [`1a97af9`](https://github.com/jorben/etf-grid-design/commit/1a97af9f68a6e138eb494edbc710cea197d2fcc6) - Optimize grid strategy display and add data quality evaluation module *(commit by [@jorben](https://github.com/jorben))*
- [`e9a8dc1`](https://github.com/jorben/etf-grid-design/commit/e9a8dc194fe51a86fb93ae270edb5d2b01b91248) - add ETF info skeleton loading component *(commit by [@jorben](https://github.com/jorben))*
- [`6f07c0e`](https://github.com/jorben/etf-grid-design/commit/6f07c0ee74b68bd4ae220c28e448fcf55eca8dc7) - **ui**: simplify ETF selection layout and reduce popular ETF list *(commit by [@jorben](https://github.com/jorben))*
- [`1c13ff9`](https://github.com/jorben/etf-grid-design/commit/1c13ff96c48c9169b09baafbc40e95cf9c4c39ba) - remove frequency preference parameter from ETF strategy analysis *(commit by [@jorben](https://github.com/jorben))*
- [`1e38b69`](https://github.com/jorben/etf-grid-design/commit/1e38b69c1131255b46437402f5a90826dc543933) - improve AnalysisReport UI layout and remove PDF export *(commit by [@jorben](https://github.com/jorben))*
- [`01a1500`](https://github.com/jorben/etf-grid-design/commit/01a1500812f7a3bee26bfeb7d48b57ca44b77b01) - add share functionality to AnalysisReport component *(commit by [@jorben](https://github.com/jorben))*
- [`55d6150`](https://github.com/jorben/etf-grid-design/commit/55d61503300cfb484a15061bc440be3a8dbc3135) - **frontend**: add react-helmet-async for SEO and meta tag management *(commit by [@jorben](https://github.com/jorben))*
- [`753fca3`](https://github.com/jorben/etf-grid-design/commit/753fca3afb2ab5bfa1917e2fb41d328cf03b8562) - **grid**: add base price anchoring to grid level calculation *(commit by [@jorben](https://github.com/jorben))*
- [`cdc0fc9`](https://github.com/jorben/etf-grid-design/commit/cdc0fc94f656d266eac2d07a23571f975e0c0d0a) - adjust ATR risk multipliers and grid strategy parameters *(commit by [@jorben](https://github.com/jorben))*
- [`5dddf4f`](https://github.com/jorben/etf-grid-design/commit/5dddf4ff20090d65a7e335b125fa9b45beabc921) - **grid**: improve buy grid calculation and price level display *(commit by [@jorben](https://github.com/jorben))*
- [`c5e9385`](https://github.com/jorben/etf-grid-design/commit/c5e9385a8bf26ac265d4192e1a8346c089d8318e) - **grid**: improve grid calculation with base price centering *(commit by [@jorben](https://github.com/jorben))*
- [`80ede6e`](https://github.com/jorben/etf-grid-design/commit/80ede6e1e58a29f62cc7ae5bc4dfb69eacca9882) - **ui**: add visual price range bar to GridParametersCard *(commit by [@jorben](https://github.com/jorben))*
- [`7ce7d20`](https://github.com/jorben/etf-grid-design/commit/7ce7d20ed01e3933141433821b0d28200c273e18) - refactor grid strategy display and move strategy analysis to dedicated component *(commit by [@jorben](https://github.com/jorben))*
- [`10aa58c`](https://github.com/jorben/etf-grid-design/commit/10aa58c65147528808fb570dfff39e36691ed726) - add version management system *(commit by [@jorben](https://github.com/jorben))*
- [`f7a960d`](https://github.com/jorben/etf-grid-design/commit/f7a960dd757dab6677e10c9c4ffd32f492192637) - **ui**: improve price range visualization in GridParametersCard *(commit by [@jorben](https://github.com/jorben))*
- [`7095a21`](https://github.com/jorben/etf-grid-design/commit/7095a21e4d3b06eaf8de5218c54e017a90ed762c) - add production static file serving and environment configuration *(commit by [@jorben](https://github.com/jorben))*

### :bug: Bug Fixes
- [`b552085`](https://github.com/jorben/etf-grid-design/commit/b55208510f17ac1f7603d00417d3318f0aa75338) - update screenshot URL to correct repository reference *(commit by [@jorben](https://github.com/jorben))*
- [`70728ff`](https://github.com/jorben/etf-grid-design/commit/70728ff3953577e3f56acf09256b7eca96f36e33) - correct screenshot filename typo in README *(commit by [@jorben](https://github.com/jorben))*

### :recycle: Refactors
- [`31b7e65`](https://github.com/jorben/etf-grid-design/commit/31b7e65d940bad415c4e37911c48e1e4c823e5dd) - **frontend**: Remove Recharts chart-related code *(commit by [@jorben](https://github.com/jorben))*
- [`e564a05`](https://github.com/jorben/etf-grid-design/commit/e564a05ba5de26012840443d36e6474efcd4ab65) - Unify terminology from "fitness" to "suitability" *(commit by [@jorben](https://github.com/jorben))*
- [`b3757b9`](https://github.com/jorben/etf-grid-design/commit/b3757b9dc4925a54a0123dd8df40976dce01d69f) - Remove ETF report summary feature *(commit by [@jorben](https://github.com/jorben))*
- [`4e4b6b6`](https://github.com/jorben/etf-grid-design/commit/4e4b6b6dacb842112ac6601a0d3ef6843cbf2ecc) - Remove preset configuration feature and optimize frontend UI *(commit by [@jorben](https://github.com/jorben))*
- [`62ca0fb`](https://github.com/jorben/etf-grid-design/commit/62ca0fbb7fda2403af8d64e8267bf800aa41a7c7) - remove hardcoded ETF data and update popular ETF list *(commit by [@jorben](https://github.com/jorben))*
- [`2523938`](https://github.com/jorben/etf-grid-design/commit/2523938c75ca8b8e839f060874da640af31b4d2e) - remove share functionality and restructure grid parameters display *(commit by [@jorben](https://github.com/jorben))*
- [`f32d985`](https://github.com/jorben/etf-grid-design/commit/f32d985324c9342a955b615d0121794fffd1e466) - improve grid trading quantity calculation for buy levels *(commit by [@jorben](https://github.com/jorben))*
- [`04d6125`](https://github.com/jorben/etf-grid-design/commit/04d6125b0f6b93674c8d52ed731efd2051cddb5a) - rename utilization_rate to grid_fund_utilization_rate *(commit by [@jorben](https://github.com/jorben))*
- [`15ef451`](https://github.com/jorben/etf-grid-design/commit/15ef45198778935cf88719151a0af5928785f74e) - remove backtest engine dependency from ETF analysis service *(commit by [@jorben](https://github.com/jorben))*
- [`726f216`](https://github.com/jorben/etf-grid-design/commit/726f2168f8edfca45821cc2745f24c80dedaf84a) - replace DataService with TushareClient for improved caching *(commit by [@jorben](https://github.com/jorben))*


## [0.0.3] - 2025-09-21
### :sparkles: New Features
- [`1e925fd`](https://github.com/jorben/etf-grid-design/commit/1e925fdf442bc832ff7e3bb2ce2a396f8efaf73d) - support URL query params for analysis page navigation *(commit by [@jorben](https://github.com/jorben))*

### :bug: Bug Fixes
- [`683ed56`](https://github.com/jorben/etf-grid-design/commit/683ed56c680b500a4c8ba46449857573ceee24c3) - update copyright text to include domain name *(commit by [@jorben](https://github.com/jorben))*


## [0.0.2] - 2025-09-21
### :sparkles: New Features
- [`acad14c`](https://github.com/jorben/etf-grid-design/commit/acad14ccf755802dd4d2c2c148d0e2ee6a3ac918) - Initialize ETF Grid Trading Strategy Design Tool project *(commit by [@jorben](https://github.com/jorben))*
- [`a192bc8`](https://github.com/jorben/etf-grid-design/commit/a192bc8691708096d81d2b92295bf487e0146058) - **etf**: add dimension scores to suitability analysis *(commit by [@jorben](https://github.com/jorben))*
- [`4652c9f`](https://github.com/jorben/etf-grid-design/commit/4652c9fd1f59908ac3a6473cb708795e30f61c0c) - **analysis**: enhance grid strategy with frequency matching and historical data *(commit by [@jorben](https://github.com/jorben))*
- [`52cca15`](https://github.com/jorben/etf-grid-design/commit/52cca15b476ab0c73bcb0b0a6edf369cf74fd4d7) - change backend port and refactor ETF grid trading evaluation *(commit by [@jorben](https://github.com/jorben))*
- [`ff5de28`](https://github.com/jorben/etf-grid-design/commit/ff5de28bda06d35ea7fd90519e4943b968193430) - Clean up test code *(commit by [@jorben](https://github.com/jorben))*
- [`5621aa1`](https://github.com/jorben/etf-grid-design/commit/5621aa1600d02cf95bd2d4b562fc363c9f9db73b) - **grid**: improve drawdown calculation and UI display formatting *(commit by [@jorben](https://github.com/jorben))*
- [`a3e38b9`](https://github.com/jorben/etf-grid-design/commit/a3e38b95b70df55da20b4cbf4bb8eba1d7584a3d) - implement dynamic shares calculator with target return optimization *(commit by [@jorben](https://github.com/jorben))*
- [`2477370`](https://github.com/jorben/etf-grid-design/commit/2477370c643bef9195bf26da21b80c6aaa290b3c) - add ETF name lookup API and optimize trading frequency parameters *(commit by [@jorben](https://github.com/jorben))*
- [`68e8a9e`](https://github.com/jorben/etf-grid-design/commit/68e8a9e201339bb995a929ac536016c03f91dbb3) - add file-based caching system with management endpoints *(commit by [@jorben](https://github.com/jorben))*
- [`bd2a307`](https://github.com/jorben/etf-grid-design/commit/bd2a307e3085061675cef5734ac9b3fab8835c14) - update UI text and icons for better user experience *(commit by [@jorben](https://github.com/jorben))*
- [`3bdd362`](https://github.com/jorben/etf-grid-design/commit/3bdd3628039cd0288607a8fa4e25a1084a775166) - add react-router-dom and implement page routing *(commit by [@jorben](https://github.com/jorben))*
- [`18a93fb`](https://github.com/jorben/etf-grid-design/commit/18a93fb69ca7f306524b4fff98e86357cd08ad68) - add Docker containerization support for ETF grid trading tool *(commit by [@jorben](https://github.com/jorben))*

### :bug: Bug Fixes
- [`62e5bdc`](https://github.com/jorben/etf-grid-design/commit/62e5bdc44d1ccb0c3b3db79c24c9594af4d349cd) - swap success/danger color semantics for price indicators *(commit by [@jorben](https://github.com/jorben))*

[0.0.2]: https://github.com/jorben/etf-grid-design/compare/0.0.1...0.0.2
[0.0.3]: https://github.com/jorben/etf-grid-design/compare/0.0.2...0.0.3
[0.1.0]: https://github.com/jorben/etf-grid-design/compare/0.0.3...0.1.0
[0.1.1]: https://github.com/jorben/etf-grid-design/compare/0.1.0...0.1.1
[0.1.2]: https://github.com/jorben/etf-grid-design/compare/0.1.1...0.1.2
[0.1.3]: https://github.com/jorben/etf-grid-design/compare/0.1.2...0.1.3
[0.1.4]: https://github.com/jorben/etf-grid-design/compare/0.1.3...0.1.4
[0.1.5]: https://github.com/jorben/etf-grid-design/compare/0.1.4...0.1.5
[0.1.6]: https://github.com/jorben/etf-grid-design/compare/0.1.5...0.1.6
[0.1.7]: https://github.com/jorben/etf-grid-design/compare/0.1.6...0.1.7
[0.2.0]: https://github.com/jorben/etf-grid-design/compare/0.1.7...0.2.0
[0.2.1]: https://github.com/jorben/etf-grid-design/compare/0.2.0...0.2.1
[0.2.2]: https://github.com/jorben/etf-grid-design/compare/0.2.1...0.2.2
[0.2.3]: https://github.com/jorben/etf-grid-design/compare/0.2.2...0.2.3
[0.2.4]: https://github.com/jorben/etf-grid-design/compare/0.2.3...0.2.4
[0.2.5]: https://github.com/jorben/etf-grid-design/compare/0.2.4...0.2.5
