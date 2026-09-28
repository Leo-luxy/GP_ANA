# v1.5.0 — 文档重构 · 回测修复 · 依赖清理

> 🧹 核心主题：**工程整理**。重构文档体系、修复回测页默认显示问题、清理冗余脚本与依赖。

---

## 🆕 新增

### 技术文档体系
| 文档 | 内容 |
|------|------|
| `Introduction.md` | **技术详解** —— 系统架构、五维决策体系、模块技术档案、数据字典、33 个 API 路由参考、设计演进与已知限制 |
| `README.md` | 重写为面向使用者的**部署与使用主文档** —— 分平台 11 步部署流程、依赖安装、Token 申请、9 条常见问题排查、安全注意事项 |

### 任务状态持久化
- `api/common.py` —— 任务状态写入 `.task_status_cache.json`，服务重启后已完成的任务记录不再丢失

---

## 🐛 Bug 修复

| 问题 | 修复 |
|------|------|
| **回测页默认显示几百天前的过时报告** | 监控报告、回测结果、回测图表的「取最新」逻辑改用**真实日期排序**。原先用字符串降序，`monitor_report_simplified_20260527.md` 会因字母 `s` 大于数字而排在 `monitor_report_20260928.md` 之前 |
| 交易记录日期框硬编码为固定日期 | 改为默认显示当天；添加记录后重置为当天而非清空 |
| `em_financial_collector.py` 遇到 JSON 返回 null 时异常 | 增加空值判断 |
| 依赖清单缺少 Web 框架 | `flask` 补入 `requirements.txt` |

---

## 🧹 清理

| 项目 | 说明 |
|------|------|
| 冗余脚本 | 移除无任何引用的脚本；清理失效的模块设计文档（合并入 `Introduction.md`） |
| 冗余依赖 | 移除 `demjson`、`pandas-datareader`、`yfinance`（代码零引用）。其中 `demjson` 依赖 Python 3.12 已移除的 `imp` 模块，是此前 3.12+ 无法安装依赖的主因 |
| 运行产物 | 选股流水线 CSV、任务状态缓存、Numbers 工作文件移出版本控制并加入 `.gitignore` |

---

## ⚠️ 升级提示

- Python 支持范围明确为 **3.9 ~ 3.12**（`numpy==1.26.3` 不支持 3.13）
- 依赖清单已可直接安装，无需再手动补装 `flask`
- 部署文档已从 `DEPLOYMENT_GUIDE.md` 迁入 `README.md`，该文件不再单独存在

---

# v1.4.0 — 市场选股 · 自选股管理

> 📊 核心主题：**全市场筛选能力 + Web 交互增强**。

---

## 🆕 新增功能

| 模块 | 功能 |
|------|------|
| **市场选股** | `stocks_filter/` 四步流水线：全市场日线 → 基础指标 → 多条件筛选 → 批量趋势回测，输出最终持仓（需 Tushare token） |
| **自选股管理** | `api/watchlist.py` + `watchlist.py`，Web 界面增删查；回测与分析优先使用关注列表 |
| **板块分析增强** | 四大板块类型（大盘/行业/概念/港股）AI 深度分析 |

---

## 🐛 Bug 修复

| 问题 | 修复 |
|------|------|
| 板块分析 KDJ 计算错误 | 弃用 `talib.STOCH` 默认参数（`fastk_period=5`+SMA），改用 A 股标准 9 日 EMA 算法 |
| 板块分析大盘对比数据过时 | 分析前刷新大盘指数数据，并增加时效性检测警告 |
| 指数代码误调成分股 API 导致连接中断 | 指数代码不再调用东方财富行业板块成分股接口 |
| `collect_broad_index_daily` 变量未初始化 | 修复 `NameError` |

---

## 🔧 增强

- 回测报告显示公司简称
- 数据抓取增加超时控制
- 大盘指数采集增加新浪财经主力数据源，东方财富降级为兜底

---

# v1.3.0 — 板块分析 · 数据源增强

> 📊 从 v1.2.0 的 55 个模块扩展到 **58 个模块**。核心主题：**板块维度覆盖 + 数据源可靠性**。

---

## 🆕 新增功能

### 板块分析系统
从个股维度扩展到板块维度，支持四大板块类型的 AI 深度分析：

