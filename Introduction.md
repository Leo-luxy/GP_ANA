# GP_ANA 技术详解

> **本文档面向开发者与二次开发者**，讲解系统内部架构、算法逻辑、数据结构与设计决策。
>
> - **部署安装、依赖配置、常见问题排查** → 请看 [README.md](README.md)
> - **版本变更记录** → 请看 [CHANGELOG.md](CHANGELOG.md)

---

## 目录

- [1. 系统架构](#1-系统架构)
- [2. 核心数据流](#2-核心数据流)
- [3. 五维决策体系](#3-五维决策体系)
- [4. 数据采集与更新](#4-数据采集与更新)
- [5. 模块技术档案](#5-模块技术档案)
- [6. 数据字典](#6-数据字典)
- [7. API 接口参考](#7-api-接口参考)
- [8. 配置体系](#8-配置体系)
- [9. 技术指标计算](#9-技术指标计算)
- [10. 运维维护](#10-运维维护)
- [11. 设计演进与架构决策](#11-设计演进与架构决策)
- [12. 已知限制与后续方向](#12-已知限制与后续方向)

---

## 1. 系统架构

### 1.1 分层架构

```
┌──────────────────────────────────────────────────────────────────────┐
│  数据采集层  Collectors                                                │
│  行情 / 财务 / 资金流 / 融资融券 / 股东 / 北向 / 行业 / 研报 / 板块       │
│  数据源：akshare · 东方财富 API · 新浪财经 · Tushare                    │
└────────────────────────────┬─────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  分析层  Analyzers                                                     │
│  单维度分析：财务报表 / 资金流 / 融资融券 / 估值 / 股东结构 / 研报 / 技术  │
│  产出：自然语言 MD 报告  +  结构化 JSON 摘要                            │
└────────────────────────────┬─────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  决策层  Process                                                       │
│  · 五维结构化引擎（财务 / 情绪估值 / 股东结构 / 研报 / 技术趋势）          │
│  · multi_strategy_analyzer.py   —— 「技术为主，其他避雷」，三种模式       │
│  · two_layer_decision_analyzer.py —— ①冲突研判 ②持仓交易计划            │
│  · 本地 LLM 推理（Ollama）                                             │
└────────────────────────────┬─────────────────────────────────────────┘
                             ▼
┌──────────────────────────────────────────────────────────────────────┐
│  展示层  Web                                                           │
│  Flask (8081) + 单页前端 + 33 个 REST 路由 + 20+ 种图表                 │
└──────────────────────────────────────────────────────────────────────┘
```

**关键设计**：分析层同时产出「人读的 MD」和「机器读的 JSON」。决策层**只消费 JSON 摘要**，不消费 MD 全文——这是系统最重要的架构决策，原因见 [第 11 章](#11-设计演进与架构决策)。

### 1.2 目录结构

```
GP_ANA/
├── api/                    # Flask 蓝图（10 个模块，33 个路由）
│   ├── analysis.py         # 完整分析
│   ├── quick_analysis.py   # 快速分析（支持 strategy_mode）
│   ├── detailed.py         # 单步功能执行
│   ├── backtest.py         # 策略回测
│   ├── sector.py           # 板块分析
│   ├── stock_selection.py  # 市场选股
│   ├── watchlist.py        # 自选股管理
│   ├── trading.py          # 交易记录
│   ├── report_viewer.py    # 报告查看
│   └── common.py           # 共享：交易所映射 / 任务队列 / 步骤执行器
├── Process/                # 五维分析引擎 + 决策层
├── daily/                  # 日线策略、指标计算、可视化
├── weekly/                 # 周线策略
├── stocks_filter/          # 全市场筛选流水线（4 步，需 Tushare token）
├── shenwan_config/         # 申万行业阈值配置系统
├── templates/              # index.html 单页前端
├── static/                 # 静态资源
├── data/                   # 运行时生成（gitignore）
├── log/                    # 运行时生成（gitignore）
├── config.py               # 本地配置（gitignore，由 example 复制）
├── trading_records.py      # 持仓记录（gitignore，由 example 复制）
├── watchlist.py            # 自选股列表
├── utils.py                # 技术指标计算核心
└── web_ui.py               # Web 服务入口
```

### 1.3 技术栈

| 层次 | 技术 |
|:---|:---|
| 语言 | Python 3.9 ~ 3.12（推荐 3.10 / 3.11） |
| Web 框架 | Flask 3.x |
| 并发模型 | `queue.Queue` + `threading`（异步任务 + 前端轮询） |
| 数据处理 | pandas、numpy |
| 技术指标 | TA-Lib（优先）+ 自实现 fallback |
| 机器学习 | scikit-learn |
| 可视化 | matplotlib、seaborn |
| LLM | Ollama 本地推理（默认 `http://localhost:11434`） |
| 数据源 | akshare、东方财富数据中心 API、新浪财经、Tushare |

---

## 2. 核心数据流

### 2.1 三条主流程

| 流程 | 触发方式 | 数据范围 | 耗时 | 产出 |
|:---|:---|:---|:---|:---|
| **完整分析** | `/api/analyze`, `task_type=init` | 全量采集 + 五维 + 两层决策 | 3–5 分钟 | `{ticker}_final_decision_{ts}.md` |
| **快速分析** | `/api/quick_analyze`, `task_type=daily` | 仅技术面 | ~30 秒 | `{ticker}_{mode}_strategy_analysis_{date}.md` |
| **批量分析** | `batch_analyze.py --mode all\|daily\|periodic` | 按 mode 决定 | 视股票数而定 | 各维度报告 |

### 2.2 完整分析流程（init）

```
1. 数据采集
   ├─ data_collector.py                     → {ticker}_qfq.csv
   ├─ stock_market_data_collector.py        → fund_flow / margin_data / valuation
   ├─ stock_company_info_collector.py       → company_basic / research_reports / 财报
   ├─ financial_indicators_collector.py     → financial_indicators.json
   ├─ em_financial_collector.py             → dupont / growth_ratio
   ├─ shareholders_collector.py             → historical_shareholders
   ├─ shareholder_num_collector.py          → shareholder_num
   └─ north_holdings.py / org_hold_collector.py

2. 技术指标计算
   └─ utils.py / calculate_technical_trend_ds.py → technical_trend_analysis.json

3. 五维结构化分析（Process/）
   ├─ financial_structured_analyzer.py      → financial_summary.json
   ├─ sentiment_valuation_analyzer.py       → sentiment_valuation.json
   ├─ shareholder_structure_analyzer.py     → shareholder_structure.json
   └─ research_report_analyzer.py           → research_report_analysis.json

4. 两层决策 LLM
   ├─ 第一层：五维冲突检测与综合研判
   └─ 第二层：结合持仓 → 生成交易计划
   → {ticker}_final_decision_{ts}.md
```

### 2.3 快速分析流程（daily）

只做技术面，跳过全部基本面采集，因此能在 30 秒内出结果：

```
K 线数据 → 技术指标计算 → calculate_technical_trend_ds.py
        → multi_strategy_analyzer.py（按 strategy_mode 选权重）
        → LLM 分析 → {ticker}_{mode}_strategy_analysis_{date}.md
```

### 2.4 首次初始化执行顺序

`check_data_updates.py` 已封装了推荐的执行顺序，一般无需手工逐步执行：

```bash
# 日更数据（行情/资金流/融资融券/估值/技术指标）
python check_data_updates.py --mode daily --ticker 300433.SZ

# 低频数据（公司信息/财报/股东/北向）
python check_data_updates.py --mode periodic --ticker 300433.SZ

# 批量分项分析
python batch_analyze.py --mode daily --ticker 300433.SZ     # 日更维度
python batch_analyze.py --mode periodic --ticker 300433.SZ  # 低频维度
python batch_analyze.py --mode all --ticker 300433.SZ       # 全部 14 步
```

---

## 3. 五维决策体系

### 3.1 维度与权重

| 维度 | 权重 | 产出 JSON | 生成模块 |
|:---|--:|:---|:---|
| 技术趋势 | **40%** | `_technical_trend_analysis.json` | `calculate_technical_trend_ds.py` |
| 财务 | 25% | `_financial_summary.json` | `Process/financial_structured_analyzer.py` |
| 情绪估值 | 15% | `_sentiment_valuation.json` | `Process/sentiment_valuation_analyzer.py` |
| 股东结构 | 10% | `_shareholder_structure.json` | `Process/shareholder_structure_analyzer.py` |
| 研报观点 | 10% | `_research_report_analysis.json` | `Process/research_report_analyzer.py` |

> 这是**默认（中性）权重**。使用 `multi_strategy_analyzer.py` 时，权重会随交易模式变化，见 3.4。

### 3.2 结构化 JSON 摘要的作用

每个维度的分析脚本都被要求**在输出自然语言报告的同时，输出一份标准化 JSON 摘要**。其结构约定包含：

| 字段 | 含义 |
|:---|:---|
| `core_verdict.signal` | 核心倾向：`BULLISH` / `NEUTRAL` / `BEARISH` |
| `core_verdict.confidence` | 信心度（0–1） |
| `core_verdict.summary` | 一句话结论 |
| `key_metrics` | 关键量化指标 |
| `major_anomalies` | 异常项列表（供决策层避雷） |
| `suggested_action` | 建议动作：`BUY` / `HOLD` / `WAIT` / `SELL` |
| `risk_tags` | 风险标签 |

这套结构让决策层能**只读取结论与异常**，而不必吞下数万字的报告全文。

### 3.3 多策略分析器：技术为主，其他避雷

`Process/multi_strategy_analyzer.py` 采用分层决策逻辑：

```
┌─────────────────────────────────────────────────────────────┐
│              主要决策层（技术面）                              │
│      80%（短期）/ 60%（中期）/ 20%（长期）                     │
│   趋势判断 · 超买超卖 · 支撑阻力 · 量价配合                     │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│              风险过滤层（其他维度，用于「避雷」）               │
│   · 财务估值风险：PE / PB / PEG / ROE / 负债率 / 现金流        │
│   · 情绪资金流风险：主力连续流出 / 融资余额异动                 │
│   · 股东结构风险：股权集中 / 机构参与度低                       │
└─────────────────────────────────────────────────────────────┘
```

**核心思想**：技术面决定「买不买、什么时候买」，其他维度**只拥有一票否决权**（避雷），不主动产生买入信号。

**技术面提取内容**（源自 `_technical_trend_analysis.json`）：

- 交易信号 `BUY`/`HOLD`/`SELL` + 信心度
- 多时间周期趋势（日线 / 周线）
- 指标一致性评分
- 超买超卖判断：
  - 超买：`RSI > 75` 或 `CCI > 150` 或 `BB_pctB > 1.0`
  - 超卖：`RSI < 25` 或 `CCI < -150` 或 `BB_pctB < 0`
- 关键技术指标（MACD、ATR 等）与关键价位（布林带支撑/阻力、MA20）

### 3.4 三种交易模式与风险阈值

| 模式 | 名称 | 时间框架 | 技术面 | 财务 | 股东 | 情绪 |
|:---|:---|:---|--:|--:|--:|--:|
| `short` | 短期交易 | < 1 个月 | **80%** | 0% | 0% | 20% |
| `medium` | 中期持仓 | 1–6 个月 | **60%** | 30% | 10% | 0% |
| `long` | 长期投资 | > 6 个月 | **20%** | 50% | 30% | 0% |

**财务风险阈值（避雷触发线）：**

| 指标 | short | medium | long |
|:---|--:|--:|--:|
| PE(TTM) | > 150 | > 100 | > 80 |
| PB | > 10 | > 10 | > 10 |
| PEG | > 2.0 | > 2.5 | > 2.0 |
| ROE | < 8% | < 8% | < 8% |
| 净利率 | < 5% | < 5% | < 5% |
| 资产负债率 | > 80% | > 70% | > 60% |
| 经营现金流 | 可为负 | **必须为正** | **必须为正** |
| 净利润增长率 | < −20% | < −20% | < −20% |

**利好加分项**：营收增长 > 20%、净利润增长 > 20%、ROE > 15%、PEG < 1.5。

**风险等级判定：**

| 风险分数 | 等级 | 决策影响 |
|:---|:---|:---|
| 0 – 1 | `LOW` | 不干预技术面信号 |
| 2 – 4 | `MEDIUM` | 与技术面冲突时降级为 HOLD |
| ≥ 5 | `HIGH` | 强制 SELL / 观望 |

### 3.5 程序化决策逻辑

```python
IF 技术信号 == BUY AND 信心度 >= 0.7 AND 风险等级 == LOW:
    → BUY   (信心度 = min(tech_conf, 0.8))

ELIF 技术信号 in [BUY, HOLD] AND 短期超买:
    → HOLD  (信心度 0.7)

ELIF 技术信号 == SELL OR 风险等级 == HIGH:
    → SELL  (信心度 = max(tech_conf, 0.6))

ELIF (技术看多 AND 风险分数 >= 2) OR (技术看空 AND 情绪看多):
    → HOLD  (信心度 0.5)      # 信号冲突，不操作

ELSE:
    → 以技术面信号为主
```

### 3.6 两层决策机制

`Process/two_layer_decision_analyzer.py` 把「判断」和「行动」拆成两步：

| 层次 | 输入 | 角色设定 | 输出 |
|:---|:---|:---|:---|
| **第一层** | 五维结构化摘要（**只传相互矛盾的部分**） | 对冲基金风险经理 | 《多维冲突分析报告》+《关键监控指标》 |
| **第二层** | 第一层结论 + **真实持仓成本与盈亏** | 交易教练 | 具体交易计划（止损 / 补仓 / 持有） |

**第二层的硬约束**：禁止给出模糊建议，必须输出「如果……就……」的情景计划树。例如：

> 如果股价无法在 3 个交易日内站稳 27.6 元（前期筹码密集区），则必须减仓至半仓。

最终产出 `{ticker}_final_decision_{ts}.md`。

> 💡 这套两层的设计动机源自真实的失败经验，详见 [第 11 章](#11-设计演进与架构决策)。

---

## 4. 数据采集与更新

### 4.1 采集器设计规范

所有采集脚本遵循统一约定（`基本要求.md` 的工程化落地）：

| 规范 | 内容 |
|:---|:---|
| **CLI 约定** | 默认提供 `--ticker {code}` 参数；不指定时依次处理 `config.py` 中 `STOCK_TICKERS` 的全部股票 |
| **存储路径** | 统一为 `data/{code}/{code}_*.csv` |
| **目录自建** | 抓取前检查股票目录是否存在，不存在则创建 |
| **增量抓取** | 存在数据文件则取最新日期继续；不存在则从起始日期抓取 |
| **跳过规则** | 最新日期 == 当前日期 → 不抓；最新日期 == 昨日的 15:00 前 → 不抓；最新日期 == 昨日的 15:00 后 → 抓当日 |
| **异常隔离** | 每个数据获取步骤独立 `try/except`，单步失败不影响整体 |
| **随机延迟** | 请求间加随机延迟防限流（区间见 5 章开头） |
| **日期处理** | 统一解析并升序排序；JSON 落盘用 `DateEncoder` 序列化日期对象 |

### 4.2 数据源总览

| 数据源 | 用途 | 是否需密钥 | 实测补充 |
|:---|:---|:---:|:---|
| **akshare** | 行情、财务、资金流、融资融券、股东户数、申万行业 | ❌ 免费 | 主力数据源 |
| **东方财富数据中心** | 杜邦分析、增长率、股东明细、机构持股、北向资金 | ❌ 免费 | 报表名如 `RPT_F10_EH_HOLDERS` |
| **新浪财经** | 历史行情、复权数据、大盘指数 | ❌ 免费 | 板块数据主源 |
| **Tushare** | 全市场日线、基础指标（仅市场选股用） | ✅ **需 token** | 需 120 积分以上 |
| **东方财富行情接口** | 板块/行业成分股 | ❌ 免费 | 指数代码不走成分股 API |

### 4.3 数据更新频率

**原始数据（抓取）：**

| 数据类型 | 文件 | 频率 | 采集程序 |
|:---|:---|:---|:---|
| 前复权行情 | `_qfq.csv` | 每日 | `data_collector.py` |
| 资金流 | `_fund_flow.csv` | 每日 | `stock_market_data_collector.py` |
| 融资融券 | `_margin_data.csv` | 每日 | `stock_market_data_collector.py` |
| 估值 | `_valuation.csv` | 每日 | `stock_market_data_collector.py` |
| 公司基本信息 | `_company_basic.json` | 季度 | `stock_company_info_collector.py` |
| 研究报告 | `_research_reports.csv` | 季度 | `stock_company_info_collector.py` |
| 主要股东 | `_main_shareholders.csv` | 季度 | `stock_company_info_collector.py` |
| 利润表 / 资产负债表 | `_financial_profit.csv` / `_financial_balance.csv` | 季度 | `stock_company_info_collector.py` |
| 北向资金持股 | `_north_holdings.csv` | 季度 | `stock_company_info_collector.py` |
| 财务指标 | `_financial_indicators.json` | 季度 | `financial_indicators_collector.py` |
| 机构持股 | `_shareholder.csv` | 季度 | `shareholders_collector.py` |
| 股东户数 | `_shareholder_num.csv` | 月度 | `shareholder_num_collector.py` |
| 杜邦 / 增长率 | `_dupont_data.csv` / `_growth_ratio_data.csv` | 季度 | `em_financial_collector.py` |

**衍生数据（计算）：**

| 数据 | 文件 | 频率 | 生成程序 |
|:---|:---|:---|:---|
| 技术指标 | `_indicators.csv` | 每日 | `daily/batch_analysis.py` |
| 技术趋势 | `_technical_trend_analysis.json` | 每日 | `calculate_technical_trend_ds.py` |
| 交易信号 | `_trading_signals.csv` | 每日 | `daily/batch_analysis.py` |
| 趋势通道信号 | `_trend_channel_signals.csv` | 每日 | `daily/trend_channel_analyzer.py` |
| 各类分析报告 | `_*_analysis_*.md` | 按需 | 各 `analyze_*.py` |
| 综合/最终决策 | `_final_decision_*.md` | 按需 | `Process/two_layer_decision_analyzer.py` |

**数据更新时点：**

- **日更数据**：交易日 **16:00 之后**（A 股 15:00 收盘，数据约 16:00 更新完成）
- **季度数据**：季度结束后 **1–2 个月**（等待财报发布）
- **节假日**：休市期间无新数据

### 4.4 数据更新检查机制

`check_data_updates.py` 是统一入口，支持三种模式：

```bash
python check_data_updates.py --mode daily    --ticker 300433.SZ  # 日更数据
python check_data_updates.py --mode periodic --ticker 300433.SZ  # 低频数据
python check_data_updates.py --mode all      --ticker 300433.SZ  # 全部
```

**被检查的日更文件与对应更新命令：**

| 文件 | 检查逻辑 | 更新命令 |
|:---|:---|:---|
| `_qfq.csv` | 最后日期是否最新 | `data_collector.py` |
| `_fund_flow.csv` | 同上 | `stock_market_data_collector.py` |
| `_margin_data.csv` | 同上 | `stock_market_data_collector.py` |
| `_valuation.csv` | 同上 | `stock_market_data_collector.py` |
| `_indicators.csv` | 同上 | `daily/batch_analysis.py` |
| `_shareholder_num.csv` | 同上 | `shareholder_num_collector.py` |

**日期判定逻辑（关键实现）**：

1. 兼容多种日期格式：`YYYY-MM-DD`、`YYYYMMDD`、`numpy.int64`
2. 兼容多种时间列名：`date`、`日期`、`数据日期`
3. 最新判定：最后日期 == 当前日期 → 最新；最后日期 == 昨日 **且当前时间在 16:00 之前** → 也视为最新
4. 通过 `subprocess` 调用对应采集脚本完成更新

**核心函数**：`is_latest_date()`、`get_last_date()`、`check_file_up_to_date()`、`run_command()`、`check_stock_data()`

---

## 5. 模块技术档案

> **通用约定（各模块不再重复）**
> - **批次遍历**：所有采集/分析脚本均为「单票」入口，`--ticker` 指定单只股票；不带参数时从 `config.py` 的 `STOCK_TICKERS` 读取全量股票列表，逐只循环处理。
> - **输出根目录**：数据统一写入 `config.py` 导入的 `DATA_DIR` 下 `{ticker}/` 子目录；`{ticker}` 形如 `300433.SZ`、`002384.SZ`、`600519.SH`。
> - **异常隔离**：所有脚本对每个数据获取/分析步骤单独 `try/except`，单个步骤失败不影响整体流程继续。
> - **随机延迟**：所有网络采集脚本在请求之间加随机延迟防限流。各模块区间不同：`data_collector.py`、`stock_company_info_collector.py`、`financial_indicators_collector.py`、`em_financial_collector.py`、`shareholders_collector.py`、`org_hold_collector.py` 为 **2–4 秒**；`stock_market_data_collector.py`、`shareholder_num_collector.py`、`north_holdings.py` 为 **1–4 秒**。
> - **增量更新**：本地已有数据时只取新数据并追加/合并，按唯一键去重。
> - **日期处理**：统一解析日期字段并按时间升序排序；JSON 输出使用自定义 `DateEncoder` 类序列化日期对象。
> - **分析类脚本共用骨架**：数据加载 → 数据提取/预处理 → 构建 Ollama AI 提示词 → 调用本地 Ollama 深度分析 → 保存「提示词 + 分析结果」，并在报告中做数据文件存在性检查与时效性警告。

### 5.1 data_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 抓取 A 股实时行情、个股历史行情（含前/后复权）、CDR 个股历史行情与分钟级行情 |
| **数据源** | 新浪财经 `finance.sina.com.cn`、`vip.stock.finance.sina.com.cn`、`quotes.sina.cn`；akshare 常量 `zh_sina_a_stock_url` 等 |
| **输入** | 无（直接走网络） |
| **输出** | `{ticker}_qfq.csv` |
| **调用** | `python data_collector.py --ticker 600519.SH` |

- 分钟级行情支持 **1 / 5 / 15 / 30 / 60 分钟** 五种周期，覆盖个股与股票指数。
- 前复权与后复权数据均可获取；最终落盘仅前复权历史行情。
- 落盘前做按日期排序 + 自动去重。
- 关键函数：`_get_zh_a_page_count`、`stock_zh_a_spot`、`stock_zh_a_daily`、`stock_zh_a_cdr_daily`、`stock_zh_a_minute`、`main`。

### 5.2 stock_market_data_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集个股估值、资金流、融资融券三类市场数据 |
| **数据源** | akshare：`ak.stock_value_em`、`ak.stock_a_pe`、`ak.stock_individual_fund_flow`、`ak.stock_margin_detail_sse`、`ak.stock_margin_detail_szse` |
| **输入** | 无 |
| **输出** | `{ticker}_valuation.csv`、`{ticker}_fund_flow.csv`、`{ticker}_margin_data.csv` |
| **调用** | `python stock_market_data_collector.py --ticker 300433.SZ` |

- **估值数据双路回退**：先试 `stock_value_em`，失败再试 `stock_a_pe`。
- **融资融券跳过周末**：按日期拉取时跳过周末日期以提升效率。
- 三个函数各自独立支持增量更新：`get_stock_valuation_data`、`get_stock_fund_flow_data`、`get_stock_margin_data`。

### 5.3 stock_company_info_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集公司基本信息、股票规模对比、主营业务、研究报告、利润表/资产负债表、财务摘要 |
| **数据源** | akshare：`stock_individual_basic_info_xq`、`stock_zh_scale_comparison_em`、`stock_zyjs_ths`、`stock_research_report_em`、`stock_financial_report_sina`、`stock_financial_abstract`、`stock_zh_a_spot_em`；东方财富 API（基本信息备用源） |
| **输入** | 无 |
| **输出** | `{ticker}_company_basic.json`、`_research_reports.csv`、`_financial_profit.csv`、`_financial_balance.csv`、`_north_holdings.csv` |
| **调用** | `python stock_company_info_collector.py --ticker 300433.SZ` |

- **基本信息字段集（21 项）**：公司简称、公司全称、成立日期、上市日期、注册资本、员工人数、经营范围、主营业务、地址、电话、邮箱、网站、实际控制人、高管人数、实际发行数量、发行价格、实际募集资金净额、发行后市盈率、网上发行成功率、所属行业、公司介绍。
- **规模对比额外包含**：总市值/流通市值/营业收入/净利润及其**各自排名**。
- **研究报告字段**：东财评级、机构、近一月研报数、2025/2026/2027 年盈利预测（收益 + 市盈率）、报告 PDF 链接。
- **多源获取基本信息**：同一字段尝试多种方法获取以提升成功率。
- `DateEncoder` 处理 JSON 日期序列化；`load_existing_data` 加载现有 JSON；`save_to_csv` 增量保存 + 去重。

### 5.4 em_financial_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 抓取东方财富杜邦分析、增长率、主要财务指标三类财务数据 |
| **数据源** | 东方财富网 `datacenter.eastmoney.com/securities/api/data` |
| **输入** | 本地已有 CSV（用于增量合并） |
| **输出** | `{ticker}_dupont_data.csv`、`_growth_ratio_data.csv`、`_main_financial_data.csv` |
| **调用** | `python em_financial_collector.py --ticker 300433.SZ [--type dupont\|growth\|main]` |

- **面向对象实现**：核心类 `EastmoneyFinancialCollector`。
- **按季度差动态定抓取量**：`_get_quarter_difference` 计算本地最新报告日与当前的季度差，`_get_latest_report_date` 取本地最新报告日期，据此决定请求条数，而非固定窗口。
- **合并去重规则**：`_merge_data` 按日期 + 类型去重，冲突时保留最新；`_save_data` 按报告日期排序落盘。
- **网络重试**：`_make_request` 内置失败重试。
- 支持按类型单取：`fetch_dupont_data` / `fetch_growth_ratio_data` / `fetch_main_financial_data` / `fetch_all_data`。

### 5.5 financial_indicators_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集现金流量表、利润表及指标、资产负债表及指标、成长指标、财务分析指标 |
| **数据源** | akshare：`stock_financial_report_sina`、`stock_financial_analysis_indicator`、`stock_financial_abstract` |
| **输入** | 无 |
| **输出** | `{ticker}_financial_indicators.json` |
| **调用** | `python financial_indicators_collector.py --ticker 300433.SZ` |

- **内置指标计算**：毛利率 `(营业收入 − 营业成本) / 营业收入 × 100`；净利率 `净利润 / 营业收入 × 100`；资产负债率 `负债合计 / 资产总计 × 100`；流动比率 `流动资产合计 / 流动负债合计`。
- **成长指标**基于利润表计算，含营收与净利润同比增长率，并主动处理**时间维度一致性**问题。
- **窗口截断**：三张报表均只保留**最近 12 组**数据。
- **多源回退**：财务分析指标获取失败时改取财务摘要数据。
- 关键函数 `get_stock_financial_indicators`，JSON 落盘用 `DateEncoder`。

### 5.6 shenwan_industry_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集申万一级/二级/三级行业信息、三级行业成分股、个股所属行业及行业平均数据 |
| **数据源** | akshare：`sw_index_first_info`、`sw_index_second_info`、`sw_index_third_info`、`sw_index_third_cons` |
| **输入** | `{ticker}_company_basic.json` |
| **输出** | `data/shenwan_industry/shenwan_industry_level{1,2,3}.csv`、`..._level3_{industry_code}_stocks.csv`、`{ticker}_industry_info.json` |
| **调用** | `python shenwan_industry_collector.py --ticker 002384.SZ` |

- 行业信息统一字段：行业代码、行业名称、上级行业、成份个数、静态市盈率、TTM 市盈率、市净率、静态股息率。
- 成分股字段：股票代码、股票简称、纳入时间、市值、市盈率、市净率、股息率、营收增长率、净利润增长率。
- `calculate_industry_average` 计算成分股平均市值/市盈率/市净率/股息率/增长率，**带单位（亿元、%、元）并保留 3 位小数**。
- **时间戳规则**：**17:00 之前记为前一天，17:00 之后记为当天**。
- `{industry_code}` 形如 `850822.SI`；落盘目录自动创建。

### 5.7 shareholders_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集历史前十大股东（机构持股）明细，按季度更新 |
| **数据源** | 东方财富数据中心，报表名 `RPT_F10_EH_HOLDERS` |
| **输入** | 本地已有 CSV |
| **输出** | `{ticker}_historical_shareholders.csv` |
| **调用** | `python shareholders_collector.py --ticker 002384.SZ [--start-date 2024-01-01 --end-date 2025-09-30]` |

- **字段**：`HOLDER_NAME`、`HOLDER_RANK`、`HOLD_NUM`、`HOLD_RATIO`、`CHANGE_NUM`、`CHANGE_RATIO`、`END_DATE`。
- **去重键**：`HOLDER_NAME + END_DATE`。
- **日期智能处理**：`get_latest_quarter_end` 自动计算最新季度末并**考虑数据发布延迟**；`get_next_quarter` 推算下一季度；`get_last_end_date` 取本地最后日期用于增量。
- `fetch_shareholders_data` 自动翻页，保证取全。

### 5.8 shareholder_num_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集股东户数、户均持股、持股集中度等筹码数据 |
| **数据源** | 东方财富数据中心，报表名 `RPT_F10_EH_HOLDERNUM`；备用 akshare `ak.stock_zh_a_gdhs_detail_em` |
| **输入** | 本地已有 CSV |
| **输出** | `{ticker}_shareholder_num.csv`（东财源）、`{ticker}_shareholder_num_info.csv`（akshare 源） |
| **调用** | `python shareholder_num_collector.py --ticker 300433.SZ` |

- **东财字段**：`HOLDER_TOTAL_NUM`、`TOTAL_NUM_RATIO`、`AVG_FREE_SHARES`、`AVG_FREESHARES_RATIO`、`HOLD_FOCUS`、`PRICE`、`AVG_HOLD_AMT`、`HOLD_RATIO_TOTAL`、`FREEHOLD_RATIO_TOTAL`。
- **akshare 字段**：股东户数统计截止日、股东户数、户均持股、户均持股市值、持股集中度。
- **去重键**：日期字段。
- `should_fetch_data` 依据本地最后日期与当前时间判断是否需要抓取（避免无谓请求）。
- **两个数据源各存一个文件**，不混合；保存前按日期升序排序。

### 5.9 north_holdings.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集北向资金（陆股通）个股持股数据 |
| **数据源** | 东方财富数据中心，报表名 `RPT_MUTUAL_STOCK_HOLDRANKN_NEW` |
| **输入** | 本地已有 CSV |
| **输出** | `{ticker}_north_holdings.csv` |
| **调用** | `python north_holdings.py --ticker 300433.SZ [--interval-type 001]` |

- **字段**：`TRADE_DATE`、`HOLD_SHARES`、`TOTAL_SHARES_RATIO`、`HOLD_MARKET_CAP`。
- **去重键**：`TRADE_DATE`。
- 股票代码与数据周期（`--interval-type`）均可命令行指定。
- `should_fetch_data` + `get_last_date_from_file` 实现抓取必要性判断；`fetch_north_holdings` 自动翻页取全。

### 5.10 org_hold_collector.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 采集机构持股明细（按机构类型、报告期） |
| **数据源** | 东方财富数据中心，报表名 `RPT_MAIN_ORGHOLDDETAIL` |
| **输入** | 本地已有 CSV |
| **输出** | `{ticker}_institutional_holdings.csv` |
| **调用** | `python org_hold_collector.py --ticker 002594.SZ [--report-date 2025-12-31] [--org-type 01]` |

- **字段**：`ORG_TYPE`、`REPORT_DATE`、`HOLDER_CODE`、`HOLDER_NAME`、`TOTAL_SHARES`、`HOLD_VALUE`、`TOTALSHARES_RATIO`、`FREESHARES_RATIO`、`FREE_MARKET_CAP`、`FREE_SHARES`、`FUND_CODE`、`NETVALUE_RATIO`。
- **去重键**：`HOLDER_CODE + REPORT_DATE`。
- 报告日期、机构类型可参数化指定；`fetch_org_hold_detail` 自动翻页。

### 5.11 analyze_financial_statements.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 财务报表 LLM 深度分析 |
| **输入** | `_company_basic.json`、`_financial_profit.csv`、`_financial_balance.csv`、`_financial_indicators_calculated.json` |
| **输出** | `{ticker}_financial_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_financial_statements.py --ticker 300433.SZ` |

- **分析维度**：盈利能力（毛利率/净利率/营业利润率/EPS/营收与净利润同比）、运营能力（总资产/应收账款/存货/固定资产周转率）、偿债能力（资产负债率/流动比率/速动比率/利息保障倍数）、现金流（经营/投资/筹资净额、经营现金流÷净利润、经营现金流÷营收）、成长能力（同比与单季环比）、历史趋势、行业对比。
- **数据标准化**：金额统一以**亿元**为单位并明确标注；比率加 `%`；每项计算指标标注明对应时间点。
- 7 步固定流水线：加载 3 类数据 → 提取财报数据 → 构建提示词 → 取 AI 结果 → 保存提示词与结果。

### 5.12 analyze_fund_flow.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 资金流向 LLM 分析 |
| **输入** | `_company_basic.json`、`_fund_flow.csv`、`_qfq.csv`、`_valuation.csv` |
| **输出** | `{ticker}_fund_flow_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_fund_flow.py --ticker 300433.SZ` |

- **预处理计算**：累计主力净流入、主力净流入率标准差（`std`）；取最近 **10 日**交易数据计算涨跌幅与振幅。
- **单位统一为万元**，比率加 `%`，标注明数据时间。
- **排序一致性**：资金流与价格数据均按日期升序排列，消除顺序歧义。
- **指标口径明确**：明确写出日均净流入率的计算公式，保证跨报告一致性。
- **自建情绪指标**：散户接盘指数，用于量化市场情绪状态。
- **数据质量提示**：显式提示成交额与换手率可能基于不同股本口径。
- 分析维度：资金流趋势（连续流入/流出/反转判定）、资金结构（四类单量相关性、主力与散户一致性）、短期走势、投资建议与触发条件、风险（最大仓位建议）、策略时间刻度（超短线 1–3 天 / 短线 5–10 天 / 波段，含止盈止损参考）。

### 5.13 analyze_margin_data.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 融资融券 LLM 分析 |
| **输入** | `_margin_data.csv`、`_company_basic.json`、`_qfq.csv`、`_valuation.csv` |
| **输出** | `{ticker}_margin_data_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_margin_data.py --ticker 300433.SZ` |

- **派生量计算（预处理核心）**：由原始字段推算**融资偿还额**与**融券偿还量**，补齐资金流动数据。
- 取最近 **20 日**交易数据计算涨跌幅与振幅。
- **单位约定**：资金统一为**万元**，股数统一为**股**；数据按日期升序排列。
- **相关性分析**：融资余额变化与股价涨跌幅的相关性、**前一日融资买入额占比与当日涨跌幅**的相关性。
- **市场活跃度比率**：融资融券余额÷流通市值、融资买入额÷成交额、换手率趋势。
- 风险视角涵盖杠杆踩踏风险与估值回归风险。

### 5.14 analyze_em_financial.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 东方财富财务数据 LLM 分析（杜邦 + 增长率 + 主要指标 + 规模排名） |
| **输入** | `_dupont_data.csv`、`_growth_ratio_data.csv`、`_main_financial_data.csv`、`_company_basic.json`、`_financial_indicators.json` |
| **输出** | `{ticker}_eastmoney_financial_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_em_financial.py --ticker 300433.SZ` |

- **输入语义**：杜邦含 ROE、销售净利率、资产周转率、权益乘数；增长率含营收/净利润/总资产的同比与环比。
- **同比/环比双口径**：对毛利率、净利率、资产负债率、流动比率、营收增长率、净利润增长率均计算同比与环比变化。
- **现金流增强**：输出最近**四个季度**现金流原始数据，并计算经营现金流÷营收。
- **规模排名**：总市值、流通市值、营业收入、净利润各自带排名。

### 5.15 analyze_peer_comparison.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 同行/行业比较 LLM 分析 |
| **输入** | `_company_basic.json`、`_financial_indicators_calculated.json`、`_industry_peers.json`、`_market_performance.json`、`_dupont_analysis.json`、`_industry_valuation.json`、`_industry_growth.json` |
| **输出** | `{ticker}_peer_comparison_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_peer_comparison.py --ticker 300433.SZ` |

- **7 路输入语义**：`_industry_peers.json` 含同行业公司净利润/市值/营收及排名；`_market_performance.json` 为历史日度市场表现；`_dupont_analysis.json` 含 ROE 行业排名与行业平均；`_industry_valuation.json` 含 PE/PE_TTM/PB/PEG 及排名；`_industry_growth.json` 含营收与净利润同比、3 年复合增长率及排名。
- **对比口径三件套**：每类排名都与**行业平均**和**中值**对比，并列出**行业前 5 名**明细。
- **时效性警告**：报告内显式插入数据滞后风险警告。
- **日期直用数据源格式**：不做时间格式转换，避免转换错误导致程序在未来时间失效。

> 上述 `_industry_peers.json`、`_market_performance.json`、`_dupont_analysis.json`、`_industry_valuation.json`、`_industry_growth.json` 由统一获取器 `eastmoney_fetcher.py` 产出。
> `--type market_performance|industry_valuation|industry_peers|industry_growth|dupont`

### 5.16 analyze_shareholder_structure.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 股东/持股结构 LLM 分析 |
| **输入** | `_company_basic.json`、`_historical_shareholders.csv`、`_institutional_holdings.csv`、`_shareholder_num.csv`、`_north_holdings.csv` |
| **输出** | `{ticker}_shareholder_structure_analysis_{ts}.md` + 提示词文件 |
| **调用** | `python analyze_shareholder_structure.py --ticker 300433.SZ` |

- **量化指标（自算）**：**HHI 指数**（前十大股东持股集中度）、股权集中度。
- 分析维度：实际控制人影响力、大股东稳定性与减持风险、机构数量与类型分布、机构持仓集中度与头部机构特征、散户化程度、北向资金增减持趋势、市值/营收/净利润行业排名。
- 流程 8 步：加载 4 类数据 → 提取并计算量化指标 → 构建提示词 → 请求 AI → 保存结果。

### 5.17 calculate_financial_indicators.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 从财务指标 JSON 读取原始报表数据，计算五大类量化财务指标并单独落盘 |
| **数据源** | 无（纯本地计算） |
| **输入** | `{ticker}_financial_indicators.json` |
| **输出** | `{ticker}_financial_indicators_calculated.json` |
| **调用** | `python calculate_financial_indicators.py --ticker 300433.SZ` |

**完整指标公式表：**

| 类别 | 指标 | 公式 |
|:---|:---|:---|
| 盈利能力 | 毛利率 | `(营业收入 − 营业成本) / 营业收入 × 100%` |
| | 净利率 | `净利润 / 营业收入 × 100%` |
| | 营业利润率 | `营业利润 / 营业收入 × 100%` |
| | EBITDA | `营业利润 + \|财务费用\|` ⚠️ **近似算法，缺折旧摊销数据** |
| | 营收/净利润同比 | `(当期 − 去年同期) / 去年同期 × 100%` |
| 偿债能力 | 资产负债率 | `负债合计 / 资产总计 × 100%` |
| | 流动比率 | `流动资产合计 / 流动负债合计` |
| | 速动比率 | `(流动资产合计 − 存货) / 流动负债合计` |
| | 利息保障倍数 | `营业利润 / \|财务费用\|` |
| 运营能力 | 总资产周转率 | `营业收入 / 资产总计` |
| | 应收账款周转率 | `营业收入 / 应收票据及应收账款` |
| | 存货周转率 | `营业成本 / 存货` |
| | 固定资产周转率 | `营业收入 / 固定资产及清理合计` |
| 现金流 | 经营现金流÷净利润 | 直接取数后相除 |
| | 经营现金流÷营业收入 | `× 100%` |
| 成长能力 | 营收/净利润单季环比 | 单季数据环比 |
| | 总资产同比 | `(当期资产总计 − 去年同期) / 去年同期 × 100%` |

- **数据溯源（`used_data`）**：每个指标都记录其计算所用的原始字段与报告日，便于核验。
- **计算前置校验**：仅当某指标所需数据齐全时才计算，缺数据即跳过。
- **日期语义**：`_extract_date_info` 提取报告日的年与月，`_get_same_month_data` 据此定位去年同期。
- **格式化**：全部计算结果保留**两位小数**。

### 5.18 stock_ai_comprehensive_analyzer.py

| 项目 | 内容 |
|:---|:---|
| **作用** | 汇总全部单维度分析报告与技术面数据，生成一次性综合 LLM 分析报告 |
| **输入** | `_indicators.csv`、`_company_basic.json`、`_valuation.csv`、各类 `_*_analysis_*.md`、`_technical_trend_analysis.json` |
| **输出** | `{ticker}_comprehensive_analysis_{ts}.md` + 提示词文件 + 支撑位/阻力位图表 |
| **调用** | `python stock_ai_comprehensive_analyzer.py --ticker 300433.SZ` |

- **技术面计算**：基于 `_indicators.csv` 计算**支撑位与阻力位**并绘图。
- **外部实时增强**：用 akshare 获取实时股票信息以提高时效性。
- **个性化持仓分析**：从交易记录反算持仓情况与浮动盈亏，使建议与个人仓位绑定。
- **报告聚合**：把技术面、基本面、市场情绪三类报告的核心内容合并进同一提示词。
- 9 步流程：加载历史行情 → 算支撑/阻力 → 绘图 → 加载基本信息与估值 → 加载各分析报告 → 由交易记录算持仓 → 生成综合提示词 → 取 AI 结果 → 保存结果与提示词。

---

## 6. 数据字典

> `{ts}` = 时间戳；`{industry_code}` 形如 `850822.SI`。

### 6.1 原始数据（采集产出）

| 文件名模式 | 所属模块 | 数据内容 | 关键字段 |
|:---|:---|:---|:---|
| `{ticker}_qfq.csv` | `data_collector.py` | 前复权历史行情 | 日期、开盘价、最高价、最低价、收盘价、成交量、成交额、换手率 |
| `{ticker}_valuation.csv` | `stock_market_data_collector.py` | 估值数据 | 市盈率、PE(TTM)、PE(静)、市净率、PEG、市现率、市销率、总市值、流通市值 |
| `{ticker}_fund_flow.csv` | `stock_market_data_collector.py` | 个股资金流 | 主力净流入、超大单净流入、大单净流入、中单净流入、小单净流入 |
| `{ticker}_margin_data.csv` | `stock_market_data_collector.py` | 融资融券 | 融资买入额、融资余额、融券卖出量、融券余量、融券余额、融资融券余额 |
| `{ticker}_company_basic.json` | `stock_company_info_collector.py` | 公司基本信息 + 规模对比 | 21 项基本信息（见 5.3）；总市值/流通市值/营收/净利润及各排名 |
| `{ticker}_research_reports.csv` | `stock_company_info_collector.py` | 研究报告 | 报告名称、东财评级、机构、近一月研报数、三年盈利预测（收益+市盈率）、PDF 链接 |
| `{ticker}_financial_profit.csv` | `stock_company_info_collector.py` | 利润表 | 营业总收入、营业收入、营业成本、研发/销售/管理/财务费用、投资收益、营业利润、利润总额、净利润 |
| `{ticker}_financial_balance.csv` | `stock_company_info_collector.py` | 资产负债表 | 资产总计、负债总计、所有者权益合计、流动/非流动资产合计、流动/非流动负债合计 |
| `{ticker}_dupont_data.csv` | `em_financial_collector.py` | 杜邦分析 | ROE、销售净利率、资产周转率、权益乘数 |
| `{ticker}_growth_ratio_data.csv` | `em_financial_collector.py` | 增长率 | 营业收入/净利润/总资产的同比与环比增长率 |
| `{ticker}_main_financial_data.csv` | `em_financial_collector.py` | 主要财务指标 | EPS、BPS、ROE、资产负债率 |
| `{ticker}_financial_indicators.json` | `financial_indicators_collector.py` | 三大报表 + 成长指标 | 结构：`profit_indicators.profit_table[]`、`debt_indicators.balance_table[]`、`cash_flow[]` |
| `{ticker}_historical_shareholders.csv` | `shareholders_collector.py` | 前十大股东明细（季度） | `HOLDER_NAME`、`HOLDER_RANK`、`HOLD_NUM`、`HOLD_RATIO`、`CHANGE_NUM`、`CHANGE_RATIO`、`END_DATE`、股本性质 |
| `{ticker}_shareholder_num.csv` | `shareholder_num_collector.py` | 股东户数（东财源） | `HOLDER_TOTAL_NUM`、`TOTAL_NUM_RATIO`、`AVG_FREE_SHARES`、`HOLD_FOCUS`、`AVG_HOLD_AMT`、`FREEHOLD_RATIO_TOTAL` |
| `{ticker}_shareholder_num_info.csv` | `shareholder_num_collector.py` | 股东户数（akshare 源） | 统计截止日、股东户数、户均持股、户均持股市值、持股集中度 |
| `{ticker}_institutional_holdings.csv` | `org_hold_collector.py` | 机构持股明细 | `ORG_TYPE`、`REPORT_DATE`、`HOLDER_CODE`、`HOLDER_NAME`、`TOTAL_SHARES`、`HOLD_VALUE`、`TOTALSHARES_RATIO`、`FREESHARES_RATIO`、`FREE_MARKET_CAP`、`NETVALUE_RATIO` |
| `{ticker}_north_holdings.csv` | `north_holdings.py` / `stock_company_info_collector.py` | 北向资金持股 | `TRADE_DATE`、`HOLD_SHARES`、`TOTAL_SHARES_RATIO`、`HOLD_MARKET_CAP` |
| `{ticker}_industry_info.json` | `shenwan_industry_collector.py` | 个股行业信息 + 行业平均 | 行业平均含市值/市盈率/市净率/股息率/增长率（带单位，3 位小数） |
| `shenwan_industry_level{1,2,3}.csv` | `shenwan_industry_collector.py` | 申万各级行业信息 | 行业代码、行业名称、上级行业、成份个数、静态市盈率、TTM 市盈率、市净率、静态股息率 |
| `shenwan_industry_level3_{industry_code}_stocks.csv` | `shenwan_industry_collector.py` | 三级行业成分股 | 股票代码、简称、纳入时间、市值、市盈率、市净率、股息率、营收增长率、净利润增长率 |

### 6.2 衍生数据（计算与决策产出）

| 文件名模式 | 所属模块 | 数据内容 | 关键字段 |
|:---|:---|:---|:---|
| `{ticker}_indicators.csv` | `daily/batch_analysis.py` | 技术指标 | 收盘/开盘/最高/最低、成交量 + MACD、KDJ、RSI 等 |
| `{ticker}_technical_trend_analysis.json` | `calculate_technical_trend_ds.py` | 技术趋势结构化分析 | 交易信号、信心度、多周期趋势、指标一致性、超买超卖、关键价位 |
| `{ticker}_financial_indicators_calculated.json` | `calculate_financial_indicators.py` | 五大类计算后指标 + 溯源 | `calculated_indicators`（盈利/偿债/运营/现金流/成长）、`used_data`（每个指标的原始字段与报告日） |
| `{ticker}_financial_summary.json` | `Process/financial_structured_analyzer.py` | 财务结构化摘要 | 五维决策输入之一 |
| `{ticker}_sentiment_valuation.json` | `Process/sentiment_valuation_analyzer.py` | 情绪+估值结构化摘要 | 五维决策输入之一 |
| `{ticker}_shareholder_structure.json` | `Process/shareholder_structure_analyzer.py` | 股东结构结构化摘要 | 五维决策输入之一 |
| `{ticker}_research_report_analysis.json` | `Process/research_report_analyzer.py` | 研报结构化摘要 | 五维决策输入之一 |
| `{ticker}_financial_analysis_{ts}.md` | `analyze_financial_statements.py` | 财务报表分析报告 | — |
| `{ticker}_fund_flow_analysis_{ts}.md` | `analyze_fund_flow.py` | 资金流分析报告 | — |
| `{ticker}_margin_data_analysis_{ts}.md` | `analyze_margin_data.py` | 融资融券分析报告 | — |
| `{ticker}_valuation_analysis_{ts}.md` | `analyze_valuation_data.py` | 估值分析报告 | — |
| `{ticker}_eastmoney_financial_analysis_{ts}.md` | `analyze_em_financial.py` | 东方财富财务分析报告 | — |
| `{ticker}_peer_comparison_analysis_{ts}.md` | `analyze_peer_comparison.py` | 同行对比分析报告 | — |
| `{ticker}_shareholder_structure_analysis_{ts}.md` | `analyze_shareholder_structure.py` | 股东结构分析报告 | — |
| `{ticker}_research_reports_analysis_{ts}.md` | `analyze_research_reports.py` | 研报分析报告 | — |
| `{ticker}_performance_analysis_{ts}.md` | `analyze_performance_forecast.py` | 业绩预测分析报告 | — |
| `{ticker}_comprehensive_analysis_{ts}.md` | `stock_ai_comprehensive_analyzer.py` | 综合 AI 分析报告 | — |
| `{ticker}_{mode}_strategy_analysis_{date}.md` | `Process/multi_strategy_analyzer.py` | 多策略分析报告（`mode` = short/medium/long） | — |
| `{ticker}_final_decision_{ts}.md` | `Process/two_layer_decision_analyzer.py` | **最终交易决策**（两层决策产出） | — |
| 各类 `_*_prompt_*` / `_prompt_info_*` | 各分析脚本 | 写入 AI 的提示词内容（用于调试与复现） | — |

> ⚠️ **已废弃**：`{ticker}_north_fund.csv`（原由 `north_fund_collector.py` 产出的北向资金逐日数据）。该采集脚本已移除，北向资金数据统一由 `north_holdings.py` 提供。

---

## 7. API 接口参考

### 7.1 路由总表

以下为**实际注册的全部 33 个路由**（从源码自动提取）。

**完整分析（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/analyze` | 启动完整分析任务（全量采集 + 五维 + 两层决策） |
| `GET` | `/api/task_status/<task_id>` | 查询分析任务进度 |
| `GET` | `/api/reports/<stock_code>` | 列出该股票的全部分析报告 |
| `GET` | `/api/report/<path:report_path>` | 读取指定报告内容 |
| `GET` | `/api/latest_report/<stock_code>` | 读取最新报告 |

**快速分析（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/quick_analyze` | 启动快速分析（仅技术面，支持 `strategy_mode`） |
| `GET` | `/api/quick_task_status/<task_id>` | 查询快速分析进度 |
| `GET` | `/api/quick_report/<stock_code>` | 读取快速分析报告 |

**单步功能执行（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/detailed_function` | 执行单个数据抓取/分析步骤 |
| `POST` | `/api/execute_single_function` | 执行指定脚本并返回输出 |

**策略回测（`/api/backtest`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/backtest/run_backtest` | 启动回测任务 |
| `GET` | `/api/backtest/task_status/<task_id>` | 查询回测进度 |
| `GET` | `/api/backtest/get_stock_list` | 获取可选股票列表 |
| `GET` | `/api/backtest/get_report` | 获取回测报告 |
| `GET` | `/api/backtest/get_chart/<path:chart_path>` | 获取回测图表 |
| `GET` | `/api/backtest/get_backtest_results` | 获取回测结果汇总 |

**板块分析（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/sector_collect` | 触发板块数据采集 |
| `POST` | `/api/sector_analyze` | 触发板块分析 |
| `GET` | `/api/sector_task_status/<task_id>` | 查询板块任务进度 |
| `GET` | `/api/sector_list` | 获取可分析板块列表 |
| `GET` | `/api/sector_report/<task_id>` | 获取指定板块报告 |
| `GET` | `/api/sector_reports` | 列出全部板块报告 |
| `GET` | `/api/sector_report_content/<path:report_name>` | 读取板块报告内容 |

**市场选股（`/api`，需 Tushare token）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/stock_selection/run` | 启动全市场选股任务 |
| `GET` | `/api/stock_selection/task_status/<task_id>` | 查询选股进度 |
| `GET` | `/api/stock_selection/get_result` | 获取选股结果 |

**自选股管理（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/watchlist/get` | 获取关注列表 |
| `POST` | `/api/watchlist/add` | 添加关注股票 |
| `POST` | `/api/watchlist/remove` | 移除关注股票 |

**交易记录（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/trading_records/<stock_code>` | 查询指定股票的交易记录 |
| `POST` | `/api/add_trading_record` | 新增买卖记录 |

**报告查看（`/api`）**

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/stocks` | 获取已有数据的股票列表 |
| `GET` | `/api/stock_reports/<stock_code>` | 获取该股票的报告列表 |

### 7.2 异步任务模式

所有耗时操作（分析、回测、板块、选股）均为**异步任务**：

```
客户端 POST 触发  →  服务端返回 task_id  →  客户端轮询状态接口  →  完成后拉取结果
```

- 实现方式：`queue.Queue` + `threading`
- 状态存储：`task_status` dict，key 为 `task_id`
- 典型流程（以快速分析为例）：

```python
import requests

# 1. 触发任务
resp = requests.post('http://localhost:8081/api/quick_analyze', json={
    'stock_code': '688981',
    'task_type': 'daily',
    'strategy_mode': 'short'        # short / medium / long
})
task_id = resp.json()['task_id']

# 2. 轮询状态
status = requests.get(f'http://localhost:8081/api/quick_task_status/{task_id}').json()

# 3. 拉取报告
report = requests.get('http://localhost:8081/api/quick_report/688981').json()
```

### 7.3 `strategy_mode` 参数

`/api/quick_analyze` 支持三种策略模式，映射到 `multi_strategy_analyzer.py` 的权重配置：

| 取值 | 含义 | 权重配置 |
|:---|:---|:---|
| `short` | 短期交易（默认） | 技术 80% + 情绪 20% |
| `medium` | 中期持仓 | 技术 60% + 财务 30% + 股东 10% |
| `long` | 长期投资 | 财务 50% + 股东 30% + 技术 20% |

- 非法取值会被拒绝并返回错误
- 生成的报告文件名格式：`{ticker}_{mode}_strategy_analysis_{date}.md`
- 报告获取接口**同时兼容旧的 `final_decision` 格式**

---

## 8. 配置体系

### 8.1 `config.py` 结构

| 配置块 | 作用 |
|:---|:---|
| `STOCK_TICKERS` | 要分析的股票列表（dict：名称 → 代码） |
| `TRADING_RECORDS` | 持仓记录（也可从 `trading_records.py` 导入） |
| `HISTORY_DATE_RANGE` | 指定股票的历史数据区间 |
| `AI_CONFIG` | Ollama 地址、模型名、temperature、max_tokens、fallback_models |
| `STRATEGY_PROMPTS` | 四种策略视角的提示词模板 |
| `TECHNICAL_INDICATORS` | 技术指标周期参数 |
| `STRATEGY_CONFIG` / `WEEKLY_STRATEGY_CONFIG` | 回测参数（初始资金、买卖阈值） |
| `OPTIMIZATION_CONFIG` / `WEEKLY_OPTIMIZATION_CONFIG` | 参数优化网格范围 |
| `DATA_DIR` | 数据目录（由 `PROJECT_ROOT` 自动推导，无需手改） |

> `DATA_DIR` 用 `os.path.dirname(os.path.abspath(__file__))` 推导，因此**项目可整体移动位置**而不必修改配置。

### 8.2 申万阈值配置系统

`shenwan_config/` 提供了一套**预设阈值系统**，用于判断研报、股东、情绪、财务各项指标的「好/坏」分界。

**6 套预设配置：**

| 配置名 | 适用范围 | 特点 |
|:---|:---|:---|
| `LARGE_CAP` | 市值 > 1000 亿 | 大盘蓝筹，研报多，标准更严 |
| `MID_CAP` | 市值 100–1000 亿 | 中盘成长，标准适中 |
| `SMALL_CAP` | 市值 < 100 亿 | 小盘股，研报少，标准更宽松 |
| `CONSERVATIVE` | 全部 | 保守风格，要求更高 |
| `BALANCED` | 全部 | 平衡风格（**推荐日常使用**） |
| `AGGRESSIVE` | 全部 | 激进风格，更宽容 |

**用法（无需自己填数字）：**

```python
# 方式一：按市值自动选择（推荐）
from shenwan_config.thresholds_config import get_config_by_market_cap
config = get_config_by_market_cap(1500)   # 单位：亿元 → 选中 LARGE_CAP

# 方式二：按风格选择
from shenwan_config.thresholds_config import get_config_by_style
config = get_config_by_style('conservative')

# 查看全部配置指南
# 在项目根目录执行：
# python shenwan_config/thresholds_config.py
```

**阈值分组示例：**

| 分组 | 代表阈值 | 含义 |
|:---|:---|:---|
| 研报 | `overweight_strong=90` | 买入+增持评级占比 ≥90% → 机构一致看好 |
| | `sell_alert=30` | 减持+卖出占比 ≥30% → 机构一致看空 |
| | `coverage_high=20` | 近 3 月研报 ≥20 篇 → 机构高度关注 |
| 股东 | `top1_dominant=50` | 第一大股东持股 ≥50% → 一股独大 |
| | `inst_hold_high=15` | 机构持仓 ≥15% → 机构持仓较高 |
| 情绪 | `main_flow=5` | 主力净流入占比 ≥5% → 显著流入 |
| | `margin_change=10` | 融资余额变化 ≥10% → 资金活跃 |
| 财务 | `roe_excellent=15` | ROE > 15% → 盈利能力优秀 |
| | `debt_ratio_alert=70` | 资产负债率 > 70% → 杠杆偏高 |

**不同配置的差异举例：**

| 阈值项 | LARGE_CAP | SMALL_CAP | 说明 |
|:---|:---|:---|:---|
| 研报高度关注 | 30 篇 | 10 篇 | 大盘股要求研报更多 |
| 增长强劲 | 20% | 40% | 小盘股预期增长更高 |
| 机构持仓较高 | 15% | 10% | 小盘股机构参与少 |

> 个股所属行业由 `shenwan_industry_collector.py` 采集，见 5.6。

### 8.3 策略提示词

`config.py` 的 `STRATEGY_PROMPTS` 定义四种交易视角的提示词模板：

| 策略 | 核心思想 |
|:---|:---|
| `trend_following` | 只在有明显趋势时交易，不预测顶底，不参与震荡；参考 ADX 与均线排列 |
| `mean_reversion` | 在极端位置反向交易；参考 RSI/CCI/布林带 %B，必须设严格止损 |
| `swing` | 持仓数天至数周，捕捉日线级波段；要求日线与周线共振 |
| `neutral` | 不预设偏好，综合多空信号给出客观判断 |

---

## 9. 技术指标计算

### 9.1 指标清单

`utils.py` 的 `calculate_technical_indicators()` 计算以下指标：

| 类别 | 指标 |
|:---|:---|
| **均线** | `MA5`、`MA10`、`MA20`、`MA50`、`MA60`、`MA120`、`MA200` |
| **KDJ** | `K`、`D`、`J` |
| **MACD** | `DIF`、`DEA`、`MACD_hist`、`MACD_hist_change` |
| **布林带** | `BB_upper`、`BB_middle`、`BB_lower`、`BB_std`、`BB_width`、`BB_pctB` |
| **RSI** | `RSI`、`RSI_6`、`RSI_24` |
| **动量** | `CCI`、`ROC`、`ROC_6`、`MTM`、`PSY`、`WR`、`WR_6` |
| **趋势** | `DMA`、`TRIX`、`ADX`、`SAR` |
| **量能** | `OBV`、`VR`、`MFI`、`VWAP` |
| **偏离** | `BIAS5`、`BIAS10`、`BIAS20` |
| **波动** | `ATR` |

### 9.2 TA-Lib 优先 + 自实现 fallback

```python
try:
    import talib
    HAS_TALIB = True
except ImportError:
    HAS_TALIB = False
```

- **优先使用 TA-Lib**（C 实现，速度快、经过充分验证）
- **未安装时自动 fallback** 到纯 pandas/numpy 自实现版本
- 因此 **TA-Lib 属于强烈推荐但非硬性依赖**——不过缺少它时计算速度会明显下降

### 9.3 KDJ 标准算法（重要历史教训）

⚠️ **不要使用 `talib.STOCH` 计算 KDJ。**

`talib.STOCH(high, low, close)` 的默认参数是 `fastk_period=5` + SMA 平滑，而 **A 股标准 KDJ 应为 `fastk_period=9` + EMA 平滑**：

```
RSV = (收盘价 − 9日最低价) / (9日最高价 − 9日最低价) × 100
K   = 2/3 × 前K + 1/3 × RSV
D   = 2/3 × 前D + 1/3 × K
J   = 3K − 2D
```

**教训**：`analyze_sector.py` 和 `utils.py` 曾因误用 `talib.STOCH` 导致 J 值算成 **119.30**，而正确值是 **98.36**——足以让超买超卖判断完全失效。

> **通用原则**：涉及技术指标时，务必注意 TA-Lib 默认参数与 A 股常用标准参数的差异。

### 9.4 指标参数

技术指标的周期参数集中在 `config.py` 的 `TECHNICAL_INDICATORS` 中：

```python
TECHNICAL_INDICATORS = {
    'lookback': 3,                      # 滞后特征天数
    'ma_periods': [5, 10, 20, 50, 60],  # 均线周期
    'vol_periods': [5, 10],             # 成交量均线周期
    'rsi_period': 14,
    'macd_fast': 12, 'macd_slow': 26, 'macd_signal': 9,
    'bb_period': 20, 'bb_std': 2,
    'kdj_period': 9,                    # 标准 9 日
    'cci_period': 14, 'roc_period': 12, 'wr_period': 14,
    'dma_short': 10, 'dma_long': 50,
}
```

---

## 10. 运维维护

### 10.1 后台常驻运行

```bash
# nohup 方式
nohup python web_ui.py > log/web_ui.log 2>&1 &

# tmux 方式（便于查看输出）
tmux new -s gpana
python web_ui.py      # Ctrl+B 再按 D 脱离；tmux attach -t gpana 重新进入
```

> ⚠️ **长期运行前请先修改 `web_ui.py`**：当前默认 `debug=True` + `host='0.0.0.0'`，
> 生产环境应改为 `app.run(host='127.0.0.1', port=8081, debug=False)`。

### 10.2 Ollama 服务常驻

```bash
ollama list                    # 检查是否运行
ollama serve                   # 未运行时启动
brew services start ollama     # macOS 常驻
```

### 10.3 数据备份

核心资产是 `data/`、`config.py`、`trading_records.py`：

```bash
tar -czf gpana_backup_$(date +%Y%m%d).tar.gz data/ config.py trading_records.py watchlist.py
```

### 10.4 日志与空间清理

```bash
rm -rf log/*.log      # 清理日志
du -sh data/          # 查看数据目录占用
```

> 💡 `data/` 会持续增长——每次分析都生成带时间戳的新报告。建议定期清理旧报告。

### 10.5 端口占用排查

```bash
lsof -i :8081                    # macOS / Linux
netstat -ano | findstr :8081     # Windows
```

端口被占用时编辑 `web_ui.py` 最后一行的 `port` 值。

### 10.6 批量任务

```bash
python batch_analyze.py --mode all      --ticker 300433.SZ   # 全部 14 步
python batch_analyze.py --mode daily    --ticker 300433.SZ   # 日更 6 步
python batch_analyze.py --mode periodic --ticker 300433.SZ   # 低频 3 步
```

不带 `--ticker` 时处理 `config.py` 中的全部股票。

---

## 11. 设计演进与架构决策

本章记录系统为何是现在这个样子——这些决策来自真实踩坑，理解它们有助于正确扩展系统。

### 11.1 从「全文拼凑」到「结构化摘要」

**早期设计**：各分项分析脚本生成自然语言报告，主程序把**所有报告全文拼接**成一份数万字的提示词，交给 LLM 做一次性综合分析。

**暴露的问题：**

| 问题 | 具体表现 |
|:---|:---|
| **Lost-in-the-Middle** | LLM 对长文本中间部分关注度下降，关键风险提示被忽略 |
| **推理深度下降** | 海量数据让 LLM 退化成「摘要器」而非「推理器」，倾向笼统总结 |
| **信息冗余与矛盾未剔除** | 财报分析给「增持」、资金流与估值给「减持」——冲突点被淹没，最终输出骑墙结论 |
| **上下文窗口浪费** | 塞入大量原始数值（如 OBV 的具体值），占用推理空间却几乎无帮助 |
| **噪音数据** | 拿不到真实数据的模块用模拟数据计算，引入错误信息 |

**结论**：看似「分而治之」，实则是「分步制造大量冗余噪音，最后强行单步处理」。

### 11.2 现行方案：两层推理 + 结构化中间层

针对上述问题，系统重构为：

```
各分项脚本 → 同时输出「自然语言 MD」+「结构化 JSON 摘要」
                        ↓
        第一层：只把【相互矛盾的摘要】送进 LLM
               角色：对冲基金风险经理
               产出：冲突分析报告 + 关键监控指标
                        ↓
        第二层：把【冲突结论 + 真实持仓盈亏】送进 LLM
               角色：交易教练
               约束：禁止模糊建议，必须给情景计划树
               产出：具体交易计划（止损/补仓/持有）
```

**两个关键改进：**

1. **引入中间层「结构化摘要」替代「全文报告」** —— LLM 在小粒度上做决策，而非吞全文
2. **引入「冲突处理」替代「单纯汇总」** —— 专门针对矛盾点做深度分析，而不是把矛盾混在一起

### 11.3 持仓感知的决策

系统中**真实持仓成本会被回溯计算并注入第二层提示词**。

**设计理由**：对已经亏损 27% 的仓位，盲目止损和盲目加仓可能都是错的。AI 必须基于**具体的盈亏状态**与压力/支撑位，给出可执行的微操计划，而不是空谈基本面。

### 11.4 板块分析的时效性修复

**Bug**：`api/sector.py` 的 `analyze_single` 只刷新板块自身数据，不刷新大盘 `sh000001` 数据，导致 `compare_sector_vs_broad_market()` 的 `intersection()` 对齐到旧数据（对齐到 6/05 而非 6/15）。

**修复**：分析前增加 `sector_data_collector.py --type broad_index --code sh000001` 刷新大盘；同时在 `compare_sector_vs_broad_market()` 中加入时效性检测警告。

**教训**：做数据对齐时，**必须校验参与对齐的各路数据都是最新的**，否则会静默产生错误结论。

### 11.5 回测入离场的对称设计

监控回测的入离场规则遵循**对称双信号**原则：

| 方向 | 触发条件 |
|:---|:---|
| **入场** | 趋势确认：多头结构 + 量能 + ADX + MACD |
| **离场** | 趋势结束：跌破 10 日低点 / MA 死叉 + MACD<0 |

**配套规则：**

1. **保护性止损全部保留**：时间止损 / 峰值回撤 / ATR 止损 / 移动止盈 / 分仓止盈
2. **离场冷却**：触发离场后 **3 个交易日内不再入场**；超过 3 天后若趋势确认仍成立则允许进场
3. **显示规则**：买入当天显示「可入场」，次日起显示「持有」（除非触发卖出/回撤警示）

**实现要点**：入场条件 = `trend_confirmed==1` 且空仓 且 `i - last_exit_idx >= reentry_cooldown_days+1`（参数 `reentry_cooldown_days: 3`）。

> ⚠️ `trend_following_backtest_simplified.py` 与 `trend_following_backtest.py`（以及 `backtest_all_stocks*.py` 两版）**必须同步修改**，否则行为不一致。

**背景**：曾出现 `001258` 在峰值回撤离场后，监控连续多天提示「可入场」、永不转为「持有」，自相矛盾（刚卖出又提示买入）。

### 11.6 数值口径统一

分析脚本普遍遵循以下约定，避免 LLM 误读：

| 约定 | 说明 |
|:---|:---|
| 金额单位 | 统一为**亿元**（部分模块为**万元**）并显式标注 |
| 股数单位 | 统一为**股** |
| 比率 | 统一加 `%` 符号 |
| 时间标注 | 每个指标标明对应的时间点 |
| 数据排序 | 统一按日期升序，消除顺序歧义 |

---

## 12. 已知限制与后续方向

### 12.1 已知限制

| 限制 | 说明 |
|:---|:---|
| **EBITDA 为近似值** | `calculate_financial_indicators.py` 用 `营业利润 + \|财务费用\|` 近似，缺少折旧摊销数据 |
| **成交额与换手率口径可能不一致** | 不同数据源的股本口径不同，`analyze_fund_flow.py` 会在报告中显式提示 |
| **股东结构维度覆盖不全** | 尚未纳入股权质押、股东类型结构、股东行为等数据 |
| **部分数据源无真实数据时会退化为模拟值** | 需警惕由此引入的噪音（历史上业绩预告分析曾出现此问题） |
| **依赖公开财经接口** | 接口变更或限流会影响数据抓取，需注意 akshare 版本升级 |
| **`data/` 无限增长** | 每次分析生成带时间戳文件，需定期手动清理 |
| **Web 默认 debug 模式** | 上线前必须手动改为 `debug=False` |
| **硬编码端口** | `8081` 写死在 `web_ui.py`，不支持命令行覆盖 |

### 12.2 可选的改进方向

| 方向 | 说明 |
|:---|:---|
| **数据文件配置化** | 把 `check_data_updates.py` 中的文件清单移到配置文件，便于扩展 |
| **并行处理多股票** | 当前为串行循环，可引入并发提升批量效率 |
| **更新失败监控预警** | 数据抓取失败时主动告警，而非静默跳过 |
| **统一数据质量检查** | 在分析前增加字段完整性与异常值校验 |
| **依赖注入解耦** | `config.py` 全局导入较多，可改为显式注入以便测试 |
| **支持云端 LLM** | `get_ai_analysis()` 可扩展支持 OpenAI / DeepSeek 等（当前仅 Ollama） |

---

## 相关文档

| 文档 | 说明 |
|:---|:---|
| [README.md](README.md) | **部署安装与使用主文档**（11 步流程 + Token 申请 + FAQ） |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全政策 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 |

---

## ⚖️ 免责声明

本文档描述的系统为**技术学习与研究工具**，所有 AI 分析结果、交易建议、回测数据**均不构成任何投资建议**。股市有风险，投资需谨慎。
