#!/usr/bin/env python3
# stock_market_data_collector.py
# 功能：专门获取股票的估值、资金流和融资融券数据
# 实现原理：
# 1. 从命令行参数或config.py中获取股票列表
# 2. 对每只股票，使用akshare获取估值、资金流和融资融券数据
# 3. 增量更新：如果本地已有数据，只获取新数据并追加
# 4. 进行错误处理，防止数据获取失败
# 5. 将数据保存为csv格式

import akshare as ak
import pandas as pd
import os
import time
import random
import sys
import argparse
from datetime import datetime, timedelta

# 导入配置
from config import DATA_DIR, STOCK_TICKERS


def get_stock_valuation_data(ticker):
    """获取单个股票的估值数据"""
    print(f"\n开始获取 {ticker} 的估值数据...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 构建输出文件路径
    output_file = os.path.join(stock_dir, f"{ticker}_valuation.csv")
    
    # 检查本地是否已有数据
    last_date = None
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file)
            if not existing_df.empty:
                # 尝试获取日期列
                date_columns = [col for col in existing_df.columns if 'date' in col.lower() or '日期' in col]
                if date_columns:
                    date_col = date_columns[0]
                    # 尝试解析日期
                    try:
                        existing_df[date_col] = pd.to_datetime(existing_df[date_col])
                        last_date = existing_df[date_col].max()
                        print(f"本地已有估值数据，最后日期: {last_date.strftime('%Y-%m-%d')}")
                    except Exception as e:
                        print(f"解析日期时出错: {str(e)}")
                        last_date = None
        except Exception as e:
            print(f"读取本地估值数据时出错: {str(e)}")
    
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        
        # 尝试使用stock_value_em获取估值指标
        try:
            valuation_df = ak.stock_value_em(symbol=code)
            if not valuation_df.empty:
                # 处理日期列
                date_columns = [col for col in valuation_df.columns if 'date' in col.lower() or '日期' in col]
                if date_columns:
                    date_col = date_columns[0]
                    try:
                        valuation_df[date_col] = pd.to_datetime(valuation_df[date_col])
                        
                        # 如果有本地数据，只保留新数据
                        if last_date:
                            new_data = valuation_df[valuation_df[date_col] > last_date]
                            if not new_data.empty:
                                # 追加到现有文件
                                new_data.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
                                print(f"估值数据已追加到: {output_file}")
                                print(f"共追加 {len(new_data)} 条数据")
                            else:
                                print("估值数据已是最新，无需更新")
                        else:
                            # 首次保存
                            valuation_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                            print(f"估值数据已保存到: {output_file}")
                            print(f"共获取 {len(valuation_df)} 条数据")
                    except Exception as e:
                        print(f"处理估值数据日期时出错: {str(e)}")
                        # 如果日期处理失败，直接覆盖保存
                        valuation_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                        print(f"估值数据已保存到: {output_file}")
                        print(f"共获取 {len(valuation_df)} 条数据")
                else:
                    # 没有日期列，直接覆盖保存
                    valuation_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"估值数据已保存到: {output_file}")
                    print(f"共获取 {len(valuation_df)} 条数据")
                return valuation_df
            else:
                print(f"未获取到 {ticker} 的估值数据")
                return None
        except Exception as e1:
            print(f"使用stock_value_em获取估值指标时出错: {str(e1)}")
            # 如果失败，尝试使用stock_a_pe
            try:
                pe_df = ak.stock_a_pe(symbol=code)
                if not pe_df.empty:
                    # 处理日期列
                    date_columns = [col for col in pe_df.columns if 'date' in col.lower() or '日期' in col]
                    if date_columns:
                        date_col = date_columns[0]
                        try:
                            pe_df[date_col] = pd.to_datetime(pe_df[date_col])
                            
                            # 如果有本地数据，只保留新数据
                            if last_date:
                                new_data = pe_df[pe_df[date_col] > last_date]
                                if not new_data.empty:
                                    # 追加到现有文件
                                    new_data.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
                                    print(f"估值数据已追加到: {output_file}")
                                    print(f"共追加 {len(new_data)} 条数据")
                                else:
                                    print("估值数据已是最新，无需更新")
                            else:
                                # 首次保存
                                pe_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                                print(f"估值数据已保存到: {output_file}")
                                print(f"共获取 {len(pe_df)} 条数据")
                        except Exception as e:
                            print(f"处理估值数据日期时出错: {str(e)}")
                            # 如果日期处理失败，直接覆盖保存
                            pe_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                            print(f"估值数据已保存到: {output_file}")
                            print(f"共获取 {len(pe_df)} 条数据")
                    else:
                        # 没有日期列，直接覆盖保存
                        pe_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                        print(f"估值数据已保存到: {output_file}")
                        print(f"共获取 {len(pe_df)} 条数据")
                    return pe_df
                else:
                    print(f"未获取到 {ticker} 的估值数据")
                    return None
            except Exception as e2:
                print(f"使用stock_a_pe获取估值指标时出错: {str(e2)}")
                return None
    except Exception as e:
        print(f"获取估值数据时出错: {str(e)}")
        return None


