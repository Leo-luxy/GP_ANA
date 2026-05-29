# config.example.py
# 项目配置文件示例
# 使用方法：复制此文件为 config.py，然后填入你的实际配置

# 股票代码配置
# 规则：6开头=上交所(SH)，0/3开头=深交所(SZ)
STOCK_TICKERS = {
    # 示例，请替换为你的实际股票：
    # 'example1': '002594.SZ',
    # 'example2': '600313.SH',
}

# 交易记录配置
# 方式一：在此直接定义
TRADING_RECORDS = {
    # '002594.SZ': [
    #     {'date': '2026-01-01', 'type': 'buy', 'price': 100.00, 'shares': 100},
    # ],
}
# 方式二：在 trading_records.py 中定义，然后取消下面这行的注释：
# from trading_records import TRADING_RECORDS

# 历史数据日期配置
HISTORY_DATE_RANGE = {
    # '002594.SZ': {
    #     'start_date': '20240101',   # 格式：YYYYMMDD
    #     'end_date': '20260331',
    # },
}

# AI 模型配置
AI_CONFIG = {
    'base_url': 'http://localhost:11434',       # Ollama 服务地址
    'model': 'qwen3.5:35b',                     # 本地模型名称
    'temperature': 0.3,                         # 生成随机性 (0-1)
    'max_tokens': 4000,                         # 最大响应长度
    # 可选：外部大模型 API 配置
    'external_api': {
        'enabled': False,
        'api_key': '',                          # 你的 API Key
        'api_url': '',                          # API 地址
        'model': '',                            # 模型名称
    },
}

# 数据目录配置
DATA_DIR = './data'

# 技术指标配置
TECHNICAL_INDICATORS = {
    'lookback': 3,
    'ma_periods': [5, 10, 20, 50, 60],
    'vol_periods': [5, 10],
    'rsi_period': 14,
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'bb_period': 20,
    'bb_std': 2,
    'kdj_period': 9,
    'cci_period': 14,
    'roc_period': 12,
    'wr_period': 14,
    'dma_short': 10,
    'dma_long': 50,
}

# 日线策略配置
STRATEGY_CONFIG = {
    'initial_capital': 100000.0,
    'rsi_buy_threshold': 25,
    'rsi_sell_threshold': 65,
    'bb_buy_mult': 1.01,
    'bb_sell_mult': 1.01,
}

# 日线优化配置
OPTIMIZATION_CONFIG = {
    'rsi_buy_thresholds': [25, 30, 35],
    'rsi_sell_thresholds': [65, 70, 75],
    'bb_buy_mults': [0.98, 1.0, 1.02],
    'bb_sell_mults': [0.98, 1.0, 1.02],
}

# 周线策略配置
WEEKLY_STRATEGY_CONFIG = {
    'initial_capital': 100000.0,
    'rsi_buy_threshold': 25,
    'rsi_sell_threshold': 65,
    'bb_buy_mult': 1.01,
    'bb_sell_mult': 1.01,
}

# 周线优化配置
WEEKLY_OPTIMIZATION_CONFIG = {
    'rsi_buy_thresholds': [20, 25, 30, 35],
    'rsi_sell_thresholds': [60, 65, 70, 75],
    'bb_buy_mults': [0.95, 0.98, 1.0, 1.02],
    'bb_sell_mults': [0.98, 1.0, 1.02, 1.05],
}
