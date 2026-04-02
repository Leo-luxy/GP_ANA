#!/usr/bin/env python3
# stock_ai_comprehensive_analyzer.py
# 功能：综合股票的财务报表、资金流、融资融券和估值分析报告，发送给本地Ollama AI进行综合分析
# 实现原理：
# 1. 加载股票历史数据
# 2. 计算支撑位和阻力位
# 3. 获取股票基本信息
# 4. 读取并提取四个分析报告的核心内容
# 5. 生成综合AI分析提示词，包含所有相关信息
# 6. 将提示词发送给本地部署的Ollama AI
# 7. 接收AI分析结果并保存为markdown文件
# 8. 绘制支撑位和阻力位图表
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import json
import os
import sys
import re
import akshare as ak

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG, TRADING_RECORDS

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class StockAIComprehensiveAnalyzer:
    def __init__(self, file_path, model="qwen3:30b"):
        self.file_path = file_path
        self.model = model
        self.data = None
        self.ticker = None
        self.support_levels = []
        self.resistance_levels = []
        self.position = {}
        self.recent_operations = []
        self.analysis_reports = {
            'financial_statements': {},
            'fund_flow': {},
            'margin_data': {},
            'valuation': {}
        }
    
    def load_data(self):
        """加载数据"""
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
            file_name = os.path.basename(self.file_path)
            self.ticker = file_name.split('_')[0]
        
        return self.data
    
    def calculate_support_resistance(self):
        """计算支撑位和阻力位"""
        # 使用简单的方法计算支撑位和阻力位
        # 1. 使用近期最低价作为支撑位
        # 2. 使用近期最高价作为阻力位
        # 3. 使用移动平均线作为动态支撑/阻力
        
        # 获取最近30天的数据
        recent_data = self.data.tail(30)
        
        # 计算支撑位
        # 最低价格
        support_low = recent_data['low'].min()
        self.support_levels.append({
            'type': '最低价格',
            'value': round(support_low, 2),
            'date': recent_data[recent_data['low'] == support_low]['date'].iloc[0].strftime('%Y-%m-%d')
        })
        
        # 50日均线作为支撑
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
        
        # 50日均线作为阻力
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
        total_shares = 0
        total_investment = 0  # 总投入资金
        total_return = 0     # 总回收资金
        purchase_date = None
        
        # 按日期排序交易记录
        sorted_records = sorted(trading_records, key=lambda x: x['date'])
        
        for record in sorted_records:
            if record['type'] == 'buy':
                total_shares += record['shares']
                total_investment += record['price'] * record['shares']
                # 更新购买日期为最后一次买入日期
                purchase_date = record['date']
            elif record['type'] == 'sell':
                total_shares -= record['shares']
                total_return += record['price'] * record['shares']
        
        # 计算剩余成本和平均成本
        remaining_cost = total_investment - total_return
        if total_shares > 0:
            average_price = remaining_cost / total_shares
        else:
            average_price = 0
        
        return {
            'shares': total_shares,
            'average_price': round(average_price, 3),
            'purchase_date': purchase_date
        }
    
    def get_stock_info(self):
        """从company_info.json文件中获取股票基本信息"""
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
            # 构建固定的公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            info_file = os.path.join(stock_dir, f"{self.ticker}_company_info.json")
            
            # 检查文件是否存在
            if not os.path.exists(info_file):
                print(f"公司信息文件不存在: {info_file}")
                return stock_info
            
            print(f"从文件加载公司基本信息: {info_file}")
            
            # 读取文件
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取公司基本信息
            if 'basic_info' in data:
                basic_info = data['basic_info']
                # 映射字段
                stock_info['name'] = basic_info.get('公司简称', '')
                stock_info['industry'] = basic_info.get('所属行业', '')
                stock_info['main_business'] = basic_info.get('主营业务', '')
            
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
                        stock_info['pe'] = latest_valuation.get('市盈率(TTM)', latest_valuation.get('pe_ttm', ''))
                        stock_info['pb'] = latest_valuation.get('市净率', latest_valuation.get('pb', ''))
                        stock_info['market_cap'] = latest_valuation.get('总市值', '')
                        print(f"成功从CSV文件加载估值信息: {valuation_file}")
                except Exception as e:
                    print(f"读取估值CSV文件时出错: {str(e)}")
            
            print("成功从文件加载公司基本信息")
            print(f"加载的基本信息: {stock_info}")
            
        except Exception as e:
            print(f"从文件获取股票基本信息时出错: {str(e)}")
        
        return stock_info
    
    def get_realtime_stock_info(self):
        """使用akshare获取实时股票信息"""
        realtime_info = {}
        
        try:
            print(f"正在获取{self.ticker}的实时数据...")
            
            # 转换股票代码格式为雪球格式
            ticker = self.ticker
            if ticker.endswith('.SZ'):
                ticker = "SZ" + ticker.replace('.SZ', '')
            elif ticker.endswith('.SS'):
                ticker = "SH" + ticker.replace('.SS', '')
            
            # 使用akshare获取实时股票信息
            df = ak.stock_individual_spot_xq(symbol=ticker)
            
            # 提取实时信息
            if not df.empty:
                # 提取所有字段
                realtime_info = df.set_index('item')['value'].to_dict()
                # 添加更新时间
                realtime_info['update_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print("成功获取实时股票信息")
                print(f"实时信息: {realtime_info}")
            else:
                print("未获取到实时股票信息")
                
        except Exception as e:
            print(f"获取实时股票信息时出错: {str(e)}")
        
        return realtime_info
    
    def get_company_details(self):
        """从stock_company_info_v2生成的文件中获取公司详细信息"""
        company_details = {
            'full_name': '',
            'business_scope': '',
            'financial_report': {},
            'data_sources': []
        }
        
        try:
            # 构建固定的公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            info_file = os.path.join(stock_dir, f"{self.ticker}_company_info.json")
            
            # 检查文件是否存在
            if not os.path.exists(info_file):
                print(f"公司详细信息文件不存在: {info_file}")
                return company_details
            
            print(f"加载公司详细信息文件: {info_file}")
            
            # 读取文件
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 提取公司信息
            if 'basic_info' in data:
                basic_info = data['basic_info']
                company_details['full_name'] = basic_info.get('公司全称', '')
                company_details['business_scope'] = basic_info.get('经营范围', '')
            
            # 提取数据来源
            if 'data_sources' in data:
                company_details['data_sources'] = data['data_sources']
            
            print("成功加载公司详细信息")
                
        except Exception as e:
            print(f"获取公司详细信息时出错: {str(e)}")
        
        return company_details
    
    def read_analysis_report(self, report_type):
        """读取分析报告文件"""
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        import glob
        
        if report_type == 'financial_statements':
            pattern = f"{self.ticker}_financial_statements_analysis_*.md"
        elif report_type == 'fund_flow':
            pattern = f"{self.ticker}_fund_flow_analysis_*.md"
        elif report_type == 'margin_data':
            pattern = f"{self.ticker}_margin_data_analysis_*.md"
        elif report_type == 'valuation':
            pattern = f"{self.ticker}_valuation_analysis_*.md"
        else:
            return {}
        
        # 查找报告文件
        report_files = glob.glob(os.path.join(stock_dir, pattern))
        if not report_files:
            print(f"未找到{report_type}分析报告文件")
            return {}
        
        # 使用最新的报告
        report_files.sort(key=os.path.getmtime, reverse=True)
        report_file = report_files[0]
        
        print(f"加载{report_type}分析报告: {report_file}")
        
        try:
            with open(report_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 提取核心内容
            core_content = self.extract_core_content(content, report_type)
            return core_content
        except Exception as e:
            print(f"读取{report_type}分析报告时出错: {str(e)}")
            return {}
    
    def extract_core_content(self, content, report_type):
        """提取分析报告的全文内容"""
        core_content = {}
        
        # 返回完整的报告内容
        core_content['全文'] = content
        
        return core_content
    
    def load_analysis_reports(self):
        """加载所有分析报告"""
        report_types = ['financial_statements', 'fund_flow', 'margin_data', 'valuation']
        for report_type in report_types:
            self.analysis_reports[report_type] = self.read_analysis_report(report_type)
        
        # 加载技术趋势分析报告
        self.analysis_reports['technical_trend'] = self.read_technical_trend_analysis()
    
    def read_technical_trend_analysis(self):
        """读取技术趋势分析报告"""
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        
        # 查找技术趋势分析文件（新的固定文件名）
        trend_file = os.path.join(stock_dir, f"{self.ticker}_technical_trend_analysis.json")
        if not os.path.exists(trend_file):
            # 尝试查找旧的带时间戳的文件
            import glob
            pattern = f"{self.ticker}_technical_trend_analysis_*.json"
            trend_files = glob.glob(os.path.join(stock_dir, pattern))
            if not trend_files:
                print(f"未找到技术趋势分析文件")
                return {}
            # 使用最新的旧文件
            trend_files.sort(key=os.path.getmtime, reverse=True)
            trend_file = trend_files[0]
        
        print(f"加载技术趋势分析报告: {trend_file}")
        
        try:
            with open(trend_file, 'r', encoding='utf-8') as f:
                content = json.load(f)
            
            return content
        except Exception as e:
            print(f"读取技术趋势分析报告时出错: {str(e)}")
            return {}
    
    def get_stock_summary(self):
        """获取股票综合信息"""
        # 获取最新数据
        latest = self.data.iloc[-1]
        
        # 获取股票基本信息
        stock_info = self.get_stock_info()
        
        # 获取公司详细信息
        company_details = self.get_company_details()
        
        # 获取实时股票信息
        realtime_info = self.get_realtime_stock_info()
        
        summary = {
            'ticker': self.ticker,
            'name': stock_info['name'],
            'industry': stock_info['industry'],
            'current_price': round(latest['close'], 2),
            'date': latest['date'].strftime('%Y-%m-%d'),
            'realtime_info': realtime_info,
            'support_levels': self.support_levels,
            'resistance_levels': self.resistance_levels,
            'position': self.position,
            'recent_operations': self.recent_operations,
            'company_details': company_details,
            'analysis_reports': self.analysis_reports,
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
                'ATR': round(latest.get('ATR', 0), 2),
                'OBV': round(latest.get('OBV', 0), 2),
                'ADX': round(latest.get('ADX', 0), 2)
            }
        }
        
        return summary
    
    def generate_ai_prompt(self):
        """生成AI分析提示词，包含所有分析报告的核心内容"""
        summary = self.get_stock_summary()
        company_details = summary.get('company_details', {})
        analysis_reports = summary.get('analysis_reports', {})
        
        prompt = f"""你是一位专业的金融分析师，擅长股票技术分析和投资建议。请基于以下股票数据和综合分析报告，提供详细的分析和操作建议：

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
        
        # 添加支撑位和阻力位分析
        prompt += "\n=== 支撑位分析 ===\n"
        for support in summary['support_levels']:
            prompt += f"- {support['type']}: {support['value']} 元 (形成日期: {support['date']})\n"
        
        prompt += "\n=== 阻力位分析 ===\n"
        for resistance in summary['resistance_levels']:
            prompt += f"- {resistance['type']}: {resistance['value']} 元 (形成日期: {resistance['date']})\n"
        
        # 添加持仓情况
        prompt += "\n=== 持仓情况 ===\n"
        if summary['position']:
            prompt += f"- 持仓数量: {summary['position']['shares']} 股\n"
            prompt += f"- 平均成本: {summary['position']['average_price']} 元\n"
            prompt += f"- 购买日期: {summary['position']['purchase_date']}\n"
            prompt += f"- 浮动盈亏: {summary['position']['unrealized_pnl']} 元 ({summary['position']['unrealized_pnl_percent']}%)\n"
        else:
            prompt += "- 暂无持仓\n"
        
        # 添加近期操作记录
        prompt += "\n=== 近期操作记录 ===\n"
        if summary['recent_operations']:
            for op in summary['recent_operations']:
                prompt += f"- {op['date']}: {op['type']} {op['shares']} 股 @ {op['price']} 元\n"
        else:
            prompt += "- 暂无近期操作\n"
        
        # 添加技术指标数据
        prompt += "\n=== 技术指标数据 ===\n"
        for indicator, value in summary['technical_indicators'].items():
            prompt += f"- {indicator}: {value}\n"
        
        # 添加实时股票信息
        if summary.get('realtime_info'):
            realtime_info = summary['realtime_info']
            prompt += "\n=== 实时股票信息 ===\n"
            # 添加所有字段
            for key, value in realtime_info.items():
                prompt += f"- {key}: {value}\n"
        
        # 添加财务报表分析
        if analysis_reports.get('financial_statements'):
            prompt += "\n=== 财务报表分析 ===\n"
            financial_report = analysis_reports['financial_statements']
            if '全文' in financial_report:
                prompt += financial_report['全文']
            else:
                for key, value in financial_report.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加资金流分析
        if analysis_reports.get('fund_flow'):
            prompt += "\n=== 资金流分析 ===\n"
            fund_flow = analysis_reports['fund_flow']
            if '全文' in fund_flow:
                prompt += fund_flow['全文']
            else:
                for key, value in fund_flow.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加融资融券分析
        if analysis_reports.get('margin_data'):
            prompt += "\n=== 融资融券分析 ===\n"
            margin_data = analysis_reports['margin_data']
            if '全文' in margin_data:
                prompt += margin_data['全文']
            else:
                for key, value in margin_data.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加估值分析
        if analysis_reports.get('valuation'):
            prompt += "\n=== 估值分析 ===\n"
            valuation = analysis_reports['valuation']
            if '全文' in valuation:
                prompt += valuation['全文']
            else:
                for key, value in valuation.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加技术趋势分析
        if analysis_reports.get('technical_trend'):
            prompt += "\n=== 技术趋势分析 ===\n"
            technical_trend = analysis_reports['technical_trend']
            if 'indicator_trends' in technical_trend:
                for indicator, trend in technical_trend['indicator_trends'].items():
                    prompt += f"- {indicator}: {trend}\n"
            if 'technical_indicators' in technical_trend:
                prompt += "\n技术指标最新值:\n"
                for indicator, value in technical_trend['technical_indicators'].items():
                    prompt += f"- {indicator}: {value}\n"
        
        # 添加分析要求
        prompt += """\n=== 综合分析要求 ===\n请基于以上所有数据和分析报告，提供以下内容：\n1. 股票当前技术面分析（趋势、动量、量能等）\n2. 支撑位和阻力位的有效性分析\n3. 针对当前持仓的具体操作建议\n4. 短期（1-2周）和中期（1-3个月）市场展望\n5. 具体的买入/卖出点位建议和止损止盈设置\n6. 风险评估和资金管理建议\n7. 结合公司基本信息和行业情况的分析\n8. 基于财报数据的财务状况分析\n9. 基于资金流数据的市场情绪分析\n10. 基于融资融券数据的多空力量分析\n11. 基于估值数据的投资价值分析\n12. 综合四个分析报告的结论，给出最终的投资建议\n\n请提供详细、专业的分析，基于数据和技术指标，避免泛泛而谈。"""
        
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
                    "max_tokens": max_tokens*2  # 足够的响应长度
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
        
        # 生成文件名：股票代码+时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.ticker}_comprehensive_analysis_{timestamp}.md"
        file_path = os.path.join(stock_dir, filename)
        
        # 构建markdown内容
        md_content = f"""# {summary['name']} ({self.ticker}) 股票综合分析报告

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
        
        md_content += "\n## 技术指标数据\n"
        for indicator, value in summary['technical_indicators'].items():
            md_content += f"- {indicator}: {value}\n"
        
        # 添加实时股票信息
        if summary.get('realtime_info'):
            realtime_info = summary['realtime_info']
            md_content += "\n## 实时股票信息\n"
            # 添加所有字段
            for key, value in realtime_info.items():
                md_content += f"- {key}: {value}\n"
        
        # 添加分析报告全文
        analysis_reports = summary.get('analysis_reports', {})
        if analysis_reports.get('financial_statements'):
            md_content += "\n## 财务报表分析全文\n"
            financial_report = analysis_reports['financial_statements']
            if '全文' in financial_report:
                md_content += financial_report['全文']
            else:
                for key, value in financial_report.items():
                    md_content += f"- {key}: {value}\n"
        
        if analysis_reports.get('fund_flow'):
            md_content += "\n## 资金流分析全文\n"
            fund_flow = analysis_reports['fund_flow']
            if '全文' in fund_flow:
                md_content += fund_flow['全文']
            else:
                for key, value in fund_flow.items():
                    md_content += f"- {key}: {value}\n"
        
        if analysis_reports.get('margin_data'):
            md_content += "\n## 融资融券分析全文\n"
            margin_data = analysis_reports['margin_data']
            if '全文' in margin_data:
                md_content += margin_data['全文']
            else:
                for key, value in margin_data.items():
                    md_content += f"- {key}: {value}\n"
        
        if analysis_reports.get('valuation'):
            md_content += "\n## 估值分析全文\n"
            valuation = analysis_reports['valuation']
            if '全文' in valuation:
                md_content += valuation['全文']
            else:
                for key, value in valuation.items():
                    md_content += f"- {key}: {value}\n"
        
        # 添加技术趋势分析
        if analysis_reports.get('technical_trend'):
            md_content += "\n## 技术趋势分析\n"
            technical_trend = analysis_reports['technical_trend']
            if 'indicator_trends' in technical_trend:
                md_content += "### 技术指标趋势\n"
                for indicator, trend in technical_trend['indicator_trends'].items():
                    md_content += f"- {indicator}: {trend}\n"
            if 'technical_indicators' in technical_trend:
                md_content += "\n### 技术指标最新值\n"
                for indicator, value in technical_trend['technical_indicators'].items():
                    md_content += f"- {indicator}: {value}\n"
        
        md_content += "\n## AI综合分析结果\n"
        md_content += analysis_content
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"综合分析报告已保存为: {file_path}")
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
        
        plt.title(f'{self.ticker} 价格走势与支撑阻力位分析')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        
        # 保存图表
        chart_path = os.path.join(stock_dir, f'{self.ticker}_support_resistance.png')
        plt.savefig(chart_path)
        print(f"支撑阻力位分析图表已保存为: {chart_path}")
    
    def save_prompt_to_md(self, prompt):
        """保存提示词相关内容到Markdown文件"""
        # 获取股票综合信息
        summary = self.get_stock_summary()
        
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{self.ticker}_prompt_info_{timestamp}.md"
        file_path = os.path.join(stock_dir, filename)
        
        # 构建Markdown内容
        md_content = f"""# {summary['name']} ({self.ticker}) 提示词信息

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 股票基本信息
- 股票代码: {summary['ticker']}
- 股票名称: {summary['name']}
- 所属行业: {summary['industry']}
- 当前价格: {summary['current_price']} 元
- 分析日期: {summary['date']}

## 支撑位分析
"""
        
        for support in summary['support_levels']:
            md_content += f"- {support['type']}: {support['value']} 元 (形成日期: {support['date']})\n"
        
        md_content += """

## 阻力位分析
"""
        
        for resistance in summary['resistance_levels']:
            md_content += f"- {resistance['type']}: {resistance['value']} 元 (形成日期: {resistance['date']})\n"
        
        md_content += """

## 持仓情况
"""
        
        if summary['position']:
            md_content += f"- 持仓数量: {summary['position']['shares']} 股\n"
            md_content += f"- 平均成本: {summary['position']['average_price']} 元\n"
            md_content += f"- 购买日期: {summary['position']['purchase_date']}\n"
            md_content += f"- 浮动盈亏: {summary['position']['unrealized_pnl']} 元 ({summary['position']['unrealized_pnl_percent']}%)\n"
        else:
            md_content += "- 暂无持仓\n"
        
        md_content += """

## 近期操作记录
"""
        
        if summary['recent_operations']:
            for op in summary['recent_operations']:
                md_content += f"- {op['date']}: {op['type']} {op['shares']} 股 @ {op['price']} 元\n"
        else:
            md_content += "- 暂无近期操作\n"
        
        md_content += """

## 技术指标数据
"""
        
        for indicator, value in summary['technical_indicators'].items():
            md_content += f"- {indicator}: {value}\n"
        
        if summary.get('realtime_info'):
            md_content += """

## 实时股票信息
"""
            realtime_info = summary['realtime_info']
            for key, value in realtime_info.items():
                md_content += f"- {key}: {value}\n"
        
        md_content += """

## 报告信息
"""
        
        md_content += f"- 财务报表分析报告: {'存在' if summary['analysis_reports'].get('financial_statements') else '无'}\n"
        md_content += f"- 资金流分析报告: {'存在' if summary['analysis_reports'].get('fund_flow') else '无'}\n"
        md_content += f"- 融资融券分析报告: {'存在' if summary['analysis_reports'].get('margin_data') else '无'}\n"
        md_content += f"- 估值分析报告: {'存在' if summary['analysis_reports'].get('valuation') else '无'}\n"
        md_content += f"- 技术趋势分析报告: {'存在' if summary['analysis_reports'].get('technical_trend') else '无'}\n"
        
        md_content += """

## 完整提示词

```
{prompt}
```
"""
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"提示词信息已保存为: {file_path}")
        return file_path
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.calculate_support_resistance()
        self.plot_support_resistance()
        self.load_analysis_reports()
        
        # 生成AI提示词
        prompt = self.generate_ai_prompt()
        print("\n=== 生成的AI分析提示词 ===")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)  # 只显示前2000个字符
        print(f"\n提示词长度: {len(prompt)} 字符")
        
        # 保存提示词信息
        self.save_prompt_to_md(prompt)
        
        # 获取AI分析结果
        ai_analysis = self.get_ai_analysis(prompt)
        
        print("\n=== AI分析结果 ===")
        print(ai_analysis)
        
        # 保存分析结果到markdown文件
        self.save_analysis_to_md(ai_analysis)
        
        # 提示用户如何使用
        print("\n=== 分析完成 ===")
        print("综合分析报告已保存为markdown文件，包含完整的股票分析和操作建议。")
        print("提示词信息已保存为Markdown文件，包含提示词内容和数据信息。")
        
        return ai_analysis

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用本地Ollama AI进行股票综合分析")
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
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker} ({ticker_name})")
    
    # 分析数据
    analyzer = StockAIComprehensiveAnalyzer(file_path)
    
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
