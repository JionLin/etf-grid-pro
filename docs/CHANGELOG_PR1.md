# PR #1 变更说明

分支 `cursor/fix-stale-pool-quotes-f138`。下面按合入顺序说明改了什么、当时怎么核对。文末是 Mac 上的启动命令和限制。

## 首页价格停在建池日

标的池超过 20 只后，首页直接读 `etf_instrument` 里的快照，不再拉行情。515220 因此一直显示 2026-09-11 的收盘 **1.292 / -2.05%**，而当时腾讯、新浪的最新价是 **1.303 / +0.85%**。

直出标的池时，用新浪分类行情的「最新价」「涨跌幅」覆盖内存和数据库。没有最新价时不用昨收顶上。行情接口失败时仍返回原快照。

核对：`backend/tests/test_services/test_pool_quote_refresh.py` 里 515220 从 1.292 被覆盖成 1.303。线上 `https://qt.gtimg.cn/q=sh515220` 返回 200，最新价字段为 1.303。

## H1 盘中日缓存

盘中不读当天日缓存，15:00 前的腾讯备用行情不写入交易日缓存。雷达和驾驶舱卡片显示行情日期。

核对：同一测试文件里的盘中不读缓存、收盘前不落库、收盘后才落库、周末仍用上一交易日缓存。

## H9 本机监听

`start.sh` 只把 Flask 绑在 `127.0.0.1`，调试器默认关闭。只有 `FLASK_DEBUG=1`（或 `true` / `yes` / `on`）或命令行 `--debug` 才打开。容器仍用 `HOST=0.0.0.0`。

核对：`backend/tests/test_listen_bind.py`。

## H2 分析周期 1825 天

分析接口接受 90、180、365、1825。名单外的值返回 400，不再静默退回 180。页面展示服务端实际采用的天数。

核对：分析天数用例，以及后来用 SQLite 启动后 `POST /api/analyze`，请求 1825，响应里 `analysisDays` 为 1825。

## H7 不够一手

每档股数取整为 0 时不再硬凑 100 股。这一档跳过，并标出资金缺口。1 万本金、股价 6 元会出现缺口；10 万本金、股价 1.3 元仍可排出 20 档。

核对：`test_composite_grid_funding_gap.py`。

## H4 回测步长不用未来 ATR

策略回测的 ATR 步长改用窗口第一根 K 线，不再用窗口最后一天。显式传入的 ATR 比例仍然有效。全市场矩阵仍用窗口末端 ATR。

限制：锚点 ATR 是拉到的窗口里第一根 K 线的波动，前面没有额外 14 日预热。

核对：`test_anchor_atr.py`。

## H5 同一根 K 线不能先卖后买

回测状态机里，同一档在一根日 K 上已经卖出后，当天不再买回。

核对：`test_backtest_state_machine.py`。

## H8 压力测试佣金

前端压力测试改为佣金万 1、最低 0.2 元。现金或底仓不够就停止，不再继续成交。

核对：在 `frontend/` 下用 node 跑 `stressTestCalculator` 的测试。

## H3 本地日 K 计算 ATR 和成交额

不再按名称写死 ATR，也不再把「今日成交额 × 0.95」当成月均成交额。重建和刷新都用本地日 K 的 14 日 ATR 和 20 日均额。样本不够标成「数据不足」，过不了雷达门槛。没有官方上市日时，列表日期也写「数据不足」，不再写死一个日期字符串。

核对：标的池与 bar metrics 相关用例。

## H6 频率和等额

频率偏好接到 ATR 步长上，且只在该轨没有自定义 ATR 倍数、也不是固定 E 大步长时生效。低频 1.5/0.6，均衡 1.0，高频 0.35/0.6。均衡、调节系数 1.0、ATR 比例 0.02 时，小步仍是以前的 0.012。底仓比例仍是 50%。等额（缩放比例 0）本来就会把各档买入金额拉平，回归测试锁的是金额而不是股数。

核对：`test_frequency_and_equal_amount.py`。回测接口只接受「低频 / 均衡 / 高频」。

## M1 涨跌幅相对前收

入库涨跌幅改为相对前一日收盘。第一天没有前收时记 0，不用开盘价代替。东财路径原本就是相对前收。

## M2 T+0 一处判定

T+0 代码和名称关键字收进 `backend/services/data/t0_rules.py`。代码包括 513130、513180、159920、513100、159941、513500、513050、164824、513520、159866、513880、513000。

