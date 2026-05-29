# em_financial_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票财务数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富网 | 主要数据来源，提供多种财务相关数据 | `https://datacenter.eastmoney.com/securities/api/data`，使用不同的报表类型获取杜邦分析、增长率和主要财务指标数据 |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 杜邦分析数据
- 从东方财富网获取股票的杜邦分析数据
- 包含ROE、净利率、总资产周转率、权益乘数等指标

### 2.2 增长率数据
- 从东方财富网获取股票的增长率数据
- 包含同比和环比增长率指标

### 2.3 主要财务指标数据
- 从东方财富网获取股票的主要财务指标数据
- 包含EPS、BPS、ROE、资产负债率等核心财务指标

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_dupont_data.csv` | `{DATA_DIR}/{ticker}/` | 杜邦分析数据，包括ROE、净利率、总资产周转率、权益乘数等 |
| `{ticker}_growth_ratio_data.csv` | `{DATA_DIR}/{ticker}/` | 增长率数据，包括同比和环比增长率指标 |
| `{ticker}_main_financial_data.csv` | `{DATA_DIR}/{ticker}/` | 主要财务指标数据，包括EPS、BPS、ROE、资产负债率等 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的数据目录路径。

## 4. 数据处理特点

1. **增量更新**：如果本地已有数据，只获取新数据并合并，避免重复数据。
2. **错误处理**：程序对每个数据获取步骤都进行异常捕获，确保某个数据获取失败不会影响整个程序运行。
3. **时间差计算**：通过计算本地数据与当前时间的季度差，动态调整获取数据的数量。
4. **数据合并**：自动合并新旧数据，根据日期和类型去重，保留最新数据。
5. **日期处理**：对日期数据进行解析和处理，确保数据的一致性。
6. **重试机制**：网络请求失败时自动重试，提高数据获取成功率。
7. **数据排序**：按报告日期排序，确保数据的时间顺序正确。

## 5. 使用方法

1. **抓取指定股票的所有财务数据**：
   ```bash
   python em_financial_collector.py --ticker 300433.SZ
   ```

2. **抓取指定股票的特定类型财务数据**：
   ```bash
   # 只抓取杜邦分析数据
   python em_financial_collector.py --ticker 300433.SZ --type dupont
   
   # 只抓取增长率数据
   python em_financial_collector.py --ticker 300433.SZ --type growth
   
   # 只抓取主要财务指标数据
   python em_financial_collector.py --ticker 300433.SZ --type main
   ```

## 6. 代码结构

- **EastmoneyFinancialCollector 类**：从东方财富网抓取股票财务数据的核心类。
  - **_make_request 方法**：发送HTTP请求，带重试机制。
  - **_load_existing_data 方法**：加载已存在的数据文件。
  - **_save_data 方法**：保存数据到CSV文件。
  - **_merge_data 方法**：合并新旧数据，避免重复。
  - **_get_quarter_difference 方法**：计算两个日期之间的季度差。
  - **_get_latest_report_date 方法**：获取本地数据文件中的最新报告日期。
  - **fetch_dupont_data 方法**：抓取杜邦分析数据。
  - **fetch_growth_ratio_data 方法**：抓取增长率数据。
  - **fetch_main_financial_data 方法**：抓取主要财务指标数据。
  - **fetch_all_data 方法**：抓取所有三类财务数据。
- **main 函数**：主函数，处理命令行参数并调用相应的数据获取方法。

该程序设计合理，结构清晰，采用面向对象的方式实现，能够有效地从东方财富网获取股票财务数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。