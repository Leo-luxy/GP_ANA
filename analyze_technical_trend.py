# analyze_technical_trend.py
# 功能：基于technical_trend_analysis.json文件，使用Ollama AI进行专门的技术趋势分析
# 实现原理：
# 1. 加载技术趋势分析JSON文件
# 2. 提取关键技术指标和趋势数据
# 3. 生成针对技术趋势的AI分析提示词
# 4. 将提示词发送给本地部署的Ollama AI
# 5. 接收AI分析结果并保存为markdown文件
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG, STRATEGY_PROMPTS

class TechnicalTrendLLMAnalyzer:
    def __init__(self, ticker, strategy='trend_following'):
        self.ticker = ticker
        self.strategy = strategy
        self.strategy_prompt_template = STRATEGY_PROMPTS.get(self.strategy, STRATEGY_PROMPTS['neutral'])
        self.technical_trend_data = {}
        self.stock_info = {
            'name': '',
            'industry': '',
            'pe': '',
            'pb': '',
            'market_cap': '',
            'main_business': ''
        }
        self.trading_records = []
        self.position = {
            'total_shares': 0,
            'total_cost': 0,
            'avg_cost': 0,
            'buy_operations': 0,
            'sell_operations': 0
        }
    
    def load_technical_trend_data(self):
        """加载技术趋势分析JSON文件"""
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        trend_file = os.path.join(stock_dir, f"{self.ticker}_technical_trend_analysis.json")
        
        if os.path.exists(trend_file):
            print(f"加载技术趋势分析文件: {trend_file}")
            with open(trend_file, 'r', encoding='utf-8') as f:
                self.technical_trend_data = json.load(f)
        else:
            print(f"技术趋势分析文件不存在: {trend_file}")
            return False
        
        return True
    
    def load_trading_records(self):
        """加载交易记录并计算持仓情况"""
        try:
            from trading_records import TRADING_RECORDS
            
            self.trading_records = TRADING_RECORDS.get(self.ticker, [])
            self.position = self.calculate_position()
            
            print(f"加载交易记录: 共 {len(self.trading_records)} 条记录")
            print(f"当前持仓: {self.position['total_shares']} 股, 平均成本: {self.position['avg_cost']:.2f} 元")
            
        except Exception as e:
            print(f"加载交易记录时出错: {str(e)}")
    
    def calculate_position(self):
        """计算当前持仓情况"""
        total_shares = 0
        total_cost = 0
        buy_operations = 0
        sell_operations = 0
        
        for operation in self.trading_records:
            if operation['type'] == 'buy':
                total_shares += operation['shares']
                total_cost += operation['price'] * operation['shares']
                buy_operations += 1
            elif operation['type'] == 'sell':
                total_shares -= operation['shares']
                total_cost -= operation['price'] * operation['shares']
                sell_operations += 1
        
        avg_cost = 0
        if total_shares > 0:
            avg_cost = total_cost / total_shares
        
        return {
            'total_shares': total_shares,
            'total_cost': total_cost,
            'avg_cost': avg_cost,
            'buy_operations': buy_operations,
            'sell_operations': sell_operations
        }
    
    def calculate_fifo_position(self):
        """按照先进先出逻辑计算最终剩余持仓"""
        # 用于存储买入批次的列表，每个批次包含价格、数量和日期
        buy_batches = []
        
        # 处理每笔交易
        for operation in self.trading_records:
            if operation['type'] == 'buy':
                # 添加买入批次
                buy_batches.append({
                    'date': operation['date'],
                    'price': operation['price'],
                    'shares': operation['shares']
                })
            elif operation['type'] == 'sell':
                # 卖出时按照先进先出原则
                shares_to_sell = operation['shares']
                while shares_to_sell > 0 and buy_batches:
                    # 取出最早的买入批次
                    earliest_batch = buy_batches[0]
                    if earliest_batch['shares'] > shares_to_sell:
                        # 卖出部分批次
                        earliest_batch['shares'] -= shares_to_sell
                        shares_to_sell = 0
                    else:
                        # 卖出整个批次
                        shares_to_sell -= earliest_batch['shares']
                        buy_batches.pop(0)
        
        # 计算剩余持仓
        remaining_shares = sum(batch['shares'] for batch in buy_batches)
        total_cost = sum(batch['price'] * batch['shares'] for batch in buy_batches)
        avg_cost = total_cost / remaining_shares if remaining_shares > 0 else 0
        
        return {
            'remaining_batches': buy_batches,
            'total_shares': remaining_shares,
            'total_cost': total_cost,
            'avg_cost': avg_cost
        }
    
    def get_stock_info(self):
        """从company_basic.json文件中获取股票基本信息"""
        try:
            # 构建固定的公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            info_file = os.path.join(stock_dir, f"{self.ticker}_company_basic.json")
            
            # 检查文件是否存在
            if not os.path.exists(info_file):
                print(f"公司信息文件不存在: {info_file}")
                return
            
            print(f"从文件加载公司基本信息: {info_file}")
            
            # 读取文件
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取公司基本信息
            if 'basic_info' in data:
                basic_info = data['basic_info']
                # 映射字段
                self.stock_info['name'] = basic_info.get('公司简称', '')
                self.stock_info['industry'] = basic_info.get('板块名称层级', '')
                self.stock_info['main_business'] = basic_info.get('主营业务', '')
            
            # 从CSV文件中读取估值信息
            valuation_file = os.path.join(stock_dir, f"{self.ticker}_valuation.csv")
            if os.path.exists(valuation_file):
                try:
                    import pandas as pd
                    df = pd.read_csv(valuation_file)
                    if not df.empty:
                        # 获取最新的估值数据
                        latest_valuation = df.iloc[0].to_dict()
                        # 尝试不同的字段名
                        self.stock_info['pe'] = latest_valuation.get('市盈率(TTM)', latest_valuation.get('pe_ttm', ''))
                        self.stock_info['pb'] = latest_valuation.get('市净率', latest_valuation.get('pb', ''))
                        self.stock_info['market_cap'] = latest_valuation.get('总市值', '')
                        print(f"成功从CSV文件加载估值信息: {valuation_file}")
                except Exception as e:
                    print(f"读取估值CSV文件时出错: {str(e)}")
            
            print("成功从文件加载公司基本信息")
            print(f"加载的基本信息: {self.stock_info}")
            
        except Exception as e:
            print(f"从文件获取股票基本信息时出错: {str(e)}")
    
    def generate_ai_prompt(self):
        """生成针对技术趋势的AI分析提示词"""
        if not self.technical_trend_data:
            return "技术趋势数据未加载"
        
        prompt = f"""你是一位专业的金融分析师，擅长股票技术分析和投资建议。请基于以下技术趋势分析数据和交易记录，{self.strategy_prompt_template}，提供详细的技术分析和操作建议：

=== 股票基本信息 ===
- 股票代码: {self.ticker}
- 股票名称: {self.stock_info.get('name', '未知')}
- 所属行业: {self.stock_info.get('industry', '未知')}
- 主营业务: {self.stock_info.get('main_business', '未知')}
- 市盈率: {self.stock_info.get('pe', '未知')}
- 市净率: {self.stock_info.get('pb', '未知')}
- 总市值: {self.stock_info.get('market_cap', '未知')}

=== 技术趋势分析数据 ===
"""
        
        # 添加技术指标数据
        if 'technical_indicators' in self.technical_trend_data:
            ti = self.technical_trend_data['technical_indicators']
            prompt += "### 技术指标最新值\n"
            for key, value in ti.items():
                prompt += f"- {key}: {value}\n"
        
        # 添加指标趋势
        if 'indicator_trends' in self.technical_trend_data:
            it = self.technical_trend_data['indicator_trends']
            prompt += "\n### 指标趋势分析\n"
            for key, value in it.items():
                prompt += f"- {key}: {value}\n"
        
        # 添加趋势信心度
        if 'trend_confidence' in self.technical_trend_data:
            tc = self.technical_trend_data['trend_confidence']
            prompt += "\n### 趋势信心度\n"
            for key, value in tc.items():
                prompt += f"- {key}: {value}\n"
        
        # 添加交易信号
        if 'trading_signal' in self.technical_trend_data:
            ts = self.technical_trend_data['trading_signal']
            prompt += "\n### 交易信号\n"
            prompt += f"- 操作: {ts.get('action', 'N/A')}\n"
            prompt += f"- 信心度: {ts.get('confidence', 'N/A')}\n"
            prompt += f"- 理由: {ts.get('reason', 'N/A')}\n"
        
        # 添加多周期趋势
        if 'multi_timeframe' in self.technical_trend_data:
            mt = self.technical_trend_data['multi_timeframe']
            prompt += "\n### 多周期趋势\n"
            prompt += f"- 周线趋势: {mt.get('weekly_trend', 'N/A')}\n"
            prompt += f"- 日线趋势: {mt.get('daily_trend', 'N/A')}\n"
            prompt += f"- 背离: {mt.get('divergence', 'N/A')}\n"
        
        # 添加一致性评分
        if 'consistency_score' in self.technical_trend_data:
            prompt += f"\n### 指标一致性评分\n"
            prompt += f"- {self.technical_trend_data['consistency_score']}\n"
        
        # 添加市场快照
        if 'market_snapshot' in self.technical_trend_data:
            prompt += f"\n### 市场快照\n"
            prompt += f"- {self.technical_trend_data['market_snapshot']}\n"
        
        # 添加交易记录和持仓情况
        if self.position['total_shares'] > 0:
            # 使用先进先出逻辑计算最终剩余持仓
            fifo_position = self.calculate_fifo_position()
            
            prompt += f"\n=== 交易记录与持仓情况 ===\n"
            prompt += f"- 当前持仓数量: {fifo_position['total_shares']} 股\n"
            prompt += f"- 平均持仓成本: {fifo_position['avg_cost']:.2f} 元\n"
            prompt += f"- 买入操作: {self.position['buy_operations']} 次\n"
            prompt += f"- 卖出操作: {self.position['sell_operations']} 次\n"
            
            # 添加最终剩余持仓记录（先进先出计算结果）
            if fifo_position['remaining_batches']:
                prompt += "\n最终剩余持仓（先进先出计算）:\n"
                for i, batch in enumerate(fifo_position['remaining_batches']):
                    prompt += f"- 批次{i+1}: {batch['shares']} 股 @ {batch['price']} 元 (日期: {batch['date']})\n"
                prompt += f"- 总计: {fifo_position['total_shares']} 股\n"
                prompt += f"- 平均成本: {fifo_position['avg_cost']:.2f} 元\n"
        
        # 添加分析要求
        prompt += """\n=== 分析要求 ===
【趋势定性】
- 主趋势方向：牛市/熊市/震荡
- 趋势强度：强/中/弱/无（基于ADX和均线排列）
- 多周期共振：周线与日线是否一致

【多空信号表】
| 类型 | 信号 | 指标依据（含具体数值） |
|------|------|----------------------|
| 看多 | (最多3个) | ... |
| 看空 | (最多3个) | ... |

【关键价位】
- 强支撑1：xx（来源：布林下轨/ATR通道/近期低点）
- 强支撑2：xx
- 强阻力1：xx（来源：MA20/布林中轨/近期高点）
- 强阻力2：xx

【风险与仓位管理】
- 波动风险：高/中/低（基于20日波动率及ATR%）
- 回撤风险：当前20日最大回撤XX%，处于历史（高/中/低）水平
- 资金流向：正向/负向/中性（基于Chaikin_MF / MFI / OBV）
- 持仓建议：若已有持仓，应（持有/减仓/加仓/止损），理由...；若无持仓，应（观望/轻仓试探/等突破）

【止损和止盈】
基于以上每笔交易的持仓成本、当前价格、ATR波动率及技术支撑阻力位，请分别给出：
1. **逐笔止损建议**：对每一笔买入记录，推荐一个止损价格，并说明理由。若某笔已浮盈，可建议移动止损。
2. **整体止盈策略**：若股价上涨，建议采用哪种止盈方式（如：目标价位止盈、移动ATR止盈、分批止盈），并给出具体参数（如：从最高点回撤2倍ATR止盈）。
3. **动态调整条件**：如果后续股价突破某个关键位置（如MA20或布林中轨），止损止盈应如何调整？请给出具体触发条件和调整后的数值。

【具体交易策略】
- 行动：买入 / 卖出 / 持有 / 观望
- 置信度：0-100%
- 若买入：建议价位区间____，仓位____%（占总资金）
- 若卖出：止损价____，或止盈目标____
- 若持有：关键观察条件（例如突破中轨且放量），及持仓的止损价____，或止盈目标____

【核心逻辑一句话】

请提供详细、专业的分析，基于数据和技术指标，考虑当前持仓情况，避免泛泛而谈。"""
        
        # 保存完整提示词到本地
        self.save_prompt_to_local(prompt)
        
        return prompt
    
    def save_prompt_to_local(self, prompt):
        """将完整提示词保存到本地文件"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳+_prompt
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_technical_trend_prompt_{timestamp}.txt"
        file_path = os.path.join(stock_dir, filename)
        
        # 保存提示词到文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(prompt)
        
        print(f"完整提示词已保存为: {file_path}")
        return file_path
    
    def get_ai_analysis(self, prompt):
        """获取本地Ollama AI分析结果"""
        try:
            import ollama
            
            # 使用配置文件中的AI模型配置
            model = AI_CONFIG['model']
            temperature = AI_CONFIG['temperature']
            max_tokens = AI_CONFIG['max_tokens']
            
            print(f"正在请求本地Ollama AI ({model})...")
            # 配置Ollama客户端使用localhost
            client = ollama.Client(host=AI_CONFIG['base_url'])
            
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的金融分析师，擅长股票技术分析和投资建议。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": temperature,  # 降低随机性，提高准确性
                    "num_predict": max_tokens  # 足够的响应长度
                }
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {str(e)}")
            # 返回默认分析结果
            return "无法获取AI分析，请检查Ollama服务是否正常运行。"
    
    def save_analysis_to_md(self, analysis_content):
        """将分析结果保存为markdown文件"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_technical_trend_llm_analysis_{timestamp}.md"
        file_path = os.path.join(stock_dir, filename)
        
        # 从技术趋势分析JSON文件中获取数据
        current_price = 0
        analysis_date = datetime.now().strftime('%Y-%m-%d')
        technical_indicators = {}
        
        if self.technical_trend_data:
            # 获取当前价格
            if 'technical_indicators' in self.technical_trend_data:
                ti = self.technical_trend_data['technical_indicators']
                current_price = ti.get('close', 0)
                # 构建技术指标字典
                technical_indicators = {
                    'MA5': round(ti.get('MA5', 0), 2),
                    'MA10': round(ti.get('MA10', 0), 2),
                    'MA20': round(ti.get('MA20', 0), 2),
                    'RSI': round(ti.get('RSI', 0), 2),
                    'DIF': round(ti.get('DIF', 0), 4),
                    'DEA': round(ti.get('DEA', 0), 4),
                    'KDJ_K': round(ti.get('K', 0), 2),
                    'KDJ_D': round(ti.get('D', 0), 2),
                    'KDJ_J': round(ti.get('J', 0), 2),
                    'ATR': round(ti.get('ATR', 0), 2),
                    'OBV': round(ti.get('OBV', 0), 2),
                    'ADX': round(ti.get('ADX', 0), 2)
                }
            # 获取分析日期
            if 'meta' in self.technical_trend_data:
                analysis_date = self.technical_trend_data['meta'].get('last_data_date', analysis_date)
        
        # 构建markdown内容
        md_content = f"""# {self.stock_info.get('name', self.ticker)} ({self.ticker}) 技术趋势LLM分析报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 股票基本信息
- 股票代码: {self.ticker}
- 股票名称: {self.stock_info.get('name', '未知')}
- 所属行业: {self.stock_info.get('industry', '未知')}
- 当前价格: {current_price:.2f} 元
- 分析基准日期: {analysis_date}

## 技术指标数据
"""
        
        for indicator, value in technical_indicators.items():
            md_content += f"- {indicator}: {value}\n"
        
        # 添加技术趋势分析摘要
        if self.technical_trend_data:
            md_content += "\n## 技术趋势分析摘要\n"
            if 'market_snapshot' in self.technical_trend_data:
                md_content += f"- {self.technical_trend_data['market_snapshot']}\n"
            if 'consistency_score' in self.technical_trend_data:
                md_content += f"- 指标一致性评分: {self.technical_trend_data['consistency_score']}\n"
            if 'trading_signal' in self.technical_trend_data:
                ts = self.technical_trend_data['trading_signal']
                md_content += f"- 交易信号: {ts.get('action', 'N/A')} (信心度: {ts.get('confidence', 'N/A')})\n"
        
        # 添加交易记录和持仓情况
        if self.position['total_shares'] > 0:
            # 使用先进先出逻辑计算最终剩余持仓
            fifo_position = self.calculate_fifo_position()
            
            md_content += "\n## 交易记录与持仓情况\n"
            md_content += f"- 当前持仓数量: {fifo_position['total_shares']} 股\n"
            md_content += f"- 平均持仓成本: {fifo_position['avg_cost']:.2f} 元\n"
            md_content += f"- 买入操作: {self.position['buy_operations']} 次\n"
            md_content += f"- 卖出操作: {self.position['sell_operations']} 次\n"
            
            # 添加最终剩余持仓记录（先进先出计算结果）
            if fifo_position['remaining_batches']:
                md_content += "\n### 最终剩余持仓（先进先出计算）\n"
                for i, batch in enumerate(fifo_position['remaining_batches']):
                    md_content += f"- 批次{i+1}: {batch['shares']} 股 @ {batch['price']} 元 (日期: {batch['date']})\n"
                md_content += f"- 总计: {fifo_position['total_shares']} 股\n"
                md_content += f"- 平均持仓成本: {fifo_position['avg_cost']:.2f} 元\n"
        
        # 添加AI分析结果
        md_content += "\n## AI技术趋势分析结果\n"
        md_content += analysis_content
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"技术趋势LLM分析报告已保存为: {file_path}")
        return file_path
    
    def run_analysis(self):
        """运行完整分析"""
        # 加载技术趋势分析数据
        if not self.load_technical_trend_data():
            print("无法加载技术趋势分析数据，分析终止")
            return
        
        # 获取股票基本信息
        self.get_stock_info()
        
        # 加载交易记录和计算持仓情况
        self.load_trading_records()
        
        # 生成AI提示词
        prompt = self.generate_ai_prompt()
        print("\n=== 生成的AI分析提示词 ===")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)  # 只显示前2000个字符
        print(f"\n提示词长度: {len(prompt)} 字符")
        
        # 获取AI分析结果
        ai_analysis = self.get_ai_analysis(prompt)
        
        print("\n=== AI分析结果 ===")
        print(ai_analysis)
        
        # 保存分析结果到markdown文件
        self.save_analysis_to_md(ai_analysis)
        
        # 提示用户如何使用
        print("\n=== 分析完成 ===")
        print("技术趋势LLM分析报告已保存为markdown文件，包含详细的技术分析和操作建议。")
        
        return ai_analysis

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="使用本地Ollama AI进行股票技术趋势分析")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    parser.add_argument('--strategy', choices=['trend_following', 'mean_reversion', 'swing', 'neutral'],
                        default='trend_following', help="交易策略视角（默认 trend_following）")
    args = parser.parse_args()

    ticker = args.ticker
    print(f"\n=====================================")
    print(f"分析股票: {ticker} | 策略视角: {args.strategy}")
    print("=====================================")

    analyzer = TechnicalTrendLLMAnalyzer(ticker, strategy=args.strategy)
    analyzer.run_analysis()
