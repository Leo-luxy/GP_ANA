# fetch_industry_peers.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票同行业公司数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供同行业公司数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_PCF10_INDUSTRY_MARKET` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 同行业公司数据
- 股票代码（CORRE_SECURITY_CODE）
- 股票名称（CORRE_SECURITY_NAME）
- 股票代码（含市场标识，CORRE_SECUCODE）
- 总市值（TOTAL_CAP）
- 流通市值（FREECAP）
- 营业总收入（TOTAL_OPERATEINCOME）
- 净利润（NETPROFIT）
- 报告类型（REPORT_TYPE）
- 总市值排名（TOTAL_CAP_RANK）
- 流通市值排名（FREECAP_RANK）
- 营业总收入排名（TOTAL_OPERATEINCOME_RANK）
- 净利润排名（NETPROFIT_RANK）

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_industry_peers.json` | `{DATA_DIR}/{ticker}/` | 同行业公司数据，包括总市值、净利润、排名等信息 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的数据目录路径。

## 4. 数据处理特点

1. **错误处理**：程序对网络请求和数据解析进行异常捕获，确保程序稳定运行。
2. **数据过滤**：过滤掉行业平均和行业中值数据，只保留具体公司数据。
3. **数据排序**：按净利润降序排序，获取行业内净利润排名前5的公司数据。
4. **单位转换**：将总市值、营业总收入和净利润转换为亿元单位。
5. **时间戳**：在保存的数据中添加时间戳，记录数据获取时间。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python fetch_industry_peers.py --ticker 002384.SZ
   ```

2. **使用默认股票**：
   ```bash
   python fetch_industry_peers.py
   ```
   默认处理股票代码为 002384.SZ。

## 6. 代码结构

- **fetch_industry_peers 函数**：从东方财富数据中心获取同行业公司数据。
- **process_peers_data 函数**：处理同行业公司数据，转换单位并整理格式。
- **save_peers_data 函数**：保存同行业公司数据到JSON文件。
- **main 函数**：主函数，处理命令行参数并调用各个数据获取和处理函数。

该程序设计合理，结构清晰，能够有效地从东方财富数据中心获取股票同行业公司数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。