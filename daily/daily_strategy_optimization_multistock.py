# daily_strategy_optimization_multistock.py
# 功能：为多只股票优化日线量化交易策略参数，找到一组通用参数
# 实现原理：
# 1. 遍历data目录下的所有股票（除了03032.HK）
# 2. 对每只股票运行参数优化
# 3. 收集所有股票的最佳参数
# 4. 分析这些参数，找出一组对大多数股票都有效的通用参数
# 5. 将通用参数更新到config.py中

import pandas as pd
import numpy as np
import os
import argparse
import sys
from datetime import datetime

# 添加父目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR, STRATEGY_CONFIG, OPTIMIZATION_CONFIG
from daily.strategy_optimization import StrategyOptimizer

class DailyMultiStockStrategyOptimizer:
    def __init__(self):
        self.stocks = []
        self.stock_results = {}
    
    def get_stock_list(self):
        """获取股票列表（除了03032.HK）"""
        print("获取股票列表...")
        data_dir = DATA_DIR
        stock_dirs = [d for d in os.listdir(data_dir) if os.path.isdir(os.path.join(data_dir, d))]
        # 排除03032.HK
        stock_dirs = [d for d in stock_dirs if d != '03032.HK']
        
        for stock in stock_dirs:
            # 优先使用indicators.csv文件
            daily_data_file = os.path.join(data_dir, stock, f"{stock}_indicators.csv")
            if not os.path.exists(daily_data_file):
                # 如果indicators.csv不存在，使用history.csv
                daily_data_file = os.path.join(data_dir, stock, f"{stock}_history.csv")
            
            if os.path.exists(daily_data_file):
                self.stocks.append(stock)
                print(f"  找到股票: {stock}")
            else:
                print(f"  跳过股票 {stock}: 缺少日线数据文件")
        
        print(f"\n共找到 {len(self.stocks)} 只股票")
        return self.stocks
    
    def optimize_all_stocks(self):
        """优化所有股票的参数"""
        print("\n=== 开始多股票参数优化 ===")
        
        for stock in self.stocks:
            print(f"\n优化股票: {stock}")
            # 优先使用indicators.csv文件
            file_path = os.path.join(DATA_DIR, stock, f"{stock}_indicators.csv")
            if not os.path.exists(file_path):
                # 如果indicators.csv不存在，使用history.csv
                file_path = os.path.join(DATA_DIR, stock, f"{stock}_history.csv")
            
            try:
                optimizer = StrategyOptimizer(file_path)
                # 先加载数据
                optimizer.load_data()
                # 然后优化参数
                best_params, all_results = optimizer.optimize_parameters()
                self.stock_results[stock] = {
                    'best_params': best_params,
                    'all_results': all_results
                }
                print(f"  股票 {stock} 优化完成")
            except Exception as e:
                print(f"  股票 {stock} 优化失败: {str(e)}")
                # 记录失败的股票
                self.stock_results[stock] = {
                    'best_params': None,
                    'error': str(e)
                }
        
        return self.stock_results
    
    def analyze_parameters(self):
        """分析所有股票的最佳参数，找出通用参数"""
        print("\n=== 分析参数分布 ===")
        
        # 收集所有股票的最佳参数
        params_list = []
        for stock, result in self.stock_results.items():
            best_params = result['best_params']
            if best_params is not None:
                params_list.append({
                    'stock': stock,
                    'rsi_buy_threshold': best_params['rsi_buy_threshold'],
                    'rsi_sell_threshold': best_params['rsi_sell_threshold'],
                    'bb_buy_mult': best_params['bb_buy_mult'],
                    'bb_sell_mult': best_params['bb_sell_mult'],
                    'sharpe_ratio': best_params['sharpe_ratio'],
                    'total_return': best_params['total_return'],
                    'max_drawdown': best_params['max_drawdown'],
                    'win_rate': best_params['win_rate']
                })
        
        if not params_list:
            print("没有成功优化的股票，使用默认参数")
            # 使用默认参数
            common_params = {
                'rsi_buy_threshold': 30,
                'rsi_sell_threshold': 70,
                'bb_buy_mult': 0.95,
                'bb_sell_mult': 1.05
            }
            return common_params, pd.DataFrame()
        
        # 创建DataFrame
        params_df = pd.DataFrame(params_list)
        print("\n各股票最佳参数:")
        print(params_df)
        
        # 计算参数统计
        print("\n参数统计:")
        print(params_df.describe())
        
        # 找出最常见的参数值
        print("\n参数众数:")
        print(params_df.mode().iloc[0])
        
        # 计算参数平均值（四舍五入到合理值）
        rsi_buy_mean = round(params_df['rsi_buy_threshold'].mean())
        rsi_sell_mean = round(params_df['rsi_sell_threshold'].mean())
        bb_buy_mean = round(params_df['bb_buy_mult'].mean(), 2)
        bb_sell_mean = round(params_df['bb_sell_mult'].mean(), 2)
        
        print("\n参数平均值:")
        print(f"  RSI买入阈值: {rsi_buy_mean}")
        print(f"  RSI卖出阈值: {rsi_sell_mean}")
        print(f"  布林带买入倍数: {bb_buy_mean}")
        print(f"  布林带卖出倍数: {bb_sell_mean}")
        
        # 选择通用参数（使用平均值）
        common_params = {
            'rsi_buy_threshold': rsi_buy_mean,
            'rsi_sell_threshold': rsi_sell_mean,
            'bb_buy_mult': bb_buy_mean,
            'bb_sell_mult': bb_sell_mean
        }
        
        return common_params, params_df
    
    def update_config(self, common_params):
        """将通用参数更新到config.py文件"""
        try:
            # 提取通用参数
            rsi_buy_threshold = common_params['rsi_buy_threshold']
            rsi_sell_threshold = common_params['rsi_sell_threshold']
            bb_buy_mult = common_params['bb_buy_mult']
            bb_sell_mult = common_params['bb_sell_mult']
            
            # 读取config.py文件
            with open('config.py', 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # 找到STRATEGY_CONFIG的位置并更新参数
            in_strategy_config = False
            new_lines = []
            
            for line in lines:
                if 'STRATEGY_CONFIG = {' in line:
                    in_strategy_config = True
                    new_lines.append(line)
                elif in_strategy_config and 'rsi_buy_threshold' in line:
                    new_lines.append(f"    'rsi_buy_threshold': {rsi_buy_threshold},  # RSI买入阈值\n")
                elif in_strategy_config and 'rsi_sell_threshold' in line:
                    new_lines.append(f"    'rsi_sell_threshold': {rsi_sell_threshold},  # RSI卖出阈值\n")
                elif in_strategy_config and 'bb_buy_mult' in line:
                    new_lines.append(f"    'bb_buy_mult': {bb_buy_mult},  # 布林带买入倍数\n")
                elif in_strategy_config and 'bb_sell_mult' in line:
                    new_lines.append(f"    'bb_sell_mult': {bb_sell_mult},  # 布林带卖出倍数\n")
                else:
                    new_lines.append(line)
                
                # 检查是否结束了STRATEGY_CONFIG
                if in_strategy_config and '}' in line and not line.strip().startswith('#'):
                    in_strategy_config = False
            
            # 写回config.py文件
            with open('config.py', 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            
            print("\n=== 配置文件更新完成 ===")
            print(f"已将通用参数写入config.py中的STRATEGY_CONFIG:")
            print(f"  RSI买入阈值: {rsi_buy_threshold}")
            print(f"  RSI卖出阈值: {rsi_sell_threshold}")
            print(f"  布林带买入倍数: {bb_buy_mult}")
            print(f"  布林带卖出倍数: {bb_sell_mult}")
            
        except Exception as e:
            print(f"更新config.py时出错: {str(e)}")
    
    def test_common_params(self, common_params):
        """使用通用参数测试所有股票"""
        print("\n=== 测试通用参数 ===")
        
        test_results = []
        
        for stock in self.stocks:
            print(f"\n测试股票: {stock}")
            # 优先使用indicators.csv文件
            file_path = os.path.join(DATA_DIR, stock, f"{stock}_indicators.csv")
            if not os.path.exists(file_path):
                # 如果indicators.csv不存在，使用history.csv
                file_path = os.path.join(DATA_DIR, stock, f"{stock}_history.csv")
            
            try:
                optimizer = StrategyOptimizer(file_path)
                optimizer.load_data()
                optimizer.calculate_signals(
                    rsi_buy_threshold=common_params['rsi_buy_threshold'],
                    rsi_sell_threshold=common_params['rsi_sell_threshold'],
                    bb_buy_mult=common_params['bb_buy_mult'],
                    bb_sell_mult=common_params['bb_sell_mult']
                )
                metrics = optimizer.backtest_strategy()
                
                test_results.append({
                    'stock': stock,
                    'sharpe_ratio': metrics['sharpe_ratio'],
                    'total_return': metrics['total_return'],
                    'max_drawdown': metrics['max_drawdown'],
                    'win_rate': metrics['win_rate'],
                    'total_trades': metrics['total_trades']
                })
                
                print(f"  夏普比率: {metrics['sharpe_ratio']:.4f}")
                print(f"  总收益率: {metrics['total_return']:.2f}%")
                print(f"  最大回撤: {metrics['max_drawdown'] * 100:.2f}%")
                print(f"  胜率: {metrics['win_rate'] * 100:.2f}%")
                print(f"  总交易次数: {metrics['total_trades']}")
            except Exception as e:
                print(f"  测试失败: {str(e)}")
                # 记录失败的测试
                test_results.append({
                    'stock': stock,
                    'sharpe_ratio': 0,
                    'total_return': 0,
                    'max_drawdown': 0,
                    'win_rate': 0,
                    'total_trades': 0,
                    'error': str(e)
                })
        
        # 分析测试结果
        if test_results:
            test_df = pd.DataFrame(test_results)
            print("\n通用参数测试结果:")
            print(test_df)
            
            print("\n测试结果统计:")
            print(test_df.describe())
            
            # 计算平均夏普比率
            avg_sharpe = test_df['sharpe_ratio'].mean()
            print(f"\n平均夏普比率: {avg_sharpe:.4f}")
            
            # 计算正收益率股票比例
            positive_return_stocks = len(test_df[test_df['total_return'] > 0])
            positive_return_ratio = positive_return_stocks / len(test_df) * 100
            print(f"正收益率股票比例: {positive_return_ratio:.2f}%")
        
        return test_results
    
    def run_optimization(self):
        """运行完整的多股票优化"""
        self.get_stock_list()
        if not self.stocks:
            print("没有找到可优化的股票")
            return
        
        self.optimize_all_stocks()
        if not self.stock_results:
            print("优化失败")
            return
        
        common_params, params_df = self.analyze_parameters()
        self.update_config(common_params)
        self.test_common_params(common_params)
        
        print("\n=== 多股票策略优化完成 ===")
        return common_params

if __name__ == "__main__":
    # 运行多股票策略优化
    optimizer = DailyMultiStockStrategyOptimizer()
    common_params = optimizer.run_optimization()
