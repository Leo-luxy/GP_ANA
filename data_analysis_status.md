# 300433.SZ 数据文件分析状态报告

## 一、CSV数据文件分析状态

| 序号 | 文件名 | 是否已被分析 | 分析程序 | 数据类型 | 建议 |
|------|--------|-------------|----------|----------|------|
| 1 | 300433.SZ_dupont_data.csv | ✅ 已分析 | analyze_em_financial.py | 杜邦分析数据 | 已整合到东方财富财务分析 |
| 2 | 300433.SZ_growth_ratio_data.csv | ✅ 已分析 | analyze_em_financial.py | 增长率数据 | 已整合到东方财富财务分析 |
| 3 | 300433.SZ_main_financial_data.csv | ✅ 已分析 | analyze_em_financial.py | 主要财务指标 | 已整合到东方财富财务分析 |
| 4 | 300433.SZ_shareholder.csv | ✅ 已分析 | analyze_shareholder_structure.py | 机构持股数据 | 股东结构分析 |
| 5 | 300433.SZ_shareholder_num.csv | ✅ 已分析 | analyze_shareholder_structure.py | 股东户数数据 | 股东结构分析 |
| 6 | 300433.SZ_fund_flow.csv | ✅ 已分析 | analyze_fund_flow.py | 资金流向数据 | 资金流分析 |
| 7 | 300433.SZ_indicators.csv | ✅ 已分析 | analyze_fund_flow.py, analyze_valuation_data.py, analyze_technical_trend.py | 技术指标数据 | 多程序共用 |
| 8 | 300433.SZ_valuation.csv | ✅ 已分析 | analyze_valuation_data.py | 估值数据 | 估值分析 |
| 9 | 300433.SZ_margin_data.csv | ✅ 已分析 | analyze_margin_data.py | 融资融券数据 | 两融分析 |
| 10 | 300433.SZ_qfq.csv | ⚠️ 未确认 | - | 前复权价格数据 | 需要确认是否被使用 |
| 11 | 300433.SZ_trading_signals.csv | ❌ 未分析 | - | 交易信号数据 | **建议创建分析程序** |
| 12 | 300433.SZ_strategy_signals.csv | ❌ 未分析 | - | 策略信号数据 | **建议创建分析程序** |
| 13 | 300433.SZ_trend_channel_signals.csv | ❌ 未分析 | - | 趋势通道信号 | **建议创建分析程序** |
| 14 | 300433.SZ_performance_forecast.csv | ❌ 未分析 | - | 业绩预告数据 | **建议创建分析程序** |
| 15 | 300433.SZ_performance_forecast_ths.csv | ❌ 未分析 | - | 同花顺业绩预告 | **建议创建分析程序** |
| 16 | 300433.SZ_ex_dividend.csv | ❌ 未分析 | - | 除权除息数据 | **建议创建分析程序** |

## 二、JSON数据文件分析状态

| 序号 | 文件名 | 是否已被分析 | 分析程序 | 数据类型 | 建议 |
|------|--------|-------------|----------|----------|------|
| 1 | 300433.SZ_company_info.json | ✅ 已分析 | analyze_shareholder_structure.py, analyze_fund_flow.py, analyze_financial_statements.py | 公司基本信息 | 多程序共用 |
| 2 | 300433.SZ_financial_indicators.json | ✅ 已分析 | - | 财务指标数据 | 由financial_indicators_collector.py生成 |
| 3 | 300433.SZ_technical_trend_analysis.json | ✅ 已分析 | analyze_technical_trend.py | 技术趋势分析 | 技术分析 |
| 4 | 300433.SZ_technical_trend_analysis_20260319_210415.json | ✅ 已分析 | analyze_technical_trend.py | 历史技术趋势分析 | 技术分析历史版本 |

## 三、未被分析的数据文件详细说明

### 1. 交易信号类（高优先级）
- **300433.SZ_trading_signals.csv** - 交易信号数据
- **300433.SZ_strategy_signals.csv** - 策略信号数据  
- **300433.SZ_trend_channel_signals.csv** - 趋势通道信号

**建议**：创建统一的`analyze_trading_signals.py`程序，综合分析各类交易信号

### 2. 业绩预告类（中优先级）
- **300433.SZ_performance_forecast.csv** - 业绩预告数据
- **300433.SZ_performance_forecast_ths.csv** - 同花顺业绩预告

**建议**：创建`analyze_performance_forecast.py`程序，对比分析不同来源的业绩预告

### 3. 除权除息类（中优先级）
- **300433.SZ_ex_dividend.csv** - 除权除息数据

**建议**：创建`analyze_dividend.py`程序，分析分红历史和股息率

### 4. 价格数据类（低优先级）
- **300433.SZ_qfq.csv** - 前复权价格数据

**状态**：可能已被技术分析程序使用，需要确认

## 四、分析程序覆盖情况总结

### 已覆盖的数据类型
✅ 财务数据（股票三类）
✅ 股东结构数据
✅ 资金流向数据
✅ 估值数据
✅ 融资融券数据
✅ 技术指标数据
✅ 技术趋势分析
✅ 公司基本信息

### 未覆盖的数据类型
❌ 交易信号数据（3个文件）
❌ 业绩预告数据（2个文件）
❌ 除权除息数据（1个文件）

## 五、建议创建的分析程序

1. **analyze_trading_signals.py** - 交易信号综合分析
   - 输入：trading_signals.csv, strategy_signals.csv, trend_channel_signals.csv
   - 功能：综合分析各类交易信号，生成交易建议

2. **analyze_performance_forecast.py** - 业绩预告分析
   - 输入：performance_forecast.csv, performance_forecast_ths.csv
   - 功能：对比分析不同来源的业绩预告，评估业绩预期

3. **analyze_dividend.py** - 分红分析
   - 输入：ex_dividend.csv
   - 功能：分析分红历史、股息率、除权除息影响

## 六、数据文件使用统计

- **总CSV文件数**：16个
- **已分析CSV文件数**：10个
- **未分析CSV文件数**：6个
- **总JSON文件数**：4个
- **已分析JSON文件数**：4个
- **未分析JSON文件数**：0个

**覆盖率**：CSV文件 62.5% 已分析，JSON文件 100% 已分析
