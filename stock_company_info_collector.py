# stock_company_info_collector.py
# 功能：获取股票公司的基本信息、资金流、研究报告、主要股东等信息
# 实现原理：
# 1. 从config.py中获取股票列表
# 2. 对每只股票，使用akshare获取各种信息
# 3. 进行错误处理，防止某个信息返回为空
# 4. 将获取的信息保存到对应的分离文件中

import akshare as ak
import pandas as pd
import json
import os
import time
import random
import sys
from datetime import date, datetime, timedelta
import csv

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


def load_existing_data(file_path):
    """加载现有数据"""
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载文件失败: {e}")
    return {}


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
                    if id_field == '序号':
                        # 对于研究报告和主要股东数据，使用序号+日期作为唯一标识
                        if '日期' in row:
                            row_id = f"{row.get('序号', '')}_{row.get('日期', '')}"
                        elif '截至日期' in row:
                            row_id = f"{row.get('序号', '')}_{row.get('截至日期', '')}"
                        else:
                            row_id = str(row.get(id_field, ''))
                    elif id_field == 'HOLDER_CODE' and 'REPORT_DATE' in row:
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
        if id_field == '序号':
            # 对于研究报告和主要股东数据，使用序号+日期作为唯一标识
            if '日期' in item:
                item_id = f"{item.get('序号', '')}_{item.get('日期', '')}"
            elif '截至日期' in item:
                item_id = f"{item.get('序号', '')}_{item.get('截至日期', '')}"
            else:
                item_id = str(item.get(id_field, ''))
        elif id_field == 'HOLDER_CODE' and 'REPORT_DATE' in item:
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
        'business_scope': '',
        'financial_abstract': {}
    }
    
    # 1. 获取股票基本信息
    
    print("获取基本信息...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        if market == 'sh':
            stock_symbol = f"SH{code}"
        else:
            stock_symbol = f"SZ{code}"
        
        # 方法2: 使用东方财富 API 获取基本信息
        try:
            print("使用方法2获取基本信息...")
            import requests
            import json
            
            # 构建东方财富 API URL
            url = f"https://datacenter.eastmoney.com/securities/api/data/v1/get"
            params = {
                "reportName": "RPT_F10_BASIC_ORGINFO",
                "columns": "ALL",
                "filter": f"(SECUCODE=\"{ticker}\")",
                "pageNumber": 1,
                "pageSize": 1,
                "source": "HSF10",
                "client": "PC",
                "v": str(int(time.time() * 1000))
            }
            
            headers = {
                "Accept": "*/*",
                "Sec-Fetch-Site": "same-site",
                "Origin": "https://emweb.securities.eastmoney.com",
                "Referer": "https://emweb.securities.eastmoney.com/",
                "Sec-Fetch-Dest": "empty",
                "Accept-Language": "zh-CN,zh-Hans;q=0.9",
                "Sec-Fetch-Mode": "cors",
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
                "Connection": "keep-alive"
            }
            
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('success') and data.get('result') and data['result'].get('data'):
                stock_info = data['result']['data'][0]
                # 保存所有返回的字段
                basic_info_dict = stock_info
                print(f"成功获取 {len(basic_info_dict)} 个字段的基本信息")
            else:
                print("方法2获取的基本信息为空")
                basic_info_dict = {}
        except Exception as e2:
            print(f"方法2获取基本信息时出错: {str(e2)}")
            basic_info_dict = {}
        
        # 保留所有字段，并添加中文映射
        filtered_basic_info = {}
        
        # 字段映射，将英文字段映射为中文
        field_mapping = {
            'SECURITY_NAME_ABBR': '公司简称',
            'ORG_NAME': '公司全称',
            'FOUND_DATE': '成立日期',
            'LISTING_DATE': '上市日期',
            'REG_CAPITAL': '注册资本',
            'EMP_NUM': '员工人数',
            'BUSINESS_SCOPE': '经营范围',
            'MAIN_BUSINESS': '主营业务',
            'ADDRESS': '地址',
            'ORG_TEL': '电话',
            'ORG_EMAIL': '邮箱',
            'ORG_WEB': '网站',
            'SECUCODE': '证券代码',
            'SECURITY_CODE': '股票代码',
            'ORG_CODE': '组织机构代码',
            'ORG_NAME_EN': '公司英文名称',
            'FORMERNAME': '曾用名',
            'STR_CODEA': 'A股代码',
            'STR_NAMEA': 'A股名称',
            'STR_CODEB': 'B股代码',
            'STR_NAMEB': 'B股名称',
            'STR_CODEH': 'H股代码',
            'STR_NAMEH': 'H股名称',
            'SECURITY_TYPE': '证券类型',
            'EM2016': 'EM2016行业分类',
            'TRADE_MARKET': '交易市场',
            'INDUSTRYCSRC1': 'CSRC行业分类',
            'PRESIDENT': '总裁',
            'LEGAL_PERSON': '法人代表',
            'SECRETARY': '董秘',
            'CHAIRMAN': '董事长',
            'SECPRESENT': '证券事务代表',
            'INDEDIRECTORS': '独立董事',
            'ORG_FAX': '传真',
            'REG_ADDRESS': '注册地址',
            'PROVINCE': '省份',
            'ADDRESS_POSTCODE': '邮政编码',
            'REG_NUM': '注册号',
            'TATOLNUMBER': '总人数',
            'LAW_FIRM': '律师事务所',
            'ACCOUNTFIRM_NAME': '会计师事务所',
            'ORG_PROFILE': '公司简介',
            'TRADE_MARKETT': '交易市场类型',
            'TRADE_MARKET_CODE': '交易市场代码',
            'SECURITY_TYPEE': '证券类型(英文)',
            'SECURITY_TYPE_CODE': '证券类型代码',
            'EXPAND_NAME_ABBRN': '扩展名称缩写(英文)',
            'EXPAND_NAME_PINYIN': '扩展名称拼音',
            'EXPAND_NAME_ABBR': '扩展名称缩写',
            'HOST_BROKER': '主承销商',
            'TRANSFER_WAY': '转让方式',
            'ACTUAL_HOLDER': '实际控制人',
            'MARKETING_START_DATE': '上市日期',
            'MARKET_MAKER': '做市商',
            'TRADE_MARKET_TYPE': '交易市场类型',
            'CURRENCY': '货币',
            'BOARD_NAME_LEVEL': '板块名称层级'
        }
        
        # 只添加映射后的中文字段
        for source_field, target_field in field_mapping.items():
            if source_field in basic_info_dict:
                filtered_basic_info[target_field] = basic_info_dict[source_field]
        
        # 处理未映射的字段，添加到"其他信息"中
        other_info = {}
        for key, value in basic_info_dict.items():
            if key not in field_mapping:
                other_info[key] = value
        
        if other_info:
            filtered_basic_info['其他信息'] = other_info
        
        # 去除对量化分析无用的字段
        useless_fields = [
            '电话', '邮箱', '网站', '组织机构代码', '公司英文名称', '曾用名',
            'B股代码', 'B股名称', 'H股代码', 'H股名称', '股票代码', 'A股代码', '交易市场',
            '总裁', '法人代表', '董秘', '董事长', '证券事务代表', '独立董事',
            '传真', '注册地址', '邮政编码', '注册号', '货币',
            '律师事务所', '会计师事务所', '经营范围',
            '交易市场类型', '交易市场代码', '证券类型(英文)', '证券类型代码', '总人数',
            '扩展名称缩写(英文)', '扩展名称拼音', '扩展名称缩写', '主承销商', '转让方式',
            '做市商'
        ]
        
        # 移除无用字段
        for field in useless_fields:
            if field in filtered_basic_info:
                del filtered_basic_info[field]
        
        # 移除其他信息中的空值字段
        if '其他信息' in filtered_basic_info:
            filtered_basic_info['其他信息'] = {k: v for k, v in filtered_basic_info['其他信息'].items() if v is not None}
            if not filtered_basic_info['其他信息']:
                del filtered_basic_info['其他信息']
        
        # 确保所有必要的字段都存在
        required_fields = ['公司简称', '公司全称', '成立日期', '上市日期', '注册资本', '员工人数', '主营业务', '地址', '省份', '实际控制人', '板块名称层级', '证券代码', 'A股名称', '证券类型', 'EM2016行业分类', 'CSRC行业分类']
        for field in required_fields:
            if field not in filtered_basic_info:
                filtered_basic_info[field] = None
       
        company_info['basic_info'] = filtered_basic_info
    except Exception as e:
        print(f"获取基本信息时出错: {str(e)}")
        company_info['basic_info'] = {}
        # 尝试从研究报告中提取股票简称
        try:
            if company_info['research_reports']:
                # 从第一个研究报告中提取股票简称
                stock_short_name = company_info['research_reports'][0].get('股票简称', '')
                if stock_short_name:
                    company_info['basic_info']['公司简称'] = stock_short_name
                    print(f"从研究报告中提取股票简称: {stock_short_name}")
        except Exception as e2:
            print(f"从研究报告中提取股票简称时出错: {str(e2)}")
    
    # 2. 获取股票规模对比
    print("获取股票规模对比...")
    try:
        time.sleep(random.uniform(2, 4))
        # 使用带市场代码的完整股票代码（大写市场代码）
        full_code = f"{market.upper()}{code}"
        scale_df = ak.stock_zh_scale_comparison_em(symbol=full_code)
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
            research_reports = report_df.to_dict('records')
            company_info['research_reports'] = research_reports
            
            # 如果基本信息中没有公司简称，尝试从研究报告中提取
            if not company_info['basic_info'].get('公司简称') and research_reports:
                stock_short_name = research_reports[0].get('股票简称', '')
                if stock_short_name:
                    company_info['basic_info']['公司简称'] = stock_short_name
                    print(f"从研究报告中提取股票简称: {stock_short_name}")
            
            # 保存到CSV文件
            if research_reports:
                reports_path = os.path.join(stock_dir, f"{ticker}_research_reports.csv")
                # 为每条数据添加ticker
                for report in research_reports:
                    report['ticker'] = ticker
                # 保存到CSV
                fieldnames = ['ticker', '序号', '股票代码', '股票简称', '报告名称', '东财评级', '机构', '近一月个股研报数', '2025-盈利预测-收益', '2025-盈利预测-市盈率', '2026-盈利预测-收益', '2026-盈利预测-市盈率', '2027-盈利预测-收益', '2027-盈利预测-市盈率', '行业', '日期', '报告PDF链接']
                save_to_csv(reports_path, research_reports, fieldnames, '序号')
    except Exception as e:
        print(f"获取研究报告时出错: {str(e)}")
    

    
    # 7. 获取财务报表
    print("获取财务报表...")
    try:
        time.sleep(random.uniform(2, 4))
        stock_symbol_sina = f"{market}{code}"
        profit_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="利润表")
        if not profit_df.empty:
            # 保存所有利润表数据
            profit_data = profit_df.to_dict('records')
            company_info['financial_report']['profit'] = profit_data
            
            # 保存到CSV文件
            if profit_data:
                profit_path = os.path.join(stock_dir, f"{ticker}_financial_profit.csv")
                # 为每条数据添加ticker
                for item in profit_data:
                    item['ticker'] = ticker
                # 保存到CSV
                if profit_data:
                    fieldnames = ['ticker'] + list(profit_data[0].keys())
                    save_to_csv(profit_path, profit_data, fieldnames, '报告日')
        
        time.sleep(random.uniform(2, 4))
        balance_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="资产负债表")
        if not balance_df.empty:
            # 保存所有资产负债表数据
            balance_data = balance_df.to_dict('records')
            company_info['financial_report']['balance'] = balance_data
            
            # 保存到CSV文件
            if balance_data:
                balance_path = os.path.join(stock_dir, f"{ticker}_financial_balance.csv")
                # 为每条数据添加ticker
                for item in balance_data:
                    item['ticker'] = ticker
                # 保存到CSV
                if balance_data:
                    fieldnames = ['ticker'] + list(balance_data[0].keys())
                    save_to_csv(balance_path, balance_data, fieldnames, '报告日')
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
    
    # 保存公司基本信息到company_basic.json（覆盖保存）
    basic_info = {
        'ticker': company_info.get('ticker'),
        'code': company_info.get('code'),
        'market': company_info.get('market'),
        'data_sources': company_info.get('data_sources'),
        'timestamp': company_info.get('timestamp'),
        'basic_info': company_info.get('basic_info'),
        'business_scope': company_info.get('business_scope'),
        'financial_abstract': company_info.get('financial_abstract'),
        'scale_comparison': company_info.get('scale_comparison')
    }
    basic_info_path = os.path.join(stock_dir, f"{ticker}_company_basic.json")
    with open(basic_info_path, 'w', encoding='utf-8') as f:
        json.dump(basic_info, f, ensure_ascii=False, indent=2, cls=DateEncoder)
    print(f"公司基本信息已保存到: {basic_info_path}")
    
    # 保存北向资金数据到north_holdings.csv（如果有）
    if 'north_holdings' in company_info:
        north_holdings = company_info['north_holdings']
        if north_holdings:
            north_holdings_path = os.path.join(stock_dir, f"{ticker}_north_holdings.csv")
            # 为每条数据添加ticker
            for item in north_holdings:
                item['ticker'] = ticker
            # 保存到CSV
            if north_holdings:
                fieldnames = ['ticker'] + list(north_holdings[0].keys())
                save_to_csv(north_holdings_path, north_holdings, fieldnames, 'TRADE_DATE')
    
    return company_info


def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="收集股票公司信息")
    parser.add_argument('--ticker', help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    print("开始收集公司信息...")
    
    # 确定股票列表
    if args.ticker:
        # 处理指定的股票
        print(f"处理指定股票: {args.ticker}")
        get_stock_company_info(args.ticker)
    else:
        # 处理配置文件中的所有股票
        print("处理配置文件中的所有股票")
        for name, ticker in STOCK_TICKERS.items():
            get_stock_company_info(ticker)
    
    print("\n公司信息收集完成！")


if __name__ == "__main__":
    main()
