# 股票分析系统

本系统用于股票数据的抓取、分析和策略回测，提供完整的股票分析流程。

## 执行顺序

1. **数据抓取**
   - `stock_history_collector_ta_v2.py` - 抓取历史数据并计算技术指标
   - `stock_data_collector_ta.py` - 抓取最新交易日数据并计算技术指标

2. **数据基础分析**
   - `daily/data_analysis.py` - 数据质量检查和可视化分析
   - `daily/technical_analysis.py` - 技术指标信号分析

3. **策略分析**
   - `daily/quantitative_strategy.py` - 量化策略回测
   - `daily/strategy_optimization.py` - 策略参数优化

4. **AI分析**
   - `daily/ai_model.py` - 机器学习模型预测
   - `stock_ai_local_analyzer.py` - 本地AI分析

5. **自动化**
   - `automation_system.py` - 自动化数据更新和策略运行

## 文件功能说明

### 1. 配置文件
- **config.py**
  - 功能：存储系统配置参数
  - 内容：股票代码、持仓情况、交易记录、历史数据日期范围、技术指标参数、AI模型配置等
  - 产出物：无
  - 注意：config.py包含私人信息，已被添加到.gitignore中，请复制config.example.py为config.py并填写实际配置

### 2. 数据抓取
- **stock_history_collector_ta_v2.py**
  - 功能：抓取指定时间段的股票历史数据并使用TA-Lib计算技术指标
  - 实现原理：优先使用akshare获取国内股票数据，失败后使用yfinance作为备选
  - 产出物：`./data/{ticker}/{ticker}_history.csv` - 包含价格和技术指标的历史数据
  - 调用方法：`python stock_history_collector_ta_v2.py 300433.SZ`
    - 可选参数：
      - `--start_date`：开始日期，格式：YYYYMMDD
      - `--end_date`：结束日期，格式：YYYYMMDD
      - `--filename`：保存数据的文件名
      - `--output-dir`：保存数据的目录

- **stock_data_collector_ta.py**
  - 功能：抓取最新交易日的股票数据并计算技术指标
  - 实现原理：使用akshare获取最新交易数据，计算技术指标并保存
  - 产出物：更新 `./data/{ticker}/{ticker}_history.csv` 文件，添加最新交易日数据
  - 调用方法：`python stock_data_collector_ta.py`

- **stock_history_collector.py**
  - 功能：抓取股票历史数据
  - 实现原理：使用akshare或yfinance获取历史数据
  - 产出物：`./data/{ticker}/{ticker}_history.csv` - 历史数据文件

- **stock_data_collector.py**
  - 功能：抓取最新股票数据
  - 实现原理：使用akshare获取最新交易数据
  - 产出物：更新 `./data/{ticker}/{ticker}_history.csv` 文件

### 3. 数据基础分析 (日线)
- **daily/data_analysis.py**
  - 功能：股票数据质量检查和可视化分析
  - 实现原理：加载数据，检查数据质量，绘制价格、成交量和技术指标图表
  - 产出物：
    - `./data/{ticker}/{ticker}_price_volume.png` - 价格和成交量图表
    - `./data/{ticker}/{ticker}_technical_indicators.png` - 技术指标图表
    - `./data/{ticker}/{ticker}_bollinger_bands.png` - 布林带图表
    - `./data/{ticker}/{ticker}_correlation.png` - 技术指标相关性热力图
  - 调用方法：
    - 默认分析第一只股票：`python daily/data_analysis.py`
    - 指定股票分析：`python daily/data_analysis.py --ticker 300433.SZ`

- **daily/technical_analysis.py**
  - 功能：技术指标信号分析和有效性评估
  - 实现原理：计算各种技术信号，评估信号有效性，绘制信号分析图表
  - 产出物：`./data/{ticker}/{ticker}_signal_analysis.png` - 技术信号分析图表
  - 调用方法：
    - 默认分析第一只股票：`python daily/technical_analysis.py`
    - 指定股票分析：`python daily/technical_analysis.py --ticker 300433.SZ`

### 4. 策略分析 (日线)
- **daily/quantitative_strategy.py**
  - 功能：基于技术指标的量化交易策略回测
  - 实现原理：计算交易信号，执行策略回测，计算性能指标
  - 产出物：
    - `./data/{ticker}/{ticker}_strategy_results.png` - 策略回测结果图表
    - `./data/{ticker}/{ticker}_trading_signals.csv` - 交易信号数据文件
  - 调用方法：
    - 默认分析第一只股票：`python daily/quantitative_strategy.py`
    - 指定股票分析：`python daily/quantitative_strategy.py --ticker 300433.SZ`

