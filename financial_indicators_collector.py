
# financial_indicators_collector.py
# 功能：获取股票的财务指标、成长指标、现金流指标等数据
# 实现原理：
# 1. 从config.py中获取股票列表
# 2. 对每只股票，使用akshare获取各种财务数据
# 3. 计算所需的财务指标
# 4. 将数据分类保存到对应股票的文件夹中

import akshare as ak
import pandas as pd
import json
import os
import time
import random
import sys
from datetime import date, datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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

def get_stock_financial_indicators(ticker):
    """获取单个股票的财务指标"""
    print(f"\n开始获取 {ticker} 的财务指标...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 初始化结果字典
    financial_indicators = {
        'ticker': ticker,
        'code': code,
        'market': market,
        'data_sources': ['akshare'],
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
        'cash_flow': {},
        'profit_indicators': {},
        'debt_indicators': {},
        'growth_indicators': {},
        'shareholder_info': {},
        'financial_analysis': {}
    }
    
    # 1. 获取现金流量表
    print("获取现金流量表...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        stock_symbol_sina = f"{market}{code}"
        cash_flow_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="现金流量表")
        if not cash_flow_df.empty:
            # 只保留最近12组数据
            cash_flow_data = cash_flow_df.to_dict('records')[:12]
            financial_indicators['cash_flow'] = cash_flow_data
    except Exception as e:
        print(f"获取现金流量表时出错: {str(e)}")
    
    # 2. 获取利润表并计算毛利率、净利率
    print("获取利润表...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        stock_symbol_sina = f"{market}{code}"
        profit_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="利润表")
        if not profit_df.empty:
            # 计算毛利率和净利率
            if '营业收入' in profit_df.columns and '营业成本' in profit_df.columns:
                # 获取最新一期数据
                latest_profit = profit_df.iloc[0]
                if pd.notna(latest_profit['营业收入']) and pd.notna(latest_profit['营业成本']):
                    revenue = latest_profit['营业收入']
                    cost = latest_profit['营业成本']
                    if revenue > 0:
                        gross_profit = (revenue - cost) / revenue * 100
                        financial_indicators['profit_indicators']['毛利率'] = round(gross_profit, 2)
                        # 保存计算依据的报告期
                        if '报告日' in latest_profit:
                            financial_indicators['profit_indicators']['毛利率报告期'] = latest_profit['报告日']
            
            if '营业收入' in profit_df.columns and '净利润' in profit_df.columns:
                # 获取最新一期数据
                latest_profit = profit_df.iloc[0]
                if pd.notna(latest_profit['营业收入']) and pd.notna(latest_profit['净利润']):
                    revenue = latest_profit['营业收入']
                    net_profit = latest_profit['净利润']
                    if revenue > 0:
                        net_profit_margin = net_profit / revenue * 100
                        financial_indicators['profit_indicators']['净利率'] = round(net_profit_margin, 2)
                        # 保存计算依据的报告期
                        if '报告日' in latest_profit:
                            financial_indicators['profit_indicators']['净利率报告期'] = latest_profit['报告日']
            
            # 只保留最近12组数据
            profit_data = profit_df.to_dict('records')[:12]
            financial_indicators['profit_indicators']['profit_table'] = profit_data
    except Exception as e:
        print(f"获取利润表时出错: {str(e)}")
    
    # 3. 获取资产负债表并计算资产负债率
    print("获取资产负债表...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        stock_symbol_sina = f"{market}{code}"
        balance_df = ak.stock_financial_report_sina(stock=stock_symbol_sina, symbol="资产负债表")
        if not balance_df.empty:
            # 计算资产负债率
            if '资产总计' in balance_df.columns and '负债合计' in balance_df.columns:
                # 获取最新一期数据
                latest_balance = balance_df.iloc[0]
                if pd.notna(latest_balance['资产总计']) and pd.notna(latest_balance['负债合计']):
                    total_assets = latest_balance['资产总计']
                    total_liabilities = latest_balance['负债合计']
                    if total_assets > 0:
                        debt_ratio = total_liabilities / total_assets * 100
                        financial_indicators['debt_indicators']['资产负债率'] = round(debt_ratio, 2)
                        # 保存计算依据的报告期
                        if '报告日' in latest_balance:
                            financial_indicators['debt_indicators']['资产负债率报告期'] = latest_balance['报告日']
            
            # 计算流动比率和速动比率
            if '流动资产合计' in balance_df.columns and '流动负债合计' in balance_df.columns:
                # 获取最新一期数据
                latest_balance = balance_df.iloc[0]
                if pd.notna(latest_balance['流动资产合计']) and pd.notna(latest_balance['流动负债合计']):
                    current_assets = latest_balance['流动资产合计']
                    current_liabilities = latest_balance['流动负债合计']
                    if current_liabilities > 0:
                        current_ratio = current_assets / current_liabilities
                        financial_indicators['debt_indicators']['流动比率'] = round(current_ratio, 2)
                        # 保存计算依据的报告期
                        if '报告日' in latest_balance:
                            financial_indicators['debt_indicators']['流动比率报告期'] = latest_balance['报告日']
            
            # 只保留最近12组数据
            balance_data = balance_df.to_dict('records')[:12]
            financial_indicators['debt_indicators']['balance_table'] = balance_data
    except Exception as e:
        print(f"获取资产负债表时出错: {str(e)}")
    
    # 4. 计算成长指标（从利润表计算）
    print("计算成长指标...")
    try:
        if 'profit_indicators' in financial_indicators and 'profit_table' in financial_indicators['profit_indicators']:
            profit_data = financial_indicators['profit_indicators']['profit_table']
            if len(profit_data) >= 2:
                # 检查时间维度一致性
                current_report_date = profit_data[0].get('报告日', '')
                previous_report_date = profit_data[1].get('报告日', '')
                
                # 提取月份
                current_month = None
                previous_month = None
                if current_report_date:
                    current_month = int(current_report_date[4:6])
                if previous_report_date:
                    previous_month = int(previous_report_date[4:6])
                
                # 确保使用相同时间维度的数据
                # 12月表示年度数据，3/6/9月表示季度数据
                if current_month == previous_month:
                    # 相同时间维度，直接计算
                    # 计算营收增长率
                    if '营业收入' in profit_data[0] and '营业收入' in profit_data[1]:
                        current_revenue = profit_data[0]['营业收入']
                        previous_revenue = profit_data[1]['营业收入']
                        if previous_revenue > 0:
                            revenue_growth = (current_revenue - previous_revenue) / previous_revenue * 100
                            financial_indicators['growth_indicators']['营收增长率'] = round(revenue_growth, 2)
                    
                    # 计算净利润增长率
                    if '净利润' in profit_data[0] and '净利润' in profit_data[1]:
                        current_profit = profit_data[0]['净利润']
                        previous_profit = profit_data[1]['净利润']
                        if previous_profit > 0:
                            profit_growth = (current_profit - previous_profit) / previous_profit * 100
                            financial_indicators['growth_indicators']['净利润增长率'] = round(profit_growth, 2)
                else:
                    # 时间维度不一致，寻找相同时间维度的数据
                    print(f"时间维度不一致: 当前 {current_report_date}, 上一期 {previous_report_date}")
                    # 寻找相同月份的数据
                    same_month_data = None
                    for i in range(1, len(profit_data)):
                        report_date = profit_data[i].get('报告日', '')
                        if report_date:
                            month = int(report_date[4:6])
                            if month == current_month:
                                same_month_data = profit_data[i]
                                break
                    
                    if same_month_data:
                        print(f"找到相同时间维度的数据: {same_month_data.get('报告日', '')}")
                        # 计算营收增长率
                        if '营业收入' in profit_data[0] and '营业收入' in same_month_data:
                            current_revenue = profit_data[0]['营业收入']
                            previous_revenue = same_month_data['营业收入']
                            if previous_revenue > 0:
                                revenue_growth = (current_revenue - previous_revenue) / previous_revenue * 100
                                financial_indicators['growth_indicators']['营收增长率'] = round(revenue_growth, 2)
                        
                        # 计算净利润增长率
                        if '净利润' in profit_data[0] and '净利润' in same_month_data:
                            current_profit = profit_data[0]['净利润']
                            previous_profit = same_month_data['净利润']
                            if previous_profit > 0:
                                profit_growth = (current_profit - previous_profit) / previous_profit * 100
                                financial_indicators['growth_indicators']['净利润增长率'] = round(profit_growth, 2)
                    else:
                        print("未找到相同时间维度的数据，无法计算增长率")
    except Exception as e:
        print(f"计算成长指标时出错: {str(e)}")
    
    # 5. 股东数数据已移至 shareholder_num_collector.py 中获取
    
    # 6. 获取财务分析指标
    print("获取财务分析指标...")
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        financial_analysis_df = ak.stock_financial_analysis_indicator(symbol=code)
        if not financial_analysis_df.empty:
            financial_indicators['financial_analysis'] = financial_analysis_df.to_dict('records')[0]
            print("成功获取财务分析指标")
        else:
            # 尝试使用stock_financial_abstract获取财务摘要
            print("尝试获取财务摘要...")
            financial_abstract_df = ak.stock_financial_abstract(symbol=code)
            if not financial_abstract_df.empty:
                # 保存所有财务摘要数据，而不仅仅是第一行
                financial_indicators['financial_analysis'] = financial_abstract_df.to_dict('records')
                print("成功获取财务摘要")
                print(f"获取到 {len(financial_abstract_df)} 条财务指标")
            else:
                print("财务分析指标和财务摘要数据均为空")
    except Exception as e:
        print(f"获取财务分析指标时出错: {str(e)}")
    
    # 直接保存新数据
    output_file = os.path.join(stock_dir, f"{ticker}_financial_indicators.json")
    
    # 保存数据
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(financial_indicators, f, ensure_ascii=False, indent=2, cls=DateEncoder)
    
    print(f"财务指标已保存到: {output_file}")
    return financial_indicators

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='收集股票财务指标')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
    args = parser.parse_args()
    
    print("开始收集财务指标...")
    
    # 确定股票列表
    if args.ticker:
        # 使用指定的股票
        print(f"处理指定股票: {args.ticker}")
        get_stock_financial_indicators(args.ticker)
    else:
        # 使用配置文件中的股票列表
        print("处理配置文件中的股票列表")
        for name, ticker in STOCK_TICKERS.items():
            get_stock_financial_indicators(ticker)
    
    print("\n财务指标收集完成！")

if __name__ == "__main__":
    main()
