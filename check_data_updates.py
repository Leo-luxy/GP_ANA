#!/opt/anaconda3/envs/PythonProject/bin/python
# check_data_updates.py
# 功能：检查指定股票的数据文件是否是最新日期以及是否有数据文件缺失
# 实现原理：
# 1. 检查qfq.csv, fund_flow.csv, margin_data.csv文件是否存在
# 2. 检查各文件的最后一行日期是否是最新日期
# 3. 如果不是最新或缺失，调用相应的collector文件获取数据
# 4. 检查indicators.csv是否是最新，如果不是，调用batch_analysis.py计算

import os
import sys
import subprocess
from datetime import datetime, timedelta
import pandas as pd

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, STOCK_TICKERS

def is_latest_date(last_date_str, current_date):
    """判断最后日期是否是最新日期"""
    try:
        # 处理不同格式的日期字符串
        if isinstance(last_date_str, str):
            # 尝试不同的日期格式
            if '-' in last_date_str:
                # 处理 YY-MM-DD 格式
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
            else:
                # 处理 YYMMDD 格式
                last_date = datetime.strptime(last_date_str, "%Y%m%d")
        else:
            # 处理其他类型的日期（如numpy.int64）
            last_date_str = str(last_date_str)
            if len(last_date_str) == 8:
                # 处理 YYMMDD 格式
                last_date = datetime.strptime(last_date_str, "%Y%m%d")
            else:
                # 尝试 YY-MM-DD 格式
                last_date = datetime.strptime(last_date_str, "%Y-%m-%d")
        
        # 如果最后日期等于当前日期，是最新
        if last_date.date() == current_date.date():
            return True
        
        # 如果最后日期是当前日期的前一天
        if last_date.date() == (current_date - timedelta(days=1)).date():
            # 当前时间在16:00以前，是最新
            if current_date.hour < 16:
                return True
            # 当前时间在16:00以后，不是最新
            else:
                return False
        
        # 其他情况，不是最新
        return False
    except Exception as e:
        print(f"日期格式错误: {e}")
        return False

def get_last_date(file_path):
    """获取文件的最后一行日期"""
    try:
        df = pd.read_csv(file_path)
        if not df.empty:
            last_row = df.iloc[-1]
            # 检查不同文件的时间列头
            if 'date' in last_row:
                return last_row['date']
            elif '日期' in last_row:
                return last_row['日期']
            elif '数据日期' in last_row:
                return last_row['数据日期']
        return None
    except Exception as e:
        print(f"读取文件出错: {e}")
        return None

def check_file_up_to_date(file_path, current_date):
    """检查文件是否是最新日期"""
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False
    
    last_date = get_last_date(file_path)
    if not last_date:
        print(f"无法获取文件的最后日期: {file_path}")
        return False
    
    return is_latest_date(last_date, current_date)

def run_command(cmd, cwd=None):
    """执行命令并返回结果"""
    print(f"执行命令: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        print(f"命令执行结果: {result.returncode}")
        if result.stdout:
            print(f"标准输出: {result.stdout}")
        if result.stderr:
            print(f"标准错误: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"执行命令出错: {e}")
        return False

def check_stock_data(ticker):
    """检查指定股票的数据文件"""
    print(f"\n=== 检查股票: {ticker} ===")
    
    # 确保数据目录存在
    stock_dir = os.path.join(DATA_DIR, ticker)
    if not os.path.exists(stock_dir):
        os.makedirs(stock_dir)
    
    # 当前日期时间
    current_date = datetime.now()
    print(f"当前日期时间: {current_date}")
    
    # 需要检查的文件
    files_to_check = {
        'qfq': os.path.join(stock_dir, f"{ticker}_qfq.csv"),
        'fund_flow': os.path.join(stock_dir, f"{ticker}_fund_flow.csv"),
        'margin_data': os.path.join(stock_dir, f"{ticker}_margin_data.csv"),
        'valuation': os.path.join(stock_dir, f"{ticker}_valuation.csv"),
        'indicators': os.path.join(stock_dir, f"{ticker}_indicators.csv")
    }
    
    # 检查qfq.csv
    if not check_file_up_to_date(files_to_check['qfq'], current_date):
        print("qfq.csv 不是最新或缺失，需要更新")
        # 调用data_collector.py获取数据
        cmd = f"python data_collector.py --ticker {ticker}"
        run_command(cmd)
    else:
        print("qfq.csv 是最新的")
    
    # 检查fund_flow.csv
    if not check_file_up_to_date(files_to_check['fund_flow'], current_date):
        print("fund_flow.csv 不是最新或缺失，需要更新")
        # 调用stock_market_data_collector.py获取数据
        cmd = f"python stock_market_data_collector.py --ticker {ticker}"
        run_command(cmd)
    else:
        print("fund_flow.csv 是最新的")
    
    # 检查margin_data.csv
    if not check_file_up_to_date(files_to_check['margin_data'], current_date):
        print("margin_data.csv 不是最新或缺失，需要更新")
        # 调用stock_market_data_collector.py获取数据
        cmd = f"python stock_market_data_collector.py --ticker {ticker}"
        run_command(cmd)
    else:
        print("margin_data.csv 是最新的")
    
    # 检查valuation.csv
    if not check_file_up_to_date(files_to_check['valuation'], current_date):
        print("valuation.csv 不是最新或缺失，需要更新")
        # 调用stock_market_data_collector.py获取数据
        cmd = f"python stock_market_data_collector.py --ticker {ticker}"
        run_command(cmd)
    else:
        print("valuation.csv 是最新的")
    
    # 检查indicators.csv
    if not check_file_up_to_date(files_to_check['indicators'], current_date):
        print("indicators.csv 不是最新或缺失，需要更新")
        # 调用daily/batch_analysis.py计算
        cmd = f"python daily/batch_analysis.py --ticker {ticker}"
        run_command(cmd)
    else:
        print("indicators.csv 是最新的")

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="检查股票数据文件是否是最新日期以及是否有数据文件缺失")
    parser.add_argument('--ticker', help="股票代码，例如：600313.SH（上交所）、000001.SZ（深交所），默认处理所有股票")
    args = parser.parse_args()
    
    # 确定要处理的股票列表
    if args.ticker:
        # 处理单只股票
        ticker_list = [args.ticker]
    else:
        # 处理所有股票
        ticker_list = list(STOCK_TICKERS.values())
        print(f"批量处理所有股票，共 {len(ticker_list)} 只")
    
    # 遍历处理每只股票
    for ticker in ticker_list:
        check_stock_data(ticker)

if __name__ == "__main__":
    main()
