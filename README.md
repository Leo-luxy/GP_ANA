# 股票分析系统

本系统用于股票数据的抓取、分析和策略回测，提供完整的股票分析流程。

## 🌐 快速开始 - Web 界面使用（推荐）

**最简单的方式：使用 Web 界面，一站式完成所有操作！**

### 启动 Web 界面

```bash
python web_ui.py
```

启动后访问：**http://localhost:8081**

### Web 界面功能

✅ **股票分析** - 支持三种分析模式：
- 🆕 新股票初始化（完整分析流程）
- 📅 每日更新（日线数据更新）
- 🔄 定期更新（财务数据等低频数据）

✅ **买卖记录管理** - 添加和查看股票交易记录

✅ **详细模式** - 精细化控制数据抓取和分析

✅ **报告查看** - 浏览所有股票的分析报告

### 使用流程

1. **启动 Web 界面**
   ```bash
   python web_ui.py
   ```

2. **打开浏览器访问** http://localhost:8081

3. **输入股票代码**（6 位数字，如：300433）

4. **选择分析类型**
   - 新股票：选择"新股票初始化"
   - 已有股票：选择"每日更新"

5. **点击"开始分析"**，系统自动执行：
   - 数据抓取（公司基本信息、财务数据、北向资金等）
   - 数据分析（财务报表、资金流、融资融券等）
   - AI 综合分析

6. **查看分析报告** - 分析完成后自动显示最新报告

### 前置要求

- ✅ 已安装所有依赖：`pip install -r requirements.txt`
- ✅ Flask 已安装（Web 界面依赖）
- ✅ Ollama 服务运行中（用于 AI 分析，可选）

---

## 程序分类

### 1. 数据抓取类

| 程序名称 | 功能 | 引用数据源 | 输出物 | 调用方法 |
|---------|------|-----------|--------|----------|
| `data_collector.py` | 抓取股票历史行情数据（前复权） | akshare | `{ticker}_qfq.csv` | `python data_collector.py [--ticker 300433.SZ]` |
| `stock_market_data_collector.py` | 股票市场数据抓取，包括资金流、融资融券和估值数据 | akshare | `{ticker}_fund_flow.csv`<br>`{ticker}_margin_data.csv`<br>`{ticker}_valuation.csv` | `python stock_market_data_collector.py [--ticker 300433.SZ]` |
| `stock_company_info_collector.py` | 获取股票公司的基本信息、研究报告、主要股东等信息 | akshare | `{ticker}_company_basic.json`<br>`{ticker}_research_reports.csv`<br>`{ticker}_main_shareholders.csv`<br>`{ticker}_financial_profit.csv`<br>`{ticker}_financial_balance.csv`<br>`{ticker}_north_holdings.csv` | `python stock_company_info_collector.py [--ticker 300433.SZ]` |
| `financial_indicators_collector.py` | 获取股票的财务指标、成长指标、现金流指标等数据 | akshare | `{ticker}_financial_indicators.json` | `python financial_indicators_collector.py [--ticker 300433.SZ]` |
| `shareholder_collector.py` | 抓取机构持股数据 | 东方财富API | `{ticker}_shareholder.csv` | `python shareholder_collector.py [--ticker 300433.SZ]` |
| `shareholder_num_collector.py` | 抓取股东户数、户均持股等历史数据 | 东方财富API | `{ticker}_shareholder_num.csv` | `python shareholder_num_collector.py [--ticker 300433.SZ]` |
| `north_holdings.py` | 获取北向资金持股数据 | 东方财富API | `{ticker}_north_holdings.csv` | `python north_holdings.py [--ticker 300433.SZ]` |
| `north_fund_collector.py` | 抓取北向资金逐日持股数据 | 东方财富API | `{ticker}_north_fund.csv` | `python north_fund_collector.py` |
| `em_financial_collector.py` | 抓取东方财富财务数据 | 东方财富API | `{ticker}_dupont_data.csv`<br>`{ticker}_growth_ratio_data.csv` | `python em_financial_collector.py [--ticker 300433.SZ]` |
| `important_missing_data_collector.py` | 抓取重要缺失数据 | 多个数据源 | 各种缺失数据文件 | `python important_missing_data_collector.py [--ticker 300433.SZ]` |
| `db_collector.py` | 数据库数据收集 | 数据库 | 数据库数据文件 | `python db_collector.py` |

