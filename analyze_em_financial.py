# analyze_em_financial.py
"""
analyze_em_financial.py
功能：分析股票财务数据（杜邦分析、增长率、主要财务指标）
特点：
1. 读取并分析三类股票财务数据
2. 计算关键财务指标和趋势
3. 生成综合财务分析报告
4. 支持AI辅助分析
"""

import pandas as pd
import os
import sys
import json
from datetime import datetime
from typing import Dict, Optional, List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, AI_CONFIG


class EastmoneyFinancialAnalyzer:
    """股票财务数据分析师""" 

    def __init__(self, ticker: str):
        """
        初始化分析师
        :param ticker: 股票代码，例如：300433.SZ
        """
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'dupont': None,
            'growth': None,
            'main': None,
            'company_basic': None,
            'financial_indicators': None
        }
        self.company_name = None

    def load_data(self) -> bool:
        """加载股票财务数据"""
        print(f"\n[{self.ticker}] 加载股票财务数据...")

        # 加载公司基本信息
        company_basic_file = os.path.join(self.stock_dir, f"{self.ticker}_company_basic.json")
        if os.path.exists(company_basic_file):
            try:
                with open(company_basic_file, 'r', encoding='utf-8') as f:
                    self.data['company_basic'] = json.load(f)
                print(f"  加载公司基本信息数据")
                # 读取公司名称
                if not self.company_name and 'basic_info' in self.data['company_basic']:
                    basic_info = self.data['company_basic']['basic_info']
                    if 'company_name' in basic_info:
                        self.company_name = basic_info['company_name']
                        print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载公司基本信息时出错: {e}")
        else:
            print(f"  公司基本信息文件不存在: {company_basic_file}")

        # 加载财务指标数据
        financial_indicators_file = os.path.join(self.stock_dir, f"{self.ticker}_financial_indicators.json")
        if os.path.exists(financial_indicators_file):
            try:
                with open(financial_indicators_file, 'r', encoding='utf-8') as f:
                    self.data['financial_indicators'] = json.load(f)
                print(f"  加载财务指标数据")
            except Exception as e:
                print(f"  加载财务指标数据时出错: {e}")
        else:
            print(f"  财务指标数据文件不存在: {financial_indicators_file}")

        # 加载杜邦分析数据
        dupont_file = os.path.join(self.stock_dir, f"{self.ticker}_dupont_data.csv")
        if os.path.exists(dupont_file):
            try:
                self.data['dupont'] = pd.read_csv(dupont_file)
                print(f"  加载杜邦分析数据: {len(self.data['dupont'])} 条记录")
                # 读取公司名称
                if not self.company_name and 'SECURITY_NAME_ABBR' in self.data['dupont'].columns and not self.data['dupont'].empty:
                    self.company_name = self.data['dupont'].iloc[0]['SECURITY_NAME_ABBR']
                    print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载杜邦数据时出错: {e}")
        else:
            print(f"  杜邦分析数据文件不存在: {dupont_file}")

        # 加载增长率数据
        growth_file = os.path.join(self.stock_dir, f"{self.ticker}_growth_ratio_data.csv")
        if os.path.exists(growth_file):
            try:
                self.data['growth'] = pd.read_csv(growth_file)
                print(f"  加载增长率数据: {len(self.data['growth'])} 条记录")
                # 如果还没有公司名称，从这里读取
                if not self.company_name and 'SECURITY_NAME_ABBR' in self.data['growth'].columns and not self.data['growth'].empty:
                    self.company_name = self.data['growth'].iloc[0]['SECURITY_NAME_ABBR']
                    print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载增长率数据时出错: {e}")
        else:
            print(f"  增长率数据文件不存在: {growth_file}")

        # 加载主要财务指标数据
        main_file = os.path.join(self.stock_dir, f"{self.ticker}_main_financial_data.csv")
        if os.path.exists(main_file):
            try:
                self.data['main'] = pd.read_csv(main_file)
                print(f"  加载主要财务指标数据: {len(self.data['main'])} 条记录")
                # 如果还没有公司名称，从这里读取
                if not self.company_name and 'SECURITY_NAME_ABBR' in self.data['main'].columns and not self.data['main'].empty:
                    self.company_name = self.data['main'].iloc[0]['SECURITY_NAME_ABBR']
                    print(f"  识别到公司名称: {self.company_name}")
            except Exception as e:
                print(f"  加载主要财务指标数据时出错: {e}")
        else:
            print(f"  主要财务指标数据文件不存在: {main_file}")

        # 检查是否有数据加载成功
        return any(df is not None for df in self.data.values())

    def preprocess_data(self):
        """预处理数据"""
        for key, data in self.data.items():
            if data is not None:
                # 只对 DataFrame 类型的数据进行处理
                if isinstance(data, pd.DataFrame):
                    # 转换日期列
                    date_columns = ['REPORT_DATE', 'NOTICE_DATE', 'UPDATE_DATE']
                    for col in date_columns:
                        if col in data.columns:
                            # 使用更灵活的日期解析方式
                            data[col] = pd.to_datetime(data[col], format='mixed')
                    
                    # 按报告日期降序排序
                    if 'REPORT_DATE' in data.columns:
                        data.sort_values('REPORT_DATE', ascending=False, inplace=True)
                        data.reset_index(drop=True, inplace=True)
    


    def analyze_dupont(self) -> Dict:
        """分析杜邦数据"""
        if self.data['dupont'] is None:
            return {}

        df = self.data['dupont']
        analysis = {
            'roe_trend': [],
            'profit_margin_trend': [],
            'asset_turnover_trend': [],
            'equity_multiplier_trend': []
        }

        # 提取最近8个报告期的数据
        recent_data = df.head(8)
        for _, row in recent_data.iterrows():
            report_date = row['REPORT_DATE']
            analysis['roe_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('ROE', 0))
            })
            analysis['profit_margin_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('SALE_NPR', 0))
            })
            analysis['asset_turnover_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('TOTAL_ASSETS_TR', 0))
            })
            analysis['equity_multiplier_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('EQUITY_MULTIPLIER', 0))
            })

        return analysis

    def analyze_growth(self) -> Dict:
        """分析增长率数据"""
        if self.data['growth'] is None:
            return {}

        df = self.data['growth']
        analysis = {
            'revenue_growth': [],
            'profit_growth': [],
            'asset_growth': []
        }

        # 筛选同比增长率数据（INTERFACE_TYPE=100.0）
        yoy_data = df[df.get('INTERFACE_TYPE', 0) == 100.0]
        recent_data = yoy_data.head(8)

        for _, row in recent_data.iterrows():
            report_date = row['REPORT_DATE']
            analysis['revenue_growth'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('TOTAL_OPERATE_INCOME', 0))
            })
            analysis['profit_growth'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('NETPROFIT', 0))
            })
            analysis['asset_growth'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('TOTAL_ASSETS', 0))
            })

        return analysis

    def analyze_main_financial(self) -> Dict:
        """分析主要财务指标数据"""
        if self.data['main'] is None:
            return {}

        df = self.data['main']
        analysis = {
            'eps_trend': [],
            'bps_trend': [],
            'roe_trend': [],
            'debt_ratio_trend': []
        }

        recent_data = df.head(8)
        for _, row in recent_data.iterrows():
            report_date = row['REPORT_DATE']
            analysis['eps_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('EPSJB', 0))
            })
            analysis['bps_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('BPS', 0))
            })
            analysis['roe_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('ROEJQ', 0))
            })
            analysis['debt_ratio_trend'].append({
                'date': report_date.strftime('%Y-%m-%d'),
                'value': float(row.get('ZCFZL', 0))
            })

        return analysis

    def generate_comprehensive_analysis(self) -> str:
        """生成综合分析报告"""
        print(f"\n[{self.ticker}] 生成综合财务分析报告...")

        # 分析各类数据
        dupont_analysis = self.analyze_dupont()
        growth_analysis = self.analyze_growth()
        main_analysis = self.analyze_main_financial()

        # 构建分析报告
        company_name_display = self.company_name if self.company_name else "未知公司"
        report = f"# {self.ticker} {company_name_display} 财务数据分析报告\n\n"
        report += f"## 分析时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        
        # 时效性警告
        # 获取最新报告期
        latest_report_date = "2025-09-30"  # 默认值
        if self.data['financial_indicators']:
            # 从现金流数据中获取最新报告期
            cash_flow = self.data['financial_indicators'].get('cash_flow', [])
            if cash_flow:
                sorted_cash = sorted(cash_flow, key=lambda x: x['报告日'], reverse=True)
                if sorted_cash:
                    latest_report_str = sorted_cash[0].get('报告日', '')
                    if latest_report_str:
                        # 转换为日期格式
                        try:
                            latest_report_date = datetime.strptime(latest_report_str, '%Y%m%d').strftime('%Y-%m-%d')
                        except:
                            pass
        report += "## 时效性警告\n"
        report += f"本报告基于截至{latest_report_date}的财务数据，当前为{datetime.now().strftime('%Y-%m-%d')}。\n"
        report += "分析时请考虑时效性对投资决策的影响。\n\n"

        # 公司基本信息（只保留有数据的部分）
        if self.data['company_basic']:
            business_scope = self.data['company_basic'].get('business_scope', '')
            if business_scope:
                report += "## 1. 公司基本信息\n"
                report += "### 经营范围\n"
                report += f"{business_scope}\n\n"
            
            # 添加规模比较数据
            scale_comparison = self.data['company_basic'].get('scale_comparison', [])
            if scale_comparison:
                report += "### 规模比较\n"
                for item in scale_comparison:
                    report += f"- 总市值: {item.get('总市值', 0):.2f}\n"
                    report += f"- 总市值排名: {item.get('总市值排名', 0)}\n"
                    report += f"- 流通市值: {item.get('流通市值', 0):.2f}\n"
                    report += f"- 流通市值排名: {item.get('流通市值排名', 0)}\n"
                    report += f"- 营业收入: {item.get('营业收入', 0):.2f}\n"
                    report += f"- 营业收入排名: {item.get('营业收入排名', 0)}\n"
                    report += f"- 净利润: {item.get('净利润', 0):.2f}\n"
                    report += f"- 净利润排名: {item.get('净利润排名', 0)}\n\n"

        # 财务指标概览
        if self.data['financial_indicators']:
            report += "## 2. 核心财务指标\n"
            
            # 利润指标
            profit_indicators = self.data['financial_indicators'].get('profit_indicators', {})
            if profit_indicators:
                report += "### 盈利能力指标\n"
                if '毛利率' in profit_indicators:
                    report += f"- 毛利率: {profit_indicators['毛利率']}%\n"
                if '净利率' in profit_indicators:
                    report += f"- 净利率: {profit_indicators['净利率']}%\n"
                # 添加原始利润表数据
                profit_table = profit_indicators.get('profit_table', [])
                if profit_table:
                    report += "- 原始数据:\n"
                    # 按报告日排序
                    sorted_profit = sorted(profit_table, key=lambda x: x['报告日'], reverse=True)
                    # 取最近4个报告期
                    recent_profit = sorted_profit[:4]
                    for item in recent_profit:
                        # 转换报告日为日期格式
                        def report_date_to_date(date_str):
                            try:
                                return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                            except:
                                return date_str
                        report_date = report_date_to_date(item['报告日'])
                        revenue = item.get('营业总收入', 0)
                        cost = item.get('营业成本', 0)
                        profit = item.get('净利润', 0)
                        report += f"  - {report_date}(营收={revenue:.2f}, 成本={cost:.2f}, 净利润={profit:.2f})\n"
                report += "\n"
            
            # 负债指标
            debt_indicators = self.data['financial_indicators'].get('debt_indicators', {})
            if debt_indicators:
                report += "### 偿债能力指标\n"
                if '资产负债率' in debt_indicators:
                    report += f"- 资产负债率: {debt_indicators['资产负债率']}%\n"
                if '流动比率' in debt_indicators:
                    report += f"- 流动比率: {debt_indicators['流动比率']}\n"
                # 添加原始资产负债表数据
                balance_table = debt_indicators.get('balance_table', [])
                if balance_table:
                    report += "- 原始数据:\n"
                    # 按报告日排序
                    sorted_balance = sorted(balance_table, key=lambda x: x['报告日'], reverse=True)
                    # 取最近4个报告期
                    recent_balance = sorted_balance[:4]
                    for item in recent_balance:
                        # 转换报告日为日期格式
                        def report_date_to_date(date_str):
                            try:
                                return datetime.strptime(date_str, '%Y%m%d').strftime('%Y-%m-%d')
                            except:
                                return date_str
                        report_date = report_date_to_date(item['报告日'])
                        assets = item.get('资产总计', 0)
                        current_assets = item.get('流动资产合计', 0)
                        current_liabilities = item.get('流动负债合计', 0)
                        non_current_liabilities = item.get('非流动负债合计', 0)
                        total_liabilities = current_liabilities + non_current_liabilities
                        debt_ratio = (total_liabilities / assets * 100) if assets > 0 else 0
                        current_ratio = current_assets / current_liabilities if current_liabilities > 0 else 0
                        report += f"  - {report_date}(资产={assets:.2f}, 流动资产={current_assets:.2f}, 流动负债={current_liabilities:.2f}, 非流动负债={non_current_liabilities:.2f}, 负债率={debt_ratio:.2f}%, 流动比率={current_ratio:.2f})\n"
                report += "\n"
            
            # 成长指标
            growth_indicators = self.data['financial_indicators'].get('growth_indicators', {})
            if growth_indicators:
                report += "### 成长能力指标\n"
                if '营收增长率' in growth_indicators:
                    report += f"- 营收增长率: {growth_indicators['营收增长率']}%\n"
                if '净利润增长率' in growth_indicators:
                    report += f"- 净利润增长率: {growth_indicators['净利润增长率']}%\n"
                if '总资产增长率' in growth_indicators:
                    report += f"- 总资产增长率: {growth_indicators['总资产增长率']}%\n"
                report += "\n"
            
            # 现金流指标
            cash_flow = self.data['financial_indicators'].get('cash_flow', [])
            if cash_flow:
                report += "### 现金流指标\n"
                # 按报告日排序
                sorted_cash = sorted(cash_flow, key=lambda x: x['报告日'], reverse=True)
                # 取最近四个季度的数据
                recent_cash = sorted_cash[:4]
                # 最新数据
                current_cash = recent_cash[0]
                operating_cash_flow = current_cash.get('经营活动产生的现金流量净额', 0)
                revenue = current_cash.get('经营活动现金流入小计', 0)
                if revenue > 0:
                    operating_cash_ratio = (operating_cash_flow / revenue) * 100
                    report += f"- 经营活动现金流量净额: {operating_cash_flow:.2f}\n"
                    report += f"- 经营现金流/营收: {operating_cash_ratio:.2f}%\n"
                else:
                    report += f"- 经营活动现金流量净额: {operating_cash_flow:.2f}\n"
                    report += "- 经营现金流/营收: 数据不足\n"
                # 添加最近四个季度的原始数据
                report += "- 原始数据:\n"
                for i, cash_data in enumerate(recent_cash):
                    # 转换报告日为日期格式
                    report_date_str = cash_data.get('报告日', '')
                    try:
                        report_date = datetime.strptime(report_date_str, '%Y%m%d').strftime('%Y-%m-%d')
                    except:
                        report_date = report_date_str
                    cash_inflow = cash_data.get('经营活动现金流入小计', 0)
                    cash_outflow = cash_data.get('经营活动现金流出小计', 0)
                    net_cash = cash_data.get('经营活动产生的现金流量净额', 0)
                    report += f"  - {report_date}(经营活动现金流入={cash_inflow:.2f}, 经营活动现金流出={cash_outflow:.2f}, 净额={net_cash:.2f})\n"
                report += "\n"

        # 3. 杜邦分析
        if dupont_analysis:
            report += "## 3. 杜邦分析\n"
            report += "### ROE趋势分析\n"
            for item in dupont_analysis['roe_trend']:
                report += f"- {item['date']}: {item['value']:.2f}%\n"
            report += "\n"

            report += "### 盈利能力分析\n"
            for item in dupont_analysis['profit_margin_trend']:
                report += f"- {item['date']}: {item['value']:.2f}%\n"
            report += "\n"

            report += "### 运营效率分析\n"
            for item in dupont_analysis['asset_turnover_trend']:
                report += f"- {item['date']}: {item['value']:.2f}\n"
            report += "\n"

            report += "### 财务杠杆分析\n"
            for item in dupont_analysis['equity_multiplier_trend']:
                report += f"- {item['date']}: {item['value']:.2f}\n"
            report += "\n"

        # 4. 主要财务指标分析
        if main_analysis:
            report += "## 4. 主要财务指标分析\n"
            report += "### 每股收益(EPS)趋势\n"
            for item in main_analysis['eps_trend']:
                report += f"- {item['date']}: {item['value']:.4f}\n"
            report += "\n"

            report += "### 每股净资产(BPS)趋势\n"
            for item in main_analysis['bps_trend']:
                report += f"- {item['date']}: {item['value']:.2f}\n"
            report += "\n"

            report += "### 净资产收益率(ROE)趋势\n"
            for item in main_analysis['roe_trend']:
                report += f"- {item['date']}: {item['value']:.2f}%\n"
            report += "\n"

            report += "### 资产负债率趋势\n"
            for item in main_analysis['debt_ratio_trend']:
                report += f"- {item['date']}: {item['value']:.2f}%\n"
            report += "\n"

        # 5. 综合评估
        report += "## 5. 综合评估\n"
        report += "### 财务健康度评估\n"
        report += "- 盈利能力: 基于销售净利率和ROE趋势分析\n"
        report += "- 成长能力: 基于营收和净利润增长率\n"
        report += "- 运营效率: 基于资产周转率\n"
        report += "- 偿债能力: 基于资产负债率和权益乘数\n"
        report += "\n"

        report += "### 投资建议\n"
        report += "- 基于财务数据分析的投资建议\n"
        report += "- 风险评估和资金管理建议\n"
        report += "- 请重点关注ROE下降原因及增长率与EPS增长不匹配的矛盾\n"

        return report

    def get_ai_analysis(self, analysis_report: str) -> str:
        """获取AI分析结果"""
        try:
            import ollama
            
            company_name_display = self.company_name if self.company_name else "未知公司"
            
            # 获取最新报告期
            latest_report_date = "2025-09-30"  # 默认值
            if self.data['financial_indicators']:
                # 从现金流数据中获取最新报告期
                cash_flow = self.data['financial_indicators'].get('cash_flow', [])
                if cash_flow:
                    sorted_cash = sorted(cash_flow, key=lambda x: x['报告日'], reverse=True)
                    if sorted_cash:
                        latest_report_str = sorted_cash[0].get('报告日', '')
                        if latest_report_str:
                            # 转换为日期格式
                            try:
                                latest_report_date = datetime.strptime(latest_report_str, '%Y%m%d').strftime('%Y-%m-%d')
                            except:
                                pass
            
            prompt = f"""你是一位量化投资分析师。基于以下{company_name_display}({self.ticker})的财务数据（最新财报日期：{latest_report_date}），请按7点要求分析。

{analysis_report}

=== 分析要求（请逐条回答） ===
1. 综合分析公司的盈利能力、运营能力、偿债能力和成长能力
2. 计算并分析关键财务指标的变化趋势和同比/环比变化（如EPS同比变化、净利率环比变化等）
3. 评估公司的财务健康状况和发展趋势
4. 基于财务数据分析，评估股票的投资价值和风险
5. 与同行业公司相比，该公司的财务表现如何。由于未提供行业平均数据，请基于公开信息或常识进行定性对比，并注明不确定性。
6. 基于财务数据分析，给出具体的投资建议（买入/持有/卖出）
7. 风险评估和资金管理建议

=== 特别注意 ===
1. 请指出数据中的矛盾或不一致之处，特别是高增长率与ROE、EPS增长不匹配的问题
2. 请基于数据进行量化分析，避免泛泛而谈
3. 请在分析中使用正确的公司名称，不要猜测其他公司名称
4. 请考虑数据时效性对投资决策的影响"""

            # 保存提示词到本地文件
            os.makedirs(self.stock_dir, exist_ok=True)
            timestamp = datetime.now().strftime('%Y%m%d')
            prompt_filename = f"{self.ticker}_em_financial_analysis_prompt_{timestamp}.txt"
            prompt_file_path = os.path.join(self.stock_dir, prompt_filename)
            
            with open(prompt_file_path, 'w', encoding='utf-8') as f:
                f.write(prompt)
            
            print(f"提示词已保存到: {prompt_file_path}")

            print(f"正在请求本地Ollama AI ({AI_CONFIG['model']})...")
            client = ollama.Client(host=AI_CONFIG['base_url'])
            
            response = client.chat(
                model=AI_CONFIG['model'],
                messages=[
                    {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从财务角度分析股票的投资价值。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": AI_CONFIG['temperature'],
                    "max_tokens": AI_CONFIG['max_tokens']
                }
            )
            
            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {e}")
            return "无法获取AI分析，请检查Ollama服务是否正常运行。"

    def save_analysis_result(self, analysis_content: str):
        """保存分析结果"""
        os.makedirs(self.stock_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_em_financial_analysis_{timestamp}.md"
        file_path = os.path.join(self.stock_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(analysis_content)
        
        print(f"分析报告已保存到: {file_path}")
        return file_path

    def analyze(self):
        """执行完整分析流程"""
        print(f"\n{'='*60}")
        print(f"开始分析 {self.ticker} 的股票财务数据")
        print(f"{'='*60}")

        # 加载数据
        if not self.load_data():
            print("没有找到任何财务数据，分析终止")
            return

        # 预处理数据
        self.preprocess_data()

        # 生成综合分析
        comprehensive_report = self.generate_comprehensive_analysis()

        # 获取AI分析
        ai_analysis = self.get_ai_analysis(comprehensive_report)

        # 合并分析结果
        # final_report = comprehensive_report + "\n## 5. AI深度分析\n" + ai_analysis
        final_report = ai_analysis
        # 保存分析结果
        self.save_analysis_result(final_report)

        print(f"\n{'='*60}")
        print(f"{self.ticker} 财务数据分析完成")
        print(f"{'='*60}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='分析财务数据')
    parser.add_argument('--ticker', type=str, required=True, 
                       help='股票代码，例如：300433.SZ')
    args = parser.parse_args()
    
    analyzer = EastmoneyFinancialAnalyzer(args.ticker)
    analyzer.analyze()


if __name__ == "__main__":
    main()
