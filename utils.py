# utils.py
# 通用工具函数，包含技术指标计算等

import pandas as pd
import numpy as np

# 尝试导入TA-Lib，如果失败则使用自己实现的计算方法
talib_available = False
try:
    import talib
    talib_available = True
    print("TA-Lib导入成功，将使用TA-Lib计算技术指标")
except ImportError:
    print("TA-Lib导入失败，将使用自己实现的方法计算技术指标")

def calculate_technical_indicators(data_df):
    """计算技术指标"""
    if talib_available:
        # 使用TA-Lib计算技术指标
        # 计算MA指标
        data_df['MA5'] = talib.MA(data_df['close'], timeperiod=5)
        data_df['MA10'] = talib.MA(data_df['close'], timeperiod=10)
        data_df['MA20'] = talib.MA(data_df['close'], timeperiod=20)
        data_df['MA50'] = talib.MA(data_df['close'], timeperiod=50)
        data_df['MA60'] = talib.MA(data_df['close'], timeperiod=60)
        data_df['MA120'] = talib.MA(data_df['close'], timeperiod=120)
        data_df['MA200'] = talib.MA(data_df['close'], timeperiod=200)
        
        # 计算VOL指标
        data_df['VOL5'] = talib.MA(data_df['volume'], timeperiod=5)
        data_df['VOL10'] = talib.MA(data_df['volume'], timeperiod=10)
        data_df['VOL20'] = talib.MA(data_df['volume'], timeperiod=20)
        data_df['Volume_Ratio'] = data_df['volume'] / data_df['volume'].rolling(window=5).mean()
        
        # 计算KDJ指标
        high, low, close = data_df['high'], data_df['low'], data_df['close']
        k, d = talib.STOCH(high, low, close, fastk_period=9, slowk_period=3, slowk_matype=0, slowd_period=3, slowd_matype=0)
        data_df['K'] = k
        data_df['D'] = d
        data_df['J'] = 3 * k - 2 * d
        
        # 计算MACD指标
        macd, macd_signal, macd_hist = talib.MACD(close, fastperiod=12, slowperiod=26, signalperiod=9)
        data_df['MACD'] = macd
        data_df['MACD_signal'] = macd_signal
        data_df['MACD_hist'] = macd_hist
        
        # 计算布林带
        upper, middle, lower = talib.BBANDS(close, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        data_df['BB_upper'] = upper
        data_df['BB_middle'] = middle
        data_df['BB_lower'] = lower
        data_df['BB_std'] = (upper - middle) / 2
        data_df['BB_width'] = (upper - lower) / middle * 100
        
        # 计算ATR指标
        data_df['ATR'] = talib.ATR(high, low, close, timeperiod=14)
        
        # 计算RSI指标
        data_df['RSI'] = talib.RSI(close, timeperiod=14)
        data_df['RSI_6'] = talib.RSI(close, timeperiod=6)
        data_df['RSI_24'] = talib.RSI(close, timeperiod=24)
        
        # 计算CCI指标
        data_df['CCI'] = talib.CCI(high, low, close, timeperiod=14)
        
        # 计算ROC指标
        data_df['ROC'] = talib.ROC(close, timeperiod=12)
        data_df['ROC_6'] = talib.ROC(close, timeperiod=6)
        
        # 计算OBV指标
        data_df['OBV'] = talib.OBV(close, data_df['volume'])
        
        # 计算威廉指标（WR）
        data_df['WR'] = talib.WILLR(high, low, close, timeperiod=14)
        data_df['WR_6'] = talib.WILLR(high, low, close, timeperiod=6)
        
        # 计算乖离率（BIAS）
        data_df['BIAS5'] = (data_df['close'] - data_df['MA5']) / data_df['MA5'] * 100
        data_df['BIAS10'] = (data_df['close'] - data_df['MA10']) / data_df['MA10'] * 100
        data_df['BIAS20'] = (data_df['close'] - data_df['MA20']) / data_df['MA20'] * 100
        
        # 计算DMA指标
        data_df['DMA'] = data_df['MA10'] - data_df['MA50']
        
        # 计算TRIX指标
        data_df['TRIX'] = talib.TRIX(close, timeperiod=12)
        
        # 计算VR指标
        data_df['VR'] = talib.VAR(data_df['volume'], timeperiod=28)
        
        # 计算PSY指标
        def calculate_psy(close, period=12):
            change = close.diff()
            positive_days = (change > 0).rolling(window=period).sum()
            return positive_days / period * 100
        data_df['PSY'] = calculate_psy(close)
        
        # 计算MTM指标
        data_df['MTM'] = talib.MOM(close, timeperiod=12)
        
        # 计算SAR指标
        data_df['SAR'] = talib.SAR(high, low, acceleration=0.02, maximum=0.2)
        
        # 计算ADX指标
        data_df['ADX'] = talib.ADX(high, low, close, timeperiod=14)
        
        # 计算MACD histogram的变化率
        data_df['MACD_hist_change'] = data_df['MACD_hist'].diff()
        
        # 计算价格动量
        data_df['Momentum'] = talib.MOM(close, timeperiod=10)
        
        # 计算价格与各均线的关系
        data_df['Price_MA5_Ratio'] = data_df['close'] / data_df['MA5']
        data_df['Price_MA20_Ratio'] = data_df['close'] / data_df['MA20']
        data_df['Price_MA60_Ratio'] = data_df['close'] / data_df['MA60']
        
        # 计算成交量与各均量的关系
        data_df['Volume_VOL5_Ratio'] = data_df['volume'] / data_df['VOL5']
        data_df['Volume_VOL20_Ratio'] = data_df['volume'] / data_df['VOL20']
    else:
        # 使用自己实现的方法计算技术指标
        # 计算MA指标
        data_df['MA5'] = data_df['close'].rolling(window=5).mean()
        data_df['MA10'] = data_df['close'].rolling(window=10).mean()
        data_df['MA20'] = data_df['close'].rolling(window=20).mean()
        data_df['MA50'] = data_df['close'].rolling(window=50).mean()
        data_df['MA60'] = data_df['close'].rolling(window=60).mean()
        data_df['MA120'] = data_df['close'].rolling(window=120).mean()
        data_df['MA200'] = data_df['close'].rolling(window=200).mean()
        
        # 计算VOL指标
        data_df['VOL5'] = data_df['volume'].rolling(window=5).mean()
        data_df['VOL10'] = data_df['volume'].rolling(window=10).mean()
        data_df['VOL20'] = data_df['volume'].rolling(window=20).mean()
        data_df['Volume_Ratio'] = data_df['volume'] / data_df['volume'].rolling(window=5).mean()
        
        # 计算KDJ指标
        low_list = data_df['low'].rolling(window=9).min()
        high_list = data_df['high'].rolling(window=9).max()
        rsv = (data_df['close'] - low_list) / (high_list - low_list) * 100
        data_df['K'] = rsv.ewm(com=2).mean()
        data_df['D'] = data_df['K'].ewm(com=2).mean()
        data_df['J'] = 3 * data_df['K'] - 2 * data_df['D']
        
        # 计算MACD指标
        exp1 = data_df['close'].ewm(span=12, adjust=False).mean()
        exp2 = data_df['close'].ewm(span=26, adjust=False).mean()
        data_df['MACD'] = exp1 - exp2
        data_df['MACD_signal'] = data_df['MACD'].ewm(span=9, adjust=False).mean()
        data_df['MACD_hist'] = data_df['MACD'] - data_df['MACD_signal']
        
        # 计算布林带
        data_df['BB_middle'] = data_df['close'].rolling(window=20).mean()
        data_df['BB_std'] = data_df['close'].rolling(window=20).std()
        data_df['BB_upper'] = data_df['BB_middle'] + 2 * data_df['BB_std']
        data_df['BB_lower'] = data_df['BB_middle'] - 2 * data_df['BB_std']
        data_df['BB_width'] = (data_df['BB_upper'] - data_df['BB_lower']) / data_df['BB_middle'] * 100
        
        # 计算ATR指标
        high_low = data_df['high'] - data_df['low']
        high_close = np.abs(data_df['high'] - data_df['close'].shift())
        low_close = np.abs(data_df['low'] - data_df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        data_df['ATR'] = true_range.rolling(window=14).mean()
        
        # 计算RSI指标
        delta = data_df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        data_df['RSI'] = 100 - (100 / (1 + rs))
        
        gain_6 = (delta.where(delta > 0, 0)).rolling(window=6).mean()
        loss_6 = (-delta.where(delta < 0, 0)).rolling(window=6).mean()
        rs_6 = gain_6 / loss_6
        data_df['RSI_6'] = 100 - (100 / (1 + rs_6))
        
        gain_24 = (delta.where(delta > 0, 0)).rolling(window=24).mean()
        loss_24 = (-delta.where(delta < 0, 0)).rolling(window=24).mean()
        rs_24 = gain_24 / loss_24
        data_df['RSI_24'] = 100 - (100 / (1 + rs_24))
        
        # 计算CCI指标
        typical_price = (data_df['high'] + data_df['low'] + data_df['close']) / 3
        sma = typical_price.rolling(window=20).mean()
        mad = typical_price.rolling(window=20).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
        data_df['CCI'] = (typical_price - sma) / (0.015 * mad)
        
        # 计算ROC指标
        data_df['ROC'] = (data_df['close'] - data_df['close'].shift(12)) / data_df['close'].shift(12) * 100
        data_df['ROC_6'] = (data_df['close'] - data_df['close'].shift(6)) / data_df['close'].shift(6) * 100
        
        # 计算OBV指标
        data_df['OBV'] = np.where(data_df['close'] > data_df['close'].shift(), data_df['volume'], 
                               np.where(data_df['close'] < data_df['close'].shift(), -data_df['volume'], 0)).cumsum()
        
        # 计算威廉指标（WR）
        low_list = data_df['low'].rolling(window=14).min()
        high_list = data_df['high'].rolling(window=14).max()
        data_df['WR'] = (high_list - data_df['close']) / (high_list - low_list) * 100
        
        low_list_6 = data_df['low'].rolling(window=6).min()
        high_list_6 = data_df['high'].rolling(window=6).max()
        data_df['WR_6'] = (high_list_6 - data_df['close']) / (high_list_6 - low_list_6) * 100
        
        # 计算乖离率（BIAS）
        data_df['BIAS5'] = (data_df['close'] - data_df['MA5']) / data_df['MA5'] * 100
        data_df['BIAS10'] = (data_df['close'] - data_df['MA10']) / data_df['MA10'] * 100
        data_df['BIAS20'] = (data_df['close'] - data_df['MA20']) / data_df['MA20'] * 100
        
        # 计算DMA指标
        data_df['DMA'] = data_df['MA10'] - data_df['MA50']
        
        # 计算TRIX指标
        def calculate_trix(close, period=12):
            ema1 = close.ewm(span=period, adjust=False).mean()
            ema2 = ema1.ewm(span=period, adjust=False).mean()
            ema3 = ema2.ewm(span=period, adjust=False).mean()
            trix = (ema3 - ema3.shift(1)) / ema3.shift(1) * 100
            return trix
        data_df['TRIX'] = calculate_trix(data_df['close'])
        
        # 计算PSY指标
        def calculate_psy(close, period=12):
            change = close.diff()
            positive_days = (change > 0).rolling(window=period).sum()
            return positive_days / period * 100
        data_df['PSY'] = calculate_psy(data_df['close'])
        
        # 计算MTM指标
        data_df['MTM'] = data_df['close'] - data_df['close'].shift(12)
        
        # 计算ADX指标
        def calculate_adx(high, low, close, period=14):
            # 计算真实波动幅度
            high_low = high - low
            high_close = np.abs(high - close.shift())
            low_close = np.abs(low - close.shift())
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            
            # 计算方向移动
            up_move = high - high.shift()
            down_move = low.shift() - low
            
            # 计算+DM和-DM
            plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
            minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)
            
            # 计算ATR
            atr = tr.rolling(window=period).mean()
            
            # 计算+DI和-DI
            plus_di = (plus_dm.rolling(window=period).mean() / atr) * 100
            minus_di = (minus_dm.rolling(window=period).mean() / atr) * 100
            
            # 计算DX
            dx = (np.abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
            
            # 计算ADX
            adx = dx.rolling(window=period).mean()
            return adx
        data_df['ADX'] = calculate_adx(data_df['high'], data_df['low'], data_df['close'])
        
        # 计算MACD histogram的变化率
        data_df['MACD_hist_change'] = data_df['MACD_hist'].diff()
        
        # 计算价格动量
        data_df['Momentum'] = data_df['close'] - data_df['close'].shift(10)
        
        # 计算价格与各均线的关系
        data_df['Price_MA5_Ratio'] = data_df['close'] / data_df['MA5']
        data_df['Price_MA20_Ratio'] = data_df['close'] / data_df['MA20']
        data_df['Price_MA60_Ratio'] = data_df['close'] / data_df['MA60']
        
        # 计算成交量与各均量的关系
        data_df['Volume_VOL5_Ratio'] = data_df['volume'] / data_df['VOL5']
        data_df['Volume_VOL20_Ratio'] = data_df['volume'] / data_df['VOL20']
    
    # 计算VWAP指标（无论是否使用TA-Lib都计算）
    data_df['VWAP'] = (data_df['close'] * data_df['volume']).cumsum() / data_df['volume'].cumsum()
    
    # 计算历史波动率（无论是否使用TA-Lib都计算）
    data_df['Volatility'] = data_df['close'].pct_change().rolling(window=20).std() * np.sqrt(252)
    
    return data_df