### 2. 数据分析类

| 程序名称 | 功能 | 引用数据源 | 输出物 | 调用方法 |
|---------|------|-----------|--------|----------|
| `analyze_financial_statements.py` | 财务报表分析 | `{ticker}_company_basic.json`<br>`{ticker}_financial_profit.csv`<br>`{ticker}_financial_balance.csv`<br>`{ticker}_financial_indicators.json` | `./data/{ticker}/{ticker}_financial_analysis_{timestamp}.md` | `python analyze_financial_statements.py --ticker 300433.SZ` |
| `analyze_fund_flow.py` | 资金流分析 | `{ticker}_fund_flow.csv` | `./data/{ticker}/{ticker}_fund_flow_analysis_{timestamp}.md` | `python analyze_fund_flow.py --ticker 300433.SZ` |
| `analyze_margin_data.py` | 融资融券分析 | `{ticker}_margin_data.csv` | `./data/{ticker}/{ticker}_margin_data_analysis_{timestamp}.md` | `python analyze_margin_data.py --ticker 300433.SZ` |
| `analyze_research_reports.py` | 研究报告分析 | `{ticker}_company_basic.json`<br>`{ticker}_research_reports.csv` | `./data/{ticker}/{ticker}_research_reports_analysis_{timestamp}.md` | `python analyze_research_reports.py --ticker 300433.SZ` |
| `analyze_shareholder_structure.py` | 股东结构分析 | `{ticker}_company_basic.json`<br>`{ticker}_main_shareholders.csv`<br>`{ticker}_shareholder.csv`<br>`{ticker}_shareholder_num.csv`<br>`{ticker}_north_fund.csv` | `./data/{ticker}/{ticker}_shareholder_structure_analysis_{timestamp}.md` | `python analyze_shareholder_structure.py --ticker 300433.SZ` |
| `analyze_valuation_data.py` | 估值分析 | `{ticker}_valuation.csv` | `./data/{ticker}/{ticker}_valuation_analysis_{timestamp}.md` | `python analyze_valuation_data.py --ticker 300433.SZ` |
| `analyze_technical_trend.py` | 技术趋势分析 | `{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_technical_trend_analysis.json` | `python analyze_technical_trend.py [--ticker 300433.SZ]` |
| `analyze_em_financial.py` | 东方财富财务分析 | 东方财富数据文件 | 财务分析报告 | `python analyze_em_financial.py --ticker 300433.SZ` |
| `analyze_performance_forecast.py` | 业绩预测分析 | 业绩预测数据文件 | 业绩预测分析报告 | `python analyze_performance_forecast.py --ticker 300433.SZ` |
| `daily/data_analysis.py` | 股票数据质量检查和可视化分析 | `{ticker}_qfq.csv`<br>`{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_price_volume.png`<br>`./data/{ticker}/{ticker}_technical_indicators.png`<br>`./data/{ticker}/{ticker}_bollinger_bands.png`<br>`./data/{ticker}/{ticker}_correlation.png` | `python daily/data_analysis.py [--ticker 300433.SZ]` |
| `daily/technical_analysis.py` | 技术指标信号分析和有效性评估 | `{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_signal_analysis.png` | `python daily/technical_analysis.py [--ticker 300433.SZ]` |
| `daily/quantitative_strategy.py` | 基于技术指标的量化交易策略回测 | `{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_strategy_results.png`<br>`./data/{ticker}/{ticker}_trading_signals.csv` | `python daily/quantitative_strategy.py [--ticker 300433.SZ]` |
| `daily/strategy_optimization.py` | 优化量化交易策略的参数 | `{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_optimization_results.png` | `python daily/strategy_optimization.py [--ticker 300433.SZ]` |
| `daily/daily_strategy_optimization_multistock.py` | 多股票策略优化 | 多个股票的指标数据 | 多股票优化结果文件 | `python daily/daily_strategy_optimization_multistock.py` |
| `daily/stock_quantitative_analyzer.py` | 股票量化分析 | `{ticker}_qfq.csv`<br>`{ticker}_indicators.csv` | `./data/{ticker}/{ticker}_analysis_{date}.csv`<br>`./data/{ticker}/{ticker}_analysis_{date}.png` | `python daily/stock_quantitative_analyzer.py [--ticker 300433.SZ]` |
| `daily/trend_channel_analyzer.py` | 趋势通道分析 | `{ticker}_qfq.csv` | `./data/{ticker}/{ticker}_trend_channel_results.png`<br>`./data/{ticker}/{ticker}_trend_channel_signals.csv` | `python daily/trend_channel_analyzer.py [--ticker 300433.SZ]` |
| `weekly/weekly_data_analysis.py` | 周线数据质量检查和可视化分析 | 周线数据文件 | 周线分析图表 | `python weekly/weekly_data_analysis.py` |
| `weekly/weekly_quantitative_strategy.py` | 基于周线的量化交易策略回测 | 周线数据文件 | 周线策略回测结果 | `python weekly/weekly_quantitative_strategy.py` |
| `weekly/weekly_strategy_optimization.py` | 周线策略参数优化 | 周线数据文件 | 周线策略优化结果 | `python weekly/weekly_strategy_optimization.py` |
| `weekly/weekly_strategy_optimization_multistock.py` | 多股票周线策略优化 | 多个股票的周线数据 | 多股票周线优化结果 | `python weekly/weekly_strategy_optimization_multistock.py` |
| `weekly/weekly_stock_analyzer.py` | 周线综合分析 | 周线数据文件 | 周线分析报告 | `python weekly/weekly_stock_analyzer.py` |
| `daily_trend_strategy.py` | 日线趋势策略分析 | 日线数据文件 | 趋势策略分析结果 | `python daily_trend_strategy.py` |

