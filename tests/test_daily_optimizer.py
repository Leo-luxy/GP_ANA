"""日线参数优化器：成交记账、三段门槛与配置写回策略的回归测试（标准库 unittest）。

覆盖：
- 买入按整笔预算扣款导致取整余款凭空消失；
- 胜率/交易次数机械配对原始信号，忽略止损、未成交和期末持仓；
- 期末卖出费用没有进权益曲线，最大回撤从首次交易后权益起算；
- time_stop 只赋值从未执行；
- 默认运行就会改写全局 config.py，且没有备份；
- 三段切分（训练/验证/测试）不重叠且顺序正确；
- 门槛要求验证段与测试段同时为正，且测试段收益不明显劣于验证段；
- --apply-best 拒绝未通过候选，只有 --force-apply 才写并打印不可外推警告。
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import daily.strategy_optimization as daily_opt  # noqa: E402
from daily.strategy_optimization import (  # noqa: E402
    DEFAULT_TEST_RATIO,
    DEFAULT_TEST_RETURN_TOLERANCE_PCT,
    DEFAULT_TRAIN_RATIO,
    DEFAULT_VAL_RATIO,
    EXIT_REASON_FINAL,
    EXIT_REASON_STOP_LOSS,
    EXIT_REASON_TIME_STOP,
    StrategyOptimizer,
    apply_best_to_config,
    candidate_passed,
    evaluate_gate,
    split_three_way,
    validate_split_ratios,
)


def make_optimizer(initial_capital=None):
    """构造一个只用于内存回测的优化器实例。"""
    optimizer = StrategyOptimizer('600000.SH_dummy.csv')
    if initial_capital is not None:
        optimizer.initial_capital = float(initial_capital)
    return optimizer


def signal_frame(rows):
    """把 (date, close, buy_signal, sell_signal) 元组列表转成信号表。"""
    normalized = []
    for row in rows:
        date = row[0]
        close = row[1]
        buy = row[2] if len(row) > 2 else 0
        sell = row[3] if len(row) > 3 else 0
        normalized.append((date, close, buy, sell))
    return pd.DataFrame(normalized, columns=['date', 'close', 'buy_signal', 'sell_signal'])


def synthetic_indicator_frame(periods=80, ticker='600000.SH'):
    """构造带布林带/均线/RSI 的合成指标数据，用于走通信号计算流程。"""
    index = np.arange(periods)
    close = 10.0 + 1.5 * np.sin(index / 5.0) + index * 0.01
    dates = pd.date_range('2024-01-01', periods=periods, freq='D')
    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'ticker': ticker,
        'close': close,
        'BB_lower': close * 1.02,
        'BB_upper': close * 0.98,
        'MA5': close,
        'MA20': close,
        'RSI': np.where(index % 10 < 5, 20.0, 80.0),
    })


def rising_trend_indicator_frame(periods=45, ticker='600000.SH'):
    """构造单边上涨且买入信号恒真的合成数据，用于验证“通过门槛”的写入路径。

    布林下轨恒高于收盘价 → 每个交易日都触发买入信号；
    布林上轨恒高于收盘价 → 不会触发卖出信号；均线相等 → 无交叉信号。
    """
    index = np.arange(periods)
    daily_returns = 0.012 + 0.008 * np.sin(index)
    close = 10.0 * np.cumprod(1.0 + daily_returns)
    dates = pd.date_range('2024-01-01', periods=periods, freq='D')
    return pd.DataFrame({
        'date': dates.strftime('%Y-%m-%d'),
        'ticker': ticker,
        'close': close,
        'BB_lower': close * 1.6,
        'BB_upper': close * 2.0,
        'MA5': close,
        'MA20': close,
        'RSI': 50.0,
    })


CONFIG_STUB = '''# 测试用配置文件桩
STRATEGY_CONFIG = {
    'initial_capital': 100000.0,  # 初始资金
    'rsi_buy_threshold': 25,  # RSI买入阈值
    'rsi_sell_threshold': 65,  # RSI卖出阈值
    'bb_buy_mult': 1.01,  # 布林带买入倍数
    'bb_sell_mult': 1.01,  # 布林带卖出倍数
}

OTHER_CONFIG = {'keep': 1}
'''


class TestCashAccounting(unittest.TestCase):
    def test_int_lot_remainder_not_lost(self):
        """恒价 7 元、30% 仓位：买 42 股只扣 294 元成本，取整余款留在现金里。"""
        optimizer = make_optimizer(initial_capital=1000.0)
        df = signal_frame([
            ('2024-01-01', 7.0, 1, 0),
            ('2024-01-02', 7.0, 0, 1),
        ])
        metrics = optimizer.backtest_strategy(df)

        buy_fill = metrics['trade_ledger'][0]
        self.assertEqual(buy_fill['side'], 'buy')
        self.assertEqual(buy_fill['shares'], 42)
        self.assertAlmostEqual(buy_fill['amount'], 294.0, places=6)
        self.assertAlmostEqual(buy_fill['fee'], 0.294, places=6)
        self.assertAlmostEqual(buy_fill['cash_after'], 1000.0 - 294.0 - 0.294, places=6)

        # 42 股 × 7 元买卖共两笔成交，期末再清算剩余 30 股，费用合计 0.588 元
        self.assertAlmostEqual(metrics['fees_total'], 0.588, places=6)
        self.assertAlmostEqual(metrics['final_value'], 999.412, places=2)
        self.assertAlmostEqual(metrics['final_value'], 1000.0 - metrics['fees_total'], places=6)
        self.assertAlmostEqual(metrics['equity_curve'][-1], metrics['final_value'], places=6)
        # 旧实现把整笔 300 元预算从现金里扣掉，终值只有 993.406，凭空少 6.006 元
        self.assertGreater(metrics['final_value'], 999.40)

    def test_ledger_has_required_fields(self):
        optimizer = make_optimizer(initial_capital=1000.0)
        df = signal_frame([
            ('2024-01-01', 7.0, 1, 0),
            ('2024-01-02', 7.0, 0, 1),
        ])
        metrics = optimizer.backtest_strategy(df)
        required = {'date', 'side', 'price', 'shares', 'amount', 'fee', 'cash_after', 'reason'}
        for fill in metrics['trade_ledger']:
            self.assertTrue(required.issubset(set(fill.keys())))
        self.assertEqual([fill['reason'] for fill in metrics['trade_ledger']],
                         ['买入信号', '卖出信号', EXIT_REASON_FINAL])


class TestTradeStatistics(unittest.TestCase):
    def test_stop_loss_not_counted_as_winning_trade(self):
        """买入后触发止损、之后再出现卖信号：胜率不能是 100%，笔数按真实成交算。"""
        optimizer = make_optimizer()
        df = signal_frame([
            ('2024-01-01', 100.0, 1, 0),
            ('2024-01-02', 85.0, 0, 0),
            ('2024-01-03', 110.0, 0, 1),
        ])
        metrics = optimizer.backtest_strategy(df)

        self.assertEqual(metrics['buy_fills'], 1)
        self.assertEqual(metrics['sell_fills'], 1)
        self.assertEqual(metrics['total_trades'], 1)
        self.assertEqual(metrics['win_rate'], 0.0)
        self.assertEqual(metrics['closed_trades'][0]['exit_reason'], EXIT_REASON_STOP_LOSS)
        self.assertLess(metrics['realized_pnl'], 0)
        self.assertAlmostEqual(metrics['total_return'], -4.5555, places=2)

    def test_extra_buy_signals_not_counted_as_filled(self):
        """连续买信号超过最大批次：没成交的信号不能计入交易次数。"""
        optimizer = make_optimizer()
        rows = [
            ('2024-01-01', 10.0, 1, 0),
            ('2024-01-02', 10.0, 1, 0),
            ('2024-01-03', 10.0, 1, 0),
            ('2024-01-04', 10.0, 1, 0),
            ('2024-01-05', 10.0, 0, 1),
        ]
        metrics = optimizer.backtest_strategy(signal_frame(rows))

        # 4 个买信号里只有 3 个真正成交（最大持仓 3 批），旧实现会按信号配对报 4 次交易
        self.assertEqual(metrics['buy_fills'], 3)
        self.assertEqual(metrics['total_trades'], 3)
        self.assertEqual(len(metrics['closed_trades']), 3)
        self.assertEqual(metrics['buy_fills'], sum(1 for fill in metrics['trade_ledger']
                                                   if fill['side'] == 'buy'))


class TestEquityAndDrawdown(unittest.TestCase):
    def test_final_fee_in_equity_and_drawdown_from_initial(self):
        """权益曲线必须包含期末清算费用，最大回撤从初始资金起算。"""
        optimizer = make_optimizer()
        df = signal_frame([
            ('2024-01-01', 100.0, 1, 0),
            ('2024-01-02', 110.0, 0, 0),
            ('2024-01-03', 110.0, 0, 0),
        ])
        metrics = optimizer.backtest_strategy(df)
        curve = metrics['equity_curve']

        self.assertEqual(len(curve), len(df) + 1)
        self.assertAlmostEqual(curve[0], 100000.0, places=6)
        self.assertAlmostEqual(metrics['final_value'], 102937.0, places=6)
        # 曲线最后一点是期末清算后的现金，旧实现停在 102970，33 元费用没有进曲线
        self.assertAlmostEqual(curve[-1], metrics['final_value'], places=6)
        self.assertNotAlmostEqual(curve[-1], 102970.0, places=2)

        expected_drawdown = 33.0 / 102970.0
        self.assertAlmostEqual(metrics['max_drawdown'], expected_drawdown, places=9)
        self.assertGreater(metrics['max_drawdown'], 0.0)

        self.assertEqual(metrics['terminal_trade_count'], 1)
        self.assertAlmostEqual(metrics['open_position_unrealized_pnl'], 2970.0, places=6)
        self.assertAlmostEqual(metrics['realized_pnl'], 2937.0, places=6)


class TestTimeStop(unittest.TestCase):
    def test_time_stop_triggers_exit(self):
        """持仓超过 30 个交易日必须真正离场，而不是只在代码里算一下。"""
        optimizer = make_optimizer()
        rows = [('2024-01-01', 100.0, 1, 0)]
        for stamp in pd.date_range('2024-01-02', periods=35, freq='D'):
            rows.append((stamp.strftime('%Y-%m-%d'), 101.0, 0, 0))
        metrics = optimizer.backtest_strategy(signal_frame(rows))

        self.assertEqual(metrics['total_trades'], 1)
        trade = metrics['closed_trades'][0]
        self.assertEqual(trade['exit_reason'], EXIT_REASON_TIME_STOP)
        # 第 0 行买入，第 31 行触发（i - buy_index > 30）
        self.assertEqual(trade['holding_days'], 31)
        sells = [fill for fill in metrics['trade_ledger'] if fill['side'] == 'sell']
        self.assertEqual(len(sells), 1)
        self.assertEqual(sells[0]['reason'], EXIT_REASON_TIME_STOP)
        self.assertNotIn(EXIT_REASON_FINAL, metrics['exit_reasons'])
        self.assertAlmostEqual(metrics['final_value'], 100239.7, places=2)


class TestThreeWaySplit(unittest.TestCase):
    """训练/验证/测试三段切分：比例、顺序与互不重叠。"""

    @staticmethod
    def date_frame(periods):
        return pd.DataFrame({
            'date': pd.date_range('2024-01-01', periods=periods, freq='D').strftime('%Y-%m-%d'),
            'close': np.linspace(10.0, 20.0, periods),
        })

    def test_default_bounds_are_60_20_20_and_ordered(self):
        frame = self.date_frame(100)
        train, val, test = split_three_way(frame)

        self.assertEqual((len(train), len(val), len(test)), (60, 20, 20))
        # 三段按时间顺序首尾相接：训练段最后一日 < 验证段首日 < 测试段首日
        self.assertLess(train['date'].iloc[-1], val['date'].iloc[0])
        self.assertLess(val['date'].iloc[-1], test['date'].iloc[0])

        # 三段索引互不重叠，并集恰好覆盖全部原始行
        index_sets = [set(part.index) for part in (train, val, test)]
        for left in range(3):
            for right in range(left + 1, 3):
                self.assertEqual(len(index_sets[left] & index_sets[right]), 0)
        self.assertEqual(len(index_sets[0] | index_sets[1] | index_sets[2]), len(frame))

    def test_custom_ratios_respected(self):
        frame = self.date_frame(100)
        train, val, test = split_three_way(frame, train_ratio=0.5, val_ratio=0.25,
                                           test_ratio=0.25)
        self.assertEqual((len(train), len(val), len(test)), (50, 25, 25))
        self.assertLess(train['date'].iloc[-1], val['date'].iloc[0])
        self.assertLess(val['date'].iloc[-1], test['date'].iloc[0])

    def test_rounding_remainder_goes_to_test_segment(self):
        frame = self.date_frame(7)
        train, val, test = split_three_way(frame)
        # 7 行按 60/20/20 取整后为 4/1/2，剩余行归测试段
        self.assertEqual((len(train), len(val), len(test)), (4, 1, 2))

    def test_invalid_ratios_rejected(self):
        frame = self.date_frame(100)
        # 比例之和不为 1
        with self.assertRaises(ValueError):
            split_three_way(frame, train_ratio=0.7, val_ratio=0.2, test_ratio=0.2)
        # 单段比例越界
        with self.assertRaises(ValueError):
            split_three_way(frame, train_ratio=0.0, val_ratio=0.5, test_ratio=0.5)
        with self.assertRaises(ValueError):
            validate_split_ratios(0.6, 0.2, 0.1)
        # 样本不足 3 行
        with self.assertRaises(ValueError):
            split_three_way(self.date_frame(2))

    def test_default_ratios_are_the_expected_constants(self):
        self.assertAlmostEqual(DEFAULT_TRAIN_RATIO, 0.6)
        self.assertAlmostEqual(DEFAULT_VAL_RATIO, 0.2)
        self.assertAlmostEqual(DEFAULT_TEST_RATIO, 0.2)


class TestCandidateGate(unittest.TestCase):
    """候选门槛：验证段与测试段同时为正，且测试段不明显劣于验证段。"""

    def test_requires_non_negative_val_and_test(self):
        val_ok = {'total_return': 5.0, 'sharpe_ratio': 1.0}
        self.assertTrue(candidate_passed(val_ok, {'total_return': 3.0, 'sharpe_ratio': 0.5}))
        # 测试段为负不能通过
        self.assertFalse(candidate_passed(val_ok, {'total_return': -0.01, 'sharpe_ratio': 5.0}))
        # 默认门槛为 0：恰好 0 收益属于“非负”，收益条件本身不卡
        self.assertTrue(candidate_passed({'total_return': 0.0, 'sharpe_ratio': 1.0},
                                         {'total_return': 0.0, 'sharpe_ratio': 0.5}))
        # 零交易候选收益 0、夏普 0，仍会被夏普门槛挡住
        self.assertFalse(candidate_passed({'total_return': 0.0, 'sharpe_ratio': 0.0},
                                          {'total_return': 0.0, 'sharpe_ratio': 0.0}))
        # 验证段夏普为零不能通过
        self.assertFalse(candidate_passed({'total_return': 5.0, 'sharpe_ratio': 0.0},
                                          {'total_return': 3.0, 'sharpe_ratio': 1.0}))

    def test_test_return_tolerance(self):
        val_ok = {'total_return': 5.0, 'sharpe_ratio': 1.0}
        tolerance = DEFAULT_TEST_RETURN_TOLERANCE_PCT
        # 恰好等于容差边界：允许通过
        self.assertTrue(candidate_passed(
            val_ok, {'total_return': 5.0 - tolerance, 'sharpe_ratio': 0.5}))
        # 比容差再多低 0.01 个百分点：拒绝
        self.assertFalse(candidate_passed(
            val_ok, {'total_return': 5.0 - tolerance - 0.01, 'sharpe_ratio': 0.5}))

    def test_gate_reason_reports_failed_condition(self):
        val_ok = {'total_return': 5.0, 'sharpe_ratio': 1.0}
        passed, reason = evaluate_gate(val_ok, {'total_return': 1.0, 'sharpe_ratio': 0.5})
        self.assertFalse(passed)
        self.assertIn('容差', reason)

        passed, reason = evaluate_gate(val_ok, {'total_return': -1.0, 'sharpe_ratio': 0.5})
        self.assertFalse(passed)
        self.assertIn('测试段收益', reason)

        passed, reason = evaluate_gate(val_ok, {'total_return': 5.0, 'sharpe_ratio': 0.5})
        self.assertTrue(passed)
        self.assertEqual(reason, '通过')


class TestConfigWritePolicy(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = self.tmp.name
        self.ticker = '600000.SH'
        self.data_dir = os.path.join(root, 'data')
        stock_dir = os.path.join(self.data_dir, self.ticker)
        os.makedirs(stock_dir)
        self.indicators_path = os.path.join(stock_dir, f'{self.ticker}_indicators.csv')
        synthetic_indicator_frame(ticker=self.ticker).to_csv(
            self.indicators_path, index=False, encoding='utf-8-sig')
        self.config_path = os.path.join(root, 'config.py')
        with open(self.config_path, 'w', encoding='utf-8') as fh:
            fh.write(CONFIG_STUB)
        self.output_path = os.path.join(root, 'out', 'optimization_candidates.csv')
        self.backup_dir = os.path.join(root, 'backup')
        self._old_data_dir = daily_opt.DATA_DIR
        daily_opt.DATA_DIR = self.data_dir
        self.addCleanup(self._restore_data_dir)

    def _restore_data_dir(self):
        daily_opt.DATA_DIR = self._old_data_dir

    def _read_config(self):
        with open(self.config_path, 'r', encoding='utf-8') as fh:
            return fh.read()

    def _read_config_bytes(self):
        with open(self.config_path, 'rb') as fh:
            return fh.read()

    def _run_cli(self, extra_args):
        stdout = io.StringIO()
        argv = ['--ticker', self.ticker, '--output', self.output_path,
                '--config', self.config_path, '--backup-dir', self.backup_dir] + list(extra_args)
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stdout):
            code = daily_opt.main(argv)
        return code, stdout.getvalue()

    def test_default_run_only_writes_candidates(self):
        before = self._read_config()
        code, log = self._run_cli([])

        self.assertEqual(code, 0)
        self.assertEqual(self._read_config(), before)
        self.assertFalse(os.path.exists(self.backup_dir))
        self.assertIn('未写 config.py', log)
        self.assertTrue(os.path.exists(self.output_path))

        candidates = pd.read_csv(self.output_path, encoding='utf-8-sig')
        self.assertEqual(len(candidates), 81)
        for column in ('ticker', 'rsi_buy_threshold', 'rsi_sell_threshold',
                       'bb_buy_mult', 'bb_sell_mult',
                       'train_total_return', 'train_sharpe_ratio', 'train_max_drawdown',
                       'train_win_rate', 'train_total_trades',
                       'val_total_return', 'val_sharpe_ratio', 'val_max_drawdown',
                       'val_win_rate', 'val_total_trades',
                       'test_total_return', 'test_sharpe_ratio', 'test_max_drawdown',
                       'test_win_rate', 'test_total_trades',
                       'test_return_gap', 'validation_score', 'passed', 'gate_reason'):
            self.assertIn(column, candidates.columns)
        # 兼容旧调用方：顶层指标等于验证段口径
        best = candidates.loc[candidates['validation_score'].idxmax()]
        self.assertAlmostEqual(best['sharpe_ratio'], best['val_sharpe_ratio'])
        self.assertAlmostEqual(best['total_return'], best['val_total_return'])
        # 测试段差值列的口径：test - val
        self.assertAlmostEqual(best['test_return_gap'],
                               best['test_total_return'] - best['val_total_return'], places=6)

    def test_apply_best_rejects_unpassed_candidate(self):
        """未通过门槛：--apply-best 必须拒绝写入，原 config 字节不变、不产生备份。"""
        before = self._read_config_bytes()
        code, log = self._run_cli(['--apply-best'])

        self.assertEqual(code, 1)
        self.assertEqual(self._read_config_bytes(), before)
        self.assertFalse(os.path.exists(self.backup_dir))
        self.assertIn('拒绝写入', log)
        self.assertNotIn('未通过门槛，仅因强制写入，不可外推', log)
        # 候选表仍然照常输出
        self.assertTrue(os.path.exists(self.output_path))
        candidates = pd.read_csv(self.output_path, encoding='utf-8-sig')
        self.assertFalse(bool(candidates['passed'].any()))

    def test_force_apply_writes_unpassed_candidate_with_warning(self):
        """--force-apply 才允许写未通过候选，写前照样备份，并打印不可外推警告。"""
        before = self._read_config_bytes()
        code, log = self._run_cli(['--apply-best', '--force-apply'])
        after = self._read_config_bytes()

        self.assertEqual(code, 0)
        self.assertNotEqual(after, before)
        compile(after.decode('utf-8'), self.config_path, 'exec')
        self.assertIn('未通过门槛，仅因强制写入，不可外推', log)
        self.assertIn('原配置已备份', log)

        backups = sorted(os.listdir(self.backup_dir))
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.backup_dir, backups[0]), 'rb') as fh:
            self.assertEqual(fh.read(), before)

        candidates = pd.read_csv(self.output_path, encoding='utf-8-sig')
        self.assertFalse(bool(candidates['passed'].any()))

    def test_apply_best_writes_passed_candidate(self):
        """通过验证段与测试段门槛的候选可以正常写入，并生成备份。"""
        rising_trend_indicator_frame(ticker=self.ticker).to_csv(
            self.indicators_path, index=False, encoding='utf-8-sig')
        before = self._read_config_bytes()
        code, log = self._run_cli(['--apply-best'])
        after = self._read_config_bytes()

        self.assertEqual(code, 0)
        self.assertNotEqual(after, before)
        after_text = after.decode('utf-8')
        compile(after_text, self.config_path, 'exec')
        self.assertNotIn('未通过门槛，仅因强制写入，不可外推', log)
        self.assertIn("'initial_capital': 100000.0", after_text)
        self.assertIn("OTHER_CONFIG = {'keep': 1}", after_text)

        backups = sorted(os.listdir(self.backup_dir))
        self.assertEqual(len(backups), 1)
        with open(os.path.join(self.backup_dir, backups[0]), 'rb') as fh:
            self.assertEqual(fh.read(), before)

        candidates = pd.read_csv(self.output_path, encoding='utf-8-sig')
        self.assertTrue(bool(candidates['passed'].any()))
        chosen = candidates.loc[candidates['validation_score'].idxmax()]
        self.assertIn("'rsi_buy_threshold': %d" % int(chosen['rsi_buy_threshold']), after_text)
        self.assertIn("'rsi_sell_threshold': %d" % int(chosen['rsi_sell_threshold']), after_text)
        self.assertIn("'bb_buy_mult': %g" % float(chosen['bb_buy_mult']), after_text)

    def test_invalid_ratio_sum_aborts_without_touching_config(self):
        before = self._read_config_bytes()
        with self.assertRaises(SystemExit):
            self._run_cli(['--train-ratio', '0.7', '--val-ratio', '0.2',
                           '--test-ratio', '0.2'])
        self.assertEqual(self._read_config_bytes(), before)
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_apply_best_missing_param_does_not_touch_file(self):
        bad_path = os.path.join(self.tmp.name, 'bad_config.py')
        content = '''STRATEGY_CONFIG = {
    'initial_capital': 1.0,
    'rsi_buy_threshold': 25,
    'rsi_sell_threshold': 65,
    'bb_buy_mult': 1.01,
}
'''
        with open(bad_path, 'w', encoding='utf-8') as fh:
            fh.write(content)
        with self.assertRaises(RuntimeError):
            apply_best_to_config({'rsi_buy_threshold': 30, 'rsi_sell_threshold': 70,
                                  'bb_buy_mult': 1.0, 'bb_sell_mult': 1.0},
                                 config_path=bad_path, backup_dir=self.backup_dir)
        with open(bad_path, 'r', encoding='utf-8') as fh:
            self.assertEqual(fh.read(), content)
        self.assertFalse(os.path.exists(self.backup_dir))


class TestIsolationAcceptance(unittest.TestCase):
    setUp = TestConfigWritePolicy.setUp
    _restore_data_dir = TestConfigWritePolicy._restore_data_dir
    _read_config_bytes = TestConfigWritePolicy._read_config_bytes
    _run_cli = TestConfigWritePolicy._run_cli

    @staticmethod
    def candidate(**changes):
        row = dict(rsi_buy_threshold=30, rsi_sell_threshold=70,
                   bb_buy_mult=1.0, bb_sell_mult=1.0, validation_score=2.0,
                   val_total_return=3.0, val_sharpe_ratio=2.0,
                   test_total_return=3.0, test_sharpe_ratio=1.0, passed=True)
        row.update(changes)
        return row

    def test_only_contiguous_indicator_warmup_prefix_is_trimmed(self):
        frame = synthetic_indicator_frame(periods=40)
        for key, count in (('MA5', 4), ('MA20', 19), ('RSI', 14),
                           ('BB_lower', 19), ('BB_upper', 19)):
            frame.loc[:count - 1, key] = np.nan
        frame.to_csv(self.indicators_path, index=False)
        optimizer = StrategyOptimizer(self.indicators_path)
        with contextlib.redirect_stdout(io.StringIO()):
            result = optimizer.load_data()
        self.assertEqual(optimizer.warmup_trim_rows, 19)
        self.assertEqual(result.attrs['warmup_trim_rows'], 19)
        self.assertEqual(len(result), 21)
        pd.testing.assert_series_equal(result['close'], frame['close'].iloc[19:].reset_index(drop=True))
        for row, key, value in ((30, 'RSI', np.nan), (39, 'MA20', np.nan),
                                (0, 'close', np.nan), (0, 'close', 0),
                                (0, 'RSI', np.inf)):
            broken = frame.copy()
            broken.loc[row, key] = value
            broken.to_csv(self.indicators_path, index=False)
            with self.subTest(row=row, key=key, value=value):
                with self.assertRaisesRegex(ValueError, '加载数据失败'):
                    optimizer.load_data()
                self.assertIsNone(optimizer.data)

    def test_low_level_gate_reuses_exact_evaluation_settings(self):
        from unittest.mock import patch
        optimizer = StrategyOptimizer(self.indicators_path)
        optimizer.load_data()
        row = self.candidate()
        settings = dict(min_val_return=-1, min_val_sharpe=0.1,
                        min_test_return=-1, test_return_tolerance=0.2)
        with patch.object(optimizer, 'backtest_strategy', return_value={
                'total_return': -0.5, 'sharpe_ratio': 0.5}):
            optimizer.evaluate_selected(row, **settings)
        self.assertEqual(row['gate_settings'], settings)
        self.assertTrue(row['passed'])
        self.assertTrue(daily_opt.application_passed(row))
        backup = apply_best_to_config(row, config_path=self.config_path,
                                      backup_dir=self.backup_dir)
        self.assertTrue(os.path.exists(backup))
        # 不能把一个较严门槛未通过的候选伪标成 passed 后绕过底层。
        row['gate_settings']['min_test_return'] = 10
        row['passed'] = True
        self.assertFalse(daily_opt.application_passed(row))
        with self.assertRaises(RuntimeError):
            optimizer.update_config(row, config_path=self.config_path,
                                    backup_dir=self.backup_dir)
        row['gate_settings'] = {'min_test_return': -1}
        self.assertFalse(daily_opt.application_passed(row))

    def test_nan_inf_and_missing_gate_inputs_are_rejected(self):
        for field in ('val_total_return', 'val_sharpe_ratio', 'test_total_return',
                      'test_sharpe_ratio'):
            for value in (float('nan'), float('inf'), -float('inf'), None):
                with self.subTest(field=field, value=value):
                    row = self.candidate(**{field: value})
                    self.assertFalse(daily_opt.application_passed(row))
        for val, test in (({}, {'total_return': 0}),
                          ({'total_return': 1, 'sharpe_ratio': 1}, {})):
            self.assertFalse(evaluate_gate(val, test)[0])
        for key in ('min_val_return', 'min_val_sharpe', 'min_test_return',
                    'test_return_tolerance'):
            self.assertFalse(evaluate_gate({'total_return': 1, 'sharpe_ratio': 1},
                                           {'total_return': 1}, **{key: float('nan')})[0])

    def test_low_level_writers_share_gate_and_do_not_create_backup_on_rejection(self):
        before = self._read_config_bytes()
        optimizer = make_optimizer()
        for flag in (False, None, 'False', 'True', 1, float('nan')):
            for writer in (apply_best_to_config, optimizer.update_config):
                with self.subTest(flag=flag, writer=writer):
                    with self.assertRaises(RuntimeError):
                        writer(self.candidate(passed=flag), config_path=self.config_path,
                               backup_dir=self.backup_dir)
        with self.assertRaises(RuntimeError):
            apply_best_to_config(self.candidate(test_total_return=-1),
                                 config_path=self.config_path, backup_dir=self.backup_dir)
        self.assertEqual(self._read_config_bytes(), before)
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_force_is_explicit_and_backup_is_exact(self):
        before = self._read_config_bytes()
        with self.assertRaises(RuntimeError):
            apply_best_to_config(self.candidate(passed=False), config_path=self.config_path,
                                 backup_dir=self.backup_dir, force_apply='yes')
        log = io.StringIO()
        with contextlib.redirect_stdout(log):
            backup = make_optimizer().update_config(
                self.candidate(passed=False), config_path=self.config_path,
                backup_dir=self.backup_dir, force_apply=True)
        with open(backup, 'rb') as fh:
            self.assertEqual(fh.read(), before)
        self.assertIn('不可外推', log.getvalue())
        with self.assertRaises(ValueError):
            apply_best_to_config(self.candidate(bb_buy_mult=float('nan')),
                                 config_path=self.config_path, backup_dir=self.backup_dir,
                                 force_apply=True)

    def test_aggregate_never_uses_test_results_to_change_params(self):
        rows = [self.candidate(ticker='A', passed=False, validation_score=3),
                self.candidate(ticker='B', passed=False, validation_score=2),
                self.candidate(ticker='C', rsi_buy_threshold=40, passed=True,
                               validation_score=100)]
        chosen = daily_opt.aggregate_best_params(rows)
        self.assertEqual(chosen['rsi_buy_threshold'], 30)
        for row in rows:
            row['passed'] = not row['passed']
            row['test_total_return'] = -999 if row['passed'] else 999
        flipped = daily_opt.aggregate_best_params(rows)
        self.assertEqual(flipped['rsi_buy_threshold'], 30)
        self.assertEqual(chosen['ticker'], flipped['ticker'])

    def test_only_frozen_candidate_reaches_test_even_when_it_raises(self):
        from unittest.mock import patch
        optimizer = StrategyOptimizer(self.indicators_path)
        original = optimizer.backtest_strategy
        test_calls = []
        active = []
        calculate = optimizer.calculate_signals
        def signal(*args):
            active[:] = args
            return calculate(*args)
        def backtest(frame):
            if frame.index.min() >= 64:
                test_calls.append(active[0])
                raise RuntimeError('测试坏了，不得回流改选')
            result = original(frame)
            result['sharpe_ratio'] = 3 if active[0] == 30 else 1
            return result
        with patch.object(optimizer, 'calculate_signals', side_effect=signal), \
             patch.object(optimizer, 'backtest_strategy', side_effect=backtest), \
             contextlib.redirect_stdout(io.StringIO()):
            best, rows = optimizer.optimize_parameters(
                rsi_buy_thresholds=[30, 40], rsi_sell_thresholds=[70],
                bb_buy_mults=[1], bb_sell_mults=[1])
        self.assertEqual(best['rsi_buy_threshold'], 30)
        self.assertFalse(best['passed'])
        self.assertEqual(test_calls, [30])
        self.assertEqual(len(rows), 2)

    def test_multistock_cli_freezes_before_testing_and_never_falls_back(self):
        from unittest.mock import patch
        import config
        tickers = ['600001.SH', '600002.SH', '600003.SH']
        for ticker in tickers:
            directory = os.path.join(self.data_dir, ticker)
            os.makedirs(directory)
            synthetic_indicator_frame(ticker=ticker).to_csv(
                os.path.join(directory, ticker + '_indicators.csv'), index=False)
        events = []
        def optimize(optimizer, **kwargs):
            self.assertIs(kwargs['evaluate_test'], False)
            optimizer.load_data()
            events.append(('validate', optimizer.ticker))
            row = self.candidate(ticker=optimizer.ticker,
                                 rsi_buy_threshold=40 if optimizer.ticker == tickers[2] else 30,
                                 passed=optimizer.ticker == tickers[2])
            return row, [row]
        def evaluate(optimizer, row, *args, **kwargs):
            events.append(('test', row['rsi_buy_threshold']))
            row.update(self.candidate(rsi_buy_threshold=row['rsi_buy_threshold'],
                                      passed=False, test_total_return=-100))
            return row
        before = self._read_config_bytes()
        with patch.dict(config.STOCK_TICKERS, dict(zip(tickers, tickers)), clear=True), \
             patch.object(StrategyOptimizer, 'optimize_parameters', optimize), \
             patch.object(StrategyOptimizer, 'evaluate_selected', evaluate), \
             contextlib.redirect_stdout(io.StringIO()):
            code = daily_opt.main(['--apply-best', '--config', self.config_path,
                                   '--backup-dir', self.backup_dir, '--output', self.output_path])
        self.assertEqual(code, 1)
        self.assertEqual(events[:3], [('validate', ticker) for ticker in tickers])
        self.assertEqual(events[3:], [('test', 30)] * 3)
        self.assertEqual(self._read_config_bytes(), before)
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_partial_missing_input_cli_returns_failure_without_apply(self):
        from unittest.mock import patch
        import config
        with patch.dict(config.STOCK_TICKERS, {'a': self.ticker, 'b': 'missing'}, clear=True), \
             contextlib.redirect_stdout(io.StringIO()):
            code = daily_opt.main(['--config', self.config_path, '--output', self.output_path])
        self.assertEqual(code, 1)
        self.assertTrue(os.path.exists(self.output_path))
        self.assertFalse(os.path.exists(self.backup_dir))

    def test_load_failure_never_returns_synthetic_data_and_cli_fails(self):
        optimizer = StrategyOptimizer(os.path.join(self.tmp.name, 'missing.csv'))
        with self.assertRaisesRegex(ValueError, '加载数据失败'):
            optimizer.load_data()
        self.assertIsNone(optimizer.data)
        with open(self.indicators_path, 'w', encoding='utf-8') as fh:
            fh.write('not,valid\n1,2\n')
        before = self._read_config_bytes()
        code, log = self._run_cli(['--apply-best', '--force-apply'])
        self.assertEqual(code, 1)
        self.assertIn('跳过', log)
        self.assertEqual(self._read_config_bytes(), before)
        self.assertFalse(os.path.exists(self.backup_dir))


if __name__ == '__main__':
    unittest.main()
