"""行情重建、指标来源及引擎输入身份的端到端回归（全程临时目录）。"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np
import pandas as pd

import backtest_artifacts as ba
import indicator_provenance as ip
import trend_following_backtest as engine
from daily import stock_daily_indicator_calculator as calculator


class IndicatorProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name
        self.ticker = '600000.SH'
        self.stock = os.path.join(self.root, self.ticker)
        os.makedirs(self.stock)
        self.source = os.path.join(self.stock, self.ticker + '_qfq.csv')
        self.output = os.path.join(self.stock, self.ticker + '_indicators.csv')
        self.frame = pd.DataFrame({
            'date': pd.bdate_range('2026-01-01', periods=150).strftime('%Y-%m-%d'),
            'open': np.linspace(10, 12, 150), 'high': np.linspace(11, 13, 150),
            'low': np.linspace(9, 11, 150), 'close': np.linspace(10, 12, 150),
            'volume': np.full(150, 1000.),
        })
        self.frame.to_csv(self.source, index=False)
        # 从落盘行情读取，避免构造器和解析器在最后一位的差异。
        self.frame = pd.read_csv(self.source, float_precision='round_trip')
        for col, value in dict(ATR=.5, ADX=30., MACD_hist=1., RSI=50., BB_lower=8., BB_upper=14.).items():
            self.frame[col] = value

    def publish(self):
        return ip.write_indicators(self.frame, self.ticker, self.root)

    def test_valid_source_roundtrip(self):
        self.publish()
        meta = ip.validate_indicators(self.ticker, self.root)
        self.assertEqual(meta['source_sha256'], ba.file_sha256(self.source))
        self.assertEqual(ba.fingerprint_csv(self.output), ba.fingerprint_frame(
            pd.read_csv(self.output, float_precision='round_trip')))
        self.assertEqual(ba.source_manifest(self.ticker, self.root)['source_sha256'], meta['source_sha256'])

    def test_freshness_accepts_newer_indicators_but_still_checks_source(self):
        import check_data_updates as cdu
        from datetime import timedelta
        self.publish()
        actual = pd.Timestamp(self.frame['date'].iloc[-1]).date()
        cutoff = actual - timedelta(days=1)
        rule = cdu.get_freshness_rule('indicators')
        self.assertTrue(cdu.check_file_freshness(self.output, cutoff, rule, 'indicators')[0])
        self.assertFalse(cdu.check_file_freshness(
            self.output, actual + timedelta(days=3), rule, 'indicators')[0])
        market = pd.read_csv(self.source)
        market.loc[0, 'open'] += .1
        market.to_csv(self.source, index=False)
        self.assertFalse(cdu.check_file_freshness(self.output, cutoff, rule, 'indicators')[0])

    def test_same_date_source_change_rejected(self):
        self.publish()
        market = pd.read_csv(self.source, float_precision='round_trip')
        market.loc[0, 'open'] += .1
        market.to_csv(self.source, index=False)
        with self.assertRaises(ip.IndicatorProvenanceError):
            ip.validate_indicators(self.ticker, self.root)

    def test_indicator_change_rejected(self):
        self.publish()
        altered = pd.read_csv(self.output)
        altered.loc[0, 'ATR'] += .1
        altered.to_csv(self.output, index=False)
        with self.assertRaises(ip.IndicatorProvenanceError):
            ip.validate_indicators(self.ticker, self.root)

    def test_source_change_during_calculation_rejected(self):
        digest = ba.file_sha256(self.source)
        with open(self.source, 'a', encoding='utf-8') as fh:
            fh.write('\n')
        with self.assertRaises(ip.IndicatorProvenanceError):
            ip.write_indicators(self.frame, self.ticker, self.root, expected_source_sha256=digest)

    def test_missing_provenance_or_new_calculator_version_rejected(self):
        self.publish()
        with mock.patch.object(ip, 'calculator_version', return_value='new-code'):
            with self.assertRaises(ip.IndicatorProvenanceError):
                ip.validate_indicators(self.ticker, self.root)
        os.remove(ip.provenance_path(self.ticker, self.root))
        with self.assertRaises(ip.IndicatorProvenanceError):
            ip.validate_indicators(self.ticker, self.root)

    def test_different_expected_date_rejected(self):
        self.publish()
        with self.assertRaises(ip.IndicatorProvenanceError):
            ip.validate_indicators(self.ticker, self.root, expected_asof='20261112')

    def test_bogus_input_cannot_be_published(self):
        self.frame.loc[0, 'close'] = 1
        with self.assertRaises(ip.IndicatorProvenanceError):
            self.publish()

    def test_engine_chain_rejects_qfq_rebuild(self):
        self.publish()
        with mock.patch.object(engine, 'DATA_DIR', self.root), mock.patch.object(ba, 'DATA_DIR', self.root), contextlib.redirect_stdout(io.StringIO()):
            strategy = engine.TrendFollowingStrategy(self.ticker, mode='simple')
            self.assertTrue(strategy.load_data())
            strategy.run_backtest()
            path = strategy.save_trades_to_csv()
            info = ba.latest(self.ticker, 'simple', strategy.input_manifest['data_asof'],
                             expect_fingerprint=strategy.input_fingerprint,
                             expect_params=strategy.p, expect_source_manifest=strategy.input_manifest)
            self.assertEqual(info['path'], path)
            self.assertIsNotNone(info['meta']['source_manifest'])
            market = pd.read_csv(self.source)
            market.loc[0, 'open'] += .1
            market.to_csv(self.source, index=False)
            self.assertFalse(engine.TrendFollowingStrategy(self.ticker).load_data())
            with self.assertRaises(ip.IndicatorProvenanceError):
                strategy.save_trades_to_csv()

    def test_calculator_missing_input_returns_failure(self):
        with mock.patch.object(sys, 'argv', ['calc', '--ticker', '000001.SZ', '--input-dir', self.root]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(calculator.main(), 1)

    def test_calculator_save_failure_returns_failure(self):
        with mock.patch.object(sys, 'argv', ['calc', '--ticker', self.ticker, '--input-dir', self.root, '--output-dir', self.root]), mock.patch.object(calculator, 'calculate_technical_indicators', side_effect=lambda df: df), mock.patch.object(calculator, 'save_results', side_effect=OSError('disk failure')), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(calculator.main(), 1)

    def test_calculator_writes_real_provenance(self):
        def compute(df):
            for col in ip.REQUIRED_INDICATORS:
                df[col] = 1.
            return df
        with mock.patch.object(sys, 'argv', ['calc', '--ticker', self.ticker, '--input-dir', self.root, '--output-dir', self.root]), mock.patch.object(calculator, 'calculate_technical_indicators', side_effect=compute), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(calculator.main(), 0)
        self.assertTrue(ip.validate_indicators(self.ticker, self.root)['valid'])


if __name__ == '__main__':
    unittest.main()
