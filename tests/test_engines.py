"""趋势跟踪引擎回归测试（标准库 unittest）。

覆盖：
* 跳空止损按开盘价成交，成交价落在当日 [low, high] 区间内（不高于最高、不低于最低）；
* 一字跌停当日不成交，顺延到下一可交易日；锁死挂起的待成交单视为开盘市价单
  （开盘价 + 显式滑点常量），连续多日锁死只成交一笔；
* full 模式的量比阈值真正接入参数（1.0 与 4.0 必须产生不同信号）；
* 工作区规则 8.1 的离场冷却：3 个交易日内不重入，第 4 个交易日趋势仍在则入场；
* 统一引擎 simple 与兼容入口的权益曲线逐日完全一致；
* 回测产物身份：strategy / params_sha1 / data_asof 正确，零交易也落盘。

全部使用进程内构造的合成指标表，不读写 data/ 目录。
"""

import json
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import indicator_provenance
import backtest_artifacts  # noqa: E402
import strategy_params  # noqa: E402
import trend_following_backtest as unified_engine  # noqa: E402
import trend_following_backtest_simplified as simplified_engine  # noqa: E402
import backtest_all_stocks as batch_monitor  # noqa: E402
from trend_following_backtest import TrendFollowingStrategy  # noqa: E402
from trend_following_backtest_simplified import (  # noqa: E402
    TrendFollowingStrategy as SimplifiedTrendFollowingStrategy,
)

BASE_TICKER = '600000.SH'
GROWTH_TICKER = '300001.SZ'


def _make_frame(n, base=10.0, step=0.01, atr=1.0, adx=30.0, volume=100.0,
                volume_from=None, volume_value=300.0, macd=-0.01):
    """构造合成指标表。

    * 收盘价按 step 线性上涨，open/high/low 默认等于 close，避免意外触发止损；
    * volume_from 之后成交量放大，用来制造 volume_ratio > 阈值；
    * macd 为 MACD_hist 初值，测试里再按需改写特定行来控制趋势确认。
    """
    idx = np.arange(n)
    closes = base + step * idx
    volumes = np.full(n, float(volume))
    if volume_from is not None:
        volumes[volume_from:] = float(volume_value)
    return pd.DataFrame({
        'date': pd.bdate_range(start='2025-01-01', periods=n),
        'open': closes,
        'high': closes,
        'low': closes,
        'close': closes,
        'volume': volumes,
        'ATR': float(atr),
        'ADX': float(adx),
        'MACD_hist': float(macd),
        'RSI': 55.0,
        'BB_lower': closes * 0.95,
        'BB_upper': closes * 1.05,
    })


def _run_engine(frame, mode='simple', ticker=BASE_TICKER, params=None,
                simplified=False, capital=1000000, ratio=0.8):
    """用合成表在进程内跑引擎，返回 (策略实例, 交易列表)。"""
    if simplified:
        strategy = SimplifiedTrendFollowingStrategy(ticker, params=params)
    else:
        strategy = TrendFollowingStrategy(ticker, mode=mode, params=params)
    strategy.data = frame.copy()
    strategy.data['date'] = pd.to_datetime(strategy.data['date'])
    strategy._calculate_base_indicators()
    trades = strategy.run_backtest(initial_capital=capital, position_ratio=ratio)
    return strategy, trades


def _index_of(strategy, date):
    matches = strategy.data.index[strategy.data['date'] == date]
    return int(matches[0])


def _entry_indices(strategy):
    return [_index_of(strategy, trade['entry_date']) for trade in strategy.trades]


def _simple_trend_frame(n=240, base=10.0, step=0.01, entry_idx=150, vol_from=140):
    """simple 模式基准表：entry_idx 当天趋势确认成立（量比放大 + MACD 转正）。"""
    frame = _make_frame(n, base=base, step=step, volume_from=vol_from)
    frame.loc[entry_idx, 'MACD_hist'] = 0.1
    return frame


