# org_hold_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票机构持股数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供机构持股明细数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_MAIN_ORGHOLDDETAIL` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 机构持股数据
- 机构类型（ORG_TYPE）
- 证券代码（SECUCODE）
- 报告日期（REPORT_DATE）
- 持股机构代码（HOLDER_CODE）
- 持股机构名称（HOLDER_NAME）
- 持股数量（TOTAL_SHARES）
- 持有市值（HOLD_VALUE）
- 持股比例（TOTALSHARES_RATIO）
- 流通股持股比例（FREESHARES_RATIO）
- 流通市值（FREE_MARKET_CAP）
- 流通股持股数量（FREE_SHARES）
- 股票代码（SECURITY_CODE）
- 基金代码（FUND_CODE）
- 基金衍生代码（FUND_DERIVECODE）
- 净值比例（NETVALUE_RATIO）

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_institutional_holdings.csv` | `data/{ticker}/` | 机构持股明细数据 |

其中，`{ticker}` 是股票代码（如 002594.SZ）。

## 4. 数据处理特点

1. **增量更新**：如果本地已有数据，只获取新数据并追加，避免重复数据。
2. **数据去重**：在保存 CSV 文件时，使用 `HOLDER_CODE + REPORT_DATE` 作为唯一标识进行去重。
3. **错误处理**：程序对网络请求和文件操作进行异常捕获，确保程序稳定运行。
4. **分页处理**：自动处理分页数据，确保获取完整的机构持股数据。
5. **随机延迟**：在每次数据请求之间添加随机延迟（2-4秒），避免请求过于频繁被 API 限制。
6. **参数化配置**：支持通过命令行参数指定股票代码、报告日期、机构类型等。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python org_hold_collector.py --ticker 002594.SZ
   ```

2. **处理指定股票的特定报告日期**：
   ```bash
   python org_hold_collector.py --ticker 002594.SZ --report-date 2025-12-31
   ```

3. **处理指定股票的特定机构类型**：
   ```bash
   python org_hold_collector.py --ticker 002594.SZ --org-type 01
   ```

4. **处理配置文件中的所有股票**：
   ```bash
   python org_hold_collector.py
   ```
   其中，股票列表从 config.py 中的 STOCK_TICKERS 获取。

## 6. 代码结构

- **save_to_csv 函数**：保存数据到 CSV 文件，支持增量保存和去重。
- **fetch_org_hold_detail 函数**：从东方财富数据中心抓取机构持股明细数据，支持分页处理和参数配置。
- **主函数**：处理命令行参数并调用 fetch_org_hold_detail 函数。

该程序设计合理，结构清晰，能够有效地从东方财富数据中心获取股票机构持股数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。