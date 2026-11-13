"""批筛读取的时效校验测试：确保不会再把旧回测当成最新持仓。"""

import os
import sys
import json
import tempfile
import unittest
from unittest import mock

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import backtest_artifacts  # noqa: E402
import stocks_filter.batch_backtest_filter as bf  # noqa: E402


def _signals(rows):
    return pd.DataFrame([
        {'date': d, 'price': p, 'signal_type': t, 'trade_profit': g, 'exit_type': e}
        for d, p, t, g, e in rows
    ])


class FilterTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self._old_art = backtest_artifacts.DATA_DIR
        self._old_bf = bf.DATA_DIR
        backtest_artifacts.DATA_DIR = self.tmp.name
        bf.DATA_DIR = self.tmp.name
        self.ticker = '688981.SH'
        self.manifest = {'source_sha256': 'fixture-source', 'data_asof': '20261112'}
        date_patch = mock.patch.object(bf, 'expected_trade_asof', return_value='20261112')
        date_patch.start()
        self.addCleanup(date_patch.stop)
        self.manifest_patch = mock.patch.object(backtest_artifacts, 'source_manifest', return_value=self.manifest)
        self.manifest_patch.start()
        self.addCleanup(self.manifest_patch.stop)
        os.makedirs(os.path.join(self.tmp.name, self.ticker), exist_ok=True)

    def tearDown(self):
        backtest_artifacts.DATA_DIR = self._old_art
        bf.DATA_DIR = self._old_bf
        self.tmp.cleanup()

    def _write(self, strategy, asof, rows, run_id='20261113T091530'):
        return backtest_artifacts.write_result(
            self.ticker, strategy, bf.get_params(strategy), asof,
            _signals(rows), run_id=run_id, source_manifest=self.manifest)


class TestReadBacktestResult(FilterTestBase):
    def test_fresh_result_accepted(self):
        self._write('simple', '20261112', [
            ('2026-04-27', 116.58, 'buy', 0.0, 'final_close'),
            ('2026-11-12', 130.00, 'sell', 0.115, 'final_close'),
        ])
        row = bf.read_backtest_result(self.ticker, '20261112')
        self.assertIsNotNone(row)
        self.assertEqual(row['股票代码'], self.ticker)
        self.assertEqual(row['数据截止日'], '20261112')
        self.assertEqual(row['离场类型'], 'final_close')

    def test_old_result_rejected(self):
        """复现 2026-11-13 的事故：目录里只有 5 月结果时，必须拒绝而不是当成持仓。"""
        self._write('simple', '20260525', [
            ('2026-04-27', 116.58, 'buy', 9.126779893635273, 'final_close'),
            ('2026-05-21', 127.22, 'sell', 9.126779893635273, 'final_close'),
        ], run_id='20260525T150000')
        with self.assertRaises(bf.StaleResultError):
            bf.read_backtest_result(self.ticker, '20261112')

    def test_mismatched_inner_date_rejected(self):
        """文件名/元数据写新日期，但内部期末记录是旧日期，也要拒绝。"""
        self._write('simple', '20261112', [
            ('2026-04-27', 116.58, 'buy', 9.126779893635273, 'final_close'),
            ('2026-05-21', 127.22, 'sell', 9.126779893635273, 'final_close'),
        ])
        with self.assertRaises(bf.StaleResultError):
            bf.read_backtest_result(self.ticker, '20261112')

    def test_no_final_close_means_flat(self):
        self._write('simple', '20261112', [
            ('2026-10-09', 10.0, 'buy', 0.0, 'stop_loss'),
            ('2026-10-15', 9.0, 'sell', -0.10, 'stop_loss'),
        ])
        self.assertIsNone(bf.read_backtest_result(self.ticker, '20261112'))


