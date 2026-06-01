# trend_following_backtest.py
# 趋势跟踪策略回测引擎
# mode='full':  严格多头排列 (MA5>MA10>MA20>MA60), MA10斜率+MA5-MA60偏离过滤
# mode='simple': 宽松多头排列 (MA5>MA20), 买入日免检卖出
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

# ============================================================
# 预设参数
# ============================================================
PRESET_PARAMS = {
    'full': {
        'adx_threshold': 25,
        'confirmation_days': 3,
        'slope_threshold': 0.005,
        'max_recent_days': 5,
        'volume_ratio_threshold': 1.2,
        'atr_stop_multiplier': 3.0,
        'exit_adx_threshold': 25,
        'trailing_ma_period': 20,
        'chandelier_atr_multiplier': 3.0,
        'profit_target_atr': 2.0,
    },
    'simple': {
        'adx_threshold': 25,
        'confirmation_days': 1,
        'max_recent_days': 5,
        'volume_ratio_threshold': 1.1,
        'atr_stop_multiplier': 3.0,
        'exit_adx_threshold': 25,
        'trailing_ma_period': 20,
        'chandelier_atr_multiplier': 3.0,
        'profit_target_atr': 2.0,
    },
}


class TrendFollowingStrategy:
    def __init__(self, ticker, mode='full', params=None):
        self.ticker = ticker
        self.mode = mode
        self.data = None
        self.trades = []

        # 按 mode 加载预设参数，再用 params 覆盖
        self.default_params = dict(PRESET_PARAMS.get(mode, PRESET_PARAMS['full']))
        if params:
            self.default_params.update(params)
        self.p = self.default_params

    # ---- 数据加载 ----
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
        df = self.data
        df['MA5'] = df['close'].rolling(5).mean()
        df['MA10'] = df['close'].rolling(10).mean()
        df['MA20'] = df['close'].rolling(20).mean()
        df['MA60'] = df['close'].rolling(60).mean()
        df['MA120'] = df['close'].rolling(120).mean()
        df['VOL20'] = df['volume'].rolling(20).mean()
        df['volume_ratio'] = df['volume'] / df['VOL20']

        if self.mode == 'full':
            df['MA10_slope'] = (df['MA10'] / df['MA10'].shift(5) - 1)
            df['MA5_MA60_diff'] = (df['MA5'] - df['MA60']) / df['MA60']

        self._calculate_swing_lows()

    def _calculate_swing_lows(self):
        self.data['swing_low'] = self.data['low'].rolling(20, min_periods=1).min().shift(1)
        self.data['swing_low'] = self.data['swing_low'].ffill()

    # ---- 信号生成 ----
    def _generate_signals(self):
        df = self.data
        p = self.p

        if self.mode == 'full':
            df['bull_arrangement'] = (
                (df['MA5'] > df['MA10']) &
                (df['MA10'] > df['MA20']) &
                (df['MA20'] > df['MA60']) &
                (df['close'] > df['MA120']) &
                (df['volume_ratio'] > 1.2)
            ).astype(int)

            df['strong_bull'] = (
                (df['bull_arrangement'] == 1) &
                (df['MA10_slope'] > p['slope_threshold']) &
                (df['MA5_MA60_diff'] > 0.01)
            ).astype(int)

            df['trend_confirmed'] = (
                (df['strong_bull'].rolling(p['confirmation_days']).sum() >= p['confirmation_days']) &
                (df['ADX'] > p['adx_threshold']) &
                (df['MACD_hist'] > 0)
            ).astype(int)
        else:
            df['bull_arrangement'] = (
                (df['MA5'] > df['MA20']) &
                (df['close'] > df['MA120']) &
                (df['volume_ratio'] > p['volume_ratio_threshold'])
            ).astype(int)

            df['trend_confirmed'] = (
                (df['bull_arrangement'].rolling(p['confirmation_days']).sum() >= p['confirmation_days']) &
                (df['ADX'] > p['adx_threshold']) &
                (df['MACD_hist'] > 0)
            ).astype(int)

        # 入场信号：最近 max_recent_days 天首次出现 trend_confirmed
        entry_signal = []
        for i in range(len(df)):
            if i < p['max_recent_days'] - 1:
                entry_signal.append(0)
            else:
                recent = df['trend_confirmed'].iloc[i - p['max_recent_days'] + 1:i]
                current = df['trend_confirmed'].iloc[i]
                entry_signal.append(1 if (current == 1 and recent.sum() == 0) else 0)
        df['entry_signal'] = entry_signal

        df['trend_ended'] = (
            ((df['MA5'] < df['MA10']) | (df['MA10'] < df['MA20'])) &
            (df['ADX'] < p['exit_adx_threshold']) &
            (df['MACD_hist'] < 0)
        ).astype(int)

        df['trailing_ma'] = df['close'].rolling(p['trailing_ma_period']).mean()

    # ---- 回测主循环 ----
    def run_backtest(self, initial_capital=1000000, position_ratio=0.8):
        if self.data is None:
            print("请先加载数据")
            return None

        self._generate_signals()
        df = self.data

        cash = initial_capital
        position = 0
        entry_price = 0
        entry_date = None
        atr_at_entry = 0
        highest_price = 0
        stop_price = 0
        trailing_activated = False
        just_bought = False
        trades = []
        portfolio_values = []

        for i in range(len(df)):
            date = df['date'].iloc[i]
            close = df['close'].iloc[i]
            low = df['low'].iloc[i]
            atr = df['ATR'].iloc[i]

            if position > 0:
                highest_price = max(highest_price, close)
                current_profit = (close - entry_price) / entry_price
                if not trailing_activated and current_profit > self.p['profit_target_atr'] * (atr_at_entry / entry_price):
                    trailing_activated = True
                # full 模式：一旦激活永久保持；simple 模式同样

            # 入场
            if df['entry_signal'].iloc[i] == 1 and position == 0:
                max_shares = int((cash * position_ratio) / close)
                if max_shares > 0:
                    position = max_shares
                    cash -= position * close
                    entry_price = close
                    entry_date = date
                    atr_at_entry = atr
                    highest_price = close
                    trailing_activated = False
                    just_bought = True
                    stop_price = entry_price - atr_at_entry * self.p['atr_stop_multiplier']
                    print(f"{date.date()}: 买入 {position} 股 @ {close:.2f}, 止损价: {stop_price:.2f}")

            # 离场判断
            if position > 0 and not just_bought:
                hit_stop = low <= stop_price
                trailing_stop = df['trailing_ma'].iloc[i]
                if trailing_activated:
                    chandelier_stop = highest_price - self.p['chandelier_atr_multiplier'] * atr
                    trailing_stop = max(trailing_stop, chandelier_stop)
                hit_trailing = trailing_activated and close < trailing_stop
                hit_trend_end = df['trend_ended'].iloc[i] == 1
                exit_price = stop_price if hit_stop else close

                if hit_stop or hit_trailing or hit_trend_end:
                    cash += position * exit_price
                    profit = (exit_price - entry_price) / entry_price * 100
                    exit_type = 'stop_loss' if hit_stop else 'trailing_stop' if hit_trailing else 'trend_end'
                    trades.append({
                        'entry_date': entry_date, 'entry_price': entry_price,
                        'exit_date': date, 'exit_price': exit_price,
                        'profit': profit, 'type': exit_type,
                    })
                    print(f"{date.date()}: {exit_type}卖出 @ {exit_price:.2f}, 收益: {profit:.2f}%")
                    position = 0

            portfolio_values.append(cash + position * close)
            just_bought = False

        # 强制平仓
        if position > 0:
            final_price = df['close'].iloc[-1]
            cash += position * final_price
            profit = (final_price - entry_price) / entry_price * 100
            trades.append({
                'entry_date': entry_date, 'entry_price': entry_price,
                'exit_date': df['date'].iloc[-1], 'exit_price': final_price,
                'profit': profit, 'type': 'final_close',
            })
            print(f"{df['date'].iloc[-1].date()}: 结束回测卖出 @ {final_price:.2f}, 收益: {profit:.2f}%")

        self.trades = trades
        df['portfolio_value'] = portfolio_values
        self._print_summary(cash, initial_capital)
        return trades

    def _print_summary(self, final_cash, initial_capital):
        if not self.trades:
            return
        profits = [t['profit'] for t in self.trades]
        win_trades = [t for t in self.trades if t['profit'] > 0]
        total_return = (final_cash - initial_capital) / initial_capital * 100

        print(f"\n=== 回测结果 ({self.mode} 模式) ===")
        print(f"初始资金: {initial_capital:,}")
        print(f"最终资金: {final_cash:,.2f}")
        print(f"总收益率: {total_return:.2f}%")
        print(f"交易次数: {len(self.trades)}")
        print(f"胜率: {len(win_trades)/len(self.trades)*100:.2f}%")
        print(f"平均收益: {np.mean(profits):.2f}%")
        print(f"最大盈利: {max(profits):.2f}%")
        print(f"最大亏损: {min(profits):.2f}%")

        type_stats = {}
        for t in self.trades:
            tp = t['type']
            if tp not in type_stats:
                type_stats[tp] = {'count': 0, 'total': 0}
            type_stats[tp]['count'] += 1
            type_stats[tp]['total'] += t['profit']
        print("\n=== 离场类型统计 ===")
        for tp, s in type_stats.items():
            print(f"  {tp}: {s['count']}次, 平均收益: {s['total']/s['count']:.2f}%")

    # ---- 导出 ----
    def save_trades_to_csv(self, save_path=None):
        if not self.trades:
            print("没有交易记录可保存")
            return None

        df = self.data
        signals_list = []
        base_cols = ['ADX', 'MACD_hist', 'RSI', 'MA5', 'MA10', 'MA20', 'MA60',
                     'ATR', 'BB_lower', 'BB_upper', 'volume_ratio',
                     'bull_arrangement', 'trend_confirmed']
        full_extra = ['MA10_slope', 'MA5_MA60_diff', 'strong_bull']

        for trade in self.trades:
            entry_row = df[df['date'] == trade['entry_date']].iloc[0]
            exit_row = df[df['date'] == trade['exit_date']].iloc[0]

            buy = {'date': trade['entry_date'].date(), 'price': trade['entry_price'],
                   'signal_type': 'buy', 'trade_profit': trade['profit'], 'exit_type': trade['type']}
            sell = {'date': trade['exit_date'].date(), 'price': trade['exit_price'],
                    'signal_type': 'sell', 'trade_profit': trade['profit'], 'exit_type': trade['type']}

            for c in base_cols:
                buy[c] = entry_row[c]
                sell[c] = exit_row[c]
            if self.mode == 'full':
                for c in full_extra:
                    buy[c] = entry_row.get(c, np.nan)
                    sell[c] = exit_row.get(c, np.nan)
            sell['trend_ended'] = exit_row['trend_ended']

            signals_list.append(buy)
            signals_list.append(sell)

        signals_df = pd.DataFrame(signals_list)

        if save_path:
            signals_df.to_csv(save_path, index=False, encoding='utf-8-sig')
        else:
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            os.makedirs(stock_dir, exist_ok=True)
            save_path = os.path.join(stock_dir, f"{self.ticker}_backtest_{datetime.now().strftime('%Y%m%d')}.csv")
            signals_df.to_csv(save_path, index=False, encoding='utf-8-sig')
        print(f"交易信号已保存到: {save_path}")
        return save_path

    # ---- 图表 ----
    def plot_results(self, save_path=None):
        if self.data is None or not self.trades:
            print("没有数据可绘制")
            return None

        plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']
        plt.rcParams['axes.unicode_minus'] = False
        df = self.data
        fig = plt.figure(figsize=(18, 18))

        # 子图1: 全量价格+信号
        ax1 = fig.add_subplot(3, 1, 1)
        ax1.plot(df['date'], df['close'], label='收盘价', color='blue', linewidth=1.5)
        ax1.plot(df['date'], df['MA20'], label='MA20', color='green', linestyle='--', linewidth=1)
        ax1.plot(df['date'], df['MA60'], label='MA60', color='red', linestyle='--', linewidth=1)
        for j, t in enumerate(self.trades):
            ax1.scatter(t['entry_date'], t['entry_price'], marker='^', color='green', s=150, label='买入' if j == 0 else "")
            ax1.scatter(t['exit_date'], t['exit_price'], marker='v', color='red', s=150, label='卖出' if j == 0 else "")
            ax1.plot([t['entry_date'], t['exit_date']], [t['entry_price'], t['exit_price']], color='orange', linewidth=2)
        ax1.set_title(f'{self.ticker} 价格走势与交易信号 ({self.mode})', fontsize=14)
        ax1.legend(); ax1.grid(True)

        # 子图2: 资金曲线
        ax2 = fig.add_subplot(3, 1, 2)
        ax2.plot(df['date'], df['portfolio_value'], label='Portfolio', color='purple', linewidth=2)
        ax2.axhline(y=1000000, color='gray', linestyle='--', label='初始资金')
        ax2.set_title('Portfolio 价值走势', fontsize=14)
        ax2.legend(); ax2.grid(True)

        # 子图3: 近3个月
        ax3 = fig.add_subplot(3, 1, 3)
        recent = df.iloc[-60:] if len(df) >= 60 else df
        ax3.plot(recent['date'], recent['close'], label='收盘价', color='blue', linewidth=1.5)
        ax3.plot(recent['date'], recent['MA20'], label='MA20', color='green', linestyle='--', linewidth=1)
        ax3.plot(recent['date'], recent['MA60'], label='MA60', color='red', linestyle='--', linewidth=1)
        for j, t in enumerate(self.trades):
            if t['entry_date'] in recent['date'].values:
                ax3.scatter(t['entry_date'], t['entry_price'], marker='^', color='green', s=200, label='买入' if j == 0 else "")
            if t['exit_date'] in recent['date'].values:
                ax3.scatter(t['exit_date'], t['exit_price'], marker='v', color='red', s=200, label='卖出' if j == 0 else "")
        ax3.set_title('近三个月走势', fontsize=14)
        ax3.legend(); ax3.grid(True); ax3.tick_params(axis='x', rotation=45)

        plt.tight_layout()
        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            print(f"图表已保存到: {save_path}")
        else:
            plt.show()
        return fig


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="趋势跟踪策略回测")
    parser.add_argument('--ticker', required=True, help='股票代码，如 300502.SZ')
    parser.add_argument('--mode', choices=['full', 'simple'], default='full', help='策略模式')
    parser.add_argument('--capital', type=int, default=1000000, help='初始资金')
    parser.add_argument('--position', type=float, default=0.8, help='仓位比例')
    parser.add_argument('--adx', type=float, default=25, help='ADX入场阈值')
    parser.add_argument('--exit_adx', type=float, default=25, help='ADX离场阈值')
    parser.add_argument('--atr_stop', type=float, default=None, help='ATR止损倍数')
    parser.add_argument('--chandelier', type=float, default=None, help='吊灯止损倍数')
    args = parser.parse_args()

    params = {
        'adx_threshold': args.adx,
        'exit_adx_threshold': args.exit_adx,
    }
    if args.atr_stop is not None:
        params['atr_stop_multiplier'] = args.atr_stop
    if args.chandelier is not None:
        params['chandelier_atr_multiplier'] = args.chandelier

    strategy = TrendFollowingStrategy(args.ticker, mode=args.mode, params=params)
    if strategy.load_data():
        strategy.run_backtest(initial_capital=args.capital, position_ratio=args.position)
        strategy.save_trades_to_csv()
        stock_dir = os.path.join(DATA_DIR, args.ticker)
        os.makedirs(stock_dir, exist_ok=True)
        plot_path = os.path.join(stock_dir, f"{args.ticker}_backtest_{datetime.now().strftime('%Y%m%d')}.png")
        strategy.plot_results(save_path=plot_path)


if __name__ == "__main__":
    main()
