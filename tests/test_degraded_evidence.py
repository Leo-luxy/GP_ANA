"""离线验收：结构化降级与失效证据不得冒充当前信号。"""
import contextlib
import io
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta
from unittest import mock

import pandas as pd
import check_data_updates as cdu
from api import common
from Process.two_layer_decision_analyzer import TwoLayerDecisionAnalyzer

TICKER = '000001.SZ'
EXPECTED = date(2026, 11, 12)


class DegradedEvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.stock = os.path.join(self.root, TICKER)
        os.makedirs(self.stock)
        patch = mock.patch.object(cdu, 'DATA_DIR', self.root)
        patch.start()
        self.addCleanup(patch.stop)

    def write(self, filename, content):
        path = os.path.join(self.stock, filename)
        with open(path, 'w', encoding='utf-8') as stream:
            stream.write(content)
        return path

    def report(self, kind, meta=None, **extra):
        suffix = {'financial': 'financial_summary', 'sentiment': 'sentiment_valuation',
                  'technical': 'technical_trend_analysis', 'shareholder': 'shareholder_structure',
                  'research': 'research_report_analysis'}[kind]
        report = {'meta': meta or {'ticker': TICKER, 'generated_at': datetime.now().isoformat()},
                  'verdict': {'signal': 'BUY'}, **extra}
        self.write(f'{TICKER}_{suffix}.json', json.dumps(report))

    def analyzer(self):
        analyzer = TwoLayerDecisionAnalyzer(TICKER)
        analyzer.data_dir = self.stock
        return analyzer

    def load(self, analyzer):
        with mock.patch.object(cdu, 'get_calendar_trade_date', return_value=EXPECTED), contextlib.redirect_stdout(io.StringIO()):
            analyzer.load_analysis_reports()

    def test_full_pipeline_checks_all_sources_before_reports(self):
        with mock.patch.object(common, '_execute_steps') as execute:
            common.run_analysis_task('offline', '000001', 'init')
        steps = execute.call_args.args[2]
        gate = next(i for i, step in enumerate(steps) if 'check_data_updates.py --mode all' in step[1])
        for i, step in enumerate(steps):
            if any(name in step[1] for name in ('org_hold_collector.py', 'shareholders_collector.py', 'eastmoney_fetcher.py', 'financial_indicators_collector.py')):
                self.assertLess(i, gate)
            if step[0].startswith(('[计算]', '[分析]', '[摘要]', '[决策]')):
                self.assertGreater(i, gate)
        for name in ('低频数据', '财务指标', '东方财富财务', '计算财务指标', '前十大股东', '股东户数'):
            step = next(step for step in steps if step[0] == '[采集] ' + name)
            self.assertFalse(common._normalize_step(step)[2])
        self.assertEqual(cdu.PERIODIC_DATA_FILES['institutional'][0], '{ticker}_institutional_holdings.csv')
        self.assertEqual(cdu.PERIODIC_DATA_FILES['shareholder'][0], '{ticker}_historical_shareholders.csv')

    def test_complete_source_checks_enable_financial_and_shareholder(self):
        # 模拟已采集的真实命名产物，只核验本任务的检查和消费协议，不运行采集器。
        for name, (filename, _) in {**cdu.DAILY_DATA_FILES, **cdu.PERIODIC_DATA_FILES}.items():
            self.write(filename.format(ticker=TICKER), json.dumps({'source': name}))
        with mock.patch.object(cdu, 'check_and_update_item', return_value=None), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cdu.check_daily_data(TICKER, EXPECTED), [])
            self.assertEqual(cdu.check_periodic_data(TICKER, EXPECTED), [])
        self.report('financial')
        self.report('shareholder')
        analyzer = self.analyzer()
        self.load(analyzer)
        self.assertTrue(analyzer.analysis_reports['financial'])
        self.assertTrue(analyzer.analysis_reports['shareholder'])

    def test_optional_failure_returns_zero_and_writes_invalid_state(self):
        files = {'shareholder_num': cdu.DAILY_DATA_FILES['shareholder_num']}
        with mock.patch.object(cdu, 'DAILY_DATA_FILES', files), mock.patch.object(cdu, 'run_command', return_value=(False, 'offline failure')),              mock.patch.object(cdu, 'get_expected_trade_date', return_value=EXPECTED),              mock.patch.object(sys, 'argv', ['check_data_updates.py', '--ticker', TICKER]), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(cdu.main(), 0)
        statuses = [common.parse_data_status(line) for line in output.getvalue().splitlines()]
        status = [s for s in statuses if s is not None][-1]
        self.assertTrue(status['degraded'])
        self.assertTrue(status['warnings'])
        with open(os.path.join(self.stock, f'{TICKER}_data_freshness.json')) as stream:
            state = json.load(stream)
        self.assertIs(state['items']['shareholder_num']['valid'], False)
        self.report('shareholder')
        self.report('research')
        analyzer = self.analyzer()
        self.load(analyzer)
        self.assertFalse(analyzer.analysis_reports['shareholder'])
        self.assertTrue(analyzer.analysis_reports['research'])

    def test_process_stdout_degradation_reaches_task_status(self):
        payload = cdu.STATUS_PREFIX + json.dumps({'degraded': True, 'warnings': ['noncore stale'], 'critical_failures': []})
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote('print(' + repr(payload) + ')')
        with mock.patch.object(common, 'project_root', self.root), mock.patch.object(common, 'TASK_STATUS_FILE', os.path.join(self.root, 'tasks.json')), mock.patch.object(common, 'task_status', {}):
            self.assertTrue(common._execute_steps('task', TICKER, [('check', command)], 'offline'))
            self.assertTrue(common.task_status['task']['degraded'])
            self.assertIn('noncore stale', common.task_status['task']['warnings'])

    def test_zero_exit_with_critical_protocol_is_failure(self):
        payload = cdu.STATUS_PREFIX + json.dumps({'critical_failures': ['invalid identity'], 'warnings': []})
        command = shlex.quote(sys.executable) + ' -c ' + shlex.quote('print(' + repr(payload) + ')')
        ok, detail = common.execute_step('check', command, self.root, [])
        self.assertFalse(ok)
        self.assertIn('invalid identity', detail)
        result = subprocess.CompletedProcess('x', 0, stdout=payload, stderr='')
        with mock.patch.object(cdu.subprocess, 'run', return_value=result):
            self.assertFalse(cdu.run_command('x')[0])

    def test_stale_void_and_undated_reports_are_not_consumed(self):
        for meta, extra in [({'generated_at': '2025-01-01T00:00:00'}, {}),
                            ({'ticker': TICKER}, {}),
                            ({'generated_at': datetime.now().isoformat()}, {'void': True})]:
            self.report('research', meta, **extra)
            analyzer = self.analyzer()
            self.load(analyzer)
            self.assertFalse(analyzer.analysis_reports['research'])

    def test_source_changed_same_date_or_report_before_check_is_rejected(self):
        dependencies = ('fund_flow', 'margin_data', 'valuation')
        items = {}
        for name in dependencies:
            filename = f'{TICKER}_{name}.csv'
            path = self.write(filename, 'date,value\n2026-11-12,1\n')
            items[name] = {'valid': True, 'filename': filename, 'sha256': cdu.source_digest(path),
                           'checked_at': datetime.now().isoformat()}
        cdu.write_evidence_state(TICKER, EXPECTED, items)
        self.report('sentiment')
        analyzer = self.analyzer()
        self.load(analyzer)
        self.assertTrue(analyzer.analysis_reports['sentiment'])
        self.write(f'{TICKER}_valuation.csv', 'date,value\n2026-11-12,2\n')
        self.load(analyzer)
        self.assertFalse(analyzer.analysis_reports['sentiment'])
        self.assertNotIn('sentiment', analyzer.extract_layer1_data())
        items['valuation']['sha256'] = cdu.source_digest(os.path.join(self.stock, f'{TICKER}_valuation.csv'))
        cdu.write_evidence_state(TICKER, EXPECTED, items)
        self.report('sentiment', {'generated_at': EXPECTED.isoformat() + 'T00:00:00'})
        self.load(analyzer)
        self.assertFalse(analyzer.analysis_reports['sentiment'])

    def test_same_date_indicator_source_change_triggers_recompute_and_recheck(self):
        from indicator_provenance import write_indicators
        qfq = pd.DataFrame({'date': ['2026-11-12'], 'open': [10], 'high': [11], 'low': [9], 'close': [10], 'volume': [100]})
        qfq.to_csv(os.path.join(self.stock, f'{TICKER}_qfq.csv'), index=False)
        indicators = qfq.copy()
        from indicator_provenance import REQUIRED_INDICATORS
        for column in REQUIRED_INDICATORS:
            indicators[column] = 1.0
        write_indicators(indicators, TICKER, data_dir=self.root)
        rule = cdu.get_freshness_rule('indicators')
        path = os.path.join(self.stock, f'{TICKER}_indicators.csv')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(cdu.check_file_freshness(path, EXPECTED, rule, 'indicators')[0])
        qfq['close'] = 10.5
        qfq.to_csv(os.path.join(self.stock, f'{TICKER}_qfq.csv'), index=False)
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')) as command, contextlib.redirect_stdout(io.StringIO()):
            failure = cdu.check_and_update_item(TICKER, 'indicators', os.path.basename(path), 'offline', EXPECTED, self.stock)
        command.assert_called_once()
        self.assertIn('指标来源版本无效', failure)
        def recompute(command):
            refreshed = qfq.copy()
            for column in REQUIRED_INDICATORS:
                refreshed[column] = 1.0
            write_indicators(refreshed, TICKER, data_dir=self.root)
            return True, ''
        with mock.patch.object(cdu, 'run_command', side_effect=recompute), contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(cdu.check_and_update_item(TICKER, 'indicators', os.path.basename(path), 'offline', EXPECTED, self.stock))


if __name__ == '__main__':
    unittest.main()
