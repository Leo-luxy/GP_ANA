import requests
import pandas as pd
import random
import time
import os
import argparse
import json
import csv
from datetime import datetime
from urllib.parse import quote, urlencode
from config import STOCK_TICKERS

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
                    if id_field == '序号':
                        # 对于研究报告和主要股东数据，使用序号+日期作为唯一标识
                        if '日期' in row:
                            row_id = f"{row.get('序号', '')}_{row.get('日期', '')}"
                        elif '截至日期' in row:
                            row_id = f"{row.get('序号', '')}_{row.get('截至日期', '')}"
                        else:
                            row_id = str(row.get(id_field, ''))
                    elif id_field == 'HOLDER_CODE' and 'REPORT_DATE' in row:
                        # 对于机构持股数据，使用 HOLDER_CODE + REPORT_DATE 作为唯一标识
                        row_id = f"{row.get('HOLDER_CODE', '')}_{row.get('REPORT_DATE', '')}"
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
        if id_field == '序号':
            # 对于研究报告和主要股东数据，使用序号+日期作为唯一标识
            if '日期' in item:
                item_id = f"{item.get('序号', '')}_{item.get('日期', '')}"
            elif '截至日期' in item:
                item_id = f"{item.get('序号', '')}_{item.get('截至日期', '')}"
            else:
                item_id = str(item.get(id_field, ''))
        elif id_field == 'HOLDER_CODE' and 'REPORT_DATE' in item:
            # 对于机构持股数据，使用 HOLDER_CODE + REPORT_DATE 作为唯一标识
            item_id = f"{item.get('HOLDER_CODE', '')}_{item.get('REPORT_DATE', '')}"
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

def fetch_north_holdings(secucode, interval_type='001', page_size=50, save_path=None):
    """
    获取某只股票的北向资金持股数据（季度/月度等）
    
    参数:
        secucode: str, 股票代码，如 '300433.SZ'
        interval_type: str, 数据周期，'001' 为季度，其他值可参考东方财富接口
        page_size: int, 每页条数
        save_path: str, 保存路径，若为 None 则返回数据列表
    返回:
        list 或 None
    """
    base_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    
    headers = {
        'Host': 'datacenter.eastmoney.com',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15',
        'Referer': 'https://emweb.securities.eastmoney.com/',
        'Origin': 'https://emweb.securities.eastmoney.com',
        'Accept': '*/*',
        'Accept-Language': 'zh-CN,zh-Hans;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    
    # 固定参数（不含分页、filter）
    common_params = {
        'reportName': 'RPT_MUTUAL_STOCK_HOLDRANKN_NEW',
        'columns': 'ALL',
        'quoteColumns': '',
        'sortTypes': '-1',
        'sortColumns': 'TRADE_DATE',
        'source': 'HSF10',
        'client': 'PC',
    }
    
    all_data = []
    page = 1
    
    while True:
        # 构建 filter 字符串，保留括号，对内部进行 URL 编码
        filter_raw = f'(INTERVAL_TYPE="{interval_type}")(SECUCODE="{secucode}")'
        filter_encoded = quote(filter_raw, safe='()')  # 保留括号
        
        # 分页及时间戳参数
        page_params = {
            'pageNumber': page,
            'pageSize': page_size,
            'v': str(int(time.time() * 1000))
        }
        
        # 合并除 filter 外的参数，并 URL 编码
        other_params = {**common_params, **page_params}
        other_encoded = urlencode(other_params, safe='()')
        
        # 完整 URL
        full_url = f"{base_url}?{other_encoded}&filter={filter_encoded}"
        
        try:
            print(f"正在请求第 {page} 页...")
            resp = requests.get(full_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"请求失败: {e}")
            break
        
        # 检查响应状态
        if not data.get('success', False):
            print(f"接口返回错误: {data.get('message', '未知错误')}")
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
        
        # 如果本页数据量小于 page_size，说明是最后一页
        if len(records) < page_size:
            break
        
        page += 1
        time.sleep(random.uniform(1, 2))  # 适当延时，避免请求过快
    
    if not all_data:
        print("未获取到任何数据")
        return None
    
    # 保存或返回
    if save_path:
        # 为每条数据添加ticker
        for item in all_data:
            item['ticker'] = secucode
        
        # 保存到CSV文件
        if all_data:
            fieldnames = ['ticker'] + list(all_data[0].keys())
            save_to_csv(save_path, all_data, fieldnames, 'TRADE_DATE')
    else:
        return all_data

def should_fetch_data(last_date_str):
    """
    根据最后一条数据的日期和当前时间判断是否需要抓取新数据
    
    参数:
        last_date_str: str, 最后一条数据的日期字符串，格式为 'YYYY-MM-DD'
    返回:
        bool, 是否需要抓取新数据
    """
    today = datetime.now().date()
    current_time = datetime.now().time()
    
    if not last_date_str:
        return True
    
    try:
        last_date = datetime.strptime(last_date_str, '%Y-%m-%d').date()
    except ValueError:
        return True
    
    # 计算日期差
    delta = (today - last_date).days
    
    if delta == 0:
        # 最新日期是今天，不需要抓取
        return False
    elif delta == 1:
        # 最新日期是昨天
        if current_time.hour < 15:
            # 下午3点前，不需要抓取
            return False
        else:
            # 下午3点后，需要抓取
            return True
    else:
        # 最新日期不是今天或昨天，需要抓取
        return True

def get_last_date_from_file(file_path):
    """
    从文件中获取最后一条数据的日期
    
    参数:
        file_path: str, 文件路径
    返回:
        str, 最后一条数据的日期字符串，格式为 'YYYY-MM-DD'，如果文件不存在或无法解析则返回空字符串
    """
    if not os.path.exists(file_path):
        return ""
    
    try:
        df = pd.read_csv(file_path)
        if 'TRADE_DATE' in df.columns:
            # 提取日期部分，去除时间
            df['DATE_ONLY'] = df['TRADE_DATE'].str.split(' ').str[0]
            last_date = df['DATE_ONLY'].max()
            return last_date
        else:
            return ""
    except Exception as e:
        print(f"读取文件失败: {e}")
        return ""

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='北向资金持股数据采集器')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
    parser.add_argument('--interval-type', type=str, default='001', help='数据周期，001为季度，默认：001')
    parser.add_argument('--page-size', type=int, default=50, help='每页大小，默认：50')
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
        save_path = f"{data_dir}/{ticker}_north_holdings.csv"
        
        # 检查是否需要抓取数据
        last_date = get_last_date_from_file(save_path)
        
        if should_fetch_data(last_date):
            print(f"需要抓取数据，最后更新日期：{last_date or '无'}")
            # 抓取数据
            fetch_north_holdings(
                secucode=ticker,
                interval_type=args.interval_type,
                page_size=args.page_size,
                save_path=save_path
            )
        else:
            print(f"数据已最新，最后更新日期：{last_date}，无需抓取")
        
        # 适当延时，避免请求过快
        time.sleep(random.uniform(1, 2))