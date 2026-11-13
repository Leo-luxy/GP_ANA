# strategy_optimization.py
# 功能：优化量化交易策略的参数，提高策略性能
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 遍历不同的策略参数组合（RSI买入/卖出阈值、布林带买入/卖出倍数）
# 3. 把样本按时间切成训练段/验证段/测试段分别回测，按验证段表现择优；
#    测试段只作最终未见证据，不参与选参数
# 4. 候选通过门槛要求验证段与测试段收益同时非负，且测试段收益不得明显劣于验证段
# 5. 默认只输出候选参数表 optimization_candidates.csv，不自动改写全局配置
# 6. 只有显式传入 --apply-best 时，才备份原配置并把通过门槛的汇总参数写回 config.py；
#    未通过门槛的候选必须再加 --force-apply 才写，并打印“不可外推”警告
#
# 成交统计口径：
# - 每笔买卖都记入成交账本（date/price/shares/amount/fee/cash_after/reason）
# - 买入按 shares = int(买入预算 / 当日价格) 成交，费用按实际成交额计算，
#   取整余款保留在现金中，不再按整笔预算扣款
# - 胜率、交易次数、平均盈亏、最大单笔盈亏、持仓天数全部由成交账本反算
# - 权益曲线从初始资金起算，包含每笔交易费用与期末清算费用；
#   年化、夏普、最大回撤都基于同一条含费曲线，回撤以初始资金为峰值起点
# - 期末强制平仓会显式记一笔卖出（reason=期末清算），平仓前的浮盈浮亏单独列出

import argparse
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime

import numpy as np
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, STRATEGY_CONFIG, OPTIMIZATION_CONFIG

# 无风险利率（年化），与旧版口径保持一致
RISK_FREE_RATE = 0.03

# 入场/离场原因：统一写进成交账本，便于按真实成交反算统计
ENTER_REASON_SIGNAL = '买入信号'
EXIT_REASON_STOP_LOSS = '止损'
EXIT_REASON_TIME_STOP = '时间止损'

# 时间止损开关。原实现只计算 i - buy_index 却从未用于离场（死代码），修复后默认生效；
# 若需要恢复到“不启用时间止损”的旧行为，把这里改成 False 即可，不需要改其他地方。
ENABLE_TIME_STOP = True
EXIT_REASON_SELL_SIGNAL = '卖出信号'
EXIT_REASON_FINAL = '期末清算'

# 默认只输出候选参数表，绝不默认改写全局配置
DEFAULT_CANDIDATES_PATH = os.path.join('backup', 'optimization', 'optimization_candidates.csv')
DEFAULT_OUTPUT_DIR = os.path.join('backup', 'optimization')

# 三段切分比例：训练 60% / 验证 20% / 测试 20%（按交易日顺序切分，三段不重叠）
DEFAULT_TRAIN_RATIO = 0.6
DEFAULT_VAL_RATIO = 0.2
DEFAULT_TEST_RATIO = 0.2

# 候选应用门槛默认值（收益单位为百分点）：
# - 验证段与测试段收益都不得低于门槛（默认 0，即要求同时非负）
# - 验证段夏普必须严格大于门槛（默认 0，零交易候选无法通过）
# - 测试段收益不得比验证段低超过 DEFAULT_TEST_RETURN_TOLERANCE_PCT 个百分点
DEFAULT_MIN_VAL_RETURN_PCT = 0.0
DEFAULT_MIN_VAL_SHARPE = 0.0
DEFAULT_MIN_TEST_RETURN_PCT = 0.0
DEFAULT_TEST_RETURN_TOLERANCE_PCT = 2.0

# config.py 中 STRATEGY_CONFIG 需要写回的四个参数
CONFIG_PARAM_KEYS = ('rsi_buy_threshold', 'rsi_sell_threshold', 'bb_buy_mult', 'bb_sell_mult')


def _format_config_value(key, value):
    """把参数值格式化成 config.py 里的字面量文本。"""
    if key in ('rsi_buy_threshold', 'rsi_sell_threshold'):
        return str(int(round(float(value))))
    text = f'{float(value):.6f}'.rstrip('0').rstrip('.')
    return text or '0'


def apply_best_to_config(best_params, config_path='config.py', backup_dir='backup', *, force_apply=False):
    """备份后把最优参数写回 config.py 的 STRATEGY_CONFIG，返回备份文件路径。

    这是唯一会改动全局配置的入口，只在显式要求（--apply-best）时调用：
    1. 先校验原文件能定位到 STRATEGY_CONFIG 且四个参数行齐全，缺一个就抛错不写；
    2. 写前把原文件复制到 backup_dir，文件名带时间戳；
    3. 先用 compile() 校验新内容，再原子替换，避免写坏配置。
    """
    if not best_params:
        raise RuntimeError('没有可写入的参数组，拒绝改写配置')
    for key in CONFIG_PARAM_KEYS:
        if key not in best_params or not _is_finite(best_params[key]):
            raise ValueError(f'参数 {key} 缺失或非有限，拒绝改写配置')
    passed = application_passed(best_params)
    if not passed and force_apply is not True:
        raise RuntimeError('候选未通过验证/测试门槛，拒绝改写配置')
    if not passed:
        print('未通过门槛，仅因强制写入，不可外推')
    with open(config_path, 'r', encoding='utf-8') as fh:
        lines = fh.readlines()

    start = None
    end = None
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if start is None and stripped.startswith('STRATEGY_CONFIG') and '=' in stripped:
            start = idx
            continue
        if start is not None and idx > start and stripped.startswith('}'):
            end = idx
            break
    if start is None or end is None:
        raise RuntimeError(f'{config_path} 中未找到 STRATEGY_CONFIG 代码块，拒绝写入')

    patterns = {
        key: re.compile(r"^(?P<prefix>\s*'" + re.escape(key) + r"'\s*:\s*)(?P<value>[^,#\n]+?)(?P<suffix>\s*,.*)?$")
        for key in CONFIG_PARAM_KEYS
    }
    found = {key: False for key in CONFIG_PARAM_KEYS}
    new_lines = list(lines)
    for idx in range(start + 1, end):
        line = lines[idx].rstrip('\n')
        for key, pattern in patterns.items():
            match = pattern.match(line)
            if not match:
                continue
            suffix = match.group('suffix') or ','
            new_lines[idx] = match.group('prefix') + _format_config_value(key, best_params[key]) + suffix + '\n'
            found[key] = True
            break

    missing = [key for key, ok in found.items() if not ok]
    if missing:
        raise RuntimeError(f'{config_path} 的 STRATEGY_CONFIG 缺少参数行 {missing}，拒绝写入')

    new_content = ''.join(new_lines)
    compile(new_content, config_path, 'exec')  # 写前语法校验

    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    backup_path = os.path.join(backup_dir, f'config_{stamp}.py.bak')
    shutil.copy2(config_path, backup_path)

    tmp_path = config_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as fh:
        fh.write(new_content)
    os.replace(tmp_path, config_path)
    return backup_path


