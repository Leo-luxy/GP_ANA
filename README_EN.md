# Stock Analysis System (GP_ANA)

This system is used for stock data crawling, analysis, and strategy backtesting, providing a complete stock analysis workflow.

## Execution Order

1. **Data Crawling**
   - `stock_history_collector_ta_v2.py` - Crawl historical data and calculate technical indicators
   - `stock_data_collector_ta.py` - Crawl latest trading day data and calculate technical indicators

2. **Data Basic Analysis**
   - `daily/data_analysis.py` - Data quality check and visualization analysis
   - `daily/technical_analysis.py` - Technical indicator signal analysis

3. **Strategy Analysis**
   - `daily/quantitative_strategy.py` - Quantitative strategy backtesting
   - `daily/strategy_optimization.py` - Strategy parameter optimization

4. **AI Analysis**
   - `daily/ai_model.py` - Machine learning model prediction
   - `stock_ai_local_analyzer.py` - Local AI analysis

5. **Automation**
   - `automation_system.py` - Automated data updates and strategy execution

## File Function Description

### 1. Configuration Files
- **config.py**
  - Function: Store system configuration parameters
  - Content: Stock codes, position information, trading records, historical data date range, technical indicator parameters, AI model configuration, etc.
  - Output: None
  - Note: config.py contains private information and has been added to .gitignore, please copy config.example.py to config.py and fill in the actual configuration

### 2. Data Crawling
- **stock_history_collector_ta_v2.py**
  - Function: Crawl stock historical data for a specified time period and calculate technical indicators using TA-Lib
  - Implementation principle: Prioritize using akshare to obtain domestic stock data, use yfinance as an alternative if it fails
  - Output: `./data/{ticker}/{ticker}_history.csv` - Historical data including prices and technical indicators
  - Calling method: `python stock_history_collector_ta_v2.py 300433.SZ`
    - Optional parameters:
      - `--start_date`: Start date, format: YYYYMMDD
      - `--end_date`: End date, format: YYYYMMDD
      - `--filename`: Filename to save data
      - `--output-dir`: Directory to save data

- **stock_data_collector_ta.py**
  - Function: Crawl the latest trading day's stock data and calculate technical indicators
  - Implementation principle: Use akshare to obtain the latest trading data, calculate technical indicators and save
  - Output: Update `./data/{ticker}/{ticker}_history.csv` file, add the latest trading day data
  - Calling method: `python stock_data_collector_ta.py`

- **stock_history_collector.py**
  - Function: Crawl stock historical data
  - Implementation principle: Use akshare or yfinance to obtain historical data
  - Output: `./data/{ticker}/{ticker}_history.csv` - Historical data file

- **stock_data_collector.py**
  - Function: Crawl latest stock data
  - Implementation principle: Use akshare to obtain the latest trading data
  - Output: Update `./data/{ticker}/{ticker}_history.csv` file

### 3. Data Basic Analysis (Daily)
- **daily/data_analysis.py**
  - Function: Stock data quality check and visualization analysis
  - Implementation principle: Load data, check data quality, draw price, volume and technical indicator charts
  - Output:
    - `./data/{ticker}/{ticker}_price_volume.png` - Price and volume chart
    - `./data/{ticker}/{ticker}_technical_indicators.png` - Technical indicators chart
    - `./data/{ticker}/{ticker}_bollinger_bands.png` - Bollinger Bands chart
    - `./data/{ticker}/{ticker}_correlation.png` - Technical indicators correlation heatmap
  - Calling method:
    - Default analysis for the first stock: `python daily/data_analysis.py`
    - Specify stock analysis: `python daily/data_analysis.py --ticker 300433.SZ`

- **daily/technical_analysis.py**
  - Function: Technical indicator signal analysis and effectiveness evaluation
  - Implementation principle: Calculate various technical signals, evaluate signal effectiveness, draw signal analysis charts
  - Output: `./data/{ticker}/{ticker}_signal_analysis.png` - Technical signal analysis chart
  - Calling method:
    - Default analysis for the first stock: `python daily/technical_analysis.py`
    - Specify stock analysis: `python daily/technical_analysis.py --ticker 300433.SZ`

