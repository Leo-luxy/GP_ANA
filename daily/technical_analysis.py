# technical_analysis.py
# 功能：技术指标信号分析和有效性评估
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 计算各种技术信号（MA交叉、MACD交叉、RSI超买超卖、KDJ交叉、布林带突破）
# 3. 评估每种信号的有效性，计算信号成功率
# 4. 绘制信号分析图表，展示价格走势和信号位置

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class TechnicalAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
    
    def load_data(self):
        """加载数据"""
        print(f"加载数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
        
        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[0]
        
        return self.data
    
    def calculate_signals(self):
        """计算交易信号"""
        # 计算价格变化
        self.data['price_change'] = self.data['close'].pct_change()
        self.data['next_day_change'] = self.data['price_change'].shift(-1)
        
        # 1. MA交叉信号
        self.data['MA5_above_MA20'] = (self.data['MA5'] > self.data['MA20']).astype(int)
        self.data['MA_crossover'] = self.data['MA5_above_MA20'].diff()
        
        # 2. MACD信号
        self.data['MACD_above_signal'] = (self.data['MACD'] > self.data['MACD_signal']).astype(int)
        self.data['MACD_crossover'] = self.data['MACD_above_signal'].diff()
        
        # 3. RSI超买超卖信号
        self.data['RSI_overbought'] = (self.data['RSI'] > 70).astype(int)
        self.data['RSI_oversold'] = (self.data['RSI'] < 30).astype(int)
        
        # 4. KDJ信号
        self.data['KDJ_golden_cross'] = ((self.data['K'] > self.data['D']) & (self.data['K'].shift() <= self.data['D'].shift())).astype(int)
        self.data['KDJ_death_cross'] = ((self.data['K'] < self.data['D']) & (self.data['K'].shift() >= self.data['D'].shift())).astype(int)
        
        # 5. 布林带信号
        self.data['price_above_upper'] = (self.data['close'] > self.data['BB_upper']).astype(int)
        self.data['price_below_lower'] = (self.data['close'] < self.data['BB_lower']).astype(int)
        
        return self.data
    
    def evaluate_signals(self):
        """评估信号有效性"""
        print("\n=== 信号有效性评估 ===")
        
        # 评估MA交叉信号
        ma_buy_signals = self.data[self.data['MA_crossover'] == 1]
        ma_sell_signals = self.data[self.data['MA_crossover'] == -1]
        
        print(f"MA金叉信号数量: {len(ma_buy_signals)}")
        if len(ma_buy_signals) > 0:
            ma_buy_success = (ma_buy_signals['next_day_change'] > 0).mean()
            print(f"MA金叉信号成功率: {ma_buy_success:.2f}")
        
        print(f"MA死叉信号数量: {len(ma_sell_signals)}")
        if len(ma_sell_signals) > 0:
            ma_sell_success = (ma_sell_signals['next_day_change'] < 0).mean()
            print(f"MA死叉信号成功率: {ma_sell_success:.2f}")
        
        # 评估MACD信号
        macd_buy_signals = self.data[self.data['MACD_crossover'] == 1]
        macd_sell_signals = self.data[self.data['MACD_crossover'] == -1]
        
        print(f"\nMACD金叉信号数量: {len(macd_buy_signals)}")
        if len(macd_buy_signals) > 0:
            macd_buy_success = (macd_buy_signals['next_day_change'] > 0).mean()
            print(f"MACD金叉信号成功率: {macd_buy_success:.2f}")
        
        print(f"MACD死叉信号数量: {len(macd_sell_signals)}")
        if len(macd_sell_signals) > 0:
            macd_sell_success = (macd_sell_signals['next_day_change'] < 0).mean()
            print(f"MACD死叉信号成功率: {macd_sell_success:.2f}")
        
        # 评估RSI信号
        rsi_oversold_signals = self.data[self.data['RSI_oversold'] == 1]
        rsi_overbought_signals = self.data[self.data['RSI_overbought'] == 1]
        
        print(f"\nRSI超卖信号数量: {len(rsi_oversold_signals)}")
        if len(rsi_oversold_signals) > 0:
            rsi_oversold_success = (rsi_oversold_signals['next_day_change'] > 0).mean()
            print(f"RSI超卖信号成功率: {rsi_oversold_success:.2f}")
        
        print(f"RSI超买信号数量: {len(rsi_overbought_signals)}")
        if len(rsi_overbought_signals) > 0:
            rsi_overbought_success = (rsi_overbought_signals['next_day_change'] < 0).mean()
            print(f"RSI超买信号成功率: {rsi_overbought_success:.2f}")
        
        # 评估KDJ信号
        kdj_golden_signals = self.data[self.data['KDJ_golden_cross'] == 1]
        kdj_death_signals = self.data[self.data['KDJ_death_cross'] == 1]
        
        print(f"\nKDJ金叉信号数量: {len(kdj_golden_signals)}")
        if len(kdj_golden_signals) > 0:
            kdj_golden_success = (kdj_golden_signals['next_day_change'] > 0).mean()
            print(f"KDJ金叉信号成功率: {kdj_golden_success:.2f}")
        
        print(f"KDJ死叉信号数量: {len(kdj_death_signals)}")
        if len(kdj_death_signals) > 0:
            kdj_death_success = (kdj_death_signals['next_day_change'] < 0).mean()
            print(f"KDJ死叉信号成功率: {kdj_death_success:.2f}")
        
        # 评估布林带信号
        bb_buy_signals = self.data[self.data['price_below_lower'] == 1]
        bb_sell_signals = self.data[self.data['price_above_upper'] == 1]
        
        print(f"\n布林带突破下轨信号数量: {len(bb_buy_signals)}")
        if len(bb_buy_signals) > 0:
            bb_buy_success = (bb_buy_signals['next_day_change'] > 0).mean()
            print(f"布林带突破下轨信号成功率: {bb_buy_success:.2f}")
        
        print(f"布林带突破上轨信号数量: {len(bb_sell_signals)}")
        if len(bb_sell_signals) > 0:
            bb_sell_success = (bb_sell_signals['next_day_change'] < 0).mean()
            print(f"布林带突破上轨信号成功率: {bb_sell_success:.2f}")
    
    def plot_signal_analysis(self):
        """绘制信号分析图表"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 12))
        
        # 价格走势与MA交叉信号
        plt.subplot(3, 1, 1)
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['MA5'], label='MA5', color='red')
        plt.plot(self.data['date'], self.data['MA20'], label='MA20', color='green')
        
        # 标记MA金叉和死叉
        golden_cross = self.data[self.data['MA_crossover'] == 1]
        death_cross = self.data[self.data['MA_crossover'] == -1]
        plt.scatter(golden_cross['date'], golden_cross['close'], marker='^', color='green', label='MA金叉', s=100)
        plt.scatter(death_cross['date'], death_cross['close'], marker='v', color='red', label='MA死叉', s=100)
        
        plt.title(f'{self.ticker} 价格走势与MA交叉信号')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # RSI信号
        plt.subplot(3, 1, 2)
        plt.plot(self.data['date'], self.data['RSI'], label='RSI', color='purple')
        plt.axhline(y=70, color='red', linestyle='--', label='超买线')
        plt.axhline(y=30, color='green', linestyle='--', label='超卖线')
        
        # 标记超买超卖
        overbought = self.data[self.data['RSI_overbought'] == 1]
        oversold = self.data[self.data['RSI_oversold'] == 1]
        plt.scatter(overbought['date'], overbought['RSI'], marker='v', color='red', label='超买', s=50)
        plt.scatter(oversold['date'], oversold['RSI'], marker='^', color='green', label='超卖', s=50)
        
        plt.title(f'{self.ticker} RSI信号')
        plt.xlabel('日期')
        plt.ylabel('RSI')
        plt.legend()
        plt.grid(True)
        
        # 布林带信号
        plt.subplot(3, 1, 3)
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['BB_upper'], label='上轨', color='red', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_middle'], label='中轨', color='green', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_lower'], label='下轨', color='purple', linestyle='--')
        
        # 标记突破信号
        above_upper = self.data[self.data['price_above_upper'] == 1]
        below_lower = self.data[self.data['price_below_lower'] == 1]
        plt.scatter(above_upper['date'], above_upper['close'], marker='v', color='red', label='突破上轨', s=50)
        plt.scatter(below_lower['date'], below_lower['close'], marker='^', color='green', label='突破下轨', s=50)
        
        plt.title(f'{self.ticker} 布林带信号')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_signal_analysis.png')
        plt.savefig(chart_path)
        print(f"信号分析图表已保存为: {chart_path}")
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.calculate_signals()
        self.evaluate_signals()
        self.plot_signal_analysis()
        print("\n=== 技术指标分析完成 ===")

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="技术指标信号分析和有效性评估")
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
    analyzer = TechnicalAnalyzer(file_path)
    analyzer.run_analysis()
