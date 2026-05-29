# shareholders_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票股东数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供股东持股数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_F10_EH_HOLDERS` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 股东数据
- 股东名称（HOLDER_NAME）
- 股东排名（HOLDER_RANK）
- 持股数量（HOLD_NUM）
- 持股比例（HOLD_RATIO）
- 变动数量（CHANGE_NUM）
- 变动比例（CHANGE_RATIO）
- 期末日期（END_DATE）
- 其他相关字段

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_historical_shareholders.csv` | `data/{ticker}/` | 历史股东数据，按季度更新 |

其中，`{ticker}` 是股票代码（如 002384.SZ）。

## 4. 数据处理特点

1. **增量更新**：如果本地已有数据，只获取新数据并追加，避免重复数据。
2. **数据去重**：在保存 CSV 文件时，使用 `HOLDER_NAME + END_DATE` 作为唯一标识进行去重。
3. **日期智能处理**：
   - 自动计算最新的季度末日期
   - 自动处理数据发布延迟，确保获取到已发布的数据
   - 支持指定日期范围的数据抓取
4. **错误处理**：程序对数据请求和文件操作进行异常捕获，确保程序稳定运行。
5. **分页处理**：自动处理分页数据，确保获取完整的股东数据。
6. **随机延迟**：在每次数据请求之间添加随机延迟（2-4秒），避免请求过于频繁被 API 限制。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python shareholders_collector.py --ticker 002384.SZ
   ```

2. **处理指定股票的特定日期范围**：
   ```bash
   python shareholders_collector.py --ticker 002384.SZ --start-date 2024-01-01 --end-date 2025-09-30
   ```

3. **处理配置文件中的所有股票**：
   ```bash
   python shareholders_collector.py
   ```
   其中，股票列表从 config.py 中的 STOCK_TICKERS 获取。

## 6. 代码结构

- **get_latest_quarter_end 函数**：获取最新的季度末日期，考虑数据发布延迟。
- **get_next_quarter 函数**：根据给定日期获取下一个季度的日期。
- **get_last_end_date 函数**：获取本地文件中的最后日期，用于增量更新。
- **save_to_csv 函数**：保存数据到 CSV 文件，支持增量保存和去重。
- **fetch_shareholders_data 函数**：从东方财富数据中心抓取股东数据，支持分页处理和日期范围指定。
- **主函数**：处理命令行参数并调用 fetch_shareholders_data 函数。

该程序设计合理，结构清晰，能够有效地从东方财富数据中心获取股票股东数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。