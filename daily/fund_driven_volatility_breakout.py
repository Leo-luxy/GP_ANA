# fund_driven_volatility_breakout.py
# 功能：实现完整的资金驱动的波动率突破策略，包括入场规则、离场规则、资金管理和回测
# 实现原理：
# 1. 读取本地股票数据
# 2. 计算各项技术指标
# 3. 按照策略规则筛选股票
# 4. 实现完整的交易逻辑（入场和离场）
# 5. 资金管理和仓位控制
# 6. 回测并计算绩效指标
# 7. 保存结果

import pandas as pd
import os
import sys
import argparse
from datetime import datetime
import numpy as np

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import calculate_technical_indicators
from config import DATA_DIR


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
    
    return data_df


def read_local_data(ticker, input_dir=None):
    """读取本地股票数据文件"""
    # 确定输入目录
    if input_dir:
        base_dir = input_dir
    else:
        # 使用项目根目录作为基准
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.join(project_root, 'data')
    
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
        
        # 计算技术指标
        df = calculate_technical_indicators(df)
        df = calculate_ema(df)
        df = calculate_obv_ma(df)
        df = calculate_keltner_channel(df)
        df = calculate_rps(df)
        
        return df
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return None


def check_entry_conditions(data):
    """检查入场条件"""
    # 第一层：基础股票池（优中选优）
    condition1 = data['close'] > data['EMA20'] > data['EMA60'] > data['EMA120']
    condition2 = data['ADX'] > 23
    condition3 = data['RPS'] > 80
    
    # 第二层：资金验证（量价配合）
    condition4 = data['OBV_MA5'] > data['OBV_MA20']
    condition5 = data['OBV_new_high']
    
    # 第三层：精确起爆点（波动率突破）
    condition6 = data['close'] > data['KC_upper']
    condition7 = data['ATR_expanding']
    
    # 综合条件
    buy_signal = all([condition1, condition2, condition3, condition4, condition5, condition6, condition7])
    
    return buy_signal


def check_exit_conditions(data, entry_price, highest_price):
    """检查离场条件"""
    # 规则A：趋势终结（主离场信号）
    condition_a = data['close'] < data['EMA60']
    
    # 规则B：移动止损（保护利润）
    condition_b = data['close'] < highest_price * (1 - 1.5 * data['ATR'])
    
    # 规则C：资金背离（预警性离场，可选）
    condition_c = data['close'] > data['EMA60'] and data['OBV'] < data['OBV_MA20']
    
    # 任一条件满足即离场
    exit_signal = condition_a or condition_b or condition_c
    
    return exit_signal


def backtest_strategy(df, initial_cash=1000000, max_positions=10, max_position_size=0.05):
    """回测策略"""
    # 初始化回测参数
    cash = initial_cash
    positions = {}
    entry_prices = {}
    highest_prices = {}
    portfolio_value = [cash]
    trades = []
    
    # 回测主循环
    for i in range(len(df)):
        current_data = df.iloc[i]
        current_date = current_data['date']
        
        # 检查离场条件
        exit_tickers = []
        for ticker in positions:
            # 更新最高价
            if current_data['close'] > highest_prices[ticker]:
                highest_prices[ticker] = current_data['close']
            
            # 检查是否需要离场
            if check_exit_conditions(current_data, entry_prices[ticker], highest_prices[ticker]):
                exit_tickers.append(ticker)
        
        # 执行离场操作
        for ticker in exit_tickers:
            # 计算卖出金额
            shares = positions[ticker]
            sell_price = current_data['close']
            sell_amount = shares * sell_price
            
            # 更新现金和持仓
            cash += sell_amount
            del positions[ticker]
            del entry_prices[ticker]
            del highest_prices[ticker]
            
            # 记录交易
            trades.append({
                'date': current_date,
                'ticker': ticker,
                'action': 'sell',
                'price': sell_price,
                'shares': shares,
                'amount': sell_amount
            })
        
        # 检查入场条件
        if len(positions) < max_positions:
            if check_entry_conditions(current_data):
                # 计算可买入金额
                available_cash = cash * max_position_size
                buy_price = current_data['close']
                shares = int(available_cash / buy_price)
                
                if shares > 0:
                    # 执行买入操作
                    buy_amount = shares * buy_price
                    cash -= buy_amount
                    
                    # 更新持仓
                    ticker = current_data.get('ticker', 'Unknown')
                    positions[ticker] = shares
                    entry_prices[ticker] = buy_price
                    highest_prices[ticker] = buy_price
                    
                    # 记录交易
                    trades.append({
                        'date': current_date,
                        'ticker': ticker,
                        'action': 'buy',
                        'price': buy_price,
                        'shares': shares,
                        'amount': buy_amount
                    })
        
        # 计算当日 portfolio 价值
        current_value = cash
        for ticker, shares in positions.items():
            current_value += shares * current_data['close']
        portfolio_value.append(current_value)
    
    # 计算绩效指标
    portfolio_value = pd.Series(portfolio_value)
    returns = portfolio_value.pct_change().dropna()
    
    # 计算关键绩效指标
    total_return = (portfolio_value.iloc[-1] / portfolio_value.iloc[0] - 1) * 100
    annual_return = (1 + total_return/100) ** (252/len(returns)) - 1 if len(returns) > 0 else 0
    sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std() if returns.std() > 0 else 0
    max_drawdown = (portfolio_value / portfolio_value.cummax() - 1).min() * 100
    
    performance = {
        'total_return': total_return,
        'annual_return': annual_return * 100,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'trades': len(trades)
    }
    
    return performance, trades, portfolio_value