| 模块 | 功能 |
|------|------|
| `sector_data_collector.py` | **板块数据采集器** — 支持大盘指数 / 行业板块 / 概念板块 / 港股指数，新浪财经主力数据源+东方财富兜底 |
| `analyze_sector.py` | **板块分析引擎** — 技术指标计算 + LLM 分析报告生成，支持 single（单板块深度）和 broad（大盘全景）两种模式 |
| `api/sector.py` | **板块分析 API** — 自包含 Blueprint，数据采集/分析触发/状态轮询/报告获取全流程 |

### Web 界面扩展
- `templates/index.html` — 新增板块分析页面：类型选择（大盘/行业/港股）、板块下拉选择/手动输入、AI 分析按钮、任务进度实时展示、历史报告浏览
- `web_ui.py` — 注册 sector API 蓝图

---

## 🔧 数据源增强

| 改进 | 说明 |
|------|------|
| **新浪财经主力数据源** | 大盘指数采集增加新浪财经作为主力数据源，东方财富降级为兜底方案，提高数据获取成功率 |
| **固定文件名覆盖** | 板块异动和资金流向数据文件使用固定文件名，每次覆盖避免历史文件堆积 |

---

## 🐛 Bug 修复

| 问题 | 修复 |
|------|------|
| `collect_broad_index_daily` 中 `df` 未初始化导致 `NameError` | 修复变量作用域问题，确保异常路径也能正确处理 |
| 板块分析使用过期数据 | 分析前始终重新采集最新数据，解决数据时效性问题 |

---

## 📊 版本对比

| | v1.2.0 | v1.3.0 |
|------|--------|--------|
| 模块总数 | 55 | 58 |
| 分析维度 | 个股五维度 | 个股五维度 + 板块分析 |
| 板块类型 | — | 大盘指数 / 行业 / 概念 / 港股 |
| 数据源 | 东方财富为主 | 新浪财经主力 + 东方财富兜底 |
| API 蓝图 | 6 个 | 7 个（+板块分析） |

---

# v1.2.0 — 架构重构 · 统一 API · 多层决策

> 🏗️ 从 v1.1.0 的 41 个模块扩展到 **55 个模块**。核心主题：**统一化 + 模块化 + 智能决策**。

---

## 🏛️ 架构重构

### 统一数据抓取
- **新增** `eastmoney_fetcher.py` — 统一的东方财富数据抓取入口，支持 `--type` 参数切换数据类型
- **移除** 5 个独立 fetch 脚本：
  - ~~`fetch_stock_market_performance.py`~~
  - ~~`fetch_industry_valuation.py`~~
  - ~~`fetch_industry_peers.py`~~
  - ~~`fetch_industry_growth.py`~~
  - ~~`fetch_dupont_analysis.py`~~

### 统一批量分析
- **新增** `batch_analyze.py` — 统一的批量分析入口，`--mode periodic|daily` 切换模式
- **移除** 3 个独立 batch 脚本：
  - ~~`batch_analyze_all.py`~~
  - ~~`batch_analyze_daily.py`~~
  - ~~`batch_analyze_periodic.py`~~

### 统一数据更新检查
- **重构** `check_data_updates.py` — 合并了原 `check_periodic_data_updates.py` 的功能，`--mode daily|periodic|all`
- **移除** ~~`check_periodic_data_updates.py`~~

### API 模块共享
- **新增** `api/common.py` — 交易所映射、任务队列管理、步骤执行引擎（DRY 原则）
- `api/analysis.py`、`api/detailed.py`、`api/trading.py`、`api/report_viewer.py` 统一引用

---

## 🧠 新增 Process/ 分析引擎

五维度 JSON 摘要 + 两层决策系统，实现从原始数据到交易计划的完整 AI 决策链：

| 模块 | 功能 | 决策权重 |
|------|------|----------|
| `Process/financial_structured_analyzer.py` | 财务数据 → 结构化 JSON 摘要 | 25% |
| `Process/sentiment_valuation_analyzer.py` | 情绪 + 估值分析 → JSON | 15% |
| `Process/shareholder_structure_analyzer.py` | 股东结构分析 → JSON | 10% |
| `Process/research_report_analyzer.py` | 研报观点提取 → JSON | 10% |
| `Process/financial_analysis_enhancer.py` | 财务深度增强 | — |
| `Process/multi_strategy_analyzer.py` | 多策略 LLM 分析（趋势/波段/均值回归） | — |
| `Process/two_layer_decision_analyzer.py` | **两层决策**：冲突检测 + 持仓交易计划 | 技术 40% |

