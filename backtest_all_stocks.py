# backtest_all_stocks.py
# 批量回测所有股票 + 每日监控
# --mode full:   严格多头排列 (MA5>MA10>MA20>MA60)
# --mode simple: 宽松多头排列 (MA5>MA20)
#
# 参数统一来自 strategy_params；每只股票的产物由引擎按 backtest_artifacts 命名落盘，
# 文件名与 _meta.json 带策略、参数指纹、行情截止日和行情内容指纹。监控读取时同时校验
# 期望行情截止日、元数据与行情指纹，取不到就明确报「数据过期/缺失」，不再回退到旧文件，
# 也不再把回测末行成交价当当前价。
#
# 监控状态按工作区规则（AGENTS 8.1）输出：
# * 持仓且入场日 == 最新交易日 -> 可入场（买入当天），否则按趋势结束/回撤给"持有"类标签；
# * 空仓且离场日在冷却期（3 个交易日）内 -> 观望；
# * 空仓且冷却已过：趋势确认成立 -> 可入场，否则 -> 观望。
from __future__ import annotations

import argparse
import json
import hashlib
import os
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from config import DATA_DIR
except ImportError:  # pragma: no cover - 允许脱离 Flask 单独运行
    DATA_DIR = "./data"

import backtest_artifacts
from strategy_params import describe, get_params
from trend_following_backtest import TrendFollowingStrategy

# 监控状态机（AGENTS 8.1）
MONITOR_STATUSES = ('可入场', '持有', '观望')

SUMMARY_COLUMNS = [
    'ticker', 'company_name', 'strategy', 'params_sha1', 'data_asof',
    'total_trades', 'win_rate', 'avg_profit', 'max_profit', 'max_loss',
    'total_return', 'final_value', 'stop_loss_count', 'trailing_stop_count',
    'trend_end_count',
]


class MonitorDataError(RuntimeError):
    """监控所需数据过期、缺失或身份不明时抛出，必须显式报告。"""


def get_all_stocks():
    """从关注列表获取股票代码"""
    try:
        from watchlist import WATCHLIST
        stocks = [item[0] for item in WATCHLIST]
        print(f"从关注列表读取到 {len(stocks)} 只股票")
        return sorted(stocks)
    except ImportError:
        print("警告：未找到 watchlist.py，将从 data 目录获取股票")
        # 降级方案：从data目录获取
        stocks = []
        if os.path.exists(DATA_DIR):
            for item in os.listdir(DATA_DIR):
                item_path = os.path.join(DATA_DIR, item)
                if os.path.isdir(item_path):
                    indicators_file = os.path.join(item_path, f"{item}_indicators.csv")
                    if os.path.exists(indicators_file):
                        stocks.append(item)
        return sorted(stocks)


