# stock_quantitative_analyzer.py
# 功能：实现资金驱动的波动率突破策略，进行量化分析并保存结果
# 实现原理：
# 1. 读取本地股票数据
# 2. 计算各项技术指标
# 3. 按照策略规则筛选股票
# 4. 生成交易信号并保存结果
# 5. 提供回测功能和风险评估

import pandas as pd
import os
import sys
import argparse
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import calculate_technical_indicators
from config import DATA_DIR, STRATEGY_CONFIG


def calculate_ema(data_df, periods=[20, 60, 120]):
    """计算指数移动平均线(EMA)"""
    for period in periods:
        data_df[f'EMA{period}'] = data_df['close'].ewm(span=period, adjust=False).mean()
    return data_df


def calculate_obv_ma(data_df):
    """计算OBV及其移动平均线"""
    # 确保OBV已经计算
    if 'OBV' not in data_df.columns:
        # 计算OBV
        data_df['OBV'] = np.where(data_df['close'] > data_df['close'].shift(), data_df['volume'], 
                               np.where(data_df['close'] < data_df['close'].shift(), -data_df['volume'], 0)).cumsum()
    
    # 计算OBV的移动平均线
    data_df['OBV_MA5'] = data_df['OBV'].rolling(window=5).mean()
    data_df['OBV_MA20'] = data_df['OBV'].rolling(window=20).mean()
    
    # 计算OBV创新高
    data_df['OBV_20d_high'] = data_df['OBV'].rolling(window=20).max()
    data_df['OBV_new_high'] = data_df['OBV'] == data_df['OBV_20d_high']
    
    return data_df


