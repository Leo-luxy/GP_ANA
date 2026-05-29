
# fetch_industry_valuation.py
# 功能：从东方财富数据中心获取指定股票在其所属行业内的估值排名数据

import requests
import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

def fetch_industry_valuation(ticker):
    """从东方财富数据中心获取行业估值排名数据"""
    print(f"开始获取 {ticker} 的行业估值排名数据...")
    
    # 构建API URL
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_CVALUE",
        "columns": "ALL",
        "filter": f"(SECUCODE=\"{ticker}\")",
        "sortTypes": 1,
        "sortColumns": "PAIMING",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000))
    }
    
    # 设置请求头
    headers = {
        "Accept": "*/*",
        "Sec-Fetch-Site": "same-site",
        "Origin": "https://emweb.securities.eastmoney.com",
        "Referer": "https://emweb.securities.eastmoney.com/",
        "Sec-Fetch-Dest": "empty",
        "Accept-Language": "zh-CN,zh-Hans;q=0.9",
        "Sec-Fetch-Mode": "cors",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Priority": "u=3, I"
    }
    
    try:
        # 发送请求
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        
        if data.get('success') and data.get('result') and data['result'].get('data'):
            valuation_data = data['result']['data']
            print(f"成功获取 {len(valuation_data)} 条行业估值排名数据")
            return valuation_data
        else:
            print("获取数据失败: 响应数据格式不正确")
            return []
    except Exception as e:
        print(f"获取数据时出错: {str(e)}")
        return []

def process_valuation_data(valuation_data, ticker):
    """处理行业估值排名数据"""
    processed_data = {
        'industry_average': None,
        'industry_median': None,
        'company_data': None,
        'top_companies': []
    }
    
    for item in valuation_data:
        # 打印所有数据项，以便调试
        print(f"DEBUG: CORRE_SECURITY_CODE: {item.get('CORRE_SECURITY_CODE')}, CORRE_SECURITY_NAME: {item.get('CORRE_SECURITY_NAME')}, SECURITY_NAME_ABBR: {item.get('SECURITY_NAME_ABBR')}")
        
        if item.get('CORRE_SECURITY_NAME') == '行业平均':
            processed_data['industry_average'] = {
                'PE': item.get('PE', 0),
                'PE_TTM': item.get('PE_TTM', 0),
                'PE_1Y': item.get('PE_1Y', 0),
                'PE_2Y': item.get('PE_2Y', 0),
                'PE_3Y': item.get('PE_3Y', 0),
                'PS': item.get('PS', 0),
                'PS_TTM': item.get('PS_TTM', 0),
                'PB': item.get('PB', 0),
                'PB_MRQ': item.get('PB_MRQ', 0),
                'PEG': item.get('PEG', 0),
                'REPORT_DATE': item.get('REPORT_DATE', '')
            }
        elif item.get('CORRE_SECURITY_NAME') == '行业中值':
            processed_data['industry_median'] = {
                'PE': item.get('PE', 0),
                'PE_TTM': item.get('PE_TTM', 0),
                'PE_1Y': item.get('PE_1Y', 0),
                'PE_2Y': item.get('PE_2Y', 0),
                'PE_3Y': item.get('PE_3Y', 0),
                'PS': item.get('PS', 0),
                'PS_TTM': item.get('PS_TTM', 0),
                'PB': item.get('PB', 0),
                'PB_MRQ': item.get('PB_MRQ', 0),
                'PEG': item.get('PEG', 0),
                'REPORT_DATE': item.get('REPORT_DATE', '')
            }
        elif item.get('CORRE_SECURITY_CODE') == ticker.split('.')[0]:
            processed_data['company_data'] = {
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': item.get('CORRE_SECURITY_NAME', ''),
                'PE': item.get('PE', 0),
                'PE_TTM': item.get('PE_TTM', 0),
                'PE_1Y': item.get('PE_1Y', 0),
                'PE_2Y': item.get('PE_2Y', 0),
                'PE_3Y': item.get('PE_3Y', 0),
                'PS': item.get('PS', 0),
                'PS_TTM': item.get('PS_TTM', 0),
                'PB': item.get('PB', 0),
                'PB_MRQ': item.get('PB_MRQ', 0),
                'PEG': item.get('PEG', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', '')
            }
        elif item.get('PAIMING') and int(item.get('PAIMING')) <= 5:
            processed_data['top_companies'].append({
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': item.get('CORRE_SECURITY_NAME', ''),
                'PE': item.get('PE', 0),
                'PE_TTM': item.get('PE_TTM', 0),
                'PB': item.get('PB', 0),
                'PEG': item.get('PEG', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', '')
            })
    
    return processed_data

def save_valuation_data(ticker, processed_data):
    """保存行业估值排名数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    filename = f"{ticker}_industry_valuation.json"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建保存数据
    save_data = {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'industry_valuation': processed_data
    }
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"行业估值排名数据已保存到: {file_path}")
    return file_path

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="获取行业估值排名数据")
    parser.add_argument('--ticker', default='002384.SZ', help="股票代码，例如：002384.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"处理股票: {ticker}")
    
    # 获取行业估值排名数据
    valuation_data = fetch_industry_valuation(ticker)
    
    if not valuation_data:
        print("未获取到行业估值排名数据")
        return
    
    # 处理数据
    processed_data = process_valuation_data(valuation_data, ticker)
    
    # 保存数据
    save_valuation_data(ticker, processed_data)
    
    print("\n行业估值排名数据获取完成！")

if __name__ == "__main__":
    main()