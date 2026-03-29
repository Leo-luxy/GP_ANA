#!/usr/bin/env python3
# index_data_collector.py
# 功能：抓取指数信息，如上证指数、深证指数等
# 支持获取指数历史数据并保存到文件
import akshare as ak
import pandas as pd
import os
import sys
import argparse
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

class IndexDataCollector:
    def __init__(self):
        self.index_data_dir = os.path.join(DATA_DIR, 'index')
        if not os.path.exists(self.index_data_dir):
            os.makedirs(self.index_data_dir)
    
    def get_index_list(self):
        """获取指数列表"""
        print("获取指数列表...")
        try:
            # 使用akshare获取指数列表
            index_list = ak.index_stock_info()
            print(f"成功获取指数列表，共 {len(index_list)} 个指数")
            return index_list
        except Exception as e:
            print(f"获取指数列表时出错: {str(e)}")
            return None
    
    def get_index_hist_data(self, index_code, start_date=None, end_date=None):
        """获取指数历史数据"""
        print(f"获取指数 {index_code} 的历史数据...")
        
        try:
            # 如果未指定日期范围，默认获取最近一年的数据
            if not start_date:
                start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')
            if not end_date:
                end_date = datetime.now().strftime('%Y%m%d')
            
            print(f"日期范围: {start_date} 到 {end_date}")
            
            # 使用akshare获取指数历史数据
            df = ak.stock_zh_index_daily(symbol=index_code)
            
            # 筛选日期范围
            df['date'] = pd.to_datetime(df['date'])
            start = pd.to_datetime(start_date)
            end = pd.to_datetime(end_date)
            df = df[(df['date'] >= start) & (df['date'] <= end)]
            
            print(f"成功获取 {len(df)} 条数据")
            return df
        except Exception as e:
            print(f"获取指数历史数据时出错: {str(e)}")
            return None
    
    def save_index_data(self, df, index_code):
        """保存指数数据到文件"""
        if df is None or df.empty:
            print("没有数据可保存")
            return None
        
        try:
            # 生成文件名
            filename = f"{index_code}_historical_data.csv"
            file_path = os.path.join(self.index_data_dir, filename)
            
            # 保存数据
            df.to_csv(file_path, index=False, encoding='utf-8')
            print(f"指数数据已保存到: {file_path}")
            return file_path
        except Exception as e:
            print(f"保存指数数据时出错: {str(e)}")
            return None
    
    def get_index_real_time(self, index_code):
        """获取指数实时数据"""
        print(f"获取指数 {index_code} 的实时数据...")
        
        max_retries = 3
        for retry in range(max_retries):
            try:
                # 使用akshare获取指数实时数据
                df = ak.stock_zh_index_spot_em()
                
                # 尝试不同的代码格式
                possible_codes = [index_code]
                
                # 如果是sh开头，尝试去掉sh前缀
                if index_code.startswith('sh'):
                    possible_codes.append(index_code.replace('sh', ''))
                # 如果是sz开头，尝试去掉sz前缀
                elif index_code.startswith('sz'):
                    possible_codes.append(index_code.replace('sz', ''))
                
                for code in possible_codes:
                    index_data = df[df['代码'] == code]
                    if not index_data.empty:
                        real_time_data = index_data.iloc[0].to_dict()
                        real_time_data['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print("成功获取实时数据")
                        print(f"指数名称: {real_time_data.get('名称')}")
                        print(f"最新价: {real_time_data.get('最新价')}")
                        print(f"涨跌幅: {real_time_data.get('涨跌幅')}%")
                        return real_time_data
                
                print(f"未找到指数 {index_code} 的实时数据")
                return None
            except Exception as e:
                print(f"获取指数实时数据时出错 (尝试 {retry+1}/{max_retries}): {str(e)}")
                if retry < max_retries - 1:
                    import time
                    time.sleep(2)
                else:
                    print("达到最大重试次数，获取实时数据失败")
                    return None

if __name__ == "__main__":
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="抓取指数信息")
    parser.add_argument('--code', help="指数代码，例如：sh000001（上证指数）、sz399001（深证成指）")
    parser.add_argument('--start', help="开始日期，格式：YYYYMMDD")
    parser.add_argument('--end', help="结束日期，格式：YYYYMMDD")
    parser.add_argument('--realtime', action='store_true', help="获取实时数据")
    parser.add_argument('--list', action='store_true', help="获取指数列表")
    
    args = parser.parse_args()
    
    collector = IndexDataCollector()
    
    if args.list:
        # 获取指数列表
        collector.get_index_list()
    elif args.realtime and args.code:
        # 获取实时数据
        collector.get_index_real_time(args.code)
    elif args.code:
        # 获取历史数据
        df = collector.get_index_hist_data(args.code, args.start, args.end)
        if df is not None:
            collector.save_index_data(df, args.code)
    else:
        # 默认获取上证指数和深证成指的历史数据
        default_indices = {
            'sh000001': '上证指数',
            'sz399001': '深证成指',
            'sh000300': '沪深300',
            'sh000016': '上证50',
            'sz399006': '创业板指'
        }
        
        print("默认获取主要指数的历史数据")
        for code, name in default_indices.items():
            print(f"\n{name} ({code})")
            df = collector.get_index_hist_data(code)
            if df is not None:
                collector.save_index_data(df, code)
