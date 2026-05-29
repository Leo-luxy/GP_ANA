
# important_missing_data_collector.py
# 功能：抓取个股的重要缺失数据，包括除权除息数据、龙虎榜数据、高管持股和增减持数据、业绩预告和快报数据
# 实现原理：
# 1. 从config.py中获取股票列表
# 2. 对每只股票，使用akshare获取各种重要缺失数据
# 3. 进行错误处理，防止某个数据返回为空
# 4. 将获取的信息保存到该股票文件夹下的对应文件中

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

def get_stock_ex_dividend_data(ticker):
    """获取股票的除权除息数据"""
    print(f"获取 {ticker} 的除权除息数据...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    try:
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        # 获取所有股票的历史分红数据
        ex_dividend_df = ak.stock_history_dividend()
        if not ex_dividend_df.empty:
            # 筛选出指定股票的数据
            # 注意：这里需要根据实际的列名进行筛选
            # 假设列名为 '股票代码' 或 'code'
            if '代码' in ex_dividend_df.columns:
                # 注意：数据中的代码可能是不带市场后缀的
                stock_dividend_df = ex_dividend_df[ex_dividend_df['代码'] == code]
            elif '股票代码' in ex_dividend_df.columns:
                stock_dividend_df = ex_dividend_df[ex_dividend_df['股票代码'] == code]
            elif 'code' in ex_dividend_df.columns:
                stock_dividend_df = ex_dividend_df[ex_dividend_df['code'] == code]
            else:
                # 尝试其他可能的列名
                print(f"除权除息数据列名: {ex_dividend_df.columns.tolist()}")
                stock_dividend_df = pd.DataFrame()
            
            if not stock_dividend_df.empty:
                # 保存到CSV文件
                output_file = os.path.join(stock_dir, f"{ticker}_ex_dividend.csv")
                stock_dividend_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"除权除息数据已保存到: {output_file}")
                return stock_dividend_df
            else:
                print(f"未找到 {ticker} 的除权除息数据")
                return None
        else:
            print("除权除息数据为空")
            return None
    except Exception as e:
        print(f"获取除权除息数据时出错: {str(e)}")
        return None

def get_stock_b龙虎榜_data(ticker):
    """获取股票的龙虎榜数据"""
    print(f"获取 {ticker} 的龙虎榜数据...")
    
    # 注意：akshare 1.18.46 版本没有直接获取龙虎榜数据的函数
    # 这里我们可以尝试从其他数据源获取，或者暂时跳过
    print("龙虎榜数据暂不支持获取")
    return None

def get_stock_insider_trading_data(ticker):
    """获取股票的高管持股和增减持数据"""
    print(f"获取 {ticker} 的高管持股和增减持数据...")
    
    # 注意：akshare 1.18.46 版本没有直接获取高管持股和增减持数据的函数
    # 这里我们可以尝试从其他数据源获取，或者暂时跳过
    print("高管持股和增减持数据暂不支持获取")
    return None

def get_stock_业绩预告_data(ticker):
    """获取股票的业绩预告和快报数据"""
    print(f"获取 {ticker} 的业绩预告和快报数据...")
    
    # 解析股票代码
    code = ticker.split('.')[0]
    market = 'sh' if ticker.endswith('.SH') else 'sz'
    
    # 构建股票文件夹路径
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    try:
        # 获取东方财富的业绩预告数据
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        performance_forecast_df = ak.stock_profit_forecast_em(symbol="")
        if not performance_forecast_df.empty:
            # 筛选出指定股票的数据
            if '代码' in performance_forecast_df.columns:
                stock_forecast_df = performance_forecast_df[performance_forecast_df['代码'] == code]
            elif '股票代码' in performance_forecast_df.columns:
                stock_forecast_df = performance_forecast_df[performance_forecast_df['股票代码'] == code]
            elif 'code' in performance_forecast_df.columns:
                stock_forecast_df = performance_forecast_df[performance_forecast_df['code'] == code]
            else:
                print(f"业绩预告数据列名: {performance_forecast_df.columns.tolist()}")
                stock_forecast_df = pd.DataFrame()
            
            if not stock_forecast_df.empty:
                output_file = os.path.join(stock_dir, f"{ticker}_performance_forecast.csv")
                stock_forecast_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"东方财富业绩预告数据已保存到: {output_file}")
            else:
                print(f"未找到 {ticker} 的东方财富业绩预告数据")
        else:
            print("东方财富业绩预告数据为空")
        
        # 获取同花顺的财报预测数据
        time.sleep(random.uniform(2, 4))  # 随机间隔2-4秒
        try:
            ths_forecast_df = ak.stock_profit_forecast_ths(symbol=code)
            if not ths_forecast_df.empty:
                output_file = os.path.join(stock_dir, f"{ticker}_performance_forecast_ths.csv")
                ths_forecast_df.to_csv(output_file, index=False, encoding='utf-8-sig')
                print(f"同花顺财报预测数据已保存到: {output_file}")
            else:
                print(f"未找到 {ticker} 的同花顺财报预测数据")
        except Exception as e:
            print(f"获取同花顺财报预测数据时出错: {str(e)}")
        
        # 注意：akshare 1.18.46 版本没有直接获取业绩快报的函数
        print("业绩快报数据暂不支持获取")
        
        return True
    except Exception as e:
        print(f"获取业绩预告数据时出错: {str(e)}")
        return False

def get_stock_important_missing_data(ticker):
    """获取单个股票的重要缺失数据"""
    print(f"\n开始获取 {ticker} 的重要缺失数据...")
    
    # 获取除权除息数据
    get_stock_ex_dividend_data(ticker)
    
    # 获取龙虎榜数据
    get_stock_b龙虎榜_data(ticker)
    
    # 获取高管持股和增减持数据
    get_stock_insider_trading_data(ticker)
    
    # 获取业绩预告和快报数据
    get_stock_业绩预告_data(ticker)
    
    print(f"{ticker} 的重要缺失数据获取完成！")

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="收集股票的重要缺失数据")
    parser.add_argument('--ticker', type=str, help='指定股票代码，例如：300433.SZ')
    args = parser.parse_args()
    
    print("开始收集重要缺失数据...")
    
    # 确定股票列表
    if args.ticker:
        # 使用指定的股票
        print(f"处理指定股票: {args.ticker}")
        get_stock_important_missing_data(args.ticker)
    else:
        # 使用配置文件中的股票列表
        print("处理配置文件中的股票列表")
        for name, ticker in STOCK_TICKERS.items():
            get_stock_important_missing_data(ticker)
    
    print("\n重要缺失数据收集完成！")

if __name__ == "__main__":
    main()
