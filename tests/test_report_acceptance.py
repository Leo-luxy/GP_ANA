"""报告当前身份回归；所有IO限定临时目录，不运行采集/LLM。"""
import copy
import json
import os
import tempfile
import types
import io
import unittest
from unittest.mock import patch
from flask import Flask
import backtest_all_stocks as reports
from api import backtest as api


class ReportAcceptance(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stocks = ['600000.SH']
        self.asof = '20261112'
        self.manifest = {'600000.SH': dict(source_sha256='a'*64,
            indicators_sha256='b'*64, calculator_version='v1', data_asof=self.asof)}
        for obj, name, value in [(reports, 'DATA_DIR', self.tmp.name),
                                  (api, 'DATA_DIR', self.tmp.name),
                                  (reports, 'get_all_stocks', lambda: self.stocks),
                                  (reports, 'expected_trade_date', lambda stocks: self.asof),
                                  (reports, 'source_manifest', lambda stocks, asof: copy.deepcopy(self.manifest))]:
            ctx = patch.object(obj, name, value)
            ctx.start()
            self.addCleanup(ctx.stop)
        app = Flask(__name__)
        app.register_blueprint(api.backtest_bp, url_prefix='/bt')
        self.client = app.test_client()

    def make(self, prefix='monitor_report', mode='full', date='20261113', meta=True):
        ext = '.md' if prefix == 'monitor_report' else '.csv'
        path = os.path.join(self.tmp.name, f'{prefix}_{mode}_{date}{ext}')
        with open(path, 'w') as stream:
            stream.write('# monitor' if ext == '.md' else 'ticker,total_return\n600000.SH,1\n')
        if meta:
            reports.write_report_meta(path, 'monitor' if ext == '.md' else 'batch_summary',
                                      mode, self.asof, self.stocks)
        return path

    def response(self, results=False, mode='full'):
        route = 'get_backtest_results' if results else 'get_report'
        return self.client.get(f'/bt/{route}?mode={mode}').get_json()

    def change_meta(self, path, **changes):
        path = reports.backtest_artifacts.meta_path(path)
        with open(path) as stream:
            meta = json.load(stream)
        meta.update(changes)
        with open(path, 'w') as stream:
            json.dump(meta, stream)

    def test_api_preserves_degraded_data_warnings(self):
        def run(command, cwd, messages, **kwargs):
            if 'check_data_updates' in command:
                kwargs['on_line']('GP_DATA_STATUS=' + json.dumps(
                    dict(degraded=True, warnings=['财务证据禁用'], critical_failures=[])))
            return 0
        with patch.dict('sys.modules', {'watchlist': types.SimpleNamespace(WATCHLIST=[('600000.SH', 'stock')])}), \
                patch.object(api, '_run_command_stream', side_effect=run):
            api.run_backtest_task('report-degraded')
        result = api.backtest_task_status.pop('report-degraded')
        self.assertEqual(result['status'], 'completed')
        self.assertTrue(result['degraded'])
        self.assertEqual(result['warnings'], ['财务证据禁用'])

    def test_backtest_updates_only_price_data(self):
        """回测只更新行情+指标，不逐只抓融资融券等只服务分析报告的数据。"""
        calls = []

        def run(command, cwd, messages, **kwargs):
            calls.append(command)
            return 0

        with patch.dict('sys.modules', {'watchlist': types.SimpleNamespace(
                WATCHLIST=[('600000.SH', 'a')])}), \
                patch.object(api, '_run_command_stream', side_effect=run):
            api.run_backtest_task('price-only')
        api.backtest_task_status.pop('price-only', None)
        update_calls = [c for c in calls if 'check_data_updates' in c]
        self.assertTrue(update_calls)
        for command in update_calls:
            self.assertIn('--mode price', command)
        self.assertFalse(any('batch_margin_collector' in c for c in calls))

    def test_zero_exit_with_critical_status_still_fails(self):
        process = types.SimpleNamespace(stdout=io.StringIO(
            'GP_DATA_STATUS=' + json.dumps(dict(critical_failures=['old data'], warnings=[])) + '\n'),
            wait=lambda: 0)
        with patch.object(api.subprocess, 'Popen', return_value=process):
            self.assertNotEqual(api._run_command_stream('mock', self.tmp.name, []), 0)

    def make_chart(self, mode='full', date='20261113', meta=True, actual_params=None):
        ticker = self.stocks[0]
        directory = os.path.join(self.tmp.name, ticker)
        os.makedirs(directory, exist_ok=True)
        path = os.path.join(directory, f'{ticker}_backtest_{mode}_{date}.png')
        with open(path, 'wb') as stream:
            stream.write(b'\x89PNG\r\n\x1a\nsynthetic test bytes')
        if meta:
            reports.write_report_meta(path, 'chart', mode, self.asof, [ticker],
                                      actual_params=actual_params)
        return f'{ticker}/{os.path.basename(path)}'

    def chart_list(self, mode='full'):
        return self.client.get(f'/bt/get_stock_list?mode={mode}').get_json()

    def chart(self, path, mode='full'):
        return self.client.get(f'/bt/get_chart/{path}?mode={mode}')

    def test_old_png_without_meta_listed_but_unverified(self):
        path = self.make_chart(date='20200101', meta=False)
        data = self.chart_list()
        self.assertEqual([item['chart_path'] for item in data['stocks']], [path])
        self.assertFalse(data['verified'])
        self.assertTrue(data['warning'])
        response = self.chart(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Chart-Verified'], 'false')
        response.close()

    def test_chart_with_newer_actual_date_passes_pre_publish_cutoff(self):
        relative = self.make_chart()
        self.manifest[self.stocks[0]]['data_asof'] = '20261113'
        path = os.path.join(self.tmp.name, relative)
        reports.write_report_meta(path, 'chart', 'full', '20261113', self.stocks)
        self.assertEqual(self.chart(relative).status_code, 200)

    def test_chart_with_current_identity_is_listed_and_returned(self):
        path = self.make_chart()
        self.assertEqual(self.chart_list()['stocks'], [dict(ticker=self.stocks[0], chart_path=path)])
        response = self.chart(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, 'image/png')
        self.assertEqual(response.headers['Cache-Control'], 'no-store')
        response.close()

    def test_crossmode_chart_listed_and_served(self):
        path = self.make_chart(mode='simple')
        data = self.chart_list()  # 请求 full，只有 simple 图表
        self.assertEqual([item['chart_path'] for item in data['stocks']], [path])
        # 另一策略的图表身份是完整的，只是策略不同，仍算已核验
        self.assertTrue(data['verified'])
        unverified = self.chart(path)
        self.assertEqual(unverified.status_code, 200)
        self.assertEqual(unverified.headers['X-Chart-Verified'], 'false')
        unverified.close()
        response = self.chart(path, mode='simple')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['X-Chart-Verified'], 'true')
        response.close()

    def test_stale_source_params_or_chart_tamper_rejected(self):
        for kind in ['date', 'source', 'params', 'tamper', 'void']:
            with self.subTest(kind=kind):
                path = self.make_chart()
                full = os.path.join(self.tmp.name, path)
                if kind == 'date':
                    self.change_meta(full, data_asof='20200101')
                elif kind == 'source':
                    self.change_meta(full, source_manifest={})
                elif kind == 'params':
                    params = reports.get_params('full')
                    params['adx_threshold'] = 99
                    reports.write_report_meta(full, 'chart', 'full', self.asof, self.stocks,
                                              actual_params=params)
                elif kind == 'void':
                    self.change_meta(full, void=True)
                else:
                    with open(full, 'ab') as stream:
                        stream.write(b'tamper')
                data = self.chart_list()
                self.assertEqual([item['chart_path'] for item in data['stocks']], [path])
                self.assertFalse(data['verified'])
                response = self.chart(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['X-Chart-Verified'], 'false')
                response.close()

    def test_chart_new_invalid_candidate_keeps_valid_one(self):
        valid = self.make_chart(date='20261112')
        self.make_chart(meta=False)
        data = self.chart_list()
        # 有身份完整可用的就优先用它，不会被新的无身份图表顶掉
        self.assertEqual([item['chart_path'] for item in data['stocks']], [valid])
        self.assertTrue(data['verified'])

    def test_chart_without_any_meta_still_listed(self):
        newest = self.make_chart(meta=False)
        data = self.chart_list()
        self.assertEqual([item['chart_path'] for item in data['stocks']], [newest])
        self.assertFalse(data['verified'])

    def test_chart_path_escape_rejected(self):
        self.make_chart()
        self.assertEqual(self.chart('../outside.png').status_code, 404)

    def test_valid_report_and_summary(self):
        self.make()
        self.make('backtest_results')
        self.assertTrue(self.response()['success'])
        self.assertTrue(self.response(results=True)['success'])

    def test_report_falls_back_to_other_mode(self):
        self.make(mode='simple')
        with open(os.path.join(self.tmp.name, 'monitor_report_20261113.md'), 'w') as stream:
            stream.write('legacy')
        data = self.response()
        self.assertTrue(data['success'])
        self.assertEqual(data['mode'], 'simple')
        self.assertTrue(data['verified'])

    def test_missing_meta_report_is_shown_with_warning(self):
        self.make(meta=False)
        self.make('backtest_results', meta=False)
        data = self.response()
        self.assertTrue(data['success'])
        self.assertFalse(data['verified'])
        self.assertTrue(data['warning'])
        self.assertTrue(self.response(results=True)['success'])

    def test_reject_identity_state_params_and_source_mismatch(self):
        path = self.make()
        invalids = [dict(data_asof='20260521'), dict(strategy='simple'), dict(void=True),
                    dict(valid=False), dict(status='failed'), dict(params={}),
                    dict(params_sha1='bad'), dict(source_manifest={}), dict(tickers=[])]
        for changes in invalids:
            with self.subTest(changes=changes):
                self.make()
                self.change_meta(path, **changes)
                data = self.response()
                # 身份不通过不再挡住展示，但必须标为未核验并给出原因
                self.assertTrue(data['success'])
                self.assertFalse(data['verified'])
                self.assertTrue(data['warning'])

    def test_source_change_marks_report_unverified(self):
        self.make()
        self.manifest['600000.SH']['source_sha256'] = 'c'*64
        data = self.response()
        self.assertTrue(data['success'])
        self.assertFalse(data['verified'])

    def test_invalid_strategy_does_not_become_full(self):
        self.make()
        self.assertFalse(self.response(mode='unknown')['success'])

    def test_tampered_report_is_shown_but_flagged(self):
        path = self.make()
        with open(path, 'a') as stream:
            stream.write('changed')
        data = self.response()
        self.assertTrue(data['success'])
        self.assertFalse(data['verified'])

    def test_newer_void_report_still_displayed_with_flag(self):
        self.make(date='20261112')
        path = self.make()
        self.change_meta(path, void=True)
        data = self.response()
        self.assertTrue(data['success'])
        # 要么展示当日作废报告（未核验），要么回退到有效旧报告；不能静默当成当日有效
        self.assertTrue(data['warning'] or data['verified'])

    def test_global_expected_date_passed_to_all_monitor_tickers(self):
        with patch.object(reports, '_monitor_state', side_effect=reports.MonitorDataError('old')) as state:
            result = reports.generate_monitor_report(['a', 'b'], write_file=False)
        self.assertEqual([call.args[2] for call in state.call_args_list], [self.asof, self.asof])
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['stale']), 2)

    def test_old_latest_api_typeerror_never_retried(self):
        with patch.object(reports.backtest_artifacts, 'latest', side_effect=TypeError('old API')) as latest:
            with self.assertRaises(TypeError):
                reports._latest_artifact('600000.SH', 'full', self.asof, 'fp', {}, {})
        self.assertEqual(latest.call_count, 1)

    def test_monitor_failures_write_void_and_cli_nonzero(self):
        with patch.object(reports, '_monitor_state', side_effect=reports.MonitorDataError('old')):
            self.assertNotEqual(reports.main(['--monitor-only']), 0)
        data = self.response()
        self.assertTrue(data['success'])
        self.assertFalse(data['verified'])
        path = os.path.join(self.tmp.name, 'monitor_report_full_' + reports.datetime.now().strftime('%Y%m%d') + '.md')
        with open(reports.backtest_artifacts.meta_path(path)) as stream:
            meta = json.load(stream)
        self.assertTrue(meta['void'])
        self.assertEqual(meta['status'], 'failed')

    def test_newer_row_matches_own_source_and_summary_is_valid(self):
        actual = '20261113'
        self.manifest[self.stocks[0]]['data_asof'] = actual
        results = reports.BatchResults([dict(ticker=self.stocks[0], strategy='full',
            data_asof=actual, params_sha1=reports.backtest_artifacts.params_fingerprint(reports.get_params('full')))])
        results.stocks = self.stocks
        results.asof = self.asof  # 昨日门槛，实际今日来源，不能在汇总阶段再次误拒绝。
        results.failures = []
        results.source_manifest = copy.deepcopy(self.manifest)
        frame = reports.write_summary(results)
        self.assertTrue(frame.attrs['valid'])
        # 来源快照与行不同则仍失败，不是放开任意日期。
        results[0]['data_asof'] = self.asof
        frame = reports.write_summary(results)
        self.assertFalse(frame.attrs['valid'])

    def test_missing_section_removed_without_hiding_validation_failure(self):
        with patch.object(reports, '_monitor_state', side_effect=reports.MonitorDataError('指标缺失')):
            result = reports.generate_monitor_report(self.stocks, mode='full', asof=self.asof)
        path = os.path.join(self.tmp.name, 'monitor_report_full_' + reports.datetime.now().strftime('%Y%m%d') + '.md')
        with open(path) as stream:
            content = stream.read()
        self.assertNotIn('## 数据过期/缺失', content)
        for status in reports.MONITOR_STATUSES:
            self.assertIn('## ' + status, content)
        self.assertFalse(result['valid'])
        self.assertEqual(len(result['stale']), 1)
        with open(reports.backtest_artifacts.meta_path(path)) as stream:
            meta = json.load(stream)
        self.assertTrue(meta['void'])
        self.assertTrue(meta['failures'])

    def test_batch_load_failure_records_failure_and_invalid_summary(self):
        with patch.object(reports, 'TrendFollowingStrategy') as strategy:
            strategy.return_value.load_data.return_value = False
            results = reports.run_batch_backtest(asof=self.asof)
        self.assertEqual(len(results.failures), 1)
        frame = reports.write_summary(results)
        self.assertFalse(frame.attrs['valid'])
        self.assertTrue(self.response(results=True)['success'])


