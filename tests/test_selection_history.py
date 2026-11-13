"""按交易日留存选股结果：复盘预测准确率的前提，不能每天被覆盖。"""
import csv
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest

import pandas as pd
from flask import Flask

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import selection_result_store as store  # noqa: E402
from api import stock_selection as api  # noqa: E402

HEADER = ['股票代码', '入场日期', '入场价格', '当前日期', '当前价格',
          '收益', '离场类型', '数据截止日', '处理时间']


class SelectionHistoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output = os.path.join(self.tmp.name, 'final_holdings.csv')
        self.app = Flask(__name__)
        self.app.register_blueprint(api.stock_selection_bp)
        self.client = self.app.test_client()

    def publish(self, rows, asof='20261112', state='completed', degraded=False):
        frame = pd.DataFrame(rows, columns=HEADER)
        with open(self.output, 'w', encoding='utf-8-sig', newline='') as fh:
            frame.to_csv(fh, index=False)
        with open(self.output, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        status = dict(completed=True, valid=True, void=False, state=state,
                      degraded=degraded, data_asof=asof, holdings=len(rows),
                      processed=len(rows), csv_sha256=digest,
                      finished_at='2026-11-12T16:00:00')
        return status

    @staticmethod
    def row(ticker, asof='20261112'):
        return [ticker, '2026-11-01', '10.0', '2026-11-12', '11.0',
                '10.0', 'final_close', asof, '2026-11-12 16:00:00']

    def test_successful_batch_is_kept_per_trading_day(self):
        status = self.publish([self.row('600000.SH')])
        folder = store.archive_daily(self.output, status)
        self.assertTrue(os.path.isdir(os.path.join(folder)))
        self.assertEqual(os.path.basename(folder), '20261112')
        saved = pd.read_csv(os.path.join(folder, 'final_holdings.csv'), dtype=str)
        self.assertEqual(saved['股票代码'].tolist(), ['600000.SH'])
        with open(os.path.join(folder, 'status.json')) as fh:
            self.assertEqual(json.load(fh)['data_asof'], '20261112')

    def test_second_success_same_day_keeps_final_list_and_run_log(self):
        store.archive_daily(self.output, self.publish([self.row('600000.SH')]))
        store.archive_daily(self.output, self.publish([self.row('600000.SH'),
                                                       self.row('600001.SH')]))
        folder = os.path.join(store.history_dir(self.output), '20261112')
        saved = pd.read_csv(os.path.join(folder, 'final_holdings.csv'), dtype=str)
        self.assertEqual(len(saved), 2)
        with open(os.path.join(folder, 'runs.log')) as fh:
            self.assertEqual(len([l for l in fh if l.strip()]), 2)

    def test_failed_or_void_batch_is_not_archived(self):
        status = self.publish([self.row('600000.SH')])
        status.update(valid=False, void=True, state='failed')
        self.assertIsNone(store.archive_daily(self.output, status))
        self.assertEqual(store.history_index(self.output), [])

    def test_history_index_and_read_round_trip(self):
        store.archive_daily(self.output, self.publish([self.row('600000.SH')], '20261111'))
        store.archive_daily(self.output, self.publish([self.row('600001.SH')], '20261112'))
        dates = [item['date'] for item in store.history_index(self.output)]
        self.assertEqual(dates, ['20261112', '20261111'])
        payload, status = store.read_history(self.output, '20261111')
        rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
        self.assertEqual(rows[0]['股票代码'], '600000.SH')
        self.assertEqual(status['data_asof'], '20261111')

    def test_tampered_archive_is_rejected(self):
        folder = store.archive_daily(self.output, self.publish([self.row('600000.SH')]))
        path = os.path.join(folder, 'final_holdings.csv')
        with open(path, 'a', encoding='utf-8-sig') as fh:
            fh.write('600009.SH,2026-11-01,10,2026-11-12,11,10,final_close,20261112,x\n')
        with self.assertRaises(ValueError):
            store.read_history(self.output, '20261112')

    def test_api_lists_and_serves_history(self):
        original = api.SELECTION_DIR
        api.SELECTION_DIR = self.tmp.name
        self.addCleanup(setattr, api, 'SELECTION_DIR', original)
        store.archive_daily(self.output, self.publish([self.row('600000.SH')]))
        listed = self.client.get('/stock_selection/history').get_json()
        self.assertTrue(listed['success'])
        self.assertEqual(listed['dates'][0]['date'], '20261112')
        self.assertEqual(listed['dates'][0]['holdings'], 1)
        detail = self.client.get('/stock_selection/history/20261112').get_json()
        self.assertTrue(detail['success'])
        self.assertEqual(detail['data'][0]['股票代码'], '600000.SH')
        self.assertTrue(detail['history'])
        self.assertIn('20261112', detail['warnings'][0])
        bad = self.client.get('/stock_selection/history/2026-11-12').get_json()
        self.assertFalse(bad['success'])

    def test_legacy_backfill_does_not_replace_official_archive(self):
        store.archive_daily(self.output, self.publish([self.row('600000.SH')]))
        self.assertIsNone(store.backfill_legacy(self.output))
        with open(os.path.join(store.history_dir(self.output), '20261112',
                               'status.json')) as fh:
            self.assertTrue(json.load(fh).get('valid'))