- **daily/strategy_optimization.py**
  - 功能：优化量化交易策略的参数，提高策略性能
  - 实现原理：遍历不同参数组合，评估性能，选择最佳参数
  - 产出物：`./data/{ticker}/{ticker}_optimization_results.png` - 优化结果图表
  - 调用方法：
    - 默认分析第一只股票：`python daily/strategy_optimization.py`
    - 指定股票分析：`python daily/strategy_optimization.py --ticker 300433.SZ`

- **daily/daily_strategy_optimization_multistock.py**
  - 功能：多股票策略优化
  - 实现原理：对多只股票执行策略优化，寻找最佳参数组合
  - 产出物：多股票优化结果文件
  - 调用方法：`python daily/daily_strategy_optimization_multistock.py`

### 5. AI分析 (日线)
- **daily/ai_model.py**
  - 功能：使用机器学习模型对股票价格进行预测和分析
  - 实现原理：加载数据，准备特征，训练模型，评估性能
  - 产出物：
    - `./data/{ticker}/{ticker}_ai_predictions.png` - 预测结果图表
    - `./data/{ticker}/{ticker}_feature_importance.png` - 特征重要性图表
  - 调用方法：
    - 默认分析第一只股票：`python daily/ai_model.py`
    - 指定股票分析：`python daily/ai_model.py --ticker 300433.SZ`

- **stock_ai_local_analyzer.py**
  - 功能：将股票数据发送给AI进行分析，支持外部大模型API和本地Ollama
  - 实现原理：加载股票数据，生成AI提示词，优先使用外部API，失败后回退到本地Ollama
  - 产出物：
    - `./data/{ticker}/{ticker}_{timestamp}.md` - AI分析报告
    - `./data/{ticker}/{ticker}_support_resistance.png` - 支撑阻力位分析图表
  - 调用方法：
    - 默认分析第一只股票：`python stock_ai_local_analyzer.py`
    - 指定股票分析：`python stock_ai_local_analyzer.py --ticker 300433.SZ`
  - 外部API配置：在config.py的AI_CONFIG中设置external_api参数

- **daily/stock_ai_analyzer.py**
  - 功能：整理股票支撑数据、持仓情况和操作情况，生成AI提示词
  - 实现原理：计算支撑阻力位，整理持仓信息，生成提示词
  - 产出物：无（生成的提示词可复制到网页AI服务）

- **daily/stock_prediction.py**
  - 功能：股票价格预测
  - 实现原理：使用历史数据和技术指标预测未来价格走势
  - 产出物：预测结果图表和数据文件
  - 调用方法：`python daily/stock_prediction.py`

### 6. 周线分析
- **weekly/weekly_data_analysis.py**
  - 功能：周线数据质量检查和可视化分析
  - 实现原理：加载周线数据，检查数据质量，绘制图表
  - 产出物：周线分析图表
  - 调用方法：`python weekly/weekly_data_analysis.py`

- **weekly/weekly_quantitative_strategy.py**
  - 功能：基于周线的量化交易策略回测
  - 实现原理：计算周线交易信号，执行策略回测
  - 产出物：周线策略回测结果
  - 调用方法：`python weekly/weekly_quantitative_strategy.py`

- **weekly/weekly_strategy_optimization.py**
  - 功能：周线策略参数优化
  - 实现原理：遍历不同参数组合，评估周线策略性能
  - 产出物：周线策略优化结果
  - 调用方法：`python weekly/weekly_strategy_optimization.py`

- **weekly/weekly_strategy_optimization_multistock.py**
  - 功能：多股票周线策略优化
  - 实现原理：对多只股票执行周线策略优化
  - 产出物：多股票周线优化结果
  - 调用方法：`python weekly/weekly_strategy_optimization_multistock.py`

- **weekly/weekly_stock_analyzer.py**
  - 功能：周线综合分析
  - 实现原理：对股票周线数据进行综合分析
  - 产出物：周线分析报告
  - 调用方法：`python weekly/weekly_stock_analyzer.py`

- **weekly/weekly_stock_ai_local_analyzer.py**
  - 功能：周线AI分析，支持外部大模型API和本地Ollama
  - 实现原理：将周线数据发送给AI进行分析，优先使用外部API，失败后回退到本地Ollama
  - 产出物：周线AI分析报告
  - 调用方法：`python weekly/weekly_stock_ai_local_analyzer.py`
  - 外部API配置：在config.py的AI_CONFIG中设置external_api参数

