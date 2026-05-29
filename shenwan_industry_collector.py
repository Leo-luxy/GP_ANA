#!/usr/bin/env python3
# 程序：使用akshare获取申万三级行业信息

import akshare as ak
import pandas as pd
import json
import os
from datetime import datetime, timedelta

# 创建数据存储目录
data_dir = os.path.join(os.path.dirname(__file__), 'data', 'shenwan_industry')
os.makedirs(data_dir, exist_ok=True)

def get_shenwan_industry_level1():
    """获取申万一级行业信息"""
    try:
        print("开始获取申万一级行业信息...")
        # 使用akshare获取申万行业分类
        industry_df = ak.sw_index_first_info()
        
        print("获取到的申万一级行业信息：")
        print(industry_df)
        
        # 保存数据
        output_file = os.path.join(data_dir, 'shenwan_industry_level1.csv')
        industry_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到 {output_file}")
        
        return industry_df
    except Exception as e:
        print(f"获取申万一级行业信息时出错: {str(e)}")
        return None

def get_shenwan_industry_level2():
    """获取申万二级行业信息"""
    try:
        print("开始获取申万二级行业信息...")
        # 使用akshare获取申万二级行业分类
        industry_df = ak.sw_index_second_info()
        
        print("获取到的申万二级行业信息：")
        print(industry_df)
        
        # 保存数据
        output_file = os.path.join(data_dir, 'shenwan_industry_level2.csv')
        industry_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到 {output_file}")
        
        return industry_df
    except Exception as e:
        print(f"获取申万二级行业信息时出错: {str(e)}")
        return None





def get_shenwan_industry_full_info():
    """获取完整的申万行业信息，包括各级行业"""
    try:
        print("开始获取完整的申万行业信息...")
        
        # 首先获取一级行业
        level1_df = get_shenwan_industry_level1()
        
        if level1_df is not None:
            full_industry_info = {}
            
            for _, row in level1_df.iterrows():
                industry_code = row['board_code']
                industry_name = row['board_name']
                
                # 获取该行业的股票列表
                stocks_df = get_shenwan_industry_stocks(industry_code)
                
                if stocks_df is not None:
                    full_industry_info[industry_name] = {
                        'code': industry_code,
                        'stocks': stocks_df.to_dict('records')
                    }
            
            # 保存完整信息
            output_file = os.path.join(data_dir, 'shenwan_industry_full_info.json')
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(full_industry_info, f, ensure_ascii=False, indent=2)
            print(f"\n完整行业信息已保存到 {output_file}")
            
            return full_industry_info
        else:
            print("无法获取一级行业信息")
            return None
    except Exception as e:
        print(f"获取完整行业信息时出错: {str(e)}")
        return None

def get_shenwan_industry_level3():
    """获取申万三级行业信息"""
    try:
        print("开始获取申万三级行业信息...")
        # 使用akshare获取申万三级行业信息
        industry_df = ak.sw_index_third_info()
        
        print("获取到的申万三级行业信息：")
        print(industry_df)
        
        # 保存数据
        output_file = os.path.join(data_dir, 'shenwan_industry_level3.csv')
        industry_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到 {output_file}")
        
        return industry_df
    except Exception as e:
        print(f"获取申万三级行业信息时出错: {str(e)}")
        return None

def get_shenwan_industry_level3_stocks(industry_code):
    """获取指定申万三级行业的股票列表"""
    try:
        print(f"开始获取申万三级行业代码 {industry_code} 的股票列表...")
        # 使用akshare获取申万三级行业成分股
        stocks_df = ak.sw_index_third_cons(symbol=industry_code)
        
        print(f"获取到的股票列表：")
        print(stocks_df)
        
        # 保存数据
        output_file = os.path.join(data_dir, f'shenwan_industry_level3_{industry_code}_stocks.csv')
        stocks_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        print(f"\n数据已保存到 {output_file}")
        
        return stocks_df
    except Exception as e:
        print(f"获取申万三级行业股票列表时出错: {str(e)}")
        return None

def get_industry_for_stock(stock_code):
    """获取指定股票的所属行业"""
    try:
        print(f"开始获取股票 {stock_code} 的所属行业...")
        
        # 读取company_basic.json文件
        company_basic_file = os.path.join(os.path.dirname(__file__), 'data', stock_code, f'{stock_code}_company_basic.json')
        if os.path.exists(company_basic_file):
            with open(company_basic_file, 'r', encoding='utf-8') as f:
                company_basic = json.load(f)
            
            print(f"股票 {stock_code} 的基本信息：")
            print(company_basic)
            
            # 提取板块名称层级
            if 'basic_info' in company_basic and '板块名称层级' in company_basic['basic_info']:
                industry_level = company_basic['basic_info']['板块名称层级']
                print(f"\n板块名称层级: {industry_level}") 
                return industry_level
            else:
                print("未找到板块名称层级字段")
                return None
        else:
            print(f"公司基本信息文件不存在: {company_basic_file}")
            return None
    except Exception as e:
        print(f"获取股票行业信息时出错: {str(e)}")
        return None

