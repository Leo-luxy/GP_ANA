# fetch_industry_valuation.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票行业估值排名数据：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| 东方财富数据中心 | 主要数据来源，提供行业估值排名数据 | `https://datacenter.eastmoney.com/securities/api/data/v1/get`，使用报表名 `RPT_PCF10_INDUSTRY_CVALUE` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 行业估值排名数据
- 行业平均估值数据：PE、PE_TTM、PE_1Y、PE_2Y、PE_3Y、PS、PS_TTM、PB、PB_MRQ、PEG
- 行业中值估值数据：PE、PE_TTM、PE_1Y、PE_2Y、PE_3Y、PS、PS_TTM、PB、PB_MRQ、PEG
- 公司自身估值数据：PE、PE_TTM、PE_1Y、PE_2Y、PE_3Y、PS、PS_TTM、PB、PB_MRQ、PEG、排名
- 行业内排名前5的公司估值数据：PE、PE_TTM、PB、PEG、排名

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_industry_valuation.json` | `{DATA_DIR}/{ticker}/` | 行业估值排名数据，包括行业平均、行业中值、公司自身和行业前5公司的估值数据 |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的数据目录路径。

## 4. 数据处理特点

1. **错误处理**：程序对网络请求和数据解析进行异常捕获，确保程序稳定运行。
2. **数据分类**：将数据分为行业平均、行业中值、公司自身和行业前5公司四类。
3. **数据排序**：按排名排序，获取行业内排名前5的公司数据。
4. **时间戳**：在保存的数据中添加时间戳，记录数据获取时间。
5. **调试信息**：打印调试信息，便于排查问题。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python fetch_industry_valuation.py --ticker 002384.SZ
   ```

2. **使用默认股票**：
   ```bash
   python fetch_industry_valuation.py
   ```
   默认处理股票代码为 002384.SZ。

## 6. 代码结构

- **fetch_industry_valuation 函数**：从东方财富数据中心获取行业估值排名数据。
- **process_valuation_data 函数**：处理行业估值排名数据，分类整理为行业平均、行业中值、公司自身和行业前5公司四类。
- **save_valuation_data 函数**：保存行业估值排名数据到JSON文件。
- **main 函数**：主函数，处理命令行参数并调用各个数据获取和处理函数。

该程序设计合理，结构清晰，能够有效地从东方财富数据中心获取股票行业估值排名数据，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。