# batch_margin_collector.py
import os
import pandas as pd
import argparse
from datetime import datetime, timedelta
import random
import time

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

def get_all_stocks():
    """获取data文件夹中的所有股票代码"""
    stocks = []
    if os.path.exists(DATA_DIR):
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path) and '.' in item:
                stocks.append(item)
    return sorted(stocks)

def get_margin_data_for_date(date_str):
    """获取指定日期的全市场融资融券数据"""
    try:
        import akshare as ak
        
        # 获取沪市数据
        sh_margin = ak.stock_margin_detail_sse(date=date_str)
        # 获取深市数据
        sz_margin = ak.stock_margin_detail_szse(date=date_str)
        
        return sh_margin, sz_margin
    except Exception as e:
        print(f"获取 {date_str} 全市场融资融券数据失败: {str(e)}")
        return None, None

def get_last_margin_date(ticker):
    """获取股票融资融券数据的最后日期"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    output_file = os.path.join(stock_dir, f"{ticker}_margin_data.csv")
    
    if os.path.exists(output_file):
        try:
            df = pd.read_csv(output_file)
            if 'date' in df.columns and len(df) > 0:
                try:
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                    last_date = df['date'].max()
                    return last_date
                except:
                    df['date'] = pd.to_datetime(df['date'])
                    last_date = df['date'].max()
                    return last_date
        except Exception as e:
            print(f"读取 {ticker} 融资融券数据失败: {str(e)}")
    
    return None

def get_existing_dates(ticker):
    """获取股票已有的融资融券数据日期集合"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    output_file = os.path.join(stock_dir, f"{ticker}_margin_data.csv")
    existing_dates = set()
    
    if os.path.exists(output_file):
        try:
            df = pd.read_csv(output_file)
            if 'date' in df.columns:
                try:
                    df['date'] = pd.to_datetime(df['date'], format='%Y%m%d')
                except:
                    df['date'] = pd.to_datetime(df['date'])
                existing_dates = set(df['date'].dt.strftime('%Y%m%d'))
        except Exception as e:
            print(f"读取 {ticker} 已有日期失败: {str(e)}")
    
    return existing_dates

def save_margin_data(ticker, data, date_str, existing_dates=None):
    """保存单只股票的融资融券数据（带查重处理）"""
    # 检查是否已存在该日期数据
    if existing_dates is not None and date_str in existing_dates:
        return False
    
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    output_file = os.path.join(stock_dir, f"{ticker}_margin_data.csv")
    
    if not data.empty:
        data = data.copy()
        data['date'] = date_str
        
        if os.path.exists(output_file):
            data.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
        else:
            data.to_csv(output_file, index=False, encoding='utf-8-sig')
        
        return True
    return False

def batch_collect_margin_data(start_date=None, end_date=None):
    """批量获取所有股票的融资融券数据（自动日期范围+查重处理）"""
    stocks = get_all_stocks()
    print(f"找到 {len(stocks)} 只股票")
    
    if not stocks:
        print("未找到股票数据")
        return
    
    # 确定结束日期
    if end_date is None:
        end_date = datetime.now()
    else:
        end_date = datetime.strptime(end_date, '%Y%m%d')
    
    # 自动确定开始日期：取所有股票最早的最后日期的下一天
    print("\n正在获取各股票的最新融资融券数据日期...")
    earliest_start = None
    stock_last_dates = {}
    
    for ticker in stocks:
        last_date = get_last_margin_date(ticker)
        stock_last_dates[ticker] = last_date
        
        if last_date is None:
            # 没有数据，从30天前开始
            ticker_start = end_date - timedelta(days=30)
        else:
            ticker_start = last_date + timedelta(days=1)
        
        if earliest_start is None or ticker_start < earliest_start:
            earliest_start = ticker_start
        
        if last_date:
            print(f"  {ticker}: {last_date.strftime('%Y-%m-%d')}")
        else:
            print(f"  {ticker}: 无数据")
    
    # 如果用户指定了开始日期，取较晚的那个
    if start_date is not None:
        specified_start = datetime.strptime(start_date, '%Y%m%d')
        if specified_start > earliest_start:
            earliest_start = specified_start
    
    print(f"\n最早开始日期: {earliest_start.strftime('%Y-%m-%d')}")
    print(f"结束日期: {end_date.strftime('%Y-%m-%d')}")
    
    if earliest_start > end_date:
        print("所有股票的融资融券数据已是最新，无需更新")
        return
    
    # 预先获取每只股票已有的日期集合（用于查重）
    print("\n正在获取各股票已有的日期数据...")
    stock_existing_dates = {}
    for ticker in stocks:
        stock_existing_dates[ticker] = get_existing_dates(ticker)
        print(f"  {ticker}: {len(stock_existing_dates[ticker])} 条已有数据")
    
    # 遍历日期
    current_date = earliest_start
    total_added = 0
    total_skipped = 0
    
    while current_date <= end_date:
        # 跳过周末
        if current_date.weekday() >= 5:
            current_date += timedelta(days=1)
            continue
        
        date_str = current_date.strftime('%Y%m%d')
        print(f"\n===== 处理 {date_str} =====")
        
        # 获取当天全市场数据
        sh_margin, sz_margin = get_margin_data_for_date(date_str)
        
        if sh_margin is None or sz_margin is None:
            print(f"跳过 {date_str}")
            current_date += timedelta(days=1)
            continue
        
        # 为每只股票筛选数据（带查重）
        day_added = 0
        day_skipped = 0
        for ticker in stocks:
            # 检查该日期是否已存在
            if date_str in stock_existing_dates[ticker]:
                day_skipped += 1
                continue
            
            code = ticker.split('.')[0]
            market = 'sh' if ticker.endswith('.SH') else 'sz'
            
            if market == 'sh':
                stock_data = sh_margin[sh_margin['标的证券代码'] == code]
            else:
                stock_data = sz_margin[sz_margin['证券代码'] == code]
            
            if save_margin_data(ticker, stock_data, date_str, stock_existing_dates[ticker]):
                day_added += 1
                # 更新已有的日期集合
                stock_existing_dates[ticker].add(date_str)
        
        print(f"当天新增 {day_added} 条，跳过重复 {day_skipped} 条")
        total_added += day_added
        total_skipped += day_skipped
        
        # 随机延迟，避免请求过快
        time.sleep(random.uniform(2, 4))
        
        current_date += timedelta(days=1)
    
    print(f"\n===== 批量获取完成 =====")
    print(f"共新增 {total_added} 条融资融券数据")
    print(f"共跳过 {total_skipped} 条重复数据")

def main():
    parser = argparse.ArgumentParser(description='批量获取股票融资融券数据')
    parser.add_argument('--start_date', type=str, help='开始日期，格式：YYYYMMDD')
    parser.add_argument('--end_date', type=str, help='结束日期，格式：YYYYMMDD')
    args = parser.parse_args()
    
    print("开始批量获取融资融券数据...")
    batch_collect_margin_data(args.start_date, args.end_date)

if __name__ == "__main__":
    main()