# fetch_stock_market_performance.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票历史日度市场表现数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供历史日度市场表现数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_PCF10_MARKETPER` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 历史日度市场表现数据
- 交易日期（TRADE_DATE）
- 涨跌幅（CHANGERATE）
- 沪深300涨跌幅（HS300_CHANGERATE）
- 板块涨跌幅（BOARD_CHANGERATE）
- 板块名称（BOARD_NAME）
- 板块代码（BOARD_CODE）

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_market_performance.json` | `{DATA_DIR}/{ticker}/` | 历史日度市场表现数据，包括涨跌幅、板块涨跌幅等 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的数据目录路径。

## 4. 数据处理特点

1. **错误处理**：程序对网络请求和数据解析进行异常捕获，确保程序稳定运行。
2. **数据排序**：按日期排序，最新日期在前。
3. **数据完整性**：不过滤数据，保留所有数据以便分析。
4. **时间戳**：在保存的数据中添加时间戳，记录数据获取时间。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python fetch_stock_market_performance.py --ticker 002384.SZ
   ```

2. **使用默认股票**：
   ```bash
   python fetch_stock_market_performance.py
   ```
   默认处理股票代码为 002384.SZ。

## 6. 代码结构

- **fetch_market_performance 函数**：从东方财富数据中心获取历史日度市场表现数据。
- **process_market_data 函数**：处理历史日度市场表现数据，转换为标准格式。
- **save_market_data 函数**：保存历史日度市场表现数据到JSON文件。
- **main 函数**：主函数，处理命令行参数并调用各个数据获取和处理函数。

该程序设计合理，结构清晰，能够有效地从东方财富数据中心获取股票历史日度市场表现数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。