### 4. Strategy Analysis (Daily)
- **daily/quantitative_strategy.py**
  - Function: Quantitative trading strategy backtesting based on technical indicators
  - Implementation principle: Calculate trading signals, execute strategy backtesting, calculate performance indicators
  - Output:
    - `./data/{ticker}/{ticker}_strategy_results.png` - Strategy backtesting results chart
    - `./data/{ticker}/{ticker}_trading_signals.csv` - Trading signals data file
  - Calling method:
    - Default analysis for the first stock: `python daily/quantitative_strategy.py`
    - Specify stock analysis: `python daily/quantitative_strategy.py --ticker 300433.SZ`

- **daily/strategy_optimization.py**
  - Function: Optimize quantitative trading strategy parameters to improve strategy performance
  - Implementation principle: Iterate through different parameter combinations, evaluate performance, select optimal parameters
  - Output: `./data/{ticker}/{ticker}_optimization_results.png` - Optimization results chart
  - Calling method:
    - Default analysis for the first stock: `python daily/strategy_optimization.py`
    - Specify stock analysis: `python daily/strategy_optimization.py --ticker 300433.SZ`

- **daily/daily_strategy_optimization_multistock.py**
  - Function: Multi-stock strategy optimization
  - Implementation principle: Execute strategy optimization for multiple stocks, find optimal parameter combinations
  - Output: Multi-stock optimization result files
  - Calling method: `python daily/daily_strategy_optimization_multistock.py`

### 5. AI Analysis (Daily)
- **daily/ai_model.py**
  - Function: Use machine learning models for stock price prediction and analysis
  - Implementation principle: Load data, prepare features, train model, evaluate performance
  - Output:
    - `./data/{ticker}/{ticker}_ai_predictions.png` - Prediction results chart
    - `./data/{ticker}/{ticker}_feature_importance.png` - Feature importance chart
  - Calling method:
    - Default analysis for the first stock: `python daily/ai_model.py`
    - Specify stock analysis: `python daily/ai_model.py --ticker 300433.SZ`

- **stock_ai_local_analyzer.py**
  - Function: Send stock data to local Ollama AI for analysis
  - Implementation principle: Load stock data, generate AI prompts, get AI analysis results
  - Output:
    - `./data/{ticker}/{ticker}_{timestamp}.md` - AI analysis report
    - `./data/{ticker}/{ticker}_support_resistance.png` - Support and resistance analysis chart
  - Calling method:
    - Default analysis for the first stock: `python stock_ai_local_analyzer.py`
    - Specify stock analysis: `python stock_ai_local_analyzer.py --ticker 300433.SZ`

- **daily/stock_ai_analyzer.py**
  - Function: Organize stock support data, position information and operation conditions, generate AI prompts
  - Implementation principle: Calculate support and resistance levels, organize position information, generate prompts
  - Output: None (generated prompts can be copied to web AI services)

- **daily/stock_prediction.py**
  - Function: Stock price prediction
  - Implementation principle: Use historical data and technical indicators to predict future price trends
  - Output: Prediction result charts and data files
  - Calling method: `python daily/stock_prediction.py`

### 6. Weekly Analysis
- **weekly/weekly_data_analysis.py**
  - Function: Weekly data quality check and visualization analysis
  - Implementation principle: Load weekly data, check data quality, draw charts
  - Output: Weekly analysis charts
  - Calling method: `python weekly/weekly_data_analysis.py`

- **weekly/weekly_quantitative_strategy.py**
  - Function: Weekly-based quantitative trading strategy backtesting
  - Implementation principle: Calculate weekly trading signals, execute strategy backtesting
  - Output: Weekly strategy backtesting results
  - Calling method: `python weekly/weekly_quantitative_strategy.py`

- **weekly/weekly_strategy_optimization.py**
  - Function: Weekly strategy parameter optimization
  - Implementation principle: Iterate through different parameter combinations, evaluate weekly strategy performance
  - Output: Weekly strategy optimization results
  - Calling method: `python weekly/weekly_strategy_optimization.py`

- **weekly/weekly_strategy_optimization_multistock.py**
  - Function: Multi-stock weekly strategy optimization
  - Implementation principle: Execute weekly strategy optimization for multiple stocks
  - Output: Multi-stock weekly optimization results
  - Calling method: `python weekly/weekly_strategy_optimization_multistock.py`

