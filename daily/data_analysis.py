# data_analysis.py
# 功能：股票数据质量检查和可视化分析
# 实现原理：
# 1. 加载股票历史数据，检查数据质量（缺失值、数据类型等）
# 2. 绘制价格和成交量图表，展示股票价格走势
# 3. 绘制技术指标图表（MACD、RSI、KDJ），分析股票技术形态
# 4. 绘制布林带图表，分析股票价格波动范围
# 5. 进行相关性分析，计算各技术指标与收盘价的相关性

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class DataAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
    
    def load_data(self):
        """加载数据"""
        print(f"加载数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 检查数据基本信息
        print(f"数据形状: {self.data.shape}")
        print(f"数据列名: {list(self.data.columns)}")
        
        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[0]
            print(f"股票代码: {self.ticker}")
        
        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
            print(f"日期范围: {self.data['date'].min()} 到 {self.data['date'].max()}")
        
        return self.data
    
    def check_data_quality(self):
        """检查数据质量"""
        print("\n=== 数据质量检查 ===")
        
        # 检查缺失值
        missing_values = self.data.isnull().sum()
        print("缺失值统计:")
        print(missing_values[missing_values > 0])
        
        # 检查数据类型
        print("\n数据类型:")
        print(self.data.dtypes)
        
        # 基本统计信息
        print("\n基本统计信息:")
        print(self.data.describe())
    
    def plot_price_volume(self):
        """绘制价格和成交量图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 10))
        
        # 价格走势
        plt.subplot(2, 1, 1)
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['MA5'], label='MA5', color='red')
        plt.plot(self.data['date'], self.data['MA20'], label='MA20', color='green')
        plt.plot(self.data['date'], self.data['MA60'], label='MA60', color='purple')
        plt.title(f'{self.ticker} 价格走势')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # 成交量
        plt.subplot(2, 1, 2)
        plt.bar(self.data['date'], self.data['volume'], label='成交量', color='gray', alpha=0.7)
        plt.title(f'{self.ticker} 成交量')
        plt.xlabel('日期')
        plt.ylabel('成交量')
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_price_volume.png')
        plt.savefig(chart_path)
        print(f"价格和成交量图表已保存为: {chart_path}")
    
    def plot_technical_indicators(self):
        """绘制技术指标图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 15))
        
        # MACD
        plt.subplot(3, 1, 1)
        plt.plot(self.data['date'], self.data['MACD'], label='MACD', color='blue')
        plt.plot(self.data['date'], self.data['MACD_signal'], label='Signal', color='red')
        plt.bar(self.data['date'], self.data['MACD_hist'], label='Histogram', color='green', alpha=0.5)
        plt.title(f'{self.ticker} MACD指标')
        plt.xlabel('日期')
        plt.ylabel('MACD')
        plt.legend()
        plt.grid(True)
        
        # RSI
        plt.subplot(3, 1, 2)
        plt.plot(self.data['date'], self.data['RSI'], label='RSI', color='purple')
        plt.axhline(y=70, color='red', linestyle='--', label='超买线')
        plt.axhline(y=30, color='green', linestyle='--', label='超卖线')
        plt.title(f'{self.ticker} RSI指标')
        plt.xlabel('日期')
        plt.ylabel('RSI')
        plt.legend()
        plt.grid(True)
        
        # KDJ
        plt.subplot(3, 1, 3)
        plt.plot(self.data['date'], self.data['K'], label='K', color='blue')
        plt.plot(self.data['date'], self.data['D'], label='D', color='red')
        plt.plot(self.data['date'], self.data['J'], label='J', color='green')
        plt.title(f'{self.ticker} KDJ指标')
        plt.xlabel('日期')
        plt.ylabel('KDJ')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_technical_indicators.png')
        plt.savefig(chart_path)
        print(f"技术指标图表已保存为: {chart_path}")
    
    def plot_bollinger_bands(self):
        """绘制布林带"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 8))
        
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['BB_upper'], label='上轨', color='red', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_middle'], label='中轨', color='green', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_lower'], label='下轨', color='purple', linestyle='--')
        plt.fill_between(self.data['date'], self.data['BB_upper'], self.data['BB_lower'], color='gray', alpha=0.1)
        
        plt.title(f'{self.ticker} 布林带')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_bollinger_bands.png')
        plt.savefig(chart_path)
        print(f"布林带图表已保存为: {chart_path}")
    
    def correlation_analysis(self):
        """相关性分析"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 选择关键技术指标
        indicators = ['close', 'MA5', 'MA20', 'MA60', 'VOL5', 'K', 'D', 'J', 'MACD', 'RSI', 'CCI', 'WR']
        
        # 计算相关性矩阵
        corr_matrix = self.data[indicators].corr()
        
        # 绘制相关性热力图
        plt.figure(figsize=(12, 10))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt='.2f')
        plt.title(f'{self.ticker} 技术指标相关性分析')
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_correlation.png')
        plt.savefig(chart_path)
        print(f"相关性分析图表已保存为: {chart_path}")
        
        # 显示与收盘价相关性最高的指标
        close_corr = corr_matrix['close'].sort_values(ascending=False)
        print("\n与收盘价相关性排序:")
        print(close_corr)
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.check_data_quality()
        self.plot_price_volume()
        self.plot_technical_indicators()
        self.plot_bollinger_bands()
        self.correlation_analysis()
        print("\n=== 分析完成 ===")

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="股票数据质量检查和可视化分析")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认使用config.py中的配置")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
        ticker_name = ticker
    else:
        # 使用第一个股票代码进行分析
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker}")
    
    # 分析数据
    analyzer = DataAnalyzer(file_path)
    analyzer.run_analysis()
