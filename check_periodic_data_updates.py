
# check_periodic_data_updates.py
# 功能：检查指定股票的低频更新数据文件是否需要更新
# 实现原理：
# 1. 检查基本信息、财务数据、股东数据等低频更新的数据文件
# 2. 根据数据类型的更新频率，判断是否需要更新
# 3. 如果需要更新，调用相应的collector文件获取数据
# 4. 支持增量更新，追加保存数据

import os
import sys
import subprocess
from datetime import datetime, timedelta, date
import pandas as pd

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, STOCK_TICKERS

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

def check_file_exists(file_path):
    """检查文件是否存在"""
    return os.path.exists(file_path)

def get_file_modification_date(file_path):
    """获取文件的修改日期"""
    if os.path.exists(file_path):
        return date.fromtimestamp(os.path.getmtime(file_path))
    return None

def get_latest_data_date(file_path):
    """获取文件中数据的最新日期"""
    try:
        if file_path.endswith('.json'):
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 检查不同类型文件的日期字段
            if 'timestamp' in data:
                # 公司信息文件，使用timestamp字段
                timestamp_str = data['timestamp']
                try:
                    # 尝试解析不同格式的时间戳
                    if ' ' in timestamp_str:
                        # 格式: 2026-04-15 21:23:37
                        return date.fromisoformat(timestamp_str.split(' ')[0])
                    else:
                        # 格式: 2026-04-15
                        return date.fromisoformat(timestamp_str)
                except Exception:
                    pass
            
            # 检查research_reports中的最新日期
            if 'research_reports' in data and data['research_reports']:
                latest_date = None
                for report in data['research_reports']:
                    if '日期' in report:
                        try:
                            report_date = date.fromisoformat(report['日期'])
                            if not latest_date or report_date > latest_date:
                                latest_date = report_date
                        except Exception:
                            pass
                if latest_date:
                    return latest_date
            
            # 检查main_shareholders中的最新日期
            if 'main_shareholders' in data and data['main_shareholders']:
                latest_date = None
                for shareholder in data['main_shareholders']:
                    if '截至日期' in shareholder:
                        try:
                            shareholder_date = date.fromisoformat(shareholder['截至日期'])
                            if not latest_date or shareholder_date > latest_date:
                                latest_date = shareholder_date
                        except Exception:
                            pass
                if latest_date:
                    return latest_date
            
        elif file_path.endswith('.csv'):
            import pandas as pd
            df = pd.read_csv(file_path)
            
            # 检查常见的日期列
            date_columns = ['REPORT_DATE', 'date', '截至日期', '日期']
            for col in date_columns:
                if col in df.columns:
                    # 尝试解析日期列
                    try:
                        df[col] = pd.to_datetime(df[col])
                        if not df[col].empty:
                            latest_date = df[col].max().date()
                            return latest_date
                    except Exception:
                        pass
        
        # 如果无法获取数据日期，返回None
        return None
    except Exception as e:
        print(f"获取文件数据日期时出错: {e}")
        return None

def is_file_need_update(file_path, update_frequency_days):
    """判断文件是否需要更新"""
    if not os.path.exists(file_path):
        print(f"文件不存在，需要更新: {file_path}")
        return True
    
    # 尝试获取文件中数据的最新日期
    latest_data_date = get_latest_data_date(file_path)
    
    if latest_data_date:
        # 使用数据的最新日期来判断
        days_since_data = (date.today() - latest_data_date).days
        if days_since_data >= update_frequency_days:
            print(f"数据已超过 {update_frequency_days} 天未更新，需要更新: {file_path}")
            print(f"数据最新日期: {latest_data_date}")
            print(f"当前日期: {date.today()}")
            print(f"天数差: {days_since_data} 天")
            return True
        else:
            print(f"数据是最新的: {file_path}")
            print(f"数据最新日期: {latest_data_date}")
            print(f"当前日期: {date.today()}")
            print(f"天数差: {days_since_data} 天")
            return False
    else:
        # 如果无法获取数据日期，回退到使用文件修改日期
        mod_date = get_file_modification_date(file_path)
        if not mod_date:
            print(f"无法获取文件修改日期，需要更新: {file_path}")
            return True
        
        days_since_mod = (date.today() - mod_date).days
        if days_since_mod >= update_frequency_days:
            print(f"文件已超过 {update_frequency_days} 天未更新，需要更新: {file_path}")
            return True
        
        print(f"文件是最新的: {file_path}")
        return False

def check_stock_periodic_data(ticker):
    """检查指定股票的低频更新数据文件"""
    print(f"\n=== 检查股票: {ticker} ===")
    
    # 确保数据目录存在
    stock_dir = os.path.join(DATA_DIR, ticker)
    if not os.path.exists(stock_dir):
        os.makedirs(stock_dir)
    
    print(f"当前日期: {date.today()}")
    
    # 需要检查的低频更新文件
    files_to_check = {
        # 基本信息 - 月度更新
        'company_basic': {
            'path': os.path.join(stock_dir, f"{ticker}_company_basic.json"),
            'frequency': 30,  # 30天更新一次
            'collector': f"python stock_company_info_collector.py --ticker {ticker}"
        },
        
        # 财务指标 - 季度更新
        'financial_indicators': {
            'path': os.path.join(stock_dir, f"{ticker}_financial_indicators.json"),
            'frequency': 90,  # 90天更新一次
            'collector': f"python financial_indicators_collector.py --ticker {ticker}"
        },
        
        # 股票财务数据 - 季度更新
        'eastmoney_financial': {
            'path': os.path.join(stock_dir, f"{ticker}_dupont_data.csv"),
            'frequency': 90,  # 90天更新一次
            'collector': f"python em_financial_collector.py --ticker {ticker}"
        },
        
        # 股东数据 - 季度更新
        'shareholder': {
            'path': os.path.join(stock_dir, f"{ticker}_shareholder.csv"),
            'frequency': 90,  # 90天更新一次
            'collector': f"python shareholder_collector.py --ticker {ticker}"
        },
        

        
        # 重要缺失数据 - 月度更新
        'important_missing': {
            'path': os.path.join(stock_dir, f"{ticker}_ex_dividend.csv"),
            'frequency': 30,  # 30天更新一次
            'collector': f"python important_missing_data_collector.py --ticker {ticker}"
        },
        
        # 机构持股 - 季度更新
        'institutional_holdings': {
            'path': os.path.join(stock_dir, f"{ticker}_institutional_holdings.csv"),
            'frequency': 90,  # 90天更新一次
            'collector': f"python org_hold_collector.py --ticker {ticker}"
        },
        
        # 北向资金 - 月度更新
        'north_fund': {
            'path': os.path.join(stock_dir, f"{ticker}_north_fund.csv"),
            'frequency': 30,  # 30天更新一次
            'collector': f"python north_fund_collector.py --ticker {ticker}"
        }
    }
    
    # 检查并更新每个文件
    for data_type, config in files_to_check.items():
        print(f"\n检查 {data_type} 数据...")
        if is_file_need_update(config['path'], config['frequency']):
            print(f"需要更新 {data_type} 数据")
            run_command(config['collector'])
        else:
            print(f"{data_type} 数据是最新的，无需更新")

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="检查股票低频更新数据文件是否需要更新")
    parser.add_argument('--ticker', help="股票代码，例如：300433.SZ，默认处理所有股票")
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
        check_stock_periodic_data(ticker)

if __name__ == "__main__":
    main()
