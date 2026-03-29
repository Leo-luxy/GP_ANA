#!/usr/bin/env python3
# stock_company_info_collector.py
# 功能：获取股票公司的基本信息、资金流、研究报告、主要股东等信息
# 实现原理：
# 1. 从config.py中获取股票列表
# 2. 对每只股票，使用akshare获取各种信息
# 3. 进行错误处理，防止某个信息返回为空
# 4. 将获取的信息保存到该股票文件夹下的company_info.json文件中

import akshare as ak
import pandas as pd
import json
import os
import time
import random
import sys
from datetime import date, datetime, timedelta

# 文件现在在根目录，不需要添加路径

from config import DATA_DIR, STOCK_TICKERS


class DateEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理日期对象"""
    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            try:
                return obj.strftime('%Y-%m-%d')
            except:
                return None
        elif isinstance(obj, pd.Timestamp):
            try:
                if pd.isna(obj):
                    return None
                return obj.strftime('%Y-%m-%d')
            except:
                return None
        return super().default(obj)


def get_stock_company_info(ticker):
    """获取单个股票的公司信息"""
    print(f"\n开始获取 {ticker} 的公司信息...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 初始化结果字典
    company_info = {
        'ticker': ticker,
        'code': code,
        'market': market,
        'data_sources': ['akshare'],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'basic_info': {},
        'research_reports': [],
        'main_shareholders': [],
        'financial_report': {},
        'business_scope': ''
    }
    
    # 1. 获取股票基本信息
    
    print("获取基本信息...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        if market == 'sh':
            stock_symbol = f"SH{code}"
        else:
            stock_symbol = f"SZ{code}"
        stock_individual_basic_info_xq_df = ak.stock_individual_basic_info_xq(symbol=stock_symbol)
        
        # 检查DataFrame是否为空
        if not stock_individual_basic_info_xq_df.empty:
            # 检查DataFrame结构，处理不同格式
            basic_info_dict = stock_individual_basic_info_xq_df.set_index('item')['value'].to_dict()
            
            # 字段映射关系
            field_mapping = {
                'org_name_cn': '公司全称',
                'org_short_name_cn': '公司简称',
                'main_operation_business': '主营业务',
                'established_date': '成立日期',
                'reg_asset': '注册资本',
                'staff_num': '员工人数',
                'listed_date': '上市日期',
                'actual_controller': '实际控制人',
                'executives_nums': '高管人数',
                'actual_issue_vol': '实际发行数量',
                'issue_price': '发行价格',
                'actual_rc_net_amt': '实际募集资金净额',
                'pe_after_issuing': '发行后市盈率',
                'online_success_rate_of_issue': '网上发行成功率',
                'affiliate_industry': '所属行业',
                'operating_scope': '经营范围',
                'org_cn_introduction': '公司介绍'
            }
            
            # 过滤出只包含指定字段的字典
            filtered_basic_info = {}
            for source_field, target_field in field_mapping.items():
                if source_field in basic_info_dict:
                    filtered_basic_info[target_field] = basic_info_dict[source_field]

            company_info['basic_info'] = filtered_basic_info
        else:
            print("基本信息DataFrame为空")
    except Exception as e:
        print(f"获取基本信息时出错: {str(e)}")
    
    # 2. 获取股票规模对比
    print("获取股票规模对比...")
    try:
        time.sleep(random.uniform(2, 4))
        scale_df = ak.stock_zh_scale_comparison_em(symbol=code)
        if not scale_df.empty:
            company_info['scale_comparison'] = scale_df.to_dict('records')
    except Exception as e:
        print(f"获取股票规模对比时出错: {str(e)}")
    
    # 3. 获取股票主营业务
    print("获取主营业务...")
    try:
        time.sleep(random.uniform(2, 4))
        business_df = ak.stock_zyjs_ths(symbol=code)
        if not business_df.empty:
            company_info['business_scope'] = business_df.to_dict('records')[0].get('主营业务', '')
    except Exception as e:
        print(f"获取主营业务时出错: {str(e)}")
    

    
    # 5. 获取股票研究报告
    print("获取研究报告...")
    try:
        time.sleep(random.uniform(2, 4))
        report_df = ak.stock_research_report_em(symbol=code)
        if not report_df.empty:
            # 保存所有研究报告
            company_info['research_reports'] = report_df.to_dict('records')
    except Exception as e:
        print(f"获取研究报告时出错: {str(e)}")
    
    # 6. 获取股票主要股东
    print("获取主要股东...")
    try:
        time.sleep(random.uniform(2, 4))
        shareholder_df = ak.stock_main_stock_holder(stock=code)
        if not shareholder_df.empty:
            # 保存所有主要股东数据
            company_info['main_shareholders'] = shareholder_df.to_dict('records')
    except Exception as e:
        print(f"获取主要股东时出错: {str(e)}")
    
    # 7. 获取财务报表
    print("获取财务报表...")
    try:
        time.sleep(random.uniform(2, 4))
        stock_symbol_sina = f"{market}{code}"
        profit_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="利润表")
        if not profit_df.empty:
            # 保存所有利润表数据
            company_info['financial_report']['profit'] = profit_df.to_dict('records')
        
        time.sleep(random.uniform(2, 4))
        balance_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="资产负债表")
        if not balance_df.empty:
            # 保存所有资产负债表数据
            company_info['financial_report']['balance'] = balance_df.to_dict('records')
    except Exception as e:
        print(f"获取财务报表时出错: {str(e)}")
    

    
    # 9. 获取财务摘要
    print("获取财务摘要...")
    try:
        time.sleep(random.uniform(2, 4))
        financial_abstract_df = ak.stock_financial_abstract(symbol=code)
        if not financial_abstract_df.empty:
            company_info['financial_abstract'] = financial_abstract_df.to_dict('records')[0]
    except Exception as e:
        print(f"获取财务摘要时出错: {str(e)}")
    
    # 保存到json文件
    output_file = os.path.join(stock_dir, f"{ticker}_company_info.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(company_info, f, ensure_ascii=False, indent=2, cls=DateEncoder)
    
    print(f"公司信息已保存到: {output_file}")
    return company_info


def main():
    """主函数"""
    print("开始收集公司信息...")
    MY_STOCK_TICKERS = {
        'zycx': '688766.SH',  # 兆易创新
        # 可以添加更多股票代码
        # 'example': '000001.SZ'  # 示例股票
    }
    # 遍历所有股票
    for name, ticker in MY_STOCK_TICKERS.items():
        get_stock_company_info(ticker)
    
    print("\n公司信息收集完成！")


if __name__ == "__main__":
    main()