def get_company_name(ticker):
    """获取股票的公司简称"""
    company_file = os.path.join(DATA_DIR, ticker, f"{ticker}_company_basic.json")
    if os.path.exists(company_file):
        try:
            with open(company_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'basic_info' in data and '公司简称' in data['basic_info']:
                    return data['basic_info']['公司简称']
        except Exception:
            pass
    return ticker



def expected_trade_date(stocks):
    # 共同门槛由 18:00 发布切点确定，不能被单只股票提前发布的当日线抬高。
    from check_data_updates import get_expected_trade_date
    value = get_expected_trade_date(stocks)
    if value > datetime.now().date():
        raise MonitorDataError('行情日期在未来，拒绝生成当前报告')
    return value.strftime('%Y%m%d')


def source_manifest(stocks, asof):
    manifest = {}
    for ticker in sorted(stocks):
        value = backtest_artifacts.source_manifest(ticker, data_dir=DATA_DIR)
        actual = value['data_asof']
        if actual < asof:
            raise MonitorDataError(f'源数据截止 {actual}，未达到期望交易日 {asof}')
        if actual > datetime.now().strftime('%Y%m%d'):
            raise MonitorDataError(f'源数据日期 {actual} 在未来')
        manifest[ticker] = value
    return manifest


def _file_sha256(path):
    with open(path, 'rb') as stream:
        return hashlib.sha256(stream.read()).hexdigest()


def write_report_meta(path, kind, mode, asof, stocks, failures=None, expected_manifest=None, actual_params=None):
    failures = list(failures or [])
    manifest = {}
    try:
        manifest = source_manifest(stocks, asof)
        if expected_manifest is not None and manifest != expected_manifest:
            failures.append('计算期间源版本已改变，请重跑')
    except Exception as exc:
        failures.append(str(exc))
    valid = bool(stocks) and not failures
    params = get_params(mode) if actual_params is None else dict(actual_params)
    meta = dict(schema=2, kind=kind, strategy=mode, data_asof=asof,
                params=params, params_sha1=backtest_artifacts.params_fingerprint(params),
                source_manifest=manifest, tickers=sorted(stocks), valid=valid, void=not valid,
                status='completed' if valid else 'failed', failures=failures,
                generated_at=datetime.now().isoformat(), report_sha256=_file_sha256(path))
    meta_path = backtest_artifacts.meta_path(path)
    with open(meta_path + '.tmp', 'w', encoding='utf-8') as stream:
        json.dump(meta, stream, ensure_ascii=False, indent=2)
    os.replace(meta_path + '.tmp', meta_path)
    return meta


def validate_report_file(path, kind, mode, asof, stocks):
    with open(backtest_artifacts.meta_path(path), encoding='utf-8') as stream:
        meta = json.load(stream)
    params = get_params(mode)
    if not (meta.get('schema') == 2 and meta.get('kind') == kind and
            meta.get('strategy') == mode and
            (meta.get('data_asof') == asof or (kind == 'chart' and
             asof <= str(meta.get('data_asof', '')) <= datetime.now().strftime('%Y%m%d'))) and
            meta.get('valid') is True and meta.get('void') is False and
            meta.get('status') == 'completed' and meta.get('failures') == [] and
            meta.get('tickers') == sorted(stocks) and bool(stocks) and
            meta.get('params') == params and
            meta.get('params_sha1') == backtest_artifacts.params_fingerprint(params) and
            meta.get('report_sha256') == _file_sha256(path)):
        raise MonitorDataError('报告身份、参数、状态或内容校验失败，请重跑回测')
    if meta.get('source_manifest') != source_manifest(stocks, asof):
        raise MonitorDataError('报告源版本不匹配，请重跑回测')
    return meta


class BatchResults(list):
    pass

def run_batch_backtest(mode='full', asof=None):
    """批量回测所有股票，逐票落盘带策略/参数/行情截止日的产物。"""
    stocks = get_all_stocks()
    mode_label = '严格多头排列' if mode == 'full' else '宽松多头排列'
    params = get_params(mode)
    params_sha1 = backtest_artifacts.params_fingerprint(params)
    print(f"找到 {len(stocks)} 只股票")
    print(f"\n📌 策略模式: {mode_label} ({mode})，参数指纹: {params_sha1}")
    print(describe(mode))

    results = BatchResults()
    results.stocks = list(stocks)
    results.asof = asof or expected_trade_date(stocks)
    results.failures = []
    results.source_manifest = {}
    timestamp = datetime.now().strftime('%Y%m%d')

    for ticker in stocks:
        print(f"\n=== 分析 {ticker} ===")

        try:
            results.source_manifest.update(source_manifest([ticker], results.asof))
            strategy = TrendFollowingStrategy(ticker, mode=mode)
            if strategy.load_data():
                actual_asof = backtest_artifacts.data_asof_from_frame(strategy.data)
                if actual_asof != results.source_manifest[ticker]['data_asof']:
                    raise MonitorDataError("加载行情截止日与来源快照不一致")
                trades = strategy.run_backtest(initial_capital=1000000, position_ratio=0.8)

                # 保存交易信号（零交易也会写空结果，覆盖旧结论）
                strategy.save_trades_to_csv()
                data_asof = backtest_artifacts.data_asof_from_frame(strategy.data)

                # 生成回测图表
                stock_dir = os.path.join(DATA_DIR, ticker)
                os.makedirs(stock_dir, exist_ok=True)
                # 图表也带策略标识，避免 full/simple 互相覆盖
                plot_path = os.path.join(stock_dir, f"{ticker}_backtest_{mode}_{timestamp}.png")
                if os.path.exists(plot_path):
                    write_report_meta(plot_path, 'chart', mode, results.asof, [ticker],
                                      failures=['本次图表正在重建'], actual_params=strategy.p)
                figure = strategy.plot_results(save_path=plot_path)
                if figure is not None and os.path.isfile(plot_path):
                    chart_meta = write_report_meta(
                        plot_path, 'chart', mode, results.asof, [ticker],
                        expected_manifest={ticker: results.source_manifest[ticker]},
                        actual_params=strategy.p)
                    if not chart_meta['valid']:
                        raise MonitorDataError('图表源身份在计算期间变化')
                elif trades:
                    raise MonitorDataError('应生成的回测图表缺失')

                if trades and len(trades) > 0:
                    profits = [t['profit'] for t in trades]
                    win_trades = [t for t in trades if t['profit'] > 0]

                    result = {
                        'ticker': ticker,
                        'company_name': get_company_name(ticker),
                        'strategy': mode,
                        'params_sha1': backtest_artifacts.params_fingerprint(strategy.p),
                        'data_asof': data_asof,
                        'total_trades': len(trades),
                        'win_rate': len(win_trades) / len(trades) * 100,
                        'avg_profit': float(np.mean(profits)),
                        'max_profit': max(profits),
                        'max_loss': min(profits),
                        'total_return': float((strategy.data['portfolio_value'].iloc[-1] - 1000000) / 1000000 * 100),
                        'final_value': float(strategy.data['portfolio_value'].iloc[-1]),
                        'stop_loss_count': sum(1 for t in trades if t['type'] == 'stop_loss'),
                        'trailing_stop_count': sum(1 for t in trades if t['type'] == 'trailing_stop'),
                        'trend_end_count': sum(1 for t in trades if t['type'] == 'trend_end'),
                    }
                    results.append(result)

                    print(f"总收益率: {result['total_return']:.2f}%")
                    print(f"交易次数: {result['total_trades']}")
                    print(f"胜率: {result['win_rate']:.2f}%")
                else:
                    print("无交易信号（已写入空结果，旧结果不再冒充最新）")
            else:
                results.failures.append(f"{ticker}: 加载数据失败")
                print("加载数据失败")
        except Exception as e:
            results.failures.append(f"{ticker}: {e}")
            print(f"分析失败: {str(e)}")

    return results


def write_summary(results, mode='full'):
    """写批量汇总 CSV 与同名 _meta.json；本期零结果也写表头。"""
    timestamp = datetime.now().strftime('%Y%m%d')
    # 文件名带策略，避免 full / simple 同一天互相覆盖
    result_path = os.path.join(DATA_DIR, f"backtest_results_{mode}_{timestamp}.csv")
    params = get_params(mode)
    params_sha1 = backtest_artifacts.params_fingerprint(params)

    df = pd.DataFrame(results) if results else pd.DataFrame(columns=SUMMARY_COLUMNS)
    for col in SUMMARY_COLUMNS:
        if col not in df.columns:
            df[col] = None
    df = df[SUMMARY_COLUMNS]

    tmp = result_path + '.tmp'
    df.to_csv(tmp, index=False, encoding='utf-8-sig')
    os.replace(tmp, result_path)

    stocks = getattr(results, 'stocks', None) or get_all_stocks()
    asof = getattr(results, 'asof', None) or expected_trade_date(stocks)
    failures = list(getattr(results, 'failures', []))
    batch_manifest = getattr(results, 'source_manifest', {})
    for row in results:
        ticker = row.get('ticker')
        actual_asof = batch_manifest.get(ticker, {}).get('data_asof')
        # asof 是全批最低时效门槛；每行必须精确匹配本轮该股来源日期。
        if (row.get('strategy') != mode or not actual_asof or actual_asof < asof or
                row.get('data_asof') != actual_asof or
                row.get('params_sha1') != params_sha1 or ticker not in stocks):
            failures.append(f'{ticker}: 汇总行身份与本轮来源快照不一致')
    if not isinstance(results, BatchResults):
        failures.append('汇总缺少批次完成状态')
    meta = write_report_meta(result_path, 'batch_summary', mode, asof, stocks, failures,
                             getattr(results, 'source_manifest', None))
    meta_path = backtest_artifacts.meta_path(result_path)
    df.attrs['valid'] = meta['valid']

    print(f"\n📁 结果已保存到: {result_path}")
    print(f"   结果元信息: {meta_path}（策略 {mode}，参数指纹 {params_sha1}）")
    return df


def analyze_results(results, mode='full'):
    """分析回测结果并落盘汇总（零结果也写表头）。"""
    df = write_summary(results, mode=mode)
    if not results:
        print("没有回测结果")
        return df

    print("\n" + "="*80)
    print(f"📊 批量回测结果统计（策略 {mode}）")
    print("="*80)

    # 整体统计
    print(f"\n总股票数: {len(df)}")
    print(f"盈利股票数: {len(df[df['total_return'] > 0])} ({len(df[df['total_return'] > 0])/len(df)*100:.1f}%)")
    print(f"平均收益率: {df['total_return'].mean():.2f}%")
    print(f"平均胜率: {df['win_rate'].mean():.2f}%")
    print(f"平均交易次数: {df['total_trades'].mean():.1f}")

    # 表现最好的股票
    top_stocks = df.sort_values('total_return', ascending=False).head(5)
    print("\n🏆 表现最佳的5只股票:")
    for _, row in top_stocks.iterrows():
        print(f"  {row['ticker']}: 收益率 {row['total_return']:.2f}%, 胜率 {row['win_rate']:.1f}%, 交易 {int(row['total_trades'])}次")

    # 表现最差的股票
    worst_stocks = df.sort_values('total_return').head(5)
    print("\n💀 表现最差的5只股票:")
    for _, row in worst_stocks.iterrows():
        print(f"  {row['ticker']}: 收益率 {row['total_return']:.2f}%, 胜率 {row['win_rate']:.1f}%, 交易 {int(row['total_trades'])}次")

    # 离场类型分析
    print("\n📈 离场类型分布:")
    total_stop_loss = df['stop_loss_count'].sum()
    total_trailing = df['trailing_stop_count'].sum()
    total_trend_end = df['trend_end_count'].sum()
    total = total_stop_loss + total_trailing + total_trend_end

    if total > 0:
        print(f"  止损离场: {total_stop_loss}次 ({total_stop_loss/total*100:.1f}%)")
        print(f"  移动止盈: {total_trailing}次 ({total_trailing/total*100:.1f}%)")
        print(f"  趋势结束: {total_trend_end}次 ({total_trend_end/total*100:.1f}%)")

    # 策略有效性分析
    profitable = df[df['total_return'] > 0]
    avg_profit_win = profitable['avg_profit'].mean()
    avg_loss_lose = df[df['total_return'] <= 0]['avg_profit'].mean()

    print("\n📊 盈亏比分析:")
    print(f"  盈利股票平均收益: {avg_profit_win:.2f}%")
    print(f"  亏损股票平均亏损: {avg_loss_lose:.2f}%")

    return df


def generate_suggestions(df):
    """生成优化建议"""
    if df is None or len(df) == 0:
        print("没有可分析的回测结果，跳过优化建议")
        return

    print("\n" + "="*80)
    print("💡 策略优化建议")
    print("="*80)

    avg_win_rate = df['win_rate'].mean()
    avg_return = df['total_return'].mean()

    suggestions = []

    if avg_win_rate < 40:
        suggestions.append("⚠️ 胜率偏低(<40%)，建议：")
        suggestions.append("   - 提高ADX入场阈值，过滤弱趋势")
        suggestions.append("   - 增加量能要求，确保突破有效性")
        suggestions.append("   - 缩短趋势确认天数，减少延迟")

    if avg_return < 50:
        suggestions.append("\n⚠️ 整体收益偏低，建议：")
        suggestions.append("   - 优化止损参数，减少不必要的止损")
        suggestions.append("   - 调整移动止盈参数，让利润奔跑")
        suggestions.append("   - 考虑多时间周期确认")

    top_performer = df.sort_values('total_return', ascending=False).iloc[0]
    if top_performer['total_return'] > 100:
        suggestions.append(f"\n⭐ 优秀案例: {top_performer['ticker']}")
        suggestions.append(f"   - 收益率: {top_performer['total_return']:.2f}%")
        suggestions.append(f"   - 胜率: {top_performer['win_rate']:.1f}%")
        suggestions.append("   - 分析该股票特征，推广到其他股票")

    worst_performer = df.sort_values('total_return').iloc[0]
    if worst_performer['total_return'] < -30:
        suggestions.append(f"\n💀 问题案例: {worst_performer['ticker']}")
        suggestions.append(f"   - 收益率: {worst_performer['total_return']:.2f}%")
        suggestions.append(f"   - 交易次数: {int(worst_performer['total_trades'])}")
        suggestions.append("   - 分析失败原因，调整参数")

    for suggestion in suggestions:
        print(suggestion)


def _position_state(signals):
    """从回测信号表判断当前持仓状态。

    final_close 表示回测期末仍持仓，最后一条 sell 记录不代表已经离场。
    """
    state = {
        'holding': False, 'entry_date': None, 'entry_price': None,
        'last_exit_date': None, 'last_exit_type': None,
    }
    if signals is None or len(signals) == 0:
        return state

    last = signals.iloc[-1]
    signal_type = str(last.get('signal_type'))
    exit_type = str(last.get('exit_type'))
    if signal_type == 'sell':
        if exit_type == 'final_close':
            buys = signals[signals['signal_type'] == 'buy']
            if len(buys) == 0:
                return state
            last_buy = buys.iloc[-1]
            state['holding'] = True
            state['entry_date'] = pd.to_datetime(last_buy['date']).to_pydatetime()
            state['entry_price'] = float(last_buy['price'])
            return state
        state['last_exit_date'] = pd.to_datetime(last['date']).to_pydatetime()
        state['last_exit_type'] = exit_type
        return state
    if signal_type == 'buy':
        state['holding'] = True
        state['entry_date'] = pd.to_datetime(last['date']).to_pydatetime()
        state['entry_price'] = float(last['price'])
    return state


def _latest_artifact(ticker, mode, actual_asof, expect_fingerprint, params, manifest):
    return backtest_artifacts.latest(
        ticker, strategy=mode, data_asof=actual_asof, require_meta=True,
        expect_fingerprint=expect_fingerprint, expect_params=params,
        expect_source_manifest=manifest)


def _monitor_state(ticker, mode, expected_asof):
    """计算单只股票的监控状态；数据过期/缺失时抛 MonitorDataError。"""
    strategy = TrendFollowingStrategy(ticker, mode=mode)
    if not strategy.load_data():
        raise MonitorDataError('指标文件缺失，无法监控')
    strategy._generate_signals()
    df = strategy.data
    actual_asof = df['date'].iloc[-1].strftime('%Y%m%d')
    if expected_asof and actual_asof < str(expected_asof):
        raise MonitorDataError(f'行情数据过期：期望截止 {expected_asof}，实际 {actual_asof}')

    provenance = source_manifest([ticker], expected_asof)[ticker]
    if provenance['data_asof'] != actual_asof:
        raise MonitorDataError('加载行情截止日与来源快照不一致')
    expect_fingerprint = backtest_artifacts.fingerprint_frame(df)

    # 只接受与当前行情截止日一致、元数据可核、行情指纹匹配的产物
    try:
        info = _latest_artifact(ticker, mode, actual_asof, expect_fingerprint,
                                strategy.p, provenance)
    except backtest_artifacts.StaleArtifactError as exc:
        raise MonitorDataError(str(exc))
    meta = info.get('meta')
    if not meta:
        raise MonitorDataError(f'回测产物缺少元信息（旧格式）：{info["filename"]}，请重跑回测')
    expected_sha1 = backtest_artifacts.params_fingerprint(strategy.p)
    if meta.get('params_sha1') != expected_sha1:
        raise MonitorDataError(
            f'回测产物参数与当前预设不一致（产物 {meta.get("params_sha1")}，当前 {expected_sha1}），请重跑回测')
    try:
        signals = backtest_artifacts.load_signals(info['path'])
    except Exception as exc:
        raise MonitorDataError(f'回测产物无法解析：{info["filename"]}（{exc}），请重跑回测')

    latest = df.iloc[-1]
    current_price = float(latest['close'])
    current_date = latest['date']
    trend_ended = int(latest['trend_ended']) if pd.notna(latest['trend_ended']) else 0
    trend_confirmed = int(latest['trend_confirmed']) if pd.notna(latest['trend_confirmed']) else 0
    adx = float(latest['ADX']) if pd.notna(latest['ADX']) else float('nan')
    macd_hist = float(latest['MACD_hist']) if pd.notna(latest['MACD_hist']) else float('nan')

    state = _position_state(signals)
    cooldown = int(strategy.p['reentry_cooldown_days'])

    row = {
        'ticker': ticker,
        'company_name': get_company_name(ticker),
        'strategy': mode,
        'data_asof': actual_asof,
        'current_date': current_date.strftime('%Y-%m-%d'),
        'current_price': current_price,
        'ADX': adx,
        'MACD_hist': macd_hist,
        'trend_confirmed': trend_confirmed,
        'trend_ended': trend_ended,
        'entry_date': None,
        'entry_price': None,
        'profit': 0.0,
        'last_exit_date': None,
        'last_exit_type': None,
        'status': None,
        'detail': '',
    }

    if state['holding']:
        entry_date = state['entry_date']
        row['entry_date'] = entry_date.strftime('%Y-%m-%d') if entry_date else 'N/A'
        row['entry_price'] = state['entry_price']
        if state['entry_price']:
            row['profit'] = (current_price - state['entry_price']) / state['entry_price'] * 100
        if entry_date is not None and pd.Timestamp(entry_date) == pd.Timestamp(current_date):
            # 买入当天显示"可入场"，次日起才是"持有"
            row['status'] = '可入场'
            row['detail'] = '买入当日'
        else:
            row['status'] = '持有'
            if trend_ended == 1:
                row['detail'] = '趋势结束预警'
            elif pd.notna(latest['trailing_ma']) and current_price < latest['trailing_ma']:
                row['detail'] = '跌破移动均线'
            else:
                row['detail'] = '趋势延续'
        return row

    if state['last_exit_date'] is not None:
        exit_date = state['last_exit_date']
        row['last_exit_date'] = exit_date.strftime('%Y-%m-%d')
        row['last_exit_type'] = state['last_exit_type']
        matches = df.index[df['date'] == exit_date]
        if len(matches) == 0:
            # 离场K线不在当前数据里（例如数据窗口滚动），按冷却已过处理并注明
            row['detail'] = '离场日期不在当前数据区间，按冷却已过处理'
        else:
            distance = (len(df) - 1) - int(matches[0])
            if distance <= cooldown:
                row['status'] = '观望'
                row['detail'] = f'离场冷却中（第 {distance}/{cooldown} 个交易日）'
                return row

    if trend_confirmed == 1:
        row['status'] = '可入场'
        row['detail'] = row['detail'] or '趋势确认成立'
    else:
        row['status'] = '观望'
        row['detail'] = row['detail'] or '趋势未确认'
    return row


def _format_monitor_line(row):
    if row['status'] == '观望':
        return (f"{row['ticker']:<12} {row['company_name']:<12} {'观望':<6} "
                f"{row['last_exit_date'] or 'N/A':<12} {row['last_exit_type'] or 'N/A':<12} "
                f"{row['current_price']:<9.2f} {row['ADX']:<8.2f} {row['detail']}")
    return (f"{row['ticker']:<12} {row['company_name']:<12} {row['status']:<6} "
            f"{row['entry_date'] or 'N/A':<12} {row['entry_price'] or 0:<9.2f} "
            f"{row['current_price']:<9.2f} {row['profit']:<9.2f} {row['ADX']:<8.2f} {row['detail']}")


def generate_monitor_report(stocks, mode='full', asof=None, write_file=True, failures=None):
    """生成监控报告，按 AGENTS 8.1 输出 可入场/持有/观望 状态。

    只读取与期望行情截止日一致、且策略/参数身份匹配的回测产物；
    取不到就明确报「数据过期/缺失」，绝不静默使用旧文件。
    """
    stocks = list(stocks)
    asof = asof or expected_trade_date(stocks)
    print("\n" + "="*80)
    print(f"📡 实时监控报告（策略 {mode}，期望行情截止 {asof}）")
    print("="*80)

    buckets = {status: [] for status in MONITOR_STATUSES}
    stale = list(failures or [])
    input_manifest = {}

    failed_tickers = {item.get('ticker') for item in stale}
    for ticker in stocks:
        if ticker in failed_tickers:
            continue
        try:
            input_manifest.update(source_manifest([ticker], asof))
            row = _monitor_state(ticker, mode, asof)
        except MonitorDataError as exc:
            stale.append({'ticker': ticker, 'company_name': get_company_name(ticker),
                          'reason': str(exc)})
            print(f"⚠️  {ticker}: 数据过期/缺失 - {exc}")
            continue
        except Exception as exc:  # 单票异常不能拖垮整份监控
            stale.append({'ticker': ticker, 'company_name': get_company_name(ticker),
                          'reason': f'处理异常: {exc}'})
            print(f"❌ {ticker}: 处理异常 - {exc}")
            continue
        buckets[row['status']].append(row)

    buckets['可入场'].sort(key=lambda r: r['ticker'])
    buckets['持有'].sort(key=lambda r: (r['entry_date'] or ''), reverse=True)
    buckets['观望'].sort(key=lambda r: (r['last_exit_date'] or ''), reverse=True)

    print(f"\n📊 可入场（{len(buckets['可入场'])}只）:")
    print("-" * 140)
    if buckets['可入场']:
        print(f"{'股票代码':<12} {'公司简称':<12} {'状态':<6} {'入场日期':<12} {'入场价':<9} {'当前价':<9} {'收益(%)':<9} {'ADX':<8} 说明")
        for row in buckets['可入场']:
            print(_format_monitor_line(row))
    else:
        print("（无）")

    print(f"\n📊 持有（{len(buckets['持有'])}只）:")
    print("-" * 140)
    if buckets['持有']:
        print(f"{'股票代码':<12} {'公司简称':<12} {'状态':<6} {'入场日期':<12} {'入场价':<9} {'当前价':<9} {'收益(%)':<9} {'ADX':<8} 说明")
        for row in buckets['持有']:
            print(_format_monitor_line(row))
    else:
        print("（无）")

    print(f"\n📊 观望（{len(buckets['观望'])}只）:")
    print("-" * 140)
    if buckets['观望']:
        print(f"{'股票代码':<12} {'公司简称':<12} {'状态':<6} {'上次离场':<12} {'离场类型':<12} {'当前价':<9} {'ADX':<8} 说明")
        for row in buckets['观望']:
            print(_format_monitor_line(row))
    else:
        print("（无）")

    # 单股异常已实时写入日志，汇总正文只展示三个交易状态。

    if write_file:
        timestamp = datetime.now().strftime('%Y%m%d')
        # 文件名带策略，避免 full / simple 同一天互相覆盖
        monitor_file = os.path.join(DATA_DIR, f"monitor_report_{mode}_{timestamp}.md")
        with open(monitor_file, 'w', encoding='utf-8') as f:
            f.write("# 📡 实时监控报告\n\n")
            f.write(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"> 策略: {mode}｜期望行情截止: {asof}\n\n")

            for status in MONITOR_STATUSES:
                rows = buckets[status]
                f.write(f"## {status}（{len(rows)}只）\n\n")
                if status == '观望':
                    f.write("| 股票代码 | 公司简称 | 状态 | 上次离场 | 离场类型 | 当前价 | ADX | 说明 |\n")
                    f.write("| :--- | :--- | :--- | :--- | :--- | :---: | :---: | :--- |\n")
                    for row in rows:
                        f.write(f"| {row['ticker']} | {row['company_name']} | {row['status']} | "
                                f"{row['last_exit_date'] or 'N/A'} | {row['last_exit_type'] or 'N/A'} | "
                                f"{row['current_price']:.2f} | {row['ADX']:.2f} | {row['detail']} |\n")
                else:
                    f.write("| 股票代码 | 公司简称 | 状态 | 入场日期 | 入场价 | 当前价 | 收益(%) | ADX | 说明 |\n")
                    f.write("| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |\n")
                    for row in rows:
                        f.write(f"| {row['ticker']} | {row['company_name']} | {row['status']} | "
                                f"{row['entry_date'] or 'N/A'} | {row['entry_price'] or 0:.2f} | "
                                f"{row['current_price']:.2f} | {row['profit']:.2f} | {row['ADX']:.2f} | "
                                f"{row['detail']} |\n")
                f.write("\n")

            # 缺失明细保留在任务日志及元数据，不在监控正文重复列栏。

        meta = write_report_meta(monitor_file, 'monitor', mode, asof, stocks, stale, input_manifest)
        if not meta['valid'] and not stale:
            stale.append({'ticker': '*', 'company_name': '', 'reason': '; '.join(map(str, meta['failures']))})
        print(f"\n📁 监控报告已保存到: {monitor_file}")

    return {'可入场': buckets['可入场'], '持有': buckets['持有'],
            '观望': buckets['观望'], 'stale': stale, 'valid': bool(stocks) and not stale}


def Glob(pattern, path):
    """简单的glob实现"""
    import fnmatch
    matches = []
    if os.path.exists(path):
        for filename in os.listdir(path):
            if fnmatch.fnmatch(filename, pattern):
                matches.append(filename)
    return matches


def main(argv=None):
    parser = argparse.ArgumentParser(description="批量回测所有股票")
    parser.add_argument('--mode', choices=['full', 'simple'], default='full')
    parser.add_argument('--asof', default=None, help='全局期望交易日 YYYYMMDD')
    parser.add_argument('--monitor-only', action='store_true')
    args = parser.parse_args(argv)
    try:
        stocks = get_all_stocks()
        asof = args.asof or expected_trade_date(stocks)
        valid = bool(stocks)
        if not args.monitor_only:
            results = run_batch_backtest(mode=args.mode, asof=asof)
            df = analyze_results(results, mode=args.mode)
            valid = valid and df.attrs.get('valid', False)
            if valid:
                generate_suggestions(df)
        failures = [] if valid else [{'ticker': '*', 'company_name': '', 'reason': '本次批量回测失败或输入为空'}]
        report = generate_monitor_report(stocks, mode=args.mode, asof=asof, failures=failures)
        return 0 if valid and report['valid'] else 2
    except Exception as exc:
        print(f"回测/监控失败: {exc}")
        return 2


if __name__ == '__main__':
    raise SystemExit(main())