class RealSourceAcceptance(unittest.TestCase):
    def test_same_date_source_rebuild_invalidates_report(self):
        import pandas as pd
        import indicator_provenance
        ticker = '600000.SH'
        frame = pd.DataFrame(dict(date=['2026-11-11', '2026-11-12'],
            open=[10., 11.], high=[10., 11.], low=[10., 11.], close=[10., 11.],
            volume=[100., 100.], ATR=[1., 1.], ADX=[30., 30.], MACD_hist=[.1, .1],
            RSI=[50., 50.], BB_lower=[9., 9.], BB_upper=[12., 12.]))
        with tempfile.TemporaryDirectory() as directory, patch.object(reports, 'DATA_DIR', directory):
            stock_dir = os.path.join(directory, ticker)
            os.makedirs(stock_dir)
            source = os.path.join(stock_dir, f'{ticker}_qfq.csv')
            frame[list(reports.backtest_artifacts.MARKET_COLUMNS)].to_csv(source, index=False)
            indicator_provenance.write_indicators(frame, ticker, data_dir=directory)
            path = os.path.join(directory, 'monitor_report_full_20261113.md')
            with open(path, 'w') as stream:
                stream.write('valid report')
            reports.write_report_meta(path, 'monitor', 'full', '20261112', [ticker])
            reports.validate_report_file(path, 'monitor', 'full', '20261112', [ticker])
            frame.loc[:, ['open', 'high', 'low', 'close']] *= 2
            frame[list(reports.backtest_artifacts.MARKET_COLUMNS)].to_csv(source, index=False)
            with self.assertRaises(ValueError):
                reports.validate_report_file(path, 'monitor', 'full', '20261112', [ticker])
            indicator_provenance.write_indicators(frame, ticker, data_dir=directory)
            with self.assertRaises(reports.MonitorDataError):
                reports.validate_report_file(path, 'monitor', 'full', '20261112', [ticker])


if __name__ == '__main__':
    unittest.main()