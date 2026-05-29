import requests
import csv
import random
import time
import os
import argparse
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
                    if id_field == 'HOLDER_CODE' and 'REPORT_DATE' in row:
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
        if id_field == 'HOLDER_CODE' and 'REPORT_DATE' in item:
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
    else:
        print("无新数据需要保存")

def fetch_org_hold_detail(secucode, report_date, org_type='01', page_size=50, save_path='org_hold_detail.csv'):
    """
    抓取机构持股明细并保存为 CSV
    使用手动构建 URL 的方式确保 filter 参数编码正确
    """
    base_url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    
    # 请求头（与原始 curl 保持一致）
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
    
    # 固定参数（除 filter 外）
    common_params = {
        'reportName': 'RPT_MAIN_ORGHOLDDETAIL',
        'columns': ','.join([
            'ORG_TYPE', 'SECUCODE', 'REPORT_DATE', 'HOLDER_CODE', 'HOLDER_NAME',
            'TOTAL_SHARES', 'HOLD_VALUE', 'TOTALSHARES_RATIO', 'FREESHARES_RATIO',
            'FREE_MARKET_CAP', 'FREE_SHARES', 'SECURITY_CODE', 'FUND_CODE',
            'FUND_DERIVECODE', 'NETVALUE_RATIO'
        ]),
        'quoteColumns': '',
        'source': 'HSF10',
        'client': 'PC',
        'sortTypes': '-1',
        'sortColumns': 'TOTAL_SHARES',
    }
    
    all_data = []
    page = 1
    while True:
        # 动态生成 filter 字符串，并手动编码（括号保留，等号和引号编码）
        filter_raw = f'(SECUCODE="{secucode}")(ORG_TYPE="{org_type}")(REPORT_DATE=\'{report_date}\')'
        filter_encoded = quote(filter_raw, safe='()')  # safe='()' 使括号不被编码
        # 示例结果: (SECUCODE%3D%22002594.SZ%22)(ORG_TYPE%3D%2201%22)(REPORT_DATE%3D%272025-12-31%27)
        
        # 分页参数
        page_params = {
            'pageNumber': page,
            'pageSize': page_size,
            'v': str(int(time.time() * 1000)),  # 时间戳防缓存
        }
        
        # 合并所有参数（filter 单独处理）
        params = {**common_params, **page_params}
        # 使用 urlencode 编码除 filter 外的参数，但注意 urlencode 会编码所有字符（包括括号等），这里 safe 参数可保留括号，但其他参数中无括号，忽略）
        other_params_encoded = urlencode(params, safe='()')
        
        # 构建完整 URL
        full_url = f"{base_url}?{other_params_encoded}&filter={filter_encoded}"
        
        try:
            print(f"正在请求第 {page} 页...")
            response = requests.get(full_url, headers=headers, timeout=15)
            response.raise_for_status()
            
            # 调试：打印状态码和响应开头
            print(f"状态码: {response.status_code}")
            print(f"响应内容前200字符: {response.text[:200]}")
            
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"网络请求失败: {e}")
            break
        except ValueError as e:
            print(f"JSON 解析失败: {e}")
            print("原始响应内容:", response.text[:500])
            break
        
        # 处理返回数据
        if not data.get('success', False):
            print(f"接口返回错误: {data.get('message', '未知错误')}")
            break
        
        result = data.get('result')
        if result is None:
            print("返回数据中无 result 字段")
            break
        
        records = result.get('data', [])
        if not records:
            print(f"第 {page} 页无数据")
            break
        
        all_data.extend(records)
        print(f"已抓取第 {page} 页，共 {len(records)} 条记录")
        
        if len(records) < page_size:
            break
        page += 1
        time.sleep(1)  # 适当延时，避免请求过快
    
    if not all_data:
        print("未获取到任何数据")
        return
    
    # 保存 CSV
    try:
        if all_data:
            # 定义字段名
            fieldnames = ['ORG_TYPE', 'SECUCODE', 'REPORT_DATE', 'HOLDER_CODE', 'HOLDER_NAME',
                        'TOTAL_SHARES', 'HOLD_VALUE', 'TOTALSHARES_RATIO', 'FREESHARES_RATIO',
                        'FREE_MARKET_CAP', 'FREE_SHARES', 'SECURITY_CODE', 'FUND_CODE',
                        'FUND_DERIVECODE', 'NETVALUE_RATIO']
            # 使用增量保存函数
            save_to_csv(save_path, all_data, fieldnames, 'HOLDER_CODE')
    except Exception as e:
        print(f"保存文件失败: {e}")

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='股东持股信息采集器')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：002594.SZ')
    parser.add_argument('--report-date', type=str, default='2025-12-31', help='报告日期，默认：2025-12-31')
    parser.add_argument('--org-type', type=str, default='01', help='机构类型，默认：01')
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
        save_path = f"{data_dir}/{ticker}_institutional_holdings.csv"
        
        # 抓取数据
        fetch_org_hold_detail(
            secucode=ticker,
            report_date=args.report_date,
            org_type=args.org_type,
            page_size=args.page_size,
            save_path=save_path
        )
        
        # 适当延时，避免请求过快
        time.sleep(random.uniform(2, 4))