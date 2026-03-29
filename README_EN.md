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
  - Content: Stock codes, position information, trading records, historical data date range, technical indicator parameters, etc.
  - Output: None

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

- **daily/