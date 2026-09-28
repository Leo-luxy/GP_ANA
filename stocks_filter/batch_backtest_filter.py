#!/usr/bin/env python3
# batch_backtest_filter.py
# 功能：批量处理筛选后的股票列表，执行数据获取、指标计算、趋势回测，并筛选出最终持仓股票

import pandas as pd
import subprocess
import os
import sys
import argparse
from datetime import datetime

# 添加项目根目录到Python路径（当前文件位于 stocks_filter 文件夹）
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR

# 当前文件所在目录（stocks_filter）
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))

# 项目根目录
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)


def run_command(cmd, description):
    """执行系统命令并返回结果"""
    print(f"\n{'='*60}")
    print(f"执行: {description}")
    print(f"命令: {cmd}")
    print('='*60)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"成功: {description}")
            if result.stdout:
                print(f"输出:\n{result.stdout[-2000:] if len(result.stdout) > 2000 else result.stdout}")
            return True
        else:
            print(f"失败: {description}")
            print(f"错误信息:\n{result.stderr[-1000:] if len(result.stderr) > 1000 else result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"超时: {description}")
        return False
    except Exception as e:
        print(f"异常: {description} - {str(e)}")
        return False


def get_stock_list(input_file):
    """读取筛选后的股票列表"""
    input_path = os.path.join(CURRENT_DIR, input_file)
    if not os.path.exists(input_path):
        print(f"错误：未找到输入文件 {input_path}")
        return None
    
    df = pd.read_csv(input_path)
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
    
    stock_list = df[code_col].tolist()
    return stock_list


def process_single_stock(ticker, skip_data_collection=False):
    """处理单只股票：数据获取 -> 指标计算 -> 趋势回测"""
    print(f"\n{'='*80}")
    print(f"开始处理股票: {ticker}")
    print('='*80)
    
    # 1. 获取行情数据（如果未跳过）
    if not skip_data_collection:
        cmd = f"python {os.path.join(PROJECT_ROOT, 'data_collector.py')} --ticker {ticker}"
        success = run_command(cmd, f"获取 {ticker} 行情数据")
        if not success:
            print(f"警告：获取 {ticker} 行情数据失败，尝试继续")
    
    # 2. 计算技术指标
    cmd = f"python {os.path.join(PROJECT_ROOT, 'daily', 'stock_daily_indicator_calculator.py')} --ticker {ticker}"
    success = run_command(cmd, f"计算 {ticker} 技术指标")
    if not success:
        print(f"错误：计算 {ticker} 技术指标失败，跳过该股票")
        return None
    
    # 3. 趋势回测
    cmd = f"python {os.path.join(PROJECT_ROOT, 'trend_following_backtest_simplified.py')} --ticker {ticker}"
    success = run_command(cmd, f"趋势回测 {ticker}")
    if not success:
        print(f"错误：{ticker} 回测失败，跳过该股票")
        return None
    
    # 4. 读取回测结果
    return read_backtest_result(ticker)


def read_backtest_result(ticker):
    """读取单只股票的回测结果，仅筛选 exit_type 为 final_close 的记录"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    # 查找最新的回测结果文件
    backtest_files = []
    if os.path.exists(stock_dir):
        for f in os.listdir(stock_dir):
            if f.startswith(f"{ticker}_backtest_") and f.endswith(".csv"):
                backtest_files.append(f)
    
    if not backtest_files:
        print(f"未找到 {ticker} 的回测结果文件")
        return None
    
    # 按时间戳排序，取最新的
    backtest_files.sort()
    latest_file = backtest_files[-1]
    file_path = os.path.join(stock_dir, latest_file)
    
    try:
        df = pd.read_csv(file_path)
        
        # 严格筛选 exit_type 为 final_close 的记录
        final_trades = df[df['exit_type'] == 'final_close']
        
        if len(final_trades) > 0:
            # 获取 final_close 的卖出记录（signal_type == 'sell'）
            final_sell = final_trades[final_trades['signal_type'] == 'sell'].iloc[-1]
            final_buy = final_trades[final_trades['signal_type'] == 'buy'].iloc[-1]
            return {
                '股票代码': ticker,
                '入场日期': final_buy['date'],
                '入场价格': final_buy['price'],
                '当前日期': final_sell['date'],
                '当前价格': final_sell['price'],
                '收益': final_sell['trade_profit'],
                '离场类型': final_sell['exit_type']
            }
        
        # 如果没有 final_close 记录，返回 None（不包含其他类型）
        print(f"{ticker} 没有 final_close 类型的交易记录")
        return None
    except Exception as e:
        print(f"读取 {ticker} 回测结果时出错: {str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser(description="批量处理筛选后的股票列表，执行趋势回测并筛选最终持仓")
    parser.add_argument('--input', default='stocks_daily_filtered.csv', help='输入的筛选股票列表文件')
    parser.add_argument('--output', default='final_holdings.csv', help='输出的最终持仓股票文件')
    parser.add_argument('--skip-data', action='store_true', help='跳过数据获取（假设数据已存在）')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的股票数量（用于测试）')
    args = parser.parse_args()
    
    print(f"{'='*80}")
    print("批量趋势回测筛选程序")
    print(f"输入文件: {args.input}")
    print(f"输出文件: {args.output}")
    print(f"跳过数据获取: {args.skip_data}")
    print(f"处理数量限制: {args.limit if args.limit else '全部'}")
    print('='*80)
    
    # 1. 读取股票列表
    stock_list = get_stock_list(args.input)
    if not stock_list:
        print("无法获取股票列表，程序退出")
        return
    
    # 限制处理数量
    if args.limit and args.limit < len(stock_list):
        stock_list = stock_list[:args.limit]
        print(f"限制处理前 {args.limit} 只股票")
    
    # 2. 批量处理股票
    final_holdings = []
    failed_stocks = []
    
    for i, ticker in enumerate(stock_list, 1):
        print(f"\n[{i}/{len(stock_list)}] 处理股票: {ticker}")
        
        # 标准化股票代码格式（确保包含交易所后缀）
        if '.' not in ticker:
            if ticker.startswith('6'):
                ticker = f"{ticker}.SH"
            else:
                ticker = f"{ticker}.SZ"
        
        result = process_single_stock(ticker, args.skip_data)
        
        if result:
            final_holdings.append(result)
        else:
            failed_stocks.append(ticker)
    
    # 3. 输出结果
    print(f"\n{'='*80}")
    print("处理完成！")
    print(f"成功处理: {len(final_holdings)} 只股票")
    print(f"失败: {len(failed_stocks)} 只股票")
    
    if failed_stocks:
        print(f"失败列表: {failed_stocks}")
    
    # 4. 保存最终持仓列表
    if final_holdings:
        df_result = pd.DataFrame(final_holdings)
        
        # 按入场日期降序排序
        df_result = df_result.sort_values('入场日期', ascending=False, na_position='last')
        
        # 添加统计信息
        df_result['处理时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 构建保存路径（保存到当前文件夹）
        output_path = os.path.join(CURRENT_DIR, args.output)
        
        # 保存到CSV
        df_result.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n最终持仓股票已保存到: {output_path}")
        print(f"持仓数量: {len(df_result)}")
        
        # 打印摘要
        print("\n持仓股票摘要:")
        print(df_result[['股票代码', '入场日期', '收益', '离场类型']].to_string(index=False))
    else:
        print("\n没有找到最终持仓的股票")


if __name__ == "__main__":
    main()