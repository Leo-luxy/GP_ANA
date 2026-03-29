# config.py
# 项目配置文件

# 股票代码配置
STOCK_TICKERS = {
    #范例如下：
    'baiyadi': '002594.SZ',  # 比亚迪
    'nongfazhongye': '600313.SH',  # 农发种业
    'zhaoyichuangxin': '603986.SH',  # 兆易创新
    # 可以添加更多股票代码
    # 'example': '000001.SZ'  # 示例股票
}

# 交易记录配置
TRADING_RECORDS = {
    '300469.SZ': [
        {'date': '2026-02-13', 'type': 'buy', 'price': 69.88, 'shares': 500},
        {'date': '2026-02-26', 'type': 'buy', 'price': 70.60, 'shares': 500},
        {'date': '2026-02-26', 'type': 'buy', 'price': 70.40, 'shares': 500},
        {'date': '2026-03-13', 'type': 'sell', 'price': 75.00, 'shares': 100},
        {'date': '2026-03-13', 'type': 'sell', 'price': 75.01, 'shares': 100},
        {'date': '2026-03-17', 'type': 'sell', 'price': 75.88, 'shares': 100},
        {'date': '2026-03-17', 'type': 'sell', 'price': 76.20, 'shares': 100},
        {'date': '2026-03-19', 'type': 'sell', 'price': 68.00, 'shares': 1100},
    ],
    '300433.SZ': [
        {'date': '2026-01-09', 'type': 'buy', 'price': 35.02, 'shares': 600},
        {'date': '2026-01-13', 'type': 'buy', 'price': 40.69, 'shares': 100},
        {'date': '2026-01-13', 'type': 'buy', 'price': 41.14, 'shares': 100},
        {'date': '2026-01-13', 'type': 'buy', 'price': 39.73, 'shares': 100},
        {'date': '2026-01-13', 'type': 'buy', 'price': 39.29, 'shares': 100},
        {'date': '2026-01-16', 'type': 'buy', 'price': 38.67, 'shares': 200},
        {'date': '2026-01-20', 'type': 'buy', 'price': 38.70, 'shares': 1000},
        {'date': '2026-01-20', 'type': 'buy', 'price': 38.30, 'shares': 100},
        {'date': '2026-01-30', 'type': 'buy', 'price': 36.56, 'shares': 100},
        {'date': '2026-01-30', 'type': 'buy', 'price': 36.42, 'shares': 100},
        {'date': '2026-01-30', 'type': 'buy', 'price': 36.70, 'shares': 100},
        {'date': '2026-02-09', 'type': 'buy', 'price': 35.42, 'shares': 200},
        {'date': '2026-03-04', 'type': 'buy', 'price': 32.54, 'shares': 1000},
    ],
    '603267.SH': [
        {'date': '2026-02-13', 'type': 'buy', 'price': 56.95, 'shares': 500},
        {'date': '2026-02-25', 'type': 'buy', 'price': 58.56, 'shares': 1000},
        {'date': '2026-02-27', 'type': 'buy', 'price': 67.21, 'shares': 1000},
        {'date': '2026-03-17', 'type': 'buy', 'price': 54.80, 'shares': 300},
    ],
    '603993.SH': [
        {'date': '2026-03-04', 'type': 'buy', 'price': 23.56, 'shares': 1000},
        {'date': '2026-03-17', 'type': 'buy', 'price': 19.68, 'shares': 500},
    ],
    '688052.SH': [
        {'date': '2025-12-05', 'type': 'buy', 'price': 150.16, 'shares': 200},
        {'date': '2025-12-08', 'type': 'buy', 'price': 153.58, 'shares': 200},
        {'date': '2026-01-09', 'type': 'buy', 'price': 176.50, 'shares': 310},
    ],
    '600313.SH': [
        {'date': '2026-02-11', 'type': 'buy', 'price': 7.45, 'shares': 7000},
        {'date': '2026-02-26', 'type': 'buy', 'price': 7.77, 'shares': 10000},
        {'date': '2026-03-05', 'type': 'buy', 'price': 8.56, 'shares': 5000},
        {'date': '2026-03-10', 'type': 'buy', 'price': 8.42, 'shares': 2000},
        {'date': '2026-03-16', 'type': 'sell', 'price': 9.03, 'shares': 10000},
        {'date': '2026-03-16', 'type': 'sell', 'price': 9.00, 'shares': 2000},
    ],
    # 可以添加更多股票的交易记录
}