def analyze_stock(ticker, input_dir=None):
    """分析单个股票"""
    # 读取数据
    df = read_local_data(ticker, input_dir)
    if df is None:
        return None
    
    # 添加股票代码列
    df['ticker'] = ticker
    
    # 回测策略
    print(f"回测股票: {ticker}")
    performance, trades, portfolio_value = backtest_strategy(df)
    
    # 构建分析结果
    result = {
        'ticker': ticker,
        'total_return': performance['total_return'],
        'annual_return': performance['annual_return'],
        'sharpe_ratio': performance['sharpe_ratio'],
        'max_drawdown': performance['max_drawdown'],
        'trades': performance['trades']
    }
    
    return result, trades, portfolio_value


def save_analysis_results(results, trades_list, portfolio_values, output_dir=None):
    """保存分析结果"""
    # 确定输出目录
    if output_dir:
        base_dir = output_dir
    else:
        base_dir = os.path.join(DATA_DIR, 'analysis')
    
    # 确保目录存在
    os.makedirs(base_dir, exist_ok=True)
    
    # 保存绩效结果
    performance_file = os.path.join(base_dir, f"strategy_performance_{datetime.now().strftime('%Y%m%d')}.csv")
    try:
        performance_df = pd.DataFrame(results)
        performance_df.to_csv(performance_file, index=False)
        print(f"绩效结果已保存到: {performance_file}")
    except Exception as e:
        print(f"保存绩效结果时出错: {str(e)}")
    
    # 保存交易记录
    all_trades = []
    for trades in trades_list:
        all_trades.extend(trades)
    
    if all_trades:
        trades_file = os.path.join(base_dir, f"trades_{datetime.now().strftime('%Y%m%d')}.csv")
        try:
            trades_df = pd.DataFrame(all_trades)
            trades_df.to_csv(trades_file, index=False)
            print(f"交易记录已保存到: {trades_file}")
        except Exception as e:
            print(f"保存交易记录时出错: {str(e)}")
    
    # 保存组合价值
    if portfolio_values:
        portfolio_file = os.path.join(base_dir, f"portfolio_value_{datetime.now().strftime('%Y%m%d')}.csv")
        try:
            portfolio_df = pd.DataFrame()
            for ticker, pv in portfolio_values.items():
                # 生成日期序列（简化处理）
                dates = pd.date_range(start='2020-01-01', periods=len(pv))
                temp_df = pd.DataFrame({'date': dates, 'portfolio_value': pv})
                temp_df['ticker'] = ticker
                portfolio_df = pd.concat([portfolio_df, temp_df])
            portfolio_df.to_csv(portfolio_file, index=False)
            print(f"组合价值已保存到: {portfolio_file}")
        except Exception as e:
            print(f"保存组合价值时出错: {str(e)}")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="实现完整的资金驱动的波动率突破策略，包括入场规则、离场规则、资金管理和回测")
    parser.add_argument('--tickers', nargs='+', help="股票代码列表，例如：300433.SZ 600313.SH")
    parser.add_argument('--input-dir', help="输入数据目录，默认为config.py中的配置")
    parser.add_argument('--output-dir', help="输出数据目录，默认为data/analysis")
    parser.add_argument('--initial-cash', type=float, default=1000000, help="初始资金，默认为1000000")
    parser.add_argument('--max-positions', type=int, default=10, help="最大持仓数，默认为10")
    parser.add_argument('--max-position-size', type=float, default=0.05, help="单票最大仓位，默认为0.05")
    args = parser.parse_args()
    
    # 如果没有指定股票代码，使用data目录下的所有股票
    if not args.tickers:
        tickers = []
        if args.input_dir:
            data_dir = args.input_dir
        else:
            # 使用项目根目录作为基准
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            data_dir = os.path.join(project_root, 'data')
        
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
    trades_list = []
    portfolio_values = {}
    for ticker in tickers:
        print(f"\n分析股票: {ticker}")
        result, trades, portfolio_value = analyze_stock(ticker, args.input_dir)
        if result:
            results.append(result)
            trades_list.append(trades)
            portfolio_values[ticker] = portfolio_value
    
    # 保存结果
    if results:
        save_analysis_results(results, trades_list, portfolio_values, args.output_dir)
    else:
        print("没有成功分析的股票")


if __name__ == "__main__":
    main()