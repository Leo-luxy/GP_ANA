
# daily_trend_strategy.py
# 功能：基于日线数据的量化策略，利用位置、量能、形态、背离四个维度进行分析
# 优化版本：加入趋势过滤器、动态移动止损、顶背离二次确认

import pandas as pd
import numpy as np
import os
import sys
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# 尝试设置matplotlib字体以支持中文
plt.rcParams['axes.unicode_minus'] = False  # 解决负号显示问题

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 假设config中有DATA_DIR
try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"  # 默认路径

class DailyTrendStrategy:
    def __init__(self, ticker):
        """初始化策略"""
        self.ticker = ticker
        self.code = ticker.split('.')[0]
        self.data = None
        self.indicators = None
        self.signals = None
        self.trades = []  # 保存交易记录

    def load_data(self):
        """加载日线数据"""
        data_file = os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_qfq.csv")
        if not os.path.exists(data_file):
            print(f"数据文件不存在: {data_file}")
            return False

        try:
            self.data = pd.read_csv(data_file)
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
            elif 'Date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['Date'])
            self.data.sort_values('date', inplace=True)
            self.data.reset_index(drop=True, inplace=True)
            return True
        except Exception as e:
            print(f"加载数据时出错: {str(e)}")
            return False

    def calculate_indicators(self):
        """计算技术指标"""
        if self.data is None:
            print("数据未加载")
            return False

        self.indicators = self.data.copy()

        # 先尝试加载indicators.csv文件，获取已计算好的MACD等指标
        indicators_file = os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_indicators.csv")
        if os.path.exists(indicators_file):
            try:
                indicators_df = pd.read_csv(indicators_file)
                # 合并MACD相关列
                for col in ['DIF', 'DEA', 'MACD_hist']:
                    if col in indicators_df.columns:
                        self.indicators[col] = indicators_df[col]
                print(f"已加载 {indicators_file} 中的技术指标")
            except Exception as e:
                print(f"加载指标文件时出错: {str(e)}，将重新计算")

        # 均线
        self.indicators['MA20'] = self.indicators['close'].rolling(window=20).mean()
        self.indicators['MA60'] = self.indicators['close'].rolling(window=60).mean()
        self.indicators['MA250'] = self.indicators['close'].rolling(window=250).mean()
        self.indicators['MA10'] = self.indicators['close'].rolling(window=10).mean()

        # 均线方向
        self.indicators['MA60_direction'] = np.where(self.indicators['MA60'] > self.indicators['MA60'].shift(1), 1, -1)
        self.indicators['MA250_direction'] = np.where(self.indicators['MA250'] > self.indicators['MA250'].shift(1), 1, -1)

        # 相对位置
        self.indicators['price_ma60_ratio'] = (self.indicators['close'] - self.indicators['MA60']) / self.indicators['MA60'] * 100
        self.indicators['price_ma250_ratio'] = (self.indicators['close'] - self.indicators['MA250']) / self.indicators['MA250'] * 100
        self.indicators['ma60_ma250_ratio'] = (self.indicators['MA60'] - self.indicators['MA250']) / self.indicators['MA250'] * 100

        # 成交量指标
        self.indicators['volume_5ma'] = self.indicators['volume'].rolling(window=5).mean()
        self.indicators['volume_ratio'] = self.indicators['volume'] / self.indicators['volume_5ma']

        # 换手率处理
        if 'turnover' in self.indicators.columns:
            if self.indicators['turnover'].max() > 100:
                self.indicators['turnover_rate'] = self.indicators['turnover']
            else:
                self.indicators['turnover_rate'] = self.indicators['turnover'] * 100
        else:
            if 'outstanding_share' in self.indicators.columns:
                valid = self.indicators['outstanding_share'] > 0
                self.indicators['turnover_rate'] = 0.0
                self.indicators.loc[valid, 'turnover_rate'] = \
                    self.indicators.loc[valid, 'volume'] / self.indicators.loc[valid, 'outstanding_share'] * 100
            else:
                float_shares = 100000000
                self.indicators['turnover_rate'] = self.indicators['volume'] / float_shares * 100

        # MACD - 如果indicators.csv中没有加载到，才重新计算
        if 'DIF' not in self.indicators.columns or 'DEA' not in self.indicators.columns or 'MACD_hist' not in self.indicators.columns:
            print("重新计算MACD指标...")
            exp1 = self.indicators['close'].ewm(span=12, adjust=False).mean()
            exp2 = self.indicators['close'].ewm(span=26, adjust=False).mean()
            self.indicators['DIF'] = exp1 - exp2
            self.indicators['DEA'] = self.indicators['DIF'].ewm(span=9, adjust=False).mean()
            self.indicators['MACD_hist'] = self.indicators['DIF'] - self.indicators['DEA']
        
        # 保持向后兼容性，设置dif、dea、macd_hist（与标准命名一致）
        self.indicators['dif'] = self.indicators['DIF']
        self.indicators['dea'] = self.indicators['DEA']
        self.indicators['macd'] = self.indicators['MACD_hist']  # 柱状图，不乘以2！

        # MACD柱高度（用于背离）
        self.indicators['macd_hist_height'] = abs(self.indicators['MACD_hist'])

        # 背离（优化版：记录连续两次顶背离）
        self.indicators['price_high'] = self.indicators['close'].rolling(window=20).max()
        self.indicators['macd_high'] = self.indicators['macd_hist_height'].rolling(window=20).max()
        # 第一次顶背离标记
        self.indicators['top_divergence'] = np.where(
            (self.indicators['close'] == self.indicators['price_high']) &
            (self.indicators['macd_hist_height'] < self.indicators['macd_high']),
            1, 0
        )
        # 连续两次顶背离（用于卖出确认）
        self.indicators['top_divergence_consecutive'] = (self.indicators['top_divergence'].rolling(window=2).sum() >= 2).fillna(0).astype(int)

        self.indicators['price_low'] = self.indicators['close'].rolling(window=20).min()
        self.indicators['macd_low'] = self.indicators['macd_hist_height'].rolling(window=20).min()
        self.indicators['bottom_divergence'] = np.where(
            (self.indicators['close'] == self.indicators['price_low']) &
            (self.indicators['macd_hist_height'] > self.indicators['macd_low']),
            1, 0
        )

        # K线形态
        self.indicators['is_red'] = np.where(self.indicators['close'] > self.indicators['open'], 1, 0)
        self.indicators['is_green'] = np.where(self.indicators['close'] < self.indicators['open'], 1, 0)
        self.indicators['is_doji'] = np.where(
            abs(self.indicators['close'] - self.indicators['open']) / self.indicators['open'] < 0.005,
            1, 0
        )
        # 防止分母为0
        body = np.maximum(self.indicators['open'], self.indicators['close']) - np.minimum(self.indicators['open'], self.indicators['close'])
        upper_shadow = self.indicators['high'] - np.maximum(self.indicators['open'], self.indicators['close'])
        self.indicators['has_long_upper_shadow'] = np.where(
            (body > 0) & (upper_shadow / body > 1.5), 1, 0
        )
        # 将 numpy 数组转为 Series 并填充 NaN
        self.indicators['has_long_upper_shadow'] = pd.Series(
            self.indicators['has_long_upper_shadow'], index=self.indicators.index
        ).fillna(0)

        # 涨幅
        self.indicators['pct_change'] = self.indicators['close'].pct_change() * 100

        return True

    def generate_signals(self):
        """生成交易信号（买入信号 + 卖出信号（趋势过滤后））"""
        if self.indicators is None:
            return False

        self.signals = self.indicators.copy()
        self.signals['buy_signal'] = 0
        self.signals['sell_signal'] = 0

        # 买入条件
        condition1 = (self.signals['MA60_direction'] == 1) & (self.signals['MA250_direction'] == 1)
        condition2 = (self.signals['volume_ratio'] > 2) & (self.signals['is_red'] == 1)
        condition3 = (self.signals['volume_ratio'] < 0.6) & \
                     (abs(self.signals['close'] - self.signals['MA20']) / self.signals['MA20'] < 0.02)
        condition4 = (self.signals['pct_change'] > 5) & (self.signals['volume_ratio'] > 1.5)
        condition5 = (self.signals['turnover_rate'] > 5) & (self.signals['is_red'] == 1)
        buy_candidates = condition1 & (condition2 | condition3 | condition4 | condition5)
        # 强势趋势定义：MA60向上，股价>MA60，偏离度<30%（未严重超买）
        strong_up_trend = (self.signals['MA60_direction'] == 1) & \
                          (self.signals['close'] > self.signals['MA60']) & \
                          (self.signals['price_ma60_ratio'] < 30)

        # 卖出条件（传统）
        condition_sell1 = (self.signals['price_ma60_ratio'] > 30)  # 严重偏离
        condition_sell2 = (self.signals['volume_ratio'] > 3) & \
                          ((self.signals['is_doji'] == 1) | (self.signals['has_long_upper_shadow'] == 1))
        condition_sell3 = (self.signals['top_divergence_consecutive'] == 1)  # 连续两次顶背离
        condition_sell4 = (self.signals['turnover_rate'] > 15) & (self.signals['is_green'] == 1)

        # 卖出候选（原始条件）
        sell_candidates_raw = condition_sell1 | condition_sell2 | condition_sell3 | condition_sell4
        sell_candidates = sell_candidates_raw & (~strong_up_trend)

        # 状态机生成信号
        position = 0
        for i in range(len(self.signals)):
            if buy_candidates.iloc[i] and position == 0:
                self.signals.loc[self.signals.index[i], 'buy_signal'] = 1
                position = 1
            elif sell_candidates.iloc[i] and position == 1:
                self.signals.loc[self.signals.index[i], 'sell_signal'] = 1
                position = 0

        return True

    def backtest(self):
        """回测策略（使用动态10日线移动止损 + 趋势止盈）"""
        if self.signals is None:
            print("信号未生成")
            return False

        total_capital = 100000
        capital = total_capital * 0.8   # 可用资金
        reserved = total_capital * 0.2  # 预留
        shares = 0
        buy_price = 0.0
        buy_count = 0
        self.trades = []

        # 辅助计算仓位
        def current_position(shares, current_price, cap):
            invested = (total_capital * 0.8) - cap
            return (invested / (total_capital * 0.8)) * 100 if (total_capital * 0.8) > 0 else 0

        for i in range(len(self.signals)):
            row = self.signals.iloc[i]
            date = row['date']
            close = row['close']
            ma10 = row['MA10'] if not pd.isna(row['MA10']) else close  # 避免NaN
            buy_signal = row['buy_signal']
            sell_signal = row['sell_signal']   # 信号卖出（趋势走弱时触发）

            # 分批买入逻辑（同原版）
            pos = current_position(shares, close, capital)
            if buy_signal == 1 and pos < 80:
                if buy_count == 0:
                    buy_amount = total_capital * 0.3
                elif buy_count == 1:
                    buy_amount = total_capital * 0.3
                elif buy_count == 2:
                    buy_amount = total_capital * 0.2
                else:
                    buy_count = 0
                    buy_amount = total_capital * 0.3

                if buy_amount > 0 and capital >= buy_amount:
                    buy_shares = int(buy_amount // close)
                    if buy_shares > 0:
                        cost = buy_shares * close
                        capital -= cost
                        shares += buy_shares
                        buy_count += 1
                        if buy_price == 0:
                            buy_price = close
                        else:
                            total_cost = (buy_price * (shares - buy_shares)) + (close * buy_shares)
                            buy_price = total_cost / shares

                        self.trades.append({
                            'date': date,
                            'type': 'buy',
                            'price': close,
                            'shares': buy_shares,
                            'capital': capital + reserved,
                            'position': current_position(shares, close, capital)
                        })
                        print(f"{date}: 买入 {buy_shares}股，价格{close:.2f}，仓位{current_position(shares, close, capital):.2f}%")

            # 持仓处理
            if shares > 0:
                profit = (close - buy_price) / buy_price * 100

                # 1. 动态止损：跌破10日线清仓
                if close < ma10:
                    proceeds = shares * close
                    capital += proceeds
                    self.trades.append({
                        'date': date,
                        'type': 'sell',
                        'price': close,
                        'shares': shares,
                        'capital': capital + reserved,
                        'reason': '移动止损(破10日线)',
                        'position': 0
                    })
                    print(f"{date}: 移动止损，卖出 {shares}股，价格{close:.2f}，收益{profit:.2f}%")
                    shares = 0
                    buy_price = 0
                    buy_count = 0
                    continue

                # 2. 趋势止盈：利润超过30%后，每再涨10%减仓10%
                if profit > 30:
                    # 计算当前利润相对于30%的超额部分，每10%减仓10%
                    excess = profit - 30
                    # 最多减仓5次（即50%），避免清仓过快
                    reduction = min(int(excess // 10), 5)
                    target_share_ratio = max(0.5, 1 - reduction * 0.1)  # 保留至少50%
                    target_shares = int(shares * target_share_ratio)
                    if target_shares < shares:
                        sell_shares = shares - target_shares
                        if sell_shares > 0:
                            proceeds = sell_shares * close
                            capital += proceeds
                            shares = target_shares
                            self.trades.append({
                                'date': date,
                                'type': 'sell',
                                'price': close,
                                'shares': sell_shares,
                                'capital': capital + reserved,
                                'reason': f'趋势止盈(利润{profit:.1f}%)',
                                'position': current_position(shares, close, capital)
                            })
                            print(f"{date}: 趋势止盈，卖出 {sell_shares}股，价格{close:.2f}，剩余仓位{current_position(shares, close, capital):.2f}%")

                # 3. 信号卖出（仅在非强势趋势时已经生成）
                if sell_signal == 1 and shares > 0:
                    # 一次性清仓（信号表示趋势可能转弱）
                    proceeds = shares * close
                    capital += proceeds
                    self.trades.append({
                        'date': date,
                        'type': 'sell',
                        'price': close,
                        'shares': shares,
                        'capital': capital + reserved,
                        'reason': '信号卖出(趋势转弱)',
                        'position': 0
                    })
                    print(f"{date}: 信号卖出，清仓 {shares}股，价格{close:.2f}，收益{profit:.2f}%")
                    shares = 0
                    buy_price = 0
                    buy_count = 0

        # 最终清算
        if shares > 0:
            final_close = self.signals.iloc[-1]['close']
            capital += shares * final_close
            shares = 0

        total_return = (capital + reserved - total_capital) / total_capital * 100
        print(f"\n回测结果:")
        print(f"初始资金: {total_capital:.2f}")
        print(f"最终资金: {capital + reserved:.2f}")
        print(f"总收益率: {total_return:.2f}%")
        print(f"交易次数: {len(self.trades)}")
        return True

    def plot_results(self):
        """绘制结果"""
        if self.signals is None:
            return False

        plt.figure(figsize=(15, 10))

        # 价格与信号
        ax1 = plt.subplot(3, 1, 1)
        ax1.plot(self.signals['date'], self.signals['close'], label='Close')
        ax1.plot(self.signals['date'], self.signals['MA20'], label='MA20', linestyle='--')
        ax1.plot(self.signals['date'], self.signals['MA60'], label='MA60', linestyle='--')
        ax1.plot(self.signals['date'], self.signals['MA250'], label='MA250', linestyle='--')

        buy_dates = self.signals[self.signals['buy_signal'] == 1]['date']
        buy_prices = self.signals[self.signals['buy_signal'] == 1]['close']
        ax1.scatter(buy_dates, buy_prices, color='red', marker='^', s=100, label='Buy')
        sell_dates = self.signals[self.signals['sell_signal'] == 1]['date']
        sell_prices = self.signals[self.signals['sell_signal'] == 1]['close']
        ax1.scatter(sell_dates, sell_prices, color='green', marker='v', s=100, label='Sell')
        ax1.set_title(f'{self.ticker} Price & Signals')
        ax1.legend()

        # 成交量与换手率
        ax2 = plt.subplot(3, 1, 2, sharex=ax1)
        ax2.bar(self.signals['date'], self.signals['volume'], label='Volume')
        ax2.set_ylabel('Volume')
        ax2b = ax2.twinx()
        ax2b.plot(self.signals['date'], self.signals['turnover_rate'], color='red', label='Turnover Rate')
        ax2b.set_ylabel('Turnover Rate (%)')
        ax2b.legend(loc='upper right')
        ax2.set_title('Volume & Turnover')

        # MACD
        ax3 = plt.subplot(3, 1, 3, sharex=ax1)
        ax3.plot(self.signals['date'], self.signals['dif'], label='DIF')
        ax3.plot(self.signals['date'], self.signals['dea'], label='DEA')
        ax3.bar(self.signals['date'], self.signals['macd'], label='MACD')
        ax3.set_title('MACD')
        ax3.legend()

        plt.tight_layout()
        plt.savefig(os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_strategy_results.png"))
        plt.show()
        return True

    def save_signals(self):
        """保存信号文件（直接使用已生成的信号，不再重复模拟交易）"""
        if self.signals is None:
            return False

        signals_file = os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_strategy_signals.csv")
        # 直接保存所有信号数据，包括买入/卖出标记
        self.signals.to_csv(signals_file, index=False, encoding='utf-8-sig')
        print(f"信号已保存到: {signals_file}")
        return True

    def run(self):
        """运行完整流程"""
        print(f"开始运行 {self.ticker} 日线趋势策略...")
        if not self.load_data():
            return False
        if not self.calculate_indicators():
            return False
        if not self.generate_signals():
            return False
        if not self.backtest():
            return False
        self.plot_results()
        self.save_signals()
        return True

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--ticker', type=str, required=True, help='股票代码，如 300433.SZ')
    args = parser.parse_args()
    strategy = DailyTrendStrategy(args.ticker)
    strategy.run()

if __name__ == "__main__":
    main()