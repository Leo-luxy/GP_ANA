# stock_weekly_analyzer.py
# 功能：读取本地指定股票的日线数据，计算周线相关数据及指标，将结果保存到本地
# 实现原理：
# 1. 加载本地股票的日线数据
# 2. 将日线数据转换为周线数据
# 3. 计算周线的技术指标
# 4. 将周线数据和指标保存到本地文件

import pandas as pd
import numpy as np
import os
import argparse
from datetime import datetime
from config import DATA_DIR
from utils import calculate_technical_indicators

class StockWeeklyAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.daily_data = None
        self.weekly_data = None
        self.ticker = None
    
    def load_daily_data(self):
        """加载日线数据"""
        print(f"加载日线数据文件: {self.file_path}")
        self.daily_data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'date' in self.daily_data.columns:
            self.daily_data['date'] = pd.to_datetime(self.daily_data['date'])
        
        # 获取股票代码
        if 'ticker' in self.daily_data.columns:
            self.ticker = self.daily_data['ticker'].iloc[0]
        
        return self.daily_data
    
    def convert_to_weekly(self):
        """将日线数据转换为周线数据"""
        if self.daily_data is None:
            self.load_daily_data()
        
        print(f"将日线数据转换为周线数据...")
        
        # 设置日期为索引
        df = self.daily_data.set_index('date')
        
        # 过滤掉非交易日（周六和周日）
        df = df[df.index.weekday < 5]  # 0-4 表示周一到周五
        
        # 按周分组，计算周线数据，使用周一作为周的开始
        weekly = df.resample('W-MON').agg({
            'open': 'first',      # 周开盘价
            'high': 'max',        # 周最高价
            'low': 'min',         # 周最低价
            'close': 'last',      # 周收盘价
            'volume': 'sum',      # 周成交量
            '成交额': 'sum',      # 周成交额
            '涨跌幅': 'last',      # 周涨跌幅
            '涨跌额': 'last'       # 周涨跌额
        })
        
        # 重置索引
        weekly = weekly.reset_index()
        
        # 重命名列名
        weekly = weekly.rename(columns={'date': 'week_start'})
        
        # 添加周结束日期（周五）
        weekly['week_end'] = weekly['week_start'] + pd.Timedelta(days=4)  # 周一 + 4天 = 周五
        
        # 重新排序列
        weekly = weekly[['week_start', 'week_end', 'open', 'high', 'low', 'close', 'volume', '成交额', '涨跌幅', '涨跌额']]
        
        # 过滤掉没有数据的周
        weekly = weekly.dropna(subset=['open', 'high', 'low', 'close'])
        
        self.weekly_data = weekly
        print(f"周线数据转换完成，共 {len(weekly)} 周")
        return weekly
    
    def calculate_weekly_indicators(self):
        """计算周线技术指标"""
        if self.weekly_data is None:
            self.convert_to_weekly()
        
        print("计算周线技术指标...")
        
        # 复制周线数据用于计算指标
        weekly_with_indicators = self.weekly_data.copy()
        
        # 重命名列以匹配calculate_technical_indicators函数的预期
        weekly_with_indicators = weekly_with_indicators.rename(columns={
            'week_start': 'date',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        # 计算技术指标
        weekly_with_indicators = calculate_technical_indicators(weekly_with_indicators)
        
        # 恢复原始列名
        weekly_with_indicators = weekly_with_indicators.rename(columns={
            'date': 'week_start'
        })
        
        # 重新添加week_end列
        weekly_with_indicators['week_end'] = weekly_with_indicators['week_start'] + pd.Timedelta(days=6)
        
        self.weekly_data = weekly_with_indicators
        print("周线技术指标计算完成")
        return weekly_with_indicators
    
    def save_weekly_data(self):
        """保存周线数据到本地"""
        if self.weekly_data is None:
            self.calculate_weekly_indicators()
        
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名
        filename = f"{self.ticker}_weekly_data.csv"
        file_path = os.path.join(stock_dir, filename)
        
        # 保存到CSV文件
        self.weekly_data.to_csv(file_path, index=False, encoding='utf-8-sig')
        print(f"周线数据已保存到: {file_path}")
        return file_path
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_daily_data()
        self.convert_to_weekly()
        self.calculate_weekly_indicators()
        self.save_weekly_data()
        print("\n=== 周线分析完成 ===")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="读取本地指定股票的日线数据，计算周线相关数据及指标")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所）")
    args = parser.parse_args()
    
    if not args.ticker:
        print("请指定股票代码，例如：python stock_weekly_analyzer.py --ticker 300433.SZ")
        exit(1)
    
    # 构建日线数据文件路径
    ticker = args.ticker
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_history.csv'
    
    if not os.path.exists(file_path):
        print(f"日线数据文件不存在: {file_path}")
        print("请先运行 stock_history_collector_ta_v2.py 抓取日线数据")
        exit(1)
    
    print(f"分析股票: {ticker}")
    
    # 运行周线分析
    analyzer = StockWeeklyAnalyzer(file_path)
    analyzer.run_analysis()
