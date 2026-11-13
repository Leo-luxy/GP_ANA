# trend_following_backtest.py
# 趋势跟踪策略回测引擎（统一实现）
# mode='full':   严格多头排列 (MA5>MA10>MA20>MA60 + 收盘>MA120)，再用 MA10 斜率、
#                MA5-MA60 偏离和量比过滤；参数取自 strategy_params 的 full 预设。
# mode='simple': 宽松多头排列 (MA5>MA20 + 收盘>MA120)，只用价、量条件；
#                参数取自 strategy_params 的 simple 预设。
#
# 入离场按工作区既定规则（AGENTS 8.1 / 8.4 / 8.5）实现：
# * 入场 = 空仓 + 趋势确认成立 + 距上次离场已满 reentry_cooldown_days 个交易日；
# * 离场 = 保护止损 / 移动止盈 / 趋势结束，触发离场时记录离场 K 线位置供冷却判断；
# * 保护止损成交分两段语义：
#   1) 当日新触发（当日最低价 <= 止损价）：按 min(止损价, 当日开盘价) 成交，跳空取更差的开盘价；
#   2) 跨日锁死挂起（一字跌停期间没有对手盘、顺延下来的委托）：视为开盘市价单，
#      按开盘价加显式滑点常量 PENDING_STOP_SLIPPAGE 成交；
#   两段成交价最终都夹在当日 [low, high] 区间内，连续多日锁死也只成交一笔；
# * 一字跌停当日不成交、保持持仓，挂单顺延到后续首个可成交日。
#
# 结果统一通过 backtest_artifacts.write_result 落盘：文件名带策略、行情截止日和 run_id，
# 同时写同名 _meta.json；零交易也写空结果，避免旧文件继续冒充最新。
from __future__ import annotations

import argparse
import os
from datetime import datetime

# matplotlib 只在真正要出图时才导入：批量回测每次都要起子进程，
# 顶层导入 pyplot 会平白多花几秒（纯计算路径用不到它）。
import numpy as np
import pandas as pd

try:
    from config import DATA_DIR
except ImportError:  # pragma: no cover - 允许脱离 Flask 单独运行
    DATA_DIR = "./data"

import backtest_artifacts
from indicator_provenance import validate_indicators, IndicatorProvenanceError
from strategy_params import describe, get_params

# A股一字跌停判定阈值：主板 ±10%、创业板/科创板 ±20%、北交所 ±30%，
# 各留 0.5% 容差，抵消前复权价四舍五入造成的边界误差。
LIMIT_DOWN_THRESHOLD_MAIN = 0.095
LIMIT_DOWN_THRESHOLD_GROWTH = 0.195
LIMIT_DOWN_THRESHOLD_BSE = 0.295

# 成交执行假设（不是策略参数，不进入参数指纹）：
# 一字跌停锁死期间挂起、顺延到首个可成交日的止损单，原止损价往往已远低于当日区间，
# 不再按原止损价成交，而是按开盘市价单执行；卖出价 = 开盘价 × (1 - 滑点)，再夹回当日区间。
PENDING_STOP_SLIPPAGE = 0.001

# 回测结果 CSV 的固定列（实盘信号 + 当日指标快照）
BASE_SIGNAL_COLUMNS = [
    'date', 'price', 'signal_type', 'trade_profit', 'exit_type',
    'ADX', 'MACD_hist', 'RSI', 'MA5', 'MA10', 'MA20', 'MA60',
    'ATR', 'BB_lower', 'BB_upper', 'volume_ratio',
    'bull_arrangement', 'trend_confirmed',
]
FULL_SIGNAL_COLUMNS = ['MA10_slope', 'MA5_MA60_diff', 'strong_bull']


def limit_down_threshold_for(ticker):
    """按板块返回一字跌停的相对跌幅阈值。"""
    code = str(ticker).split('.')[0]
    if code.startswith(('300', '301', '688', '689')):
        return LIMIT_DOWN_THRESHOLD_GROWTH
    if code.startswith(('4', '8', '92')):
        return LIMIT_DOWN_THRESHOLD_BSE
    return LIMIT_DOWN_THRESHOLD_MAIN


