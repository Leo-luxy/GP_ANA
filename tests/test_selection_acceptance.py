"""批筛失败、发布中断与接口严格读取验收；只使用临时目录。"""
import contextlib
import io
import json
import os
import sys
import shutil
import tempfile
from datetime import datetime
import unittest
from unittest import mock

from flask import Flask
import pandas as pd
import stocks_filter.batch_backtest_filter as bf
import api.stock_selection as api


class SelectionProgressTest(unittest.TestCase):
    def test_progress_line_updates_task_range(self):
        api.selection_tasks['t'] = {'status': 'running', 'progress': 0,
                                    'progress_base': 40, 'progress_span': 55}
        api._update_step_progress('t', '[63/127] 处理股票: 600000.SH')
        self.assertEqual(api.selection_tasks['t']['progress'], 40 + int(55 * 63 / 127))
        self.assertIn('63/127', api.selection_tasks['t']['progress_label'])
        api._set_step_progress('t', 15, '全市场行情完成')
        self.assertEqual(api.selection_tasks['t']['progress'], 15)
        self.assertEqual(api.selection_tasks['t']['progress_label'], '全市场行情完成')
        # 没有 [i/N] 的普通输出不应改变进度
        api._update_step_progress('t', '没有进度标记的普通输出')
        self.assertEqual(api.selection_tasks['t']['progress'], 15)
        api.selection_tasks.pop('t')


class SelectionAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = self.tmp.name
        self.output = os.path.join(self.base, 'final_holdings.csv')
        self.status_path = os.path.join(self.base, 'final_holdings_status.json')
        self.app = Flask(__name__)
        self.app.register_blueprint(api.stock_selection_bp)
        self.patch = mock.patch.object(api, 'SELECTION_DIR', self.base)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.manifest = {'source_sha256': 'source', 'indicators_sha256': 'ind', 'calculator_version': 'calc', 'data_asof': '20261112'}
        for patcher in [mock.patch.object(bf, 'expected_trade_asof', return_value='20261112'),
                        mock.patch.object(api, 'expected_trade_asof', return_value='20261112'),
                        mock.patch.object(bf, 'qfq_asof', return_value='20261112'),
                        mock.patch.object(bf.backtest_artifacts, 'source_manifest', return_value=self.manifest)]:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.input_path = os.path.join(self.base, 'stocks_daily_filtered.csv')
        pd.DataFrame({'股票代码': ['600000.SH']}).to_csv(self.input_path, index=False)
        api.selection_tasks.clear()
        api.selection_results.clear()

    def status(self):
        with open(self.status_path, encoding='utf-8') as fh:
            return json.load(fh)

    def publish(self, rows=None):
        status = dict(generated_at='2026-11-13T14:00:00', strategy='simple', params=bf.get_params('simple'),
                      input_count=1, processed=1, holding=0, flat=1, failed=0,
                      completed=True, valid=True, void=False, exit_code=0,
                      state='completed', run_id='fixture-run', degraded=False,
                      data_asof='20261112', input_tickers=['600000.SH'],
                      processed_tickers=['600000.SH'],
                      input_file='stocks_daily_filtered.csv', input_sha256=bf.file_hash(self.input_path),
                      source_manifest={'600000.SH': self.manifest.copy()})
        bf.write_holdings(rows or [], self.output, self.status_path, status)
        return status

    def main(self, outcomes=None, tickers=None, input_error=None, real_failure=False):
        with contextlib.ExitStack() as stack:
            stack.enter_context(mock.patch.object(bf, 'CURRENT_DIR', self.base))
            stack.enter_context(mock.patch.object(sys, 'argv', ['batch_filter']))
            stack.enter_context(mock.patch.object(bf, 'get_stock_list',
                                return_value=tickers or ['600000.SH'], side_effect=input_error))
            if real_failure:
                stack.enter_context(mock.patch.object(bf, 'prepare_batch',
                    side_effect=RuntimeError('行情取数失败（退出码 2）')))
            else:
                stack.enter_context(mock.patch.object(bf, 'prepare_batch', return_value=dict(
                    tickers=[t for t in (tickers or ['600000.SH']) if not bf.is_bj_ticker(t)],
                    data_asof='20261112', snapshot_dir=self.base, raw_hashes={}, warnings=[])))
                stack.enter_context(mock.patch.object(bf, 'process_single_stock', side_effect=outcomes))
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            return bf.main()

    def test_real_collection_failure_returns_three_and_void(self):
        self.publish()
        self.assertEqual(self.main(real_failure=True), 3)
        s = self.status()
        self.assertTrue(s['void'])
        self.assertEqual(s['processed'], 0)  # 预检失败，未进入回测阶段
        self.assertEqual(s['exit_code'], 3)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_real_indicator_failure_returns_triple(self):
        with mock.patch.object(bf, 'run_command_status', return_value=1):
            outcome = bf.process_single_stock('600000.SH', True)
        self.assertEqual(outcome[0], 'failed')
        self.assertEqual(outcome[2], None)
        self.assertIn('指标', outcome[1])

    def test_unexpected_exception_also_replaces_old_result_with_void(self):
        self.publish()
        self.assertEqual(self.main(outcomes=RuntimeError('fixture crash')), 3)
        self.assertIn('fixture crash', self.status()['void_reason'])
        self.assertEqual(len(pd.read_csv(self.output)), 0)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_bad_input_and_missing_input_are_void(self):
        self.publish()
        self.assertEqual(self.main(input_error=ValueError('bad csv')), 1)
        self.assertTrue(self.status()['void'])
        self.assertEqual(self.status()['exit_code'], 1)

    def test_stale_after_success_voids_partial_rows(self):
        row = {'股票代码': '600000.SH', '入场日期': '2026-11-12'}
        outcomes = [('holding', row, '20261112'), bf.StaleResultError('stale')]
        self.assertEqual(self.main(outcomes, ['600000.SH', '600001.SH']), 2)
        self.assertTrue(self.status()['void'])
        self.assertEqual(len(pd.read_csv(self.output)), 0)

    def test_minority_failure_is_degraded_but_displayable(self):
        """少量失败：名单里的行仍可用，但必须显式降级并列出缺失股票。"""
        self.assertEqual(self.main([('flat', None, '20261112'),
                                    ('flat', None, '20261112'), ('failed', None, None)],
                                   ['600000.SH', '600001.SH', '600002.SH']), 0)
        s = self.status()
        self.assertEqual(s['state'], 'degraded')
        self.assertTrue(s['degraded'])
        self.assertIs(s['void'], False)
        self.assertIs(s['valid'], True)
        self.assertEqual(s['processed_tickers'], ['600000.SH', '600001.SH'])
        self.assertTrue(s['warnings'])
        response = self.app.test_client().get('/stock_selection/get_result').get_json()
        self.assertTrue(response['success'])
        self.assertTrue(response['degraded'])
        self.assertEqual(response['data'], [])

    def test_valid_empty_completed_result_is_success(self):
        self.publish()
        result = api._read_current_holdings()
        self.assertTrue(result['success'])
        self.assertEqual(result['data'], [])

    def test_missing_corrupt_and_incomplete_status_rejected(self):
        for value in [None, '{bad', '{}', '[]']:
            self.publish()
            if value is None:
                os.unlink(self.status_path)
            else:
                with open(self.status_path, 'w') as fh:
                    fh.write(value)
            self.assertFalse(api._read_current_holdings()['success'])

    def test_modified_csv_rejected(self):
        self.publish()
        with open(self.output, 'a') as fh:
            fh.write('tampered')
        self.assertFalse(api._read_current_holdings()['success'])

    def test_void_does_not_fallback_to_preliminary(self):
        pd.DataFrame([{'股票代码': '600000.SH'}]).to_csv(
            os.path.join(self.base, 'stocks_daily_filtered.csv'), index=False)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_publisher_failure_leaves_void_state(self):
        self.publish()
        with mock.patch.object(pd.DataFrame, 'to_csv', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.publish()
        self.assertTrue(self.status()['void'])
        self.assertFalse(api._read_current_holdings()['success'])

    def test_run_selection_rejects_zero_exit_without_publish(self):
        self.publish()
        with mock.patch.object(api, 'run_command_with_output', return_value=0):
            api.run_selection('fake', False, True)
        self.assertEqual(api.selection_tasks['fake']['status'], 'failed')
        self.assertNotIn('fake', api.selection_results)

    def test_run_selection_uses_same_degraded_reader(self):
        def command(*args, **kwargs):
            self.main([('flat', None, '20261112'), ('flat', None, '20261112'),
                       ('failed', None, None)], ['600000.SH', '600001.SH', '600002.SH'])
            return 0
        with mock.patch.object(api, 'run_command_with_output', side_effect=command):
            api.run_selection('degraded', False, True)
        self.assertEqual(api.selection_tasks['degraded']['status'], 'degraded')
        self.assertIn('degraded', api.selection_results)
        self.assertEqual(api.selection_results['degraded'], [])

    def test_latest_success_remains_visible_after_failed_new_attempt(self):
        self.publish()
        api.invalidate_holdings('新任务运行中')
        self.assertFalse(api._read_current_holdings()['success'])
        displayed = api.read_final_holdings()
        self.assertTrue(displayed['success'])
        self.assertTrue(displayed['showing_saved_result'])
        self.assertEqual(displayed['data_asof'], '20261112')
        # 失败批次写空CSV也不能覆盖成功空仓或成功持仓的快照。
        failed = dict(completed=True, valid=False, void=True, state='failed')
        bf.write_holdings([], self.output, self.status_path, failed)
        self.assertTrue(api.read_final_holdings()['success'])

    def test_legacy_display_is_explicitly_not_a_verified_current_batch(self):
        import selection_result_store as store
        row = {'股票代码': '600000.SH', '入场日期': '2026-11-10',
               '当前日期': '2026-11-12', '数据截止日': '20261112', '离场类型': 'final_close'}
        pd.DataFrame([row]).to_csv(self.output, index=False)
        store.preserve_legacy_display(self.output)
        bf.atomic_status(self.status_path, {'void': True, 'valid': False, 'state': 'running'})
        result = api.read_final_holdings()
        self.assertTrue(result['success'])
        self.assertFalse(result['verified'])
        self.assertFalse(result['is_current'])
        self.assertEqual(len(result['data']), 1)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_preliminary_only_reports_candidates_not_stale(self):
        """只跑初筛时，查询要说明"尚未生成最终持仓"，而不是报结果过期。"""
        pd.DataFrame({'股票代码': ['600000.SH', '600001.SH']}).to_csv(self.input_path, index=False)
        with mock.patch.object(api, 'run_command_with_output', return_value=0):
            api.run_selection('pre-only', True, False)
        result = api._read_current_holdings()
        self.assertFalse(result['success'])
        self.assertTrue(result['preliminary_only'])
        self.assertEqual(result['candidates'], 2)
        self.assertIn('尚未生成最终持仓', result['message'])
        self.assertNotIn('期望', result['message'])

    def _patch_latest_available(self, asof):
        return mock.patch('check_data_updates.get_latest_available_trade_date',
                          return_value=datetime.strptime(asof, '%Y%m%d').date())

    def test_result_matching_latest_available_data_is_current(self):
        """本地最新行情就是 11-12 时，11-12 的结果应视为当前（即使日历已是 11-13）。"""
        self.publish()
        with self._patch_latest_available('20261112'):
            result = api._read_current_holdings()
        self.assertTrue(result['success'])
        self.assertIs(result['is_current'], True)
        self.assertFalse(any('当前交易日' in w for w in result['warnings']))

    def test_result_older_than_latest_available_is_displayed_with_hint(self):
        self.publish()
        with self._patch_latest_available('20261113'):
            result = api._read_current_holdings()
        self.assertTrue(result['success'])
        self.assertIs(result['is_current'], False)
        joined = '；'.join(result['warnings'])
        self.assertIn('20261112', joined)
        self.assertIn('20261113', joined)

    def test_partial_basic_data_rebuilds_whole_preliminary_previous_day(self):
        source_day = datetime.now().strftime('%Y%m%d')
        pd.DataFrame({'trade_date': [source_day]}).to_csv(
            os.path.join(self.base, 'stocks_daily_temp.csv'), index=False)
        calls = []
        basics = 0
        def command(task_id, cmd, cwd, description):
            nonlocal basics
            calls.append(cmd)
            if 'step2_daily_basic.py' in cmd[1]:
                basics += 1
                return 4 if basics == 1 else 0
            return 0
        with mock.patch.object(api, 'run_command_with_output', side_effect=command):
            api.run_selection('basic-fallback', True, False)
        self.assertEqual(api.selection_tasks['basic-fallback']['status'], 'completed')
        rebuilt = [cmd for cmd in calls if '--trade-date' in cmd]
        self.assertEqual(len(rebuilt), 1)
        self.assertLess(rebuilt[0][-1], source_day)

    def test_preliminary_is_candidates_not_holdings(self):
        pd.DataFrame([{'股票代码': '600000.SH'}]).to_csv(
            os.path.join(self.base, 'stocks_daily_filtered.csv'), index=False)
        with mock.patch.object(api, 'run_command_with_output', return_value=0):
            api.run_selection('preliminary', True, False)
        self.assertEqual(api.selection_tasks['preliminary']['result_kind'], 'preliminary')
        self.assertNotIn('preliminary', api.selection_results)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_indicators_updated_after_result_still_displayed_with_warning(self):
        status = self.publish()
        status['generated_at'] = '2020-01-01T00:00:00'
        bf.atomic_status(self.status_path, status)
        data_dir = tempfile.mkdtemp(prefix='gp_sel_data_')
        self.addCleanup(shutil.rmtree, data_dir, True)
        os.makedirs(os.path.join(data_dir, '600000.SH'), exist_ok=True)
        with open(os.path.join(data_dir, '600000.SH', '600000.SH_indicators.csv'), 'w') as fh:
            fh.write('date\n2026-11-12\n')
        with mock.patch.object(api, 'DATA_DIR', data_dir):
            result = api._read_current_holdings()
        self.assertTrue(result['success'])
        self.assertTrue(any('更新过' in w for w in result['warnings']))

    def test_changed_input_list_is_warning_not_error(self):
        self.publish()
        pd.DataFrame({'股票代码': ['600001.SH']}).to_csv(self.input_path, index=False)
        result = api._read_current_holdings()
        self.assertTrue(result['success'])
        self.assertTrue(any('候选池' in w for w in result['warnings']))

    def test_skip_data_marks_stale_market_as_failed_without_calculator(self):
        """单只停牌/停更不应中断整批：记为该股失败，且不进入指标计算与回测。"""
        with mock.patch.object(bf, 'qfq_asof', return_value='20260512'), \
             mock.patch.object(bf, 'run_command_status') as command:
            outcome, payload, asof = bf.process_single_stock('600000.SH', True, True)
        command.assert_not_called()
        self.assertEqual(outcome, 'failed')
        self.assertIn('停更', payload)
        self.assertIsNone(asof)

    def test_main_rejects_old_asof_even_if_worker_returns_success(self):
        self.assertEqual(self.main([('flat', None, '20260512')]), 2)
        self.assertTrue(self.status()['void'])

    def test_bound_csv_with_wrong_row_date_is_still_rejected(self):
        row = {'股票代码': '600000.SH', '入场日期': '2026-11-10',
               '当前日期': '2026-05-12', '数据截止日': '20261112', '离场类型': 'final_close'}
        status = self.publish([row])
        status.update(holding=1, flat=0)
        bf.atomic_status(self.status_path, status)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_self_consistent_older_row_is_rejected_in_uniform_batch(self):
        row = {'股票代码': '600000.SH', '入场日期': '2026-11-10',
               '当前日期': '2026-11-11', '数据截止日': '20261111', '离场类型': 'final_close'}
        status = self.publish([row])
        status.update(holding=1, flat=0)
        bf.atomic_status(self.status_path, status)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_ticker_input_preserves_zero_and_supports_beijing(self):
        pd.DataFrame({'code': ['000001', '688981.SH', '830001', '920001.BJ']}).to_csv(self.input_path, index=False)
        self.assertEqual(bf.get_stock_list(self.input_path),
                         ['000001.SZ', '688981.SH', '830001.BJ', '920001.BJ'])
        for value in ['', 'nan', '600000; echo x', '600000.SZ', '../000001', float('nan')]:
            with self.assertRaises(ValueError):
                bf.normalize_ticker(value)

    def test_missing_input_replaces_old_status(self):
        self.publish()
        os.unlink(self.input_path)
        with mock.patch.object(bf, 'CURRENT_DIR', self.base), \
             mock.patch.object(sys, 'argv', ['batch_filter']), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(bf.main(), 1)
        self.assertTrue(self.status()['void'])

    def test_successful_selection_uses_verified_published_rows(self):
        def command(*args, **kwargs):
            self.publish()
            return 0
        with mock.patch.object(api, 'run_command_with_output', side_effect=command):
            api.run_selection('valid', False, True)
        self.assertEqual(api.selection_tasks['valid']['status'], 'completed')
        self.assertEqual(api.selection_results['valid'], [])

    def test_broken_status_counts_are_rejected(self):
        s = self.publish()
        s.pop('input_count')
        s.pop('processed')
        bf.atomic_status(self.status_path, s)
        self.assertFalse(api._read_current_holdings()['success'])

    def test_status_write_failure_marks_task_failed(self):
        with mock.patch.object(api, 'invalidate_holdings', side_effect=OSError('disk full')):
            api.run_selection('disk', False, True)
        self.assertEqual(api.selection_tasks['disk']['status'], 'failed')

    def test_valid_provenance_skips_calculator_but_still_runs_backtest(self):
        with mock.patch.object(bf.indicator_provenance, 'validate_indicators',
                               return_value={'source_sha256': 'source'}), \
             mock.patch.object(bf, 'indicator_asof', return_value='20261112'), \
             mock.patch.object(bf.backtest_artifacts, 'fingerprint_csv', return_value='fp'), \
             mock.patch.object(bf, 'read_backtest_result', return_value=None) as reader, \
             mock.patch.object(bf, 'run_command', return_value=True) as command:
            self.assertEqual(bf.process_single_stock('600000.SH', True, True),
                             ('flat', None, '20261112'))
            self.assertEqual(command.call_count, 1)
            self.assertIn('trend_following_backtest.py', command.call_args.args[0])
            reader.assert_called_once_with('600000.SH', '20261112', 'fp', 'source')

    def test_skip_indicator_must_validate_content_and_recompute_if_invalid(self):
        with mock.patch.object(bf.indicator_provenance, 'validate_indicators',
                               side_effect=ValueError('source changed')), \
             mock.patch.object(bf, 'run_command_status', return_value=1) as command:
            outcome = bf.process_single_stock('600000.SH', True, True)
            self.assertEqual(outcome[0], 'failed')
            self.assertEqual(outcome[2], None)
            self.assertIn('指标', outcome[1])
            self.assertIn('stock_daily_indicator_calculator.py', command.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