class TestExitCodes(FilterTestBase):
    """批筛退出码：全失败/过半失败不能被当成正常空结果。"""

    def _run_main(self, outcomes, tickers=None, extra_args=()):
        import contextlib
        import io
        tickers = tickers or [self.ticker]
        out_dir = os.path.join(self.tmp.name, 'out')
        os.makedirs(out_dir, exist_ok=True)
        pd.DataFrame({'股票代码': tickers}).to_csv(os.path.join(out_dir, 'stocks_daily_filtered.csv'), index=False)
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(
                sys, 'argv', ['batch_backtest_filter.py', *extra_args]))
            stack.enter_context(mock.patch.object(
                bf, 'get_stock_list', return_value=tickers))
            stack.enter_context(mock.patch.object(
                bf, 'process_single_stock', side_effect=outcomes))
            stack.enter_context(mock.patch.object(bf, 'CURRENT_DIR', out_dir))
            planned = [t for t in tickers if not bf.is_bj_ticker(t)]
            if '--limit' in extra_args:
                planned = planned[:int(extra_args[extra_args.index('--limit') + 1])]
            stack.enter_context(mock.patch.object(bf, 'prepare_batch', return_value=dict(
                tickers=planned, data_asof='20261112', snapshot_dir=self.tmp.name,
                raw_hashes={}, warnings=[])))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return bf.main()

    def test_all_failed_exits_nonzero(self):
        rc = self._run_main([('failed', None, None)], tickers=[self.ticker])
        self.assertEqual(rc, 3)

    def test_majority_failed_exits_nonzero(self):
        outcomes = [('failed', None, None), ('failed', None, None),
                    ('flat', None, '20261112')]
        rc = self._run_main(outcomes, tickers=['600000.SH', '600001.SH', '600002.SH'])
        self.assertEqual(rc, 3)

    def test_all_flat_is_normal(self):
        rc = self._run_main([('flat', None, '20261112')], tickers=[self.ticker])
        self.assertEqual(rc, 0)

    def test_holding_is_normal(self):
        row = {'股票代码': self.ticker, '入场日期': '2026-11-10', '入场价格': 10.0,
               '当前日期': '2026-11-12', '当前价格': 11.0, '收益': 10.0,
               '离场类型': 'final_close', '数据截止日': '20261112'}
        rc = self._run_main([('holding', row, '20261112')], tickers=[self.ticker])
        self.assertEqual(rc, 0)

    def test_limit_run_marks_void_diagnostic(self):
        """--limit 只跑前几只，结果天然不完整，不能发布成当前持仓。"""
        tickers = [self.ticker, '600000.SH', '600001.SH']
        rc = self._run_main([('flat', None, '20261112')], tickers=tickers,
                            extra_args=('--limit', '1'))
        self.assertEqual(rc, 0)
        status_path = os.path.join(self.tmp.name, 'out', 'final_holdings_status.json')
        with open(status_path, encoding='utf-8') as fh:
            status = json.load(fh)
        self.assertEqual(status['state'], 'diagnostic')
        self.assertIs(status['void'], True)
        self.assertIs(status['valid'], False)
        self.assertEqual(status['holdings'], 0)

    def test_bj_tickers_are_excluded_not_failed(self):
        """北交所不在覆盖范围：跳过且不计失败，结果仍为正常完成。"""
        rc = self._run_main([('flat', None, '20261112')],
                            tickers=['600000.SH', '920186.BJ'])
        self.assertEqual(rc, 0)
        with open(os.path.join(self.tmp.name, 'out', 'final_holdings_status.json'),
                  encoding='utf-8') as fh:
            status = json.load(fh)
        self.assertEqual(status['excluded_bj'], ['920186.BJ'])
        self.assertEqual(status['input_count'], 1)
        self.assertEqual(status['failed'], 0)
        self.assertEqual(status['state'], 'completed')
        self.assertIs(status['void'], False)

    def test_stale_result_exits_two(self):
        def _raise(*args, **kwargs):
            raise bf.StaleResultError('行情与结果不一致')

        rc = self._run_main(_raise, tickers=[self.ticker])
        self.assertEqual(rc, 2)


class TestFingerprintGuard(FilterTestBase):
    def _write(self, fingerprint=None):
        return backtest_artifacts.write_result(
            self.ticker, 'simple', bf.get_params('simple'), '20261112',
            _signals([('2026-04-27', 116.58, 'buy', 0.0, 'final_close'),
                      ('2026-11-12', 130.0, 'sell', 0.115, 'final_close')]),
            data_fingerprint=fingerprint, run_id='20261113T091530',
            source_manifest=self.manifest)

    def test_fingerprint_mismatch_rejected(self):
        self._write(fingerprint='aaaaaaaaaaaaaaaa')
        with self.assertRaises(bf.StaleResultError):
            bf.read_backtest_result(self.ticker, '20261112',
                                    expect_fingerprint='bbbbbbbbbbbbbbbb')

    def test_fingerprint_match_accepted(self):
        self._write(fingerprint='aaaaaaaaaaaaaaaa')
        row = bf.read_backtest_result(self.ticker, '20261112',
                                      expect_fingerprint='aaaaaaaaaaaaaaaa')
        self.assertEqual(row['数据截止日'], '20261112')

    def test_missing_fingerprint_rejected_when_expected(self):
        """产物没写指纹时也不能放行：说明是重建前的旧产物。"""
        self._write(fingerprint=None)
        with self.assertRaises(bf.StaleResultError):
            bf.read_backtest_result(self.ticker, '20261112',
                                    expect_fingerprint='aaaaaaaaaaaaaaaa')


