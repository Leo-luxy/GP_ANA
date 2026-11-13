# backtest_all_stocks_simplified.py
# 已弃用：简化版批量回测入口。
#
# 历史问题：本脚本自带一套 ADX20 / 量比1.05 / ATR3 的"优化后"参数，与统一引擎的
# simple 预设（ADX25 / 量比1.1 / ATR3）不是一回事，却把结果写成同名产物，
# 先跑哪个入口就决定了后续读到哪套参数的回测。现在简化版口径统一到
# strategy_params.simple，本文件只打印弃用提示，然后转调 backtest_all_stocks.py 的
# simple 模式，保留旧入口但不保留第二套参数。
from __future__ import annotations

import argparse

import backtest_all_stocks as unified
from strategy_params import describe


def main():
    parser = argparse.ArgumentParser(description="[已弃用] 批量回测所有股票（简化版入口）")
    parser.add_argument('--asof', default=None,
                        help='监控期望的行情截止日（YYYYMMDD），默认取各票指标文件最后一行')
    parser.add_argument('--monitor-only', action='store_true', help='只生成监控报告，不重跑回测')
    args = parser.parse_args()

    print("=" * 80)
    print("⚠️  backtest_all_stocks_simplified.py 已弃用")
    print("    简化版参数已统一到 strategy_params.simple，本脚本转调")
    print("    backtest_all_stocks.py --mode simple，不再保留第二套参数口径。")
    print("=" * 80)
    print(describe('simple'))

    if not args.monitor_only:
        results = unified.run_batch_backtest(mode='simple')
        df = unified.analyze_results(results, mode='simple')
        unified.generate_suggestions(df)

    stocks = unified.get_all_stocks()
    unified.generate_monitor_report(stocks, mode='simple', asof=args.asof)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
