# shareholder_num_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票股东户数数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供详细的股东户数数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_F10_EH_HOLDERNUM` |
| akshare | 备用数据源，提供股东户数数据 | `ak.stock_zh_a_gdhs_detail_em` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 东方财富数据源
- 股票代码（SECUCODE）
- 证券代码（SECURITY_CODE）
- 截止日期（END_DATE）
- 股东总户数（HOLDER_TOTAL_NUM）
- 股东户数增减比例（TOTAL_NUM_RATIO）
- 户均持流通股（AVG_FREE_SHARES）
- 户均持流通股增减比例（AVG_FREESHARES_RATIO）
- 持股集中度（HOLD_FOCUS）
- 股价（PRICE）
- 户均持股市值（AVG_HOLD_AMT）
- 总持股比例（HOLD_RATIO_TOTAL）
- 流通股持股比例（FREEHOLD_RATIO_TOTAL）

### 2.2 akshare数据源
- 股东户数统计截止日
- 股东户数
- 户均持股
- 户均持股市值
- 持股集中度
- 其他相关字段

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_shareholder_num.csv` | `{DATA_DIR}/{ticker}/` | 从东方财富获取的股东户数数据 |
| `{ticker}_shareholder_num_info.csv` | `{DATA_DIR}/{ticker}/` | 从akshare获取的股东户数数据 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的 data 目录路径。

## 4. 数据处理特点

1. **增量更新**：如果本地已有数据，只获取新数据并追加，避免重复数据。
2. **数据去重**：在保存 CSV 文件时，使用日期字段作为唯一标识进行去重。
3. **智能抓取判断**：根据最后一条数据的日期和当前时间判断是否需要抓取新数据。
4. **多源数据获取**：同时从东方财富和 akshare 获取数据，提高数据获取成功率。
5. **错误处理**：程序对数据请求和文件操作进行异常捕获，确保程序稳定运行。
6. **分页处理**：自动处理分页数据，确保获取完整的股东户数数据。
7. **随机延迟**：在每次数据请求之间添加随机延迟（1-4秒），避免请求过于频繁被 API 限制。
8. **数据排序**：对保存的文件按日期进行升序排序，确保数据的时序性。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python shareholder_num_collector.py --ticker 300433.SZ
   ```

2. **处理配置文件中的所有股票**：
   ```bash
   python shareholder_num_collector.py
   ```
   其中，股票列表从 config.py 中的 STOCK_TICKERS 获取。

## 6. 代码结构

- **save_to_csv 函数**：保存数据到 CSV 文件，支持增量保存和去重。
- **fetch_shareholder_num 函数**：从东方财富数据中心抓取股东户数数据，支持分页处理。
- **should_fetch_data 函数**：根据最后一条数据的日期和当前时间判断是否需要抓取新数据。
- **get_last_date_from_file 函数**：从文件中获取最后一条数据的日期。
- **fetch_shareholder_num_akshare 函数**：从 akshare 获取股东户数数据。
- **主函数**：处理命令行参数并调用各个数据获取函数。

该程序设计合理，结构清晰，能够有效地从多个数据源获取股票股东户数数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。