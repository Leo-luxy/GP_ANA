# strategy_optimization.py
# 功能：优化量化交易策略的参数，提高策略性能
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 遍历不同的策略参数组合（RSI买入/卖出阈值、布林带买入/卖出倍数）
# 3. 对每个参数组合执行策略回测，计算性能指标
# 4. 选择夏普比率最高的参数组合作为最佳参数
# 5. 绘制优化结果图表，展示参数组合的性能分布

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import DATA_DIR, STRATEGY_CONFIG, OPTIMIZATION_CONFIG

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class StrategyOptimizer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        # 使用配置文件中的初始资金
        self.initial_capital = STRATEGY_CONFIG['initial_capital']  # 初始资金
        # 资金管理参数
        self.position_size = 0.3  # 每次买入/卖出的资金比例（30%）
        self.max_positions = 3  # 最大持仓批次
        self.current_positions = 0  # 当前持仓批次
        # 交易成本参数
        self.trade_cost = 0.001  # 交易成本比例（0.1%）
        # 止损参数
        self.stop_loss_pct = 0.1  # 固定止损比例（10%）
    
    def load_data(self):
        """加载数据"""
        try:
            print(f"加载数据文件: {self.file_path}")
            self.data = pd.read_csv(self.file_path)
            
            # 转换日期格式
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
            
            # 获取股票代码
            if 'ticker' in self.data.columns:
                self.ticker = self.data['ticker'].iloc[0]
            else:
                # 从文件路径中提取股票代码
                import os
                file_name = os.path.basename(self.file_path)
                self.ticker = file_name.split('_')[0]
            
            return self.data
        except Exception as e:
            print(f"  加载数据失败: {e}")
            # 创建一个空的DataFrame作为默认值
            self.data = pd.DataFrame({
                'close': [100.0],
                'BB_lower': [95.0],
                'BB_upper': [105.0],
                'MA5': [100.0],
                'MA20': [100.0],
                'RSI': [50.0]
            })
            # 从文件路径中提取股票代码
            import os
            file_name = os.path.basename(self.file_path)
            self.ticker = file_name.split('_')[0]
            return self.data
    
    def calculate_signals(self, rsi_buy_threshold=None, rsi_sell_threshold=None, bb_buy_mult=None, bb_sell_mult=None):
        """计算交易信号"""
        try:
            # 使用配置文件中的默认参数
            if rsi_buy_threshold is None:
                rsi_buy_threshold = STRATEGY_CONFIG['rsi_buy_threshold']
            if rsi_sell_threshold is None:
                rsi_sell_threshold = STRATEGY_CONFIG['rsi_sell_threshold']
            if bb_buy_mult is None:
                bb_buy_mult = STRATEGY_CONFIG['bb_buy_mult']
            if bb_sell_mult is None:
                bb_sell_mult = STRATEGY_CONFIG['bb_sell_mult']
            
            # 1. 布林带信号
            if 'close' in self.data.columns and 'BB_lower' in self.data.columns:
                self.data['bb_buy_signal'] = (self.data['close'] < self.data['BB_lower'] * bb_buy_mult).astype(int)
            else:
                self.data['bb_buy_signal'] = 0
            
            if 'close' in self.data.columns and 'BB_upper' in self.data.columns:
                self.data['bb_sell_signal'] = (self.data['close'] > self.data['BB_upper'] * bb_sell_mult).astype(int)
            else:
                self.data['bb_sell_signal'] = 0
            
            # 2. MA交叉信号
            if 'MA5' in self.data.columns and 'MA20' in self.data.columns:
                self.data['MA5_above_MA20'] = (self.data['MA5'] > self.data['MA20']).astype(int)
                self.data['ma_crossover'] = self.data['MA5_above_MA20'].diff()
                self.data['ma_buy_signal'] = (self.data['ma_crossover'] == 1).astype(int)
                self.data['ma_sell_signal'] = (self.data['ma_crossover'] == -1).astype(int)
            else:
                self.data['MA5_above_MA20'] = 0
                self.data['ma_crossover'] = 0
                self.data['ma_buy_signal'] = 0
                self.data['ma_sell_signal'] = 0
            
            # 3. RSI信号
            if 'RSI' in self.data.columns:
                self.data['rsi_buy_signal'] = (self.data['RSI'] < rsi_buy_threshold).astype(int)
                self.data['rsi_sell_signal'] = (self.data['RSI'] > rsi_sell_threshold).astype(int)
            else:
                self.data['rsi_buy_signal'] = 0
                self.data['rsi_sell_signal'] = 0
            
            # 4. 综合信号
            # 买入信号：布林带突破下轨 OR (MA金叉 AND RSI超卖)
            self.data['buy_signal'] = ((self.data['bb_buy_signal'] == 1) | 
                                     ((self.data['ma_buy_signal'] == 1) & (self.data['rsi_buy_signal'] == 1))).astype(int)
            
            # 卖出信号：布林带突破上轨 OR (MA死叉 AND RSI超买)
            self.data['sell_signal'] = ((self.data['bb_sell_signal'] == 1) | 
                                      ((self.data['ma_sell_signal'] == 1) & (self.data['rsi_sell_signal'] == 1))).astype(int)
            
            return self.data
        except Exception as e:
            # 如果计算信号失败，返回默认信号
            print(f"  计算信号失败: {e}")
            # 设置默认信号
            self.data['bb_buy_signal'] = 0
            self.data['bb_sell_signal'] = 0
            self.data['MA5_above_MA20'] = 0
            self.data['ma_crossover'] = 0
            self.data['ma_buy_signal'] = 0
            self.data['ma_sell_signal'] = 0
            self.data['rsi_buy_signal'] = 0
            self.data['rsi_sell_signal'] = 0
            self.data['buy_signal'] = 0
            self.data['sell_signal'] = 0
            return self.data
    
    def backtest_strategy(self):
        """回测策略"""
        try:
            # 初始化
            position = 0
            cash = self.initial_capital
            portfolio_value = []
            # 资金管理相关变量
            current_positions = 0  # 当前持仓批次
            position_size = self.position_size  # 每次买入/卖出的资金比例
            max_positions = self.max_positions  # 最大持仓批次
            position_batches = []  # 记录每个批次的买入价格和数量
            trade_cost = self.trade_cost  # 交易成本比例
            stop_loss_pct = self.stop_loss_pct  # 止损比例
            
            # 遍历每一个交易日
            for i in range(len(self.data)):
                try:
                    close_price = self.data['close'].iloc[i]
                    buy_signal = self.data['buy_signal'].iloc[i]
                    sell_signal = self.data['sell_signal'].iloc[i]
                except Exception as e:
                    # 如果数据访问失败，跳过当前周期
                    continue
                
                # 检查止损条件
                if position > 0:
                    # 遍历所有持仓批次，检查止损
                    batches_to_remove = []
                    for j, (buy_price, shares, buy_date) in enumerate(position_batches):
                        # 1. 固定百分比止损
                        stop_loss_price = buy_price * (1 - stop_loss_pct)
                        # 2. 技术指标止损条件
                        technical_stop = False
                        # 3. 时间止损条件（持仓超过30天）
                        time_stop = False
                        try:
                            # 技术指标止损 - 只使用跌破MA20作为条件，不再叠加RSI条件
                            if 'MA20' in self.data.columns and close_price < self.data['MA20'].iloc[i]:
                                technical_stop = True
                            # 时间止损
                            if i - buy_date > 30:  # 持仓超过30个交易日
                                time_stop = True
                        except Exception as e:
                            pass
                        
                        # 触发止损条件
                        if close_price <= stop_loss_price or (technical_stop and close_price < buy_price * 0.95):
                            # 触发止损
                            sell_amount = shares * close_price
                            # 计算交易成本
                            cost = sell_amount * trade_cost
                            cash += sell_amount - cost
                            position -= shares
                            current_positions -= 1
                            batches_to_remove.append(j)
                    
                    # 移除触发止损的批次
                    for j in reversed(batches_to_remove):
                        position_batches.pop(j)
                
                # 执行买入信号（分批买入）
                if buy_signal == 1 and current_positions < max_positions:
                    # 计算本次买入的资金量
                    buy_amount = cash * position_size
                    if buy_amount > 0:
                        # 计算可购买的股票数量
                        shares_to_buy = int(buy_amount / close_price)
                        if shares_to_buy > 0:
                            # 计算交易成本
                            cost = buy_amount * trade_cost
                            if cash >= buy_amount + cost:
                                position += shares_to_buy
                                cash -= buy_amount + cost
                                current_positions += 1
                                # 记录批次信息（包含买入日期）
                                position_batches.append((close_price, shares_to_buy, i))
                
                # 执行卖出信号（分批卖出）
                elif sell_signal == 1 and current_positions > 0:
                    # 计算本次卖出的股票数量（按批次比例）
                    shares_to_sell = int(position * position_size)
                    if shares_to_sell > 0:
                        sell_amount = shares_to_sell * close_price
                        # 计算交易成本
                        cost = sell_amount * trade_cost
                        cash += sell_amount - cost
                        position -= shares_to_sell
                        
                        # 按批次比例减少持仓
                        remaining_shares = shares_to_sell
                        batches_to_remove = []
                        for j, (buy_price, shares, buy_date) in enumerate(position_batches):
                            if remaining_shares > 0:
                                if shares <= remaining_shares:
                                    # 卖出整个批次
                                    remaining_shares -= shares
                                    batches_to_remove.append(j)
                                    current_positions -= 1
                                else:
                                    # 卖出部分批次
                                    position_batches[j] = (buy_price, shares - remaining_shares, buy_date)
                                    remaining_shares = 0
                        
                        # 移除完全卖出的批次
                        for j in reversed(batches_to_remove):
                            position_batches.pop(j)
                
                # 计算当前portfolio价值
                current_value = cash + (position * close_price)
                portfolio_value.append(current_value)
            
            # 回测结束时，如果还有持仓，卖出所有持仓
            if position > 0:
                try:
                    final_price = self.data['close'].iloc[-1]
                    sell_amount = position * final_price
                    # 计算交易成本
                    cost = sell_amount * trade_cost
                    cash += sell_amount - cost
                    position = 0
                except Exception as e:
                    pass
            
            # 计算最终portfolio价值
            final_value = cash
            total_return = (final_value - self.initial_capital) / self.initial_capital * 100
            
            # 计算策略评估指标
            if len(portfolio_value) > 1:
                returns = np.diff(portfolio_value) / portfolio_value[:-1]
                num_trading_days = len(returns)
                annual_return = (portfolio_value[-1] / self.initial_capital) ** (252 / num_trading_days) - 1 if num_trading_days > 0 else 0
                volatility = np.std(returns) * np.sqrt(252) if num_trading_days > 0 else 0
                risk_free_rate = 0.03
                sharpe_ratio = (annual_return - risk_free_rate) / volatility if volatility > 0 else 0
                
                # 计算最大回撤
                portfolio_array = np.array(portfolio_value)
                peak = portfolio_array[0]
                max_drawdown = 0
                
                for value in portfolio_array:
                    if value > peak:
                        peak = value
                    drawdown = (peak - value) / peak
                    if drawdown > max_drawdown:
                        max_drawdown = drawdown
            else:
                annual_return = 0
                volatility = 0
                sharpe_ratio = 0
                max_drawdown = 0
            
            # 计算胜率
            try:
                buy_signals = self.data[self.data['buy_signal'] == 1]
                sell_signals = self.data[self.data['sell_signal'] == 1]
                
                winning_trades = 0
                total_trades = 0
                
                for i in range(len(buy_signals)):
                    buy_date = buy_signals.index[i]
                    # 找到下一个卖出信号
                    sell_candidates = sell_signals[sell_signals.index > buy_date]
                    if not sell_candidates.empty:
                        sell_date = sell_candidates.index[0]
                        buy_price = self.data['close'].iloc[buy_date]
                        sell_price = self.data['close'].iloc[sell_date]
                        if sell_price > buy_price:
                            winning_trades += 1
                        total_trades += 1
                
                win_rate = winning_trades / total_trades if total_trades > 0 else 0
            except Exception as e:
                win_rate = 0
                total_trades = 0
            
            return {
                'final_value': final_value,
                'total_return': total_return,
                'annual_return': annual_return,
                'volatility': volatility,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown': max_drawdown,
                'win_rate': win_rate,
                'total_trades': total_trades
            }
        except Exception as e:
            # 如果回测失败，返回默认值
            print(f"  回测失败: {e}")
            return {
                'final_value': self.initial_capital,
                'total_return': 0,
                'annual_return': 0,
                'volatility': 0,
                'sharpe_ratio': 0,
                'max_drawdown': 0,
                'win_rate': 0,
                'total_trades': 0
            }
    
    def optimize_parameters(self):
        """优化策略参数"""
        print("\n=== 策略参数优化 ===")
        
        # 加载数据
        self.load_data()
        
        # 使用配置文件中的参数搜索空间
        rsi_buy_thresholds = OPTIMIZATION_CONFIG['rsi_buy_thresholds']
        rsi_sell_thresholds = OPTIMIZATION_CONFIG['rsi_sell_thresholds']
        bb_buy_mults = OPTIMIZATION_CONFIG['bb_buy_mults']
        bb_sell_mults = OPTIMIZATION_CONFIG['bb_sell_mults']
        
        best_params = None
        best_score = -float('inf')
        all_results = []
        
        # 遍历所有参数组合
        for rsi_buy in rsi_buy_thresholds:
            for rsi_sell in rsi_sell_thresholds:
                for bb_buy in bb_buy_mults:
                    for bb_sell in bb_sell_mults:
                        try:
                            # 计算信号
                            self.calculate_signals(rsi_buy, rsi_sell, bb_buy, bb_sell)
                            # 回测策略
                            metrics = self.backtest_strategy()
                            
                            # 使用夏普比率作为评分指标
                            score = metrics['sharpe_ratio']
                            
                            # 记录结果
                            result = {
                                'rsi_buy_threshold': rsi_buy,
                                'rsi_sell_threshold': rsi_sell,
                                'bb_buy_mult': bb_buy,
                                'bb_sell_mult': bb_sell,
                                'score': score,
                                **metrics
                            }
                            all_results.append(result)
                            
                            # 更新最佳参数
                            if score > best_score:
                                best_score = score
                                best_params = result
                                print(f"找到更优参数组合: 夏普比率 = {score:.4f}")
                        except Exception as e:
                            print(f"  参数组合失败: {e}")
                            continue
        
        # 如果没有找到最佳参数，使用默认参数
        if best_params is None:
            print("  没有找到最佳参数，使用默认参数")
            best_params = {
                'rsi_buy_threshold': STRATEGY_CONFIG['rsi_buy_threshold'],
                'rsi_sell_threshold': STRATEGY_CONFIG['rsi_sell_threshold'],
                'bb_buy_mult': STRATEGY_CONFIG['bb_buy_mult'],
                'bb_sell_mult': STRATEGY_CONFIG['bb_sell_mult'],
                'score': 0,
                'total_return': 0,
                'max_drawdown': 0,
                'win_rate': 0
            }
        
        # 按夏普比率排序，获取前10个最佳参数组合
        if all_results:
            sorted_results = sorted(all_results, key=lambda x: x['score'], reverse=True)
            top_10_results = sorted_results[:10]
        else:
            top_10_results = [best_params]
        
        print("\n=== 优化完成 ===")
        print(f"最佳参数组合:")
        print(f"  RSI买入阈值: {best_params['rsi_buy_threshold']}")
        print(f"  RSI卖出阈值: {best_params['rsi_sell_threshold']}")
        print(f"  布林带买入倍数: {best_params['bb_buy_mult']}")
        print(f"  布林带卖出倍数: {best_params['bb_sell_mult']}")
        print(f"  夏普比率: {best_params['sharpe_ratio']:.4f}")
        print(f"  总收益率: {best_params['total_return']:.2f}%")
        print(f"  最大回撤: {best_params['max_drawdown'] * 100:.2f}%")
        print(f"  胜率: {best_params['win_rate'] * 100:.2f}%")
        
        print("\n前10个最佳参数组合:")
        for i, result in enumerate(top_10_results, 1):
            print(f"\n第{i}名参数组合:")
            print(f"  RSI买入阈值: {result['rsi_buy_threshold']}")
            print(f"  RSI卖出阈值: {result['rsi_sell_threshold']}")
            print(f"  布林带买入倍数: {result['bb_buy_mult']}")
            print(f"  布林带卖出倍数: {result['bb_sell_mult']}")
            print(f"  夏普比率: {result['sharpe_ratio']:.4f}")
            print(f"  总收益率: {result['total_return']:.2f}%")
            print(f"  最大回撤: {result['max_drawdown'] * 100:.2f}%")
            print(f"  胜率: {result['win_rate'] * 100:.2f}%")
        
        return best_params, all_results
    
    def plot_optimization_results(self, all_results):
        """绘制优化结果"""
        try:
            # 确保数据目录存在
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            if not os.path.exists(stock_dir):
                os.makedirs(stock_dir)
            
            # 转换结果为DataFrame
            results_df = pd.DataFrame(all_results)
            
            # 按夏普比率排序
            results_df = results_df.sort_values('score', ascending=False)
            
            # 绘制前10个最佳参数组合
            top_10 = results_df.head(10)
            
            plt.figure(figsize=(15, 10))
            
            # 绘制夏普比率与总收益率的关系
            plt.subplot(2, 1, 1)
            scatter = plt.scatter(results_df['total_return'], results_df['sharpe_ratio'], 
                                 c=results_df['max_drawdown'], cmap='RdYlGn_r', alpha=0.6)
            plt.colorbar(scatter, label='最大回撤')
            plt.scatter(top_10['total_return'], top_10['sharpe_ratio'], color='red', s=100, label='Top 10')
            plt.title('参数组合性能分布')
            plt.xlabel('总收益率 (%)')
            plt.ylabel('夏普比率')
            plt.legend()
            plt.grid(True)
            
            # 绘制最佳参数组合的详细指标
            plt.subplot(2, 1, 2)
            metrics = ['total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate']
            metrics_labels = ['总收益率 (%)', '夏普比率', '最大回撤 (%)', '胜率 (%)']
            
            values = [top_10.iloc[0]['total_return'],
                     top_10.iloc[0]['sharpe_ratio'],
                     top_10.iloc[0]['max_drawdown'] * 100,
                     top_10.iloc[0]['win_rate'] * 100]
            
            plt.bar(metrics_labels, values, color=['green', 'blue', 'red', 'purple'])
            plt.title('最佳参数组合性能指标')
            plt.ylabel('值')
            plt.grid(axis='y')
            
            # 在柱状图上添加数值
            for i, v in enumerate(values):
                plt.text(i, v + 0.01 * max(values), f'{v:.2f}', ha='center')
            
            plt.tight_layout()
            chart_path = os.path.join(stock_dir, f'{self.ticker}_optimization_results.png')
            plt.savefig(chart_path)
            print(f"优化结果图表已保存为: {chart_path}")
        except Exception as e:
            print(f"  绘制图表失败: {e}")
    
    def update_config(self, best_params):
        """将最佳参数更新到config.py文件"""
        try:
            # 提取最佳参数
            rsi_buy_threshold = best_params['rsi_buy_threshold']
            rsi_sell_threshold = best_params['rsi_sell_threshold']
            bb_buy_mult = best_params['bb_buy_mult']
            bb_sell_mult = best_params['bb_sell_mult']
            
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
            print(f"已将最佳参数写入config.py中的STRATEGY_CONFIG:")
            print(f"  RSI买入阈值: {rsi_buy_threshold}")
            print(f"  RSI卖出阈值: {rsi_sell_threshold}")
            print(f"  布林带买入倍数: {bb_buy_mult}")
            print(f"  布林带卖出倍数: {bb_sell_mult}")
            
        except Exception as e:
            print(f"更新config.py时出错: {str(e)}")
    
    def run_optimization(self):
        """运行完整的优化"""
        best_params, all_results = self.optimize_parameters()
        self.plot_optimization_results(all_results)
        # 更新config.py文件
        self.update_config(best_params)
        print("\n=== 策略优化完成 ===")
        return best_params, all_results

if __name__ == "__main__":
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 遍历所有股票代码进行策略优化
    for ticker_name, ticker in STOCK_TICKERS.items():
        print(f"\n=== 分析股票: {ticker} ({ticker_name}) ===")
        file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
        print(f"分析股票: {ticker}")
        
        # 运行策略优化
        optimizer = StrategyOptimizer(file_path)
        best_params, all_results = optimizer.run_optimization()
    
    print("\n=== 所有股票策略优化完成 ===")