- **weekly/weekly_stock_prediction.py**
  - 功能：周线价格预测
  - 实现原理：使用周线数据预测未来价格走势
  - 产出物：周线预测结果
  - 调用方法：`python weekly/weekly_stock_prediction.py`

- **weekly/weekly_batch_analysis.py**
  - 功能：周线批量分析
  - 实现原理：对多只股票执行周线分析
  - 产出物：多股票周线分析结果
  - 调用方法：`python weekly/weekly_batch_analysis.py`

- **weekly/weekly_batch_analysis_complete.py**
  - 功能：周线完整批量分析
  - 实现原理：对多只股票执行完整的周线分析流程
  - 产出物：多股票周线完整分析结果
  - 调用方法：`python weekly/weekly_batch_analysis_complete.py`

### 7. 工具和自动化
- **utils.py**
  - 功能：通用工具函数，包含技术指标计算
  - 实现原理：尝试使用TA-Lib计算技术指标，失败后使用自定义实现
  - 产出物：无

- **automation_system.py**
  - 功能：自动化股票数据更新、策略运行和性能监控
  - 实现原理：使用schedule库设置定时任务，定期执行数据更新和策略运行
  - 产出物：`automation.log` - 自动化系统日志

- **stock_company_info_v2.py**
  - 功能：从多个权威金融数据源获取公司基本信息和财报数据
  - 实现原理：从新浪财经、东方财富等多个数据源获取信息并融合
  - 产出物：
    - `./data/{ticker}/{ticker}_{name}_company_info_v2.json` - 公司信息JSON文件
    - `./data/{ticker}/{ticker}_{name}_company_info_v2.csv` - 公司信息CSV文件
  - 调用方法：
    - 默认分析第一只股票：`python stock_company_info_v2.py`
    - 指定股票分析：`python stock_company_info_v2.py --ticker 300433.SZ`

- **daily/batch_analysis.py**
  - 功能：批量对多只股票执行完整的日线分析流程
  - 实现原理：从config.py中读取所有股票代码，依次执行分析脚本
  - 产出物：各股票的分析结果文件
  - 调用方法：`python daily/batch_analysis.py`

## 使用方法

1. **配置股票信息**：在`config.py`中设置股票代码、持仓情况等参数
2. **抓取历史数据**：运行`stock_history_collector_ta_v2.py`抓取股票历史数据
3. **抓取最新数据**：运行`stock_data_collector_ta.py`抓取最新交易日数据
4. **分析数据**：运行`daily/data_analysis.py`和`daily/technical_analysis.py`进行基础分析
5. **回测策略**：运行`daily/quantitative_strategy.py`进行策略回测
6. **优化策略**：运行`daily/strategy_optimization.py`优化策略参数
7. **AI分析**：
   - 运行`daily/ai_model.py`进行机器学习预测
   - 运行`stock_ai_local_analyzer.py`获取AI分析报告
     - 默认分析第一只股票：`python stock_ai_local_analyzer.py`
     - 指定股票分析：`python stock_ai_local_analyzer.py --ticker 300433.SZ`
   - **外部大模型API配置**：
     - 在config.py的AI_CONFIG中设置external_api参数
     - 示例配置：
       ```python
       'external_api': {
           'enabled': True,  # 启用外部API
           'api_key': 'your_api_key_here',  # 你的API密钥
           'api_url': 'https://api.openai.com/v1/chat/completions',  # API地址（示例为OpenAI）
           'model': 'gpt-4'  # 模型名称
       }
       ```
     - 支持任何符合OpenAI API格式的大模型服务
8. **周线分析**：运行weekly目录下的相应脚本进行周线分析
9. **自动化运行**：运行`automation_system.py`设置定时任务

## 依赖项

- pandas
- numpy
- matplotlib
- seaborn
- yfinance
- akshare
- TA-Lib
- scikit-learn
- schedule
- requests
- pyperclip
- APScheduler

## 注意事项

- 确保已安装所有依赖项
- 对于国内股票，优先使用akshare数据源
- 技术指标计算需要TA-Lib库支持
- 本地AI分析需要部署Ollama服务
- 自动化系统需要保持运行状态以执行定时任务
- 数据抓取脚本位于根目录，分析脚本分别位于daily和weekly目录