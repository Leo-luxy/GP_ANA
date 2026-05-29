
# fetch_industry_peers.py
# 功能：从东方财富数据中心获取与指定股票同行业且净利润排名前5的其他公司的关键财务与市值数据

import requests
import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

def fetch_industry_peers(ticker):
    """从东方财富数据中心获取同行业公司数据"""
    print(f"开始获取 {ticker} 的同行业公司数据...")
    
    # 构建API URL
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_MARKET",
        "columns": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,CORRE_SECUCODE,CORRE_SECURITY_CODE,CORRE_SECURITY_NAME,CORRE_ORG_CODE,TOTAL_CAP,FREECAP,TOTAL_OPERATEINCOME,NETPROFIT,REPORT_TYPE,TOTAL_CAP_RANK,FREECAP_RANK,TOTAL_OPERATEINCOME_RANK,NETPROFIT_RANK",
        "filter": f"(SECUCODE=\"{ticker}\")(CORRE_SECUCODE<>\"{ticker}\")(CORRE_SECUCODE<>\"行业平均\")(CORRE_SECUCODE<>\"行业中值\")",
        "pageNumber": 1,
        "pageSize": 5,
        "sortTypes": -1,
        "sortColumns": "NETPROFIT",
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
            peers_data = data['result']['data']
            print(f"成功获取 {len(peers_data)} 家同行业公司数据")
            return peers_data
        else:
            print("获取数据失败: 响应数据格式不正确")
            return []
    except Exception as e:
        print(f"获取数据时出错: {str(e)}")
        return []

def process_peers_data(peers_data, ticker):
    """处理同行业公司数据"""
    processed_data = []
    
    for item in peers_data:
        processed_item = {
            'stock_code': item.get('CORRE_SECURITY_CODE', ''),
            'stock_name': item.get('CORRE_SECURITY_NAME', ''),
            'ticker': item.get('CORRE_SECUCODE', ''),
            'total_market_cap': item.get('TOTAL_CAP', 0) / 100000000,  # 转换为亿元
            'free_market_cap': item.get('FREECAP', 0),
            'total_operating_income': item.get('TOTAL_OPERATEINCOME', 0) / 100000000,  # 转换为亿元
            'net_profit': item.get('NETPROFIT', 0) / 100000000,  # 转换为亿元
            'report_type': item.get('REPORT_TYPE', ''),
            'total_cap_rank': item.get('TOTAL_CAP_RANK', 0),
            'free_cap_rank': item.get('FREECAP_RANK', 0),
            'operating_income_rank': item.get('TOTAL_OPERATEINCOME_RANK', 0),
            'net_profit_rank': item.get('NETPROFIT_RANK', 0)
        }
        processed_data.append(processed_item)
    
    return processed_data

def save_peers_data(ticker, processed_data):
    """保存同行业公司数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名（去掉时间码）
    filename = f"{ticker}_industry_peers.json"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建保存数据
    save_data = {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'report_type': processed_data[0].get('report_type', '') if processed_data else '',
        'industry_peers': processed_data
    }
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"同行业公司数据已保存到: {file_path}")
    return file_path

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="获取同行业公司数据")
    parser.add_argument('--ticker', default='002384.SZ', help="股票代码，例如：002384.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"处理股票: {ticker}")
    
    # 获取同行业公司数据
    peers_data = fetch_industry_peers(ticker)
    
    if not peers_data:
        print("未获取到同行业公司数据")
        return
    
    # 处理数据
    processed_data = process_peers_data(peers_data, ticker)
    
    # 保存数据
    save_peers_data(ticker, processed_data)
    
    print("\n同行业公司数据获取完成！")

if __name__ == "__main__":
    main()