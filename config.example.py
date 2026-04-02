# config.example.py
# 项目配置文件示例
# 复制此文件为config.py并填写实际配置

# 股票代码配置
STOCK_TICKERS = {
    #范例如下：
    'example1': '002594.SZ',  # 示例股票1
    'example2': '600313.SH',  # 示例股票2
    # 可以添加更多股票代码
    # 'example': '000001.SZ'  # 示例股票
}

# 交易记录配置
TRADING_RECORDS = {
    '002594.SZ': [
        {'date': '2026-01-01', 'type': 'buy', 'price': 100.00, 'shares': 100},
        # 可以添加更多交易记录
    ],
    # 可以添加更多股票的交易记录
}

# 历史数据日期配置
HISTORY_DATE_RANGE = {
    '002594.SZ': {
        'start_date': '20240101',  # 开始日期，格式：YYYYMMDD
        'end_date': '20260331',  # 结束日期，格式：YYYYMMDD
    },
    # 可以添加更多股票的日期范围
}

# AI模型配置
AI_CONFIG = {
    'base_url': 'http://localhost:11434',  # Deepseek API基础URL
    'model': 'qwen3.5:397b-cloud', # 'qwen3.5:35b',  # 使用的AI模型
    'temperature': 0.3,  # 生成文本的随机性
    'max_tokens': 4000,  # 最大响应长度
    # 外部大模型API配置
    'external_api': {
        'enabled': False,  # 是否启用外部API
        'api_key': '',  # API密钥
        'api_url': '',  # API地址
        'model': ''  # 外部模型名称
    }
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
