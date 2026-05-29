import requests
import pandas as pd
import random
import time
import os
import argparse
import csv
from datetime import datetime
from urllib.parse import quote, urlencode
import akshare as ak
from config import STOCK_TICKERS, DATA_DIR

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
                    if id_field in row:
                        row_id = str(row.get(id_field, ''))
                        existing_data[row_id] = row
        except Exception as e:
            print(f"读取CSV文件失败: {e}")
    
    # 去重并添加新数据
    new_data = []
    for item in data:
        # 生成唯一标识
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
        
        # 写入文件 - 使用增量保存方式
        # 如果文件已存在，使用追加模式('a')，否则使用写入模式('w')
        mode = 'a' if existing_data else 'w'
        with open(file_path, mode, newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=all_fieldnames)
            if not existing_data:
                writer.writeheader()
            for item in new_data:
                writer.writerow(item)
        print(f"已保存 {len(new_data)} 条新数据到 {file_path}")
        print("保存方式：增量保存（只添加新数据，保留原有数据）")

def fetch_shareholder_num(secucode, page_size=50, save_path=None):
    """
    抓取个股的股东户数、户均持股等历史数据

    参数:
        secucode: str, 股票代码，如 '300433.SZ'
        page_size: int, 每页记录数
        save_path: str, CSV保存路径，若为None则返回DataFrame
    返回:
        pandas.DataFrame 或 None
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
        'reportName': 'RPT_F10_EH_HOLDERNUM',
        'columns': ','.join([
            'SECUCODE', 'SECURITY_CODE', 'END_DATE', 'HOLDER_TOTAL_NUM', 'TOTAL_NUM_RATIO',
            'AVG_FREE_SHARES', 'AVG_FREESHARES_RATIO', 'HOLD_FOCUS', 'PRICE',
            'AVG_HOLD_AMT', 'HOLD_RATIO_TOTAL', 'FREEHOLD_RATIO_TOTAL'
        ]),
        'quoteColumns': '',
        'sortTypes': '-1',
        'sortColumns': 'END_DATE',      # 按报告期降序
        'source': 'HSF10',
        'client': 'PC',
    }
    
    all_data = []
    page = 1
    
    while True:
        # 构造 filter 字符串，保留括号，内部编码
        filter_raw = f'(SECUCODE="{secucode}")'
        filter_encoded = quote(filter_raw, safe='()')
        
        # 分页参数
        page_params = {
            'pageNumber': page,
            'pageSize': page_size,
            'v': str(int(time.time() * 1000))
        }
        
        # 合并除 filter 外的参数，并编码
        other_params = {**common_params, **page_params}
        other_encoded = urlencode(other_params, safe='()')
        
        full_url = f"{base_url}?{other_encoded}&filter={filter_encoded}"
        
        try:
            print(f"正在请求第 {page} 页...")
            resp = requests.get(full_url, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"请求失败: {e}")
            break
        
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
    
    # 转换为 DataFrame
    df = pd.DataFrame(all_data)
    
    # 按 END_DATE 升序排序
    if 'END_DATE' in df.columns:
        df = df.sort_values('END_DATE', ascending=True)
    
    # 保存或返回
    if save_path:
        # 转换为字典列表
        data_list = df.to_dict('records')
        if data_list:
            # 使用 END_DATE 作为唯一标识符
            fieldnames = list(data_list[0].keys())
            save_to_csv(save_path, data_list, fieldnames, 'END_DATE')
    else:
        return df

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
        if 'END_DATE' in df.columns:
            # 提取日期部分，去除时间
            df['DATE_ONLY'] = df['END_DATE'].str.split(' ').str[0]
            last_date = df['DATE_ONLY'].max()
            return last_date
        elif '股东户数统计截止日' in df.columns:
            last_date = df['股东户数统计截止日'].max()
            return last_date
        else:
            return ""
    except Exception as e:
        print(f"读取文件失败: {e}")
        return ""

def fetch_shareholder_num_akshare(code, save_path=None):
    """
    从akshare获取股东户数数据
    
    参数:
        code: str, 股票代码，如 '300433'
        save_path: str, CSV保存路径，若为None则返回DataFrame
    返回:
        pandas.DataFrame 或 None
    """
    print("从akshare获取股东户数数据...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        shareholder_df = ak.stock_zh_a_gdhs_detail_em(symbol=code)
        if not shareholder_df.empty:
            # 按照股东户数统计截止日字段降序排序
            if '股东户数统计截止日' in shareholder_df.columns:
                # 将日期字符串转换为日期类型进行排序
                shareholder_df['股东户数统计截止日'] = pd.to_datetime(shareholder_df['股东户数统计截止日'])
                shareholder_df = shareholder_df.sort_values('股东户数统计截止日', ascending=False)
                # 再转换回字符串格式
                shareholder_df['股东户数统计截止日'] = shareholder_df['股东户数统计截止日'].dt.strftime('%Y-%m-%d')
            elif 'END_DATE' in shareholder_df.columns:
                # 备用字段名
                shareholder_df = shareholder_df.sort_values('END_DATE', ascending=False)
            
            # 保存或返回
            if save_path:
                # 转换为字典列表
                data_list = shareholder_df.to_dict('records')
                if data_list:
                    # 使用 股东户数统计截止日 作为唯一标识符
                    fieldnames = list(data_list[0].keys())
                    save_to_csv(save_path, data_list, fieldnames, '股东户数统计截止日')
            else:
                return shareholder_df
    except Exception as e:
        print(f"从akshare获取股东数时出错: {str(e)}")
        return None

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股东户数数据采集器')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
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
        data_dir = os.path.join(DATA_DIR, ticker)
        os.makedirs(data_dir, exist_ok=True)  # 确保目录存在
        
        # 1. 从东方财富API获取股东户数数据
        print("\n1. 从东方财富API获取股东户数数据...")
        save_path_eastmoney = os.path.join(data_dir, f"{ticker}_shareholder_num.csv")
        
        # 检查是否需要抓取数据
        last_date = get_last_date_from_file(save_path_eastmoney)
        if should_fetch_data(last_date):
            print(f"需要抓取数据，最后更新日期：{last_date or '无'}")
            # 抓取数据
            fetch_shareholder_num(
                secucode=ticker,
                page_size=args.page_size,
                save_path=save_path_eastmoney
            )
        else:
            print(f"数据已最新，最后更新日期：{last_date}，无需抓取")
        
        # 2. 从akshare获取股东户数数据
        print("\n2. 从akshare获取股东户数数据...")
        code = ticker.split('.')[0]
        save_path_akshare = os.path.join(data_dir, f"{ticker}_shareholder_num_info.csv")
        
        # 抓取数据（akshare数据直接抓取，不做日期检查）
        fetch_shareholder_num_akshare(
            code=code,
            save_path=save_path_akshare
        )
        
        # 3. 对保存的文件进行升序排序
        for file_path in [save_path_eastmoney, save_path_akshare]:
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                    # 根据日期字段排序
                    if 'END_DATE' in df.columns:
                        # 提取日期部分，去除时间
                        df['DATE_ONLY'] = df['END_DATE'].str.split(' ').str[0]
                        df = df.sort_values('DATE_ONLY', ascending=True)
                        del df['DATE_ONLY']
                    elif '股东户数统计截止日' in df.columns:
                        df = df.sort_values('股东户数统计截止日', ascending=True)
                    # 保存排序后的数据
                    df.to_csv(file_path, index=False, encoding='utf-8')
                    print(f"已对 {os.path.basename(file_path)} 按日期升序排序")
                except Exception as e:
                    print(f"排序文件时出错: {e}")
        
        # 适当延时，避免请求过快
        time.sleep(random.uniform(1, 2))