#!/usr/bin/env python3
# test_realtime_data.py
# 功能：测试获取股票实时数据的功能
# 测试单个股票和config股票列表的实时数据获取
import akshare as ak
import json
import os
import sys
import time
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, STOCK_TICKERS

class RealtimeDataTester:
    def __init__(self):
        self.test_results = []
        self.start_time = None
    
    def test_single_stock(self, ticker):
        """测试单个股票的实时数据获取"""
        result = {
            'ticker': ticker,
            'status': 'unknown',
            'error': None,
            'data': None,
            'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        
        try:
            print(f"\n测试股票: {ticker}")
            print(f"开始时间: {result['time']}")
            
            # 转换股票代码格式为雪球格式
            xq_ticker = ticker
            if ticker.endswith('.SZ'):
                xq_ticker = "SZ" + ticker.replace('.SZ', '')
            elif ticker.endswith('.SH'):
                xq_ticker = "SH" + ticker.replace('.SH', '')
            
            print(f"转换后的雪球代码: {xq_ticker}")
            
            # 测试akshare的实时数据获取
            start = time.time()
            df = ak.stock_individual_spot_xq(symbol=xq_ticker)
            end = time.time()
            
            print(f"获取数据耗时: {end - start:.2f}秒")
            
            if not df.empty:
                # 提取实时信息
                realtime_info = df.set_index('item')['value'].to_dict()
                # 添加更新时间
                realtime_info['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                result['status'] = 'success'
                result['data'] = realtime_info
                print(f"成功获取实时数据，包含 {len(realtime_info)} 个字段")
                # 打印部分关键字段
                key_fields = ['最新价', '涨跌幅', '成交量', '成交额', '市盈率(TTM)']
                for field in key_fields:
                    if field in realtime_info:
                        print(f"  {field}: {realtime_info[field]}")
            else:
                result['status'] = 'empty'
                result['error'] = '未获取到数据'
                print("未获取到实时数据")
                
        except Exception as e:
            result['status'] = 'error'
            result['error'] = str(e)
            print(f"获取实时数据时出错: {str(e)}")
        
        self.test_results.append(result)
        return result
    
    def test_all_stocks(self):
        """测试config中的所有股票"""
        print("\n" + "="*60)
        print("开始测试所有股票的实时数据获取")
        print("="*60)
        
        self.start_time = datetime.now()
        print(f"测试开始时间: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        for name, ticker in STOCK_TICKERS.items():
            print(f"\n{name} ({ticker})")
            print("-" * 40)
            self.test_single_stock(ticker)
            # 添加延迟，避免API限流
            time.sleep(2)
        
        end_time = datetime.now()
        print("\n" + "="*60)
        print(f"测试结束时间: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"总耗时: {(end_time - self.start_time).total_seconds():.2f}秒")
        print("="*60)
    
    def generate_report(self):
        """生成测试报告"""
        print("\n" + "="*80)
        print("测试报告")
        print("="*80)
        
        total = len(self.test_results)
        success = sum(1 for r in self.test_results if r['status'] == 'success')
        error = sum(1 for r in self.test_results if r['status'] == 'error')
        empty = sum(1 for r in self.test_results if r['status'] == 'empty')
        
        print(f"总测试股票数: {total}")
        print(f"成功: {success} ({success/total*100:.1f}%)")
        print(f"失败: {error} ({error/total*100:.1f}%)")
        print(f"无数据: {empty} ({empty/total*100:.1f}%)")
        
        print("\n失败详情:")
        for result in self.test_results:
            if result['status'] == 'error':
                print(f"  {result['ticker']}: {result['error']}")
        
        # 保存测试结果到文件
        report_dir = os.path.join(DATA_DIR, 'test_results')
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
        
        report_file = os.path.join(report_dir, f"realtime_data_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\n测试结果已保存到: {report_file}")

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="测试股票实时数据获取功能")
    parser.add_argument('--ticker', help="单个股票代码，例如：600519.SH（上交所）、000001.SZ（深交所）")
    parser.add_argument('--all', action='store_true', help="测试所有股票")
    args = parser.parse_args()
    
    tester = RealtimeDataTester()
    
    if args.ticker:
        # 测试单个股票
        tester.test_single_stock(args.ticker)
    elif args.all:
        # 测试所有股票
        tester.test_all_stocks()
    else:
        # 默认测试所有股票
        tester.test_all_stocks()
    
    # 生成测试报告
    tester.generate_report()
