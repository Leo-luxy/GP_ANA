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