### 两层决策流程
```
第1层：五维度冲突检测与综合研判
  财务(25%) + 情绪估值(15%) + 技术趋势(40%) + 股东结构(10%) + 研报观点(10%)
  ↓
第2层：结合持仓生成具体交易计划（买入/卖出/观望 + 仓位 + 止损位）
```

---

## 🚀 新增功能模块

### API 扩展
| 模块 | 功能 |
|------|------|
| `api/quick_analysis.py` | **快速分析 API** — 仅 K 线 + 技术趋势，支持 short/medium/long 三种策略视角 |
| `api/backtest.py` | **回测 API** — 趋势跟踪策略回测 |
| `api/common.py` | 共享工具模块（交易所映射、任务队列） |

### 数据采集增强
| 模块 | 功能 |
|------|------|
| `batch_margin_collector.py` | 批量融资融券数据采集 |
| `stock_market_data_collector.py` | +融资融券数据抓取函数（SSE + SZSE） |

### 回测系统
| 模块 | 功能 |
|------|------|
| `backtest_all_stocks.py` | 全股票批量回测 |
| `trend_following_backtest.py` | 趋势跟踪策略回测引擎 |

### 技术分析增强
- `daily/data_analysis.py` — 新增 **OBV、ATR、ADX、MFI** 四项技术指标
- `calculate_technical_trend_ds.py` — DeepSeek 驱动的技术趋势分析（替代旧版 `analyze_technical_trend_ds.py`）

### 行业配置
- **新增** `shenwan_config/` — 申万行业阈值配置模块，支持按市值自动选择配置

### Web 界面
- `web_ui.py` — 注册 quick_analysis 和 backtest API 蓝图

---

## 🔧 功能增强

| 模块 | 改进内容 |
|------|---------|
| `daily/quantitative_strategy.py` | **信号去重** — 防止连续重复买卖信号；新增 `actual_buy`/`actual_sell` 列追踪实际执行；新增 `trades` 交易记录 |
| `stock_company_info_collector.py` | **CSV 去重优化** — 智能行 ID 生成；损坏文件自动检测删除；追加/覆盖模式智能切换 |
| `stock_market_data_collector.py` | **融资融券数据** — 完整的 margin data 抓取函数，支持增量更新 |
| `daily/stock_daily_indicator_calculator.py` | 换手率列优先从 qfq 文件读取 |
| `analyze_technical_trend.py` | 支持 `--strategy` 参数切换趋势跟踪/均值回归/波段/中性四种策略视角 |

---

## 🐛 Bug 修复

| 问题 | 修复 |
|------|------|
| `api/analysis.py` 中错误使用 `analyze_performance_forecast.py` 采集数据 | 改为正确的 `important_missing_data_collector.py` |
| Ollama API 参数名错误 (`max_tokens`) | 全部改为 `num_predict`，部分文件令牌上限提升至 8192 |
| 多个分析模块令牌数减半导致输出不完整 | 取消减半，使用完整 max_tokens |

---

## 🔒 安全改进

- `.gitignore` 新增 `config.py` 排除规则
- `config.example.py` 模板更新至 v1.2 配置结构（含 STRATEGY_PROMPTS）
- `trading_records.py` 保持空模板 + gitignore 保护

---

## 📊 版本对比

| | v1.1.0 | v1.2.0 |
|------|--------|--------|
| 模块总数 | 41 | 55 |
| 数据抓取入口 | 5 个独立脚本 | 1 个统一入口 + `--type` |
| 批量分析入口 | 3 个独立脚本 | 1 个统一入口 + `--mode` |
| 分析引擎 | 单层 LLM | 五维度 + 两层决策 |
| API 端点 | 4 个蓝图 | 6 个蓝图（+快速分析、回测） |
| 技术指标 | 12 个 | 16 个（+OBV, ATR, ADX, MFI） |
| 量化策略 | 基础信号 | 信号去重 + 实际执行追踪 |

---

**完整 changelog**: https://github.com/Leo-luxy/GP_ANA/compare/v1.1.0...v1.2.0