class TestBasisChangeRebuild(FilterTestBase):
    """退出码 3 = 前复权基准变化：必须自动重建，而不是当成网络失败。"""

    def _setup_ok(self, **patches):
        defaults = {
            'qfq_asof': mock.patch.object(bf, 'qfq_asof', return_value='20261112'),
            'indicator_asof': mock.patch.object(bf, 'indicator_asof', return_value='20261112'),
            'validate': mock.patch.object(bf.indicator_provenance, 'validate_indicators',
                                          return_value={'source_sha256': 's', 'data_asof': '20261112'}),
            'fingerprint': mock.patch.object(bf.backtest_artifacts, 'fingerprint_csv',
                                             return_value='fp'),
            'read': mock.patch.object(bf, 'read_backtest_result', return_value=None),
        }
        defaults.update(patches)
        for item in defaults.values():
            item.start()
            self.addCleanup(item.stop)

    def test_basis_change_triggers_rebuild_then_continues(self):
        self._setup_ok()
        with mock.patch.object(bf, 'run_command_status', side_effect=[3, 0, 0, 0]) as run:
            outcome, payload, asof = bf.process_single_stock(self.ticker, False)
        commands = [call.args[0] for call in run.call_args_list]
        self.assertIn('--rebuild', commands[1])
        self.assertEqual(outcome, 'flat')
        self.assertIsNone(payload)

    def test_rebuild_failure_reports_reason(self):
        self._setup_ok()
        with mock.patch.object(bf, 'run_command_status', side_effect=[3, 4]):
            outcome, payload, asof = bf.process_single_stock(self.ticker, False)
        self.assertEqual(outcome, 'failed')
        self.assertIn('重建失败', payload)


class TestHoldingRow(FilterTestBase):
    def test_holding_row_has_processing_time(self):
        row = bf.read_backtest_result  # 仅确认函数存在，真正断言在写入端
        payload = {'股票代码': self.ticker, '入场日期': '2026-11-10', '入场价格': 10.0,
                   '当前日期': '2026-11-12', '当前价格': 11.0, '收益': 10.0,
                   '离场类型': 'final_close', '数据截止日': '20261112',
                   '处理时间': '2026-11-13 15:00:00'}
        out = os.path.join(self.tmp.name, 'holdings.csv')
        df = bf.write_holdings([payload], out, out + '.status.json', {})
        self.assertIn('处理时间', df.columns)
        self.assertEqual(df.iloc[0]['处理时间'], '2026-11-13 15:00:00')


class TestWriteHoldings(FilterTestBase):
    def test_empty_result_writes_header_and_overwrites_old_rows(self):
        out = os.path.join(self.tmp.name, 'final_holdings.csv')
        status_path = os.path.join(self.tmp.name, 'final_holdings_status.json')

        # 先有一批持仓
        bf.write_holdings(
            [{'股票代码': '600000.SH', '入场日期': '2026-11-10', '入场价格': 10.0,
              '当前日期': '2026-11-12', '当前价格': 11.0, '收益': 10.0,
              '离场类型': 'final_close', '数据截止日': '20261112', '处理时间': 'x'}],
            out, status_path, {})

        # 本期零持仓 → 必须写成空表，不能让旧名单继续存在
        df = bf.write_holdings([], out, status_path, {})
        self.assertEqual(len(df), 0)
        reloaded = pd.read_csv(out, encoding='utf-8-sig')
        self.assertEqual(len(reloaded), 0)
        self.assertIn('股票代码', reloaded.columns)
        with open(status_path, 'r', encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['holdings'], 0)


if __name__ == '__main__':
    unittest.main()
