"""选股统一交易日快照：先收齐行情，再选日期，最后隔离计算。"""
import os
import shutil
from datetime import datetime

import pandas as pd
import check_data_updates
import indicator_provenance


class SelectionSnapshotError(ValueError):
    pass


def missing_market_codes(current, previous):
    """保守覆盖门禁：不以小批非空行情冒充当日全市场齐备。

    上一交易日沪深行情作为覆盖基准；缺行即回退，正常停牌也保守回退，
    不以无证据的停牌假设豁免。北交所不在覆盖范围。
    """
    def codes(frame):
        return {str(t) for t in frame['ts_code'] if not str(t).endswith('.BJ')}
    return codes(previous) - codes(current)


# 个别股票停牌/退市导致当日无行情是正常市场状态，不该让全批退回前一天；
# 只有成规模缺失（数据源没发布全）才整批回退。
MAX_SUSPENSION_RATIO = 0.005


def evaluate_market_gap(missing, baseline_count, max_ratio=MAX_SUSPENSION_RATIO):
    """判断当日缺失是否属于可接受的个别停牌，返回 (是否保留当日, 说明)。"""
    if not missing:
        return True, '当日行情覆盖前一交易日全部沪深代码'
    ratio = len(missing) / max(baseline_count, 1)
    detail = '、'.join(sorted(missing)[:5]) + ('…' if len(missing) > 5 else '')
    if ratio <= max_ratio:
        return True, (f'{len(missing)} 只当日无行情（{detail}），占比 {ratio:.2%}，'
                      f'按个别停牌/退市处理，仍使用当日数据')
    return False, (f'{len(missing)} 只缺当日行情，占比 {ratio:.2%}，超过 {max_ratio:.1%}，'
                   f'判为当日数据未齐，整批回退前一交易日')


def previous_trade_asof(asof):
    day = datetime.strptime(asof, '%Y%m%d')
    # 00:00 按发布切点回退一个交易日，并保留交易日历钩子。
    return check_data_updates.get_calendar_trade_date(day).strftime('%Y%m%d')


def read_market(ticker, data_dir):
    path = os.path.join(data_dir, ticker, f'{ticker}_qfq.csv')
    before = check_data_updates.get_last_data_date(path)
    if before is None:
        raise SelectionSnapshotError(f'{ticker}: 行情缺失或日期不可读')
    from backtest_artifacts import file_sha256
    sha = file_sha256(path)
    frame = pd.read_csv(path, float_precision='round_trip')
    dates = pd.to_datetime(frame['date'], errors='raise')
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise SelectionSnapshotError(f'{ticker}: 行情日期缺失、重复或乱序')
    if dates.max() > pd.Timestamp(datetime.now().date()):
        raise SelectionSnapshotError(f'{ticker}: 行情包含未来日期')
    if file_sha256(path) != sha:
        raise SelectionSnapshotError(f'{ticker}: 读取期间行情已变化，请重试')
    return frame, dates.dt.strftime('%Y%m%d'), sha


def choose_batch_asof(tickers, data_dir, requested_asof, force_previous=False):
    """只允许请求日或其前一交易日；不能无限回退到任意旧日期。"""
    missing = []
    for ticker in tickers:
        _, dates, _ = read_market(ticker, data_dir)
        if requested_asof not in set(dates):
            missing.append(ticker)
    # 18点前请求日已经是昨日，不允许再退到前天。
    fallback = (missing or force_previous) and requested_asof == datetime.now().strftime('%Y%m%d')
    chosen = previous_trade_asof(requested_asof) if fallback else requested_asof
    for ticker in tickers:
        _, dates, _ = read_market(ticker, data_dir)
        if chosen not in set(dates):
            raise SelectionSnapshotError(f'{ticker}: 缺少统一交易日 {chosen} 行情，禁止混合日期出结果')
    return chosen, missing


def build_snapshot(tickers, data_dir, snapshot_dir, asof):
    """保留原始行情；快照只包含截至统一日期的历史，并独立绑定指标来源。"""
    os.makedirs(snapshot_dir, exist_ok=False)
    raw_hashes = {}
    for ticker in tickers:
        frame, dates, sha = read_market(ticker, data_dir)
        selected = frame.loc[dates <= asof].copy()
        if selected.empty or dates.loc[selected.index].iloc[-1] != asof:
            raise SelectionSnapshotError(f'{ticker}: 快照未达到统一交易日 {asof}')
        target = os.path.join(snapshot_dir, ticker)
        os.makedirs(target)
        qfq = os.path.join(target, f'{ticker}_qfq.csv')
        if len(selected) == len(frame):
            shutil.copyfile(os.path.join(data_dir, ticker, f'{ticker}_qfq.csv'), qfq)
            # 仅完全相同的来源可复用指标；截断后的指标必须重算。
            try:
                indicator_provenance.validate_indicators(ticker, data_dir, expected_asof=asof)
                for source in (os.path.join(data_dir, ticker, f'{ticker}_indicators.csv'),
                               indicator_provenance.provenance_path(ticker, data_dir)):
                    shutil.copyfile(source, os.path.join(target, os.path.basename(source)))
                indicator_provenance.validate_indicators(ticker, snapshot_dir, expected_asof=asof)
            except (ValueError, OSError):
                pass  # 子进程的来源验证会决定重算，绝不盲目复用。
        else:
            selected.to_csv(qfq, index=False)
        from backtest_artifacts import file_sha256
        if len(selected) == len(frame) and file_sha256(qfq) != sha:
            raise SelectionSnapshotError(f'{ticker}: 复制期间行情已变化')
        raw_hashes[ticker] = sha
    return raw_hashes
