# check_data_updates.py
# 统一的数据更新检查入口
# --mode daily:    检查日更数据（qfq, fund_flow, margin, valuation, indicators）
# --mode periodic: 检查低频数据（company_basic, financial, shareholder, north 等）
# --mode all:      检查全部

import os
import sys
import subprocess
from datetime import datetime, timedelta, date
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, STOCK_TICKERS


# ============================================================
# 工具函数
# ============================================================
def run_command(cmd, cwd=None):
    print(f"执行命令: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        if result.stdout:
            print(f"标准输出: {result.stdout}")
        if result.stderr:
            print(f"标准错误: {result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"执行命令出错: {e}")
        return False


def parse_date_str(value):
    """统一解析日期字符串/数值"""
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, 'date'):
        return value.date()
    s = str(value)
    for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(s.split(' ')[0], fmt).date()
        except (ValueError, IndexError):
            continue
    return None


# ---- 日更数据的检查逻辑（基于最后一行日期） ----
def is_latest_date(last_date_val, current_date):
    try:
        d = parse_date_str(last_date_val)
        if not d:
            return False
        if d == current_date.date():
            return True
        if d == (current_date - timedelta(days=1)).date():
            return current_date.hour < 16  # 16:00 前，前一天数据视为最新
        return False
    except Exception:
        return False


def get_last_date(file_path):
    try:
        df = pd.read_csv(file_path)
        if df.empty:
            return None
        for col in ['date', '日期', '数据日期']:
            if col in df.columns:
                return df.iloc[-1][col]
        return None
    except Exception as e:
        print(f"读取文件出错: {e}")
        return None


def check_file_up_to_date(file_path, current_date):
    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        return False
    last_date = get_last_date(file_path)
    if last_date is None:
        print(f"无法获取文件的最后日期: {file_path}")
        return False
    return is_latest_date(last_date, current_date)


# ---- 低频数据的检查逻辑（基于文件修改时间/数据日期） ----
def get_file_modification_date(file_path):
    if os.path.exists(file_path):
        return date.fromtimestamp(os.path.getmtime(file_path))
    return None


def get_latest_data_date(file_path):
    try:
        if file_path.endswith('.json'):
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'timestamp' in data:
                d = parse_date_str(data['timestamp'])
                if d:
                    return d
            # 研报中的最新日期
            for report in data.get('research_reports', []) or []:
                if '日期' in report:
                    d = parse_date_str(report['日期'])
                    if d:
                        return d
            # 股东中的最新日期
            for sh in data.get('main_shareholders', []) or []:
                if '截至日期' in sh:
                    d = parse_date_str(sh['截至日期'])
                    if d:
                        return d
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            for col in ['REPORT_DATE', 'date', '截至日期', '日期']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    if not df[col].dropna().empty:
                        return df[col].max().date()
        return None
    except Exception as e:
        print(f"获取文件数据日期时出错: {e}")
        return None


def is_file_need_update(file_path, update_frequency_days):
    if not os.path.exists(file_path):
        print(f"文件不存在，需要更新: {file_path}")
        return True
    latest = get_latest_data_date(file_path)
    if latest:
        days_since = (date.today() - latest).days
        if days_since >= update_frequency_days:
            print(f"数据已超过 {update_frequency_days} 天未更新 ({latest}，距今 {days_since} 天)")
            return True
    else:
        mod_date = get_file_modification_date(file_path)
        if not mod_date:
            return True
        days_since = (date.today() - mod_date).days
        if days_since >= update_frequency_days:
            return True
    print(f"数据是最新的: {file_path}")
    return False


# ============================================================
# 检查逻辑
# ============================================================
def check_daily_data(ticker):
    """检查日更数据"""
    print(f"\n=== [日更] 检查股票: {ticker} ===")
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    now = datetime.now()

    files_map = {
        'qfq': (f"{ticker}_qfq.csv", f"python data_collector.py --ticker {ticker}"),
        'fund_flow': (f"{ticker}_fund_flow.csv", f"python stock_market_data_collector.py --ticker {ticker}"),
        'margin_data': (f"{ticker}_margin_data.csv", f"python batch_margin_collector.py --ticker {ticker}"),
        'indicators': (f"{ticker}_indicators.csv", f"python daily/batch_analysis.py --ticker {ticker}"),
        'shareholder_num': (f"{ticker}_shareholder_num.csv", f"python shareholder_num_collector.py --ticker {ticker}"),
    }

    for name, (filename, cmd) in files_map.items():
        file_path = os.path.join(stock_dir, filename)
        if not check_file_up_to_date(file_path, now):
            print(f"  {filename} 不是最新（或缺失），更新中...")
            run_command(cmd)
        else:
            print(f"  {filename} 是最新的")


def check_periodic_data(ticker):
    """检查低频更新数据"""
    print(f"\n=== [定期] 检查股票: {ticker} ===")
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)

    files_map = {
        'company_basic': (f"{ticker}_company_basic.json", 30, f"python stock_company_info_collector.py --ticker {ticker}"),
        'financial_indicators': (f"{ticker}_financial_indicators.json", 90, f"python financial_indicators_collector.py --ticker {ticker}"),
        'dupont': (f"{ticker}_dupont_data.csv", 90, f"python em_financial_collector.py --ticker {ticker}"),
        'shareholder': (f"{ticker}_shareholder.csv", 90, f"python shareholders_collector.py --ticker {ticker}"),
        'ex_dividend': (f"{ticker}_ex_dividend.csv", 30, f"python important_missing_data_collector.py --ticker {ticker}"),
        'institutional': (f"{ticker}_institutional_holdings.csv", 90, f"python org_hold_collector.py --ticker {ticker}"),
        'north_holdings': (f"{ticker}_north_holdings.csv", 30, f"python north_holdings.py --ticker {ticker}"),
    }

    for name, (filename, freq, cmd) in files_map.items():
        file_path = os.path.join(stock_dir, filename)
        if is_file_need_update(file_path, freq):
            run_command(cmd)
        else:
            print(f"  {name} 无需更新")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="统一数据更新检查")
    parser.add_argument('--ticker', help="股票代码，如 300433.SZ（不指定则处理全部）")
    parser.add_argument('--mode', choices=['daily', 'periodic', 'all'], default='daily',
                        help="更新模式 (default: daily)")
    args = parser.parse_args()

    tickers = [args.ticker] if args.ticker else list(STOCK_TICKERS.values())
    if not args.ticker:
        print(f"批量处理 {len(tickers)} 只股票")

    for t in tickers:
        if args.mode in ('daily', 'all'):
            check_daily_data(t)
        if args.mode in ('periodic', 'all'):
            check_periodic_data(t)


if __name__ == "__main__":
    main()
