"""趋势跟踪策略参数的唯一来源（full / simple 两套预设）。

问题背景
--------
此前 full 与 simplified 两套引擎、批量回测脚本、旧独立简化批量脚本各自维护一份参数：
同名"简化版"实际是 ADX25/量比1.1/ATR3 或 ADX20/量比1.05/ATR3 等不同口径，却把结果写成
同一天的同名文件；full 模式的量比、斜率、MA5-MA60 偏离阈值还写死在代码里，参数改了不生效。
参数不一致时，先跑哪个入口就决定了后面读到什么，回测结论无法回溯。

本模块只回答"参数是什么"，不包含回测逻辑：
* 所有入口通过 get_params() 取参数，落盘时把参数写进产物元信息，用参数指纹标识身份；
* 未知参数键直接报错，避免拼写错误被静默忽略（history 上 full 量比就是因此没接线）。

参数含义
--------
adx_threshold            入场 ADX 下限（ADX 只代表趋势强度，不代表方向）
confirmation_days        趋势确认需要连续成立的天数
volume_ratio_threshold   量比下限（量比 = 当日成交量 / 20 日均量）
slope_threshold          MA10 五日斜率下限（仅 full 模式使用）
ma5_ma60_diff_threshold  MA5 相对 MA60 的偏离下限（仅 full 模式使用）
max_recent_days          保留字段：旧的"最近 N 日首次确认"窗口，已不再作为入场门禁
atr_stop_multiplier      入场时按 ATR 设置的保护止损倍数
exit_adx_threshold       趋势结束条件里的 ADX 上限
trailing_ma_period       移动止盈均线周期
chandelier_atr_multiplier 吊灯止损的 ATR 倍数
profit_target_atr        盈利达到多少倍 ATR 后启动移动止盈
reentry_cooldown_days    离场后禁止再入场的交易日数（工作区规则为 3）
"""

from __future__ import annotations

import copy

# ============================================================
# 预设参数（唯一来源，两版引擎与批量脚本都从这里取值）
# ============================================================
PRESET_PARAMS = {
    'full': {
        'adx_threshold': 25,
        'confirmation_days': 3,
        'volume_ratio_threshold': 1.2,
        'slope_threshold': 0.005,
        'ma5_ma60_diff_threshold': 0.01,
        'max_recent_days': 5,
        'atr_stop_multiplier': 3.0,
        'exit_adx_threshold': 25,
        'trailing_ma_period': 20,
        'chandelier_atr_multiplier': 3.0,
        'profit_target_atr': 2.0,
        'reentry_cooldown_days': 3,
    },
    'simple': {
        'adx_threshold': 25,
        'confirmation_days': 1,
        'volume_ratio_threshold': 1.1,
        'slope_threshold': 0.005,
        'ma5_ma60_diff_threshold': 0.01,
        'max_recent_days': 5,
        'atr_stop_multiplier': 3.0,
        'exit_adx_threshold': 25,
        'trailing_ma_period': 20,
        'chandelier_atr_multiplier': 3.0,
        'profit_target_atr': 2.0,
        'reentry_cooldown_days': 3,
    },
}

# 仅 full 模式真正使用的参数；simple 预设保留同名字段，只为参数表结构一致
FULL_ONLY_KEYS = ('slope_threshold', 'ma5_ma60_diff_threshold')

# 保留字段：入场门禁已改为"趋势确认 + 离场冷却"，本字段不再影响信号
INERT_KEYS = ('max_recent_days',)

_PARAM_DOCS = {
    'adx_threshold': 'ADX 入场下限',
    'confirmation_days': '趋势确认连续成立天数',
    'volume_ratio_threshold': '量比下限（当日量/20日均量）',
    'slope_threshold': 'MA10 五日斜率下限（仅 full）',
    'ma5_ma60_diff_threshold': 'MA5 相对 MA60 偏离下限（仅 full）',
    'max_recent_days': '保留字段，不再作为入场门禁',
    'atr_stop_multiplier': 'ATR 保护止损倍数',
    'exit_adx_threshold': '趋势结束的 ADX 上限',
    'trailing_ma_period': '移动止盈均线周期',
    'chandelier_atr_multiplier': '吊灯止损 ATR 倍数',
    'profit_target_atr': '盈利多少倍 ATR 后启动移动止盈',
    'reentry_cooldown_days': '离场后禁止再入场的交易日数',
}


def get_params(mode='full', overrides=None):
    """取指定模式的参数（深拷贝，调用方可以随意修改）。

    overrides 必须是已知参数键，出现未知键直接报错——历史上 full 量比参数
    因为拼写/没接线被静默忽略，这里不允许重演。
    """
    if mode not in PRESET_PARAMS:
        raise ValueError(f"未知的策略模式: {mode!r}，可选: {tuple(PRESET_PARAMS)}")
    params = copy.deepcopy(PRESET_PARAMS[mode])
    if overrides:
        unknown = sorted(set(overrides) - set(params))
        if unknown:
            raise KeyError(
                f"未知参数: {unknown}，{mode} 模式可用参数: {sorted(params)}"
            )
        for key, value in overrides.items():
            params[key] = value
    return params


def describe(mode='full'):
    """返回便于打印的参数说明（含每个参数的中文含义）。"""
    params = get_params(mode)
    lines = [f"{mode} 预设参数（共 {len(params)} 项）："]
    for key, value in params.items():
        lines.append(f"  {key:<26} = {value:<8} {_PARAM_DOCS.get(key, '')}")
    lines.append(
        "  说明：入场条件为「空仓 + 趋势确认成立 + 距上次离场满 "
        f"{params['reentry_cooldown_days']} 个交易日」，max_recent_days 为保留字段；"
        "simple 模式不使用 slope_threshold / ma5_ma60_diff_threshold。"
    )
    return "\n".join(lines)
