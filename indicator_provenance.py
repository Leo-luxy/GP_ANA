"""指标来源协议：原始行情、指标内容、计算代码三者绑定，禁止仅按日期复用。"""
from __future__ import annotations

import importlib.metadata
import json
import os
from datetime import datetime

import pandas as pd

from backtest_artifacts import (MARKET_COLUMNS, atomic_write_csv, atomic_write_json,
                                data_asof_from_frame, file_sha256, fingerprint_frame)

SCHEMA = 1
REQUIRED_INDICATORS = ('ATR', 'ADX', 'MACD_hist', 'RSI', 'BB_lower', 'BB_upper')


class IndicatorProvenanceError(ValueError):
    """缺少来源、内容改变、计算版本改变或业务日期不匹配。"""


def provenance_path(ticker, data_dir):
    return os.path.join(data_dir, ticker, f'{ticker}_indicators_meta.json')


def calculator_version():
    """计算实现或依赖版本改变后必须重算，不复用旧指标。"""
    root = os.path.dirname(os.path.abspath(__file__))
    parts = {}
    for rel in ('utils.py', 'daily/stock_daily_indicator_calculator.py', 'indicator_provenance.py'):
        parts[rel] = file_sha256(os.path.join(root, rel))
    for package in ('numpy', 'pandas', 'TA-Lib'):
        try:
            parts[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            parts[package] = 'unavailable'
    import hashlib
    return hashlib.sha256(json.dumps(parts, sort_keys=True).encode('utf-8')).hexdigest()


def _paths(ticker, data_dir):
    import re
    if not re.fullmatch(r'[0-9]{6}.[A-Z]{2}', str(ticker)):
        raise IndicatorProvenanceError('无效的股票代码')
    if data_dir is None:
        from config import DATA_DIR
        data_dir = DATA_DIR
    base = os.path.join(data_dir, ticker)
    return data_dir, os.path.join(base, f'{ticker}_qfq.csv'), os.path.join(base, f'{ticker}_indicators.csv')


def _read(path):
    return pd.read_csv(path, float_precision='round_trip')


def write_indicators(df, ticker, data_dir=None, source_path=None, expected_source_sha256=None):
    """保存指标并发布来源元数据；输入变化或保存失败会明确抛错。"""
    data_dir, default_source, output = _paths(ticker, data_dir)
    source_path = source_path or default_source
    try:
        before = file_sha256(source_path)
        if expected_source_sha256 is not None and before != expected_source_sha256:
            raise IndicatorProvenanceError('计算期间行情内容已改变，请重新计算')
        source = _read(source_path)
        if set(REQUIRED_INDICATORS) - set(df.columns):
            raise IndicatorProvenanceError('指标缺少引擎必需列')
        if fingerprint_frame(source, MARKET_COLUMNS) != fingerprint_frame(df, MARKET_COLUMNS):
            raise IndicatorProvenanceError('指标OHLCV序列与源行情不一致')
        if file_sha256(source_path) != before:
            raise IndicatorProvenanceError('读取期间行情内容已改变')
        atomic_write_csv(output, df)
        saved = _read(output)
        if fingerprint_frame(source, MARKET_COLUMNS) != fingerprint_frame(saved, MARKET_COLUMNS):
            raise IndicatorProvenanceError('指标落盘后行情序列不一致')
        fingerprint_frame(saved)
        if file_sha256(source_path) != before:
            raise IndicatorProvenanceError('保存期间行情内容已改变')
        meta = {
            'schema': SCHEMA, 'ticker': ticker, 'kind': 'indicators', 'valid': True,
            'source_sha256': before, 'indicators_sha256': file_sha256(output),
            'calculator_version': calculator_version(), 'data_asof': data_asof_from_frame(saved),
            'rows': len(saved), 'generated_at': datetime.now().isoformat(timespec='seconds'),
        }
        atomic_write_json(provenance_path(ticker, data_dir), meta)
        return output
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise IndicatorProvenanceError(f'{ticker}: 指标保存/来源校验失败：{exc}') from exc


def validate_indicators(ticker, data_dir=None, expected_asof=None):
    """验证现有指标及其来源；元数据缺失绝不视为成功。"""
    data_dir, source_path, output = _paths(ticker, data_dir)
    try:
        with open(provenance_path(ticker, data_dir), encoding='utf-8') as fh:
            meta = json.load(fh)
        if not isinstance(meta, dict) or meta.get('schema') != SCHEMA:
            raise IndicatorProvenanceError('指标缺少有效的来源元数据，请重算')
        if meta.get('ticker') != ticker or meta.get('kind') != 'indicators' or meta.get('valid') is not True:
            raise IndicatorProvenanceError('指标元数据身份异常')
        if meta.get('calculator_version') != calculator_version():
            raise IndicatorProvenanceError('指标计算实现版本已变，请重算')
        source_sha, output_sha = file_sha256(source_path), file_sha256(output)
        if meta.get('source_sha256') != source_sha:
            raise IndicatorProvenanceError('源行情内容已变化，即使截止日相同也必须重算指标')
        if meta.get('indicators_sha256') != output_sha:
            raise IndicatorProvenanceError('指标内容与来源元数据不一致，请重算')
        source, indicators = _read(source_path), _read(output)
        if set(REQUIRED_INDICATORS) - set(indicators.columns):
            raise IndicatorProvenanceError('指标缺少引擎必需列')
        if fingerprint_frame(source, MARKET_COLUMNS) != fingerprint_frame(indicators, MARKET_COLUMNS):
            raise IndicatorProvenanceError('指标与源行情OHLCV序列不一致')
        fingerprint_frame(indicators)
        asof = data_asof_from_frame(indicators)
        if meta.get('data_asof') != asof or meta.get('rows') != len(indicators):
            raise IndicatorProvenanceError('指标日期/行数元数据不一致')
        if expected_asof is not None and asof != pd.Timestamp(str(expected_asof)).strftime('%Y%m%d'):
            raise IndicatorProvenanceError(f'行情日期过期：期望 {expected_asof}，实际 {asof}')
        if file_sha256(source_path) != source_sha or file_sha256(output) != output_sha:
            raise IndicatorProvenanceError('校验期间输入文件改变，请重试')
        return meta
    except (OSError, ValueError, TypeError, KeyError) as exc:
        raise IndicatorProvenanceError(f'{ticker}: 指标来源无效：{exc}') from exc