- **weekly/weekly_stock_analyzer.py**
  - Function: Weekly comprehensive analysis
  - Implementation principle: Perform comprehensive analysis on stock weekly data
  - Output: Weekly analysis report
  - Calling method: `python weekly/weekly_stock_analyzer.py`

- **weekly/weekly_stock_ai_local_analyzer.py**
  - Function: Weekly AI analysis
  - Implementation principle: Send weekly data to local Ollama AI for analysis
  - Output: Weekly AI analysis report
  - Calling method: `python weekly/weekly_stock_ai_local_analyzer.py`

- **weekly/weekly_stock_prediction.py**
  - Function: Weekly price prediction
  - Implementation principle: Use weekly data to predict future price trends
  - Output: Weekly prediction results
  - Calling method: `python weekly/weekly_stock_prediction.py`

- **weekly/weekly_batch_analysis.py**
  - Function: Weekly batch analysis
  - Implementation principle: Execute weekly analysis for multiple stocks
  - Output: Multi-stock weekly analysis results
  - Calling method: `python weekly/weekly_batch_analysis.py`

- **weekly/weekly_batch_analysis_complete.py**
  - Function: Weekly complete batch analysis
  - Implementation principle: Execute complete weekly analysis process for multiple stocks
  - Output: Multi-stock weekly complete analysis results
  - Calling method: `python weekly/weekly_batch_analysis_complete.py`

### 7. Tools and Automation
- **utils.py**
  - Function: General utility functions, including technical indicator calculation
  - Implementation principle: Try to use TA-Lib to calculate technical indicators, use custom implementation if it fails
  - Output: None

- **automation_system.py**
  - Function: Automated stock data updates, strategy execution and performance monitoring
  - Implementation principle: Use schedule library to set up scheduled tasks, periodically execute data updates and strategy runs
  - Output: `automation.log` - Automation system log

- **stock_company_info_v2.py**
  - Function: Obtain company basic information and financial report data from multiple authoritative financial data sources
  - Implementation principle: Obtain information from multiple data sources such as Sina Finance and East Money and integrate
  - Output:
    - `./data/{ticker}/{ticker}_{name}_company_info_v2.json` - Company information JSON file
    - `./data/{ticker}/{ticker}_{name}_company_info_v2.csv` - Company information CSV file
  - Calling method:
    - Default analysis for the first stock: `python stock_company_info_v2.py`
    - Specify stock analysis: `python stock_company_info_v2.py --ticker 300433.SZ`

- **daily/batch_analysis.py**
  - Function: Batch execute complete daily analysis process for multiple stocks
  - Implementation principle: Read all stock codes from config.py, execute analysis scripts in sequence
  - Output: Analysis result files for each stock
  - Calling method: `python daily/batch_analysis.py`

## Usage Method

1. **Configure stock information**: Set stock codes, position information and other parameters in `config.py`
2. **Crawl historical data**: Run `stock_history_collector_ta_v2.py` to crawl stock historical data
3. **Crawl latest data**: Run `stock_data_collector_ta.py` to crawl the latest trading day data
4. **Analyze data**: Run `daily/data_analysis.py` and `daily/technical_analysis.py` for basic analysis
5. **Backtest strategy**: Run `daily/quantitative_strategy.py` for strategy backtesting
6. **Optimize strategy**: Run `daily/strategy_optimization.py` to optimize strategy parameters
7. **AI analysis**:
   - Run `daily/ai_model.py` for machine learning prediction
   - Run `stock_ai_local_analyzer.py` to get AI analysis report
     - Default analysis for the first stock: `python stock_ai_local_analyzer.py`
     - Specify stock analysis: `python stock_ai_local_analyzer.py --ticker 300433.SZ`
8. **Weekly analysis**: Run the corresponding scripts in the weekly directory for weekly analysis
9. **Automated operation**: Run `automation_system.py` to set up scheduled tasks

## Dependencies

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

## Notes

- Ensure all dependencies are installed
- For domestic stocks, prioritize using akshare data source
- Technical indicator calculation requires TA-Lib library support
- Local AI analysis requires Ollama service deployment
- Automation system needs to keep running to execute scheduled tasks
- Data crawling scripts are located in the root directory, analysis scripts are located in daily and weekly directories
