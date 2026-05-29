
# batch_analyze_periodic.py
# 功能：批量对多只股票执行基于季度/月度更新数据的分析
# 实现原理：
# 1. 从config.py中读取所有股票代码
# 2. 对每只股票依次执行季度/月度更新数据的分析脚本
# 3. 记录执行结果和时间
import os
import sys
import time

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="批量分析股票或处理单只股票（季度/月度更新数据）")
    parser.add_argument('--ticker', help="股票代码，例如：300433.SZ，若不指定则分析config.py中的所有股票")
    args = parser.parse_args()
    
    if args.ticker:
        # 处理单只股票
        print("=== 单只股票季度/月度数据分析开始 ===")
        stock_code = args.ticker
        print(f"\n\n=====================================")
        print(f"开始分析股票: {stock_code}")
        print("=====================================")
        
        # 1. 财务报表分析（季度更新）
        print("\n1. 执行 analyze_financial_statements.py")
        run_command(f"python analyze_financial_statements.py --ticker {stock_code}")
        
        # 2. 研究报告分析（月度更新）
        print("\n2. 执行 analyze_research_reports.py")
        run_command(f"python analyze_research_reports.py --ticker {stock_code}")
          
        # 3. 股票财务数据分析（季度更新）
        print("\n3. 执行 analyze_em_financial.py")
        run_command(f"python analyze_em_financial.py --ticker {stock_code}")
            
        print(f"\n=====================================")
        print(f"股票 {stock_code} 季度/月度数据分析完成")
        print("=====================================")
    else:
        # 处理config.py中的所有股票
        print("=== 批量季度/月度数据分析开始 ===")
        print(f"总共需要分析 {len(STOCK_TICKERS)} 只股票")
        
        for stock_name, stock_code in STOCK_TICKERS.items():
            print(f"\n\n=====================================")
            print(f"开始分析股票: {stock_name} ({stock_code})")
            print("=====================================")
            
            # 1. 财务报表分析（季度更新）
            print("\n1. 执行 analyze_financial_statements.py")
            run_command(f"python analyze_financial_statements.py --ticker {stock_code}")
            
            # 2. 研究报告分析（月度更新）
            print("\n2. 执行 analyze_research_reports.py")
            run_command(f"python analyze_research_reports.py --ticker {stock_code}")

            # 3. 股票财务数据分析（季度更新）
            print("\n3. 执行 analyze_em_financial.py")
            run_command(f"python analyze_em_financial.py --ticker {stock_code}")
              
            print(f"\n=====================================")
            print(f"股票 {stock_name} ({stock_code}) 季度/月度数据分析完成")
            print("=====================================")
            
            # 等待2秒，避免请求过于频繁
            time.sleep(2)
    
    print("\n=== 批量季度/月度数据分析完成 ===")

if __name__ == "__main__":
    main()
