# stock_company_info_collector.py 程序说明

## 1. 数据源

该程序从以下数据源获取股票公司信息：

| 数据源 | 描述 | 使用的函数/API |
|-------|------|--------------|
| akshare | 主要数据来源，提供多种股票相关数据 | `ak.stock_individual_basic_info_xq`、`ak.stock_zh_scale_comparison_em`、`ak.stock_zyjs_ths`、`ak.stock_research_report_em`、`ak.stock_financial_report_sina`、`ak.stock_financial_abstract`、`ak.stock_zh_a_spot_em` |
| 东方财富 API | 备用数据源，用于获取基本信息 | `https://datacenter.eastmoney.com/securities/api/data/v1/get` |
| 新浪财经 API | 通过 akshare 间接使用，获取财务报表 | `ak.stock_financial_report_sina` |

## 2. 抓取的数据

程序为每只股票抓取以下数据：

### 2.1 基本信息
- 公司简称
- 公司全称
- 成立日期
- 上市日期
- 注册资本
- 员工人数
- 经营范围
- 主营业务
- 地址
- 电话
- 邮箱
- 网站
- 实际控制人
- 高管人数
- 实际发行数量
- 发行价格
- 实际募集资金净额
- 发行后市盈率
- 网上发行成功率
- 所属行业
- 公司介绍

### 2.2 股票规模对比
- 股票规模相关数据

### 2.3 主营业务
- 公司主营业务详细信息

### 2.4 研究报告
- 序号
- 股票代码
- 股票简称
- 报告名称
- 东财评级
- 机构
- 近一月个股研报数
- 2025-盈利预测-收益
- 2025-盈利预测-市盈率
- 2026-盈利预测-收益
- 2026-盈利预测-市盈率
- 2027-盈利预测-收益
- 2027-盈利预测-市盈率
- 行业
- 日期
- 报告PDF链接

### 2.5 财务报表
- 利润表数据
- 资产负债表数据

### 2.6 财务摘要
- 公司财务摘要信息

## 3. 保存的文件

程序将数据保存到以下文件中：

| 文件名 | 保存路径 | 数据内容 |
|-------|---------|---------|
| `{ticker}_company_basic.json` | `{DATA_DIR}/{ticker}/` | 公司基本信息、业务范围、财务摘要、规模对比 |
| `{ticker}_research_reports.csv` | `{DATA_DIR}/{ticker}/` | 研究报告数据 |
| `{ticker}_financial_profit.csv` | `{DATA_DIR}/{ticker}/` | 财务利润表数据 |
| `{ticker}_financial_balance.csv` | `{DATA_DIR}/{ticker}/` | 财务资产负债表数据 |
| `{ticker}_north_holdings.csv` | `{DATA_DIR}/{ticker}/` | 北向资金数据（如果有） |

其中，`{ticker}` 是股票代码（如 300433.SZ），`{DATA_DIR}` 是从 config.py 导入的 data 目录路径。

## 4. 数据处理特点

1. **错误处理**：程序对每个数据获取步骤都进行了异常捕获，确保某个数据获取失败不会影响整个程序运行。
2. **数据去重**：在保存 CSV 文件时，程序会加载现有数据并去重，避免重复数据。
3. **增量保存**：对于 CSV 文件，程序采用增量保存方式，只添加新数据。
4. **数据格式处理**：程序使用自定义的 DateEncoder 类处理日期对象，确保日期数据正确序列化。
5. **多源数据获取**：对于基本信息，程序尝试使用多种方法获取，提高数据获取成功率。
6. **随机延迟**：在每次数据请求之间添加随机延迟（2-4秒），避免请求过于频繁被 API 限制。

## 5. 使用方法

1. **处理指定股票**：
   ```bash
   python stock_company_info_collector.py --ticker 300433.SZ
   ```

2. **处理配置文件中的所有股票**：
   ```bash
   python stock_company_info_collector.py
   ```
   其中，股票列表从 config.py 中的 STOCK_TICKERS 获取。

## 6. 代码结构

- **DateEncoder 类**：自定义 JSON 编码器，处理日期对象。
- **load_existing_data 函数**：加载现有 JSON 数据。
- **save_to_csv 函数**：保存数据到 CSV 文件，支持增量保存和去重。
- **get_stock_company_info 函数**：获取单个股票的公司信息。
- **main 函数**：主函数，处理命令行参数并调用 get_stock_company_info。

该程序设计合理，结构清晰，能够有效地从多个数据源获取股票公司信息，并将数据保存到相应的文件中，为后续的分析和处理提供了便利。