class TestStopExecutionPrice(unittest.TestCase):
    """P0-4：止损成交价必须落在当日可成交区间内。"""

    def test_gap_down_stop_fills_at_open(self):
        frame = _simple_trend_frame()
        # 次日跳空：开盘 7.5 < 止损价 8.5，且当日最高价 7.8 也低于止损价
        frame.loc[151, ['open', 'high', 'low', 'close']] = [7.5, 7.8, 7.0, 7.6]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['type'], 'stop_loss')
        self.assertAlmostEqual(trade['entry_price'], 11.5, places=6)
        # 跳空按开盘价成交，而不是按止损价 8.5 成交
        self.assertAlmostEqual(trade['exit_price'], 7.5, places=6)
        self.assertAlmostEqual(trade['exit_price'], frame.loc[151, 'open'], places=6)
        # 成交价不得高于当日最高价（旧实现会以 8.5 成交，高于最高价 7.8）
        self.assertLessEqual(trade['exit_price'], frame.loc[151, 'high'] + 1e-9)
        # 真实收益约 -34.8%，旧实现报告 -26.1%
        self.assertAlmostEqual(trade['profit'], (7.5 - 11.5) / 11.5 * 100, places=6)

    def test_intraday_stop_uses_stop_price_not_above_high(self):
        frame = _simple_trend_frame()
        # 盘中止损：开盘 9.0 高于止损价 8.5，按止损价成交
        frame.loc[151, ['open', 'high', 'low', 'close']] = [9.0, 9.2, 8.0, 9.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['type'], 'stop_loss')
        self.assertAlmostEqual(trade['exit_price'], 8.5, places=6)
        self.assertLessEqual(trade['exit_price'], frame.loc[151, 'high'] + 1e-9)

    def test_limit_down_locked_day_holds_then_exits_next_tradable_day(self):
        frame = _simple_trend_frame(n=240, base=100.0, step=0.1)
        # 次日一字跌停：前一交易日收盘 115，跌停价 103.5，全天只有一个价格
        frame.loc[151, ['open', 'high', 'low', 'close']] = [103.5, 103.5, 103.5, 103.5]
        # 再下一日继续低开，可以正常成交
        frame.loc[152, ['open', 'high', 'low', 'close']] = [93.15, 93.6, 92.5, 92.8]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['type'], 'stop_loss')
        # 跌停当日不能成交：离场发生在下一可交易日
        self.assertEqual(_index_of(strategy, trade['exit_date']), 152)
        # 顺延下来的挂单按开盘市价单成交（开盘 93.15，含显式滑点），不再用原止损价 112
        expected_fill = 93.15 * (1 - unified_engine.PENDING_STOP_SLIPPAGE)
        self.assertAlmostEqual(trade['exit_price'], expected_fill, places=6)
        self.assertLess(trade['exit_price'], 112.0)
        # 成交价必须落在成交日 [low, high] 区间内
        exit_row = strategy.data.iloc[152]
        self.assertGreaterEqual(trade['exit_price'], float(exit_row['low']) - 1e-9)
        self.assertLessEqual(trade['exit_price'], float(exit_row['high']) + 1e-9)

        # 持仓在跌停当日仍然保留：权益 = 现金 + 持股数 * 跌停价
        entry_price = trade['entry_price']
        shares = int(1000000 * 0.8 / entry_price)
        cash_after_entry = 1000000 - shares * entry_price
        expected_equity = cash_after_entry + shares * 103.5
        self.assertAlmostEqual(strategy.data['portfolio_value'].iloc[151], expected_equity, places=4)

    def test_growth_board_limit_is_20_percent(self):
        """创业板跌停幅度是 20%：-10% 的一字板不是跌停锁死，应当日成交。"""
        frame = _simple_trend_frame(n=240, base=100.0, step=0.1)
        frame.loc[151, ['open', 'high', 'low', 'close']] = [103.5, 103.5, 103.5, 103.5]
        strategy, trades = _run_engine(frame, ticker=GROWTH_TICKER)

        self.assertEqual(len(trades), 1)
        self.assertEqual(_index_of(strategy, trades[0]['exit_date']), 151)
        self.assertAlmostEqual(trades[0]['exit_price'], 103.5, places=6)


