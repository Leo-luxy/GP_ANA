#!/opt/anaconda3/envs/PythonProject/bin/python
import akshare as ak
import pandas as pd
import random
import time
import json



# 股票基本信息
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
ticker_code = "603861.SH"
short_code = ticker_code.split(".")[0]
market = 'sh' if ticker_code.endswith('.SH') else 'sz'
if market == 'sh':
    stock_symbol = f"SH{short_code}"
else:
    stock_symbol = f"SZ{short_code}"

# 股票财务指标
# time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
# stock_financial_analysis_indicator_df = ak.stock_financial_analysis_indicator(symbol="603861", start_year="2023")
# print(stock_financial_analysis_indicator_df)

# 股东户数
# time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
# stock_zh_a_gdhs_detail_em_df = ak.stock_zh_a_gdhs_detail_em(symbol="603861")
# print(stock_zh_a_gdhs_detail_em_df)

stock_zyjs_ths_df = ak.stock_zyjs_ths(symbol="300433")
print(stock_zyjs_ths_df)
"""
#stock_individual_info_em_df = ak.stock_individual_info_em(symbol=stock_symbol)
stock_individual_basic_info_xq_df = ak.stock_individual_basic_info_xq(symbol=stock_symbol)
print(stock_individual_basic_info_xq_df)
if not stock_individual_basic_info_xq_df.empty:
    filepath = f"data/{ticker_code}/{ticker_code}_company_info.txt"
    stock_individual_basic_info_xq_df.to_csv(filepath, index=False, encoding='utf-8-sig')

if not stock_individual_basic_info_xq_df.empty:
    # 只保留用户指定的字段
    basic_info_dict = stock_individual_basic_info_xq_df.set_index('item')['value'].to_dict()
    print(basic_info_dict)
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
    print(filtered_basic_info)
    # 初始化company_info字典
    company_info = {
        'ticker': ticker_code,
        'code': short_code,
        'market': market,
        'data_sources': ['akshare'],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'basic_info': filtered_basic_info
    }
    
    # 打印结果
    print("\n过滤后的数据:")
    print(json.dumps(company_info, ensure_ascii=False, indent=2))
    
    # 保存到json文件
    output_file = f"data/{ticker_code}/{ticker_code}_company_info_test.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(company_info, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")
        

# 股票规模对比
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_zh_scale_comparison_em_df = ak.stock_zh_scale_comparison_em(symbol="SH600313")
print(stock_zh_scale_comparison_em_df)

# 股票主营业务
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_zyjs_ths_df = ak.stock_zyjs_ths(symbol="600313")
print(stock_zyjs_ths_df)

# 股票资金流
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_individual_fund_flow_df = ak.stock_individual_fund_flow(stock="600313", market="sh")
print(stock_individual_fund_flow_df)

# 股票研究报告
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_research_report_em_df = ak.stock_research_report_em(symbol="600313")
print(stock_research_report_em_df)

# 股票资产负债表
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_financial_report_sina_df = ak.stock_financial_report_sina(stock="sh600313", symbol="利润表")
print(stock_financial_report_sina_df)
stock_financial_report_sina_df = ak.stock_financial_report_sina(stock="sh600313", symbol="资产负债表")
print(stock_financial_report_sina_df)

# 股票主股东
time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
stock_main_stock_holder_df = ak.stock_main_stock_holder(stock="600313")
print(stock_main_stock_holder_df)

STOCK_TICKERS = {
    '300469.SZ',  # 信息发展
    '300433.SZ',  # 蓝思科技
    '603267.SH',  # 鸿远电子
    '603993.SH',  # 洛阳钼业
    '688052.SH',  # 纳芯微
    '600313.SH',  # 农发种业
    # 可以添加更多股票代码
    # 'example': '000001.SZ'  # 示例股票
}
for ticker in STOCK_TICKERS:
    # 1. 获取某一天深市的全市场融资融券明细
    target_date = "20260317"
    sz_margin_all = ak.stock_margin_detail_szse(date=target_date)

    # 2. 假设你关心的股票代码是 "000858" (五粮液)
    my_stock_code = ticker.split('.')[0]  # 从配置中提取股票代码部分    

    # 3. 从全市场数据中筛选出目标股票
    my_stock_margin = sz_margin_all[sz_margin_all['证券代码'] == my_stock_code]

    # 如果当天该股票有融资融券数据，就打印出来
    if not my_stock_margin.empty:
        print(f"找到股票 {my_stock_code} 在 {target_date} 的数据：")
        print(my_stock_margin)
    else:
        print(f"在 {target_date} 未找到股票 {my_stock_code} 的融资融券数据，可能当日不是标的证券或无交易。")
"""