def clamp_to_daily_range(price, low_p, high_p):
    """把成交价夹在当日 [low, high] 区间内。

    A股日线只给出当日成交区间，落在区间外的价格是不可能成交的价格
    （例如"卖在当日最低价之下"），这里统一夹回区间，避免回测记录虚假成交。
    """
    if not np.isfinite(price):
        return price
    if not (np.isfinite(low_p) and np.isfinite(high_p)):
        return price
    lower, upper = (low_p, high_p) if low_p <= high_p else (high_p, low_p)
    return min(max(price, lower), upper)


def same_day_stop_fill_price(stop_price, open_p, low_p, high_p):
    """当日新触发止损的成交价：跳空按开盘价，否则按止损价，再夹在当日区间内。"""
    return clamp_to_daily_range(min(stop_price, open_p), low_p, high_p)


def pending_stop_fill_price(open_p, low_p, high_p, slippage=PENDING_STOP_SLIPPAGE):
    """跨日锁死挂起的待成交止损单：首个可成交日视为开盘市价单。

    这类委托在早前已经触发，只因一字跌停没有对手盘才顺延下来；原止损价往往
    已远低于当日区间，若继续按 min(止损价, 开盘价) 成交，就会卖出当日最低价
    之下的不存在价格。改为按开盘价加不利滑点成交，并夹回当日区间。
    """
    if not (np.isfinite(open_p) and open_p > 0):
        return clamp_to_daily_range(open_p, low_p, high_p)
    return clamp_to_daily_range(open_p * (1.0 - slippage), low_p, high_p)


