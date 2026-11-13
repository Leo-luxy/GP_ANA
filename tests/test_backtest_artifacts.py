"""回测产物身份与批筛读取的回归测试（标准库 unittest）。"""

import json
import os
import sys
import tempfile
import unittest

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import backtest_artifacts  # noqa: E402


def _signals(rows):
    """构造与回测输出同列的最小信号表。"""
    return pd.DataFrame([
        {'date': d, 'price': p, 'signal_type': t, 'trade_profit': g, 'exit_type': e}
        for d, p, t, g, e in rows
    ])


class ArtifactTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.data_dir = self.tmp.name
        self._old = backtest_artifacts.DATA_DIR
        backtest_artifacts.DATA_DIR = self.data_dir
        self.ticker = '600000.SH'
        os.makedirs(os.path.join(self.data_dir, self.ticker), exist_ok=True)

    def tearDown(self):
        backtest_artifacts.DATA_DIR = self._old
        self.tmp.cleanup()


class TestParseAndLatest(ArtifactTestBase):
    def test_parse_new_and_legacy_names(self):
        new = backtest_artifacts.parse_name(
            '300433.SZ_backtest_simple_20261112_20261113T091530.csv')
        self.assertEqual(new['strategy'], 'simple')
        self.assertEqual(new['data_asof'], '20261112')
        self.assertFalse(new['legacy'])

        legacy_full = backtest_artifacts.parse_name('688981.SH_backtest_20261113.csv')
        self.assertEqual(legacy_full['strategy'], 'full')
        self.assertTrue(legacy_full['legacy'])

        legacy_simple = backtest_artifacts.parse_name(
            '688981.SH_backtest_simplified_20260525.csv')
        self.assertEqual(legacy_simple['strategy'], 'simple')
        self.assertEqual(legacy_simple['data_asof'], '20260525')

        self.assertIsNone(backtest_artifacts.parse_name('notes.csv'))
        self.assertIsNone(backtest_artifacts.parse_name('600000.SH_monitor_20261113.csv'))

    def test_latest_selects_by_real_date_not_string_order(self):
        """旧命名 simplified 的字母 s 曾压过新日期，这里必须按真实日期取。"""
        signals = _signals([('2026-05-21', 127.22, 'sell', 0.09, 'final_close')])
        backtest_artifacts.write_result(
            self.ticker, 'simple', {'atr_stop_multiplier': 3.0}, '20260525', signals,
            run_id='20260525T150000')
        signals_new = _signals([('2026-11-12', 66.66, 'sell', -0.02, 'stop_loss')])
        backtest_artifacts.write_result(
            self.ticker, 'simple', {'atr_stop_multiplier': 3.0}, '20261112', signals_new,
            run_id='20261113T091530')

        latest = backtest_artifacts.latest(self.ticker, strategy='simple', allow_any_asof=True)
        self.assertEqual(latest['data_asof'], '20261112')

        # 反向：只有旧文件时，要求新截止日必须报错，而不是退回去用旧的
        info = backtest_artifacts.latest(self.ticker, strategy='simple', data_asof='20260525')
        self.assertEqual(info['data_asof'], '20260525')
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, strategy='simple', data_asof='20261201')

    def test_latest_missing_artifact_raises(self):
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, strategy='full', data_asof='20261112')


