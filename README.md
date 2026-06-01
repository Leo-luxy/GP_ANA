# GP_ANA — A 股 AI 综合分析系统

> 🧠 **GP_ANA** 是一个面向 A 股市场的全流程智能分析平台。系统从 20+ 数据源自动采集行情、财务、资金流、融资融券、股东结构、行业对比等多维数据，通过 **本地 Ollama 大模型或第三方 API（如 OpenAI / DeepSeek / 通义千问等）** 驱动 AI 分析引擎，生成从基本面到技术面的完整分析报告与交易决策建议。同时内置量化策略回测系统和 Flask Web 可视化界面，形成 **数据采集 → 多维分析 → AI 决策 → 策略回测 → 可视交互** 的完整闭环。
>
> **适用场景**：个人量化研究、A 股投资决策辅助、策略回测验证。
>
> **AI 模型支持**：
> - 🖥️ **本地部署**：Ollama（默认），数据不出本机，隐私安全
> - ☁️ **第三方 API**：兼容 OpenAI / DeepSeek / 通义千问等任意 OpenAI 兼容接口，灵活扩展

**当前版本：v1.2.0**

---

## 🎯 核心能力

| 能力 | 说明 |
|------|------|
| 📡 **数据采集** | 20+ 采集器，覆盖行情、财务、资金流、融资融券、股东、行业、研报等 |
| 📊 **多维分析** | 财务质量、资金流向、融资融券、估值水平、技术趋势、股东结构、同行对比、研报观点 — 八大维度 |
| 🧠 **AI 决策** | 五维度 JSON 摘要 + 两层决策引擎（冲突检测 → 交易计划），3 种策略模式（趋势跟踪/波段/均值回归） |
| 📈 **策略回测** | 趋势跟踪回测系统，含信号去重、实际执行追踪、多股票批量回测 |
| 🌐 **Web 界面** | Flask Web UI（localhost:8081），完整分析 / 快速分析 / 回测 / 交易记录管理，一站式操作 |
| 🔧 **统一入口** | `eastmoney_fetcher.py` 统一数据抓取，`batch_analyze.py --mode` 统一批量分析 |

---

## 程序分类

### 1. 数据抓取类

| 程序名称 | 功能 | 数据源 | 输出物 |
|---------|------|--------|--------|
| `data_collector.py` | 历史行情数据（前复权） | akshare | `{ticker}_qfq.csv` |
| `stock_market_data_collector.py` | 资金流、融资融券、估值数据 | akshare | `{ticker}_fund_flow.csv` / `_margin_data.csv` / `_valuation.csv` |
| `stock_company_info_collector.py` | 公司基本信息、研报、股东、财务报表 | akshare | `{ticker}_company_basic.json` / `_research_reports.csv` 等 |
| `eastmoney_fetcher.py` ⭐ | **统一东方财富数据抓取入口** (`--type market_performance\|industry_valuation\|industry_peers\|industry_growth\|dupont`) | 东方财富 API | 各类行业/市场数据 |
| `financial_indicators_collector.py` | 财务指标、成长指标、现金流指标 | akshare | `{ticker}_financial_indicators.json` |
| `shareholders_collector.py` | 前十大股东历史数据 | 东方财富 API | `{ticker}_historical_shareholders.csv` |
| `shareholder_num_collector.py` | 股东户数、户均持股 | 东方财富 API | `{ticker}_shareholder_num.csv` |
| `north_holdings.py` | 北向资金持股 | 东方财富 API | `{ticker}_north_holdings.csv` |
| `org_hold_collector.py` | 机构持仓明细 | 东方财富 API | `{ticker}_institutional_holdings.csv` |
| `em_financial_collector.py` | 东方财富财务数据 | 东方财富 API | `{ticker}_dupont_data.csv` / `_growth_ratio_data.csv` |
| `important_missing_data_collector.py` | 业绩预告与分红数据 | 多数据源 | `{ticker}_performance_forecast.csv` / `_ex_dividend.csv` |
| `shenwan_industry_collector.py` | 申万行业分类 | 东方财富 API | `{ticker}_industry_info.json` |
| `batch_margin_collector.py` ⭐ | 批量融资融券数据采集 | akshare | 多股票 `_margin_data.csv` |
| `index_data_collector.py` | 指数数据采集 | akshare | 指数数据文件 |

### 2. 数据分析类