### 3. AI分析类

| 程序名称 | 功能 | 引用数据源 | 输出物 | 调用方法 |
|---------|------|-----------|--------|----------|
| `daily/ai_model.py` | 使用机器学习模型对股票价格进行预测和分析 | `{ticker}_indicators.csv` | `{ticker}_ai_predictions.png`<br>`{ticker}_feature_importance.png` | `python daily/ai_model.py [--ticker 300433.SZ]` |
| `daily/stock_prediction.py` | 股票价格预测 | `{ticker}_qfq.csv`<br>`{ticker}_indicators.csv` | 预测结果图表和数据文件 | `python daily/stock_prediction.py` |
| `weekly/weekly_stock_prediction.py` | 周线价格预测 | 周线数据文件 | 周线预测结果 | `python weekly/weekly_stock_prediction.py` |

### 4. LLM分析类

| 程序名称 | 功能 | 引用数据源 | 输出物 | 调用方法 |
|---------|------|-----------|--------|----------|
| `stock_ai_comprehensive_analyzer.py` | 综合股票的财务报表、资金流、融资融券和估值分析报告，发送给本地Ollama AI进行综合分析 | 各种分析报告文件 | `{ticker}_comprehensive_analysis_{timestamp}.md`<br>`{ticker}_prompt_info_{timestamp}.md` | `python stock_ai_comprehensive_analyzer.py [--ticker 300433.SZ]` |
| `daily/stock_ai_local_analyzer.py` | 将股票数据发送给本地Ollama AI进行分析 | `{ticker}_qfq.csv`<br>`{ticker}_indicators.csv` | `{ticker}_{timestamp}.md`<br>`{ticker}_support_resistance.png` | `python daily/stock_ai_local_analyzer.py [--ticker 300433.SZ]` |
| `weekly/weekly_stock_ai_local_analyzer.py` | 周线AI分析 | 周线数据文件 | 周线AI分析报告 | `python weekly/weekly_stock_ai_local_analyzer.py` |

### 5. 工具和自动化类

