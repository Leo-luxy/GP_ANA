# weekly_stock_ai_local_analyzer.py
# 功能：将周线股票分析提示词发送给本地部署的Ollama AI，并将分析结果保存为markdown文件
# 实现原理：
# 1. 加载股票周线历史数据
# 2. 计算支撑位和阻力位
# 3. 获取股票基本信息
# 4. 生成AI分析提示词，包含股票基本信息、支撑位、阻力位、持仓情况和交易记录
# 5. 将提示词发送给本地部署的Ollama AI
# 6. 接收AI分析结果并保存为markdown文件
# 7. 绘制支撑位和阻力位图表
# 8. 支持从config.py中读取AI模型配置、持仓情况和交易记录
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import requests
import time
import os
from config import DATA_DIR, AI_CONFIG, TRADING_RECORDS

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class WeeklyStockAILocalAnalyzer:
    def __init__(self, file_path, model="qwen3:30b"):
        self.file_path = file_path
        self.model = model
        self.data = None
        self.ticker = None
        self.support_levels = []
        self.resistance_levels = []
        self.position = {}
        self.recent_operations = []
    
    def load_data(self):
        """加载周线数据"""
        print(f"加载周线数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'week_start' in self.data.columns:
            self.data['week_start'] = pd.to_datetime(self.data['week_start'])
            # 添加date列作为week_start的别名，保持兼容性
            self.data['date'] = self.data['week_start']
        elif 'date' in self.data.columns:
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
    
    def calculate_support_resistance(self):
        """计算支撑位和阻力位"""
        # 使用简单的方法计算支撑位和阻力位
        # 1. 使用近期最低价作为支撑位
        # 2. 使用近期最高价作为阻力位
        # 3. 使用移动平均线作为动态支撑/阻力
        
        # 获取最近12周的数据
        recent_data = self.data.tail(12)
        
        # 计算支撑位
        # 最低价格
        support_low = recent_data['low'].min()
        self.support_levels.append({
            'type': '最低价格',
            'value': round(support_low, 2),
            'date': recent_data[recent_data['low'] == support_low]['date'].iloc[0].strftime('%Y-%m-%d')
        })
        
        # 50周均线作为支撑
        if 'MA50' in recent_data.columns:
            ma50_support = recent_data['MA50'].iloc[-1]
            self.support_levels.append({
                'type': 'MA50支撑',
                'value': round(ma50_support, 2),
                'date': recent_data['date'].iloc[-1].strftime('%Y-%m-%d')
            })
        
        # 计算阻力位
        # 最高价格
        resistance_high = recent_data['high'].max()
        self.resistance_levels.append({
            'type': '最高价格',
            'value': round(resistance_high, 2),
            'date': recent_data[recent_data['high'] == resistance_high]['date'].iloc[0].strftime('%Y-%m-%d')
        })
        
        # 50周均线作为阻力
        if 'MA50' in recent_data.columns:
            ma50_resistance = recent_data['MA50'].iloc[-1]
            self.resistance_levels.append({
                'type': 'MA50阻力',
                'value': round(ma50_resistance, 2),
                'date': recent_data['date'].iloc[-1].strftime('%Y-%m-%d')
            })
        
        # 布林带上下轨
        if 'BB_upper' in recent_data.columns and 'BB_lower' in recent_data.columns:
            bb_upper = recent_data['BB_upper'].iloc[-1]
            bb_lower = recent_data['BB_lower'].iloc[-1]
            self.resistance_levels.append({
                'type': '布林带上轨',
                'value': round(bb_upper, 2),
                'date': recent_data['date'].iloc[-1].strftime('%Y-%m-%d')
            })
            self.support_levels.append({
                'type': '布林带下轨',
                'value': round(bb_lower, 2),
                'date': recent_data['date'].iloc[-1].strftime('%Y-%m-%d')
            })
    
    def set_position(self, shares, average_price, purchase_date):
        """设置持仓情况"""
        self.position = {
            'shares': shares,
            'average_price': average_price,
            'purchase_date': purchase_date,
            'current_price': self.data['close'].iloc[-1],
            'unrealized_pnl': round((self.data['close'].iloc[-1] - average_price) * shares, 2),
            'unrealized_pnl_percent': round((self.data['close'].iloc[-1] - average_price) / average_price * 100, 2)
        }
    
    def add_operation(self, date, type, price, shares):
        """添加操作记录"""
        operation = {
            'date': date,
            'type': type,  # 'buy' 或 'sell'
            'price': price,
            'shares': shares,
            'amount': round(price * shares, 2)
        }
        self.recent_operations.append(operation)
    
    def calculate_position_from_trading_records(self, trading_records):
        """从交易记录计算持仓情况"""
        shares = 0
        total_cost = 0
        purchase_date = None
        
        # 按日期排序交易记录
        sorted_records = sorted(trading_records, key=lambda x: x['date'])
        
        for record in sorted_records:
            if record['type'] == 'buy':
                shares += record['shares']
                total_cost += record['price'] * record['shares']
                # 更新购买日期为最后一次买入日期
                purchase_date = record['date']
            elif record['type'] == 'sell':
                shares -= record['shares']
                # 卖出时不更新总成本，因为平均成本是基于买入计算的
        
        # 计算平均成本
        if shares > 0:
            average_price = total_cost / shares
        else:
            average_price = 0
        
        return {
            'shares': shares,
            'average_price': round(average_price, 3),
            'purchase_date': purchase_date
        }
    
    def get_stock_info(self):
        """获取股票基本信息"""
        import akshare as ak
        
        stock_info = {
            'name': '',
            'industry': '',
            'pe': '',
            'pb': '',
            'market_cap': '',
            'total_assets': '',
            'main_business': ''
        }
        
        try:
            # 处理股票代码格式
            code = self.ticker
            if '.SS' in code:
                code = code.replace('.SS', '')
            elif '.SZ' in code:
                code = code.replace('.SZ', '')
            
            # 使用akshare获取股票基本信息
            stock_zh_a_spot_df = ak.stock_zh_a_spot_em()
            stock_data = stock_zh_a_spot_df[stock_zh_a_spot_df['代码'] == code]
            
            if not stock_data.empty:
                stock_info['name'] = stock_data['名称'].iloc[0]
                
            # 尝试获取更多基本信息
            try:
                stock_zh_a_basic_df = ak.stock_zh_a_basic()
                basic_data = stock_zh_a_basic_df[stock_zh_a_basic_df['代码'] == code]
                if not basic_data.empty:
                    stock_info['industry'] = basic_data['所属行业'].iloc[0]
            except Exception as e:
                print(f"获取行业信息时出错: {str(e)}")
                
        except Exception as e:
            print(f"获取股票基本信息时出错: {str(e)}")
        
        return stock_info
    
    def get_company_details(self):
        """从stock_company_info_v2生成的文件中获取公司详细信息"""
        company_details = {
            'full_name': '',
            'business_scope': '',
            'financial_report': {},
            'data_sources': []
        }
        
        try:
            # 构建公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            
            # 查找公司信息文件
            import glob
            info_files = glob.glob(os.path.join(stock_dir, f"{self.ticker}_*_company_info_v2.json"))
            
            if info_files:
                # 使用最新的文件
                info_files.sort(key=os.path.getmtime, reverse=True)
                info_file = info_files[0]
                
                print(f"加载公司详细信息文件: {info_file}")
                
                # 读取文件
                with open(info_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # 提取公司信息
                if 'company_info' in data:
                    company_info = data['company_info']
                    company_details['full_name'] = company_info.get('full_name', '')
                    company_details['business_scope'] = company_info.get('business_scope', '')
                    company_details['data_sources'] = company_info.get('data_sources', [])
                
                # 提取财务报告
                if 'financial_report' in data:
                    company_details['financial_report'] = data['financial_report']
                
                print("成功加载公司详细信息")
            else:
                print("未找到公司详细信息文件，使用默认值")
                
        except Exception as e:
            print(f"获取公司详细信息时出错: {str(e)}")
        
        return company_details
    
    def get_stock_summary(self):
        """获取股票综合信息"""
        # 获取最新数据
        latest = self.data.iloc[-1]
        
        # 获取股票基本信息
        stock_info = self.get_stock_info()
        
        # 获取公司详细信息
        company_details = self.get_company_details()
        
        summary = {
            'ticker': self.ticker,
            'name': stock_info['name'],
            'industry': stock_info['industry'],
            'current_price': round(latest['close'], 2),
            'date': latest['date'].strftime('%Y-%m-%d'),
            'support_levels': self.support_levels,
            'resistance_levels': self.resistance_levels,
            'position': self.position,
            'recent_operations': self.recent_operations,
            'company_details': company_details,
            'technical_indicators': {
                'MA5': round(latest.get('MA5', 0), 2),
                'MA10': round(latest.get('MA10', 0), 2),
                'MA20': round(latest.get('MA20', 0), 2),
                'RSI': round(latest.get('RSI', 0), 2),
                'MACD': round(latest.get('MACD', 0), 4),
                'MACD_signal': round(latest.get('MACD_signal', 0), 4),
                'KDJ_K': round(latest.get('K', 0), 2),
                'KDJ_D': round(latest.get('D', 0), 2),
                'KDJ_J': round(latest.get('J', 0), 2),
                'ATR': round(latest.get('ATR', 0), 2)
            }
        }
        
        return summary
    
    def generate_ai_prompt(self):
        """生成AI分析提示词，适合复制到网页AI服务中"""
        summary = self.get_stock_summary()
        company_details = summary.get('company_details', {})
        
        prompt = f"""你是一位专业的金融分析师，擅长股票技术分析和投资建议。请基于以下周线股票数据，提供详细的分析和操作建议：

=== 股票基本信息 ===
股票代码: {summary['ticker']}
股票名称: {summary['name']}
所属行业: {summary['industry']}
当前价格: {summary['current_price']} 元
分析日期: {summary['date']}

=== 公司详细信息 ===
"""
        
        # 添加公司详细信息
        if company_details.get('full_name'):
            prompt += f"- 公司全称: {company_details['full_name']}\n"
        if company_details.get('business_scope'):
            prompt += f"- 经营范围: {company_details['business_scope'][:150]}...\n"
        if company_details.get('data_sources'):
            prompt += f"- 数据来源: {', '.join(company_details['data_sources'])}\n"
        
        # 添加财报信息
        financial_report = company_details.get('financial_report', {})
        if financial_report:
            prompt += "\n=== 财务报表信息 ===\n"
            if financial_report.get('latest_quarter'):
                prompt += f"- 最新财报期: {financial_report['latest_quarter']}\n"
            if financial_report.get('revenue'):
                prompt += f"- 营业总收入: {financial_report['revenue']} 万元\n"
            if financial_report.get('net_profit'):
                prompt += f"- 净利润: {financial_report['net_profit']} 万元\n"
            if financial_report.get('eps'):
                prompt += f"- 基本每股收益: {financial_report['eps']}\n"
            if financial_report.get('roe'):
                prompt += f"- 净资产收益率: {financial_report['roe']}%\n"
            if financial_report.get('pe'):
                prompt += f"- 市盈率: {financial_report['pe']}\n"
            if financial_report.get('pb'):
                prompt += f"- 市净率: {financial_report['pb']}\n"
        
        prompt += "\n=== 支撑位分析 ===\n"
        for support in summary['support_levels']:
            prompt += f"- {support['type']}: {support['value']} 元 (形成日期: {support['date']})\n"
        
        prompt += "\n=== 阻力位分析 ===\n"
        for resistance in summary['resistance_levels']:
            prompt += f"- {resistance['type']}: {resistance['value']} 元 (形成日期: {resistance['date']})\n"
        
        prompt += "\n=== 持仓情况 ===\n"
        if summary['position']:
            prompt += f"- 持仓数量: {summary['position']['shares']} 股\n"
            prompt += f"- 平均成本: {summary['position']['average_price']} 元\n"
            prompt += f"- 购买日期: {summary['position']['purchase_date']}\n"
            prompt += f"- 浮动盈亏: {summary['position']['unrealized_pnl']} 元 ({summary['position']['unrealized_pnl_percent']}%)\n"
        else:
            prompt += "- 暂无持仓\n"
        
        prompt += "\n=== 近期操作记录 ===\n"
        if summary['recent_operations']:
            for op in summary['recent_operations']:
                prompt += f"- {op['date']}: {op['type']} {op['shares']} 股 @ {op['price']} 元\n"
        else:
            prompt += "- 暂无近期操作\n"
        
        prompt += "\n=== 技术指标数据（周线） ===\n"
        for indicator, value in summary['technical_indicators'].items():
            prompt += f"- {indicator}: {value}\n"
        
        prompt += """\n=== 分析要求 ===\n请提供以下内容：\n1. 股票当前技术面分析（周线趋势、动量、量能等）\n2. 支撑位和阻力位的有效性分析\n3. 针对当前持仓的具体操作建议\n4. 短期（1-4周）和中期（1-3个月）市场展望\n5. 具体的买入/卖出点位建议和止损止盈设置\n6. 风险评估和资金管理建议\n7. 结合公司基本信息和行业情况的分析\n8. 基于财报数据的财务状况分析\n9. 购买记录分析：评估过去的购买行为是否合理，包括购买时机、价格和数量的合理性\n10. 购买策略优化建议：基于周线数据和当前市场情况，提供更优化的购买策略，包括时机选择、价格区间和仓位管理\n\n请提供详细、专业的分析，基于周线数据和技术指标，避免泛泛而谈。"""
        
        return prompt
    
    def get_ai_analysis(self, prompt):
        """获取AI分析结果，优先使用外部API，否则使用本地Ollama"""
        # 检查是否启用了外部API
        if AI_CONFIG.get('external_api', {}).get('enabled', False):
            return self.get_external_ai_analysis(prompt)
        else:
            return self.get_local_ai_analysis(prompt)
    
    def get_local_ai_analysis(self, prompt):
        """获取本地Ollama AI分析结果"""
        import ollama
        
        try:
            # 使用配置文件中的AI模型配置
            model = AI_CONFIG['model']
            temperature = AI_CONFIG['temperature']
            max_tokens = AI_CONFIG['max_tokens']
            
            print(f"正在请求本地Ollama AI ({model})...")
            # 配置Ollama客户端使用localhost
            client = ollama.Client(host=AI_CONFIG.get('base_url', 'http://localhost:11434'))
            
            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的金融分析师，擅长股票技术分析和投资建议。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": temperature,  # 降低随机性，提高准确性
                    "max_tokens": max_tokens  # 足够的响应长度
                }
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {str(e)}")
            # 返回默认分析结果
            return "无法获取AI分析，请检查Ollama服务是否正常运行。"
    
    def get_external_ai_analysis(self, prompt):
        """获取外部大模型API分析结果"""
        try:
            import requests
            
            # 获取外部API配置
            external_api = AI_CONFIG['external_api']
            api_key = external_api['api_key']
            api_url = external_api['api_url']
            model = external_api['model']
            
            print(f"正在请求外部大模型API ({model})...")
            
            # 构建请求参数
            headers = {
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            }
            
            data = {
                'model': model,
                'messages': [
                    {"role": "system", "content": "你是一位专业的金融分析师，擅长股票技术分析和投资建议。"},
                    {"role": "user", "content": prompt}
                ],
                'temperature': AI_CONFIG.get('temperature', 0.3),
                'max_tokens': AI_CONFIG.get('max_tokens', 4000)
            }
            
            # 发送请求
            response = requests.post(api_url, headers=headers, json=data, timeout=60)
            response.raise_for_status()  # 检查响应状态
            
            # 解析响应
            result = response.json()
            return result['choices'][0]['message']['content']
        except Exception as e:
            print(f"调用外部大模型API时出错: {str(e)}")
            # 回退到本地Ollama
            print("回退到本地Ollama AI...")
            return self.get_local_ai_analysis(prompt)
    
    def save_analysis_to_md(self, analysis_content):
        """将分析结果保存为markdown文件"""
        # 获取股票综合信息
        summary = self.get_stock_summary()
        
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳+weekly
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.ticker}_{timestamp}_weekly.md"
        file_path = os.path.join(stock_dir, filename)
        
        # 构建markdown内容
        md_content = f"""# {summary['name']} ({self.ticker}) 周线股票分析报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 股票基本信息
- 股票代码: {self.ticker}
- 股票名称: {summary['name']}
- 所属行业: {summary['industry']}
- 当前价格: {self.data['close'].iloc[-1]:.2f} 元
- 分析基准日期: {self.data['date'].iloc[-1].strftime('%Y-%m-%d')}

## 支撑位分析
"""
        
        for support in self.support_levels:
            md_content += f"- {support['type']}: {support['value']} 元 (形成日期: {support['date']})\n"
        
        md_content += "\n## 阻力位分析\n"
        for resistance in self.resistance_levels:
            md_content += f"- {resistance['type']}: {resistance['value']} 元 (形成日期: {resistance['date']})\n"
        
        md_content += "\n## 持仓情况\n"
        if self.position:
            md_content += f"- 持仓数量: {self.position['shares']} 股\n"
            md_content += f"- 平均成本: {self.position['average_price']} 元\n"
            md_content += f"- 购买日期: {self.position['purchase_date']}\n"
            md_content += f"- 浮动盈亏: {self.position['unrealized_pnl']} 元 ({self.position['unrealized_pnl_percent']}%)\n"
        else:
            md_content += "- 暂无持仓\n"
        
        md_content += "\n## 近期操作记录\n"
        if self.recent_operations:
            for op in self.recent_operations:
                md_content += f"- {op['date']}: {op['type']} {op['shares']} 股 @ {op['price']} 元\n"
        else:
            md_content += "- 暂无近期操作\n"
        
        md_content += "\n## AI分析结果（基于周线数据）\n"
        md_content += analysis_content
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"周线分析报告已保存为: {file_path}")
        return file_path
    
    def plot_support_resistance(self):
        """绘制支撑位和阻力位图表"""
        plt.figure(figsize=(15, 8))
        
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 绘制价格走势
        plt.plot(self.data['date'], self.data['close'], label='收盘价', color='blue')
        
        # 绘制移动平均线
        if 'MA5' in self.data.columns:
            plt.plot(self.data['date'], self.data['MA5'], label='MA5', color='red', linestyle='--')
        if 'MA20' in self.data.columns:
            plt.plot(self.data['date'], self.data['MA20'], label='MA20', color='green', linestyle='--')
        if 'MA50' in self.data.columns:
            plt.plot(self.data['date'], self.data['MA50'], label='MA50', color='purple', linestyle='--')
        
        # 绘制支撑位和阻力位
        for support in self.support_levels:
            plt.axhline(y=support['value'], color='green', linestyle='--', alpha=0.5)
            plt.text(self.data['date'].iloc[0], support['value'], f"支撑: {support['value']} ({support['type']})", 
                     color='green', fontsize=10, verticalalignment='bottom')
        
        for resistance in self.resistance_levels:
            plt.axhline(y=resistance['value'], color='red', linestyle='--', alpha=0.5)
            plt.text(self.data['date'].iloc[0], resistance['value'], f"阻力: {resistance['value']} ({resistance['type']})", 
                     color='red', fontsize=10, verticalalignment='top')
        
        # 标记持仓成本
        if self.position:
            plt.axhline(y=self.position['average_price'], color='orange', linestyle='-', alpha=0.7)
            plt.text(self.data['date'].iloc[0], self.position['average_price'], 
                     f"持仓成本: {self.position['average_price']}", 
                     color='orange', fontsize=10, verticalalignment='bottom')
        
        plt.title(f'{self.ticker} 周线价格走势与支撑阻力位分析')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        # 保存图表
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_support_resistance.png')
        plt.savefig(chart_path)
        print(f"周线支撑阻力位分析图表已保存为: {chart_path}")
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.calculate_support_resistance()
        self.plot_support_resistance()
        
        # 生成AI提示词
        prompt = self.generate_ai_prompt()
        print("\n=== 生成的AI分析提示词 ===")
        print(prompt)
        
        # 获取AI分析结果
        ai_analysis = self.get_ai_analysis(prompt)
        
        print("\n=== AI分析结果 ===")
        print(ai_analysis)
        
        # 保存分析结果到markdown文件
        self.save_analysis_to_md(ai_analysis)
        
        # 提示用户如何使用
        print("\n=== 分析完成 ===")
        print("周线分析报告已保存为markdown文件，包含完整的股票分析和操作建议。")
        
        return ai_analysis

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用本地Ollama AI分析周线股票")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认使用config.py中的第一个股票")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
        # 查找对应的股票名称
        ticker_name = ticker
        for name, code in STOCK_TICKERS.items():
            if code == ticker:
                ticker_name = name
                break
    else:
        # 使用第一个股票代码进行分析
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_weekly_data.csv'
    print(f"分析股票: {ticker} ({ticker_name})")
    
    # 分析数据
    analyzer = WeeklyStockAILocalAnalyzer(file_path)
    
    # 先加载数据
    analyzer.load_data()
    
    # 从交易记录计算持仓情况
    if ticker in TRADING_RECORDS:
        position = analyzer.calculate_position_from_trading_records(TRADING_RECORDS[ticker])
        analyzer.set_position(
            position['shares'],
            position['average_price'],
            position['purchase_date']
        )
        print(f"从交易记录计算的持仓情况: {position['shares']}股，平均成本: {position['average_price']}元")
    else:
        print("配置文件中没有找到该股票的交易记录，无法计算持仓情况")
    
    # 从配置文件中获取交易记录
    if ticker in TRADING_RECORDS:
        for operation in TRADING_RECORDS[ticker]:
            analyzer.add_operation(
                operation['date'],
                operation['type'],
                operation['price'],
                operation['shares']
            )
        print(f"使用配置文件中的交易记录，共{len(TRADING_RECORDS[ticker])}条")
    else:
        print("配置文件中没有找到该股票的交易记录")
    
    # 运行分析
    analyzer.run_analysis()