| 程序名称 | 功能 | 输出物 |
|---------|------|--------|
| `analyze_financial_statements.py` | 财务报表 AI 分析 | `{ticker}_financial_analysis_{timestamp}.md` |
| `analyze_fund_flow.py` | 资金流 AI 分析 | `{ticker}_fund_flow_analysis_{timestamp}.md` |
| `analyze_margin_data.py` | 融资融券 AI 分析 | `{ticker}_margin_data_analysis_{timestamp}.md` |
| `analyze_research_reports.py` | 研究报告 AI 分析 | `{ticker}_research_reports_analysis_{timestamp}.md` |
| `analyze_shareholder_structure.py` | 股东结构 AI 分析 | `{ticker}_shareholder_structure_analysis_{timestamp}.md` |
| `analyze_valuation_data.py` | 估值 AI 分析 | `{ticker}_valuation_analysis_{timestamp}.md` |
| `analyze_technical_trend.py` | 技术趋势 AI 分析（支持 `--strategy` 切换策略视角） | `{ticker}_technical_trend_analysis.json` |
| `analyze_em_financial.py` | 东方财富财务 AI 分析 | 财务分析报告 |
| `analyze_performance_forecast.py` | 业绩预测 AI 分析 | 业绩预测分析报告 |
| `analyze_peer_comparison.py` | 同行对比 AI 分析 | 同行对比分析报告 |
| `calculate_financial_indicators.py` | 综合财务指标计算（盈利能力/偿债能力/运营能力/现金流/成长能力） | `{ticker}_financial_indicators_calculated.json` |
| `calculate_technical_trend_ds.py` ⭐ | DeepSeek 技术趋势分析 | 技术趋势分析数据 |
| `daily/data_analysis.py` | 数据质量检查 + 可视化（16 项指标含 OBV/ATR/ADX/MFI） | 价格/成交量/布林带/相关性图表 |
| `daily/technical_analysis.py` | 技术指标信号分析与有效性评估 | 信号分析图表 |
| `daily/quantitative_strategy.py` | 量化策略回测（含信号去重） | 策略回测图表 + 交易信号 CSV |
| `daily/strategy_optimization.py` | 策略参数优化 | 优化结果图表 |
| `daily/trend_channel_analyzer.py` | 趋势通道分析 | 趋势通道图表 + 信号 CSV |
| `daily/stock_quantitative_analyzer.py` | 股票量化综合分析 | 分析 CSV + 图表 |
| `weekly/` | 周线分析（数据检查/策略回测/优化/综合分析/AI预测） | 周线分析报告 |

### 3. Process/ 分析引擎 ⭐ (v1.2 新增)

五维度 JSON 摘要 + 两层决策系统：

| 模块 | 功能 |
|------|------|
| `Process/financial_structured_analyzer.py` | 财务数据 → 结构化 JSON（盈利能力/成长性/风险） |
| `Process/sentiment_valuation_analyzer.py` | 情绪 + 估值 → JSON（市场情绪/估值分位/技术情绪） |
| `Process/shareholder_structure_analyzer.py` | 股东结构 → JSON（集中度/机构动向/北向资金） |
| `Process/research_report_analyzer.py` | 研报观点 → JSON（评级分布/目标价/关键观点） |
| `Process/financial_analysis_enhancer.py` | 财务深度增强分析 |
| `Process/multi_strategy_analyzer.py` | 多策略 LLM 分析（趋势跟踪/均值回归/波段） |
| `Process/two_layer_decision_analyzer.py` | **两层决策** — 冲突检测 + 持仓交易计划 |

### 4. AI / LLM 分析类

| 程序名称 | 功能 |
|---------|------|
| `stock_ai_comprehensive_analyzer.py` | 综合各维度分析报告 → AI 大模型综合分析（支持本地 Ollama / 第三方 API） |
| `daily/stock_ai_local_analyzer.py` | K 线数据 → AI 日线分析 |
| `weekly/weekly_stock_ai_local_analyzer.py` | 周线数据 → AI 周线分析 |

### 5. 回测系统 ⭐

| 程序名称 | 功能 |
|---------|------|
| `trend_following_backtest.py` | 趋势跟踪策略回测引擎 |
| `backtest_all_stocks.py` | 全股票批量回测 |

### 6. Web 界面 & API

