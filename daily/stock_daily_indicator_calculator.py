# stock_daily_indicator_calculator.py
# 功能：读取本地日线数据文件，计算技术指标并保存结果
# 实现原理：
# 1. 读取本地"股票代码_qfq.csv"文件
# 2. 调用utils.py中的calculate_technical_indicators函数计算技术指标
# 3. 补充计算EMA和RPS指标
# 4. 将计算结果保存到本地

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


def calculate_ema(data_df, periods=[5, 10, 20, 50, 60, 120, 200]):
    """计算指数移动平均线(EMA)"""
    for period in periods:
        data_df[f'EMA{period}'] = data_df['close'].ewm(span=period, adjust=False).mean()
    return data_df


def calculate_rps(data_df, period=250):
    """计算相对强弱指数(RPS)"""
    # 这里简化计算，实际RPS需要与其他股票比较
    # 这里使用股票自身的收益率与波动率的比值作为简化版RPS
    data_df['return'] = data_df['close'].pct_change()
    data_df['cum_return'] = (1 + data_df['return']).cumprod()
    data_df['volatility'] = data_df['return'].rolling(window=20).std() * np.sqrt(252)
    data_df['RPS'] = data_df['cum_return'] / data_df['volatility']
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
        
        return df
    except Exception as e:
        print(f"读取文件时出错: {str(e)}")
        return None


def save_results(df, ticker, output_dir=None):
    """保存计算结果到本地文件"""
    # 确定输出目录
    if output_dir:
        base_dir = output_dir
    else:
        # 使用项目根目录作为基准
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        base_dir = os.path.join(project_root, 'data')
    
    # 确保目录存在
    stock_dir = os.path.join(base_dir, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 构建文件路径
    file_path = os.path.join(stock_dir, f"{ticker}_indicators.csv")
    
    # 按照history.csv的列顺序重新排列
    history_columns = [
        'date', '股票代码', 'open', 'close', 'high', 'low', 'volume', '成交额', '振幅', '涨跌幅', '涨跌额', '换手率',
        'MA5', 'MA10', 'MA20', 'MA50', 'MA60', 'MA120', 'MA200',
        'VOL5', 'VOL10', 'VOL20', 'Volume_Ratio',
        'K', 'D', 'J',
        'MACD', 'MACD_signal', 'MACD_hist',
        'BB_upper', 'BB_middle', 'BB_lower', 'BB_std', 'BB_width',
        'ATR',
        'RSI', 'RSI_6', 'RSI_24',
        'CCI',
        'ROC', 'ROC_6',
        'OBV',
        'WR', 'WR_6',
        'BIAS5', 'BIAS10', 'BIAS20',
        'DMA',
        'TRIX',
        'VR',
        'PSY',
        'MTM',
        'SAR',
        'ADX',
        'MACD_hist_change',
        'Momentum',
        'Price_MA5_Ratio', 'Price_MA20_Ratio', 'Price_MA60_Ratio',
        'Volume_VOL5_Ratio', 'Volume_VOL20_Ratio',
        'VWAP',
        'Volatility',
        'ticker'
    ]
    
    # 添加indicators.csv独有的列
    indicators_columns = [
        'amount', 'outstanding_share',
        'EMA5', 'EMA10', 'EMA20', 'EMA50', 'EMA60', 'EMA120', 'EMA200',
        'return', 'cum_return', 'volatility', 'RPS'
    ]
    
    # 合并列顺序
    all_columns = history_columns + indicators_columns
    
    # 添加缺失的列
    if '股票代码' not in df.columns:
        df['股票代码'] = ticker.split('.')[0]
    if '成交额' not in df.columns:
        df['成交额'] = df['volume'] * df['close']
    if '振幅' not in df.columns:
        df['振幅'] = (df['high'] - df['low']) / df['low'] * 100
    if '涨跌幅' not in df.columns:
        df['涨跌幅'] = df['close'].pct_change() * 100
    if '涨跌额' not in df.columns:
        df['涨跌额'] = df['close'] - df['close'].shift(1)
    if '换手率' not in df.columns:
        df['换手率'] = 0  # 默认为0，实际数据需要根据流通股本计算
    if 'ticker' not in df.columns:
        df['ticker'] = ticker
    
    # 确保所有列都存在
    for col in all_columns:
        if col not in df.columns:
            df[col] = 0
    
    # 按顺序排列列
    df = df[all_columns]
    
    # 保存文件
    try:
        df.to_csv(file_path, index=False)
        print(f"计算结果已保存到: {file_path}")
    except Exception as e:
        print(f"保存文件时出错: {str(e)}")


def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="读取本地日线数据文件，计算技术指标并保存结果")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所）")
    parser.add_argument('--input-dir', help="输入数据目录，默认为config.py中的配置")
    parser.add_argument('--output-dir', help="输出数据目录，默认为config.py中的配置")
    args = parser.parse_args()
    
    # 检查ticker参数是否存在
    if not args.ticker:
        print("错误：必须指定股票代码，请使用 --ticker 参数")
        return
    
    # 读取本地数据
    df = read_local_data(args.ticker, args.input_dir)
    
    if df is not None and not df.empty:
        # 计算技术指标
        print("计算技术指标...")
        df = calculate_technical_indicators(df)
        
        # 补充计算EMA指标
        print("计算EMA指标...")
        df = calculate_ema(df)
        
        # 补充计算RPS指标
        print("计算RPS指标...")
        df = calculate_rps(df)
        
        # 保存结果
        save_results(df, args.ticker, args.output_dir)
        
        print("计算完成！")
    else:
        print("无法读取数据，计算失败。")


if __name__ == "__main__":
    main()