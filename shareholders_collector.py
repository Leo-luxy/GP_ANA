import requests
import pandas as pd
import csv
import time
import os
import argparse
import random
from urllib.parse import quote
from config import STOCK_TICKERS

def get_latest_quarter_end():
    """获取最新的季度末日期"""
    today = pd.Timestamp.today()
    # 计算当前所在季度的季度末日期
    quarter = (today.month - 1) // 3 + 1
    quarter_end_month = quarter * 3
    quarter_end_day = 30 if quarter_end_month == 6 else 31
    latest_quarter_end = pd.Timestamp(year=today.year, month=quarter_end_month, day=quarter_end_day)
    
    # 如果当前日期在季度末之后但数据可能还未发布，使用上一个季度末
    if today.day <= 15 and quarter == 1:
        # 1月上旬，可能去年Q4数据还未发布
        return pd.Timestamp(year=today.year-1, month=12, day=31)
    elif today.day <= 30 and (quarter == 2 or quarter == 3 or quarter == 4):
        # 其他季度的月初，可能上季度数据还未发布
        if quarter == 2:
            return pd.Timestamp(year=today.year, month=3, day=31)
        elif quarter == 3:
            return pd.Timestamp(year=today.year, month=6, day=30)
        else:  # quarter == 4
            return pd.Timestamp(year=today.year, month=9, day=30)
    
    return latest_quarter_end

def get_next_quarter(date_str):
    """获取下一个季度的日期"""
    date = pd.to_datetime(date_str)
    # 计算当前季度
    quarter = (date.month - 1) // 3 + 1
    # 计算下一个季度
    next_quarter = quarter + 1
    next_year = date.year
    if next_quarter > 4:
        next_quarter = 1
        next_year += 1
    # 计算下一个季度末日期
    month = next_quarter * 3
    day = 30 if month == 6 else 31
    return pd.Timestamp(year=next_year, month=month, day=day)

def get_last_end_date(save_path):
    """获取本地文件中的最后日期"""
    if not os.path.exists(save_path):
        return None
    
    try:
        df = pd.read_csv(save_path)
        if 'END_DATE' in df.columns:
            # 转换日期格式并获取最大值
            df['END_DATE'] = pd.to_datetime(df['END_DATE'])
            last_date = df['END_DATE'].max()
            return last_date.strftime('%Y-%m-%d')
    except Exception as e:
        print(f"读取本地文件失败: {e}")
    
    return None

def save_to_csv(file_path, data, fieldnames, id_field):
    """保存数据到CSV文件，增量保存，去重"""
    if not data:
        return
    
    # 加载现有数据
    existing_data = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # 生成唯一标识
                    if id_field == 'HOLDER_NAME' and 'END_DATE' in row:
                        # 对于股东数据，使用 HOLDER_NAME + END_DATE 作为唯一标识
                        row_id = f"{row.get('HOLDER_NAME', '')}_{row.get('END_DATE', '')}"
                    else:
                        # 其他情况保持原逻辑
                        row_id = str(row.get(id_field, ''))
                    existing_data[row_id] = row
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
    
    # 去重并添加新数据
    new_data = []
    for item in data:
        # 生成唯一标识
        if id_field == 'HOLDER_NAME' and 'END_DATE' in item:
            # 对于股东数据，使用 HOLDER_NAME + END_DATE 作为唯一标识
            item_id = f"{item.get('HOLDER_NAME', '')}_{item.get('END_DATE', '')}"
        else:
            # 其他情况保持原逻辑
            item_id = str(item.get(id_field, ''))
        
        if item_id not in existing_data:
            new_data.append(item)
    
    # 如果有新数据，保存
    if new_data:
        # 确定所有字段
        all_fieldnames = fieldnames
        for item in new_data:
            for key in item.keys():
                if key not in all_fieldnames:
                    all_fieldnames.append(key)
        
        # 写入文件
        mode = 'a' if existing_data else 'w'
        with open(file_path, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_fieldnames)
            if not existing_data:
                writer.writeheader()
            for item in new_data:
                writer.writerow(item)
        print(f"已保存 {len(new_data)} 条新数据到 {file_path}")
    else:
        print("无新数据需要保存")

