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

from config import DATA_DIR, AI_CONFIG
from trading_records import TRADING_RECORDS

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class StockAIComprehensiveAnalyzer:
    def __init__(self, file_path, model="qwen3:30b"):
        self.file_path = file_path
        self.model = model
        self.ticker = None
        self.analysis_reports = {
            'financial_statements': {},
            'fund_flow': {},
            'margin_data': {},
            'valuation': {},
            'eastmoney_financial': {},
            'performance_forecast': {},
            'shareholder_structure': {},
            'research_reports': {}
        }
    
    def load_data(self):
        """加载数据"""
        # 从文件路径中提取股票代码
        file_name = os.path.basename(self.file_path)
        self.ticker = file_name.split('_')[0]
        print(f"加载股票: {self.ticker}")
        
        # 从技术趋势分析JSON文件中获取数据
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        trend_file = os.path.join(stock_dir, f"{self.ticker}_technical_trend_analysis.json")
        
        if os.path.exists(trend_file):
            print(f"加载技术趋势分析文件: {trend_file}")
            with open(trend_file, 'r', encoding='utf-8') as f:
                self.technical_trend_data = json.load(f)
        else:
            print(f"技术趋势分析文件不存在: {trend_file}")
            self.technical_trend_data = {}
        
        return self.ticker
    
    def get_stock_info(self):
        """从company_basic.json文件中获取股票基本信息"""
        stock_info = {
            'name': '',
            'industry': '',
            'pe': '',
            'pb': '',
            'market_cap': '',
            'total_assets': '',
            'main_business': '',
            'full_name': '',
            'registered_capital': '',
            'employee_count': '',
            'em_industry': '',
            'csrc_industry': '',
            'actual_controller': '',
            'sector_hierarchy': ''
        }
        
        try:
            # 构建固定的公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            info_file = os.path.join(stock_dir, f"{self.ticker}_company_basic.json")
            
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
                stock_info['industry'] = basic_info.get('板块名称层级', '')
                stock_info['main_business'] = basic_info.get('主营业务', '')
                stock_info['full_name'] = basic_info.get('公司全称', '')
                stock_info['registered_capital'] = basic_info.get('注册资本', '')
                stock_info['employee_count'] = basic_info.get('员工人数', '')
                stock_info['em_industry'] = basic_info.get('EM2016行业分类', '')
                stock_info['csrc_industry'] = basic_info.get('CSRC行业分类', '')
                stock_info['actual_controller'] = basic_info.get('实际控制人', '')
                stock_info['sector_hierarchy'] = basic_info.get('板块名称层级', '')
            
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
        """从company_basic.json文件中获取公司详细信息"""
        company_details = {
            'full_name': '',
            'business_scope': '',
            'financial_report': {},
            'data_sources': []
        }
        
        try:
            # 构建固定的公司信息文件路径
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            info_file = os.path.join(stock_dir, f"{self.ticker}_company_basic.json")
            
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
            
            # 提取经营范围（如果basic_info中没有）
            if not company_details['business_scope'] and 'business_scope' in data:
                company_details['business_scope'] = data['business_scope']
            
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
            pattern = f"{self.ticker}_financial_analysis_*.md"
        elif report_type == 'fund_flow':
            pattern = f"{self.ticker}_fund_flow_analysis_*.md"
        elif report_type == 'margin_data':
            pattern = f"{self.ticker}_margin_data_analysis_*.md"
        elif report_type == 'valuation':
            pattern = f"{self.ticker}_valuation_analysis_*.md"
        elif report_type == 'eastmoney_financial':
            pattern = f"{self.ticker}_em_financial_analysis_*.md"
        elif report_type == 'performance_forecast':
            pattern = f"{self.ticker}_performance_analysis_*.md"
        elif report_type == 'shareholder_structure':
            pattern = f"{self.ticker}_shareholder_structure_analysis_*.md"
        elif report_type == 'research_reports':
            pattern = f"{self.ticker}_research_reports_analysis_*.md"
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
        report_types = ['financial_statements', 'fund_flow', 'margin_data', 'valuation', 
                      'eastmoney_financial', 'performance_forecast', 'shareholder_structure', 'research_reports']
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
        # 获取股票基本信息
        stock_info = self.get_stock_info()
        
        # 获取公司详细信息
        company_details = self.get_company_details()
        
        # 获取实时股票信息
        realtime_info = self.get_realtime_stock_info()
        
        summary = {
            'realtime_info': realtime_info,
            'company_details': company_details,
            'analysis_reports': self.analysis_reports,
            'stock_info': stock_info
        }
        
        return summary
    
    def generate_ai_prompt(self):
        """生成AI分析提示词，包含所有分析报告的核心内容"""
        summary = self.get_stock_summary()
        company_details = summary.get('company_details', {})
        analysis_reports = summary.get('analysis_reports', {})
        
        prompt = f"""你是一位专业的金融分析师，擅长股票技术分析和投资建议。请基于以下股票数据和综合分析报告，提供详细的分析和操作建议：

=== 公司详细信息 ===
"""
        
        # 添加公司详细信息
        if company_details.get('full_name'):
            prompt += f"- 公司全称: {company_details['full_name']}\n"
        if company_details.get('business_scope'):
            prompt += f"- 经营范围: {company_details['business_scope'][:150]}...\n"
        if company_details.get('data_sources'):
            prompt += f"- 数据来源: {', '.join(company_details['data_sources'])}\n"
        
        # 添加公司基本信息
        stock_info = summary.get('stock_info', {})
        if stock_info.get('full_name'):
            prompt += f"- 公司全称: {stock_info['full_name']}\n"
        if stock_info.get('registered_capital'):
            # 将注册资本从万元换算为亿元并标注单位
            try:
                registered_capital = float(stock_info['registered_capital'])
                registered_capital_billion = round(registered_capital / 10000, 2)
                prompt += f"- 注册资本: {registered_capital_billion} 亿元\n"
            except (ValueError, TypeError):
                prompt += f"- 注册资本: {stock_info['registered_capital']}\n"
        if stock_info.get('employee_count'):
            prompt += f"- 员工人数: {stock_info['employee_count']}\n"
        if stock_info.get('main_business'):
            prompt += f"- 主营业务: {stock_info['main_business']}\n"
        if stock_info.get('em_industry'):
            prompt += f"- EM2016行业分类: {stock_info['em_industry']}\n"
        if stock_info.get('csrc_industry'):
            prompt += f"- CSRC行业分类: {stock_info['csrc_industry']}\n"
        if stock_info.get('actual_controller'):
            prompt += f"- 实际控制人: {stock_info['actual_controller']}\n"
        if stock_info.get('sector_hierarchy'):
            prompt += f"- 板块名称层级: {stock_info['sector_hierarchy']}\n"
        
        # 添加技术趋势分析JSON全文
        if analysis_reports.get('technical_trend'):
            technical_trend = analysis_reports['technical_trend']
            prompt += "\n=== 技术趋势分析JSON全文 ===\n"
            prompt += json.dumps(technical_trend, ensure_ascii=False, indent=2) + "\n"
        
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
        # 暂时屏蔽技术趋势分析文本内容的生成，避免与JSON部分重复
        
        # 添加股票财务分析
        if analysis_reports.get('eastmoney_financial'):
            prompt += "\n=== 股票财务分析 ===\n"
            eastmoney_financial = analysis_reports['eastmoney_financial']
            if '全文' in eastmoney_financial:
                prompt += eastmoney_financial['全文']
            else:
                for key, value in eastmoney_financial.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加业绩预告与分红分析
        if analysis_reports.get('performance_forecast'):
            prompt += "\n=== 业绩预告与分红分析 ===\n"
            performance_forecast = analysis_reports['performance_forecast']
            if '全文' in performance_forecast:
                prompt += performance_forecast['全文']
            else:
                for key, value in performance_forecast.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加股东结构分析
        if analysis_reports.get('shareholder_structure'):
            prompt += "\n=== 股东结构分析 ===\n"
            shareholder_structure = analysis_reports['shareholder_structure']
            if '全文' in shareholder_structure:
                prompt += shareholder_structure['全文']
            else:
                for key, value in shareholder_structure.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加研究报告分析
        if analysis_reports.get('research_reports'):
            prompt += "\n=== 研究报告分析 ===\n"
            research_reports = analysis_reports['research_reports']
            if '全文' in research_reports:
                prompt += research_reports['全文']
            else:
                for key, value in research_reports.items():
                    prompt += f"- {key}: {value}\n"
        
        # 添加交易记录信息
        prompt += "\n=== 交易记录 ===\n"
        if self.ticker in TRADING_RECORDS:
            # 预处理交易记录，计算持仓信息
            total_shares = 0
            total_cost = 0
            buy_operations = 0
            sell_operations = 0
            
            for operation in TRADING_RECORDS[self.ticker]:
                prompt += f"- 日期: {operation['date']}, 类型: {operation['type']}, 价格: {operation['price']}, 数量: {operation['shares']}\n"
                
                if operation['type'] == 'buy':
                    total_shares += operation['shares']
                    total_cost += operation['price'] * operation['shares']
                    buy_operations += 1
                elif operation['type'] == 'sell':
                    total_shares -= operation['shares']
                    total_cost -= operation['price'] * operation['shares']
                    sell_operations += 1
            
            # 计算持仓成本
            avg_cost = 0
            if total_shares > 0:
                avg_cost = total_cost / total_shares
            
            # 添加持仓信息
            prompt += f"\n=== 持仓信息 ===\n"
            prompt += f"- 持仓数量: {total_shares} 股\n"
            if total_shares > 0:
                prompt += f"- 持仓成本: {avg_cost:.2f} 元\n"
            else:
                prompt += f"- 持仓成本: 0 元\n"
            prompt += f"- 买入操作: {buy_operations} 次\n"
            prompt += f"- 卖出操作: {sell_operations} 次\n"
        else:
            prompt += "暂无持仓及交易\n"
            prompt += "\n=== 持仓信息 ===\n"
            prompt += "- 持仓数量: 0 股\n"
            prompt += "- 持仓成本: 0 元\n"
            prompt += "- 买入操作: 0 次\n"
            prompt += "- 卖出操作: 0 次\n"
        
        # 添加分析要求
        prompt += """\n=== 综合分析要求 ===\n请基于以上所有数据和分析报告，提供以下内容：\n1. 股票当前技术面分析（趋势、动量、量能等）\n2. 支撑位和阻力位的有效性分析\n3. 针对当前持仓的具体操作建议\n4. 短期（1-2周）和中期（1-3个月）市场展望\n5. 具体的买入/卖出点位建议和止损止盈设置\n6. 风险评估和资金管理建议\n7. 结合公司基本信息和行业情况的分析\n8. 基于财报数据的财务状况分析\n9. 基于资金流数据的市场情绪分析\n10. 基于融资融券数据的多空力量分析\n11. 基于估值数据的投资价值分析\n12. 基于东方财富财务数据的深度财务分析\n13. 基于业绩预告与分红数据的盈利预期分析\n14. 基于股东结构数据的股权结构分析\n15. 基于研究报告数据的机构观点分析\n16. 综合所有分析报告的结论，给出最终的投资建议\n\n请提供详细、专业的分析，基于数据和技术指标，避免泛泛而谈。"""
        
        return prompt
    
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
                    "max_tokens": max_tokens  # 足够的响应长度
                }
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {str(e)}")
            # 返回默认分析结果
            return "无法获取AI分析，请检查Ollama服务是否正常运行。"
    
    def save_analysis_to_md(self, analysis_content):
        """将分析结果保存为markdown文件"""
        # 获取股票基本信息
        stock_info = self.get_stock_info()
        
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_comprehensive_analysis_{timestamp}.md"
        file_path = os.path.join(stock_dir, filename)
        
        # 从技术趋势分析JSON文件中获取数据
        current_price = 0
        analysis_date = datetime.now().strftime('%Y-%m-%d')
        technical_indicators = {}
        
        # 使用analysis_reports['technical_trend']作为唯一数据源，确保数据一致性
        technical_trend = self.analysis_reports.get('technical_trend', {})
        if technical_trend:
            # 获取当前价格
            if 'technical_indicators' in technical_trend:
                ti = technical_trend['technical_indicators']
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
            if 'meta' in technical_trend:
                analysis_date = technical_trend['meta'].get('last_data_date', analysis_date)
        
        # 构建markdown内容
        md_content = f"""# {stock_info['name']} ({self.ticker}) 股票综合分析报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 股票基本信息
- 股票代码: {self.ticker}
- 股票名称: {stock_info['name']}
- 所属行业: {stock_info['industry']}
- 当前价格: {current_price:.2f} 元
- 分析基准日期: {analysis_date}

## 技术指标数据
"""
        
        for indicator, value in technical_indicators.items():
            md_content += f"- {indicator}: {value}\n"
        
        # 添加实时股票信息
        realtime_info = self.get_realtime_stock_info()
        if realtime_info:
            md_content += "\n## 实时股票信息\n"
            # 添加所有字段
            for key, value in realtime_info.items():
                md_content += f"- {key}: {value}\n"
        
        # 添加分析报告全文
        analysis_reports = self.analysis_reports
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
            if 'trend_confidence' in technical_trend:
                md_content += "\n### 趋势信心度\n"
                for trend, confidence in technical_trend['trend_confidence'].items():
                    md_content += f"- {trend}: {confidence}\n"
            if 'trading_signal' in technical_trend:
                md_content += "\n### 交易信号\n"
                trading_signal = technical_trend['trading_signal']
                md_content += f"- 操作: {trading_signal.get('action', 'N/A')}\n"
                md_content += f"- 信心度: {trading_signal.get('confidence', 'N/A')}\n"
                md_content += f"- 理由: {trading_signal.get('reason', 'N/A')}\n"
            if 'signal_conflicts' in technical_trend:
                md_content += "\n### 信号冲突\n"
                for conflict in technical_trend['signal_conflicts']:
                    md_content += f"- {conflict}\n"
            if 'risk_metrics' in technical_trend:
                md_content += "\n### 风险指标\n"
                for metric, value in technical_trend['risk_metrics'].items():
                    md_content += f"- {metric}: {value}\n"
            if 'price_action' in technical_trend and 'volatility_regime' in technical_trend['price_action']:
                md_content += f"\n### 波动率状态\n"
                md_content += f"- {technical_trend['price_action']['volatility_regime']}\n"
            if 'multi_timeframe' in technical_trend:
                md_content += "\n### 多周期趋势\n"
                multi_timeframe = technical_trend['multi_timeframe']
                md_content += f"- 周线趋势: {multi_timeframe.get('weekly_trend', 'N/A')}\n"
                md_content += f"- 日线趋势: {multi_timeframe.get('daily_trend', 'N/A')}\n"
                md_content += f"- 背离: {multi_timeframe.get('divergence', 'N/A')}\n"
            if 'consistency_score' in technical_trend:
                md_content += "\n### 指标一致性评分\n"
                md_content += f"- {technical_trend['consistency_score']}\n"
            if 'market_snapshot' in technical_trend:
                md_content += "\n### 市场快照\n"
                md_content += f"- {technical_trend['market_snapshot']}\n"
        
        # 添加股票财务分析
        if analysis_reports.get('eastmoney_financial'):
            md_content += "\n## 东方财富财务分析全文\n"
            eastmoney_financial = analysis_reports['eastmoney_financial']
            if '全文' in eastmoney_financial:
                md_content += eastmoney_financial['全文']
            else:
                for key, value in eastmoney_financial.items():
                    md_content += f"- {key}: {value}\n"
        
        # 添加业绩预告与分红分析
        if analysis_reports.get('performance_forecast'):
            md_content += "\n## 业绩预告与分红分析全文\n"
            performance_forecast = analysis_reports['performance_forecast']
            if '全文' in performance_forecast:
                md_content += performance_forecast['全文']
            else:
                for key, value in performance_forecast.items():
                    md_content += f"- {key}: {value}\n"
        
        # 添加股东结构分析
        if analysis_reports.get('shareholder_structure'):
            md_content += "\n## 股东结构分析全文\n"
            shareholder_structure = analysis_reports['shareholder_structure']
            if '全文' in shareholder_structure:
                md_content += shareholder_structure['全文']
            else:
                for key, value in shareholder_structure.items():
                    md_content += f"- {key}: {value}\n"
        
        # 添加研究报告分析
        if analysis_reports.get('research_reports'):
            md_content += "\n## 研究报告分析全文\n"
            research_reports = analysis_reports['research_reports']
            if '全文' in research_reports:
                md_content += research_reports['全文']
            else:
                for key, value in research_reports.items():
                    md_content += f"- {key}: {value}\n"
        
        md_content += "\n## AI综合分析结果\n"
        md_content += analysis_content
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"综合分析报告已保存为: {file_path}")
        return file_path
    
    def save_prompt_to_txt(self, prompt):
        """保存提示词相关内容到TXT文件"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成文件名：股票代码+时间戳
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_prompt_info_{timestamp}.txt"
        file_path = os.path.join(stock_dir, filename)
        
        # 构建TXT内容
        txt_content = f"{self.ticker} 提示词信息\n"
        txt_content += "=" * 80 + "\n"
        txt_content += f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        txt_content += "完整提示词\n"
        txt_content += "=" * 80 + "\n"
        txt_content += prompt + "\n"
        
        # 保存文件
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(txt_content)
        
        print(f"提示词信息已保存为: {file_path}")
        return file_path
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.load_analysis_reports()
        
        # 生成AI提示词
        prompt = self.generate_ai_prompt()
        print("\n=== 生成的AI分析提示词 ===")
        print(prompt[:2000] + "..." if len(prompt) > 2000 else prompt)  # 只显示前2000个字符
        print(f"\n提示词长度: {len(prompt)} 字符")
        
        # 保存提示词信息
        self.save_prompt_to_txt(prompt)
        
        # 获取AI分析结果
        ai_analysis = self.get_ai_analysis(prompt)
        
        print("\n=== AI分析结果 ===")
        print(ai_analysis)
        
        # 保存分析结果到markdown文件
        self.save_analysis_to_md(ai_analysis)
        
        # 提示用户如何使用
        print("\n=== 分析完成 ===")
        print("综合分析报告已保存为markdown文件，包含完整的股票分析和操作建议。")
        print("提示词信息已保存为TXT文件，包含提示词内容和数据信息。")
        
        return ai_analysis

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用本地Ollama AI进行股票综合分析")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认分析config.py中的所有股票")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定要分析的股票列表
    if args.ticker:
        # 分析单个股票
        ticker = args.ticker
        # 查找对应的股票名称
        ticker_name = ticker
        for name, code in STOCK_TICKERS.items():
            if code == ticker:
                ticker_name = name
                break
        stock_list = [(ticker_name, ticker)]
    else:
        # 分析所有股票
        stock_list = list(STOCK_TICKERS.items())
        print(f"分析配置文件中的所有股票，共{len(stock_list)}只")
    
    # 遍历分析每只股票
    for ticker_name, ticker in stock_list:
        print(f"\n=====================================")
        print(f"分析股票: {ticker} ({ticker_name})")
        print("=====================================")
        
        file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
        
        # 分析数据
        analyzer = StockAIComprehensiveAnalyzer(file_path)
        
        # 运行完整分析
        analyzer.run_analysis()
        
        # 等待2秒，避免请求过于频繁
        import time
        time.sleep(2)