| 程序名称 | 功能 |
|---------|------|
| `web_ui.py` | Flask Web 主界面（`http://localhost:8081`） |
| `api/analysis.py` | 完整分析 API（全量数据 + 五维度 + 两层决策） |
| `api/quick_analysis.py` ⭐ | 快速分析 API（仅 K 线 + 技术趋势，三种策略视角） |
| `api/backtest.py` ⭐ | 回测 API |
| `api/detailed.py` | 详细模式 API（单步数据抓取/分析/查询） |
| `api/trading.py` | 交易记录管理 API |
| `api/report_viewer.py` | 报告查看 API |
| `api/common.py` ⭐ | 共享模块（交易所映射、任务队列、步骤执行引擎） |
| `report_viewer.py` | 独立报告查看器 |

---

## 🚀 快速开始

### 环境要求

- Python 3.9+
- [Ollama](https://ollama.com/)（本地 AI 分析）
- TA-Lib（技术指标计算）

### 安装

```bash
pip install -r requirements.txt
cp config.example.py config.py  # 编辑 config.py 填入你的配置
```

### Web 界面使用（推荐）

```bash
python web_ui.py
# 打开浏览器访问 http://localhost:8081
```

**三种分析模式：**

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| 🔍 **完整分析** | 全量数据采集 + 五维度 + 两层决策 | 新股票初始化 |
| ⚡ **快速分析** | 仅 K 线 + 技术趋势 | 每日盘后快速查看 |
| 📊 **回测** | 趋势跟踪策略回测 | 验证交易策略 |

---

## 执行流程

### 完整分析（新股票初始化）
```
数据采集 (16 步) → 技术指标计算 → 五维度 JSON 摘要 → 两层决策 → 综合报告
```

### 快速分析（每日更新）
```
日更数据更新 → 技术趋势计算 → 技术趋势 AI 分析（3 种策略视角可选）
```

### 命令行使用

```bash
# 统一批量分析
python batch_analyze.py --mode periodic --ticker 300433.SZ
python batch_analyze.py --mode daily --ticker 300433.SZ

# 统一数据抓取
python eastmoney_fetcher.py --type market_performance --ticker 300433.SZ
python eastmoney_fetcher.py --type dupont --ticker 300433.SZ

# 数据更新检查
python check_data_updates.py --mode daily --ticker 300433.SZ
python check_data_updates.py --mode periodic --ticker 300433.SZ

# 技术趋势分析（切换策略视角）
python analyze_technical_trend.py --strategy trend_following --ticker 300433.SZ
python analyze_technical_trend.py --strategy swing --ticker 300433.SZ
```

---

## 配置

编辑 `config.py`（从 `config.example.py` 复制）：

```python
# 股票代码
STOCK_TICKERS = {
    'example': '002594.SZ',
}

# AI 模型配置（支持本地 Ollama 或第三方 API）
AI_CONFIG = {
    # 本地 Ollama（默认）
    'base_url': 'http://localhost:11434',
    'model': 'qwen3.6:35b-a3b-coding-nvfp4',
    'temperature': 0.3,
    'max_tokens': 8192,
    'trading_strategy': 'neutral',          # trend_following / mean_reversion / swing / neutral
    'fallback_models': ['qwen3.6:35b-a3b-coding-nvfp4'],
    # 第三方 API（可选，兼容 OpenAI / DeepSeek / 通义千问等）
    # 'external_api': {
    #     'enabled': True,
    #     'api_key': 'your-api-key',
    #     'api_url': 'https://api.openai.com/v1',
    #     'model': 'gpt-4o',
    # },
}

# 交易记录（在 trading_records.py 中定义）
from trading_records import TRADING_RECORDS
```

---

## 依赖项

```
pandas, numpy, matplotlib, seaborn, yfinance, akshare, TA-Lib,
scikit-learn, schedule, requests, flask
```

---

## 注意事项

- 国内股票优先使用 akshare 数据源
- 技术指标计算需要 TA-Lib 库支持
- 本地 AI 分析需要部署 Ollama 服务
- 所有数据采集程序采用增量保存，避免数据丢失
- 数据文件存储在 `./data/{ticker}/` 目录下
- `config.py` 和 `trading_records.py` 包含敏感信息，已加入 `.gitignore`

---

## 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v1.2.0** | 2026-05 | 架构重构：统一入口、Process/引擎、两层决策、快速分析、回测系统 |
| v1.1.0 | 2026-03 | 41 模块：Web 界面、12 个新采集器、5 个新分析引擎 |
| v1.0.1 | 2026-02 | 18 模块：数据采集 + 基础分析 |

详见 [CHANGELOG.md](CHANGELOG.md)
