"""整批统一日期：真实快照+真实子进程计算，所有文件限定临时目录。"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from datetime import datetime
from unittest import mock

import pandas as pd
import selection_snapshot as snapshot
import stocks_filter.batch_backtest_filter as bf
from tests.test_engines import _make_frame


class UniformSelectionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.tickers = ['600000.SH', '600001.SH']
        clock = mock.patch.object(snapshot, 'datetime', wraps=datetime)
        self.clock = clock.start()
        self.addCleanup(clock.stop)
        self.clock.now.return_value = datetime(2026, 11, 13, 19, 0)
        self.today = '20261113'
        self.previous = snapshot.previous_trade_asof(self.today)
        self.frame = _make_frame(260)
        self.frame['date'] = pd.bdate_range(end=self.today, periods=len(self.frame))

    def write_market(self, ticker, current=True):
        path = os.path.join(self.root, ticker)
        os.makedirs(path, exist_ok=True)
        data = self.frame if current else self.frame[self.frame['date'] <= pd.Timestamp(self.previous)]
        data[list(bf.backtest_artifacts.MARKET_COLUMNS)].to_csv(
            os.path.join(path, f'{ticker}_qfq.csv'), index=False)

    def test_partial_today_freezes_yesterday_and_does_not_touch_originals(self):
        self.write_market(self.tickers[0])
        self.write_market(self.tickers[1], False)
        chosen, missing = snapshot.choose_batch_asof(self.tickers, self.root, self.today)
        self.assertEqual(chosen, self.previous)
        self.assertEqual(missing, [self.tickers[1]])
        before = {t: bf.file_hash(os.path.join(self.root, t, f'{t}_qfq.csv')) for t in self.tickers}
        output = os.path.join(self.root, 'snapshot')
        snapshot.build_snapshot(self.tickers, self.root, output, chosen)
        for t in self.tickers:
            data = pd.read_csv(os.path.join(output, t, f'{t}_qfq.csv'))
            self.assertEqual(pd.Timestamp(data.iloc[-1]['date']).strftime('%Y%m%d'), chosen)
            self.assertEqual(bf.file_hash(os.path.join(self.root, t, f'{t}_qfq.csv')), before[t])

    def test_all_today_uses_today(self):
        for t in self.tickers:
            self.write_market(t)
        self.assertEqual(snapshot.choose_batch_asof(self.tickers, self.root, self.today), (self.today, []))

    def test_missing_previous_day_refuses_to_mix_or_fall_back_further(self):
        self.write_market(self.tickers[0])
        self.write_market(self.tickers[1], False)
        path = os.path.join(self.root, self.tickers[1], f'{self.tickers[1]}_qfq.csv')
        data = pd.read_csv(path).iloc[:-3]
        data.to_csv(path, index=False)
        with self.assertRaisesRegex(snapshot.SelectionSnapshotError, '禁止混合日期'):
            snapshot.choose_batch_asof(self.tickers, self.root, self.today)

    def test_fallback_rebuilds_preliminary_pool_for_same_day(self):
        for t, current in zip(self.tickers, [True, False]):
            self.write_market(t, current)
        candidate = os.path.join(self.root, 'stocks_daily_filtered.csv')
        pd.DataFrame({'股票代码': self.tickers, '交易日期': self.today}).to_csv(candidate, index=False)
        commands = []
        def command(cmd, description):
            commands.append(cmd)
            if 'step3_filter.py' in cmd:
                pd.DataFrame({'股票代码': self.tickers, '交易日期': self.previous}).to_csv(candidate, index=False)
            return 0
        with mock.patch.object(bf, 'DATA_DIR', self.root), \
             mock.patch.object(bf, 'CURRENT_DIR', self.root), \
             mock.patch.object(bf, 'run_command_status', side_effect=command):
            plan = bf.prepare_batch(self.tickers, candidate, self.today, True, 'rebuild-test')
        self.assertEqual(plan['data_asof'], self.previous)
        self.assertEqual(len(commands), 3)
        self.assertIn('--trade-date ' + self.previous, commands[0])
        self.assertEqual(set(pd.read_csv(candidate)['交易日期'].astype(str)), {self.previous})

    def test_rebuilt_today_pool_adds_missing_stock_and_reverts_whole_pool(self):
        self.write_market(self.tickers[0], True)
        self.write_market(self.tickers[1], False)
        candidate = os.path.join(self.root, 'stocks_daily_filtered.csv')
        pd.DataFrame({'股票代码': [self.tickers[0]], '交易日期': self.previous}).to_csv(candidate, index=False)
        commands, chosen = [], [self.today]
        def command(cmd, description):
            commands.append(cmd)
            if 'step1_daily.py' in cmd:
                chosen[0] = cmd.split('--trade-date ')[1]
            if 'step3_filter.py' in cmd:
                pd.DataFrame({'股票代码': self.tickers, '交易日期': chosen[0]}).to_csv(candidate, index=False)
            return 0
        with mock.patch.object(bf, 'DATA_DIR', self.root), \
             mock.patch.object(bf, 'CURRENT_DIR', self.root), \
             mock.patch.object(bf, 'run_command_status', side_effect=command):
            plan = bf.prepare_batch([self.tickers[0]], candidate, self.today, True, 'new-pool')
        self.assertEqual(plan['data_asof'], self.previous)
        self.assertEqual(len(commands), 6)
        self.assertEqual(set(pd.read_csv(candidate)['交易日期'].astype(str)), {self.previous})

    def test_partial_market_publication_is_not_complete(self):
        baseline = pd.DataFrame({'ts_code': ['600000.SH', '600001.SH', '920001.BJ']})
        partial = pd.DataFrame({'ts_code': ['600000.SH']})
        self.assertEqual(snapshot.missing_market_codes(partial, baseline), {'600001.SH'})
        full = pd.DataFrame({'ts_code': ['600000.SH', '600001.SH', '600002.SH']})
        self.assertEqual(snapshot.missing_market_codes(full, baseline), set())

    def test_few_suspended_tickers_still_use_today(self):
        # 停牌股当日无行情是正常状态，不能让全批退回昨天。
        accept, reason = snapshot.evaluate_market_gap({'000635.SZ', '002731.SZ'}, 5571)
        self.assertTrue(accept)
        self.assertIn('停牌', reason)

    def test_widespread_gap_forces_previous_day(self):
        missing = {f'6000{i:02d}.SH' for i in range(60)}
        accept, reason = snapshot.evaluate_market_gap(missing, 5571)
        self.assertFalse(accept)
        self.assertIn('回退', reason)

    def test_empty_gap_is_fully_covered(self):
        self.assertEqual(snapshot.evaluate_market_gap(set(), 5571)[0], True)

    def test_network_failure_is_not_misreported_as_incomplete_publication(self):
        candidate = os.path.join(self.root, 'input.csv')
        pd.DataFrame({'股票代码': self.tickers}).to_csv(candidate, index=False)
        with mock.patch.object(bf, 'run_command_status', return_value=2):
            with self.assertRaisesRegex(RuntimeError, '未冒充当日未齐'):
                bf.prepare_batch(self.tickers, candidate, self.today, False, 'network-error')

    def test_real_batch_subprocesses_use_one_day(self):
        self.write_market(self.tickers[0])
        self.write_market(self.tickers[1], False)
        candidate = os.path.join(self.root, 'input.csv')
        pd.DataFrame({'股票代码': self.tickers}).to_csv(candidate, index=False)
        output = os.path.join(self.root, 'holdings.csv')
        with mock.patch.object(bf, 'DATA_DIR', self.root), \
             mock.patch.object(bf, 'expected_trade_asof', return_value=self.today), \
             mock.patch.object(sys, 'argv', ['batch', '--input', candidate, '--output', output, '--skip-data']), \
             contextlib.redirect_stdout(io.StringIO()):
            rc = bf.main()
        with open(os.path.splitext(output)[0] + '_status.json') as fh:
            status = json.load(fh)
        self.assertEqual(rc, 0, status.get('error'))
        self.assertEqual(status['data_asof'], self.previous)
        self.assertEqual(status['processed'], 2)
        self.assertEqual({m['data_asof'] for m in status['source_manifest'].values()}, {self.previous})
        rows = pd.read_csv(output)
        if not rows.empty:
            self.assertEqual(set(rows['数据截止日'].astype(str)), {self.previous})