## M3 短缺口

只隔周末的缺口可以跳过补齐。中间夹了工作日就不再当成周末。例：2026-10-16 到 2026-10-18 可以跳过；2026-10-15 到 2026-10-18 不行。有交易日历时，休市日也算非交易日。

## M4 上海时间

无时区的时间按上海墙钟理解，不另做时区换算。带时区的时间先换到上海。有已缓存的交易日历时，节假日不当成交易日；没有日历时只排除周末。Docker 镜像安装 tzdata，并设置 `TZ=Asia/Shanghai`。

核对：`test_market_clock.py`。

## M5 腾讯 HTTPS

三处腾讯行情地址从 `http` 改为 `https`。K 线备用源本来就是 `https://web.ifzq.gtimg.cn`。

## M6 文档与容器环境变量

当时先把文档改成「库是 MySQL」。随后的 SQLite/MySQL 切换又改回默认 SQLite，并保留「选了 MySQL 但连不上不会改回 SQLite」。`docker-compose` 传入 `MYSQL_*`。

## M7 浏览器不看异常原文

接口、启动同步状态、适合度榜和矩阵原因在出错时返回固定中文。日志里仍保留异常。参数校验故意返回的 `ValueError` 中文提示继续返回给页面。

核对：`test_browser_error_text.py`。

## M8 当年交易日历

过去的年份继续用永久缓存。当年按上海日期放进日缓存，不沿用过期的永久缓存，拉取成功后再写回永久缓存。随包的 akshare 日历只到 2025-12-31，当年日历需要网络。

核对：`test_trading_calendar.py`。

## L1 资金快选

去掉 150 万和 200 万两档，上限仍是 100 万。

核对：`test_capital_presets.py`。

## L2 文献路径

去掉写死的 `/Users/johnny`。顺序是环境变量 `EDA_LITERATURE_PATH`、仓库里的 `E大/网格3篇.md`、当前工作目录。

核对：`test_literature_paths.py`。

## L3 测试不强制 MySQL 和真实 Token

`conftest` 在导入配置前，若没有 `TUSHARE_TOKEN` 就放一个测试占位值，不覆盖你自己的 token。数据库测试在连不上所选后端时跳过。默认 SQLite 时这些测试会真正执行。

## 数据库：默认 SQLite，可切 MySQL

`DB_TYPE=sqlite|mysql`，不写时是 `sqlite`。文件是 `SQLITE_PATH`，默认 `data/etf_grid.sqlite`。测试库在同一目录，文件名 `etf_grid_test.sqlite`。选了 MySQL 时，测试会自己建 `etf_grid_test`。

MySQL 仓库里的 SQL 保持原样。SQLite 只在连接层翻译 `%s`、`ON DUPLICATE KEY`、`DATE_SUB`、`AUTO_INCREMENT`、`DOUBLE`、表注释和 `TRUNCATE`。选了 `DB_TYPE=mysql` 但连不上会直接失败，不会改去打开 SQLite。

SQLite 的启动互斥是数据库文件旁边的本机文件锁。多机互斥仍然用 MySQL `GET_LOCK`。

已改 README、`.env.example`、`start.sh`、`docker-compose.yml`、`deploy/entrypoint.sh`。

核对：

- SQLite 全量 `backend/tests`：当时 199 通过、1 跳过。跳过的是「错误密码不得改走 SQLite」，只在 MySQL 下执行。档案库、标的池、适合度榜都跑了。
- 本机 MySQL 8.0.46 全量：199 通过、1 失败。失败的是首页标的池路由，原因是开盘前新浪最新价和成交额为 0，见下一节。把有效成交额写回后再跑该路由以及档案库、标的池、适合度榜，28 通过。
- SQLite 启动 Flask（`127.0.0.1:5001`，调试关闭）：`/api/health` 200；分析 1825 天返回 `analysisDays=1825`，样本 2021-10-18 至 2026-10-14；回测 1825 天 200，515220 最新价 1.303，档案写入 SQLite。

## 开盘前的 0 价和 0 成交额

新浪在开盘前、收盘后和休市日会把最新价、成交额报成 0。这会把已保存的价格覆盖成 0，也会让「今日成交额 ≥ 门槛」把整个池子滤空。全市场列表没有超时，接口可以一直挂着。

现在的规则：

