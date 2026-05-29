# check_periodic_data_updates.py 设计说明

## 1. 功能说明

`check_periodic_data_updates.py` 是一个用于检查和更新股票低频数据的脚本，主要功能包括：

- 检查股票的低频更新数据文件是否需要更新
- 根据数据类型的更新频率，判断是否需要更新
- 如果需要更新，调用相应的collector文件获取数据
- 支持增量更新，追加保存数据

## 2. 执行的程序列表

`check_periodic_data_updates.py` 会执行以下程序：

| 程序名称 | 功能 | 更新频率 |
|---------|------|---------|
| `stock_company_info_collector.py` | 获取公司基本信息，包括公司简介、行业排名等 | 30天 |
| `financial_indicators_collector.py` | 获取财务指标数据 | 90天 |
| `em_financial_collector.py` | 获取东方财富财务数据（如杜邦分析数据） | 90天 |
| `shareholder_collector.py` | 获取股东数据 | 90天 |
| `org_hold_collector.py` | 获取机构持股数据 | 90天 |
| `important_missing_data_collector.py` | 获取重要缺失数据（如分红数据） | 30天 |
| `north_fund_collector.py` | 获取北向资金数据 | 30天 |

## 3. 执行逻辑

### 3.1 主要流程

1. **检查文件是否存在**：检查指定股票的数据文件是否存在
2. **判断是否需要更新**：根据文件的更新频率（30天或90天）判断是否需要更新
3. **执行更新**：如果需要更新，调用相应的collector文件获取数据
4. **支持增量更新**：追加保存数据，避免重复数据

### 3.2 核心函数

1. **`run_command(cmd, cwd=None)`**：执行命令并返回结果
2. **`check_file_exists(file_path)`**：检查文件是否存在
3. **`get_file_modification_date(file_path)`**：获取文件的修改日期
4. **`get_latest_data_date(file_path)`**：获取文件中数据的最新日期
5. **`is_file_need_update(file_path, update_frequency_days)`**：判断文件是否需要更新
6. **`check_stock_periodic_data(ticker)`**：检查指定股票的低频更新数据文件

## 4. 更新频率

- **月度更新**（30天）：公司基本信息、重要缺失数据、北向资金
- **季度更新**（90天）：财务指标、股票财务数据、股东数据、机构持股数据

## 5. 技术实现细节

### 5.1 日期判断逻辑

1. **优先使用数据中的日期**：尝试从文件内容中提取数据的最新日期
   - 对于JSON文件，检查timestamp字段、research_reports中的日期、main_shareholders中的截至日期
   - 对于CSV文件，检查常见的日期列（REPORT_DATE, date, 截至日期, 日期）

2. **回退到文件修改日期**：如果无法从文件内容中提取日期，使用文件的修改日期

3. **判断是否需要更新**：计算当前日期与最新数据日期的差值，与更新频率比较

### 5.2 数据文件配置

```python
files_to_check = {
    # 基本信息 - 月度更新
    'company_basic': {
        'path': os.path.join(stock_dir, f"{ticker}_company_basic.json"),
        'frequency': 30,  # 30天更新一次
        'collector': f"python stock_company_info_collector.py --ticker {ticker}"
    },
    # 其他数据文件...
}
```

### 5.3 命令执行

使用`subprocess`模块执行collector脚本：

```python
def run_command(cmd, cwd=None):
    print(f"执行命令: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        print(f"命令执行结果: {result.returncode}")
        if result.stdout:
            print(f"标准输出: {result.stdout}")
        if result.stderr:
            print(f"标准错误: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"执行命令出错: {e}")
        return False
```

## 6. 应用场景

1. **定期数据更新**：通过cron等定时任务定期执行，确保数据的及时性
2. **新股票初始化**：在分析新股票时，确保所有必要的数据文件都已创建
3. **数据完整性检查**：检查数据文件是否存在，确保分析所需的数据完整

## 7. 优势与特点

1. **智能更新**：根据数据类型的不同，设置不同的更新频率
2. **增量更新**：支持追加保存数据，避免重复数据
3. **灵活性**：支持处理单只股票或批量处理所有股票
4. **可靠性**：优先使用数据中的日期进行判断，确保更新的准确性
5. **可扩展性**：易于添加新的数据类型和更新频率

## 8. 未来发展方向

1. **自动化程度提升**：增加自动检测数据更新频率的功能
2. **数据质量检查**：增加数据质量检查，确保数据的准确性
3. **并行处理**：支持并行处理多只股票，提高更新效率
4. **异常处理**：增强异常处理能力，提高脚本的稳定性
5. **配置化管理**：将数据文件配置移到配置文件中，便于管理和修改

---

通过以上设计，`check_periodic_data_updates.py` 实现了对股票低频数据的智能检查和更新，确保数据的及时性和准确性，为后续的分析提供了可靠的数据基础。