# trend_following_backtest_simplified.py
import pandas as pd
import numpy as np
import os
import argparse
import matplotlib.pyplot as plt
from datetime import datetime

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

class TrendFollowingStrategy:
    def __init__(self, ticker, params=None):
        self.ticker = ticker
        self.data = None
        self.trades = []
        
        self.default_params = {
            'adx_threshold': 25,
            'confirmation_days': 1,
            'max_recent_days': 5,
            'volume_ratio_threshold': 1.1,
            'atr_stop_multiplier': 3.0,
            'exit_adx_threshold': 25,
            'trailing_ma_period': 20,
            'chandelier_atr_multiplier': 3.0,
            'profit_target_atr': 2.0
        }
        
        if params:
            self.default_params.update(params)
        
        self.p = self.default_params
    
    def load_data(self):
        indicators_file = os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_indicators.csv")
        
        if not os.path.exists(indicators_file):
            print(f"错误：未找到 {self.ticker} 的指标文件")
            return False
        
        self.data = pd.read_csv(indicators_file)
        self.data['date'] = pd.to_datetime(self.data['date'])
        self.data.sort_values('date', inplace=True)
        self.data.reset_index(drop=True, inplace=True)
        
        self._calculate_base_indicators()
        return True
    
    def _calculate_base_indicators(self):
        self.data['MA5'] = self.data['close'].rolling(window=5).mean()
        self.data['MA10'] = self.data['close'].rolling(window=10).mean()
        self.data['MA20'] = self.data['close'].rolling(window=20).mean()
        self.data['MA60'] = self.data['close'].rolling(window=60).mean()
        self.data['MA120'] = self.data['close'].rolling(window=120).mean()
        
        self.data['VOL20'] = self.data['volume'].rolling(window=20).mean()
        self.data['volume_ratio'] = self.data['volume'] / self.data['VOL20']
        
        self._calculate_swing_lows()
    
    def _calculate_swing_lows(self):
        self.data['swing_low'] = self.data['low'].rolling(window=20, center=False).min().shift(1)
        self.data['swing_low'] = self.data['swing_low'].ffill()
    
    def _generate_signals(self):
        self.data['bull_arrangement'] = (
            (self.data['MA5'] > self.data['MA20']) &
            (self.data['close'] > self.data['MA120']) &
            (self.data['volume_ratio'] > self.p['volume_ratio_threshold'])
        ).astype(int)
        
        self.data['trend_confirmed'] = (
            (self.data['bull_arrangement'].rolling(window=self.p['confirmation_days']).sum() >= self.p['confirmation_days']) &
            (self.data['ADX'] > self.p['adx_threshold']) &
            (self.data['MACD_hist'] > 0)
        ).astype(int)
        
        entry_signal = []
        for i in range(len(self.data)):
            if i < self.p['max_recent_days'] - 1:
                entry_signal.append(0)
            else:
                recent_window = self.data['trend_confirmed'].iloc[i-self.p['max_recent_days']+1:i]
                current = self.data['trend_confirmed'].iloc[i]
                if current == 1 and recent_window.sum() == 0:
                    entry_signal.append(1)
                else:
                    entry_signal.append(0)
        
        self.data['entry_signal'] = entry_signal
        
        self.data['trend_ended'] = (
            ((self.data['MA5'] < self.data['MA10']) | (self.data['MA10'] < self.data['MA20'])) &
            (self.data['ADX'] < self.p['exit_adx_threshold']) &
            (self.data['MACD_hist'] < 0)
        ).astype(int)
        
        self.data['trailing_ma'] = self.data['close'].rolling(window=self.p['trailing_ma_period']).mean()
    
    def run_backtest(self, initial_capital=1000000, position_ratio=0.8):
        if self.data is None:
            print("请先加载数据")
            return None
        
        self._generate_signals()
        
        cash = initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        atr_at_entry = 0
        swing_low_at_entry = 0
        highest_price = 0
        stop_price = 0
        trailing_activated = False
        just_bought = False
        trades = []
        portfolio_values = []
        
        for i in range(len(self.data)):
            date = self.data['date'].iloc[i]
            close = self.data['close'].iloc[i]
            low = self.data['low'].iloc[i]
            atr = self.data['ATR'].iloc[i]
            entry_signal = self.data['entry_signal'].iloc[i]
            trend_ended = self.data['trend_ended'].iloc[i]
            trailing_ma = self.data['trailing_ma'].iloc[i]
            
            current_profit = 0
            trailing_stop = close
            
            if position > 0:
                highest_price = max(highest_price, close)
                current_profit = (close - entry_price) / entry_price
                
                if not trailing_activated and current_profit > self.p['profit_target_atr'] * (atr_at_entry / entry_price):
                    trailing_activated = True
                
                if trailing_activated:
                    trailing_stop = trailing_ma
                    chandelier_stop = highest_price - self.p['chandelier_atr_multiplier'] * atr
                    trailing_stop = max(trailing_stop, chandelier_stop)
            
            if entry_signal == 1 and position == 0:
                max_shares = int((cash * position_ratio) / close)
                if max_shares > 0:
                    position = max_shares
                    cash -= position * close
                    entry_price = close
                    entry_date = date
                    atr_at_entry = atr
                    swing_low_at_entry = self.data['swing_low'].iloc[i]
                    highest_price = close
                    trailing_activated = False
                    just_bought = True
                    
                    protective_stop = atr_at_entry * self.p['atr_stop_multiplier']
                    stop_price = entry_price - protective_stop
                    print(f"{date.date()}: 买入 {position} 股 @ {close:.2f}, 止损价: {stop_price:.2f}")
            
            if position > 0 and not just_bought:
                hit_stop = False
                hit_trailing = False
                hit_trend_end = False
                exit_price = close
                
                if low <= stop_price:
                    exit_price = stop_price
                    hit_stop = True
                elif trailing_activated and close < trailing_stop:
                    hit_trailing = True
                elif trend_ended == 1:
                    hit_trend_end = True
                
                if hit_stop or hit_trailing or hit_trend_end:
                    cash += position * exit_price
                    profit = (exit_price - entry_price) / entry_price * 100
                    
                    exit_type = 'stop_loss' if hit_stop else 'trailing_stop' if hit_trailing else 'trend_end'
                    trades.append({
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': date,
                        'exit_price': exit_price,
                        'profit': profit,
                        'type': exit_type
                    })
                    
                    print(f"{date.date()}: {exit_type}卖出 @ {exit_price:.2f}, 收益: {profit:.2f}%")
                    position = 0
            
            current_value = cash + (position * close)
            portfolio_values.append(current_value)
            
            just_bought = False
        
        if position > 0:
            final_price = self.data['close'].iloc[-1]
            cash += position * final_price
            profit = (final_price - entry_price) / entry_price * 100
            trades.append({
                'entry_date': entry_date,
                'entry_price': entry_price,
                'exit_date': self.data['date'].iloc[-1],
                'exit_price': final_price,
                'profit': profit,
                'type': 'final_close'
            })
            print(f"{self.data['date'].iloc[-1].date()}: 结束回测卖出 @ {final_price:.2f}, 收益: {profit:.2f}%")
        
        self.trades = trades
        self.data['portfolio_value'] = portfolio_values
        
        if len(trades) > 0:
            profits = [t['profit'] for t in trades]
            win_trades = [t for t in trades if t['profit'] > 0]
            total_return = (cash - initial_capital) / initial_capital * 100
            win_rate = len(win_trades) / len(trades) * 100
            avg_profit = np.mean(profits)
            max_profit = max(profits)
            max_loss = min(profits)
            
            print(f"\n=== 回测结果 ===")
            print(f"初始资金: {initial_capital:,}")
            print(f"最终资金: {cash:,.2f}")
            print(f"总收益率: {total_return:.2f}%")
            print(f"交易次数: {len(trades)}")
            print(f"胜率: {win_rate:.2f}%")
            print(f"平均收益: {avg_profit:.2f}%")
            print(f"最大盈利: {max_profit:.2f}%")
            print(f"最大亏损: {max_loss:.2f}%")
            
            type_stats = {}
            for t in trades:
                t_type = t['type']
                if t_type not in type_stats:
                    type_stats[t_type] = {'count': 0, 'avg_profit': 0}
                type_stats[t_type]['count'] += 1
                type_stats[t_type]['avg_profit'] += t['profit']
            
            print("\n=== 离场类型统计 ===")
            for t_type, stats in type_stats.items():
                avg_p = stats['avg_profit'] / stats['count']
                print(f"{t_type}: {stats['count']}次, 平均收益: {avg_p:.2f}%")
        
        return trades
    
    def save_trades_to_csv(self, save_path=None):
        if len(self.trades) == 0:
            print("没有交易记录可保存")
            return None
        
        signals_list = []
        for trade in self.trades:
            entry_row = self.data[self.data['date'] == trade['entry_date']].iloc[0]
            exit_row = self.data[self.data['date'] == trade['exit_date']].iloc[0]
            
            signals_list.append({
                'date': trade['entry_date'].date(),
                'price': trade['entry_price'],
                'signal_type': 'buy',
                'trade_profit': trade['profit'],
                'exit_type': trade['type'],
                'ADX': entry_row['ADX'],
                'MACD_hist': entry_row['MACD_hist'],
                'RSI': entry_row['RSI'],
                'MA5': entry_row['MA5'],
                'MA10': entry_row['MA10'],
                'MA20': entry_row['MA20'],
                'MA60': entry_row['MA60'],
                'ATR': entry_row['ATR'],
                'BB_lower': entry_row['BB_lower'],
                'BB_upper': entry_row['BB_upper'],
                'volume_ratio': entry_row['volume_ratio'],
                'bull_arrangement': entry_row['bull_arrangement'],
                'trend_confirmed': entry_row['trend_confirmed']
            })
            
            signals_list.append({
                'date': trade['exit_date'].date(),
                'price': trade['exit_price'],
                'signal_type': 'sell',
                'trade_profit': trade['profit'],
                'exit_type': trade['type'],
                'ADX': exit_row['ADX'],
                'MACD_hist': exit_row['MACD_hist'],
                'RSI': exit_row['RSI'],
                'MA5': exit_row['MA5'],
                'MA10': exit_row['MA10'],
                'MA20': exit_row['MA20'],
                'MA60': exit_row['MA60'],
                'ATR': exit_row['ATR'],
                'BB_lower': exit_row['BB_lower'],
                'BB_upper': exit_row['BB_upper'],
                'volume_ratio': exit_row['volume_ratio'],
                'bull_arrangement': exit_row['bull_arrangement'],
                'trend_confirmed': exit_row['trend_confirmed'],
                'trend_ended': exit_row['trend_ended']
            })
        
        signals_df = pd.DataFrame(signals_list)
        
        if save_path:
            signals_df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"交易信号已保存到: {save_path}")
        else:
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            os.makedirs(stock_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d')
            default_path = os.path.join(stock_dir, f"{self.ticker}_backtest_{timestamp}.csv")
            signals_df.to_csv(default_path, index=False, encoding='utf-8-sig')
            print(f"交易信号已保存到: {default_path}")
            save_path = default_path
        
        return save_path
    
    def plot_results(self, save_path=None):
        if self.data is None or len(self.trades) == 0:
            print("没有数据可绘制")
            return None
        
        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        
        fig = plt.figure(figsize=(18, 18))
        
        ax1 = fig.add_subplot(3, 1, 1)
        ax1.plot(self.data['date'], self.data['close'], label='收盘价', color='blue', linewidth=1.5)
        ax1.plot(self.data['date'], self.data['MA20'], label='MA20', color='green', linestyle='--', linewidth=1)
        ax1.plot(self.data['date'], self.data['MA60'], label='MA60', color='red', linestyle='--', linewidth=1)
        
        for trade in self.trades:
            entry_idx = self.data[self.data['date'] == trade['entry_date']].index[0]
            exit_idx = self.data[self.data['date'] == trade['exit_date']].index[0]
            
            ax1.scatter(trade['entry_date'], trade['entry_price'], marker='^', color='green', s=150, label='买入' if trade == self.trades[0] else "")
            ax1.scatter(trade['exit_date'], trade['exit_price'], marker='v', color='red', s=150, label='卖出' if trade == self.trades[0] else "")
            
            ax1.plot([trade['entry_date'], trade['exit_date']], 
                     [trade['entry_price'], trade['exit_price']], 
                     color='orange', linewidth=2, linestyle='-')
        
        ax1.set_title(f'{self.ticker} 价格走势与交易信号', fontsize=14)
        ax1.set_xlabel('日期', fontsize=12)
        ax1.set_ylabel('价格', fontsize=12)
        ax1.legend()
        ax1.grid(True)
        
        ax2 = fig.add_subplot(3, 1, 2)
        ax2.plot(self.data['date'], self.data['portfolio_value'], label='Portfolio价值', color='purple', linewidth=2)
        ax2.axhline(y=self.default_params.get('initial_capital', 1000000), color='gray', linestyle='--', label='初始资金')
        
        ax2.set_title(f'{self.ticker} Portfolio价值走势', fontsize=14)
        ax2.set_xlabel('日期', fontsize=12)
        ax2.set_ylabel('价值', fontsize=12)
        ax2.legend()
        ax2.grid(True)
        
        ax3 = fig.add_subplot(3, 1, 3)
        if len(self.data) >= 60:
            recent_data = self.data.iloc[-60:]
        else:
            recent_data = self.data
        
        ax3.plot(recent_data['date'], recent_data['close'], label='收盘价', color='blue', linewidth=1.5)
        ax3.plot(recent_data['date'], recent_data['MA20'], label='MA20', color='green', linestyle='--', linewidth=1)
        ax3.plot(recent_data['date'], recent_data['MA60'], label='MA60', color='red', linestyle='--', linewidth=1)
        
        for trade in self.trades:
            if trade['entry_date'] in recent_data['date'].values:
                ax3.scatter(trade['entry_date'], trade['entry_price'], marker='^', color='green', s=200, label='买入' if trade == self.trades[0] else "")
            if trade['exit_date'] in recent_data['date'].values:
                ax3.scatter(trade['exit_date'], trade['exit_price'], marker='v', color='red', s=200, label='卖出' if trade == self.trades[0] else "")
        
        ax3.set_title(f'{self.ticker} 最近三个月价格走势与交易信号', fontsize=14)
        ax3.set_xlabel('日期', fontsize=12)
        ax3.set_ylabel('价格', fontsize=12)
        ax3.legend()
        ax3.grid(True)
        ax3.tick_params(axis='x', rotation=45)
        
        plt.tight_layout()
        
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存到: {save_path}")
        else:
            plt.show()
        
        return fig

def main():
    parser = argparse.ArgumentParser(description="趋势跟踪策略回测（简化版：MA5 > MA20）")
    parser.add_argument('--ticker', required=True, help='股票代码，如 300502.SZ')
    parser.add_argument('--capital', type=int, default=1000000, help='初始资金，默认100万')
    parser.add_argument('--position', type=float, default=0.8, help='仓位比例，默认80%')
    parser.add_argument('--adx', type=float, default=25, help='ADX入场阈值')
    parser.add_argument('--exit_adx', type=float, default=25, help='ADX离场阈值')
    parser.add_argument('--atr_stop', type=float, default=2.0, help='ATR止损倍数')
    parser.add_argument('--chandelier', type=float, default=3.0, help='吊灯止损倍数')
    args = parser.parse_args()
    
    params = {
        'adx_threshold': args.adx,
        'exit_adx_threshold': args.exit_adx,
        'atr_stop_multiplier': args.atr_stop,
        'chandelier_atr_multiplier': args.chandelier
    }
    
    strategy = TrendFollowingStrategy(args.ticker, params)
    if strategy.load_data():
        strategy.run_backtest(initial_capital=args.capital, position_ratio=args.position)
        
        strategy.save_trades_to_csv()
    
        stock_dir = os.path.join(DATA_DIR, args.ticker)
        os.makedirs(stock_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d')
        plot_path = os.path.join(stock_dir, f"{args.ticker}_backtest_{timestamp}.png")
        strategy.plot_results(save_path=plot_path)

if __name__ == "__main__":
    main()