# 历史数据日期配置
HISTORY_DATE_RANGE = {
    '300469.SZ': {
        'start_date': '20260312',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD
    },
    '300433.SZ': {
        'start_date': '20260312',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD
    },
    '603267.SH': {
        'start_date': '20240101',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD
    },
    '603993.SH': {
        'start_date': '20260312',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD         
    },
    '688052.SH': {
        'start_date': '20260312',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD
    },
    '600313.SH': {
        'start_date': '20260312',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260316',  # 结束日期，格式：YYYYMMDD
    },
    # 可以添加更多股票的日期范围
}

# AI模型配置
AI_CONFIG = {
    'base_url': 'http://localhost:11434',  # Deepseek API基础URL
    'model': 'qwen3.5:397b-cloud', # 'qwen3.5:35b',  # 使用的AI模型
    'temperature': 0.3,  # 生成文本的随机性
    'max_tokens': 4000  # 最大响应长度
}

# 数据目录配置
DATA_DIR = './data'  # 数据保存目录

# 技术指标配置
TECHNICAL_INDICATORS = {
    'lookback': 3,  # 滞后特征的天数
    'ma_periods': [5, 10, 20, 50, 60],  # 移动平均线周期
    'vol_periods': [5, 10],  # 成交量移动平均线周期
    'rsi_period': 14,  # RSI周期
    'macd_fast': 12,  # MACD快速周期
    'macd_slow': 26,  # MACD慢速周期
    'macd_signal': 9,  # MACD信号周期
    'bb_period': 20,  # 布林带周期
    'bb_std': 2,  # 布林带标准差倍数
    'kdj_period': 9,  # KDJ周期
    'cci_period': 14,  # CCI周期
    'roc_period': 12,  # ROC周期
    'wr_period': 14,  # 威廉指标周期
    'dma_short': 10,  # DMA短期周期
    'dma_long': 50,  # DMA长期周期
}

# 策略配置
STRATEGY_CONFIG = {
    'initial_capital': 100000.0,  # 初始资金
    'rsi_buy_threshold': 25,  # RSI买入阈值
    'rsi_sell_threshold': 65,  # RSI卖出阈值
    'bb_buy_mult': 1.01,  # 布林带买入倍数
    'bb_sell_mult': 1.01,  # 布林带卖出倍数
}

# 优化配置
OPTIMIZATION_CONFIG = {
    'rsi_buy_thresholds': [25, 30, 35],  # RSI买入阈值范围
    'rsi_sell_thresholds': [65, 70, 75],  # RSI卖出阈值范围
    'bb_buy_mults': [0.98, 1.0, 1.02],  # 布林带买入倍数范围
    'bb_sell_mults': [0.98, 1.0, 1.02],  # 布林带卖出倍数范围
}

# 周线策略配置
WEEKLY_STRATEGY_CONFIG = {
    'initial_capital': 100000.0,  # 初始资金
    'rsi_buy_threshold': 25,  # RSI买入阈值
    'rsi_sell_threshold': 65,  # RSI卖出阈值
    'bb_buy_mult': 1.01,  # 布林带买入倍数
    'bb_sell_mult': 1.01,  # 布林带卖出倍数
}

# 周线优化配置
WEEKLY_OPTIMIZATION_CONFIG = {
    'rsi_buy_thresholds': [20, 25, 30, 35],  # RSI买入阈值范围
    'rsi_sell_thresholds': [60, 65, 70, 75],  # RSI卖出阈值范围
    'bb_buy_mults': [0.95, 0.98, 1.0, 1.02],  # 布林带买入倍数范围
    'bb_sell_mults': [0.98, 1.0, 1.02, 1.05],  # 布林带卖出倍数范围
}