def get_stock_fund_flow_data(ticker):
    """获取单个股票的资金流数据"""
    print(f"\n开始获取 {ticker} 的资金流数据...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 构建输出文件路径
    output_file = os.path.join(stock_dir, f"{ticker}_fund_flow.csv")
    
    # 检查本地是否已有数据
    last_date = None
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file)
            if not existing_df.empty:
                # 尝试获取日期列
                date_columns = [col for col in existing_df.columns if 'date' in col.lower() or '日期' in col]
                if date_columns:
                    date_col = date_columns[0]
                    # 尝试解析日期
                    try:
                        existing_df[date_col] = pd.to_datetime(existing_df[date_col])
                        last_date = existing_df[date_col].max()
                        print(f"本地已有资金流数据，最后日期: {last_date.strftime('%Y-%m-%d')}")
                    except Exception as e:
                        print(f"解析日期时出错: {str(e)}")
                        last_date = None
        except Exception as e:
            print(f"读取本地资金流数据时出错: {str(e)}")
    
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        
        fund_flow_df = ak.stock_individual_fund_flow(stock=code, market=market)
        if not fund_flow_df.empty:
            # 处理日期列
            date_columns = [col for col in fund_flow_df.columns if 'date' in col.lower() or '日期' in col]
            if date_columns:
                date_col = date_columns[0]
                try:
                    fund_flow_df[date_col] = pd.to_datetime(fund_flow_df[date_col])
                    
                    # 如果有本地数据，只保留新数据
                    if last_date:
                        new_data = fund_flow_df[fund_flow_df[date_col] > last_date]
                        if not new_data.empty:
                            # 追加到现有文件
                            new_data.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
                            print(f"资金流数据已追加到: {output_file}")
                            print(f"共追加 {len(new_data)} 条数据")
                        else:
                            print("资金流数据已是最新，无需更新")
                    else:
                        # 首次保存
                        fund_flow_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                        print(f"资金流数据已保存到: {output_file}")
                        print(f"共获取 {len(fund_flow_df)} 条数据")
                except Exception as e:
                    print(f"处理资金流数据日期时出错: {str(e)}")
                    # 如果日期处理失败，直接覆盖保存
                    fund_flow_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"资金流数据已保存到: {output_file}")
                    print(f"共获取 {len(fund_flow_df)} 条数据")
            else:
                # 没有日期列，直接覆盖保存
                fund_flow_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"资金流数据已保存到: {output_file}")
                print(f"共获取 {len(fund_flow_df)} 条数据")
            return fund_flow_df
        else:
            print(f"未获取到 {ticker} 的资金流数据")
            return None
    except Exception as e:
        print(f"获取资金流数据时出错: {str(e)}")
        return None