def calculate_industry_average(stocks_df):
    """根据成分股信息计算行业平均数据"""
    try:
        if stocks_df is not None and not stocks_df.empty:
            # 计算行业平均数据
            average_data = {
                '平均市值(亿元)': round(stocks_df.get('市值', pd.Series([0])).mean(), 3),
                '平均市盈率': round(stocks_df.get('市盈率', pd.Series([0])).mean(), 3),
                '平均市盈率TTM': round(stocks_df.get('市盈率ttm', pd.Series([0])).mean(), 3),
                '平均市净率': round(stocks_df.get('市净率', pd.Series([0])).mean(), 3),
                '平均股息率(%)': round(stocks_df.get('股息率', pd.Series([0])).mean(), 3),
                '平均价格(元)': round(stocks_df.get('价格', pd.Series([0])).mean(), 3),
                '平均营收增长率(09-30)(%)': round(stocks_df.get('营业收入同比增长(09-30)', pd.Series([0])).mean(), 3),
                '平均净利润增长率(09-30)(%)': round(stocks_df.get('归母净利润同比增长(09-30)', pd.Series([0])).mean(), 3),
                '平均营收增长率(06-30)(%)': round(stocks_df.get('营业收入同比增长(06-30)', pd.Series([0])).mean(), 3),
                '平均净利润增长率(06-30)(%)': round(stocks_df.get('归母净利润同比增长(06-30)', pd.Series([0])).mean(), 3)
            }
            return average_data
        else:
            return {}
    except Exception as e:
        print(f"计算行业平均数据时出错: {str(e)}")
        return {}

if __name__ == "__main__":
    print("===== 申万行业信息收集程序 =====")
    print("开始按顺序执行任务...")
    
    import argparse
    parser = argparse.ArgumentParser(description='申万行业信息收集')
    parser.add_argument('--ticker', type=str, help='指定股票代码（如002384.SZ）')
    args = parser.parse_args()
    
    # 1. 获取申万一级行业信息
    print("\n1. 获取申万一级行业信息")
    level1_df = get_shenwan_industry_level1()
    
    # 2. 获取申万二级行业信息
    print("\n2. 获取申万二级行业信息")
    level2_df = get_shenwan_industry_level2()
    
    # 3. 获取申万三级行业信息
    print("\n3. 获取申万三级行业信息")
    level3_df = get_shenwan_industry_level3()
    
    if args.ticker:
        # 处理指定股票
        print(f"\n处理股票: {args.ticker}")
        
        # 获取股票的板块名称层级
        industry_level = get_industry_for_stock(args.ticker)
        
        if industry_level:
            print(f"\n根据板块名称层级: {industry_level} 获取相关三级行业信息")
            
            if level3_df is not None and not level3_df.empty:
                # 提取板块名称层级的最后一级
                industry_parts = industry_level.split('-')
                if len(industry_parts) > 0:
                    target_industry = industry_parts[-1].strip()
                    print(f"\n目标行业: {target_industry}")
                    
                    # 查找相关的三级行业
                    relevant_industries = level3_df[level3_df['行业名称'].str.contains(target_industry, na=False)]
                    
                    if not relevant_industries.empty:
                        print(f"\n找到 {len(relevant_industries)} 个相关三级行业:")
                        print(relevant_industries)
                        
                        # 为每个相关行业获取股票列表并计算平均数据
                        for _, row in relevant_industries.iterrows():
                            industry_code = row['行业代码']
                            industry_name = row['行业名称']
                            print(f"\n获取行业: {industry_name} ({industry_code}) 的股票列表")
                            stocks_df = get_shenwan_industry_level3_stocks(industry_code)
                            
                            # 计算行业平均数据
                            industry_average = calculate_industry_average(stocks_df)
                            print(f"\n行业平均数据: {industry_average}")
                            
                            # 计算数据来源时间：17:00之前为前一天，17:00之后为当天
                            now = datetime.now()
                            if now.hour < 17:
                                data_source_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
                            else:
                                data_source_date = now.strftime('%Y-%m-%d')
                            
                            # 构建行业信息字典
                            industry_info = {
                                'ticker': args.ticker,
                                'industry_level': industry_level,
                                'level1_industry': industry_parts[0] if len(industry_parts) > 0 else '',
                                'level2_industry': industry_parts[1] if len(industry_parts) > 1 else '',
                                'level3_industry': industry_parts[2] if len(industry_parts) > 2 else '',
                                'industry_code': industry_code,
                                'industry_name': industry_name,
                                'industry_average': industry_average,
                                'data_source_timestamp': data_source_date,  # 以最近一个交易日的时间为准
                                'fetch_timestamp': now.strftime('%Y-%m-%d %H:%M:%S')
                            }
                            
                            # 保存到data/{ticker}文件夹中
                            ticker_data_dir = os.path.join(os.path.dirname(__file__), 'data', args.ticker)
                            os.makedirs(ticker_data_dir, exist_ok=True)
                            output_file = os.path.join(ticker_data_dir, f'{args.ticker}_industry_info.json')
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(industry_info, f, ensure_ascii=False, indent=2)
                            print(f"\n行业信息已保存到 {output_file}")
                    else:
                        print(f"未找到与 '{target_industry}' 相关的三级行业")
    else:
        # 4. 获取部分申万三级行业的股票列表（示例）
        if level3_df is not None and not level3_df.empty:
            print("\n4. 获取部分申万三级行业的股票列表")
            # 取前2个行业作为示例
            sample_industries = level3_df.head(2)
            for _, row in sample_industries.iterrows():
                industry_code = row['行业代码']
                industry_name = row['行业名称']
                print(f"\n获取行业: {industry_name} ({industry_code}) 的股票列表")
                get_shenwan_industry_level3_stocks(industry_code)
    
    print("\n所有任务执行完成")
