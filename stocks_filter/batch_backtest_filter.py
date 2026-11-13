#!/usr/bin/env python3
# batch_backtest_filter.py
# 功能：批量处理筛选后的股票列表，执行数据获取、指标计算、趋势回测，并筛选出最终持仓股票
#
# 2026-11 修复：最终持仓曾混入 175 天前的旧记录（688981.SH）。根因是按文件名字典序取
# 「最新」回测文件，旧命名里的 simplified 字母 s 大于日期数字 2，于是旧文件永远压过新文件。
# 现在统一走 backtest_artifacts：读取必须显式给出期望的行情截止日，过期就报错。

import os
import sys

# 项目根目录必须最先加入 sys.path：直接以脚本运行时 Python 只会把脚本所在目录
# （stocks_filter/）放进 sys.path，之后的 check_data_updates / config 等根目录模块
# 就会 ModuleNotFoundError，进程以退出码 1 结束，被上层误报成"批筛执行失败"。
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import pandas as pd
import subprocess
import json
import argparse
import hashlib
import uuid
import re
from contextlib import contextmanager
import selection_snapshot
import selection_result_store
from datetime import datetime

import check_data_updates
from config import DATA_DIR
import backtest_artifacts
import indicator_provenance
from strategy_params import get_params

# 最终持仓表头（空结果也要写表头，避免旧文件冒充本期结果）
HOLDING_COLUMNS = [
    '股票代码', '入场日期', '入场价格', '当前日期', '当前价格',
    '收益', '离场类型', '数据截止日', '处理时间',
]

# 本脚本固定使用的策略标识
STRATEGY = 'simple'


class StaleResultError(RuntimeError):
    """回测结果与当前行情不一致时抛出，属于必须中断的错误，不是可跳过的取数失败。"""


