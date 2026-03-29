# quantitative_strategy.py
# 功能：基于技术指标的量化交易策略回测
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 计算交易信号（基于布林带、MA交叉和RSI指标）
# 3. 执行策略回测，模拟买入卖出操作
# 4. 计算策略评估指标（年化收益率、波动率、夏普比率、最大回撤等）
# 5. 绘制回测结果图表，展示价格走势、交易信号和portfolio价值

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, STRATEGY_CONFIG

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class QuantitativeStrategy:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        # 使用配置文件中的初始资金
        self.initial_capital = STRATEGY_CONFIG['initial_capital']  # 初始资金
        self.position = 0  # 持仓数量
        self.cash = self.initial_capital  # 现金
        self.portfolio_value = []  #  portfolio价值历史
    
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
        # 使用配置文件中的策略参数
        rsi_buy_threshold = STRATEGY_CONFIG['rsi_buy_threshold']
        rsi_sell_threshold = STRATEGY_CONFIG['rsi_sell_threshold']
        bb_buy_mult = STRATEGY_CONFIG['bb_buy_mult']
        bb_sell_mult = STRATEGY_CONFIG['bb_sell_mult']
        
        # 1. 布林带信号
        self.data['bb_buy_signal'] = (self.data['close'] < self.data['BB_lower'] * bb_buy_mult).astype(int)
        self.data['bb_sell_signal'] = (self.data['close'] > self.data['BB_upper'] * bb_sell_mult).astype(int)
        
        # 2. MA交叉信号
        self.data['MA5_above_MA20'] = (self.data['MA5'] > self.data['MA20']).astype(int)
        self.data['ma_crossover'] = self.data['MA5_above_MA20'].diff()
        self.data['ma_buy_signal'] = (self.data['ma_crossover'] == 1).astype(int)
        self.data['ma_sell_signal'] = (self.data['ma_crossover'] == -1).astype(int)
        
        # 3. RSI信号（使用标准的RSI_14周期）
        self.data['rsi_buy_signal'] = (self.data['RSI'] < rsi_buy_threshold).astype(int)
        self.data['rsi_sell_signal'] = (self.data['RSI'] > rsi_sell_threshold).astype(int)
        
        # 4. 综合信号
        # 买入信号：布林带突破下轨 OR (MA金叉 AND RSI超卖)
        self.data['buy_signal'] = ((self.data['bb_buy_signal'] == 1) | 
                                 ((self.data['ma_buy_signal'] == 1) & (self.data['rsi_buy_signal'] == 1))).astype(int)
        
        # 卖出信号：布林带突破上轨 OR (MA死叉 AND RSI超买)
        self.data['sell_signal'] = ((self.data['bb_sell_signal'] == 1) | 
                                  ((self.data['ma_sell_signal'] == 1) & (self.data['rsi_sell_signal'] == 1))).astype(int)
        
        # 解决同时出现买入和卖出信号的问题：当同时出现时，优先考虑卖出信号
        # 因为卖出信号通常表示趋势反转或超买，应该先平仓再考虑买入
        for i in range(len(self.data)):
            if self.data['buy_signal'].iloc[i] == 1 and self.data['sell_signal'].iloc[i] == 1:
                self.data.loc[self.data.index[i], 'buy_signal'] = 0
                print(f"日期 {self.data['date'].iloc[i]}: 同时出现买入和卖出信号，优先保留卖出信号")
        
        return self.data
    
    def backtest_strategy(self):
        """回测策略"""
        print("\n=== 策略回测 ===")
        
        # 初始化
        self.position = 0
        self.cash = self.initial_capital
        self.portfolio_value = []
        
        # 遍历每一个交易日
        for i in range(len(self.data)):
            date = self.data['date'].iloc[i]
            close_price = self.data['close'].iloc[i]
            buy_signal = self.data['buy_signal'].iloc[i]
            sell_signal = self.data['sell_signal'].iloc[i]
            
            # 执行买入信号
            if buy_signal == 1 and self.position == 0:
                # 计算可购买的股票数量
                shares_to_buy = int(self.cash / close_price)
                self.position = shares_to_buy
                self.cash -= shares_to_buy * close_price
                print(f"{date}: 买入 {shares_to_buy} 股，价格: {close_price:.2f}")
            
            # 执行卖出信号
            elif sell_signal == 1 and self.position > 0:
                # 卖出所有持仓
                self.cash += self.position * close_price
                print(f"{date}: 卖出 {self.position} 股，价格: {close_price:.2f}")
                self.position = 0
            
            # 计算当前portfolio价值
            current_value = self.cash + (self.position * close_price)
            self.portfolio_value.append(current_value)
        
        # 回测结束时，如果还有持仓，卖出所有持仓
        if self.position > 0:
            final_price = self.data['close'].iloc[-1]
            self.cash += self.position * final_price
            print(f"{self.data['date'].iloc[-1]}: 结束回测，卖出 {self.position} 股，价格: {final_price:.2f}")
            self.position = 0
        
        # 计算最终portfolio价值
        final_value = self.cash
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        
        print(f"\n初始资金: {self.initial_capital:.2f}")
        print(f"最终资金: {final_value:.2f}")
        print(f"总收益率: {total_return:.2f}%")
        
        return final_value, total_return
    
    def calculate_metrics(self):
        """计算策略评估指标"""
        # 计算每日收益率
        returns = np.diff(self.portfolio_value) / self.portfolio_value[:-1]
        
        # 计算年化收益率
        num_trading_days = len(returns)
        annual_return = (self.portfolio_value[-1] / self.initial_capital) ** (252 / num_trading_days) - 1
        
        # 计算波动率
        volatility = np.std(returns) * np.sqrt(252)
        
        # 计算夏普比率（假设无风险利率为3%）
        risk_free_rate = 0.03
        sharpe_ratio = (annual_return - risk_free_rate) / volatility
        
        # 计算最大回撤
        portfolio_array = np.array(self.portfolio_value)
        peak = portfolio_array[0]
        max_drawdown = 0
        
        for value in portfolio_array:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        
        # 计算胜率
        buy_signals = self.data[self.data['buy_signal'] == 1]
        sell_signals = self.data[self.data['sell_signal'] == 1]
        
        winning_trades = 0
        total_trades = 0
        
        for i in range(len(buy_signals)):
            buy_date = buy_signals.index[i]
            # 找到下一个卖出信号
            sell_candidates = sell_signals[sell_signals.index > buy_date]
            if not sell_candidates.empty:
                sell_date = sell_candidates.index[0]
                buy_price = self.data['close'].iloc[buy_date]
                sell_price = self.data['close'].iloc[sell_date]
                if sell_price > buy_price:
                    winning_trades += 1
                total_trades += 1
        
        win_rate = winning_trades / total_trades if total_trades > 0 else 0
        
        print("\n=== 策略评估指标 ===")
        print(f"年化收益率: {annual_return * 100:.2f}%")
        print(f"年化波动率: {volatility * 100:.2f}%")
        print(f"夏普比率: {sharpe_ratio:.2f}")
        print(f"最大回撤: {max_drawdown * 100:.2f}%")
        print(f"胜率: {win_rate * 100:.2f}%")
        print(f"总交易次数: {total_trades}")
        
        return {
            'annual_return': annual_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': total_trades
        }
    
    def save_signals(self):
        """保存交易信号数据"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 提取买入信号
        buy_signals = self.data[self.data['buy_signal'] == 1][['date', 'close', 'RSI', 'MA5', 'MA20', 'BB_lower', 'BB_upper']].copy()
        buy_signals['signal_type'] = 'buy'
        
        # 提取卖出信号
        sell_signals = self.data[self.data['sell_signal'] == 1][['date', 'close', 'RSI', 'MA5', 'MA20', 'BB_lower', 'BB_upper']].copy()
        sell_signals['signal_type'] = 'sell'
        
        # 合并信号
        all_signals = pd.concat([buy_signals, sell_signals], ignore_index=True)
        
        # 按日期排序
        all_signals = all_signals.sort_values('date')
        
        # 调整列顺序，把signal_type放到第二列
        all_signals = all_signals[['date', 'signal_type', 'close', 'RSI', 'MA5', 'MA20', 'BB_lower', 'BB_upper']]
        
        # 保存为CSV文件
        signals_path = os.path.join(stock_dir, f'{self.ticker}_trading_signals.csv')
        all_signals.to_csv(signals_path, index=False, encoding='utf-8-sig')
        print(f"交易信号数据已保存为: {signals_path}")
        
        return signals_path
    
    def plot_results(self):
        """绘制回测结果"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 12))
        
        # 价格走势与交易信号
        plt.subplot(3, 1, 1)
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['BB_upper'], label='布林带上轨', color='red', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_middle'], label='布林带中轨', color='green', linestyle='--')
        plt.plot(self.data['date'], self.data['BB_lower'], label='布林带下轨', color='purple', linestyle='--')
        
        # 标记买入卖出信号
        buy_signals = self.data[self.data['buy_signal'] == 1]
        sell_signals = self.data[self.data['sell_signal'] == 1]
        plt.scatter(buy_signals['date'], buy_signals['close'], marker='^', color='green', label='买入信号', s=100)
        plt.scatter(sell_signals['date'], sell_signals['close'], marker='v', color='red', label='卖出信号', s=100)
        
        plt.title(f'{self.ticker} 价格走势与交易信号')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # portfolio价值走势
        plt.subplot(3, 1, 2)
        plt.plot(self.data['date'], self.portfolio_value, label='Portfolio价值', color='purple')
        plt.axhline(y=self.initial_capital, color='gray', linestyle='--', label='初始资金')
        plt.title(f'{self.ticker} Portfolio价值走势')
        plt.xlabel('日期')
        plt.ylabel('价值')
        plt.legend()
        plt.grid(True)
        
        # 每日收益率
        plt.subplot(3, 1, 3)
        daily_returns = np.diff(self.portfolio_value) / self.portfolio_value[:-1] * 100
        plt.plot(self.data['date'].iloc[1:], daily_returns, label='每日收益率', color='green')
        plt.axhline(y=0, color='gray', linestyle='--')
        plt.title(f'{self.ticker} 每日收益率')
        plt.xlabel('日期')
        plt.ylabel('收益率 (%)')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_strategy_results.png')
        plt.savefig(chart_path)
        print(f"策略回测结果图表已保存为: {chart_path}")
    
    def run_strategy(self):
        """运行完整策略"""
        self.load_data()
        self.calculate_signals()
        final_value, total_return = self.backtest_strategy()
        metrics = self.calculate_metrics()
        self.plot_results()
        self.save_signals()
        print("\n=== 策略运行完成 ===")
        return final_value, total_return, metrics

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="基于技术指标的量化交易策略回测")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认使用config.py中的配置")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
        ticker_name = ticker
    else:
        # 使用第一个股票代码进行策略回测
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker}")
    
    # 运行策略
    strategy = QuantitativeStrategy(file_path)
    final_value, total_return, metrics = strategy.run_strategy()