def write_candidates_csv(results, output_path=DEFAULT_CANDIDATES_PATH):
    """把参数候选表写成 CSV，返回写入路径；只输出候选，不改全局配置。"""
    if not results:
        return None
    df = pd.DataFrame(results)
    ordered = [
        'ticker',
        'rsi_buy_threshold', 'rsi_sell_threshold', 'bb_buy_mult', 'bb_sell_mult',
        'train_total_return', 'train_sharpe_ratio', 'train_max_drawdown',
        'train_win_rate', 'train_total_trades',
        'val_total_return', 'val_sharpe_ratio', 'val_max_drawdown',
        'val_win_rate', 'val_total_trades',
        'test_total_return', 'test_sharpe_ratio', 'test_max_drawdown',
        'test_win_rate', 'test_total_trades',
        'test_return_gap', 'validation_score', 'passed', 'gate_reason',
    ]
    columns = [col for col in ordered if col in df.columns]
    columns += [col for col in df.columns if col not in columns]
    df = df[columns]
    parent = os.path.dirname(os.path.abspath(output_path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    return output_path


def aggregate_best_params(per_stock_best):
    """多股票汇总：仅按验证候选参数组众数和验证分择优，测试只可否决，不可改选。

    旧实现是逐股优化后立刻复写同一个全局 config.py，最后一只股票的结果会
    覆盖前面所有股票。这里改成先收齐每只股票的候选，再汇总一次。
    """
    rows = [row for row in per_stock_best if row]
    if not rows:
        return None
    # 参数选择必须与测试值、passed 标记完全无关。
    pool = [row for row in rows if _is_finite(row.get('validation_score'))]
    if not pool:
        return None

    def param_key(row):
        return (row.get('rsi_buy_threshold'), row.get('rsi_sell_threshold'),
                row.get('bb_buy_mult'), row.get('bb_sell_mult'))

    groups = {}
    for row in pool:
        groups.setdefault(param_key(row), []).append(row)

    def group_rank(item):
        _, group = item
        scores = [float(r.get('validation_score') or 0.0) for r in group]
        return (len(group), max(scores))

    _, best_group = max(groups.items(), key=group_rank)
    chosen = dict(max(best_group, key=lambda r: float(r.get('validation_score') or 0.0)))
    chosen['stock_count'] = len(best_group)
    chosen['aggregated_from'] = len(rows)
    # 标记必须来自被选中那一行本身：有别的股票通过，不代表这只股票的候选通过
    chosen['passed'] = application_passed(chosen)
    return chosen


def validate_split_ratios(train_ratio, val_ratio, test_ratio):
    """校验三段切分比例：每段必须在 (0, 1) 内，且三者之和为 1。"""
    for name, value in (('train_ratio', train_ratio), ('val_ratio', val_ratio),
                        ('test_ratio', test_ratio)):
        value = float(value)
        if not 0 < value < 1:
            raise ValueError(f'{name} 必须在 (0, 1) 之间，收到 {value!r}')
    total = float(train_ratio) + float(val_ratio) + float(test_ratio)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(f'训练/验证/测试比例之和必须为 1，收到 {total!r}')


def split_three_way(data, train_ratio=DEFAULT_TRAIN_RATIO, val_ratio=DEFAULT_VAL_RATIO,
                    test_ratio=DEFAULT_TEST_RATIO):
    """按交易日顺序把样本切成训练/验证/测试三段，返回 (train, val, test)。

    切分按行数比例取整，三段首尾相接、互不重叠，比例取整后的剩余行归测试段；
    每段至少保留 1 行。比例非法或样本不足 3 行时抛 ValueError。
    """
    validate_split_ratios(train_ratio, val_ratio, test_ratio)
    if data is None:
        raise ValueError('没有可切分的样本')
    total = len(data)
    if total < 3:
        raise ValueError(f'样本不足 3 行，无法切成训练/验证/测试三段（当前 {total} 行）')

    n_train = int(total * float(train_ratio))
    n_val = int(total * float(val_ratio))
    # 保证每段至少 1 行：训练段最多占 total-2 行，验证段最多占剩余行数减 1
    n_train = min(max(n_train, 1), total - 2)
    n_val = min(max(n_val, 1), total - n_train - 1)
    train_end = n_train
    val_end = n_train + n_val
    return data.iloc[:train_end], data.iloc[train_end:val_end], data.iloc[val_end:]


def evaluate_gate(val_metrics, test_metrics,
                  min_val_return=DEFAULT_MIN_VAL_RETURN_PCT,
                  min_val_sharpe=DEFAULT_MIN_VAL_SHARPE,
                  min_test_return=DEFAULT_MIN_TEST_RETURN_PCT,
                  test_return_tolerance=DEFAULT_TEST_RETURN_TOLERANCE_PCT):
    """判断候选是否通过应用门槛，返回 (是否通过, 中文原因)。

    门槛口径（收益单位为百分点）：
    1. 验证段总收益不低于 min_val_return，且验证段夏普严格大于 min_val_sharpe；
    2. 测试段总收益不低于 min_test_return；
    3. 测试段总收益 >= 验证段总收益 - test_return_tolerance，
       即测试段收益不得明显劣于验证段。
    默认门槛为 0，即要求验证段与测试段收益同时非负；夏普仍保留严格大于 0，
    这样零交易候选（收益 0、夏普 0）不会因为“非负”而被误判为通过。
    测试段只在这里作为最终未见证据使用，不参与参数择优。
    """
    required = ((val_metrics, 'total_return'), (val_metrics, 'sharpe_ratio'),
                (test_metrics, 'total_return'))
    if any(key not in metrics or not _is_finite(metrics[key]) for metrics, key in required):
        return False, '门槛指标缺失或非有限值'
    if not all(_is_finite(v) for v in (min_val_return, min_val_sharpe,
                                      min_test_return, test_return_tolerance)):
        return False, '门槛配置必须为有限值'
    # 其他已提供的数值指标也不能携带 NaN/inf。
    if any(not _is_finite(v) for metrics in (val_metrics, test_metrics)
           for v in metrics.values() if not isinstance(v, (list, tuple, dict))):
        return False, '指标包含非有限值'
    val_return = float(val_metrics['total_return'])
    val_sharpe = float(val_metrics['sharpe_ratio'])
    test_return = float(test_metrics['total_return'])
    min_val_return, min_val_sharpe, min_test_return = map(
        float, (min_val_return, min_val_sharpe, min_test_return))
    tolerance = abs(float(test_return_tolerance))

    if val_return < min_val_return:
        return False, f'验证段收益 {val_return:.2f}% 低于门槛 {min_val_return:.2f}%'
    if val_sharpe <= min_val_sharpe:
        return False, f'验证段夏普 {val_sharpe:.4f} 未超过门槛 {min_val_sharpe:.4f}'
    if test_return < min_test_return:
        return False, f'测试段收益 {test_return:.2f}% 低于门槛 {min_test_return:.2f}%'
    gap = test_return - val_return
    if gap < -tolerance:
        return False, (f'测试段收益比验证段低 {abs(gap):.2f} 个百分点，'
                       f'超过容差 {tolerance:.2f} 个百分点')
    return True, '通过'


def _is_finite(value):
    try:
        return not isinstance(value, (bool, np.bool_)) and bool(np.isfinite(float(value)))
    except (TypeError, ValueError, OverflowError):
        return False


def application_passed(candidate):
    """所有写入口共用门禁：拒绝字符串真值和无指标的伪 passed。"""
    flag = candidate.get('passed')
    if not isinstance(flag, (bool, np.bool_)) or not bool(flag):
        return False
    val = {k[4:]: v for k, v in candidate.items() if k.startswith('val_')}
    test = {k[5:]: v for k, v in candidate.items() if k.startswith('test_')
            and k != 'test_return_gap'}
    settings = candidate.get('gate_settings', {})
    allowed = {'min_val_return', 'min_val_sharpe', 'min_test_return', 'test_return_tolerance'}
    if not isinstance(settings, dict) or (settings and set(settings) != allowed):
        return False
    if not evaluate_gate(val, test, **settings)[0]:
        return False
    return all(application_passed(row) for row in candidate.get('evaluation_evidence', []))


def candidate_passed(val_metrics, test_metrics, **kwargs):
    """evaluate_gate 的布尔包装：调用方只关心是否通过门槛时使用。"""
    return evaluate_gate(val_metrics, test_metrics, **kwargs)[0]


class StrategyOptimizer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        # 使用配置文件中的初始资金
        self.initial_capital = STRATEGY_CONFIG['initial_capital']  # 初始资金
        # 资金管理参数
        self.position_size = 0.3  # 每次买入/卖出的资金比例（30%）
        self.max_positions = 3  # 最大持仓批次
        # 交易成本参数
        self.trade_cost = 0.001  # 单边交易成本比例（0.1%）
        # 止损参数
        self.stop_loss_pct = 0.1  # 固定止损比例（10%）
        self.time_stop_days = 30  # 时间止损阈值（持仓超过 30 个交易日离场）

    def load_data(self):
        """读取真实输入，任何失败都显式报错，绝不构造替代行情。"""
        self.data = None
        self.ticker = None
        self.warmup_trim_rows = 0
        try:
            data = pd.read_csv(self.file_path)
            required = ('date', 'close', 'BB_lower', 'BB_upper', 'MA5', 'MA20', 'RSI')
            missing = set(required) - set(data.columns)
            if missing or len(data) < 3:
                raise ValueError(f'缺少字段 {sorted(missing)} 或样本不足3行')
            data['date'] = pd.to_datetime(data['date'], errors='raise')
            if data['date'].isna().any() or data['date'].duplicated().any() or not data['date'].is_monotonic_increasing:
                raise ValueError('日期必须有效、唯一且递增')
            # 行情与日期在完整输入上校验，不允许借指标预热删掉坏行情。
            prices = [key for key in ('open', 'high', 'low', 'close') if key in data]
            for key in prices:
                data[key] = pd.to_numeric(data[key], errors='raise')
                if not np.isfinite(data[key]).all() or (data[key] <= 0).any():
                    raise ValueError(f'{key} 行情必须为有限正数')
            if all(key in data for key in ('open', 'high', 'low', 'close')):
                if ((data['low'] > data[['open', 'close']].min(axis=1)) |
                        (data['high'] < data[['open', 'close']].max(axis=1))).any():
                    raise ValueError('OHLC 区间不合法')
            trim = 0
            for key in required[2:]:
                series = pd.to_numeric(data[key], errors='raise')
                if np.isinf(series).any():
                    raise ValueError(f'{key} 包含无穷值')
                valid = np.flatnonzero(series.notna().to_numpy())
                if not len(valid) or series.iloc[valid[0]:].isna().any():
                    raise ValueError(f'{key} 中间/后缀缺失或全列缺失')
                trim = max(trim, int(valid[0]))
                data[key] = series
            # 仅剔除各 rolling 指标连续的前缀预热区，不填充、不拼造数据。
            if len(data) - trim < 3:
                raise ValueError('剔除预热后样本不足3行')
            data = data.iloc[trim:].copy().reset_index(drop=True)
            self.warmup_trim_rows = trim
            data.attrs['warmup_trim_rows'] = trim
            if trim:
                print(f'  剔除连续前缀指标预热 {trim} 行；保留 {len(data)} 行真实样本')
            self.ticker = (data['ticker'].iloc[0] if 'ticker' in data.columns
                           else os.path.basename(self.file_path).split('_')[0])
            self.data = data
            return data
        except Exception as exc:
            raise ValueError(f'加载数据失败 {self.file_path}: {exc}') from exc

    def calculate_signals(self, rsi_buy_threshold=None, rsi_sell_threshold=None, bb_buy_mult=None, bb_sell_mult=None):
        """计算交易信号"""
        try:
            # 使用配置文件中的默认参数
            if rsi_buy_threshold is None:
                rsi_buy_threshold = STRATEGY_CONFIG['rsi_buy_threshold']
            if rsi_sell_threshold is None:
                rsi_sell_threshold = STRATEGY_CONFIG['rsi_sell_threshold']
            if bb_buy_mult is None:
                bb_buy_mult = STRATEGY_CONFIG['bb_buy_mult']
            if bb_sell_mult is None:
                bb_sell_mult = STRATEGY_CONFIG['bb_sell_mult']

            # 1. 布林带信号
            if 'close' in self.data.columns and 'BB_lower' in self.data.columns:
                self.data['bb_buy_signal'] = (self.data['close'] < self.data['BB_lower'] * bb_buy_mult).astype(int)
            else:
                self.data['bb_buy_signal'] = 0

            if 'close' in self.data.columns and 'BB_upper' in self.data.columns:
                self.data['bb_sell_signal'] = (self.data['close'] > self.data['BB_upper'] * bb_sell_mult).astype(int)
            else:
                self.data['bb_sell_signal'] = 0

            # 2. MA交叉信号
            if 'MA5' in self.data.columns and 'MA20' in self.data.columns:
                self.data['MA5_above_MA20'] = (self.data['MA5'] > self.data['MA20']).astype(int)
                self.data['ma_crossover'] = self.data['MA5_above_MA20'].diff()
                self.data['ma_buy_signal'] = (self.data['ma_crossover'] == 1).astype(int)
                self.data['ma_sell_signal'] = (self.data['ma_crossover'] == -1).astype(int)
            else:
                self.data['MA5_above_MA20'] = 0
                self.data['ma_crossover'] = 0
                self.data['ma_buy_signal'] = 0
                self.data['ma_sell_signal'] = 0

            # 3. RSI信号
            if 'RSI' in self.data.columns:
                self.data['rsi_buy_signal'] = (self.data['RSI'] < rsi_buy_threshold).astype(int)
                self.data['rsi_sell_signal'] = (self.data['RSI'] > rsi_sell_threshold).astype(int)
            else:
                self.data['rsi_buy_signal'] = 0
                self.data['rsi_sell_signal'] = 0

            # 4. 综合信号
            # 买入信号：布林带突破下轨 OR (MA金叉 AND RSI超卖)
            self.data['buy_signal'] = ((self.data['bb_buy_signal'] == 1) |
                                     ((self.data['ma_buy_signal'] == 1) & (self.data['rsi_buy_signal'] == 1))).astype(int)

            # 卖出信号：布林带突破上轨 OR (MA死叉 AND RSI超买)
            self.data['sell_signal'] = ((self.data['bb_sell_signal'] == 1) |
                                      ((self.data['ma_sell_signal'] == 1) & (self.data['rsi_sell_signal'] == 1))).astype(int)

            return self.data
        except Exception as e:
            # 如果计算信号失败，返回默认信号
            print(f"  计算信号失败: {e}")
            # 设置默认信号
            self.data['bb_buy_signal'] = 0
            self.data['bb_sell_signal'] = 0
            self.data['MA5_above_MA20'] = 0
            self.data['ma_crossover'] = 0
            self.data['ma_buy_signal'] = 0
            self.data['ma_sell_signal'] = 0
            self.data['rsi_buy_signal'] = 0
            self.data['rsi_sell_signal'] = 0
            self.data['buy_signal'] = 0
            self.data['sell_signal'] = 0
            return self.data

    def _empty_metrics(self):
        """空数据时返回一套结构完整、全部为零的指标。"""
        return {
            'initial_capital': float(self.initial_capital),
            'final_value': float(self.initial_capital),
            'total_return': 0.0,
            'annual_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'total_trades': 0,
            'avg_trade_pnl': 0.0,
            'max_trade_profit': 0.0,
            'max_trade_loss': 0.0,
            'avg_holding_days': 0.0,
            'realized_pnl': 0.0,
            'fees_total': 0.0,
            'buy_fills': 0,
            'sell_fills': 0,
            'terminal_trade_count': 0,
            'terminal_liquidation_pnl': 0.0,
            'open_position_shares': 0,
            'open_position_market_value': 0.0,
            'open_position_cost': 0.0,
            'open_position_unrealized_pnl': 0.0,
            'equity_curve': [float(self.initial_capital)],
            'equity_dates': [None],
            'trade_ledger': [],
            'closed_trades': [],
            'exit_reasons': {},
        }

    def backtest_strategy(self, data=None):
        """按成交账本回测策略，返回指标、成交账本与含费权益曲线。

        data 为 None 时使用 self.data；训练/验证分段回测时传入切片，
        每段都从空仓和初始资金重新起步。
        """
        df = self.data if data is None else data
        if df is None or len(df) == 0:
            return self._empty_metrics()

        closes = (pd.to_numeric(df['close'], errors='coerce').to_numpy(dtype=float)
                  if 'close' in df.columns else np.full(len(df), np.nan))
        buys = (pd.to_numeric(df['buy_signal'], errors='coerce').fillna(0).to_numpy(dtype=float)
                if 'buy_signal' in df.columns else np.zeros(len(df)))
        sells = (pd.to_numeric(df['sell_signal'], errors='coerce').fillna(0).to_numpy(dtype=float)
                 if 'sell_signal' in df.columns else np.zeros(len(df)))
        ma20 = (pd.to_numeric(df['MA20'], errors='coerce').to_numpy(dtype=float)
                if 'MA20' in df.columns else None)

        cash = float(self.initial_capital)
        lots = []            # 持仓批次：每笔买入成交对应一个批次
        ledger = []          # 成交账本
        closed_trades = []   # 已平仓交易（由批次平仓反算）
        equity = [float(self.initial_capital)]  # 权益曲线，首点为初始资金
        equity_dates = [None]
        last_price = None
        last_index = len(df) - 1

        def _fmt(i):
            """把第 i 行的日期格式化成 YYYY-MM-DD，没有日期列时用行号。"""
            if 'date' in df.columns:
                value = df['date'].iloc[i]
                try:
                    return pd.Timestamp(value).strftime('%Y-%m-%d')
                except Exception:
                    return str(value)
            return str(i)

        def _position_shares():
            return sum(lot['shares'] for lot in lots)

        def _position_cost():
            """剩余持仓成本（含买入费用中未分摊的部分）。"""
            total = 0.0
            for lot in lots:
                ratio = lot['shares'] / lot['total_shares'] if lot['total_shares'] else 0.0
                total += lot['shares'] * lot['buy_price'] + lot['buy_fee'] * ratio
            return total

        def _closed_trade_record(lot):
            cost = lot['total_shares'] * lot['buy_price'] + lot['buy_fee']
            avg_sell = lot['sell_proceeds'] / lot['total_shares'] if lot['total_shares'] else 0.0
            return {
                'entry_date': lot['buy_date'],
                'exit_date': lot['last_exit_date'],
                'shares': lot['total_shares'],
                'buy_price': lot['buy_price'],
                'avg_sell_price': avg_sell,
                'holding_days': lot['last_exit_index'] - lot['buy_index'],
                'buy_fee': lot['buy_fee'],
                'sell_fee': lot['sell_fee'],
                'pnl': lot['realized_pnl'],
                'pnl_pct': (lot['realized_pnl'] / cost * 100.0) if cost > 0 else 0.0,
                'exit_reason': lot['exit_reason'],
            }

        def _execute_sell(i, price, sell_shares, reason, only_lot=None):
            """执行一次卖出成交；默认按先进先出平仓，也可只平指定批次。"""
            nonlocal cash
            sell_shares = int(sell_shares)
            if sell_shares <= 0 or price <= 0:
                return 0.0
            remaining = sell_shares
            total_fee = 0.0
            total_realized = 0.0
            candidates = [only_lot] if only_lot is not None else list(lots)
            for lot in candidates:
                if remaining <= 0:
                    break
                take = min(lot['shares'], remaining)
                if take <= 0:
                    continue
                amount = take * price
                fee = amount * self.trade_cost
                buy_fee_part = lot['buy_fee'] * (take / lot['total_shares'])
                cost_basis = take * lot['buy_price'] + buy_fee_part
                pnl = amount - fee - cost_basis
                total_fee += fee
                total_realized += pnl
                lot['shares'] -= take
                lot['realized_pnl'] += pnl
                lot['sell_fee'] += fee
                lot['sell_proceeds'] += amount
                lot['last_exit_index'] = i
                lot['last_exit_price'] = price
                lot['last_exit_date'] = _fmt(i)
                lot['exit_reason'] = reason
                remaining -= take
                if lot['shares'] <= 0:
                    lots.remove(lot)
                    closed_trades.append(_closed_trade_record(lot))
            traded = sell_shares - remaining
            if traded <= 0:
                return 0.0
            amount_total = traded * price
            cash += amount_total - total_fee
            ledger.append({
                'date': _fmt(i),
                'side': 'sell',
                'price': float(price),
                'shares': int(traded),
                'amount': float(amount_total),
                'fee': float(total_fee),
                'cash_after': float(cash),
                'reason': reason,
                'realized_pnl': float(total_realized),
            })
            return amount_total - total_fee

        def _execute_buy(i, price):
            """执行一次买入成交：按预算取整股数，费用按实际成交额计算。"""
            nonlocal cash
            if price <= 0:
                return False
            budget = cash * self.position_size
            shares = int(budget / price)
            # 极端情况下保证现金足以覆盖成交额与费用
            shares = min(shares, int(cash / (price * (1 + self.trade_cost))))
            if shares <= 0:
                return False
            amount = shares * price
            fee = amount * self.trade_cost
            cash -= amount + fee
            ledger.append({
                'date': _fmt(i),
                'side': 'buy',
                'price': float(price),
                'shares': int(shares),
                'amount': float(amount),
                'fee': float(fee),
                'cash_after': float(cash),
                'reason': ENTER_REASON_SIGNAL,
                'realized_pnl': 0.0,
            })
            lots.append({
                'buy_index': i,
                'buy_date': _fmt(i),
                'buy_price': float(price),
                'shares': int(shares),
                'total_shares': int(shares),
                'buy_fee': float(fee),
                'sell_fee': 0.0,
                'sell_proceeds': 0.0,
                'realized_pnl': 0.0,
                'last_exit_index': None,
                'last_exit_price': None,
                'last_exit_date': None,
                'exit_reason': None,
            })
            return True

        # 遍历每一个交易日
        for i in range(len(df)):
            price = closes[i]
            if not np.isfinite(price) or price <= 0:
                # 行情缺失：沿用上一有效价格估值，不产生任何成交
                reference = last_price if last_price is not None else 0.0
                equity.append(cash + _position_shares() * reference)
                equity_dates.append(_fmt(i))
                continue
            last_price = price

            buy_signal = buys[i]
            sell_signal = sells[i]

            # 1) 保护性离场：固定止损、技术止损、时间止损
            for lot in list(lots):
                stop_loss_price = lot['buy_price'] * (1 - self.stop_loss_pct)
                technical_stop = False
                if ma20 is not None and i < len(ma20) and np.isfinite(ma20[i]):
                    technical_stop = price < ma20[i]
                if price <= stop_loss_price or (technical_stop and price < lot['buy_price'] * 0.95):
                    _execute_sell(i, price, lot['shares'], EXIT_REASON_STOP_LOSS, only_lot=lot)
                elif ENABLE_TIME_STOP and i - lot['buy_index'] > self.time_stop_days:
                    _execute_sell(i, price, lot['shares'], EXIT_REASON_TIME_STOP, only_lot=lot)

            # 2) 买入信号（与旧版一致：同日买卖信号同时出现时买入优先）
            if buy_signal == 1 and len(lots) < self.max_positions:
                _execute_buy(i, price)
            # 3) 卖出信号：按当前总持仓的固定比例卖出
            elif sell_signal == 1 and lots:
                total_shares = _position_shares()
                sell_shares = int(total_shares * self.position_size)
                if sell_shares > 0:
                    _execute_sell(i, price, sell_shares, EXIT_REASON_SELL_SIGNAL)

            equity.append(cash + _position_shares() * price)
            equity_dates.append(_fmt(i))

        # 期末：先记录未平仓的浮盈浮亏（不冒充已实现收益），再显式清算
        open_shares = _position_shares()
        open_cost = _position_cost()
        open_value = open_shares * last_price if last_price is not None else 0.0
        open_unrealized = open_value - open_cost
        if lots and last_price is not None:
            for lot in list(lots):
                _execute_sell(last_index, last_price, lot['shares'], EXIT_REASON_FINAL, only_lot=lot)
            # 权益曲线最后一点改为期末清算后的现金，期末卖出费用必须进曲线
            equity[-1] = cash

        final_value = cash
        total_return = (final_value - self.initial_capital) / self.initial_capital * 100

        # 指标与权益曲线使用同一口径：从初始资金开始，含全部交易费用
        equity_array = np.array(equity, dtype=float)
        if len(equity_array) > 1 and np.all(equity_array[:-1] > 0):
            returns = np.diff(equity_array) / equity_array[:-1]
        else:
            returns = np.array([])
        num_trading_days = len(returns)
        if num_trading_days > 0 and final_value > 0:
            annual_return = (final_value / self.initial_capital) ** (252 / num_trading_days) - 1
        else:
            annual_return = 0.0
        volatility = float(np.std(returns) * np.sqrt(252)) if num_trading_days > 0 else 0.0
        sharpe_ratio = ((annual_return - RISK_FREE_RATE) / volatility) if volatility > 0 else 0.0

        # 最大回撤：峰值从初始资金起算，避免漏掉最初一段亏损
        peak = float(self.initial_capital)
        max_drawdown = 0.0
        for value in equity_array:
            if value > peak:
                peak = value
            drawdown = (peak - value) / peak if peak > 0 else 0.0
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # 交易统计全部由成交账本反算
        total_trades = len(closed_trades)
        pnls = np.array([trade['pnl'] for trade in closed_trades], dtype=float)
        win_rate = float(np.sum(pnls > 0) / total_trades) if total_trades else 0.0
        avg_trade_pnl = float(pnls.mean()) if total_trades else 0.0
        max_trade_profit = float(pnls.max()) if total_trades else 0.0
        max_trade_loss = float(pnls.min()) if total_trades else 0.0
        avg_holding_days = (float(np.mean([trade['holding_days'] for trade in closed_trades]))
                            if total_trades else 0.0)
        realized_pnl = float(pnls.sum()) if total_trades else 0.0
        fees_total = float(sum(fill['fee'] for fill in ledger))
        terminal_trades = [trade for trade in closed_trades if trade['exit_reason'] == EXIT_REASON_FINAL]
        exit_reasons = dict(Counter(trade['exit_reason'] for trade in closed_trades))

        return {
            'initial_capital': float(self.initial_capital),
            'final_value': float(final_value),
            'total_return': float(total_return),
            'annual_return': float(annual_return),
            'volatility': float(volatility),
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'win_rate': float(win_rate),
            'total_trades': int(total_trades),
            'avg_trade_pnl': avg_trade_pnl,
            'max_trade_profit': max_trade_profit,
            'max_trade_loss': max_trade_loss,
            'avg_holding_days': avg_holding_days,
            'realized_pnl': realized_pnl,
            'fees_total': fees_total,
            'buy_fills': int(sum(1 for fill in ledger if fill['side'] == 'buy')),
            'sell_fills': int(sum(1 for fill in ledger if fill['side'] == 'sell')),
            'terminal_trade_count': len(terminal_trades),
            'terminal_liquidation_pnl': float(sum(trade['pnl'] for trade in terminal_trades)),
            'open_position_shares': int(open_shares),
            'open_position_market_value': float(open_value),
            'open_position_cost': float(open_cost),
            'open_position_unrealized_pnl': float(open_unrealized),
            'equity_curve': [float(value) for value in equity],
            'equity_dates': equity_dates,
            'trade_ledger': ledger,
            'closed_trades': closed_trades,
            'exit_reasons': exit_reasons,
        }

    def _default_best_params(self):
        """网格没有任何结果时，回落到配置里的默认参数。"""
        return {
            'ticker': self.ticker,
            'rsi_buy_threshold': STRATEGY_CONFIG['rsi_buy_threshold'],
            'rsi_sell_threshold': STRATEGY_CONFIG['rsi_sell_threshold'],
            'bb_buy_mult': STRATEGY_CONFIG['bb_buy_mult'],
            'bb_sell_mult': STRATEGY_CONFIG['bb_sell_mult'],
            'score': 0.0,
            'validation_score': 0.0,
            'passed': False,
            'gate_reason': '未获得有效候选',
            'test_return_gap': 0.0,
            'total_return': 0.0,
            'annual_return': 0.0,
            'volatility': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'total_trades': 0,
            'train_total_return': 0.0,
            'train_sharpe_ratio': 0.0,
            'train_max_drawdown': 0.0,
            'train_win_rate': 0.0,
            'train_total_trades': 0,
            'val_total_return': 0.0,
            'val_sharpe_ratio': 0.0,
            'val_max_drawdown': 0.0,
            'val_win_rate': 0.0,
            'val_total_trades': 0,
            'test_total_return': 0.0,
            'test_sharpe_ratio': 0.0,
            'test_max_drawdown': 0.0,
            'test_win_rate': 0.0,
            'test_total_trades': 0,
        }

    def optimize_parameters(self, rsi_buy_thresholds=None, rsi_sell_thresholds=None,
                            bb_buy_mults=None, bb_sell_mults=None,
                            train_ratio=DEFAULT_TRAIN_RATIO,
                            val_ratio=DEFAULT_VAL_RATIO,
                            test_ratio=DEFAULT_TEST_RATIO,
                            min_val_sharpe=DEFAULT_MIN_VAL_SHARPE,
                            min_val_return=DEFAULT_MIN_VAL_RETURN_PCT,
                            min_test_return=DEFAULT_MIN_TEST_RETURN_PCT,
                            test_return_tolerance=DEFAULT_TEST_RETURN_TOLERANCE_PCT,
                            evaluate_test=True):
        """网格搜索参数，按验证段表现择优，测试段只作最终未见证据。

        样本按交易日顺序切成训练/验证/测试三段（默认 60%/20%/20%），
        三段都从空仓和初始资金独立回测。选参数只看验证段夏普；
        测试段在择优完成后才用于“是否通过门槛”的判断，不回流改选。
        本方法不写任何配置文件。
        """
        print("\n=== 策略参数优化 ===")

        # 加载数据
        self.load_data()

        # 使用配置文件中的参数搜索空间（允许显式传入覆盖）
        rsi_buy_thresholds = rsi_buy_thresholds if rsi_buy_thresholds is not None else OPTIMIZATION_CONFIG['rsi_buy_thresholds']
        rsi_sell_thresholds = rsi_sell_thresholds if rsi_sell_thresholds is not None else OPTIMIZATION_CONFIG['rsi_sell_thresholds']
        bb_buy_mults = bb_buy_mults if bb_buy_mults is not None else OPTIMIZATION_CONFIG['bb_buy_mults']
        bb_sell_mults = bb_sell_mults if bb_sell_mults is not None else OPTIMIZATION_CONFIG['bb_sell_mults']

        if self.data is None or len(self.data) < 3:
            print("  数据不足，无法切分训练/验证/测试三段，回落到默认参数")
            return self._default_best_params(), []

        # 先校验比例并打印三段行数；真正的切片在每个参数组合算完信号后再做，
        # 因为 buy_signal/sell_signal 是本方法临时加到 self.data 上的新列
        train_frame, val_frame, test_frame = split_three_way(
            self.data, train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio)
        print(f"  三段切分: 训练段 {len(train_frame)} 行 / 验证段 {len(val_frame)} 行 / "
              f"测试段 {len(test_frame)} 行（测试段只作最终未见证据）")

        best_params = None
        best_score = -float('inf')
        all_results = []
        # 三段指标统一按同一组字段复制，保证候选表 train_/val_/test_ 三组列齐全
        metric_names = ('total_return', 'annual_return', 'volatility', 'sharpe_ratio',
                        'max_drawdown', 'win_rate', 'total_trades', 'final_value',
                        'avg_trade_pnl', 'max_trade_profit', 'max_trade_loss', 'avg_holding_days')

        # 遍历所有参数组合
        for rsi_buy in rsi_buy_thresholds:
            for rsi_sell in rsi_sell_thresholds:
                for bb_buy in bb_buy_mults:
                    for bb_sell in bb_sell_mults:
                        try:
                            # 计算信号（逐行指标，只使用当日及历史数据）
                            self.calculate_signals(rsi_buy, rsi_sell, bb_buy, bb_sell)
                            # 信号列刚加到 self.data 上，必须在算完信号之后再切三段
                            train_frame, val_frame, test_frame = split_three_way(
                                self.data, train_ratio=train_ratio,
                                val_ratio=val_ratio, test_ratio=test_ratio)
                            # 训练/验证/测试三段分别独立回测，每段都从空仓和初始资金起步
                            train_metrics = self.backtest_strategy(train_frame)
                            val_metrics = self.backtest_strategy(val_frame)
                            # 未冻结参数前禁止触碰测试段。
                            test_metrics = {name: float('nan') for name in metric_names}

                            # 择优依据只看验证段夏普比率；测试段在这个阶段不参与
                            validation_score = val_metrics['sharpe_ratio']
                            if not _is_finite(validation_score):
                                raise ValueError('验证分非有限')
                            passed, gate_reason = False, '未评估：参数冻结后才揭开测试段'
                            result = {
                                'ticker': self.ticker,
                                'warmup_trim_rows': getattr(self, 'warmup_trim_rows', 0),
                                'rsi_buy_threshold': rsi_buy,
                                'rsi_sell_threshold': rsi_sell,
                                'bb_buy_mult': bb_buy,
                                'bb_sell_mult': bb_sell,
                                'score': validation_score,
                                'validation_score': validation_score,
                                'passed': bool(passed),
                                'gate_reason': gate_reason,
                                # 测试段收益减去验证段收益（百分点），便于审核“不明显劣于”
                                'test_return_gap': float(test_metrics['total_return']
                                                         - val_metrics['total_return']),
                                # 兼容旧调用方：顶层指标取验证段口径
                                'total_return': val_metrics['total_return'],
                                'annual_return': val_metrics['annual_return'],
                                'volatility': val_metrics['volatility'],
                                'sharpe_ratio': val_metrics['sharpe_ratio'],
                                'max_drawdown': val_metrics['max_drawdown'],
                                'win_rate': val_metrics['win_rate'],
                                'total_trades': val_metrics['total_trades'],
                            }
                            for name in metric_names:
                                result[f'train_{name}'] = train_metrics[name]
                                result[f'val_{name}'] = val_metrics[name]
                                result[f'test_{name}'] = test_metrics[name]
                            all_results.append(result)

                            # 更新最佳参数（按验证段夏普；测试段只在门槛判定中使用）
                            if validation_score > best_score:
                                best_score = validation_score
                                best_params = result
                                print(f"找到更优参数组合: 验证段夏普比率 = {validation_score:.4f}")
                        except Exception as e:
                            print(f"  参数组合失败: {e}")
                            continue

        # 如果没有找到最佳参数，使用默认参数
        if best_params is None:
            print("  没有找到最佳参数，使用默认参数")
            best_params = self._default_best_params()

        if evaluate_test and all_results:
            self.evaluate_selected(best_params, train_ratio, val_ratio, test_ratio,
                                   min_val_return=min_val_return, min_val_sharpe=min_val_sharpe,
                                   min_test_return=min_test_return,
                                   test_return_tolerance=test_return_tolerance)

        # 按验证段夏普排序，展示前10个参数组合
        if all_results:
            sorted_results = sorted(all_results, key=lambda x: x['validation_score'], reverse=True)
            top_10_results = sorted_results[:10]
        else:
            top_10_results = [best_params]

        print("\n=== 优化完成 ===")
        print("最佳参数组合（按验证段夏普择优）:")
        print(f"  RSI买入阈值: {best_params['rsi_buy_threshold']}")
        print(f"  RSI卖出阈值: {best_params['rsi_sell_threshold']}")
        print(f"  布林带买入倍数: {best_params['bb_buy_mult']}")
        print(f"  布林带卖出倍数: {best_params['bb_sell_mult']}")
        print(f"  验证段夏普比率: {best_params['sharpe_ratio']:.4f}")
        print(f"  验证段总收益率: {best_params['total_return']:.2f}%")
        print(f"  验证段最大回撤: {best_params['max_drawdown'] * 100:.2f}%")
        print(f"  验证段胜率: {best_params['win_rate'] * 100:.2f}%")
        print(f"  测试段总收益率: {best_params.get('test_total_return', 0.0):.2f}%")
        print(f"  测试段夏普比率: {best_params.get('test_sharpe_ratio', 0.0):.4f}")
        print(f"  测试段最大回撤: {best_params.get('test_max_drawdown', 0.0) * 100:.2f}%")
        print(f"  测试段收益 - 验证段收益: {best_params.get('test_return_gap', 0.0):+.2f} 个百分点")
        print(f"  是否通过门槛: {'是' if best_params.get('passed') else '否'}"
              f"（{best_params.get('gate_reason', '未评估')}）")

        print("\n前10个参数组合:")
        for i, result in enumerate(top_10_results, 1):
            print(f"\n第{i}名参数组合:")
            print(f"  RSI买入阈值: {result['rsi_buy_threshold']}")
            print(f"  RSI卖出阈值: {result['rsi_sell_threshold']}")
            print(f"  布林带买入倍数: {result['bb_buy_mult']}")
            print(f"  布林带卖出倍数: {result['bb_sell_mult']}")
            print(f"  总收益率: 训练 {result['train_total_return']:.2f}% / "
                  f"验证 {result['val_total_return']:.2f}% / "
                  f"测试 {result.get('test_total_return', 0.0):.2f}%")
            print(f"  夏普比率: 训练 {result['train_sharpe_ratio']:.4f} / "
                  f"验证 {result['val_sharpe_ratio']:.4f} / "
                  f"测试 {result.get('test_sharpe_ratio', 0.0):.4f}")
            print(f"  最大回撤: 训练 {result['train_max_drawdown'] * 100:.2f}% / "
                  f"验证 {result['val_max_drawdown'] * 100:.2f}% / "
                  f"测试 {result.get('test_max_drawdown', 0.0) * 100:.2f}%")
            print(f"  交易次数: 训练 {result['train_total_trades']} / "
                  f"验证 {result['val_total_trades']} / "
                  f"测试 {result.get('test_total_trades', 0)}")
            print(f"  是否通过门槛: {'是' if result.get('passed') else '否'}"
                  f"（{result.get('gate_reason', '未评估')}）")

        return best_params, all_results

    def evaluate_selected(self, candidate, train_ratio=DEFAULT_TRAIN_RATIO,
                          val_ratio=DEFAULT_VAL_RATIO, test_ratio=DEFAULT_TEST_RATIO, **gate):
        """冻结参数后仅评估这一组；失败时只否决，永不回流改选。"""
        candidate['gate_settings'] = dict(
            min_val_return=DEFAULT_MIN_VAL_RETURN_PCT,
            min_val_sharpe=DEFAULT_MIN_VAL_SHARPE,
            min_test_return=DEFAULT_MIN_TEST_RETURN_PCT,
            test_return_tolerance=DEFAULT_TEST_RETURN_TOLERANCE_PCT)
        candidate['gate_settings'].update(gate)
        candidate['warmup_trim_rows'] = getattr(self, 'warmup_trim_rows', 0)
        self.calculate_signals(*(candidate[key] for key in CONFIG_PARAM_KEYS))
        _, val, test = split_three_way(self.data, train_ratio, val_ratio, test_ratio)
        try:
            val_metrics = self.backtest_strategy(val)
            test_metrics = self.backtest_strategy(test)
            for prefix, metrics in (('val_', val_metrics), ('test_', test_metrics)):
                for key, value in metrics.items():
                    if isinstance(value, (int, float, np.number)):
                        candidate[prefix + key] = value
            candidate['passed'], candidate['gate_reason'] = evaluate_gate(
                {k: v for k, v in val_metrics.items() if isinstance(v, (int, float, np.number))},
                {k: v for k, v in test_metrics.items() if isinstance(v, (int, float, np.number))}, **gate)
            candidate['test_return_gap'] = test_metrics['total_return'] - val_metrics['total_return']
        except Exception as exc:
            candidate['passed'] = False
            candidate['gate_reason'] = f'最终测试失败: {exc}'
        return candidate

    def plot_optimization_results(self, all_results, output_dir=None):
        """绘制优化结果（默认写到 backup/optimization，不写 data/ 目录）。"""
        if not all_results:
            return None
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
            plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
        except Exception as e:
            print(f"  绘图依赖不可用，跳过绘图: {e}")
            return None

        output_dir = output_dir or DEFAULT_OUTPUT_DIR
        try:
            os.makedirs(output_dir, exist_ok=True)
            results_df = pd.DataFrame(all_results)
            if 'score' not in results_df.columns:
                results_df['score'] = 0.0
            results_df = results_df.sort_values('score', ascending=False)
            top_10 = results_df.head(10)

            fig = plt.figure(figsize=(15, 10))

            # 绘制夏普比率与总收益率的关系
            ax1 = fig.add_subplot(2, 1, 1)
            scatter = ax1.scatter(results_df['total_return'], results_df['sharpe_ratio'],
                                  c=results_df['max_drawdown'], cmap='RdYlGn_r', alpha=0.6)
            fig.colorbar(scatter, ax=ax1, label='最大回撤')
            ax1.scatter(top_10['total_return'], top_10['sharpe_ratio'], color='red', s=100, label='Top 10')
            ax1.set_title('参数组合性能分布')
            ax1.set_xlabel('总收益率 (%)')
            ax1.set_ylabel('夏普比率')
            ax1.legend()
            ax1.grid(True)

            # 绘制最佳参数组合的详细指标
            ax2 = fig.add_subplot(2, 1, 2)
            metrics_labels = ['总收益率 (%)', '夏普比率', '最大回撤 (%)', '胜率 (%)']
            top_row = top_10.iloc[0]
            values = [top_row['total_return'],
                      top_row['sharpe_ratio'],
                      top_row['max_drawdown'] * 100,
                      top_row['win_rate'] * 100]
            ax2.bar(metrics_labels, values, color=['green', 'blue', 'red', 'purple'])
            ax2.set_title('最佳参数组合性能指标（验证段）')
            ax2.set_ylabel('值')
            ax2.grid(axis='y')
            for i, v in enumerate(values):
                ax2.text(i, v + 0.01 * max(values), f'{v:.2f}', ha='center')

            fig.tight_layout()
            chart_path = os.path.join(output_dir, f'{self.ticker}_optimization_results.png')
            fig.savefig(chart_path)
            plt.close(fig)
            print(f"优化结果图表已保存为: {chart_path}")
            return chart_path
        except Exception as e:
            print(f"  绘制图表失败: {e}")
            return None

    def update_config(self, best_params, config_path='config.py', backup_dir='backup', *, force_apply=False):
        """把最优参数备份后写回 config.py（只在显式要求时调用）。"""
        backup_path = apply_best_to_config(best_params, config_path=config_path, backup_dir=backup_dir,
                                           force_apply=force_apply)
        print("\n=== 配置文件更新完成 ===")
        print(f"原配置已备份: {backup_path}")
        print(f"已将参数写入 {config_path} 的 STRATEGY_CONFIG:")
        print(f"  RSI买入阈值: {best_params['rsi_buy_threshold']}")
        print(f"  RSI卖出阈值: {best_params['rsi_sell_threshold']}")
        print(f"  布林带买入倍数: {best_params['bb_buy_mult']}")
        print(f"  布林带卖出倍数: {best_params['bb_sell_mult']}")
        return backup_path

    def run_optimization(self, apply_best=False, force_apply=False, config_path='config.py',
                         backup_dir='backup', output_path=DEFAULT_CANDIDATES_PATH, plot=False,
                         train_ratio=DEFAULT_TRAIN_RATIO, val_ratio=DEFAULT_VAL_RATIO,
                         test_ratio=DEFAULT_TEST_RATIO, grid=None):
        """运行完整优化：默认只输出候选表；apply_best 只写通过门槛的候选。

        force_apply=True 才允许把未通过门槛的候选写回配置，并打印不可外推警告。
        """
        best_params, all_results = self.optimize_parameters(
            train_ratio=train_ratio, val_ratio=val_ratio, test_ratio=test_ratio,
            **(grid or {}))
        if output_path:
            write_candidates_csv(all_results, output_path)
            print(f"参数候选表已输出: {output_path}")
        if plot:
            self.plot_optimization_results(all_results)
        if apply_best:
            if not application_passed(best_params) and not force_apply:
                print("\n拒绝写入 config.py：候选未通过验证/测试门槛。")
                print(f"  未通过原因: {best_params.get('gate_reason', '未评估')}")
                print("  如确认仅用于调试，可显式传 force_apply=True（写入会标注不可外推）。")
            else:
                if not best_params.get('passed'):
                    print("\n未通过门槛，仅因强制写入，不可外推")
                backup_path = self.update_config(best_params, config_path=config_path,
                                                 backup_dir=backup_dir, force_apply=force_apply)
                print(f"\n=== 已按显式要求写回配置，原文件备份于: {backup_path} ===")
        else:
            print("\n未写 config.py：默认只输出候选表，确认可用后再显式加 --apply-best。")
        print("\n=== 策略优化完成 ===")
        return best_params, all_results


def main(argv=None):
    """命令行入口：默认只输出候选表，只有显式 --apply-best 才写全局配置。"""
    parser = argparse.ArgumentParser(
        description='量化策略参数优化：训练/验证/测试三段评估，按验证段择优，'
                    '默认只输出候选表，不改写全局配置')
    parser.add_argument('--ticker', default=None,
                        help='只优化指定股票代码；省略则遍历 config.STOCK_TICKERS')
    parser.add_argument('--train-ratio', type=float, default=DEFAULT_TRAIN_RATIO,
                        help=f'训练段占比（默认 {DEFAULT_TRAIN_RATIO}）')
    parser.add_argument('--val-ratio', type=float, default=DEFAULT_VAL_RATIO,
                        help=f'验证段占比（默认 {DEFAULT_VAL_RATIO}，择优依据只看这一段）')
    parser.add_argument('--test-ratio', type=float, default=DEFAULT_TEST_RATIO,
                        help=f'测试段占比（默认 {DEFAULT_TEST_RATIO}，只作最终未见证据）')
    parser.add_argument('--output', default=DEFAULT_CANDIDATES_PATH,
                        help='候选参数表输出路径（默认 backup/optimization/optimization_candidates.csv）')
    parser.add_argument('--apply-best', action='store_true',
                        help='显式批准后，才备份原配置并把通过门槛的汇总最优参数写回 config.py')
    parser.add_argument('--force-apply', action='store_true',
                        help='候选未通过门槛时仍强制写入 config.py（会打印不可外推警告）')
    parser.add_argument('--config', default='config.py', help='要写回的配置文件路径')
    parser.add_argument('--backup-dir', default='backup', help='配置文件备份目录')
    parser.add_argument('--plot', action='store_true', help='额外绘制优化结果图（默认不画）')
    parser.add_argument('--min-val-sharpe', type=float, default=DEFAULT_MIN_VAL_SHARPE,
                        help='候选通过门槛：验证段夏普比率需大于该值（默认 0）')
    parser.add_argument('--min-val-return', type=float, default=DEFAULT_MIN_VAL_RETURN_PCT,
                        help='候选通过门槛：验证段总收益率需大于该值（默认 0）')
    parser.add_argument('--min-test-return', type=float, default=DEFAULT_MIN_TEST_RETURN_PCT,
                        help='候选通过门槛：测试段总收益率需大于该值（默认 0）')
    args = parser.parse_args(argv)

    try:
        validate_split_ratios(args.train_ratio, args.val_ratio, args.test_ratio)
    except ValueError as exc:
        parser.error(str(exc))
    if args.force_apply and not args.apply_best:
        print("提示: --force-apply 只放宽写入门槛，需与 --apply-best 一起使用才会写配置。")

    from config import STOCK_TICKERS

    if args.ticker:
        targets = [args.ticker]
    else:
        targets = list(dict.fromkeys(STOCK_TICKERS.values()))
    if not targets:
        print("config.STOCK_TICKERS 中没有可优化的股票。")
        return 1

    all_rows = []
    per_stock_best = []
    optimizers = []
    failures = []
    for ticker in targets:
        print(f"\n=== 分析股票: {ticker} ===")
        file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
        if not os.path.exists(file_path):
            print(f"  跳过 {ticker}: 缺少指标数据文件 {file_path}")
            failures.append(ticker)
            continue
        optimizer = StrategyOptimizer(file_path)
        try:
            best_params, all_results = optimizer.optimize_parameters(
                train_ratio=args.train_ratio,
                val_ratio=args.val_ratio,
                test_ratio=args.test_ratio,
                min_val_sharpe=args.min_val_sharpe,
                min_val_return=args.min_val_return,
                min_test_return=args.min_test_return, evaluate_test=False)
            if not all_results:
                raise RuntimeError('未获得有效验证候选')
        except (ValueError, RuntimeError) as exc:
            print(f'  跳过 {ticker}: {exc}')
            failures.append(ticker)
            continue
        optimizers.append(optimizer)
        all_rows.extend(all_results)
        per_stock_best.append(best_params)
        if args.plot:
            optimizer.plot_optimization_results(
                all_results, output_dir=os.path.dirname(os.path.abspath(args.output)))

    if not all_rows:
        print("\n没有任何股票完成优化，未输出候选表。")
        return 1

    # 参数先在全部验证结果上冻结，再统一揭开各股票的测试段。
    chosen = aggregate_best_params(per_stock_best)
    if chosen is None:
        print('没有有限的验证候选，未写配置。')
        return 1
    evidence = []
    for optimizer in optimizers:
        row = {key: chosen[key] for key in CONFIG_PARAM_KEYS}
        optimizer.evaluate_selected(row, args.train_ratio, args.val_ratio, args.test_ratio,
                                    min_val_return=args.min_val_return,
                                    min_val_sharpe=args.min_val_sharpe,
                                    min_test_return=args.min_test_return)
        evidence.append(row)
    chosen.update({key: value for key, value in evidence[0].items()
                   if key.startswith(('val_', 'test_'))})
    chosen['gate_settings'] = evidence[0].get('gate_settings', {})
    chosen['evaluation_evidence'] = evidence
    chosen['passed'] = not failures and all(row.get('passed') is True for row in evidence)
    chosen['gate_reason'] = ('通过' if chosen['passed'] else '最终测试或输入失败；不改选参数')
    for optimizer, selected_evidence in zip(optimizers, evidence):
        for row in all_rows:
            if row['ticker'] == optimizer.ticker and all(
                    row[key] == chosen[key] for key in CONFIG_PARAM_KEYS):
                row.update(selected_evidence)
    write_candidates_csv(all_rows, args.output)
    passed_count = sum(1 for row in all_rows if row.get('passed'))
    print(f"\n参数候选表已输出: {args.output}")
    print(f"共 {len(all_rows)} 组候选（训练 {args.train_ratio:.0%} / 验证 {args.val_ratio:.0%} / "
          f"测试 {args.test_ratio:.0%}），通过验证段+测试段门槛的有 {passed_count} 组")

    if args.apply_best:
        # chosen 已冻结并完成最终测试，禁止根据测试结果重新选择。
        if failures:
            print('部分输入失败，拒绝应用不完整样本的参数。')
            return 1
        if chosen is None:
            print("没有可用参数组，未写配置。")
            return 1
        passed = application_passed(chosen)
        if not passed and not args.force_apply:
            print("\n=== 拒绝写入 config.py：候选未通过门槛 ===")
            print(f"  参数组: RSI买 {chosen['rsi_buy_threshold']} / RSI卖 {chosen['rsi_sell_threshold']} / "
                  f"布林买 {chosen['bb_buy_mult']} / 布林卖 {chosen['bb_sell_mult']}")
            print(f"  未通过原因: {chosen.get('gate_reason', '未评估')}")
            print(f"  验证段收益: {chosen.get('total_return', 0.0):.2f}% / "
                  f"测试段收益: {chosen.get('test_total_return', 0.0):.2f}%")
            print("  --apply-best 只写通过验证段与测试段门槛的候选；"
                  "如确认仅用于调试，可显式加 --force-apply（写入时标注不可外推）。")
            return 1
        print("\n=== 显式 --apply-best：汇总一次后写回配置 ===")
        print(f"  参数组: RSI买 {chosen['rsi_buy_threshold']} / RSI卖 {chosen['rsi_sell_threshold']} / "
              f"布林买 {chosen['bb_buy_mult']} / 布林卖 {chosen['bb_sell_mult']}")
        print(f"  依据: 验证段夏普比率 {chosen.get('validation_score', 0.0):.4f} / "
              f"验证段收益 {chosen.get('total_return', 0.0):.2f}% / "
              f"测试段收益 {chosen.get('test_total_return', 0.0):.2f}%")
        if not passed:
            print("未通过门槛，仅因强制写入，不可外推")
        backup_path = apply_best_to_config(chosen, config_path=args.config, backup_dir=args.backup_dir,
                                           force_apply=args.force_apply)
        print(f"  原配置已备份: {backup_path}")
        print(f"  已写回 {args.config} 的 STRATEGY_CONFIG")
    else:
        print("\n未写 config.py：默认只输出候选表，确认后再显式加 --apply-best。")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