def fetch_shareholders_data(secucode, end_date=None, start_date=None, page_size=200, save_path=None):
    """
    抓取股东数据
    使用 datacenter 接口和报表名 RPT_F10_EH_HOLDERS

    参数:
        secucode: str, 股票代码，如 '002384.SZ'
        end_date: str, 截止日期 YYYY-MM-DD（可选），默认最新日期
        start_date: str, 开始日期 YYYY-MM-DD（可选），如果提供则抓取日期范围内的数据
        page_size: int, 每页记录数，最大200
        save_path: str, CSV保存路径，若为None则返回DataFrame
    返回:
        pandas.DataFrame 或 None
    """
    headers = {
        'Host': 'datacenter.eastmoney.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Version/16.0 Safari/605.1.15',
        'Referer': 'https://emweb.securities.eastmoney.com/',
        'Origin': 'https://emweb.securities.eastmoney.com',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
    }
    
    all_data = []
    
    # 如果提供了开始日期和结束日期，生成日期范围内的所有季度末日期
    if start_date and end_date:
        # 生成季度末日期列表
        date_range = pd.date_range(start=start_date, end=end_date, freq='Q')
        dates = [d.strftime('%Y-%m-%d') for d in date_range]
    elif start_date:
        # 只设置了开始日期，使用最新季度末作为结束日期
        latest_date = get_latest_quarter_end()
        date_range = pd.date_range(start=start_date, end=latest_date, freq='Q')
        dates = [d.strftime('%Y-%m-%d') for d in date_range]
    else:
        # 只抓取指定的结束日期或默认最新季度末
        if end_date:
            dates = [end_date]
        else:
            # 自动检测最新季度末
            latest_date = get_latest_quarter_end()
            dates = [latest_date.strftime('%Y-%m-%d')]
    
    for target_date in dates:
        print(f"\n正在抓取 {target_date} 的数据...")
        page = 1
        
        while True:
            # 构建完整的URL，使用目标日期
            timestamp = int(time.time() * 1000)
            url = f"https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_F10_EH_HOLDERS&columns=ALL&quoteColumns=&filter=(SECUCODE%3D%22{secucode}%22)(END_DATE%3D%27{target_date}%27)&pageNumber={page}&pageSize={page_size}&sortTypes=1&sortColumns=HOLDER_RANK&source=HSF10&client=PC&v={timestamp}"
            
            try:
                print(f"正在请求第 {page} 页...")
                resp = requests.get(url, headers=headers, timeout=30)
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                print(f"请求失败: {e}")
                break
            
            result = data.get('result')
            if not result:
                print("无 result 字段，请求可能异常")
                break
            
            records = result.get('data', [])
            if not records:
                print(f"第 {page} 页无数据，抓取结束")
                break
            
            all_data.extend(records)
            print(f"已获取 {len(records)} 条记录，累计 {len(all_data)} 条")
            
            # 判断是否最后一页
            total_pages = result.get('pages', 0)
            if page >= total_pages:
                break
            
            page += 1
            time.sleep(0.5)
    
    if not all_data:
        print("未获取到任何数据")
        return None
    
    # 转换为 DataFrame
    df = pd.DataFrame(all_data)
    
    # 处理日期字段
    if 'END_DATE' in df.columns:
        df['END_DATE'] = pd.to_datetime(df['END_DATE']).dt.date
    
    # 保存或返回
    if save_path:
        # 确保保存目录存在
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        # 按时间升序排列
        if 'END_DATE' in df.columns:
            df = df.sort_values('END_DATE', ascending=True)
        
        # 使用增量保存
        if not df.empty:
            # 定义字段名
            fieldnames = list(df.columns)
            # 转换为字典列表
            records = df.to_dict('records')
            # 增量保存
            save_to_csv(save_path, records, fieldnames, 'HOLDER_NAME')
    else:
        return df


if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股东数据采集器')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：002384.SZ')
    parser.add_argument('--end-date', type=str, help='截止日期，例如：2025-09-30')
    parser.add_argument('--start-date', type=str, help='开始日期，例如：2024-01-01')
    parser.add_argument('--page-size', type=int, default=200, help='每页大小，默认：200')
    args = parser.parse_args()
    
    # 确定要处理的股票列表
    tickers = []
    if args.ticker:
        # 如果指定了--ticker参数，只处理该股票
        tickers = [args.ticker]
    else:
        # 否则处理config.py中的所有股票
        tickers = list(STOCK_TICKERS.values())
    
    # 遍历处理每个股票
    for ticker in tickers:
        print(f"\n开始处理股票：{ticker}")
        
        # 构建保存路径
        data_dir = f"data/{ticker}"
        os.makedirs(data_dir, exist_ok=True)  # 确保目录存在
        save_path = f"{data_dir}/{ticker}_historical_shareholders.csv"
        
        # 检查本地是否有数据
        local_start_date = args.start_date
        local_end_date = args.end_date
        
        if not local_start_date:
            # 读取本地文件的最后日期
            last_date = get_last_end_date(save_path)
            if last_date:
                # 本地有数据，设置start_date为下一个季度
                next_quarter_date = get_next_quarter(last_date)
                local_start_date = next_quarter_date.strftime('%Y-%m-%d')
                print(f"本地数据最后日期: {last_date}，设置开始日期为下一季度: {local_start_date}")
            else:
                # 本地无数据，从2024-01-01开始
                local_start_date = '2024-01-01'
                print(f"本地无数据，设置开始日期为: {local_start_date}")
        
        if not local_end_date:
            # 自动检测最新季度末日期
            latest_quarter_end = get_latest_quarter_end()
            local_end_date = latest_quarter_end.strftime('%Y-%m-%d')
            print(f"自动检测最新季度末日期: {local_end_date}")
        
        # 抓取数据
        fetch_shareholders_data(
            secucode=ticker,
            start_date=local_start_date,
            end_date=local_end_date,
            page_size=args.page_size,
            save_path=save_path
        )
        
        # 适当延时，避免请求过快
        time.sleep(random.uniform(2, 4))