def calculate_keltner_channel(data_df):
    """计算肯特纳通道"""
    # 确保ATR已经计算
    if 'ATR' not in data_df.columns:
        # 计算ATR
        high_low = data_df['high'] - data_df['low']
        high_close = np.abs(data_df['high'] - data_df['close'].shift())
        low_close = np.abs(data_df['low'] - data_df['close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = ranges.max(axis=1)
        data_df['ATR'] = true_range.rolling(window=14).mean()
    
    # 确保EMA20已经计算
    if 'EMA20' not in data_df.columns:
        data_df['EMA20'] = data_df['close'].ewm(span=20, adjust=False).mean()
    
    # 计算肯特纳通道
    data_df['KC_mid'] = data_df['EMA20']
    data_df['KC_upper'] = data_df['EMA20'] + 1.5 * data_df['ATR']
    data_df['KC_lower'] = data_df['EMA20'] - 1.5 * data_df['ATR']
    
    # 计算ATR 5日均值
    data_df['ATR_5d_mean'] = data_df['ATR'].rolling(window=5).mean()
    data_df['ATR_expanding'] = data_df['ATR'] > data_df['ATR_5d_mean']
    
    return data_df


def calculate_rps(data_df, period=120):
    """计算相对强弱指数(RPS)"""
    # 计算120日涨幅
    data_df['120d_return'] = (data_df['close'] / data_df['close'].shift(period) - 1) * 100
    
    # 这里简化计算，实际RPS需要与其他股票比较
    # 这里使用股票自身的收益率作为简化版RPS
    data_df['RPS'] = data_df['120d_return']
    
    # 计算RPS排名（简化版）
    data_df['RPS_rank'] = data_df['RPS'].rank(pct=True) * 100
    
    return data_df


def calculate_macd_analysis(data_df):
    """计算MACD相关分析"""
    # 确保MACD已经计算
    if 'MACD' not in data_df.columns or 'MACD_signal' not in data_df.columns:
        # 计算MACD
        exp1 = data_df['close'].ewm(span=12, adjust=False).mean()
        exp2 = data_df['close'].ewm(span=26, adjust=False).mean()
        data_df['MACD'] = exp1 - exp2
        data_df['MACD_signal'] = data_df['MACD'].ewm(span=9, adjust=False).mean()
    
    # 计算MACD柱状图
    data_df['MACD_hist'] = data_df['MACD'] - data_df['MACD_signal']
    
    # MACD金叉死叉
    data_df['MACD_crossover'] = 0
    data_df.loc[data_df['MACD'] > data_df['MACD_signal'], 'MACD_crossover'] = 1
    data_df.loc[data_df['MACD'] < data_df['MACD_signal'], 'MACD_crossover'] = -1
    
    # MACD趋势
    data_df['MACD_trend'] = data_df['MACD'].diff()
    
    return data_df


def calculate_volatility_analysis(data_df):
    """计算波动率分析"""
    # 计算30日波动率
    data_df['30d_volatility'] = data_df['close'].pct_change().rolling(window=30).std() * np.sqrt(252)
    
    # 计算波动率变化
    data_df['volatility_change'] = data_df['30d_volatility'].diff()
    
    # 计算波动率突破
    data_df['volatility_breakout'] = (data_df['30d_volatility'] > data_df['30d_volatility'].shift(5)).astype(int)
    
    return data_df


def check_divergence(data_df):
    """检测OBV与价格的背驰"""
    # 检测顶背离：价格创新高但OBV未创新高
    data_df['price_high'] = data_df['close'].rolling(window=20).max()
    data_df['obv_high'] = data_df['OBV'].rolling(window=20).max()
    
    data_df['price_new_high'] = data_df['close'] == data_df['price_high']
    data_df['obv_new_high'] = data_df['OBV'] == data_df['obv_high']
    
    # 顶背离：价格创新高但OBV未创新高
    data_df['top_divergence'] = data_df['price_new_high'] & (~data_df['obv_new_high'])
    
    # 底背离：价格创新低但OBV未创新低（作为参考）
    data_df['price_low'] = data_df['close'].rolling(window=20).min()
    data_df['obv_low'] = data_df['OBV'].rolling(window=20).min()
    
    data_df['price_new_low'] = data_df['close'] == data_df['price_low']
    data_df['obv_new_low'] = data_df['OBV'] == data_df['obv_low']
    
    data_df['bottom_divergence'] = data_df['price_new_low'] & (~data_df['obv_new_low'])
    
    return data_df


def calculate_risk_metrics(data_df):
    """计算风险指标"""
    # 计算最大回撤
    data_df['cumulative_return'] = (1 + data_df['close'].pct_change()).cumprod()
    data_df['peak'] = data_df['cumulative_return'].cummax()
    data_df['drawdown'] = (data_df['cumulative_return'] - data_df['peak']) / data_df['peak'] * 100
    data_df['max_drawdown'] = data_df['drawdown'].rolling(window=252).min()
    
    # 计算夏普比率（假设无风险利率为3%）
    data_df['daily_return'] = data_df['close'].pct_change()
    data_df['sharpe_ratio'] = ((data_df['daily_return'].rolling(window=252).mean() - 0.03/252) / 
                            (data_df['daily_return'].rolling(window=252).std() * np.sqrt(252)))
    
    return data_df


def read_local_data(ticker, input_dir=None):
    """读取本地股票数据文件"""
    # 确定输入目录
    if input_dir:
        base_dir = input_dir
    else:
        base_dir = DATA_DIR
    
    # 构建文件路径
    stock_dir = os.path.join(base_dir, ticker)
    file_path = os.path.join(stock_dir, f"{ticker}_qfq.csv")
    
    # 检查文件是否存在
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return None
    
    # 读取文件
    try:
        df = pd.read_csv(file_path)
        print(f"读取本地数据成功，共 {len(df)} 条记录")
        
        # 确保必要的列存在
        required_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
        for col in required_columns:
            if col not in df.columns:
                print(f"缺少必要的列: {col}")
                return None
        
        # 按日期升序排序
        df = df.sort_values('date', ascending=True)
        
        return df
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return None


def analyze_stock(ticker, input_dir=None, backtest=False):
    """分析单个股票"""
    # 读取数据
    df = read_local_data(ticker, input_dir)
    if df is None:
        return None, None
    
    # 计算技术指标
    print(f"计算技术指标...")
    df = calculate_technical_indicators(df)
    
    # 补充计算EMA
    df = calculate_ema(df)
    
    # 计算OBV相关指标
    df = calculate_obv_ma(df)
    
    # 计算肯特纳通道
    df = calculate_keltner_channel(df)
    
    # 计算RPS
    df = calculate_rps(df)
    
    # 计算MACD分析
    df = calculate_macd_analysis(df)
    
    # 计算波动率分析
    df = calculate_volatility_analysis(df)
    
    # 检测背驰
    df = check_divergence(df)
    
    # 计算风险指标
    df = calculate_risk_metrics(df)
    
    # 筛选最后一天的数据进行分析
    latest_data = df.iloc[-1]
    
    # 第一层：基础股票池（优中选优）
    condition1 = latest_data['close'] > latest_data['EMA20'] > latest_data['EMA60'] > latest_data['EMA120']
    condition2 = latest_data['ADX'] > 23
    condition3 = latest_data['RPS'] > 80
    
    # 第二层：资金验证（量价配合）
    condition4 = latest_data['OBV_MA5'] > latest_data['OBV_MA20']
    condition5 = latest_data['OBV_new_high']
    
    # 第三层：精确起爆点（波动率突破）
    condition6 = latest_data['close'] > latest_data['KC_upper']
    condition7 = latest_data['ATR_expanding']
    
    # 第四层：MACD验证
    condition8 = latest_data['MACD_crossover'] == 1
    condition9 = latest_data['MACD_hist'] > 0
    
    # 第五层：内部动能验证
    condition10 = latest_data['RSI'] > 50  # RSI(14) > 50
    
    # 第六层：风险控制
    condition11 = latest_data['max_drawdown'] > -30  # 最大回撤不超过30%
    condition12 = not np.isnan(latest_data['sharpe_ratio']) and latest_data['sharpe_ratio'] > 0
    
    # 综合条件
    buy_signal = all([condition1, condition2, condition3, condition4, condition5, condition6, condition7, condition8, condition9, condition10, condition11, condition12])
    
    # 构建分析结果
    result = {
        'ticker': ticker,
        'date': latest_data['date'],
        'close': latest_data['close'],
        'EMA20': latest_data['EMA20'],
        'EMA60': latest_data['EMA60'],
        'EMA120': latest_data['EMA120'],
        'ADX': latest_data['ADX'],
        'RPS': latest_data['RPS'],
        'RPS_rank': latest_data['RPS_rank'],
        'OBV_MA5': latest_data['OBV_MA5'],
        'OBV_MA20': latest_data['OBV_MA20'],
        'OBV_new_high': latest_data['OBV_new_high'],
        'KC_upper': latest_data['KC_upper'],
        'ATR_expanding': latest_data['ATR_expanding'],
        'MACD': latest_data['MACD'],
        'MACD_signal': latest_data['MACD_signal'],
        'MACD_hist': latest_data['MACD_hist'],
        'MACD_crossover': latest_data['MACD_crossover'],
        '30d_volatility': latest_data['30d_volatility'],
        'volatility_breakout': latest_data['volatility_breakout'],
        'max_drawdown': latest_data['max_drawdown'],
        'sharpe_ratio': latest_data['sharpe_ratio'],
        'buy_signal': buy_signal
    }
    
    # 如果需要回测，执行回测
    if backtest:
        backtest_result = backtest_strategy(df, ticker)
        result.update(backtest_result)
    
    return result, df


def backtest_strategy(df, ticker):
    """回测策略"""
    print(f"回测股票: {ticker}")
    
    # 初始化回测参数
    initial_capital = STRATEGY_CONFIG.get('initial_capital', 100000)
    cash = initial_capital
    position = 0
    portfolio_value = []
    trades = []
    buy_signals = []
    sell_signals = []
    
    # 加仓相关参数
    max_positions = 4  # 最大持仓份数
    position_count = 0  # 当前持仓份数
    last_buy_price = 0  # 上一次买入价格
    last_buy_date = None  # 上一次买入日期
    last_adx = 0  # 上一次买入时的ADX值
    
    # 金字塔式加仓比例
    position_ratios = [0.5, 0.25, 0.15, 0.1]  # 50%, 25%, 15%, 10%
    
    # 遍历每一个交易日
    for i in range(1, len(df)):
        date = df['date'].iloc[i]
        close_price = df['close'].iloc[i]
        current_adx = df['ADX'].iloc[i]
        
        # 计算信号
        # 买入条件
        condition1 = df['close'].iloc[i] > df['EMA20'].iloc[i] > df['EMA60'].iloc[i] > df['EMA120'].iloc[i]
        condition2 = df['ADX'].iloc[i] > 23
        condition3 = df['RPS'].iloc[i] > 80
        condition4 = df['OBV_MA5'].iloc[i] > df['OBV_MA20'].iloc[i]
        condition5 = df['OBV_new_high'].iloc[i]
        condition6 = df['close'].iloc[i] > df['KC_upper'].iloc[i]
        condition7 = df['ATR_expanding'].iloc[i]
        condition8 = df['MACD_crossover'].iloc[i] == 1
        condition9 = df['MACD_hist'].iloc[i] > 0
        condition10 = df['RSI'].iloc[i] > 50  # RSI(14) > 50
        
        buy_signal = all([condition1, condition2, condition3, condition4, condition5, condition6, condition7, condition8, condition9, condition10])
        
        # 记录买入信号及判据 - 移到实际交易执行时记录
        
        # 卖出条件
        # 1. 主离场信号：价格跌破EMA60
        # 2. 移动止损：收盘价低于持仓以来最高价乘以 (1 - 1.5 * ATR)
        ema60_break = False
        trailing_stop = False
        
        if position > 0:
            # 主离场信号：价格跌破EMA60
            ema60_break = df['close'].iloc[i] < df['EMA60'].iloc[i]
            
            # 计算持仓以来的最高价
            if trades and trades[-1]['type'] == 'buy':
                buy_index = df[df['date'] == trades[-1]['date']].index[0]
                highest_price = df['high'].iloc[buy_index:i+1].max()
                current_atr = df['ATR'].iloc[i]
                # 移动止损：收盘价低于持仓以来最高价乘以 (1 - 1.5 * ATR)
                trailing_stop = close_price < highest_price * (1 - 1.5 * current_atr / close_price)
        
        sell_signal = ema60_break or trailing_stop
        
        # 记录卖出信号及判据
        if sell_signal and position > 0:
            sell_signals.append({
                'date': date,
                'price': close_price,
                'exit_type': 'ema60_break' if ema60_break else 'trailing_stop',
                'conditions': {
                    'ema60_break': ema60_break,
                    'trailing_stop': trailing_stop
                }
            })
        
        # 检查是否在同一天有卖出信号
        same_day_sell = False
        if trades and trades[-1]['type'] == 'sell' and trades[-1]['date'] == date:
            same_day_sell = True
        
        # 执行交易
        if buy_signal and not same_day_sell:
            # 金字塔式加仓逻辑
            if position == 0:
                # 首次建仓
                position_count = 1
                capital_to_use = initial_capital * position_ratios[0]
                shares = int(capital_to_use / close_price)
                if shares > 0:
                    position = shares
                    cash -= shares * close_price
                    last_buy_price = close_price
                    last_buy_date = date
                    last_adx = current_adx
                    # 计算当前仓位比例
                    current_position_value = position * close_price
                    total_capital = cash + current_position_value
                    position_ratio = (current_position_value / total_capital) * 100
                    
                    trades.append({
                        'date': date,
                        'type': 'buy',
                        'price': close_price,
                        'shares': shares,
                        'position_count': position_count,
                        'ratio': position_ratios[0],
                        'total_position': position,
                        'position_ratio': position_ratio
                    })
                    # 只在实际执行交易时记录买入信号
                    buy_signals.append({
                        'date': date,
                        'price': close_price,
                        'shares': shares,
                        'position': position,
                        'position_ratio': position_ratio,
                        'conditions': {
                            'close_above_EMAs': condition1,
                            'ADX_above_23': condition2,
                            'RPS_above_80': condition3,
                            'OBV_MA5_above_MA20': condition4,
                            'OBV_new_high': condition5,
                            'close_above_KC_upper': condition6,
                            'ATR_expanding': condition7,
                            'MACD_crossover': condition8,
                            'MACD_hist_positive': condition9,
                            'RSI_above_50': condition10
                        }
                    })
            elif position_count < max_positions:
                # 加仓条件检查
                # 1. 价格相对前期加仓点上涨
                price_increase = close_price > last_buy_price
                # 2. ADX继续上升
                adx_increasing = current_adx > last_adx
                # 3. 距离上一次加仓有一定时间间隔（至少1个交易日）
                time_interval = (i - df[df['date'] == last_buy_date].index[0]) >= 1
                
                # 4. 价格回调确认支撑条件
                # 4.1 计算近期高点（过去10个交易日）
                recent_high = df['high'].iloc[max(0, i-10):i+1].max()
                # 4.2 检查价格是否从近期高点回撤了一定比例（3%~5%）
                price_retracement = (recent_high - close_price) / recent_high * 100
                retracement_condition = 3 <= price_retracement <= 5
                
                # 4.3 检查价格是否回踩到重要均线并获得支撑
                # 确保EMA10和EMA20已计算
                if 'EMA10' not in df.columns:
                    df['EMA10'] = df['close'].ewm(span=10, adjust=False).mean()
                
                # 价格回踩到EMA10或EMA20并获得支撑
                ema10_support = abs(close_price - df['EMA10'].iloc[i]) / close_price * 100 <= 1
                ema20_support = abs(close_price - df['EMA20'].iloc[i]) / close_price * 100 <= 1
                ma_support_condition = ema10_support or ema20_support
                
                # 回调确认支撑条件：满足回撤比例或均线支撑
                retracement_confirmation = retracement_condition or ma_support_condition
                
                if price_increase and adx_increasing and time_interval and retracement_confirmation:
                    # 加仓
                    position_count += 1
                    capital_to_use = initial_capital * position_ratios[position_count-1]
                    shares = int(capital_to_use / close_price)
                    if shares > 0:
                        position += shares
                        cash -= shares * close_price
                        last_buy_price = close_price
                        last_buy_date = date
                        last_adx = current_adx
                        # 计算当前仓位比例
                        current_position_value = position * close_price
                        total_capital = cash + current_position_value
                        position_ratio = (current_position_value / total_capital) * 100
                        
                        trades.append({
                            'date': date,
                            'type': 'buy',
                            'price': close_price,
                            'shares': shares,
                            'position_count': position_count,
                            'ratio': position_ratios[position_count-1],
                            'total_position': position,
                            'position_ratio': position_ratio
                        })
                        # 只在实际执行交易时记录买入信号
                        buy_signals.append({
                            'date': date,
                            'price': close_price,
                            'shares': shares,
                            'position': position,
                            'position_ratio': position_ratio,
                            'conditions': {
                                'close_above_EMAs': condition1,
                                'ADX_above_23': condition2,
                                'RPS_above_80': condition3,
                                'OBV_MA5_above_MA20': condition4,
                                'OBV_new_high': condition5,
                                'close_above_KC_upper': condition6,
                                'ATR_expanding': condition7,
                                'MACD_crossover': condition8,
                                'MACD_hist_positive': condition9,
                                'RSI_above_50': condition10
                            }
                        })
        elif sell_signal and position > 0:
            # 卖出全部持仓
            cash += position * close_price
            trades.append({
                'date': date,
                'type': 'sell',
                'price': close_price,
                'shares': position,
                'exit_type': 'ema60_break' if ema60_break else 'trailing_stop'
            })
            position = 0
            position_count = 0
            last_buy_price = 0
            last_buy_date = None
            last_adx = 0
        
        # 计算当前portfolio价值
        current_value = cash + (position * close_price)
        portfolio_value.append(current_value)
    
    # 回测结束时，如果还有持仓，卖出所有持仓
    if position > 0:
        final_price = df['close'].iloc[-1]
        cash += position * final_price
        trades.append({
            'date': df['date'].iloc[-1],
            'type': 'sell',
            'price': final_price,
            'shares': position,
            'exit_type': 'end_of_backtest'
        })
        # 记录结束回测的卖出信号
        sell_signals.append({
            'date': df['date'].iloc[-1],
            'price': final_price,
            'exit_type': 'end_of_backtest',
            'conditions': {
                'end_of_backtest': True
            }
        })
    
    # 计算回测指标
    final_value = cash
    total_return = (final_value - initial_capital) / initial_capital * 100
    
    # 计算年化收益率
    num_trading_days = len(portfolio_value)
    if num_trading_days > 0:
        annual_return = (final_value / initial_capital) ** (252 / num_trading_days) - 1 if num_trading_days > 0 else 0
    else:
        annual_return = 0
    
    # 计算最大回撤
    if portfolio_value:
        portfolio_array = np.array(portfolio_value)
        peak = portfolio_array[0]
        max_drawdown = 0
        for value in portfolio_array:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak * 100
            if drawdown > max_drawdown:
                max_drawdown = drawdown
    else:
        max_drawdown = 0
    
    # 计算胜率
    winning_trades = 0
    total_trades = 0
    buy_trades = [t for t in trades if t['type'] == 'buy']
    sell_trades = [t for t in trades if t['type'] == 'sell']
    
    for i in range(min(len(buy_trades), len(sell_trades))):
        buy_price = buy_trades[i]['price']
        sell_price = sell_trades[i]['price']
        if sell_price > buy_price:
            winning_trades += 1
        total_trades += 1
    
    win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
    
    # 构建回测结果
    backtest_result = {
        'backtest_return': total_return,
        'annual_return': annual_return * 100,
        'max_drawdown_backtest': max_drawdown,
        'win_rate_backtest': win_rate,
        'total_trades_backtest': total_trades,
        'trades': trades,
        'buy_signals': buy_signals,
        'sell_signals': sell_signals,
        'portfolio_value': portfolio_value,
        'dates': df['date'].iloc[1:].tolist()  # 保存日期列表
    }
    
    print(f"  回测收益率: {total_return:.2f}%")
    print(f"  年化收益率: {annual_return * 100:.2f}%")
    print(f"  最大回撤: {max_drawdown:.2f}%")
    print(f"  胜率: {win_rate:.2f}%")
    print(f"  总交易次数: {total_trades}")
    
    return backtest_result


def plot_stock_analysis(df, buy_signals, sell_signals, ticker, output_dir=None, portfolio_value=None, dates=None):
    """绘制单只股票的分析结果，显示买入点和卖出点"""
    # 确定输出目录
    if output_dir:
        base_dir = os.path.join(output_dir, ticker)
    else:
        base_dir = os.path.join(DATA_DIR, ticker, 'analysis')
    
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 计算每日收益率
    daily_returns = []
    if portfolio_value and len(portfolio_value) > 1:
        for i in range(1, len(portfolio_value)):
            daily_return = (portfolio_value[i] - portfolio_value[i-1]) / portfolio_value[i-1] * 100
            daily_returns.append(daily_return)
    
    # 绘制K线图和信号点
    plt.figure(figsize=(16, 18))
    
    # 绘制收盘价
    plt.subplot(3, 1, 1)
    plt.plot(df.index, df['close'], label='收盘价', color='blue', linewidth=2)
    
    # 绘制EMA线
    plt.plot(df.index, df['EMA20'], label='EMA20', color='orange', linestyle='--', linewidth=1.5)
    plt.plot(df.index, df['EMA60'], label='EMA60', color='green', linestyle='--', linewidth=1.5)
    plt.plot(df.index, df['EMA120'], label='EMA120', color='purple', linestyle='--', linewidth=1.5)
    
    # 绘制肯特纳通道
    plt.plot(df.index, df['KC_upper'], label='KC上轨', color='red', linestyle='--', linewidth=1.5)
    plt.plot(df.index, df['KC_lower'], label='KC下轨', color='green', linestyle='--', linewidth=1.5)
    
    # 标记买入点
    buy_date_indices = [df[df['date'] == signal['date']].index[0] for signal in buy_signals]
    buy_prices = [signal['price'] for signal in buy_signals]
    plt.scatter(buy_date_indices, buy_prices, marker='^', color='green', s=150, label='买入点', edgecolors='black')
    
    # 标记卖出点
    sell_date_indices = [df[df['date'] == signal['date']].index[0] for signal in sell_signals]
    sell_prices = [signal['price'] for signal in sell_signals]
    plt.scatter(sell_date_indices, sell_prices, marker='v', color='red', s=150, label='卖出点', edgecolors='black')
    
    plt.title(f'{ticker} 股票分析 - 买入/卖出信号')
    plt.xlabel('日期')
    plt.ylabel('价格')
    plt.legend(loc='upper left')
    # 减少网格线密度，使用浅色网格
    plt.grid(True, alpha=0.3, linestyle='--')
    
    # 优化日期显示，只显示部分日期
    if len(df) > 100:
        step = len(df) // 10
        # 确保刻度位置和标签数量匹配
        tick_indices = df.index[::step]
        tick_labels = df['date'][::step]
        # 如果数量不匹配，调整
        if len(tick_indices) != len(tick_labels):
            min_length = min(len(tick_indices), len(tick_labels))
            tick_indices = tick_indices[:min_length]
            tick_labels = tick_labels[:min_length]
        plt.xticks(tick_indices, tick_labels, rotation=45, ha='right')
    else:
        plt.xticks(rotation=45, ha='right')
    
    # 绘制价值走势
    plt.subplot(3, 1, 2)
    if portfolio_value and dates:
        # 创建日期索引
        date_indices = range(len(dates))
        plt.plot(date_indices, portfolio_value, label='Portfolio价值', color='purple', linewidth=2)
        # 添加初始资金线
        initial_capital = portfolio_value[0] if portfolio_value else 0
        plt.axhline(y=initial_capital, color='gray', linestyle='--', label='初始资金')
        plt.title(f'{ticker} Portfolio价值走势')
        plt.xlabel('日期')
        plt.ylabel('价值')
        plt.legend()
        plt.grid(True, alpha=0.3, linestyle='--')
        
        # 优化日期显示
        if len(dates) > 100:
            step = len(dates) // 10
            # 确保刻度位置和标签数量匹配
            tick_indices = date_indices[::step]
            tick_labels = dates[::step]
            # 如果数量不匹配，调整
            if len(tick_indices) != len(tick_labels):
                min_length = min(len(tick_indices), len(tick_labels))
                tick_indices = tick_indices[:min_length]
                tick_labels = tick_labels[:min_length]
            plt.xticks(tick_indices, tick_labels, rotation=45, ha='right')
        else:
            plt.xticks(rotation=45, ha='right')
    else:
        plt.title(f'{ticker} Portfolio价值走势')
        plt.xlabel('日期')
        plt.ylabel('价值')
        plt.grid(True, alpha=0.3, linestyle='--')
    
    # 绘制每日收益率
    plt.subplot(3, 1, 3)
    if daily_returns and dates:
        # 创建日期索引
        date_indices = range(len(daily_returns))
        plt.plot(date_indices, daily_returns, label='每日收益率', color='green', linewidth=1)
        # 添加零轴
        plt.axhline(y=0, color='gray', linestyle='--')
        plt.title(f'{ticker} 每日收益率')
        plt.xlabel('日期')
        plt.ylabel('收益率 (%)')
        plt.legend()
        plt.grid(True, alpha=0.3, linestyle='--')
        
        # 优化日期显示
        if len(dates) > 100:
            step = len(dates) // 10
            # 确保刻度位置和标签数量匹配
            tick_indices = date_indices[::step]
            tick_labels = dates[::step]
            # 如果数量不匹配，调整
            if len(tick_indices) != len(tick_labels):
                min_length = min(len(tick_indices), len(tick_labels))
                tick_indices = tick_indices[:min_length]
                tick_labels = tick_labels[:min_length]
            plt.xticks(tick_indices, tick_labels, rotation=45, ha='right')
        else:
            plt.xticks(rotation=45, ha='right')
    else:
        plt.title(f'{ticker} 每日收益率')
        plt.xlabel('日期')
        plt.ylabel('收益率 (%)')
        plt.grid(True, alpha=0.3, linestyle='--')
    
    plt.tight_layout()
    
    # 保存图表
    chart_path = os.path.join(base_dir, f"{ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.png")
    plt.savefig(chart_path, dpi=150, bbox_inches='tight')
    print(f"股票分析图表已保存到: {chart_path}")
    plt.close()


def plot_analysis_results(results, output_dir=None):
    """绘制分析结果"""
    # 确定输出目录
    if output_dir:
        base_dir = output_dir
    else:
        base_dir = os.path.join(DATA_DIR, 'analysis')
    
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 转换结果为DataFrame
    df = pd.DataFrame(results)
    
    # 绘制买入信号分布
    plt.figure(figsize=(12, 8))
    
    # 买入信号数量
    buy_count = len(df[df['buy_signal'] == True])
    total_count = len(df)
    
    plt.subplot(2, 2, 1)
    plt.bar(['买入信号', '无买入信号'], [buy_count, total_count - buy_count], color=['green', 'red'])
    plt.title('买入信号分布')
    plt.ylabel('股票数量')
    
    # 绘制RPS分布
    plt.subplot(2, 2, 2)
    plt.hist(df['RPS'], bins=20, alpha=0.7, color='blue')
    plt.title('RPS分布')
    plt.xlabel('RPS')
    plt.ylabel('股票数量')
    
    # 绘制ADX分布
    plt.subplot(2, 2, 3)
    plt.hist(df['ADX'], bins=20, alpha=0.7, color='green')
    plt.title('ADX分布')
    plt.xlabel('ADX')
    plt.ylabel('股票数量')
    
    # 绘制夏普比率分布
    plt.subplot(2, 2, 4)
    plt.hist(df['sharpe_ratio'].dropna(), bins=20, alpha=0.7, color='purple')
    plt.title('夏普比率分布')
    plt.xlabel('夏普比率')
    plt.ylabel('股票数量')
    
    plt.tight_layout()
    chart_path = os.path.join(base_dir, f"analysis_results_{datetime.now().strftime('%Y%m%d')}.png")
    plt.savefig(chart_path)
    print(f"分析结果图表已保存到: {chart_path}")
    plt.close()


def convert_conditions_to_text(conditions, signal_type):
    """将条件字典转换为文字表述"""
    if signal_type == 'buy':
        condition_texts = []
        if conditions.get('close_above_EMAs'):
            condition_texts.append('收盘价高于EMA20、EMA60、EMA120')
        if conditions.get('ADX_above_23'):
            condition_texts.append('ADX大于23')
        if conditions.get('RPS_above_80'):
            condition_texts.append('RPS大于80')
        if conditions.get('OBV_MA5_above_MA20'):
            condition_texts.append('OBV MA5高于MA20')
        if conditions.get('OBV_new_high'):
            condition_texts.append('OBV创新高')
        if conditions.get('close_above_KC_upper'):
            condition_texts.append('收盘价突破肯特纳通道上轨')
        if conditions.get('ATR_expanding'):
            condition_texts.append('ATR扩张')
        if conditions.get('MACD_crossover'):
            condition_texts.append('MACD金叉')
        if conditions.get('MACD_hist_positive'):
            condition_texts.append('MACD柱状图为正')
        if conditions.get('RSI_above_50'):
            condition_texts.append('RSI(14)大于50')
        return '; '.join(condition_texts) if condition_texts else '无'
    elif signal_type == 'sell':
        condition_texts = []
        if conditions.get('ema60_break'):
            condition_texts.append('价格跌破EMA60')
        if conditions.get('trailing_stop'):
            condition_texts.append('触发移动止损')
        if conditions.get('end_of_backtest'):
            condition_texts.append('回测结束')
        return '; '.join(condition_texts) if condition_texts else '无'
    return '无'


def save_stock_analysis(ticker, df, analysis_result, output_dir=None):
    """保存单只股票的分析结果"""
    # 确定输出目录
    if output_dir:
        base_dir = os.path.join(output_dir, ticker)
    else:
        base_dir = os.path.join(DATA_DIR, ticker, 'analysis')
    
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 保存分析结果
    analysis_file = os.path.join(base_dir, f"{ticker}_analysis_{datetime.now().strftime('%Y%m%d')}.csv")
    try:
        analysis_df = pd.DataFrame([analysis_result])
        analysis_df.to_csv(analysis_file, index=False, encoding='utf-8-sig')
        print(f"股票分析结果已保存到: {analysis_file}")
        
        # 合并买入信号和卖出信号到同一个文件
        signals_data = []
        
        # 处理买入信号
        if 'buy_signals' in analysis_result and analysis_result['buy_signals']:
            for i, signal in enumerate(analysis_result['buy_signals']):
                # 确定是首次建仓还是加仓
                if i == 0:
                    buy_type = '首次建仓'
                else:
                    buy_type = '加仓'
                
                # 获取交易量和仓位信息
                shares = signal.get('shares', 0)
                position = signal.get('position', 0)
                position_ratio = signal.get('position_ratio', 0)
                
                signals_data.append({
                    'date': signal['date'],
                    'price': signal['price'],
                    'signal_type': 'buy',
                    'buy_type': buy_type,
                    'shares': shares,
                    'position': position,
                    'position_ratio': position_ratio,
                    'exit_type': '',
                    'conditions': convert_conditions_to_text(signal['conditions'], 'buy')
                })
        
        # 处理卖出信号
        if 'sell_signals' in analysis_result and analysis_result['sell_signals']:
            for signal in analysis_result['sell_signals']:
                # 查找对应的交易记录，获取交易量
                shares = 0
                if 'trades' in analysis_result:
                    for trade in analysis_result['trades']:
                        if trade['date'] == signal['date'] and trade['type'] == 'sell':
                            shares = trade.get('shares', 0)
                            break
                
                signals_data.append({
                    'date': signal['date'],
                    'price': signal['price'],
                    'signal_type': 'sell',
                    'buy_type': '清仓',
                    'shares': shares,
                    'position': 0,  # 卖出后仓位为0
                    'position_ratio': 0,  # 卖出后仓位比例为0
                    'exit_type': signal.get('exit_type', ''),
                    'conditions': convert_conditions_to_text(signal['conditions'], 'sell')
                })
        
        # 保存合并后的信号
        if signals_data:
            signals_df = pd.DataFrame(signals_data)
            # 按照日期排序
            signals_df['date'] = pd.to_datetime(signals_df['date'])
            signals_df = signals_df.sort_values('date')
            # 转换回字符串格式
            signals_df['date'] = signals_df['date'].dt.strftime('%Y-%m-%d')
            signals_file = os.path.join(base_dir, f"{ticker}_trading_signals_{datetime.now().strftime('%Y%m%d')}.csv")
            signals_df.to_csv(signals_file, index=False, encoding='utf-8-sig')
            print(f"交易信号已保存到: {signals_file}")
        
        # 绘制股票分析图表
        if 'buy_signals' in analysis_result and 'sell_signals' in analysis_result:
            portfolio_value = analysis_result.get('portfolio_value', None)
            dates = analysis_result.get('dates', None)
            plot_stock_analysis(df, analysis_result['buy_signals'], analysis_result['sell_signals'], ticker, output_dir, portfolio_value, dates)
            
    except Exception as e:
        print(f"保存股票分析结果时出错: {str(e)}")


def save_analysis_results(results, output_dir=None):
    """保存分析结果"""
    # 确定输出目录
    if output_dir:
        base_dir = output_dir
    else:
        base_dir = os.path.join(DATA_DIR, 'analysis')
    
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 构建文件路径
    file_path = os.path.join(base_dir, f"quantitative_analysis_{datetime.now().strftime('%Y%m%d')}.csv")
    
    # 保存文件
    try:
        df = pd.DataFrame(results)
        df.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"分析结果已保存到: {file_path}")
        
        # 筛选买入信号
        buy_signals = df[df['buy_signal'] == True]
        if not buy_signals.empty:
            buy_file_path = os.path.join(base_dir, f"buy_signals_{datetime.now().strftime('%Y%m%d')}.csv")
            buy_signals.to_csv(buy_file_path, index=False, encoding='utf-8-sig')
            print(f"买入信号已保存到: {buy_file_path}")
            print(f"\n符合买入条件的股票数量: {len(buy_signals)}")
            print("符合条件的股票:")
            for ticker in buy_signals['ticker']:
                print(f"- {ticker}")
        else:
            print("\n没有符合买入条件的股票")
        
        # 绘制分析结果
        plot_analysis_results(results, output_dir)
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="实现资金驱动的波动率突破策略，进行量化分析并保存结果")
    parser.add_argument('--tickers', nargs='+', help="股票代码列表，例如：300433.SZ 600313.SH")
    parser.add_argument('--input-dir', help="输入数据目录，默认为config.py中的配置")
    parser.add_argument('--output-dir', help="输出数据目录，默认为data/analysis")
    parser.add_argument('--backtest', action='store_true', help="是否进行回测")
    parser.add_argument('--verbose', action='store_true', help="显示详细信息")
    args = parser.parse_args()
    
    # 如果没有指定股票代码，使用data目录下的所有股票
    if not args.tickers:
        tickers = []
        data_dir = args.input_dir if args.input_dir else DATA_DIR
        if os.path.exists(data_dir):
            for item in os.listdir(data_dir):
                item_path = os.path.join(data_dir, item)
                if os.path.isdir(item_path):
                    # 检查是否有qfq.csv文件
                    qfq_file = os.path.join(item_path, f"{item}_qfq.csv")
                    if os.path.exists(qfq_file):
                        tickers.append(item)
        print(f"自动检测到 {len(tickers)} 只股票")
    else:
        tickers = args.tickers
    
    # 分析每只股票
    results = []
    for ticker in tickers:
        print(f"\n分析股票: {ticker}")
        result, df = analyze_stock(ticker, args.input_dir, args.backtest)
        if result:
            results.append(result)
            # 保存单只股票的分析结果
            save_stock_analysis(ticker, df, result, args.output_dir)
    
    # 保存综合结果
    if results:
        save_analysis_results(results, args.output_dir)
        
        # 显示详细分析结果
        if args.verbose:
            print("\n=== 详细分析结果 ===")
            df = pd.DataFrame(results)
            print(df)
    else:
        print("没有成功分析的股票")


if __name__ == "__main__":
    main()