| 程序名称 | 功能 | 引用数据源 | 输出物 | 调用方法 |
|---------|------|-----------|--------|----------|
| `check_data_updates.py` | 检查指定股票的数据文件是否是最新日期以及是否有数据文件缺失 | 数据文件 | 无（自动更新数据文件） | `python check_data_updates.py [--ticker 300433.SZ]` |
| `check_periodic_data_updates.py` | 检查定期数据更新 | 定期数据文件 | 无（自动更新数据文件） | `python check_periodic_data_updates.py [--ticker 300433.SZ]` |
| `batch_analyze_all.py` | 批量对多只股票执行完整的分析流程 | 所有分析脚本 | 各股票的分析结果文件 | `python batch_analyze_all.py [--ticker 300433.SZ]` |
| `batch_analyze_daily.py` | 批量执行日线分析 | 日线分析脚本 | 各股票的日线分析结果 | `python batch_analyze_daily.py [--ticker 300433.SZ]` |
| `batch_analyze_periodic.py` | 批量执行定期数据分析 | 定期分析脚本 | 各股票的定期分析结果 | `python batch_analyze_periodic.py [--ticker 300433.SZ]` |
| `separate_company_info.py` | 将公司信息分离为多个文件 | `{ticker}_company_info.json` | 分离后的多个文件 | `python separate_company_info.py [--ticker 300433.SZ]` |
| `manage_logs.py` | 日志管理 | 日志文件 | 管理后的日志文件 | `python manage_logs.py` |
| `trading_records.py` | 交易记录管理 | 交易记录文件 | 管理后的交易记录 | `python trading_records.py` |
| `utils.py` | 通用工具函数，包含技术指标计算 | 无 | 无 | 被其他脚本引用 |
| `web_ui.py` | Web界面 | 各种数据文件 | Web界面 | `python web_ui.py` |
| `api/analysis.py` | 分析API | 分析结果文件 | API响应 | 被Web界面调用 |
| `api/detailed.py` | 详细信息API | 各种数据文件 | API响应 | 被Web界面调用 |
| `api/report_viewer.py` | 报告查看API | 分析报告文件 | API响应 | 被Web界面调用 |
| `api/trading.py` | 交易API | 交易记录文件 | API响应 | 被Web界面调用 |
| `report_viewer.py` | 报告查看器 | 分析报告文件 | 报告查看界面 | `python report_viewer.py` |

### 6. 配置文件

| 文件名 | 功能 | 内容 |
|-------|------|------|
| `config.py` | 存储系统配置参数 | 股票代码、持仓情况、交易记录、历史数据日期范围、技术指标参数等 |
| `requirements.txt` | 依赖项列表 | 系统所需的Python包 |

## 执行流程

1. **数据抓取**
   - 运行数据抓取类程序获取股票数据
   - 优先运行 `stock_company_info_collector.py` 获取公司基本信息
   - 然后运行 `data_collector.py` 和 `stock_market_data_collector.py` 获取市场数据
   - 最后运行其他数据抓取程序获取补充数据

2. **数据处理**
   - 运行 `separate_company_info.py` 分离公司信息（如果需要）
   - 运行 `check_data_updates.py` 检查数据更新情况

3. **数据分析**
   - 运行数据分析类程序进行各种分析
   - 可以使用 `batch_analyze_daily.py` 批量执行日线分析
   - 使用 `batch_analyze_periodic.py` 批量执行定期数据分析

4. **AI分析**
   - 运行AI分析类程序进行机器学习预测
   - 运行LLM分析类程序获取AI分析报告
   - 使用 `stock_ai_comprehensive_analyzer.py` 获取综合分析报告

5. **自动化运行**
   - 可以设置定时任务自动执行数据抓取和分析
   - 监控数据更新情况，确保数据及时更新

## 依赖项

- pandas
- numpy
- matplotlib
- seaborn
- yfinance
- akshare
- TA-Lib
- scikit-learn
- schedule
- requests
- pyperclip

## 注意事项

- 确保已安装所有依赖项
- 对于国内股票，优先使用akshare数据源
- 技术指标计算需要TA-Lib库支持
- 本地AI分析需要部署Ollama服务
- 数据抓取脚本位于根目录，分析脚本分别位于daily和weekly目录
- 所有数据抓取程序均采用增量保存方式，避免数据丢失
- 数据文件存储在 `./data/{ticker}/` 目录下，按股票代码分类

## 最新更新

- 所有数据抓取程序已改为增量保存，确保数据的完整性和一致性
- 公司信息已分离为多个专用文件，提高数据管理的清晰度和效率
- 新增了多种分析脚本，提供更全面的股票分析功能
- 优化了AI分析流程，提供更准确的分析报告