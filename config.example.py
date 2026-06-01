# config.example.py
# 项目配置文件示例
# 使用方法：复制此文件为 config.py，然后填入你的实际配置

# 6开头 ：上海证券交易所（SH）
# 0开头 ：深圳证券交易所（SZ）
# 3开头 ：深圳证券交易所创业板（SZ）
# 股票代码配置
STOCK_TICKERS = {
    # 示例，请替换为你的实际股票：
    # 'example1': '002594.SZ',  # 比亚迪
    # 'example2': '688052.SH',  # 纳芯微
    # 'example3': '600313.SH',  # 农发种业
}

# 交易记录配置
# 方式一：在此直接定义
# TRADING_RECORDS = {
#     '002594.SZ': [
#         {'date': '2026-01-01', 'type': 'buy', 'price': 100.00, 'shares': 100},
#     ],
# }
# 方式二：在 trading_records.py 中定义，然后取消下面这行的注释：
# from trading_records import TRADING_RECORDS

# 历史数据日期配置
HISTORY_DATE_RANGE = {
    # '002594.SZ': {
    #     'start_date': '20240101',  # 开始日期，格式：YYYYMMDD
    #     'end_date': '20260331',    # 结束日期，格式：YYYYMMDD
    # },
}

# AI模型配置
AI_CONFIG = {
    'base_url': 'http://localhost:11434',  # Ollama本地服务地址
    'model': 'qwen3.6:35b-a3b-coding-nvfp4',  # 本地模型（请根据实际模型修改）
    'temperature': 0.3,  # 生成文本的随机性
    'max_tokens': 8192,  # 最大响应长度
    'trading_strategy': 'neutral',
    # 备用模型列表
    'fallback_models': ['qwen3.6:35b-a3b-coding-nvfp4', 'qwen3.5:397b-cloud'],
}

# 交易策略提示词
STRATEGY_PROMPTS = {
    'trend_following': '''
你当前采用趋势跟踪策略。该策略的核心思想是：只在市场有明显趋势时交易，不预测顶底，不参与震荡。
请基于当前技术数据判断：
- 是否存在明确的趋势方向？（参考 ADX、均线排列）
- 当前趋势强度是否足够支持开仓？（ADX > 25 通常视为有趋势，但允许你结合波动率和价格行为灵活判断）
- 如果已经在趋势内，判断是否已经接近趋势末期，若有持仓，分析是否需要考虑离场？
- 若不存在明确趋势，若有持仓且亏损，可以建议通过波段降低成本；若有持仓且有盈利，可以建议止盈策略，若无持仓，应建议"观望"。
''',
    'mean_reversion': '''
你当前采用均值回归策略。该策略认为价格会回归均值，在极端位置反向交易。
请基于当前技术数据判断：
- 当前价格是否处于极端区域？（RSI < 30 或 > 70，CCI < -100 或 > 100，布林带 %B < 0 或 > 1）
- 是否有反转迹象？（MACD 柱状线缩短、KDJ 金叉/死叉雏形）
- 若条件满足，可建议反向交易，但必须设置严格止损（如突破布林带外侧 1.5 倍 ATR）。
''',
    'swing': '''
你当前采用波段交易策略，持仓数天至数周，捕捉日线级别的上升/下降波段。
请基于当前日线趋势、支撑阻力、以及周线方向进行判断：
- 当前日线趋势与周线是否共振？若共振，按方向交易；若背离，降低仓位。
- 寻找回调至关键支撑/阻力位的入场点，结合 KDJ 或 MACD 的转向信号。
''',
    'neutral': '''
你当前没有预设交易策略偏好，请基于技术指标给出客观、平衡的分析。
考虑多空双方信号，明确指出当前技术状态最适合的操作方向（如有）。
可以综合趋势、动量、量能、波动率等因素，给出综合判断。
''',
}

# 数据目录配置
import os
# 获取项目根目录的绝对路径
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')  # 数据保存目录

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
