# trend_following_backtest_simplified.py
# 兼容入口：简化版（simple 语义）已并入统一引擎 trend_following_backtest.py。
#
# 保留本文件是为了让旧的导入路径与命令行调用继续可用：
# * 类名 TrendFollowingStrategy 仍可直接导入，固定走 simple 模式；
# * 默认参数取自 strategy_params 的 simple 预设（ATR止损 3 倍），命令行覆盖依旧生效；
# * 信号、成交、冷却逻辑全部复用统一引擎，不在这里另写一份，保证同一份数据同一组参数
#   下两边的权益曲线逐日完全一致。
from __future__ import annotations

import argparse

from strategy_params import describe
from trend_following_backtest import (
    TrendFollowingStrategy as _UnifiedTrendFollowingStrategy,
    add_param_arguments,
    collect_param_overrides,
    execute_backtest,
)


class TrendFollowingStrategy(_UnifiedTrendFollowingStrategy):
    """简化版策略：固定 simple 模式，参数取 strategy_params.simple 预设。"""

    def __init__(self, ticker, params=None):
        super().__init__(ticker, mode='simple', params=params)


def build_arg_parser():
    parser = argparse.ArgumentParser(description="趋势跟踪策略回测（简化版：MA5 > MA20）")
    parser.add_argument('--ticker', required=True, help='股票代码，如 300502.SZ')
    add_param_arguments(parser)
    return parser


def main():
    args = build_arg_parser().parse_args()
    print(describe('simple'))
    overrides = collect_param_overrides(args)
    strategy = TrendFollowingStrategy(args.ticker, params=overrides or None)
    if not strategy.load_data():
        return 1
    execute_backtest(strategy, capital=args.capital, position_ratio=args.position,
                     plot=not args.no_plot)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