class TestWriteResult(ArtifactTestBase):
    def test_meta_contains_identity(self):
        signals = _signals([
            ('2026-04-27', 116.58, 'buy', 0.0, 'final_close'),
            ('2026-11-12', 130.0, 'sell', 0.115, 'final_close'),
        ])
        params = {'atr_stop_multiplier': 3.0, 'adx_threshold': 25}
        csv_path, meta_file = backtest_artifacts.write_result(
            self.ticker, 'full', params, '20261112', signals,
            initial_capital=1000000, position_ratio=0.8, run_id='20261113T091530')

        self.assertTrue(os.path.exists(csv_path))
        self.assertTrue(os.path.exists(meta_file))
        with open(meta_file, 'r', encoding='utf-8') as fh:
            meta = json.load(fh)
        self.assertEqual(meta['strategy'], 'full')
        self.assertEqual(meta['data_asof'], '20261112')
        self.assertEqual(meta['params_sha1'], backtest_artifacts.params_fingerprint(params))
        self.assertEqual(meta['trades'], 1)
        # 文件名带策略与截止日，便于肉眼核对
        self.assertIn('_backtest_full_20261112_', os.path.basename(csv_path))

    def test_zero_trade_still_written(self):
        """本期零交易也要落盘，否则旧结果会继续冒充最新。"""
        csv_path, meta_file = backtest_artifacts.write_result(
            self.ticker, 'simple', {'adx_threshold': 25}, '20261112',
            pd.DataFrame(columns=['date', 'price', 'signal_type', 'trade_profit', 'exit_type']),
            run_id='20261113T091531')
        self.assertTrue(os.path.exists(csv_path))
        with open(meta_file, 'r', encoding='utf-8') as fh:
            self.assertEqual(json.load(fh)['trades'], 0)
        loaded = backtest_artifacts.load_signals(csv_path)
        self.assertEqual(len(loaded), 0)

    def test_rejects_bad_inputs(self):
        with self.assertRaises(ValueError):
            backtest_artifacts.write_result(self.ticker, 'swing', {}, '20261112', pd.DataFrame())
        with self.assertRaises(ValueError):
            backtest_artifacts.write_result(self.ticker, 'full', {}, '2026-11-12', pd.DataFrame())


class TestStrictIdentity(ArtifactTestBase):
    """严格身份：缺元数据、行情指纹不符、不给期望截止日都必须被拒绝。"""

    def _write(self, rows, asof='20261112', fingerprint=None, run_id='20261113T091530'):
        return backtest_artifacts.write_result(
            self.ticker, 'simple', {'atr_stop_multiplier': 3.0}, asof,
            _signals(rows), run_id=run_id, data_fingerprint=fingerprint)

    def test_requires_expected_asof(self):
        self._write([('2026-11-12', 10.0, 'sell', 0.0, 'final_close')])
        with self.assertRaises(ValueError):
            backtest_artifacts.latest(self.ticker, strategy='simple')

    def test_rejects_artifact_without_meta(self):
        csv_path, _ = self._write([('2026-11-12', 10.0, 'sell', 0.0, 'final_close')])
        os.remove(backtest_artifacts.meta_path(csv_path))
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, strategy='simple', data_asof='20261112')
        # allow_legacy 只能放行真正旧命名，不能把新命名的损坏身份当旧格式。
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(
                self.ticker, strategy='simple', data_asof='20261112', allow_legacy=True)
        os.rename(csv_path, os.path.join(self.data_dir, self.ticker,
                                       f'{self.ticker}_backtest_simplified_20261112.csv'))
        legacy = backtest_artifacts.latest(
            self.ticker, strategy='simple', data_asof='20261112', allow_legacy=True)
        self.assertTrue(legacy['legacy'])

    def test_fingerprint_mismatch_rejected(self):
        """行情重建后 data_asof 不变，但价格已变，旧回测必须失效。"""
        self._write([('2026-11-12', 10.0, 'sell', 0.0, 'final_close')],
                    fingerprint='aaaaaaaaaaaaaaaa')
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(
                self.ticker, strategy='simple', data_asof='20261112',
                expect_fingerprint='bbbbbbbbbbbbbbbb')

    def test_fingerprint_match_accepted(self):
        self._write([('2026-11-12', 10.0, 'sell', 0.0, 'final_close')],
                    fingerprint='cccccccccccccccc')
        info = backtest_artifacts.latest(
            self.ticker, strategy='simple', data_asof='20261112',
            expect_fingerprint='cccccccccccccccc')
        self.assertEqual(info['meta']['data_fingerprint'], 'cccccccccccccccc')

    def test_fingerprint_changes_when_price_changes(self):
        df1 = pd.DataFrame({'date': ['2026-11-11', '2026-11-12'],
                            'open': [10., 10.], 'high': [12., 12.], 'low': [8., 8.],
                            'close': [10.0, 11.0], 'volume': [100.0, 120.0]})
        df2 = df1.copy()
        df2.loc[1, 'close'] = 9.0
        self.assertNotEqual(backtest_artifacts.fingerprint_frame(df1),
                            backtest_artifacts.fingerprint_frame(df2))
        self.assertEqual(backtest_artifacts.fingerprint_frame(df1),
                         backtest_artifacts.fingerprint_frame(df1.copy()))


