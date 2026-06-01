
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


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='收集股票估值和资金流数据')
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
    args = parser.parse_args()
    
    print("开始收集估值和资金流数据...")
    
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
    
    print("\n估值和资金流数据收集完成！")


if __name__ == "__main__":
    main()