class TrendFollowingStrategy:
    def __init__(self, ticker, mode='full', params=None):
        if mode not in ('full', 'simple'):
            raise ValueError(f"未知的策略模式: {mode!r}，可选: ('full', 'simple')")
        self.ticker = ticker
        self.mode = mode
        self.data = None
        self.trades = []
        self.initial_capital = 1000000.0
        self.position_ratio = 0.8
        self.limit_down_threshold = limit_down_threshold_for(ticker)
        self.input_manifest = None
        self.input_fingerprint = None
        # 参数唯一来源：strategy_params 的预设 + 显式覆盖（未知键会直接报错）
        self.p = get_params(mode, params)
        # 兼容旧属性名
        self.default_params = self.p

    # ---- 数据加载 ----
    def load_data(self):
        indicators_file = os.path.join(DATA_DIR, self.ticker, f"{self.ticker}_indicators.csv")
        if not os.path.exists(indicators_file):
            print(f"错误：未找到 {self.ticker} 的指标文件")
            return False
        try:
            meta = validate_indicators(self.ticker, data_dir=DATA_DIR)
            self.input_manifest = {key: meta[key] for key in
                                   ('source_sha256', 'indicators_sha256', 'calculator_version', 'data_asof')}
            self.data = pd.read_csv(indicators_file, float_precision='round_trip')
            self.data['date'] = pd.to_datetime(self.data['date'])
            self.input_fingerprint = backtest_artifacts.fingerprint_frame(self.data)
            if backtest_artifacts.file_sha256(indicators_file) != meta['indicators_sha256']:
                raise IndicatorProvenanceError('加载期间指标改变')
            self._calculate_base_indicators()
            return True
        except (IndicatorProvenanceError, OSError, ValueError, KeyError) as exc:
            self.data = None
            self.input_manifest = None
            self.input_fingerprint = None
            print(f'错误：{self.ticker} 指标来源无效，请重算：{exc}')
            return False

    def _calculate_base_indicators(self):
        df = self.data
        # 老版本指标文件可能没有开/高/低价；缺失时退化为收盘价，保证引擎不崩
        for col in ('open', 'high', 'low'):
            if col not in df.columns:
                df[col] = df['close']
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
                (df['volume_ratio'] > p['volume_ratio_threshold'])
            ).astype(int)

            df['strong_bull'] = (
                (df['bull_arrangement'] == 1) &
                (df['MA10_slope'] > p['slope_threshold']) &
                (df['MA5_MA60_diff'] > p['ma5_ma60_diff_threshold'])
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

        df['trend_ended'] = (
            ((df['MA5'] < df['MA10']) | (df['MA10'] < df['MA20'])) &
            (df['ADX'] < p['exit_adx_threshold']) &
            (df['MACD_hist'] < 0)
        ).astype(int)

        df['trailing_ma'] = df['close'].rolling(p['trailing_ma_period']).mean()

    def _is_limit_down_locked(self, high_p, low_p, prev_close):
        """当日是否为一字跌停：最高价等于最低价，且相对前收盘跌幅达到跌停幅度。

        一字跌停全天无法成交，止损单只能等后续可成交日执行。
        """
        if prev_close is None or not np.isfinite(prev_close) or prev_close <= 0:
            return False
        if not np.isfinite(high_p) or not np.isfinite(low_p):
            return False
        if abs(high_p - low_p) > max(1e-9, abs(high_p) * 1e-9):
            return False
        return (low_p / prev_close - 1.0) <= -self.limit_down_threshold

    # ---- 回测主循环 ----
    def run_backtest(self, initial_capital=1000000, position_ratio=0.8):
        if self.data is None:
            print("请先加载数据")
            return None

        self.initial_capital = float(initial_capital)
        self.position_ratio = float(position_ratio)
        self._generate_signals()
        df = self.data
        p = self.p

        cash = float(initial_capital)
        position = 0
        entry_price = 0.0
        entry_date = None
        atr_at_entry = 0.0
        highest_price = 0.0
        stop_price = 0.0
        stop_pending = False
        trailing_activated = False
        just_bought = False
        last_exit_idx = None
        trades = []
        portfolio_values = []
        prev_close = None

        for i in range(len(df)):
            date = df['date'].iloc[i]
            open_p = float(df['open'].iloc[i])
            high_p = float(df['high'].iloc[i])
            low_p = float(df['low'].iloc[i])
            close_p = float(df['close'].iloc[i])
            atr = df['ATR'].iloc[i]
            atr = float(atr) if pd.notna(atr) else float('nan')
            trend_confirmed = df['trend_confirmed'].iloc[i] == 1
            trend_ended = df['trend_ended'].iloc[i] == 1
            locked_limit_down = self._is_limit_down_locked(high_p, low_p, prev_close)

            if position > 0:
                highest_price = max(highest_price, close_p)
                current_profit = (close_p - entry_price) / entry_price
                if (not trailing_activated and np.isfinite(atr) and atr_at_entry > 0
                        and entry_price > 0):
                    if current_profit > p['profit_target_atr'] * (atr_at_entry / entry_price):
                        trailing_activated = True

            # 入场：空仓 + 趋势确认成立 + 距上次离场已满冷却交易日
            if position == 0 and trend_confirmed:
                cooldown_ok = (last_exit_idx is None
                               or (i - last_exit_idx) >= p['reentry_cooldown_days'] + 1)
                if cooldown_ok and close_p > 0:
                    max_shares = int((cash * position_ratio) / close_p)
                    if max_shares > 0:
                        position = max_shares
                        cash -= position * close_p
                        entry_price = close_p
                        entry_date = date
                        highest_price = close_p
                        trailing_activated = False
                        just_bought = True
                        stop_pending = False
                        if np.isfinite(atr) and atr > 0:
                            atr_at_entry = atr
                            stop_price = entry_price - atr_at_entry * p['atr_stop_multiplier']
                            stop_text = f"{stop_price:.2f}"
                        else:
                            # ATR 无效时不设保护止损（与旧实现一致：不会触发止损）
                            atr_at_entry = 0.0
                            stop_price = float('-inf')
                            stop_text = "无（ATR 无效）"
                        print(f"{date.date()}: 买入 {position} 股 @ {close_p:.2f}, 止损价: {stop_text}")

            # 离场：保护止损 > 移动止盈 > 趋势结束
            if position > 0 and not just_bought:
                exit_price = None
                exit_type = None
                exit_note = ''

                # 止损委托有两段语义，必须区分开：
                # * 当日新触发：此前没有挂单，当日最低价首次触及止损价 —— 当日可执行；
                # * 跨日挂起：早前已经触发、只因一字跌停没有对手盘而顺延下来 —— 首个
                #   可成交日按开盘市价单执行，不能再用早已低于当日区间的原止损价。
                stop_triggered_today = (not stop_pending) and (low_p <= stop_price)
                if stop_triggered_today:
                    stop_pending = True
                pending_carried_over = stop_pending and not stop_triggered_today

                if stop_pending and locked_limit_down:
                    # 一字跌停，全天无法成交；挂单保持有效，继续持仓等下一可交易日
                    print(f"{date.date()}: 一字跌停无法卖出，继续持仓（止损价 {stop_price:.2f}，挂单待成交）")
                elif stop_triggered_today:
                    # 当日触发：跳空时按更差的开盘价，否则按止损价；再夹回当日区间
                    exit_price = same_day_stop_fill_price(stop_price, open_p, low_p, high_p)
                    exit_type = 'stop_loss'
                elif pending_carried_over:
                    # 锁死期间挂起的止损单顺延到这里：按开盘市价单成交（含显式滑点）
                    exit_price = pending_stop_fill_price(open_p, low_p, high_p)
                    exit_type = 'stop_loss'
                    exit_note = f'（跌停顺延首日按开盘市价成交，滑点 {PENDING_STOP_SLIPPAGE:.3%}）'
                elif locked_limit_down:
                    # 一字跌停也无法执行趋势离场，信号顺延到下一可交易日
                    pass
                else:
                    trailing_stop = df['trailing_ma'].iloc[i]
                    if trailing_activated:
                        chandelier_stop = highest_price - p['chandelier_atr_multiplier'] * atr
                        if pd.notna(chandelier_stop):
                            trailing_stop = (chandelier_stop if pd.isna(trailing_stop)
                                             else max(trailing_stop, chandelier_stop))
                    if trailing_activated and pd.notna(trailing_stop) and close_p < trailing_stop:
                        exit_price = clamp_to_daily_range(close_p, low_p, high_p)
                        exit_type = 'trailing_stop'
                    elif trend_ended:
                        exit_price = clamp_to_daily_range(close_p, low_p, high_p)
                        exit_type = 'trend_end'

                if exit_price is not None:
                    cash += position * exit_price
                    profit = (exit_price - entry_price) / entry_price * 100
                    trades.append({
                        'entry_date': entry_date,
                        'entry_price': entry_price,
                        'exit_date': date,
                        'exit_price': exit_price,
                        'profit': profit,
                        'type': exit_type,
                    })
                    print(f"{date.date()}: {exit_type}卖出 @ {exit_price:.2f}{exit_note}, 收益: {profit:.2f}%")
                    last_exit_idx = i
                    position = 0
                    stop_pending = False

            portfolio_values.append(cash + position * close_p)
            just_bought = False
            prev_close = close_p

        # 强制平仓：期末仍持仓按最后收盘价结算，并保留 final_close 记录供监控判断持仓
        if position > 0:
            final_price = clamp_to_daily_range(
                float(df['close'].iloc[-1]),
                float(df['low'].iloc[-1]),
                float(df['high'].iloc[-1]),
            )
            cash += position * final_price
            profit = (final_price - entry_price) / entry_price * 100
            trades.append({
                'entry_date': entry_date,
                'entry_price': entry_price,
                'exit_date': df['date'].iloc[-1],
                'exit_price': final_price,
                'profit': profit,
                'type': 'final_close',
            })
            print(f"{df['date'].iloc[-1].date()}: 结束回测卖出 @ {final_price:.2f}, 收益: {profit:.2f}%")

        self.trades = trades
        df['portfolio_value'] = portfolio_values
        self._print_summary(cash, initial_capital)
        return trades

    def _print_summary(self, final_cash, initial_capital):
        if not self.trades:
            print("\n本期没有产生交易信号")
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
    def _signal_columns(self):
        cols = list(BASE_SIGNAL_COLUMNS)
        if self.mode == 'full':
            cols.extend(FULL_SIGNAL_COLUMNS)
        cols.append('trend_ended')
        return cols

    def _build_signals_frame(self):
        """把交易记录展开成 buy/sell 两行，附带当日指标快照。"""
        if not self.trades:
            return pd.DataFrame(columns=self._signal_columns())

        df = self.data
        signals_list = []
        for trade in self.trades:
            entry_row = df[df['date'] == trade['entry_date']].iloc[0]
            exit_row = df[df['date'] == trade['exit_date']].iloc[0]

            buy = {'date': trade['entry_date'].date(), 'price': trade['entry_price'],
                   'signal_type': 'buy', 'trade_profit': trade['profit'], 'exit_type': trade['type']}
            sell = {'date': trade['exit_date'].date(), 'price': trade['exit_price'],
                    'signal_type': 'sell', 'trade_profit': trade['profit'], 'exit_type': trade['type']}

            for col in BASE_SIGNAL_COLUMNS[5:]:
                buy[col] = entry_row.get(col, np.nan)
                sell[col] = exit_row.get(col, np.nan)
            if self.mode == 'full':
                for col in FULL_SIGNAL_COLUMNS:
                    buy[col] = entry_row.get(col, np.nan)
                    sell[col] = exit_row.get(col, np.nan)
            sell['trend_ended'] = exit_row['trend_ended']

            signals_list.append(buy)
            signals_list.append(sell)

        return pd.DataFrame(signals_list, columns=self._signal_columns())

    def save_trades_to_csv(self, save_path=None):
        """按统一产物命名写入回测结果（含行情截止日与参数身份），返回 CSV 路径。"""
        if self.data is None:
            print("请先加载数据")
            return None

        signals_df = self._build_signals_frame()
        data_asof = backtest_artifacts.data_asof_from_frame(self.data)
        # 真实文件输入必须仍是加载时那一版，运行期间变化则不发布旧结果。
        manifest = self.input_manifest
        if manifest is not None:
            current = backtest_artifacts.source_manifest(self.ticker, DATA_DIR)
            if current != manifest:
                raise IndicatorProvenanceError('回测期间行情/指标输入改变，请重跑')
        data_fingerprint = self.input_fingerprint or backtest_artifacts.fingerprint_frame(self.data)
        csv_path, meta_path = backtest_artifacts.write_result(
            ticker=self.ticker, strategy=self.mode, params=self.p, data_asof=data_asof,
            signals_df=signals_df, initial_capital=self.initial_capital,
            position_ratio=self.position_ratio, data_fingerprint=data_fingerprint,
            source_manifest=manifest,
            extra={'execution': 'daily_ohlc', 'pending_stop_slippage': PENDING_STOP_SLIPPAGE},
        )
        if self.trades:
            print(f"交易信号已保存到: {csv_path}（行情截止 {data_asof}，{len(self.trades)} 笔交易）")
        else:
            print(f"本期零交易，已写入空结果: {csv_path}（行情截止 {data_asof}）")
        print(f"结果元信息已保存到: {meta_path}")

        # 兼容旧调用：需要指定路径时额外落一份副本，主产物仍按统一命名保存
        if save_path:
            os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
            signals_df.to_csv(save_path, index=False, encoding='utf-8-sig')
            print(f"交易信号副本已保存到: {save_path}")
        return csv_path

    # ---- 图表 ----
    def plot_results(self, save_path=None):
        import matplotlib
        matplotlib.use('Agg')  # 无界面环境也能出图，避免依赖交互后端
        import matplotlib.pyplot as plt

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
        ax2.axhline(y=self.initial_capital, color='gray', linestyle='--', label='初始资金')
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
            if self.input_manifest is not None:
                from backtest_all_stocks import write_report_meta
                meta = write_report_meta(
                    save_path, 'chart', self.mode, backtest_artifacts.data_asof_from_frame(self.data),
                    [self.ticker], expected_manifest={self.ticker: self.input_manifest},
                    actual_params=self.p)
                if not meta['valid']:
                    raise IndicatorProvenanceError('绘图期间源数据改变，图表已作废')
            print(f"图表已保存到: {save_path}")
        else:
            plt.show()
        return fig


# ============================================================
# CLI（完整版与兼容入口共用参数定义，避免两套口径）
# ============================================================
def add_param_arguments(parser):
    """加入参数覆盖项；默认值 None 表示使用 strategy_params 的对应预设。"""
    parser.add_argument('--capital', type=int, default=1000000, help='初始资金')
    parser.add_argument('--position', type=float, default=0.8, help='仓位比例')
    parser.add_argument('--adx', type=float, default=None, help='ADX入场阈值（默认取预设）')
    parser.add_argument('--exit_adx', type=float, default=None, help='ADX离场阈值（默认取预设）')
    parser.add_argument('--atr_stop', type=float, default=None, help='ATR止损倍数（默认取预设）')
    parser.add_argument('--chandelier', type=float, default=None, help='吊灯止损倍数（默认取预设）')
    parser.add_argument('--cooldown', type=int, default=None, help='离场后再入场的冷却交易日数（默认取预设 3）')
    parser.add_argument('--no-plot', action='store_true', help='不生成图表（批量跑时省时间）')


def collect_param_overrides(args):
    """把命令行里显式给出的覆盖项收集成 dict。"""
    overrides = {}
    if args.adx is not None:
        overrides['adx_threshold'] = args.adx
    if args.exit_adx is not None:
        overrides['exit_adx_threshold'] = args.exit_adx
    if args.atr_stop is not None:
        overrides['atr_stop_multiplier'] = args.atr_stop
    if args.chandelier is not None:
        overrides['chandelier_atr_multiplier'] = args.chandelier
    if getattr(args, 'cooldown', None) is not None:
        overrides['reentry_cooldown_days'] = args.cooldown
    return overrides


def execute_backtest(strategy, capital=1000000, position_ratio=0.8, plot=True):
    """跑回测 + 落盘 + 出图，供各命令行入口共用。"""
    strategy.run_backtest(initial_capital=capital, position_ratio=position_ratio)
    strategy.save_trades_to_csv()
    if plot:
        stock_dir = os.path.join(DATA_DIR, strategy.ticker)
        os.makedirs(stock_dir, exist_ok=True)
        plot_path = os.path.join(
            stock_dir,
            f"{strategy.ticker}_backtest_{strategy.mode}_{datetime.now().strftime('%Y%m%d')}.png")
        strategy.plot_results(save_path=plot_path)
    return strategy


def build_arg_parser():
    parser = argparse.ArgumentParser(description="趋势跟踪策略回测")
    parser.add_argument('--ticker', required=True, help='股票代码，如 300502.SZ')
    parser.add_argument('--mode', choices=['full', 'simple'], default='full', help='策略模式')
    parser.add_argument('--data-dir', help='隔离行情/指标及回测输出目录，默认使用项目配置')
    add_param_arguments(parser)
    return parser


def main():
    global DATA_DIR
    args = build_arg_parser().parse_args()
    if args.data_dir:
        DATA_DIR = os.path.abspath(args.data_dir)
        backtest_artifacts.DATA_DIR = DATA_DIR
    print(describe(args.mode))
    overrides = collect_param_overrides(args)
    strategy = TrendFollowingStrategy(args.ticker, mode=args.mode, params=overrides or None)
    if not strategy.load_data():
        return 1
    execute_backtest(strategy, capital=args.capital, position_ratio=args.position,
                     plot=not args.no_plot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