class TestPendingStopExecution(unittest.TestCase):
    """跨日锁死挂起的止损单：两段成交语义、区间边界、连续锁死只成交一笔。"""

    @staticmethod
    def _locked_frame(ticker=BASE_TICKER):
        """simple 基准表：入场 115（第 151 根），ATR=1、3 倍止损 -> 止损价 112。"""
        return _simple_trend_frame(n=240, base=100.0, step=0.1)

    def test_rebound_day_fill_stays_inside_daily_range(self):
        """复现背景缺陷：一字跌停锁死后次日反弹，原止损价 112 已低于当日最低价 113。"""
        frame = self._locked_frame()
        frame.loc[151, ['open', 'high', 'low', 'close']] = [103.5, 103.5, 103.5, 103.5]
        frame.loc[152, ['open', 'high', 'low', 'close']] = [114.0, 120.0, 113.0, 118.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['type'], 'stop_loss')
        self.assertEqual(_index_of(strategy, trade['exit_date']), 152)
        low = float(strategy.data.iloc[152]['low'])
        high = float(strategy.data.iloc[152]['high'])
        # 成交价必须在当日区间内，且不能再用低于最低价的 112
        self.assertGreaterEqual(trade['exit_price'], low - 1e-9)
        self.assertLessEqual(trade['exit_price'], high + 1e-9)
        self.assertGreater(trade['exit_price'], 113.0)
        # 锁死挂单顺延到首个可成交日，按开盘市价 + 显式滑点成交
        self.assertAlmostEqual(
            trade['exit_price'], 114.0 * (1 - unified_engine.PENDING_STOP_SLIPPAGE), places=6)

    def test_same_day_trigger_uses_stop_price_without_slippage(self):
        """当日新触发按 min(止损价, 开盘价)，不套用挂单滑点。"""
        frame = self._locked_frame()
        # 开盘 114 高于止损 112，盘中最低 111 触发止损
        frame.loc[151, ['open', 'high', 'low', 'close']] = [114.0, 116.0, 111.0, 115.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        self.assertEqual(_index_of(strategy, trades[0]['exit_date']), 151)
        self.assertAlmostEqual(trades[0]['exit_price'], 112.0, places=6)

    def test_same_day_gap_down_fills_at_open(self):
        """当日触发但跳空低开：按更差的开盘价成交，且不低于当日最低价。"""
        frame = self._locked_frame()
        frame.loc[151, ['open', 'high', 'low', 'close']] = [110.0, 111.0, 109.0, 110.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        self.assertEqual(_index_of(strategy, trades[0]['exit_date']), 151)
        self.assertAlmostEqual(trades[0]['exit_price'], 110.0, places=6)
        self.assertGreaterEqual(trades[0]['exit_price'], 109.0 - 1e-9)

    def test_locked_day_has_no_fill(self):
        """一字跌停当日不产生任何成交，持仓与权益保持不变。"""
        frame = self._locked_frame()
        frame.loc[151, ['open', 'high', 'low', 'close']] = [103.5, 103.5, 103.5, 103.5]
        frame.loc[152, ['open', 'high', 'low', 'close']] = [114.0, 120.0, 113.0, 118.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        self.assertEqual(_index_of(strategy, trades[0]['exit_date']), 152)
        entry_price = trades[0]['entry_price']
        shares = int(1000000 * 0.8 / entry_price)
        cash_after_entry = 1000000 - shares * entry_price
        self.assertAlmostEqual(
            float(strategy.data['portfolio_value'].iloc[151]),
            cash_after_entry + shares * 103.5, places=4)
        # 信号表里锁死当日没有卖出记录
        signals = strategy._build_signals_frame()
        sell_rows = signals[signals['signal_type'] == 'sell']
        self.assertEqual(len(sell_rows), 1)
        self.assertEqual(pd.to_datetime(sell_rows['date'].iloc[0]).date(),
                         pd.Timestamp(frame['date'].iloc[152]).date())

    def test_multiple_locked_days_sell_only_once(self):
        """连续多日一字跌停只允许一笔卖出成交，不得重复扣仓。"""
        frame = self._locked_frame()
        frame.loc[151, ['open', 'high', 'low', 'close']] = [103.5, 103.5, 103.5, 103.5]
        frame.loc[152, ['open', 'high', 'low', 'close']] = [93.15, 93.15, 93.15, 93.15]
        frame.loc[153, ['open', 'high', 'low', 'close']] = [83.835, 83.835, 83.835, 83.835]
        frame.loc[154, ['open', 'high', 'low', 'close']] = [90.0, 95.0, 88.0, 92.0]
        strategy, trades = _run_engine(frame)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade['type'], 'stop_loss')
        self.assertEqual(_index_of(strategy, trade['exit_date']), 154)
        self.assertAlmostEqual(
            trade['exit_price'], 90.0 * (1 - unified_engine.PENDING_STOP_SLIPPAGE), places=6)

        entry_price = trade['entry_price']
        shares = int(1000000 * 0.8 / entry_price)
        cash_after_entry = 1000000 - shares * entry_price
        # 三个锁死交易日均无成交：权益只随跌停价变动，没有提前卖出
        for idx, locked_price in ((151, 103.5), (152, 93.15), (153, 83.835)):
            self.assertAlmostEqual(
                float(strategy.data['portfolio_value'].iloc[idx]),
                cash_after_entry + shares * locked_price, places=4)
        # 首个可成交日只成交一笔：权益 = 买入后现金 + 一笔卖出所得
        self.assertAlmostEqual(
            float(strategy.data['portfolio_value'].iloc[154]),
            cash_after_entry + shares * trade['exit_price'], places=4)

    def test_fill_price_always_within_daily_range_across_scenarios(self):
        """多组构造：任何成交价都不高于当日最高、不低于当日最低。"""
        scenarios = [
            ('主板盘中止损', BASE_TICKER, {151: [114.0, 116.0, 111.0, 115.0]}),
            ('主板跳空止损', BASE_TICKER, {151: [110.0, 111.0, 109.0, 110.0]}),
            ('跌停后反弹', BASE_TICKER,
             {151: [103.5, 103.5, 103.5, 103.5], 152: [114.0, 120.0, 113.0, 118.0]}),
            ('连续跌停后反弹', BASE_TICKER,
             {151: [103.5, 103.5, 103.5, 103.5], 152: [93.15, 93.15, 93.15, 93.15],
              153: [83.835, 83.835, 83.835, 83.835], 154: [90.0, 95.0, 88.0, 92.0]}),
            ('创业板20%跌停后反弹', GROWTH_TICKER,
             {151: [92.0, 92.0, 92.0, 92.0], 152: [113.0, 116.0, 111.0, 115.0]}),
            ('反弹日开盘即最低', BASE_TICKER,
             {151: [103.5, 103.5, 103.5, 103.5], 152: [100.0, 105.0, 100.0, 104.0]}),
            ('继续深跌后开盘', BASE_TICKER,
             {151: [103.5, 103.5, 103.5, 103.5], 152: [80.0, 82.0, 78.0, 79.0]}),
        ]
        for name, ticker, rows in scenarios:
            with self.subTest(scenario=name):
                frame = _simple_trend_frame(n=240, base=100.0, step=0.1)
                for idx, ohlc in rows.items():
                    frame.loc[idx, ['open', 'high', 'low', 'close']] = ohlc
                strategy, trades = _run_engine(frame, ticker=ticker)
                self.assertGreaterEqual(len(trades), 1, name)
                for trade in trades:
                    exit_idx = _index_of(strategy, trade['exit_date'])
                    exit_row = strategy.data.iloc[exit_idx]
                    low = float(exit_row['low'])
                    high = float(exit_row['high'])
                    self.assertGreaterEqual(trade['exit_price'], low - 1e-9,
                                            f'{name}: 成交价低于当日最低价 {trade["exit_price"]} < {low}')
                    self.assertLessEqual(trade['exit_price'], high + 1e-9,
                                         f'{name}: 成交价高于当日最高价 {trade["exit_price"]} > {high}')


class TestFullParamWiring(unittest.TestCase):
    """4.1：full 模式量比阈值必须真正生效。"""

    def _confirmed_count(self, threshold):
        frame = _make_frame(240, base=10.0, step=0.02, volume_from=140, volume_value=400.0)
        frame['MACD_hist'] = 0.1
        strategy, trades = _run_engine(
            frame, mode='full', params={'volume_ratio_threshold': threshold})
        return int(strategy.data['trend_confirmed'].sum()), trades

    def test_volume_ratio_threshold_changes_signals(self):
        confirmed_low, trades_low = self._confirmed_count(1.0)
        confirmed_high, trades_high = self._confirmed_count(4.0)

        self.assertGreater(confirmed_low, 0)
        self.assertEqual(confirmed_high, 0)
        self.assertNotEqual(confirmed_low, confirmed_high)
        # 阈值 4.0 时量比永远达不到，不应产生任何交易
        self.assertEqual(len(trades_high), 0)
        self.assertGreaterEqual(len(trades_low), 1)

    def test_unknown_param_rejected(self):
        with self.assertRaises(KeyError):
            TrendFollowingStrategy(BASE_TICKER, mode='full', params={'volume_ratio': 1.0})


class TestReentryCooldown(unittest.TestCase):
    """8.1：离场后 3 个交易日内不重入，第 4 个交易日趋势仍在则入场。"""

    def test_no_reentry_within_three_days_then_entry_on_fourth(self):
        frame = _simple_trend_frame()
        # 离场后趋势确认持续成立
        frame.loc[150:, 'MACD_hist'] = 0.1
        # 第 151 根触发保护止损
        frame.loc[151, ['open', 'high', 'low', 'close']] = [11.49, 11.50, 8.0, 11.4]
        strategy, trades = _run_engine(frame)

        entries = _entry_indices(strategy)
        self.assertEqual(entries[0], 150)
        # 151 离场，152/153/154 在冷却期内，155（第 4 个交易日）趋势仍在才重新入场
        self.assertEqual(entries[1], 155)
        self.assertEqual(entries, [150, 155])
        self.assertNotIn(152, entries)
        self.assertNotIn(153, entries)
        self.assertNotIn(154, entries)
        self.assertEqual(trades[0]['type'], 'stop_loss')

    def test_cooldown_parameter_is_configurable(self):
        frame = _simple_trend_frame()
        frame.loc[150:, 'MACD_hist'] = 0.1
        frame.loc[151, ['open', 'high', 'low', 'close']] = [11.49, 11.50, 8.0, 11.4]
        # 冷却 2 个交易日：151 离场后，154 就允许再入场（默认 3 天要等到 155）
        strategy, trades = _run_engine(frame, params={'reentry_cooldown_days': 2})

        entries = _entry_indices(strategy)
        self.assertEqual(entries, [150, 154])


class TestExpandedParamDefaults(unittest.TestCase):
    """参数默认值必须来自 strategy_params，且两版入口一致。"""

    def test_unified_engine_uses_preset(self):
        strategy = TrendFollowingStrategy(BASE_TICKER, mode='full')
        self.assertEqual(strategy.p, strategy_params.PRESET_PARAMS['full'])
        strategy.p['adx_threshold'] = 1
        self.assertEqual(strategy_params.PRESET_PARAMS['full']['adx_threshold'], 25)

    def test_simplified_entry_defaults_to_atr3(self):
        strategy = SimplifiedTrendFollowingStrategy(BASE_TICKER)
        self.assertEqual(strategy.mode, 'simple')
        self.assertEqual(strategy.p, strategy_params.PRESET_PARAMS['simple'])
        self.assertAlmostEqual(strategy.p['atr_stop_multiplier'], 3.0)
        self.assertEqual(strategy.p['reentry_cooldown_days'], 3)


class TestSimpleEquivalence(unittest.TestCase):
    """两份文件对同一份数据、同一组参数必须跑出完全相同的权益曲线。"""

    def _frames(self):
        frame = _simple_trend_frame()
        frame.loc[150:, 'MACD_hist'] = 0.1
        frame.loc[151, ['open', 'high', 'low', 'close']] = [11.49, 11.50, 8.0, 11.4]
        return frame

    def _assert_same(self, params):
        frame = self._frames()
        unified, unified_trades = _run_engine(frame, mode='simple', params=params)
        legacy, legacy_trades = _run_engine(frame, params=params, simplified=True)

        np.testing.assert_array_equal(
            unified.data['portfolio_value'].to_numpy(),
            legacy.data['portfolio_value'].to_numpy(),
        )
        self.assertEqual(len(unified_trades), len(legacy_trades))
        for left, right in zip(unified_trades, legacy_trades):
            self.assertEqual(left['entry_date'], right['entry_date'])
            self.assertEqual(left['exit_date'], right['exit_date'])
            self.assertEqual(left['type'], right['type'])
            self.assertAlmostEqual(left['entry_price'], right['entry_price'], places=9)
            self.assertAlmostEqual(left['exit_price'], right['exit_price'], places=9)

    def test_default_params_give_identical_equity(self):
        self._assert_same(None)

    def test_override_params_give_identical_equity(self):
        self._assert_same({'atr_stop_multiplier': 2.0, 'adx_threshold': 20})


class TestArtifactIdentity(unittest.TestCase):
    """回测产物必须带策略/参数/行情截止日身份，零交易也落盘。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_data_dir = backtest_artifacts.DATA_DIR
        self._old_engine_dir = unified_engine.DATA_DIR
        unified_engine.DATA_DIR = self.tmp.name
        backtest_artifacts.DATA_DIR = self.tmp.name

    def tearDown(self):
        backtest_artifacts.DATA_DIR = self._old_data_dir
        unified_engine.DATA_DIR = self._old_engine_dir
        self.tmp.cleanup()

    def _files(self, ticker):
        ticker_dir = os.path.join(self.tmp.name, ticker)
        self.assertTrue(os.path.isdir(ticker_dir))
        return sorted(os.listdir(ticker_dir))

    def test_meta_has_strategy_params_and_data_asof(self):
        frame = _simple_trend_frame()
        strategy, trades = _run_engine(frame, mode='simple')
        self.assertGreaterEqual(len(trades), 1)

        ticker_dir = os.path.join(self.tmp.name, strategy.ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        strategy.data[list(backtest_artifacts.MARKET_COLUMNS)].to_csv(
            os.path.join(ticker_dir, f'{strategy.ticker}_qfq.csv'), index=False)
        indicator_provenance.write_indicators(strategy.data, strategy.ticker, data_dir=self.tmp.name)
        strategy.input_manifest = backtest_artifacts.source_manifest(strategy.ticker, data_dir=self.tmp.name)
        csv_path = strategy.save_trades_to_csv()
        asof = strategy.data['date'].iloc[-1].strftime('%Y%m%d')
        filename = os.path.basename(csv_path)

        self.assertIn('_backtest_simple_' + asof + '_', filename)
        self.assertTrue(os.path.exists(backtest_artifacts.meta_path(csv_path)))
        with open(backtest_artifacts.meta_path(csv_path), 'r', encoding='utf-8') as fh:
            meta = json.load(fh)

        self.assertEqual(meta['strategy'], 'simple')
        self.assertEqual(meta['data_asof'], asof)
        self.assertEqual(meta['params_sha1'], backtest_artifacts.params_fingerprint(strategy.p))
        self.assertEqual(meta['params']['reentry_cooldown_days'], 3.0)
        self.assertEqual(meta['execution'], 'daily_ohlc')
        # 行情内容指纹与成交执行假设写进元信息，读取端据此识别"行情已重建、回测没重跑"
        self.assertEqual(meta['data_fingerprint'],
                         backtest_artifacts.fingerprint_frame(strategy.data))
        self.assertEqual(meta['pending_stop_slippage'],
                         unified_engine.PENDING_STOP_SLIPPAGE)
        self.assertEqual(meta['trades'], len(trades))
        self.assertEqual(meta['rows'], len(trades) * 2)

        # 读取端按策略 + 期望截止日可以精确取到这份产物
        info = backtest_artifacts.latest(BASE_TICKER, strategy='simple', data_asof=asof)
        self.assertEqual(info['path'], csv_path)
        signals = backtest_artifacts.load_signals(csv_path)
        self.assertEqual(len(signals), len(trades) * 2)
        self.assertEqual(int(signals['signal_type'].eq('sell').sum()), len(trades))

    def test_zero_trade_still_written(self):
        # MACD 恒为负，趋势确认不成立，本期零交易
        frame = _make_frame(240, volume_from=140)
        strategy, trades = _run_engine(frame, mode='simple')
        self.assertEqual(trades, [])

        ticker_dir = os.path.join(self.tmp.name, strategy.ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        strategy.data[list(backtest_artifacts.MARKET_COLUMNS)].to_csv(
            os.path.join(ticker_dir, f'{strategy.ticker}_qfq.csv'), index=False)
        indicator_provenance.write_indicators(strategy.data, strategy.ticker, data_dir=self.tmp.name)
        strategy.input_manifest = backtest_artifacts.source_manifest(strategy.ticker, data_dir=self.tmp.name)
        csv_path = strategy.save_trades_to_csv()
        asof = strategy.data['date'].iloc[-1].strftime('%Y%m%d')
        self.assertIn('_backtest_simple_' + asof + '_', os.path.basename(csv_path))

        with open(backtest_artifacts.meta_path(csv_path), 'r', encoding='utf-8') as fh:
            meta = json.load(fh)
        self.assertEqual(meta['rows'], 0)
        self.assertEqual(meta['trades'], 0)

        loaded = backtest_artifacts.load_signals(csv_path)
        self.assertEqual(len(loaded), 0)
        self.assertIn('signal_type', loaded.columns)
        # 零交易的空结果也能被读取端按截止日取到，旧结果不会再冒充最新
        info = backtest_artifacts.latest(BASE_TICKER, strategy='simple', data_asof=asof)
        self.assertEqual(info['path'], csv_path)

    def test_full_mode_zero_trade_keeps_full_columns(self):
        frame = _make_frame(240, base=10.0, step=0.02, volume_from=140, volume_value=400.0)
        strategy, trades = _run_engine(frame, mode='full')
        self.assertEqual(trades, [])

        ticker_dir = os.path.join(self.tmp.name, strategy.ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        strategy.data[list(backtest_artifacts.MARKET_COLUMNS)].to_csv(
            os.path.join(ticker_dir, f'{strategy.ticker}_qfq.csv'), index=False)
        indicator_provenance.write_indicators(strategy.data, strategy.ticker, data_dir=self.tmp.name)
        strategy.input_manifest = backtest_artifacts.source_manifest(strategy.ticker, data_dir=self.tmp.name)
        csv_path = strategy.save_trades_to_csv()
        asof = strategy.data['date'].iloc[-1].strftime('%Y%m%d')
        self.assertIn('_backtest_full_' + asof + '_', os.path.basename(csv_path))

        with open(backtest_artifacts.meta_path(csv_path), 'r', encoding='utf-8') as fh:
            meta = json.load(fh)
        self.assertEqual(meta['strategy'], 'full')

        loaded = backtest_artifacts.load_signals(csv_path)
        self.assertEqual(len(loaded), 0)
        self.assertIn('MA10_slope', loaded.columns)
        self.assertIn('strong_bull', loaded.columns)


class TestStrategyParams(unittest.TestCase):
    """参数单一来源的约束。"""

    REQUIRED_KEYS = {
        'adx_threshold', 'confirmation_days', 'volume_ratio_threshold',
        'slope_threshold', 'ma5_ma60_diff_threshold', 'max_recent_days',
        'atr_stop_multiplier', 'exit_adx_threshold', 'trailing_ma_period',
        'chandelier_atr_multiplier', 'profit_target_atr', 'reentry_cooldown_days',
    }

    def test_presets_are_complete_and_unchanged(self):
        full = strategy_params.get_params('full')
        simple = strategy_params.get_params('simple')
        self.assertEqual(set(full), self.REQUIRED_KEYS)
        self.assertEqual(set(simple), self.REQUIRED_KEYS)
        # full：保留原有数值 + 新增的量比/偏离/冷却
        self.assertEqual(full['volume_ratio_threshold'], 1.2)
        self.assertEqual(full['ma5_ma60_diff_threshold'], 0.01)
        self.assertEqual(full['confirmation_days'], 3)
        # simple：不顺手改动既有 ADX25 / ATR3 / 量比1.1
        self.assertEqual(simple['adx_threshold'], 25)
        self.assertAlmostEqual(simple['atr_stop_multiplier'], 3.0)
        self.assertEqual(simple['volume_ratio_threshold'], 1.1)
        for params in (full, simple):
            self.assertEqual(params['reentry_cooldown_days'], 3)

    def test_get_params_returns_deep_copy(self):
        params = strategy_params.get_params('full')
        params['adx_threshold'] = 99
        params['volume_ratio_threshold'] = 9.9
        reloaded = strategy_params.get_params('full')
        self.assertEqual(reloaded['adx_threshold'], 25)
        self.assertEqual(reloaded['volume_ratio_threshold'], 1.2)

    def test_overrides_and_errors(self):
        params = strategy_params.get_params('simple', {'atr_stop_multiplier': 2.0})
        self.assertAlmostEqual(params['atr_stop_multiplier'], 2.0)
        self.assertAlmostEqual(strategy_params.PRESET_PARAMS['simple']['atr_stop_multiplier'], 3.0)
        with self.assertRaises(KeyError):
            strategy_params.get_params('simple', {'volume_ratio': 1.0})
        with self.assertRaises(ValueError):
            strategy_params.get_params('swing')

    def test_describe_mentions_key_params(self):
        text = strategy_params.describe('simple')
        for key in ('atr_stop_multiplier', 'reentry_cooldown_days', 'volume_ratio_threshold'):
            self.assertIn(key, text)


class TestCliOverrides(unittest.TestCase):
    """命令行覆盖仍然有效；默认值来自 strategy_params 预设。"""

    def test_unified_cli_overrides_take_effect(self):
        parser = unified_engine.build_arg_parser()
        args = parser.parse_args([
            '--ticker', BASE_TICKER, '--mode', 'simple',
            '--atr_stop', '2', '--cooldown', '5', '--adx', '20',
        ])
        overrides = unified_engine.collect_param_overrides(args)
        self.assertEqual(overrides, {
            'atr_stop_multiplier': 2.0,
            'reentry_cooldown_days': 5,
            'adx_threshold': 20.0,
        })
        strategy = TrendFollowingStrategy(BASE_TICKER, mode='simple', params=overrides)
        self.assertAlmostEqual(strategy.p['atr_stop_multiplier'], 2.0)
        self.assertEqual(strategy.p['reentry_cooldown_days'], 5)
        self.assertAlmostEqual(strategy.p['adx_threshold'], 20.0)

    def test_simplified_cli_defaults_to_preset(self):
        parser = simplified_engine.build_arg_parser()
        args = parser.parse_args(['--ticker', BASE_TICKER])
        overrides = unified_engine.collect_param_overrides(args)
        self.assertEqual(overrides, {})
        strategy = simplified_engine.TrendFollowingStrategy(BASE_TICKER, params=overrides or None)
        # 简化版入口默认 ATR 止损 3 倍（此前 CLI 默认 2 倍，现已对齐 simple 预设）
        self.assertAlmostEqual(strategy.p['atr_stop_multiplier'], 3.0)

    def test_simplified_cli_override_still_works(self):
        parser = simplified_engine.build_arg_parser()
        args = parser.parse_args(['--ticker', BASE_TICKER, '--atr_stop', '2'])
        overrides = unified_engine.collect_param_overrides(args)
        strategy = simplified_engine.TrendFollowingStrategy(BASE_TICKER, params=overrides)
        self.assertAlmostEqual(strategy.p['atr_stop_multiplier'], 2.0)
        # 预设本身不能被命令行改掉
        self.assertAlmostEqual(
            strategy_params.PRESET_PARAMS['simple']['atr_stop_multiplier'], 3.0)


class TestMonitorStateMachine(unittest.TestCase):
    """监控状态机：可入场 / 持有 / 观望，以及数据过期、旧格式产物必须显式报告。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = self.tmp.name
        self._old = {
            'artifacts': backtest_artifacts.DATA_DIR,
            'engine': unified_engine.DATA_DIR,
            'batch': batch_monitor.DATA_DIR,
        }
        backtest_artifacts.DATA_DIR = self.data_dir
        unified_engine.DATA_DIR = self.data_dir
        batch_monitor.DATA_DIR = self.data_dir

    def tearDown(self):
        backtest_artifacts.DATA_DIR = self._old['artifacts']
        unified_engine.DATA_DIR = self._old['engine']
        batch_monitor.DATA_DIR = self._old['batch']
        self.tmp.cleanup()

    def _write_indicators(self, ticker, frame):
        ticker_dir = os.path.join(self.data_dir, ticker)
        os.makedirs(ticker_dir, exist_ok=True)
        frame[list(backtest_artifacts.MARKET_COLUMNS)].to_csv(
            os.path.join(ticker_dir, f'{ticker}_qfq.csv'), index=False)
        indicator_provenance.write_indicators(frame, ticker, data_dir=self.data_dir)
        self.expected_asof = frame['date'].iloc[-1].strftime('%Y%m%d')
        return frame['date'].iloc[-1].strftime('%Y%m%d')

    def _indicator_fingerprint(self, ticker):
        """监控产物写入时同样带上行情内容指纹，读取端才能做三重身份校验。"""
        path = os.path.join(self.data_dir, ticker, f"{ticker}_indicators.csv")
        return backtest_artifacts.fingerprint_csv(path)

    def _write_signals(self, ticker, asof, rows):
        backtest_artifacts.write_result(
            ticker, 'simple', strategy_params.get_params('simple'), asof,
            pd.DataFrame(rows), run_id='20260101T000000',
            data_fingerprint=self._indicator_fingerprint(ticker),
            source_manifest=backtest_artifacts.source_manifest(ticker, data_dir=self.data_dir))

    @staticmethod
    def _row(date, price, signal_type, exit_type, profit=0.0):
        return {'date': date.strftime('%Y-%m-%d'), 'price': price,
                'signal_type': signal_type, 'trade_profit': profit,
                'exit_type': exit_type}

    def _run_monitor(self, tickers, asof=None):
        return batch_monitor.generate_monitor_report(tickers, mode='simple',
                                                     asof=asof or self.expected_asof, write_file=False)

    def test_holding_with_entry_today_is_entry_signal(self):
        ticker = '600000.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        latest = frame['date'].iloc[-1]
        self._write_signals(ticker, asof, [
            self._row(latest, 10.0, 'buy', 'final_close'),
            self._row(latest, 10.0, 'sell', 'final_close', 0.0),
        ])
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'], [])
        self.assertEqual(report['可入场'][0]['ticker'], ticker)
        self.assertEqual(report['可入场'][0]['detail'], '买入当日')

    def test_mixed_source_dates_accept_each_exact_artifact(self):
        frame = _make_frame(240)
        cutoff = frame['date'].iloc[-2].strftime('%Y%m%d')
        for ticker, data in [('600010.SH', frame.iloc[:-1].copy()),
                             ('600011.SH', frame.copy())]:
            actual = self._write_indicators(ticker, data)
            latest = data['date'].iloc[-1]
            self._write_signals(ticker, actual, [
                self._row(latest, 10.0, 'buy', 'final_close'),
                self._row(latest, 10.0, 'sell', 'final_close'),
            ])
        report = self._run_monitor(['600010.SH', '600011.SH'], asof=cutoff)
        self.assertEqual(report['stale'], [])
        self.assertEqual(len(report['可入场']), 2)

    def test_holding_from_earlier_day_is_hold(self):
        ticker = '600001.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        entry = frame['date'].iloc[-6]
        latest = frame['date'].iloc[-1]
        self._write_signals(ticker, asof, [
            self._row(entry, 10.0, 'buy', 'final_close'),
            self._row(latest, 10.5, 'sell', 'final_close', 5.0),
        ])
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'], [])
        row = report['持有'][0]
        self.assertEqual(row['ticker'], ticker)
        self.assertEqual(row['entry_date'], entry.strftime('%Y-%m-%d'))
        # 当前价必须取最新行情的收盘价，而不是回测末行成交价
        self.assertAlmostEqual(row['current_price'], float(frame['close'].iloc[-1]), places=6)
        self.assertAlmostEqual(row['profit'], (float(frame['close'].iloc[-1]) - 10.0) / 10.0 * 100, places=6)

    def test_exit_in_cooldown_is_wait(self):
        ticker = '600002.SH'
        frame = _make_frame(240, volume_from=230)
        asof = self._write_indicators(ticker, frame)
        exit_day = frame['date'].iloc[-2]
        self._write_signals(ticker, asof, [
            self._row(frame['date'].iloc[-10], 10.0, 'buy', 'stop_loss'),
            self._row(exit_day, 9.0, 'sell', 'stop_loss', -10.0),
        ])
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'], [])
        self.assertEqual(report['观望'][0]['ticker'], ticker)
        self.assertIn('离场冷却中', report['观望'][0]['detail'])

    def test_trend_confirmed_after_cooldown_is_entry(self):
        ticker = '600003.SH'
        # 末端放量 + MACD 转正 -> 趋势确认成立
        frame = _make_frame(240, volume_from=230)
        frame['MACD_hist'] = 0.1
        asof = self._write_indicators(ticker, frame)
        exit_day = frame['date'].iloc[-10]
        self._write_signals(ticker, asof, [
            self._row(frame['date'].iloc[-20], 10.0, 'buy', 'stop_loss'),
            self._row(exit_day, 9.0, 'sell', 'stop_loss', -10.0),
        ])
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'], [])
        self.assertEqual(report['可入场'][0]['ticker'], ticker)

    def test_flat_without_trend_is_wait(self):
        ticker = '600004.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        # 用引擎真实产出的零交易空结果（带表头），监控要能读到并按趋势未确认给"观望"
        strategy = TrendFollowingStrategy(ticker, mode='simple')
        self.assertTrue(strategy.load_data())
        self.assertEqual(strategy.run_backtest(), [])
        strategy.save_trades_to_csv()
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'], [])
        self.assertEqual(report['观望'][0]['ticker'], ticker)
        self.assertEqual(report['观望'][0]['detail'], '趋势未确认')

    def test_broken_artifact_reported(self):
        ticker = '600009.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        # 完全没有列的空文件：无法解析时要明确报出来，而不是静默跳过
        backtest_artifacts.write_result(
            ticker, 'simple', strategy_params.get_params('simple'), asof,
            pd.DataFrame(), run_id='20260101T000000',
            data_fingerprint=self._indicator_fingerprint(ticker),
            source_manifest=backtest_artifacts.source_manifest(ticker, data_dir=self.data_dir))
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        self.assertIn('无法解析', report['stale'][0]['reason'])

    def test_stale_artifact_reported_not_used(self):
        ticker = '600005.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        # 产物截止日与当前行情不一致，必须报数据过期
        self._write_signals(ticker, '20200101', [
            self._row(frame['date'].iloc[-1], 10.0, 'sell', 'final_close'),
        ])
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        self.assertIn('没有行情截止日', report['stale'][0]['reason'])
        self.assertEqual(report['可入场'] + report['持有'] + report['观望'], [])

    def test_asof_override_mismatch_reported(self):
        ticker = '600006.SH'
        frame = _make_frame(240)
        self._write_indicators(ticker, frame)
        # 要求比实际行情晚的日期时仍必须拒绝，不能降低时效门槛。
        report = self._run_monitor([ticker], asof='20251203')
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        self.assertIn('期望交易日', report['stale'][0]['reason'])

    def test_legacy_artifact_without_meta_reported(self):
        ticker = '600007.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        # 旧命名不带 _meta.json，无法验证参数身份，必须拒绝
        legacy_path = os.path.join(self.data_dir, ticker,
                                   f"{ticker}_backtest_simplified_{asof}.csv")
        pd.DataFrame([self._row(frame['date'].iloc[-1], 10.0, 'sell', 'final_close')]).to_csv(
            legacy_path, index=False, encoding='utf-8-sig')
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        # 产物身份模块统一后的文案是"缺少可用元数据"；两种措辞都表示身份不明必须拒绝
        reason = report['stale'][0]['reason']
        self.assertTrue('元数据' in reason or '元信息' in reason, reason)

    def test_fingerprint_mismatch_reported(self):
        ticker = '600010.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        # 同一行情截止日，但产物记录的行情指纹与当前指标文件不一致：
        # 说明复权基准重建过而回测没重跑，旧结果必须失效
        backtest_artifacts.write_result(
            ticker, 'simple', strategy_params.get_params('simple'), asof,
            pd.DataFrame([self._row(frame['date'].iloc[-1], 10.0, 'sell', 'final_close')]),
            run_id='20260101T000000', data_fingerprint='0123456789abcdef',
            source_manifest=backtest_artifacts.source_manifest(ticker, data_dir=self.data_dir))
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        self.assertIn('指纹', report['stale'][0]['reason'])
        self.assertEqual(report['可入场'] + report['持有'] + report['观望'], [])

    def test_parameter_mismatch_reported(self):
        ticker = '600008.SH'
        frame = _make_frame(240)
        asof = self._write_indicators(ticker, frame)
        params = strategy_params.get_params('simple')
        params['atr_stop_multiplier'] = 2.0
        backtest_artifacts.write_result(
            ticker, 'simple', params, asof,
            pd.DataFrame([self._row(frame['date'].iloc[-1], 10.0, 'sell', 'final_close')]),
            run_id='20260101T000000',
            data_fingerprint=self._indicator_fingerprint(ticker),
            source_manifest=backtest_artifacts.source_manifest(ticker, data_dir=self.data_dir))
        report = self._run_monitor([ticker])
        self.assertEqual(report['stale'][0]['ticker'], ticker)
        self.assertIn('参数', report['stale'][0]['reason'])


if __name__ == '__main__':
    unittest.main()