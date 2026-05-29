# stock_market_data_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票市场数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| akshare | 主要数据来源，提供多种股票市场相关数据 | `ak.stock_value_em`、`ak.stock_a_pe`、`ak.stock_individual_fund_flow`、`ak.stock_margin_detail_sse`、`ak.stock_margin_detail_szse` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 估值数据
- 股票估值相关指标，包括市盈率、市净率等

### 2.2 资金流数据
- 个股资金流数据，包括净流入、净流出等

### 2.3 融资融券数据
- 融资融券详细数据，包括融资余额、融券余额等

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_valuation.csv` | `{DATA_DIR}/{ticker}/` | 股票估值数据 |
| `{ticker}_fund_flow.csv` | `{DATA_DIR}/{ticker}/` | 股票资金流数据 |
| `{ticker}_margin_data.csv` | `{DATA_DIR}/{ticker}/` | 股票融资融券数据 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的 data 目录路径。

## 4. 数据处理特点

1. **增量更新**：如果本地已有数据，只获取新数据并追加，避免重复数据。
2. **错误处理**：程序对每个数据获取步骤都进行了异常捕获，确保某个数据获取失败不会影响整个程序运行。
3. **随机延迟**：在每次数据请求之间添加随机延迟（1-4秒），避免请求过于频繁被 API 限制。
4. **多方法尝试**：获取估值数据时，先尝试使用 `stock_value_em`，如果失败则尝试使用 `stock_a_pe`。
5. **日期处理**：对日期数据进行解析和处理，确保数据的一致性。
6. **周末跳过**：获取融资融券数据时，会跳过周末日期，提高数据获取效率。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python stock_market_data_collector.py --ticker 300433.SZ
   ```

2. **处理配置文件中的所有股票**：
   ```bash
   python stock_market_data_collector.py
   ```
   其中，股票列表从 config.py 中的 STOCK_TICKERS 获取。

## 6. 代码结构

- **get_stock_valuation_data 函数**：获取单个股票的估值数据，支持增量更新。
- **get_stock_fund_flow_data 函数**：获取单个股票的资金流数据，支持增量更新。
- **get_stock_margin_data 函数**：获取单个股票的融资融券数据，支持增量更新和周末跳过。
- **main 函数**：主函数，处理命令行参数并调用各个数据获取函数。

该程序设计合理，结构清晰，能够有效地从 akshare 获取股票市场数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。