# batch_analyze.py
# 统一的批量分析入口
# --mode all:      完整分析（全部 11 步）
# --mode daily:    日更数据分析（6 步）
# --mode periodic: 定期/低频数据分析（4 步）

import os
import sys
import time
import argparse

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import STOCK_TICKERS


def run_command(command, stock=None):
    """运行 shell 命令并计时"""
    if stock:
        print(f"\n=== 正在处理股票: {stock} ===")
    print(f"执行命令: {command}")
    start_time = time.time()
    result = os.system(command)
    elapsed = time.time() - start_time
    print(f"执行时间: {elapsed:.2f}秒")
    if result != 0:
        print(f"警告: 命令执行失败，返回码: {result}")
    return result


def run_steps(stock_code, steps, mode_name):
    """依次执行步骤列表"""
    print(f"\n{'='*50}")
    print(f"开始 {mode_name} 分析: {stock_code}")
    print(f"{'='*50}")

    for i, (step_name, command) in enumerate(steps, 1):
        print(f"\n[{i}/{len(steps)}] {step_name}")
        run_command(command, stock=stock_code)


def get_all_steps(stock_code):
    """返回三种模式各自的步骤列表"""
    return {
        'all': [
            # V1 旧分析模块（MD 报告）
            ("财务报表分析", f"python analyze_financial_statements.py --ticker {stock_code}"),
            ("业绩预告与分红分析", f"python analyze_performance_forecast.py --ticker {stock_code}"),
            ("股东结构分析", f"python analyze_shareholder_structure.py --ticker {stock_code}"),
            ("同行比较分析", f"python analyze_peer_comparison.py --ticker {stock_code}"),
            ("东方财富财务分析", f"python analyze_em_financial.py --ticker {stock_code}"),
            ("资金流分析", f"python analyze_fund_flow.py --ticker {stock_code}"),
            ("融资融券分析", f"python analyze_margin_data.py --ticker {stock_code}"),
            ("估值分析", f"python analyze_valuation_data.py --ticker {stock_code}"),
            ("研究报告分析", f"python analyze_research_reports.py --ticker {stock_code}"),
            # V3 Process 模块（JSON 摘要）
            ("计算技术趋势数据", f"python calculate_technical_trend_ds.py --ticker {stock_code}"),
            ("生成财务结构化JSON", f"python Process/financial_structured_analyzer.py --ticker {stock_code}"),
            ("生成情绪估值JSON", f"python Process/sentiment_valuation_analyzer.py --ticker {stock_code}"),
            ("生成股东结构JSON", f"python Process/shareholder_structure_analyzer.py --ticker {stock_code}"),
            ("生成研报分析JSON", f"python Process/research_report_analyzer.py --ticker {stock_code}"),
        ],
        'daily': [
            ("资金流分析", f"python analyze_fund_flow.py --ticker {stock_code}"),
            ("融资融券分析", f"python analyze_margin_data.py --ticker {stock_code}"),
            ("估值分析", f"python analyze_valuation_data.py --ticker {stock_code}"),
            ("计算技术趋势数据", f"python calculate_technical_trend_ds.py --ticker {stock_code}"),
            ("技术趋势 LLM 分析", f"python analyze_technical_trend.py --ticker {stock_code}"),
            ("股东结构分析", f"python analyze_shareholder_structure.py --ticker {stock_code}"),
        ],
        'periodic': [
            ("财务报表分析", f"python analyze_financial_statements.py --ticker {stock_code}"),
            ("业绩预告与分红分析", f"python analyze_performance_forecast.py --ticker {stock_code}"),
            ("股东结构分析", f"python analyze_shareholder_structure.py --ticker {stock_code}"),
            ("同行比较分析", f"python analyze_peer_comparison.py --ticker {stock_code}"),
        ],
    }


def main():
    parser = argparse.ArgumentParser(description="批量股票分析（统一入口）")
    parser.add_argument('--ticker', help="单只股票代码，如 300433.SZ（不指定则处理 config 中的所有股票）")
    parser.add_argument('--mode', choices=['all', 'daily', 'periodic'], default='daily',
                        help="分析模式：all(全部) daily(日更) periodic(定期)")
    args = parser.parse_args()

    mode_names = {'all': '完整', 'daily': '日更数据', 'periodic': '定期数据'}

    if args.ticker:
        stock_code = args.ticker
        steps = get_all_steps(stock_code)[args.mode]
        run_steps(stock_code, steps, mode_names[args.mode])
    else:
        tickers = list(STOCK_TICKERS.values())
        print(f"=== 批量 {mode_names[args.mode]} 分析开始 ===")
        print(f"共 {len(tickers)} 只股票: {', '.join(tickers)}")

        for stock_code in tickers:
            steps = get_all_steps(stock_code)[args.mode]
            run_steps(stock_code, steps, mode_names[args.mode])

        print("\n=== 批量分析完成 ===")


if __name__ == "__main__":
    main()
