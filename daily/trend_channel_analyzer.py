# trend_channel_analyzer.py
# 功能：基于趋势通道分析的量化交易策略
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 识别股票的趋势通道（上升/下降）
# 3. 在上升通道开始时生成买入信号
# 4. 在上升通道转向下降通道时生成卖出信号
# 5. 回测策略性能
# 6. 绘制趋势通道和交易信号图表

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

class TrendChannelAnalyzer:
    def __init__(self, file_path, params=None):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        # 使用配置文件中的初始资金
        self.initial_capital = STRATEGY_CONFIG['initial_capital']  # 初始资金
        self.position = 0  # 持仓数量
        self.cash = self.initial_capital  # 现金
        self.portfolio_value = []  # portfolio价值历史
        
        # 默认参数
        self.params = params or {
            'window': 20,  # 移动平均窗口
            'std_multiplier': 2.0,  # 通道宽度倍数
            'slope_window': 5,  # 斜率计算窗口
            'rsi_threshold': 30,  # RSI超卖阈值
            'stop_loss_pct': 0.08,  # 止损百分比（增大以减少频繁止损）
            'take_profit_pct': 0.20,  # 止盈百分比（增大以提高收益）
            'trend_confirmation_days': 3,  # 趋势确认天数（增加以减少假信号）
            'trend_strength_threshold': 0.01,  # 趋势强度阈值
            'max_position_pct': 0.8,  # 最大仓位比例
            'sideways_margin': 0.005,  # 横盘裕度，斜率绝对值小于此值时认为是横盘
        }
    
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
        else:
            # 从文件路径中提取股票代码
            import os
            self.ticker = os.path.basename(self.file_path).split('_')[0]
        
        return self.data
    
    def calculate_trend_channels(self):
        """计算趋势通道"""
        window = self.params['window']
        std_multiplier = self.params['std_multiplier']
        slope_window = self.params['slope_window']
        
        # 计算移动平均线作为趋势线
        self.data['MA20'] = self.data['close'].rolling(window=window).mean()
        
        # 计算价格的标准差
        self.data['std'] = self.data['close'].rolling(window=window).std()
        
        # 计算通道上轨和下轨
        self.data['channel_upper'] = self.data['MA20'] + std_multiplier * self.data['std']
        self.data['channel_lower'] = self.data['MA20'] - std_multiplier * self.data['std']
        
        # 计算趋势方向
        # 使用MA20的斜率来判断趋势方向
        self.data['MA20_slope'] = self.data['MA20'].diff(slope_window) / slope_window
        
        # 计算RSI（如果数据中没有）
        if 'RSI' not in self.data.columns:
            delta = self.data['close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            self.data['RSI'] = 100 - (100 / (1 + rs))
        
        # 计算MACD（如果数据中没有）
        if 'MACD' not in self.data.columns:
            exp1 = self.data['close'].ewm(span=12, adjust=False).mean()
            exp2 = self.data['close'].ewm(span=26, adjust=False).mean()
            self.data['MACD'] = exp1 - exp2
            self.data['MACD_signal'] = self.data['MACD'].ewm(span=9, adjust=False).mean()
        
        # 趋势判断
        sideways_margin = self.params['sideways_margin']
        
        # 上升趋势：MA20斜率大于横盘裕度，且价格在通道中上部，且MACD>0
        self.data['uptrend'] = ((self.data['MA20_slope'] > sideways_margin) & 
                              (self.data['close'] > self.data['MA20']) &
                              (self.data['MACD'] > self.data['MACD_signal'])).astype(int)
        
        # 下降趋势：MA20斜率小于负的横盘裕度，且价格在通道中下部，且MACD<0
        self.data['downtrend'] = ((self.data['MA20_slope'] < -sideways_margin) & 
                               (self.data['close'] < self.data['MA20']) &
                               (self.data['MACD'] < self.data['MACD_signal'])).astype(int)
        
        # 无明显趋势（横盘）：斜率绝对值小于横盘裕度，或不满足上升/下降趋势条件
        self.data['sideways'] = ((self.data['uptrend'] == 0) & 
                               (self.data['downtrend'] == 0)).astype(int)
        
        # 趋势强度
        self.data['trend_strength'] = abs(self.data['MA20_slope']) / self.data['close'] * 100
        
        return self.data
    
    def generate_signals(self):
        """生成交易信号"""
        # 初始化信号列
        self.data['buy_signal'] = 0
        self.data['sell_signal'] = 0
        self.data['stop_loss_signal'] = 0
        self.data['take_profit_signal'] = 0
        
        rsi_threshold = self.params['rsi_threshold']
        trend_confirmation_days = self.params['trend_confirmation_days']
        trend_strength_threshold = self.params['trend_strength_threshold']
        
        # 计算趋势确认
        # 上升趋势确认：连续多天满足上升趋势条件
        self.data['uptrend_confirm'] = self.data['uptrend'].rolling(window=trend_confirmation_days).sum() >= trend_confirmation_days
        # 下降趋势确认：连续多天满足下降趋势条件
        self.data['downtrend_confirm'] = self.data['downtrend'].rolling(window=trend_confirmation_days).sum() >= trend_confirmation_days
        
        # 计算趋势变化
        self.data['uptrend_confirm_change'] = self.data['uptrend_confirm'].diff()
        self.data['downtrend_confirm_change'] = self.data['downtrend_confirm'].diff()
        
        # 计算RSI背离
        # 价格创新高但RSI未创新高，可能形成顶背离
        self.data['price_high'] = self.data['close'].rolling(window=20).max()
        self.data['rsi_high'] = self.data['RSI'].rolling(window=20).max()
        self.data['price_new_high'] = (self.data['close'] == self.data['price_high']).astype(int)
        self.data['rsi_new_high'] = (self.data['RSI'] == self.data['rsi_high']).astype(int)
        self.data['top_divergence'] = ((self.data['price_new_high'] == 1) & (self.data['rsi_new_high'] == 0)).astype(int)
        
        # 计算趋势强度变化
        self.data['trend_strength_change'] = self.data['trend_strength'].diff()
        
        # 买入信号：只在上升趋势开始时生成一次
        # 当从非上升趋势转为上升趋势确认时，且RSI不超买，且趋势强度足够
        buy_conditions = (self.data['uptrend_confirm_change'] == 1) & \
                         (self.data['RSI'] < 70) & \
                         (self.data['trend_strength'] > trend_strength_threshold)
        self.data.loc[buy_conditions, 'buy_signal'] = 1
        
        # 卖出信号：
        # 1. 上升趋势转下降趋势时
        # 2. 出现顶背离时
        # 3. 趋势强度明显减弱时
        for i in range(1, len(self.data)):
            # 上升趋势转下降趋势
            if self.data['uptrend_confirm'].iloc[i-1] and self.data['downtrend_confirm'].iloc[i]:
                self.data.loc[self.data.index[i], 'sell_signal'] = 1
            # 顶背离
            elif self.data['top_divergence'].iloc[i] == 1 and self.data['uptrend_confirm'].iloc[i]:
                self.data.loc[self.data.index[i], 'sell_signal'] = 1
            # 趋势强度明显减弱
            elif self.data['uptrend_confirm'].iloc[i] and self.data['trend_strength_change'].iloc[i] < -0.01:
                self.data.loc[self.data.index[i], 'sell_signal'] = 1
        
        # 确保在同一上升趋势中只生成一次买入信号
        # 记录已经生成买入信号的上升趋势区间
        in_uptrend = False
        for i in range(len(self.data)):
            if self.data['uptrend_confirm'].iloc[i]:
                if not in_uptrend:
                    in_uptrend = True
                    # 找到这个上升趋势中的第一个买入信号
                    buy_idx = i
                    while buy_idx < len(self.data) and self.data['uptrend_confirm'].iloc[buy_idx]:
                        if self.data['buy_signal'].iloc[buy_idx] == 1:
                            # 保留第一个买入信号，删除其他的
                            for j in range(buy_idx + 1, len(self.data)):
                                if not self.data['uptrend_confirm'].iloc[j]:
                                    break
                                if self.data['buy_signal'].iloc[j] == 1:
                                    self.data.loc[self.data.index[j], 'buy_signal'] = 0
                            break
                        buy_idx += 1
            else:
                in_uptrend = False
        
        # 确保在同一个趋势中只生成一次卖出信号
        # 遍历所有数据，标记每个趋势区间
        trend_intervals = []
        current_trend = None
        start_idx = 0
        
        for i in range(len(self.data)):
            # 确定当前趋势
            if self.data['uptrend_confirm'].iloc[i]:
                trend = 'uptrend'
            elif self.data['downtrend_confirm'].iloc[i]:
                trend = 'downtrend'
            else:
                trend = 'sideways'
            
            # 如果趋势变化，记录上一个趋势区间
            if current_trend is not None and trend != current_trend:
                trend_intervals.append({'start': start_idx, 'end': i-1, 'trend': current_trend})
                start_idx = i
            
            current_trend = trend
        
        # 记录最后一个趋势区间
        if current_trend is not None:
            trend_intervals.append({'start': start_idx, 'end': len(self.data)-1, 'trend': current_trend})
        
        # 对每个趋势区间，只保留第一个卖出信号
        for interval in trend_intervals:
            start = interval['start']
            end = interval['end']
            
            # 找到该区间内的第一个卖出信号
            first_sell = None
            for i in range(start, end + 1):
                if self.data['sell_signal'].iloc[i] == 1:
                    first_sell = i
                    break
            
            # 删除该区间内的其他卖出信号
            if first_sell is not None:
                for i in range(start, end + 1):
                    if i != first_sell and self.data['sell_signal'].iloc[i] == 1:
                        self.data.loc[self.data.index[i], 'sell_signal'] = 0
        
        # 解决同时出现买入和卖出信号的问题
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
        self.buy_price = 0  # 记录买入价格
        self.trades = []  # 记录所有交易
        
        stop_loss_pct = self.params['stop_loss_pct']
        take_profit_pct = self.params['take_profit_pct']
        
        # 遍历每一个交易日
        for i in range(len(self.data)):
            date = self.data['date'].iloc[i]
            close_price = self.data['close'].iloc[i]
            buy_signal = self.data['buy_signal'].iloc[i]
            sell_signal = self.data['sell_signal'].iloc[i]
            
            # 执行买入信号
            if buy_signal == 1 and self.position == 0:
                # 计算可购买的股票数量（考虑最大仓位限制）
                max_position = self.initial_capital * self.params['max_position_pct']
                max_shares = int(max_position / close_price)
                shares_to_buy = min(int(self.cash / close_price), max_shares)
                self.position = shares_to_buy
                self.buy_price = close_price
                self.cash -= shares_to_buy * close_price
                print(f"{date}: 买入 {shares_to_buy} 股，价格: {close_price:.2f}")
                # 记录买入交易
                self.trades.append({
                    'type': 'buy',
                    'date': date,
                    'price': close_price,
                    'shares': shares_to_buy
                })
            
            # 检查止盈止损
            if self.position > 0:
                # 计算止盈止损价格
                stop_loss_price = self.buy_price * (1 - stop_loss_pct)
                take_profit_price = self.buy_price * (1 + take_profit_pct)
                
                # 止盈
                if close_price >= take_profit_price:
                    self.cash += self.position * close_price
                    print(f"{date}: 止盈卖出 {self.position} 股，价格: {close_price:.2f}")
                    # 记录卖出交易
                    self.trades.append({
                        'type': 'sell',
                        'date': date,
                        'price': close_price,
                        'shares': self.position,
                        'exit_type': 'take_profit'
                    })
                    self.position = 0
                    self.buy_price = 0
                # 止损
                elif close_price <= stop_loss_price:
                    self.cash += self.position * close_price
                    print(f"{date}: 止损卖出 {self.position} 股，价格: {close_price:.2f}")
                    # 记录卖出交易
                    self.trades.append({
                        'type': 'sell',
                        'date': date,
                        'price': close_price,
                        'shares': self.position,
                        'exit_type': 'stop_loss'
                    })
                    self.position = 0
                    self.buy_price = 0
            
            # 执行卖出信号
            elif sell_signal == 1 and self.position > 0:
                # 卖出所有持仓
                self.cash += self.position * close_price
                print(f"{date}: 趋势反转卖出 {self.position} 股，价格: {close_price:.2f}")
                # 记录卖出交易
                self.trades.append({
                    'type': 'sell',
                    'date': date,
                    'price': close_price,
                    'shares': self.position,
                    'exit_type': 'trend_reversal'
                })
                self.position = 0
                self.buy_price = 0
            
            # 计算当前portfolio价值
            current_value = self.cash + (self.position * close_price)
            self.portfolio_value.append(current_value)
        
        # 回测结束时，如果还有持仓，卖出所有持仓
        if self.position > 0:
            final_price = self.data['close'].iloc[-1]
            self.cash += self.position * final_price
            print(f"{self.data['date'].iloc[-1]}: 结束回测，卖出 {self.position} 股，价格: {final_price:.2f}")
            # 记录卖出交易
            self.trades.append({
                'type': 'sell',
                'date': self.data['date'].iloc[-1],
                'price': final_price,
                'shares': self.position,
                'exit_type': 'end_of_backtest'
            })
            self.position = 0
            self.buy_price = 0
        
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
        sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
        
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
        winning_trades = 0
        total_trades = 0
        
        # 配对买入和卖出交易
        buy_trades = [trade for trade in self.trades if trade['type'] == 'buy']
        sell_trades = [trade for trade in self.trades if trade['type'] == 'sell']
        
        # 确保买入和卖出交易数量匹配
        min_trades = min(len(buy_trades), len(sell_trades))
        for i in range(min_trades):
            buy_trade = buy_trades[i]
            sell_trade = sell_trades[i]
            
            # 确保卖出价格大于买入价格
            if sell_trade['price'] > buy_trade['price']:
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
    
    def plot_results(self):
        """绘制回测结果"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 12))
        
        # 价格走势与趋势通道
        plt.subplot(3, 1, 1)
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        plt.plot(self.data['date'], self.data['MA20'], label='MA20', color='green', linestyle='--')
        plt.plot(self.data['date'], self.data['channel_upper'], label='通道上轨', color='red', linestyle='--')
        plt.plot(self.data['date'], self.data['channel_lower'], label='通道下轨', color='purple', linestyle='--')
        
        # 标记买入卖出信号
        buy_signals = self.data[self.data['buy_signal'] == 1]
        sell_signals = self.data[self.data['sell_signal'] == 1]
        plt.scatter(buy_signals['date'], buy_signals['close'], marker='^', color='green', label='买入信号', s=100)
        plt.scatter(sell_signals['date'], sell_signals['close'], marker='v', color='red', label='卖出信号', s=100)
        
        plt.title(f'{self.ticker} 价格走势与趋势通道')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # 趋势状态
        plt.subplot(3, 1, 2)
        plt.plot(self.data['date'], self.data['uptrend'], label='上升趋势', color='green')
        plt.plot(self.data['date'], self.data['downtrend'], label='下降趋势', color='red')
        plt.plot(self.data['date'], self.data['sideways'], label='横盘', color='blue')
        plt.title(f'{self.ticker} 趋势状态')
        plt.xlabel('日期')
        plt.ylabel('状态')
        plt.legend()
        plt.grid(True)
        
        # portfolio价值走势
        plt.subplot(3, 1, 3)
        plt.plot(self.data['date'], self.portfolio_value, label='Portfolio价值', color='purple')
        plt.axhline(y=self.initial_capital, color='gray', linestyle='--', label='初始资金')
        plt.title(f'{self.ticker} Portfolio价值走势')
        plt.xlabel('日期')
        plt.ylabel('价值')
        plt.legend()
        plt.grid(True)
        
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_trend_channel_results.png')
        plt.savefig(chart_path)
        print(f"趋势通道分析结果图表已保存为: {chart_path}")
    
    def save_signals(self):
        """保存交易信号数据"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 提取买入信号
        buy_signals = self.data[self.data['buy_signal'] == 1][['date', 'close', 'MA20', 'channel_upper', 'channel_lower', 'MA20_slope']].copy()
        buy_signals['signal_type'] = 'buy'
        
        # 提取卖出信号
        sell_signals = self.data[self.data['sell_signal'] == 1][['date', 'close', 'MA20', 'channel_upper', 'channel_lower', 'MA20_slope']].copy()
        sell_signals['signal_type'] = 'sell'
        
        # 合并信号
        all_signals = pd.concat([buy_signals, sell_signals], ignore_index=True)
        
        # 按日期排序
        all_signals = all_signals.sort_values('date')
        
        # 调整列顺序，把signal_type放到第二列
        all_signals = all_signals[['date', 'signal_type', 'close', 'MA20', 'channel_upper', 'channel_lower', 'MA20_slope']]
        
        # 保存为CSV文件
        signals_path = os.path.join(stock_dir, f'{self.ticker}_trend_channel_signals.csv')
        all_signals.to_csv(signals_path, index=False, encoding='utf-8-sig')
        print(f"趋势通道交易信号数据已保存为: {signals_path}")
        
        return signals_path
    
    def run_analysis(self):
        """运行完整的趋势通道分析"""
        self.load_data()
        self.calculate_trend_channels()
        self.generate_signals()
        final_value, total_return = self.backtest_strategy()
        metrics = self.calculate_metrics()
        self.plot_results()
        self.save_signals()
        print("\n=== 趋势通道分析完成 ===")
        return final_value, total_return, metrics

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="基于趋势通道分析的量化交易策略")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000000.SZ（深交所），默认使用config.py中的配置")
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
    
    # 运行趋势通道分析
    analyzer = TrendChannelAnalyzer(file_path)
    final_value, total_return, metrics = analyzer.run_analysis()
