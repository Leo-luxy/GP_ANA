#!/usr/bin/env python3
# weekly_batch_analysis.py
# 功能：批量对多只股票执行周线数据的完整分析流程
# 实现原理：
# 1. 从config.py中读取所有股票代码
# 2. 对每只股票依次执行周线数据分析脚本
# 3. 记录执行结果和时间

import os
import time
from config import STOCK_TICKERS

def run_command(command, stock=None):
    """运行命令并打印输出"""
    if stock:
        print(f"\n=== 正在处理股票: {stock} ===")
    print(f"执行命令: {command}")
    start_time = time.time()
    result = os.system(command)
    end_time = time.time()
    print(f"执行时间: {end_time - start_time:.2f}秒")
    if result != 0:
        print(f"警告: 命令执行失败，返回码: {result}")
    return result

def main():
    """主函数"""
    print("=== 周线数据批量分析开始 ===")
    print(f"总共需要分析 {len(STOCK_TICKERS)} 只股票")
    
    for stock_name, stock_code in STOCK_TICKERS.items():
        print(f"\n\n=====================================")
        print(f"开始分析股票: {stock_name} ({stock_code})")
        print("=====================================")
        
        # 1. 生成周线数据
        print("\n1. 执行 stock_weekly_analyzer.py")
        run_command(f"python stock_weekly_analyzer.py --ticker {stock_code}")
        
        # 2. 周线数据分析
        print("\n2. 执行 weekly_data_analysis.py")
        run_command(f"python weekly_data_analysis.py --ticker {stock_code}")
        
        print(f"\n=====================================")
        print(f"股票 {stock_name} ({stock_code}) 周线分析完成")
        print("=====================================")
        
        # 等待2秒，避免请求过于频繁
        time.sleep(2)
    
    print("\n=== 周线数据批量分析完成 ===")

if __name__ == "__main__":
    main()