- 连续竞价（交易日 09:30 至 15:00）里，只拒绝非正价格。
- 这段时间之外，最新价 ≤ 0 或成交额为 0 都视为无效。成交额这一列缺失时，不据此把正常报价判无效。
- 无效行情不覆盖已有的正价格和涨跌幅。库里的价格已经是 0，或全量重建时，改用本地日 K 最后一根收盘、其涨跌幅和成交额，并把该 K 线的日期标在卡片上。
- 全市场新浪请求超时 10 秒。超时或失败时返回已落库的池子，不再继续等。

核对：`test_pool_quote_refresh.py` 中开盘前保留 1.303、空价格回退到 2026-10-14 收盘、0 成交额仍能入库、`requests.get` 的 `timeout` 为 10 且失败时不调用 `save_pool`。`test_market_clock.py` 覆盖开盘前、周末和盘中三种判断。本次在 SQLite 上重跑全量 `backend/tests`：**204 通过，1 跳过**（仍是那条只在 MySQL 下执行的错误密码用例）。

## 在 Mac 上用 SQLite

```bash
git fetch origin cursor/fix-stale-pool-quotes-f138
git checkout cursor/fix-stale-pool-quotes-f138
cp .env.example .env
```

编辑 `.env`，只需要填 Token，数据库保持这两行：

```bash
TUSHARE_TOKEN=你的真实token
DB_TYPE=sqlite
SQLITE_PATH=data/etf_grid.sqlite
```

然后：

```bash
uv sync
cd frontend && npm install && cd ..
chmod +x start.sh
./start.sh
```

浏览器打开 http://localhost:3000 。库文件在项目里的 `data/etf_grid.sqlite`。

只跑后端测试：

```bash
uv run pytest backend/tests/ -v
```

## 改用 MySQL，以及改回 SQLite

先保证本机 MySQL 已启动，账号能够建库。把 `.env` 改成：

```bash
DB_TYPE=mysql
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_USER=你的用户
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=etf_grid
```

再执行：

```bash
./start.sh
```

连不上会直接报错，不会悄悄改用 SQLite 文件。

改回 SQLite 时把数据库相关行换回：

```bash
DB_TYPE=sqlite
SQLITE_PATH=data/etf_grid.sqlite
```

`MYSQL_*` 可以留着，`DB_TYPE=sqlite` 时不会去连它们。然后重新 `./start.sh`。

## Docker

默认也是 SQLite。数据在挂载的 `./data`，容器内路径是 `/app/data/etf_grid.sqlite`。

```bash
docker compose up --build
```

容器里改用 Mac 本机 MySQL 时，在 `.env` 或 compose 环境里设置：

```bash
DB_TYPE=mysql
MYSQL_HOST=host.docker.internal
MYSQL_PORT=3306
MYSQL_USER=你的用户
MYSQL_PASSWORD=你的密码
MYSQL_DATABASE=etf_grid
```

容器里的 `127.0.0.1` 是容器自己，不是 Mac。`MYSQL_HOST` 要用 `host.docker.internal`。

## 使用时要注意

- 已有的 SQLite 文件靠 `CREATE TABLE IF NOT EXISTS` 建表。以后表结构变了，不会自动迁移旧文件。需要新结构时，先停服务，把 `data/etf_grid.sqlite` 移走，再启动让它重建。MySQL 上的 `ALTER` 备注语句在 SQLite 上会跳过。
- SQLite 启动锁是本机文件锁，只防止同一台机器上的两个进程同时做启动同步。多台机器要互斥时用 MySQL 的 `GET_LOCK`。
- 开盘前、收盘后和休市日，新浪仍可能给出 0 价和 0 成交额。程序会忽略它们并显示上一根有效收盘和日期。连续竞价开始后才会用新的最新价覆盖。
- 本地标的不足 20 只时会拉一次全市场行情。这一步现在最多等 10 秒，超时就用已有数据。新浪慢的时候，首页第一次打开仍可能多等这 10 秒。
- 本机调试器默认关闭。需要 Werkzeug 调试器时再设 `FLASK_DEBUG=1`。`start.sh` 监听 `127.0.0.1`，不要对公网暴露。
- `TUSHARE_TOKEN` 必须是至少 16 位的真实 token，应用才能启动。测试收集时如果环境里没有这个变量，会临时用占位值，不会改你的 `.env`。
- 没有交易日历缓存时，休市判断只排除周末。当年交易日历要能访问网络才会更新。
- 回测锚点 ATR 没有窗口前的预热 K 线。频率偏好只缩放默认 ATR 倍数，底仓仍是 50%。
