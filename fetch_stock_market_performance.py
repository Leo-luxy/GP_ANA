
# fetch_stock_market_performance.py
# 功能：从东方财富数据中心获取指定股票的历史日度市场表现数据

import requests
import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

def fetch_market_performance(ticker):
    """从东方财富数据中心获取历史日度市场表现数据"""
    print(f"开始获取 {ticker} 的历史日度市场表现数据...")
    
    # 构建API URL - 使用TIME_TYPE=1
    url = "https://datacenter.eastmoney.com/securities/api/data/v1/get"
    params = {
        "reportName": "RPT_PCF10_MARKETPER",
        "columns": "ALL",
        "filter": f"(SECUCODE=\"{ticker}\")(TIME_TYPE=1)",
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
        "Priority": "u=3, i"
    }
    
    try:
        # 发送请求
        response = requests.get(url, params=params, headers=headers)
        response.raise_for_status()
        
        # 解析响应
        data = response.json()
        
        if data.get('success') and data.get('result') and data['result'].get('data'):
            market_data = data['result']['data']
            print(f"成功获取 {len(market_data)} 条历史日度市场表现数据 (TIME_TYPE=1)")
            
            # 打印所有数据，按日期排序
            print("\n所有数据（按日期升序）：")
            sorted_data = sorted(market_data, key=lambda x: x.get('TRADE_DATE', ''))
            for i, item in enumerate(sorted_data):
                print(f"日期: {item.get('TRADE_DATE', '')}, CHANGERATE: {item.get('CHANGERATE', 0):.2f}%")
            
            return market_data
        else:
            print("获取数据失败: 响应数据格式不正确")
            return []
    except Exception as e:
        print(f"获取数据时出错: {str(e)}")
        return []

def process_market_data(market_data, ticker):
    """处理历史日度市场表现数据"""
    processed_data = []
    
    for item in market_data:
        # 获取原始涨跌幅数据
        change_rate = item.get('CHANGERATE', 0)
        
        # 不过滤数据，保留所有数据以便分析
        processed_item = {
            'trade_date': item.get('TRADE_DATE', ''),
            'change_rate': change_rate,
            'hs300_change_rate': item.get('HS300_CHANGERATE', 0),
            'board_change_rate': item.get('BOARD_CHANGERATE', 0),
            'board_name': item.get('BOARD_NAME', ''),
            'board_code': item.get('BOARD_CODE', '')
        }
        processed_data.append(processed_item)
    
    # 按日期排序（最新日期在前）
    processed_data.sort(key=lambda x: x['trade_date'], reverse=True)
    
    return processed_data

def save_market_data(ticker, processed_data):
    """保存历史日度市场表现数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    filename = f"{ticker}_market_performance.json"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建保存数据
    save_data = {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'market_performance': processed_data
    }
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)
    
    print(f"历史日度市场表现数据已保存到: {file_path}")
    return file_path

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="获取历史日度市场表现数据")
    parser.add_argument('--ticker', default='002384.SZ', help="股票代码，例如：002384.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"处理股票: {ticker}")
    
    # 获取历史日度市场表现数据
    market_data = fetch_market_performance(ticker)
    
    if not market_data:
        print("未获取到历史日度市场表现数据")
        return
    
    # 处理数据
    processed_data = process_market_data(market_data, ticker)
    
    # 保存数据
    save_market_data(ticker, processed_data)
    
    print("\n历史日度市场表现数据获取完成！")

if __name__ == "__main__":
    main()