class TestAcceptanceIdentity(ArtifactTestBase):
    def _artifact(self, **kwargs):
        return backtest_artifacts.write_result(
            self.ticker, 'simple', {'atr': 3, 'adx': 25}, '20261112',
            _signals([('2026-11-12', 10., 'sell', 0., 'final_close')]), **kwargs)

    def test_empty_partial_and_old_schema_meta_rejected(self):
        path, meta_path = self._artifact()
        for meta in ({}, {'data_fingerprint': 'x'}, {'schema': 1}):
            with self.subTest(meta=meta):
                with open(meta_path, 'w', encoding='utf-8') as fh:
                    json.dump(meta, fh)
                with self.assertRaises(backtest_artifacts.StaleArtifactError):
                    backtest_artifacts.latest(self.ticker, 'simple', '20261112')

    def test_params_tamper_and_expectation_rejected(self):
        path, meta_path = self._artifact()
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, 'simple', '20261112', expect_params={'atr': 99})
        with open(meta_path, encoding='utf-8') as fh:
            meta = json.load(fh)
        meta['params']['atr'] = 99
        with open(meta_path, 'w', encoding='utf-8') as fh:
            json.dump(meta, fh)
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, 'simple', '20261112')

    def test_csv_tamper_rejected(self):
        path, _ = self._artifact()
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('tampered')
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, 'simple', '20261112')

    def test_stale_option_does_not_remove_expected_date_requirement(self):
        with self.assertRaises(ValueError):
            backtest_artifacts.latest(self.ticker, allow_stale=True)

    def test_no_fallback_from_invalid_newest(self):
        self._artifact(run_id='20261113T120000')
        _, meta_path = self._artifact(run_id='20261113T120001')
        with open(meta_path, 'w', encoding='utf-8') as fh:
            fh.write('{}')
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, 'simple', '20261112')

    def test_unique_runs_and_explicit_collision_refused(self):
        one, _ = self._artifact()
        two, _ = self._artifact()
        self.assertNotEqual(one, two)
        self.assertIsNotNone(backtest_artifacts.parse_name(os.path.basename(one)))
        self._artifact(run_id='20261113T120001')
        with self.assertRaises(FileExistsError):
            self._artifact(run_id='20261113T120001')

    def test_source_manifest_required_when_expected(self):
        self._artifact(source_manifest={'source_sha256': 'one'})
        with self.assertRaises(backtest_artifacts.StaleArtifactError):
            backtest_artifacts.latest(self.ticker, 'simple', '20261112',
                                     expect_source_manifest={'source_sha256': 'two'})

    def test_ohlcv_and_indicator_precision_changes_invalidate(self):
        frame = pd.DataFrame([{'date': '2026-11-12', 'open': 10., 'high': 12.,
                               'low': 8., 'close': 11., 'volume': 100., 'ATR': 1.23456789}])
        original = backtest_artifacts.fingerprint_frame(frame)
        for col in ('open', 'high', 'low', 'close', 'volume', 'ATR'):
            with self.subTest(col=col):
                altered = frame.copy()
                altered.loc[0, col] += 0.00000001
                self.assertNotEqual(original, backtest_artifacts.fingerprint_frame(altered))
        with self.assertRaises(ValueError):
            backtest_artifacts.fingerprint_frame(frame.drop(columns=['open']))

    def test_params_numeric_roundtrip(self):
        self.assertEqual(backtest_artifacts.params_fingerprint({'a': 3}),
                         backtest_artifacts.params_fingerprint({'a': 3.0}))


class TestDataAsof(unittest.TestCase):
    def test_data_asof_from_frame(self):
        df = pd.DataFrame({'date': ['2026-11-10', '2026-11-12'], 'close': [1.0, 2.0]})
        self.assertEqual(backtest_artifacts.data_asof_from_frame(df), '20261112')
        with self.assertRaises(ValueError):
            backtest_artifacts.data_asof_from_frame(pd.DataFrame({'date': []}))


if __name__ == '__main__':
    unittest.main()