def get_stock_margin_data(ticker):
    """获取单个股票的融资融券数据"""
    print(f"\n开始获取 {ticker} 的融资融券数据...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 构建输出文件路径
    output_file = os.path.join(stock_dir, f"{ticker}_margin_data.csv")
    
    # 初始化结果数据
    margin_data = []
    
    # 确定开始和结束日期
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)  # 默认最近30天
    
    # 检查本地是否已有数据
    if os.path.exists(output_file):
        try:
            existing_df = pd.read_csv(output_file)
            if not existing_df.empty:
                # 尝试获取日期列
                if 'date' in existing_df.columns:
                    # 尝试解析日期
                    try:
                        existing_df['date'] = pd.to_datetime(existing_df['date'], format='%Y%m%d')
                        last_date = existing_df['date'].max()
                        print(f"本地已有融资融券数据，最后日期: {last_date.strftime('%Y-%m-%d')}")
                        
                        # 如果最后日期已经是今天或昨天，跳过获取
                        if last_date.date() >= (end_date - timedelta(days=1)).date():
                            print("融资融券数据已是最新，无需更新")
                            return existing_df
                        
                        # 从最后日期的下一天开始获取
                        start_date = last_date + timedelta(days=1)
                    except Exception as e:
                        print(f"解析日期时出错: {str(e)}")
        except Exception as e:
            print(f"读取本地融资融券数据时出错: {str(e)}")
    
    # 转换日期格式
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    print(f"时间范围: {start_str} 到 {end_str}")
    
    # 遍历日期范围
    current_date = start_date
    while current_date <= end_date:
        # 检查是否为周末
        if current_date.weekday() >= 5:  # 0-4是工作日，5-6是周末
            date_str = current_date.strftime('%Y%m%d')
            print(f"跳过周末日期: {date_str}")
            # 增加一天
            current_date += timedelta(days=1)
            continue
        
        date_str = current_date.strftime('%Y%m%d')
        print(f"获取 {date_str} 的数据...")
        
        try:
            time.sleep(random.uniform(1, 3))  # 随机间隔1-3秒
            
            if market == 'sh':
                # 获取沪市融资融券数据
                margin_df = ak.stock_margin_detail_sse(date=date_str)
                # 筛选目标股票
                stock_data = margin_df[margin_df['标的证券代码'] == code]
            else:
                # 获取深市融资融券数据
                margin_df = ak.stock_margin_detail_szse(date=date_str)
                # 筛选目标股票
                stock_data = margin_df[margin_df['证券代码'] == code]
            
            if not stock_data.empty:
                # 添加日期列，使用copy()避免SettingWithCopyWarning
                stock_data = stock_data.copy()
                stock_data['date'] = date_str
                margin_data.append(stock_data)
                print(f"成功获取 {date_str} 的数据")
            else:
                print(f"{date_str} 无 {ticker} 的融资融券数据")
                
        except Exception as e:
            print(f"获取 {date_str} 数据时出错: {str(e)}")
        
        # 增加一天
        current_date += timedelta(days=1)
    
    # 合并数据
    if margin_data:
        result_df = pd.concat(margin_data, ignore_index=True)
        
        # 如果本地已有数据，追加新数据
        if os.path.exists(output_file):
            result_df.to_csv(output_file, mode='a', header=False, index=False, encoding='utf-8-sig')
            print(f"融资融券数据已追加到: {output_file}")
            print(f"共追加 {len(result_df)} 条数据")
        else:
            # 首次保存
            result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
            print(f"融资融券数据已保存到: {output_file}")
            print(f"共获取 {len(result_df)} 条数据")
        return result_df
    else:
        print(f"未获取到 {ticker} 的融资融券数据")
        return None


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='收集股票市场数据')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
    args = parser.parse_args()
    
    print("开始收集估值、资金流和融资融券数据...")
    
    # 确定股票列表
    if args.ticker:
        # 使用指定的股票
        stock_tickers = {args.ticker: args.ticker}
        print(f"处理指定股票: {args.ticker}")
    else:
        # 使用配置文件中的股票列表
        # 或者使用自定义的股票列表
        stock_tickers = STOCK_TICKERS
        print("处理配置文件中的股票列表")
    
    # 遍历所有股票
    for name, ticker in stock_tickers.items():
        print(f"\n=== 处理股票: {name} ({ticker}) ===")
        get_stock_valuation_data(ticker)
        get_stock_fund_flow_data(ticker)
        get_stock_margin_data(ticker)
    
    print("\n估值、资金流和融资融券数据收集完成！")


if __name__ == "__main__":
    main()
