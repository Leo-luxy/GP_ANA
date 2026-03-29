# weekly_quantitative_strategy.py
# 功能：基于周线技术指标的量化交易策略回测
# 实现原理：
# 1. 加载股票周线数据，包括价格和技术指标
# 2. 计算交易信号（基于布林带、MA交叉和RSI指标）
# 3. 执行策略回测，模拟买入卖出操作
# 4. 计算策略评估指标（年化收益率、波动率、夏普比率、最大回撤等）
# 5. 绘制回测结果图表，展示价格走势、交易信号和portfolio价值

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
from config import DATA_DIR, WEEKLY_STRATEGY_CONFIG

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class WeeklyQuantitativeStrategy:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        # 使用配置文件中的初始资金
        self.initial_capital = WEEKLY_STRATEGY_CONFIG['initial_capital']  # 初始资金
        self.position = 0  # 持仓数量
        self.cash = self.initial_capital  # 现金
        self.portfolio_value = []  #  portfolio价值历史
        # 资金管理参数
        self.position_size = 0.3  # 每次买入/卖出的资金比例（30%）
        self.max_positions = 3  # 最大持仓批次
        self.current_positions = 0  # 当前持仓批次
        # 交易成本参数
        self.trade_cost = 0.001  # 交易成本比例（0.1%）
        # 止损参数
        self.stop_loss_pct = 0.1  # 固定止损比例（10%）
        # 持仓批次记录
        self.position_batches = []  # 记录每个批次的买入价格、数量和日期
    
    def load_data(self):
        """加载周线数据"""
        print(f"加载周线数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'week_start' in self.data.columns:
            self.data['week_start'] = pd.to_datetime(self.data['week_start'])
        
        # 从文件名中提取股票代码
        self.ticker = os.path.basename(self.file_path).split('_')[0]
        
        return self.data
    
    def calculate_signals(self):
        """计算交易信号"""
        # 使用配置文件中的策略参数
        rsi_buy_threshold = WEEKLY_STRATEGY_CONFIG['rsi_buy_threshold']
        rsi_sell_threshold = WEEKLY_STRATEGY_CONFIG['rsi_sell_threshold']
        bb_buy_mult = WEEKLY_STRATEGY_CONFIG['bb_buy_mult']
        bb_sell_mult = WEEKLY_STRATEGY_CONFIG['bb_sell_mult']
        
        # 1. 布林带信号
        if 'BB_lower' in self.data.columns and 'BB_upper' in self.data.columns:
            self.data['bb_buy_signal'] = (self.data['close'] < self.data['BB_lower'] * bb_buy_mult).astype(int)
            self.data['bb_sell_signal'] = (self.data['close'] > self.data['BB_upper'] * bb_sell_mult).astype(int)
        else:
            self.data['bb_buy_signal'] = 0
            self.data['bb_sell_signal'] = 0
        
        # 2. MA交叉信号
        if 'MA5' in self.data.columns and 'MA20' in self.data.columns:
            self.data['MA5_above_MA20'] = (self.data['MA5'] > self.data['MA20']).astype(int)
            self.data['ma_crossover'] = self.data['MA5_above_MA20'].diff()
            self.data['ma_buy_signal'] = (self.data['ma_crossover'] == 1).astype(int)
            self.data['ma_sell_signal'] = (self.data['ma_crossover'] == -1).astype(int)
        else:
            self.data['ma_buy_signal'] = 0
            self.data['ma_sell_signal'] = 0
        
        # 3. RSI信号（使用RSI_6更适合周线分析）
        if 'RSI_6' in self.data.columns:
            self.data['rsi_buy_signal'] = (self.data['RSI_6'] < rsi_buy_threshold).astype(int)
            self.data['rsi_sell_signal'] = (self.data['RSI_6'] > rsi_sell_threshold).astype(int)
        else:
            self.data['rsi_buy_signal'] = 0
            self.data['rsi_sell_signal'] = 0
        
        # 4. 综合信号
        # 买入信号：布林带突破下轨 OR MA金叉 OR RSI超卖
        self.data['buy_signal'] = ((self.data['bb_buy_signal'] == 1) | 
                                 (self.data['ma_buy_signal'] == 1) | 
                                 (self.data['rsi_buy_signal'] == 1)).astype(int)
        
        # 卖出信号：布林带突破上轨 OR MA死叉 OR RSI超买
        self.data['sell_signal'] = ((self.data['bb_sell_signal'] == 1) | 
                                  (self.data['ma_sell_signal'] == 1) | 
                                  (self.data['rsi_sell_signal'] == 1)).astype(int)
        
        # 解决同时出现买入和卖出信号的问题：当同时出现时，优先考虑卖出信号
        # 因为卖出信号通常表示趋势反转或超买，应该先平仓再考虑买入
        for i in range(len(self.data)):
            if self.data['buy_signal'].iloc[i] == 1 and self.data['sell_signal'].iloc[i] == 1:
                self.data.loc[self.data.index[i], 'buy_signal'] = 0
                print(f"日期 {self.data['week_start'].iloc[i]}: 同时出现买入和卖出信号，优先保留卖出信号")
        
        return self.data
    
    def backtest_strategy(self):
        """回测策略"""
        print("\n=== 周线策略回测 ===")
        
        # 初始化
        self.position = 0
        self.cash = self.initial_capital
        self.portfolio_value = []
        self.current_positions = 0  # 当前持仓批次
        self.position_batches = []  # 记录每个批次的买入价格、数量和日期
        position_size = self.position_size  # 每次买入/卖出的资金比例
        max_positions = self.max_positions  # 最大持仓批次
        
        # 遍历每一个交易周
        for i in range(len(self.data)):
            date = self.data['week_start'].iloc[i]
            close_price = self.data['close'].iloc[i]
            buy_signal = self.data['buy_signal'].iloc[i]
            sell_signal = self.data['sell_signal'].iloc[i]
            
            # 检查止损条件
            if self.position > 0:
                # 遍历所有持仓批次，检查止损
                batches_to_remove = []
                for j, (buy_price, shares, buy_date) in enumerate(self.position_batches):
                    # 1. 固定百分比止损
                    stop_loss_price = buy_price * (1 - self.stop_loss_pct)
                    # 2. 技术指标止损条件
                    technical_stop = False
                    # 3. 时间止损条件（持仓超过10周）
                    time_stop = False
                    
                    try:
                        # 技术指标止损 - 价格跌破MA20
                        if 'MA20' in self.data.columns and close_price < self.data['MA20'].iloc[i]:
                            technical_stop = True
                        # 时间止损
                        if i - buy_date > 10:  # 持仓超过10个交易周
                            time_stop = True
                    except Exception as e:
                        pass
                    
                    # 触发止损条件
                    if close_price <= stop_loss_price or (technical_stop and close_price < buy_price * 0.95) or time_stop:
                        # 触发止损
                        sell_amount = shares * close_price
                        # 计算交易成本
                        cost = sell_amount * self.trade_cost
                        self.cash += sell_amount - cost
                        self.position -= shares
                        self.current_positions -= 1
                        batches_to_remove.append(j)
                        if close_price <= stop_loss_price:
                            print(f"{date}: 止损卖出 {shares} 股，价格: {close_price:.2f}，止损价格: {stop_loss_price:.2f}")
                        elif technical_stop:
                            print(f"{date}: 技术指标止损卖出 {shares} 股，价格: {close_price:.2f}")
                        elif time_stop:
                            print(f"{date}: 时间止损卖出 {shares} 股，价格: {close_price:.2f}")
                
                # 移除触发止损的批次
                for j in reversed(batches_to_remove):
                    self.position_batches.pop(j)
            
            # 执行买入信号（分批买入）
            if buy_signal == 1 and self.current_positions < max_positions:
                # 计算本次买入的资金量
                buy_amount = self.cash * position_size
                if buy_amount > 0:
                    # 计算可购买的股票数量
                    shares_to_buy = int(buy_amount / close_price)
                    if shares_to_buy > 0:
                        # 计算交易成本
                        cost = buy_amount * self.trade_cost
                        if self.cash >= buy_amount + cost:
                            self.position += shares_to_buy
                            self.cash -= buy_amount + cost
                            self.current_positions += 1
                            # 记录批次信息（包含买入日期）
                            self.position_batches.append((close_price, shares_to_buy, i))
                            print(f"{date}: 买入 {shares_to_buy} 股，价格: {close_price:.2f}，持仓批次: {self.current_positions}/{max_positions}，交易成本: {cost:.2f}")
            
            # 执行卖出信号（分批卖出）
            elif sell_signal == 1 and self.current_positions > 0:
                # 计算本次卖出的股票数量（按批次比例）
                shares_to_sell = int(self.position * position_size)
                if shares_to_sell > 0:
                    sell_amount = shares_to_sell * close_price
                    # 计算交易成本
                    cost = sell_amount * self.trade_cost
                    self.cash += sell_amount - cost
                    self.position -= shares_to_sell
                    
                    # 按批次比例减少持仓
                    remaining_shares = shares_to_sell
                    batches_to_remove = []
                    for j, (buy_price, shares, buy_date) in enumerate(self.position_batches):
                        if remaining_shares > 0:
                            if shares <= remaining_shares:
                                # 卖出整个批次
                                remaining_shares -= shares
                                batches_to_remove.append(j)
                                self.current_positions -= 1
                            else:
                                # 卖出部分批次
                                self.position_batches[j] = (buy_price, shares - remaining_shares, buy_date)
                                remaining_shares = 0
                    
                    # 移除完全卖出的批次
                    for j in reversed(batches_to_remove):
                        self.position_batches.pop(j)
                    
                    print(f"{date}: 卖出 {shares_to_sell} 股，价格: {close_price:.2f}，剩余持仓: {self.position} 股，交易成本: {cost:.2f}")
            
            # 计算当前portfolio价值
            current_value = self.cash + (self.position * close_price)
            self.portfolio_value.append(current_value)
        
        # 回测结束时，如果还有持仓，卖出所有持仓
        if self.position > 0:
            final_price = self.data['close'].iloc[-1]
            sell_amount = self.position * final_price
            # 计算交易成本
            cost = sell_amount * self.trade_cost
            self.cash += sell_amount - cost
            print(f"{self.data['week_start'].iloc[-1]}: 结束回测，卖出 {self.position} 股，价格: {final_price:.2f}，交易成本: {cost:.2f}")
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
        # 计算每周收益率
        returns = np.diff(self.portfolio_value) / self.portfolio_value[:-1]
        
        # 计算年化收益率
        num_trading_weeks = len(returns)
        annual_return = (self.portfolio_value[-1] / self.initial_capital) ** (52 / num_trading_weeks) - 1
        
        # 计算波动率
        volatility = np.std(returns) * np.sqrt(52)
        
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
        
        print("\n=== 周线策略评估指标 ===")
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
        buy_signals = self.data[self.data['buy_signal'] == 1][['week_start', 'close', 'RSI_6', 'MA5', 'MA20', 'BB_lower', 'BB_upper']].copy()
        buy_signals['signal_type'] = 'buy'
        
        # 提取卖出信号
        sell_signals = self.data[self.data['sell_signal'] == 1][['week_start', 'close', 'RSI_6', 'MA5', 'MA20', 'BB_lower', 'BB_upper']].copy()
        sell_signals['signal_type'] = 'sell'
        
        # 合并信号
        all_signals = pd.concat([buy_signals, sell_signals], ignore_index=True)
        
        # 按日期排序
        all_signals = all_signals.sort_values('week_start')
        
        # 调整列顺序，把signal_type放到第二列
        all_signals = all_signals[['week_start', 'signal_type', 'close', 'RSI_6', 'MA5', 'MA20', 'BB_lower', 'BB_upper']]
        
        # 保存为CSV文件
        signals_path = os.path.join(stock_dir, f'{self.ticker}_weekly_trading_signals.csv')
        all_signals.to_csv(signals_path, index=False, encoding='utf-8-sig')
        print(f"周线交易信号数据已保存为: {signals_path}")
        
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
        plt.plot(self.data['week_start'], self.data['close'], label='周收盘价', color='blue')
        if 'BB_upper' in self.data.columns and 'BB_middle' in self.data.columns and 'BB_lower' in self.data.columns:
            plt.plot(self.data['week_start'], self.data['BB_upper'], label='布林带上轨', color='red', linestyle='--')
            plt.plot(self.data['week_start'], self.data['BB_middle'], label='布林带中轨', color='green', linestyle='--')
            plt.plot(self.data['week_start'], self.data['BB_lower'], label='布林带下轨', color='purple', linestyle='--')
        
        # 标记买入卖出信号
        buy_signals = self.data[self.data['buy_signal'] == 1]
        sell_signals = self.data[self.data['sell_signal'] == 1]
        plt.scatter(buy_signals['week_start'], buy_signals['close'], marker='^', color='green', label='买入信号', s=100)
        plt.scatter(sell_signals['week_start'], sell_signals['close'], marker='v', color='red', label='卖出信号', s=100)
        
        plt.title(f'{self.ticker} 周线价格走势与交易信号')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # portfolio价值走势
        plt.subplot(3, 1, 2)
        plt.plot(self.data['week_start'], self.portfolio_value, label='Portfolio价值', color='purple')
        plt.axhline(y=self.initial_capital, color='gray', linestyle='--', label='初始资金')
        plt.title(f'{self.ticker} 周线Portfolio价值走势')
        plt.xlabel('日期')
        plt.ylabel('价值')
        plt.legend()
        plt.grid(True)
        
        # 每周收益率
        plt.subplot(3, 1, 3)
        weekly_returns = np.diff(self.portfolio_value) / self.portfolio_value[:-1] * 100
        plt.plot(self.data['week_start'].iloc[1:], weekly_returns, label='每周收益率', color='green')
        plt.axhline(y=0, color='gray', linestyle='--')
        plt.title(f'{self.ticker} 每周收益率')
        plt.xlabel('日期')
        plt.ylabel('收益率 (%)')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_strategy_results.png')
        plt.savefig(chart_path)
        print(f"周线策略回测结果图表已保存为: {chart_path}")
    
    def run_strategy(self):
        """运行完整策略"""
        self.load_data()
        self.calculate_signals()
        final_value, total_return = self.backtest_strategy()
        metrics = self.calculate_metrics()
        self.plot_results()
        self.save_signals()
        print("\n=== 周线策略运行完成 ===")
        return final_value, total_return, metrics

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="基于周线技术指标的量化交易策略回测")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所）")
    args = parser.parse_args()
    
    if not args.ticker:
        print("请指定股票代码，例如：python weekly_quantitative_strategy.py --ticker 300433.SZ")
        exit(1)
    
    # 构建周线数据文件路径
    ticker = args.ticker
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_weekly_data.csv'
    
    if not os.path.exists(file_path):
        print(f"周线数据文件不存在: {file_path}")
        print("请先运行 stock_weekly_analyzer.py 生成周线数据")
        exit(1)
    
    print(f"分析股票: {ticker}")
    
    # 运行策略
    strategy = WeeklyQuantitativeStrategy(file_path)
    final_value, total_return, metrics = strategy.run_strategy()