def run_command_status(cmd, description):
    """执行命令并返回真实退出码（0 成功，-1 启动异常/超时）。"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"命令: {cmd}")
    print('='*60)
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        print(f"超时: {description}")
        return -1
    except Exception as exc:
        print(f"异常: {description} - {exc}")
        return -1
    if result.returncode == 0:
        print(f"成功: {description}")
        if result.stdout:
            print(f"输出:\n{result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout}")
    else:
        print(f"失败: {description}（returncode={result.returncode}）")
        tail = (result.stderr or result.stdout or '')[-1500:]
        if tail:
            print(f"输出尾部:\n{tail}")
    return result.returncode


def run_command(cmd, description):
    """兼容旧调用：只关心成败。"""
    return run_command_status(cmd, description) == 0


def indicator_asof(ticker):
    """取指标文件最后一根K线的日期，作为期望的行情截止日。"""
    path = os.path.join(DATA_DIR, ticker, f"{ticker}_indicators.csv")
    if not os.path.exists(path):
        return None
    tail = pd.read_csv(path, usecols=['date'])
    if tail.empty:
        return None
    return pd.to_datetime(tail['date'].iloc[-1]).strftime('%Y%m%d')


def qfq_asof(ticker):
    """取前复权行情最后一根K线的日期，用于判断指标是否已经是最新。"""
    path = os.path.join(DATA_DIR, ticker, f"{ticker}_qfq.csv")
    if not os.path.exists(path):
        return None
    try:
        tail = pd.read_csv(path, usecols=['date'])
    except Exception:
        return None
    if tail.empty:
        return None
    return pd.to_datetime(tail['date'].iloc[-1]).strftime('%Y%m%d')


def expected_trade_asof(tickers):
    return pd.Timestamp(check_data_updates.get_expected_trade_date(tickers)).strftime('%Y%m%d')




def normalize_ticker(value):
    if not isinstance(value, str):
        raise ValueError('股票代码必须是字符串')
    match = re.fullmatch(r'([0-9]{6})(?:[.](SH|SZ|BJ))?', value.strip().upper())
    if not match:
        raise ValueError(f'无效股票代码: {value!r}')
    code, suffix = match.groups()
    exchange = 'SH' if code.startswith('6') else ('BJ' if code.startswith(('4', '8', '9')) else 'SZ')
    if code[0] not in '036489' or (suffix and suffix != exchange):
        raise ValueError(f'股票代码与交易所不匹配: {value!r}')
    return f'{code}.{exchange}'


def file_hash(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def get_stock_list(input_file):
    """读取筛选后的股票列表"""
    input_path = input_file if os.path.isabs(input_file) else os.path.join(CURRENT_DIR, input_file)
    if not os.path.exists(input_path):
        print(f"错误：未找到输入文件 {input_path}")
        return None

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False)
    print(f"读取到 {len(df)} 只股票")

    # 确定股票代码列
    code_columns = ['股票代码', 'code', '证券代码', 'stock_code']
    code_col = None
    for col in code_columns:
        if col in df.columns:
            code_col = col
            break

    if code_col is None:
        print("错误：未找到股票代码列")
        return None

    stock_list = list(dict.fromkeys(normalize_ticker(v) for v in df[code_col].tolist()))
    return stock_list


def is_bj_ticker(ticker):
    """北交所不在本项目覆盖范围：不取数、不回测、也不计入失败。"""
    return str(ticker).upper().endswith('.BJ')


def process_single_stock(ticker, skip_data_collection=False, skip_indicators=False, expected_asof=None):
    """处理单只股票：数据获取 -> 指标计算 -> 趋势回测 -> 读取带时效的结果。

    返回 (holding | flat | failed, result_dict | None, expected_asof)。取数/计算失败按既有规则跳过该股票，
    但结果身份异常（过期、身份不明）会抛 StaleResultError 中断整批。
    """
    print(f"\n{'='*80}")
    print(f"开始处理股票: {ticker}")
    print('='*80)

    ticker = normalize_ticker(ticker)
    python = sys.executable or 'python'

    # 1. 获取行情数据（如果未跳过）
    if not skip_data_collection:
        collector = f'"{python}" "{os.path.join(PROJECT_ROOT, "data_collector.py")}"'
        code = run_command_status(f'{collector} --ticker {ticker}', f"获取 {ticker} 行情数据")
        if code == 3:
            # 退出码 3 = 前复权基准变化（除权除息）。增量追加会造假跌，必须用统一基准重建。
            # 重建会备份旧文件、校验行数/日期/OHLC 后原子替换，失败不会动原数据。
            print(f"检测到 {ticker} 前复权基准变化（除权除息），自动重建完整历史")
            rebuild_code = run_command_status(
                f'{collector} --ticker {ticker} --rebuild', f"重建 {ticker} 前复权历史")
            if rebuild_code != 0:
                return ('failed',
                        f'前复权基准变化，自动重建失败（退出码 {rebuild_code}，需人工执行 '
                        f'data_collector.py --ticker {ticker} --rebuild）', None)
        elif code != 0:
            print(f"错误：获取 {ticker} 行情数据失败，跳过该股票（不用旧数据继续回测）")
            return 'failed', f'行情取数失败（退出码 {code}）', None

    # 复用必须验证源内容、指标内容及算法版本，日期相同远远不够。
    meta = None
    market_asof = qfq_asof(ticker)
    expected_asof = expected_asof or expected_trade_asof([ticker])
    if market_asof is None:
        return 'failed', '本地没有可用行情文件', None
    if market_asof > expected_asof:
        raise StaleResultError(f'{ticker}: 行情超出本轮统一截止 {expected_asof}，必须使用截断快照')
    if market_asof < expected_asof:
        # 单只股票行情停更（长期停牌、退市整理等）不应该中断整批：
        # 记为该股失败并写明原因，其余股票照常出结果（整体标记为降级）。
        print(f"错误：{ticker} 行情停更（最后 {market_asof}，全局 {expected_asof}），跳过该股票")
        return 'failed', f'行情停更（最后 {market_asof}）', None
    if skip_indicators:
        try:
            meta = indicator_provenance.validate_indicators(
                ticker, data_dir=DATA_DIR, expected_asof=expected_asof)
        except (ValueError, OSError):
            print('指标来源验证失败，重新计算')
    if meta is None:
        cmd = (
            f'"{python}" "{os.path.join(PROJECT_ROOT, "daily", "stock_daily_indicator_calculator.py")}"'
            f' --ticker {ticker} --input-dir "{DATA_DIR}" --output-dir "{DATA_DIR}"'
        )
        indicator_code = run_command_status(cmd, f"计算 {ticker} 技术指标")
        if indicator_code != 0:
            return 'failed', f'技术指标计算失败（退出码 {indicator_code}）', None
        try:
            meta = indicator_provenance.validate_indicators(
                ticker, data_dir=DATA_DIR, expected_asof=expected_asof)
        except (ValueError, OSError) as exc:
            raise StaleResultError(f'{ticker}: 指标来源校验失败: {exc}') from exc
    if indicator_asof(ticker) != expected_asof:
        raise StaleResultError(f'{ticker}: 指标截止日不等于全局期望 {expected_asof}')
    indicator_path = os.path.join(DATA_DIR, ticker, f"{ticker}_indicators.csv")
    expect_fingerprint = backtest_artifacts.fingerprint_csv(indicator_path)

    # 3. 趋势回测（统一引擎 simple 模式，参数与预设一致）
    # 批量筛选不需要图表：跳过绘图能显著缩短整批耗时
    cmd = (
        f'"{python}" "{os.path.join(PROJECT_ROOT, "trend_following_backtest.py")}"'
        f' --ticker {ticker} --mode {STRATEGY} --no-plot --data-dir "{DATA_DIR}"'
    )
    success = run_command(cmd, f"趋势回测 {ticker}")
    if not success:
        print(f"错误：{ticker} 回测失败，跳过该股票")
        return 'failed', '趋势回测失败', expected_asof

    # 4. 读取回测结果（必须与本次期望截止日、行情内容指纹都一致）
    row = read_backtest_result(ticker, expected_asof, expect_fingerprint, meta['source_sha256'])
    return ('holding' if row else 'flat'), row, expected_asof


def read_backtest_result(ticker, expected_asof, expect_fingerprint=None, source_fingerprint=None):
    """读取与当前行情截止日一致的回测结果，仅筛选 exit_type 为 final_close 的记录。

    严格身份：必须带元数据；给了行情指纹就必须匹配，否则说明行情已重建、
    回测没重跑，旧结果不能用。
    """
    try:
        manifest = backtest_artifacts.source_manifest(ticker, data_dir=DATA_DIR)
        info = backtest_artifacts.latest(
            ticker, strategy=STRATEGY, data_asof=expected_asof,
            allow_stale=False, require_meta=True,
            expect_fingerprint=expect_fingerprint,
            expect_params=get_params(STRATEGY),
            expect_source_fingerprint=source_fingerprint,
            expect_source_manifest=manifest,
        )
    except (backtest_artifacts.StaleArtifactError, ValueError, OSError) as exc:
        # 统一成批筛自己的异常类型，上游只需处理一种错误
        raise StaleResultError(str(exc))
    if info is None:
        raise StaleResultError(f"{ticker}: 没有可用的回测结果")

    try:
        df = backtest_artifacts.load_signals(info['path'])
    except (OSError, ValueError, KeyError) as exc:
        raise StaleResultError(f'{ticker}: 回测CSV读取失败: {exc}') from exc
    print(f"读取回测结果: {info['filename']}（行情截止 {expected_asof}）")

    required = {'exit_type', 'signal_type', 'date', 'price', 'trade_profit'}
    if not required.issubset(df.columns):
        raise StaleResultError(f'{ticker}: 回测结果缺少必要交易列，文件可能损坏')

    # 严格筛选 exit_type 为 final_close 的记录（期末仍在持仓）
    final_trades = df[df['exit_type'] == 'final_close']
    if len(final_trades) == 0:
        print(f"{ticker} 没有 final_close 类型的交易记录（本期空仓收尾）")
        return None

    sells = final_trades[final_trades['signal_type'] == 'sell']
    buys = final_trades[final_trades['signal_type'] == 'buy']
    if len(sells) != 1 or len(buys) != 1:
        raise StaleResultError(f'{ticker}: 期末持仓买卖记录不完整或重复')
    final_sell = sells.iloc[0]
    final_buy = buys.iloc[0]

    # 防伪：期末记录日期必须落在本期数据截止日内，否则说明拿到的是历史片段
    sell_date = pd.to_datetime(final_sell['date']).strftime('%Y%m%d')
    buy_date = pd.to_datetime(final_buy['date']).strftime('%Y%m%d')
    if sell_date != expected_asof or buy_date > expected_asof:
        raise StaleResultError(
            f"{ticker}: 回测结果日期（买 {buy_date} / 卖 {sell_date}）与期望截止日 {expected_asof} 不符"
        )

    return {
        '股票代码': ticker,
        '入场日期': final_buy['date'],
        '入场价格': final_buy['price'],
        '当前日期': final_sell['date'],
        '当前价格': final_sell['price'],
        '收益': final_sell['trade_profit'],
        '离场类型': final_sell['exit_type'],
        '数据截止日': expected_asof,
        '处理时间': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
    }


def atomic_status(status_path, status):
    tmp = status_path + '.' + uuid.uuid4().hex + '.tmp'
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump(status, fh, ensure_ascii=False, indent=2)
        os.replace(tmp, status_path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_holdings(rows, output_path, status_path, status):
    """先作废再发布 CSV + SHA256 绑定状态；中途失败保持不可读取。"""
    pending = dict(status, void=True, valid=False, completed=False,
                   void_reason='结果发布尚未完成')
    atomic_status(status_path, pending)
    df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=HOLDING_COLUMNS)
    df = df.reindex(columns=HOLDING_COLUMNS)
    if len(df):
        df = df.sort_values('入场日期', ascending=False, na_position='last')
    tmp = output_path + '.' + uuid.uuid4().hex + '.tmp'
    try:
        df.to_csv(tmp, index=False, encoding='utf-8-sig')
        with open(tmp, 'rb') as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        os.replace(tmp, output_path)
        status.update(holdings=len(df), output=os.path.basename(output_path),
                      csv_sha256=digest)
        atomic_status(status_path, status)
        selection_result_store.save_result(output_path, status)
        selection_result_store.archive_daily(output_path, status)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return df


def collect_market(ticker):
    """预检阶段先更新全部行情；网络/权限错误不是“尚未发布”，仍然失败。"""
    python = sys.executable
    collector = f'"{python}" "{os.path.join(PROJECT_ROOT, "data_collector.py")}"'
    code = run_command_status(f'{collector} --ticker {ticker}', f'预检更新 {ticker} 行情')
    if code == 3:
        code = run_command_status(f'{collector} --ticker {ticker} --rebuild', f'重建 {ticker} 前复权历史')
    if code:
        raise RuntimeError(f'{ticker}: 行情取数失败（退出码 {code}），未冒充当日未齐')


def prepare_batch(tickers, input_path, requested_asof, skip_data, run_id):
    updated = set()
    def update_pool(pool):
        for i, ticker in enumerate(pool, 1):
            print(f'[{i}/{len(pool)}] 预检行情 {ticker}', flush=True)
            if not skip_data and ticker not in updated:
                collect_market(ticker)
                updated.add(ticker)
    update_pool(tickers)
    chosen, missing = selection_snapshot.choose_batch_asof(tickers, DATA_DIR, requested_asof)
    warnings = []
    if chosen != requested_asof:
        warnings.append(f'{len(missing)} 只未包含 {requested_asof} 行情，整批统一回退 {chosen}，不混用日期')
    # 初筛也必须对应同一天；否则“今日初筛 + 昨日回测”会引入跨日前视。
    for attempt in range(3):
        candidate = pd.read_csv(input_path, dtype=str)
        dates = set(candidate['交易日期'].astype(str)) if '交易日期' in candidate.columns else set()
        # 纯ticker自定义列表没有初筛语义；默认初筛文件必须证明日期。
        if not dates and os.path.basename(input_path) != 'stocks_daily_filtered.csv':
            break
        if dates == {chosen}:
            break
        if os.path.basename(input_path) != 'stocks_daily_filtered.csv':
            raise StaleResultError(f'候选池日期 {sorted(dates)} 与统一日期 {chosen} 不同，请按该日重新初筛')
        print(f'候选池日期变化，按 {chosen} 重建整套初筛', flush=True)
        incomplete = False
        for script, extra in [('step1_daily.py', f' --trade-date {chosen}'),
                              ('step2_daily_basic.py', ''), ('step3_filter.py', '')]:
            cmd = f'"{sys.executable}" "{os.path.join(CURRENT_DIR, script)}"{extra}'
            code = run_command_status(cmd, f'按 {chosen} 重建初筛 {script}')
            if code == 4 and chosen == datetime.now().strftime('%Y%m%d'):
                chosen = selection_snapshot.previous_trade_asof(chosen)
                warnings.append(f'今日初筛数据未齐，整批统一回退 {chosen}')
                incomplete = True
                break
            if code:
                raise RuntimeError(f'{script}: 无法重建 {chosen} 初筛，不混用跨日候选池')
        if incomplete:
            continue
        tickers = [t for t in (get_stock_list(input_path) or []) if not is_bj_ticker(t)]
        if not tickers:
            raise StaleResultError(f'{chosen} 初筛无候选股票')
        check = pd.read_csv(input_path, dtype=str)
        if set(check['交易日期'].astype(str)) != {chosen}:
            raise StaleResultError('重建后的初筛日期仍不一致')
        update_pool(tickers)
        revised, missing = selection_snapshot.choose_batch_asof(tickers, DATA_DIR, chosen)
        if revised != chosen:
            chosen = revised
            warnings.append(f'新候选行情未齐，整批统一回退 {chosen} 并重建初筛')
            continue
        break
    else:
        raise StaleResultError('无法稳定整批候选日期，已停止而非混用')
    # 新候选股票也必须包含冻结的那一天；不允许二次回退到更早日期。
    snapshot_dir = os.path.join(DATA_DIR, '.selection_snapshots', run_id)
    raw_hashes = selection_snapshot.build_snapshot(tickers, DATA_DIR, snapshot_dir, chosen)
    return dict(tickers=tickers, data_asof=chosen, snapshot_dir=snapshot_dir,
                raw_hashes=raw_hashes, warnings=warnings)


@contextmanager
def snapshot_context(directory):
    """批筛独立进程内切换，退出时恢复；真实 data 不会被截断结果覆盖。"""
    global DATA_DIR
    old, old_artifacts = DATA_DIR, backtest_artifacts.DATA_DIR
    try:
        DATA_DIR = directory
        backtest_artifacts.DATA_DIR = directory
        yield
    finally:
        DATA_DIR, backtest_artifacts.DATA_DIR = old, old_artifacts


def main():
    parser = argparse.ArgumentParser(description="批量处理筛选后的股票列表，执行趋势回测并筛选最终持仓")
    parser.add_argument('--input', default='stocks_daily_filtered.csv', help='输入的筛选股票列表文件')
    parser.add_argument('--output', default='final_holdings.csv', help='输出的最终持仓股票文件')
    parser.add_argument('--skip-data', action='store_true', help='跳过数据获取（假设数据已存在）')
    parser.add_argument('--skip-indicators', action='store_true',
                        help='来源内容、指标内容和算法版本校验通过后复用指标，否则重算')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的股票数量（用于测试）')
    parser.add_argument('--asof', help='冻结整批交易日 YYYYMMDD，仅用于已确认的初筛回退')
    args = parser.parse_args()

    print(f"{'='*80}")
    print("批量趋势回测筛选程序")
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")
    print(f"策略: {STRATEGY}")
    print(f"跳过数据获取: {args.skip_data}")
    print(f"处理数量限制: {args.limit if args.limit else '全部'}")
    print('='*80)

    status = {
        'generated_at': datetime.now().isoformat(timespec='seconds'),
        'strategy': STRATEGY,
        'params': get_params(STRATEGY),
        'input_file': os.path.basename(args.input),
        'skip_data': bool(args.skip_data),
        'input_count': 0,
        'processed': 0,      # 只有真正跑完并读到结果的才算处理成功
        'holding': 0,
        'flat': 0,
        'failed': 0,
        'skipped': [],
        'holdings': 0,
        'error': None,
    }

    output_path = os.path.join(CURRENT_DIR, args.output)
    status_path = os.path.splitext(output_path)[0] + '_status.json'
    selection_result_store.preserve_existing(output_path, status_path)
    selection_result_store.preserve_legacy_display(output_path)
    status.update(run_id=uuid.uuid4().hex, completed=False, valid=False,
                  void=True, void_reason='批筛尚未完成', warnings=[], degraded=False)
    atomic_status(status_path, status)
    final_holdings = []
    code = 3
    try:
        try:
            stock_list = get_stock_list(args.input)
            if stock_list:
                stock_list = [normalize_ticker(t) for t in stock_list]
                excluded_bj = [t for t in stock_list if is_bj_ticker(t)]
                stock_list = [t for t in stock_list if not is_bj_ticker(t)]
                status['excluded_bj'] = excluded_bj
                input_path = args.input if os.path.isabs(args.input) else os.path.join(CURRENT_DIR, args.input)
                status['input_sha256'] = file_hash(input_path)
        except Exception as exc:
            stock_list = None
            status['error'] = f'输入读取失败: {exc}'
        if not stock_list or (args.limit is not None and args.limit <= 0):
            code = 1
            status['error'] = status['error'] or '无法获取有效股票列表'
        else:
            if args.limit:
                stock_list = stock_list[:args.limit]
            status['input_count'] = len(stock_list)
            status['input_tickers'] = stock_list
            calendar_asof = expected_trade_asof(stock_list)
            status['calendar_asof'] = calendar_asof
            target_asof = args.asof or calendar_asof
            datetime.strptime(target_asof, '%Y%m%d')
            if target_asof > calendar_asof:
                raise StaleResultError('冻结日期不能晚于18点发布门槛')
            plan = prepare_batch(stock_list, input_path, target_asof, args.skip_data, status['run_id'])
            stock_list = plan['tickers'][:args.limit] if args.limit else plan['tickers']
            status.update(data_asof=plan['data_asof'], input_tickers=stock_list,
                          input_count=len(stock_list), snapshot_dir=plan['snapshot_dir'],
                          raw_source_sha256=plan['raw_hashes'], date_policy='uniform')
            status['input_sha256'] = file_hash(input_path)
            status['warnings'].extend(plan['warnings'])
            status['source_lag'] = plan['data_asof'] != calendar_asof
            print(f'本轮全部股票统一按 {plan["data_asof"]} 计算', flush=True)
            status['source_manifest'] = {}
            with snapshot_context(plan['snapshot_dir']):
                for index, ticker in enumerate(stock_list, 1):
                    print(f'[{index}/{len(stock_list)}] 统一截止 {status["data_asof"]} {ticker}', flush=True)
                    outcome, payload, expected_asof = process_single_stock(
                        ticker, True, args.skip_indicators, status['data_asof'])
                    if outcome in ('holding', 'flat'):
                        if expected_asof != status['data_asof']:
                            raise StaleResultError(f'{ticker}: 回测截止日不是本轮统一日期')
                        manifest = backtest_artifacts.source_manifest(ticker, data_dir=DATA_DIR)
                        if manifest.get('data_asof') != expected_asof:
                            raise StaleResultError(f'{ticker}: 来源截止日与回测不一致')
                        status['source_manifest'][ticker] = manifest
                    if outcome == 'holding' and (str(payload.get('数据截止日')) != expected_asof
                            or pd.Timestamp(payload.get('当前日期')).strftime('%Y%m%d') != expected_asof):
                        raise StaleResultError(f'{ticker}: 持仓行截止日与回测不一致')
                    if outcome == 'holding' and isinstance(payload, dict):
                        final_holdings.append(payload)
                        status['holding'] += 1
                        status['processed'] += 1
                    elif outcome == 'flat' and payload is None:
                        status['flat'] += 1
                        status['processed'] += 1
                    elif outcome == 'failed':
                        status['failed'] += 1
                        reason = payload if isinstance(payload, str) and payload else '数据/指标/回测失败'
                        status['skipped'].append({'ticker': ticker, 'reason': reason})
                    else:
                        raise RuntimeError(f'{ticker}: 无效处理返回值 {outcome}')
            code = 3 if status['failed'] / len(stock_list) >= 0.5 else 0
            if code:
                status['error'] = '全部或至少一半股票处理失败'
    except (StaleResultError, selection_snapshot.SelectionSnapshotError) as exc:
        code = 2
        status['error'] = f'结果身份/时效异常: {exc}'
    except Exception as exc:
        code = 3
        status['error'] = f'批筛异常: {type(exc).__name__}: {exc}'
    # 少量失败仍可发布：名单里的每一行都经过严格身份校验，只是覆盖面少了那几只，
    # 必须标降级并显式列出缺失股票，而不是把整份结果作废（否则缺 1 只就等于没结果）。
    status['degraded'] = bool(status['failed'] and code == 0)
    if status['degraded']:
        missing = status['skipped']
        detail = '；'.join(f"{item['ticker']}：{item['reason']}" for item in missing[:8])
        status['warnings'] = list(status['warnings']) + [
            f'{len(missing)} 只未处理成功（{detail}'
            f'{"…" if len(missing) > 8 else ""}），名单仅含其余已完成校验的股票']
    # --limit 只用于人工诊断：结果天然不完整，绝不能作为当前持仓发布。
    diagnostic = args.limit is not None
    if diagnostic:
        status['limit'] = args.limit
        status['warnings'] = list(status['warnings']) + [
            f'诊断模式仅处理前 {args.limit} 只，结果不作为当前持仓']
        status['error'] = status['error'] or f'诊断模式（--limit {args.limit}），结果不完整'
    status['processed_tickers'] = [t for t in status.get('input_tickers', [])
                                   if t not in {item['ticker'] for item in status['skipped']}]
    status['finished_at'] = datetime.now().isoformat(timespec='seconds')
    status.update(exit_code=code, exit_code_reason=status['error'], completed=True,
                  valid=(code == 0 and not diagnostic),
                  void=(code != 0 or diagnostic),
                  state=('diagnostic' if diagnostic and code == 0 else
                         'failed' if code else
                         'degraded' if status['degraded'] else 'completed'))
    status['void_reason'] = (status['error'] if code else
                             f'诊断模式（--limit {args.limit}）' if diagnostic else None)
    # 无效部分名单不发布为持仓；诊断计数及失败明细保留在状态内。
    write_holdings(final_holdings if status['valid'] else [], output_path, status_path, status)
    print(f"批筛终态: {status['state']}，退出码 {code}")
    if diagnostic:
        print('注意：本次为 --limit 诊断运行，结果已标记为 void，不会被当成当前持仓展示')
    return code


if __name__ == "__main__":
    sys.exit(main())
