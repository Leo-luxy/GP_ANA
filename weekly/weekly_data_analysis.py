# weekly_data_analysis.py
# 功能：分析股票周线数据，生成相关图表和分析结果
# 实现原理：
# 1. 加载股票周线数据
# 2. 进行数据质量检查
# 3. 绘制周线价格和成交量图表
# 4. 绘制周线技术指标图表
# 5. 绘制周线布林带图表
# 6. 分析周线技术指标相关性

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import os
import argparse
from datetime import datetime
from config import DATA_DIR

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class WeeklyDataAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
    
    def load_data(self):
        """加载周线数据"""
        print(f"加载周线数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'week_start' in self.data.columns:
            self.data['week_start'] = pd.to_datetime(self.data['week_start'])
        if 'week_end' in self.data.columns:
            self.data['week_end'] = pd.to_datetime(self.data['week_end'])
        
        # 从文件名中提取股票代码
        self.ticker = os.path.basename(self.file_path).split('_')[0]
        
        return self.data
    
    def check_data_quality(self):
        """检查数据质量"""
        print("检查数据质量...")
        
        # 检查数据维度
        print(f"数据维度: {self.data.shape}")
        
        # 检查缺失值
        missing_values = self.data.isnull().sum()
        print("缺失值统计:")
        print(missing_values[missing_values > 0])
        
        # 检查数据时间范围
        if 'week_start' in self.data.columns:
            start_date = self.data['week_start'].min()
            end_date = self.data['week_start'].max()
            print(f"数据时间范围: {start_date} 到 {end_date}")
            print(f"共 {len(self.data)} 周的数据")
    
    def plot_price_volume(self):
        """绘制周线价格和成交量图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 10))
        
        # 价格走势
        plt.subplot(2, 1, 1)
        plt.plot(self.data['week_start'], self.data['close'], label='周收盘价', color='blue')
        plt.plot(self.data['week_start'], self.data['open'], label='周开盘价', color='green', linestyle='--')
        plt.title(f'{self.ticker} 周线价格走势')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # 成交量
        plt.subplot(2, 1, 2)
        plt.bar(self.data['week_start'], self.data['volume'], label='周成交量', color='orange')
        plt.title(f'{self.ticker} 周线成交量')
        plt.xlabel('日期')
        plt.ylabel('成交量')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_price_volume.png')
        plt.savefig(chart_path)
        print(f"周线价格和成交量图表已保存为: {chart_path}")
    
    def plot_technical_indicators(self):
        """绘制周线技术指标图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 15))
        
        # 价格和移动平均线
        plt.subplot(3, 1, 1)
        plt.plot(self.data['week_start'], self.data['close'], label='周收盘价', color='blue')
        if 'MA5' in self.data.columns:
            plt.plot(self.data['week_start'], self.data['MA5'], label='MA5', color='red', linestyle='--')
        if 'MA20' in self.data.columns:
            plt.plot(self.data['week_start'], self.data['MA20'], label='MA20', color='green', linestyle='--')
        if 'MA60' in self.data.columns:
            plt.plot(self.data['week_start'], self.data['MA60'], label='MA60', color='purple', linestyle='--')
        plt.title(f'{self.ticker} 周线价格和移动平均线')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # RSI
        if 'RSI_6' in self.data.columns:
            plt.subplot(3, 1, 2)
            plt.plot(self.data['week_start'], self.data['RSI_6'], label='RSI_6', color='purple')
            plt.axhline(y=70, color='red', linestyle='--', label='超买线')
            plt.axhline(y=30, color='green', linestyle='--', label='超卖线')
            plt.title(f'{self.ticker} 周线RSI_6指标')
            plt.xlabel('日期')
            plt.ylabel('RSI_6')
            plt.legend()
            plt.grid(True)
        
        # MACD
        if 'MACD' in self.data.columns and 'MACD_signal' in self.data.columns:
            plt.subplot(3, 1, 3)
            plt.plot(self.data['week_start'], self.data['MACD'], label='MACD', color='blue')
            plt.plot(self.data['week_start'], self.data['MACD_signal'], label='MACD Signal', color='red')
            if 'MACD_hist' in self.data.columns:
                plt.bar(self.data['week_start'], self.data['MACD_hist'], label='MACD Hist', color='green', alpha=0.5)
            plt.title(f'{self.ticker} 周线MACD指标')
            plt.xlabel('日期')
            plt.ylabel('MACD')
            plt.legend()
            plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_technical_indicators.png')
        plt.savefig(chart_path)
        print(f"周线技术指标图表已保存为: {chart_path}")
    
    def plot_bollinger_bands(self):
        """绘制周线布林带图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        if 'BB_upper' in self.data.columns and 'BB_middle' in self.data.columns and 'BB_lower' in self.data.columns:
            plt.figure(figsize=(15, 8))
            plt.plot(self.data['week_start'], self.data['close'], label='周收盘价', color='blue')
            plt.plot(self.data['week_start'], self.data['BB_upper'], label='布林带上轨', color='red', linestyle='--')
            plt.plot(self.data['week_start'], self.data['BB_middle'], label='布林带中轨', color='green', linestyle='--')
            plt.plot(self.data['week_start'], self.data['BB_lower'], label='布林带下轨', color='purple', linestyle='--')
            plt.fill_between(self.data['week_start'], self.data['BB_lower'], self.data['BB_upper'], alpha=0.1, color='gray')
            plt.title(f'{self.ticker} 周线布林带分析')
            plt.xlabel('日期')
            plt.ylabel('价格')
            plt.legend()
            plt.grid(True)
            plt.tight_layout()
            chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_bollinger_bands.png')
            plt.savefig(chart_path)
            print(f"周线布林带图表已保存为: {chart_path}")
    
    def correlation_analysis(self):
        """相关性分析"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 选择关键技术指标
        indicators = ['close', 'MA5', 'MA20', 'MA60', 'VOL5', 'K', 'D', 'J', 'MACD', 'RSI_6', 'CCI', 'WR']
        available_indicators = [ind for ind in indicators if ind in self.data.columns]
        
        # 计算相关性矩阵
        corr_matrix = self.data[available_indicators].corr()
        
        # 绘制相关性热力图
        plt.figure(figsize=(12, 10))
        sns.heatmap(corr_matrix, annot=True, cmap='coolwarm', fmt='.2f')
        plt.title(f'{self.ticker} 周线技术指标相关性分析')
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_correlation.png')
        plt.savefig(chart_path)
        print(f"周线相关性分析图表已保存为: {chart_path}")
        
        # 显示与收盘价相关性最高的指标
        if 'close' in available_indicators:
            close_corr = corr_matrix['close'].sort_values(ascending=False)
            print("\n与周收盘价相关性排序:")
            print(close_corr)
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.check_data_quality()
        self.plot_price_volume()
        self.plot_technical_indicators()
        self.plot_bollinger_bands()
        self.correlation_analysis()
        print("\n=== 周线数据分析完成 ===")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="分析股票周线数据")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所）")
    args = parser.parse_args()
    
    if not args.ticker:
        print("请指定股票代码，例如：python weekly_data_analysis.py --ticker 300433.SZ")
        exit(1)
    
    # 构建周线数据文件路径
    ticker = args.ticker
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_weekly_data.csv'
    
    if not os.path.exists(file_path):
        print(f"周线数据文件不存在: {file_path}")
        print("请先运行 stock_weekly_analyzer.py 生成周线数据")
        exit(1)
    
    print(f"分析股票: {ticker}")
    
    # 运行周线分析
    analyzer = WeeklyDataAnalyzer(file_path)
    analyzer.run_analysis()
