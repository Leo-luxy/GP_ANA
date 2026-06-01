# financial_structured_analyzer.py
"""
财务结构化摘要生成器
功能：整合多源财务数据，计算关键指标，生成标准化JSON摘要
特点：
1. 整合杜邦分析、增长率、财务报表、行业信息等数据源
2. 计算增长能力、盈利能力、偿债能力、现金流质量等指标
3. 检测异常情况（盈利恶化、现金流背离、债务风险等）
4. 生成BULLISH/NEUTRAL/BEARISH信号
5. 输出标准JSON格式，供多智能体决策系统使用
"""

import json
import os
import sys
import pandas as pd
from datetime import datetime
from typing import Dict, Optional, Any, List

# 添加父目录到路径
import os
import sys
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 加载申万阈值配置
from shenwan_config import get_shenwan_thresholds, ShenwanIndustryThresholds

# 加载项目配置（使用别名避免与config包冲突）
import importlib.util
config_spec = importlib.util.spec_from_file_location("project_config", 
    os.path.join(project_root, 'config.py'))
project_config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(project_config)
DATA_DIR = project_config.DATA_DIR
AI_CONFIG = project_config.AI_CONFIG


class FinancialStructuredAnalyzer:
    """财务数据加载与结构化摘要生成器"""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'dupont': None,
            'growth': None,
            'main': None,
            'company_basic': None,
            'financial_indicators': None,
            'financial_profit': None,
            'financial_balance': None,
            'financial_indicators_calculated': None,
            'industry_info': None,
            'qfq': None,
            'valuation': None
        }
        self.company_name = None
        self.calculated_metrics = {}
        self.anomalies = []
        self.risk_tags = []
        self.shenwan_manager = get_shenwan_thresholds()
        self.industry_thresholds = None

    # ---------- 数据加载 ----------
    def load_all_data(self) -> bool:
        """加载所有可用的财务数据"""
        print(f"[{self.ticker}] 开始加载财务数据...")

        # 1) 公司基本信息
        self._load_json('company_basic', f"{self.ticker}_company_basic.json", 'company_basic')

        # 2) 财务指标（东方财富）
        self._load_json('financial_indicators', f"{self.ticker}_financial_indicators.json")

        # 3) 杜邦分析
        self._load_csv('dupont', f"{self.ticker}_dupont_data.csv")

        # 4) 增长率
        self._load_csv('growth', f"{self.ticker}_growth_ratio_data.csv")

        # 5) 主要财务指标
        self._load_csv('main', f"{self.ticker}_main_financial_data.csv")

        # 6) 利润表
        self._load_csv('financial_profit', f"{self.ticker}_financial_profit.csv")

        # 7) 资产负债表
        self._load_csv('financial_balance', f"{self.ticker}_financial_balance.csv")

        # 8) 计算后的财务指标
        self._load_json('financial_indicators_calculated',
                        f"{self.ticker}_financial_indicators_calculated.json")

        # 9) 行业信息
        self._load_json('industry_info', f"{self.ticker}_industry_info.json")

        # 10) 行情数据（用于计算估值指标）
        self._load_csv('qfq', f"{self.ticker}_qfq.csv")

        # 11) 估值数据（包含总股本、PE、PB等）
        self._load_csv('valuation', f"{self.ticker}_valuation.csv")

        # 提取公司名称
        self._extract_company_name()

        # 获取申万行业阈值
        self._load_industry_thresholds()

        return any(v is not None for v in self.data.values())

    def _load_industry_thresholds(self):
        """从申万数据加载行业阈值"""
        industry_info = self.data.get('industry_info')
        if not industry_info:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            print(f"  未找到行业信息，使用默认阈值")
            return

        industry_level = industry_info.get('level3_industry', '')

        if not industry_level:
            industry_level = industry_info.get('level1_industry', '')

        if not industry_level:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            print(f"  未找到行业名称，使用默认阈值")
            return

        # 首先尝试精确匹配
        level1_info = self.shenwan_manager.get_level1_industry_info(industry_level)

        # 如果精确匹配失败，尝试使用一级行业名称（板块名称层级的第一部分）
        if not level1_info and 'industry_level' in industry_info:
            industry_full = industry_info.get('industry_level', '')
            if '-' in industry_full:
                level1_name = industry_full.split('-')[0].strip()
                level1_info = self.shenwan_manager.get_level1_industry_info(level1_name)
                if level1_info:
                    print(f"  精确匹配失败，使用一级行业: {level1_name}")

        if level1_info:
            industry_code = level1_info.get('行业代码')
            self.industry_thresholds = self.shenwan_manager.get_industry_thresholds(
                industry_name=level1_info.get('行业名称')
            )
            print(f"  加载申万行业阈值成功: {level1_info.get('行业名称')} ({industry_code})")
            print(f"    PE基准: {self.industry_thresholds.get('pe_medium', 'N/A')}")
            print(f"    PB基准: {self.industry_thresholds.get('pb_medium', 'N/A')}")
        else:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            print(f"  未找到申万行业数据，使用默认阈值")

    def _load_json(self, key: str, filename: str, sub_key: Optional[str] = None):
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = json.load(f)
                self.data[key] = content if sub_key is None else content.get(sub_key, {})
                print(f"  加载 {filename} 成功")
            except Exception as e:
                print(f"  加载 {filename} 失败: {e}")
        else:
            print(f"  文件不存在: {filename}")

    def _load_csv(self, key: str, filename: str):
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                self.data[key] = df
                print(f"  加载 {filename} 成功，{len(df)} 行")
            except Exception as e:
                print(f"  加载 {filename} 失败: {e}")
        else:
            print(f"  文件不存在: {filename}")

    def _extract_company_name(self):
        """从多个来源提取公司名称"""
        if self.data['company_basic'] and 'basic_info' in self.data['company_basic']:
            self.company_name = self.data['company_basic']['basic_info'].get('公司简称', '')
        if not self.company_name and self.data['dupont'] is not None and not self.data['dupont'].empty:
            latest_dupont = self._get_latest_row(self.data['dupont'])
            self.company_name = latest_dupont.get('SECURITY_NAME_ABBR', '') if latest_dupont else ''
        if not self.company_name and self.data['main'] is not None and not self.data['main'].empty:
            latest_main = self._get_latest_row(self.data['main'])
            self.company_name = latest_main.get('SECURITY_NAME_ABBR', '') if latest_main else ''
        if not self.company_name:
            self.company_name = "未知公司"
        print(f"  公司名称: {self.company_name}")

    def _get_latest_row(self, df):
        """从DataFrame获取最新数据行（基于REPORT_DATE列）"""
        if df is None or df.empty:
            return None
        try:
            if 'REPORT_DATE' in df.columns:
                df_sorted = df.sort_values('REPORT_DATE', ascending=False)
                return df_sorted.iloc[0].to_dict()
            else:
                return df.iloc[-1].to_dict()
        except:
            return df.iloc[-1].to_dict()

    # ---------- 指标计算 ----------
    def calculate_all_metrics(self):
        """计算所有关键财务指标"""
        print(f"\n[{self.ticker}] 开始计算财务指标...")
        
        # 增长能力指标
        self._calculate_growth_metrics()
        
        # 盈利能力指标
        self._calculate_profitability_metrics()
        
        # 偿债能力指标
        self._calculate_solvency_metrics()
        
        # 现金流质量指标
        self._calculate_cashflow_metrics()
        
        # 杜邦分析指标
        self._calculate_dupont_metrics()
        
        # 运营能力指标
        self._calculate_operation_metrics()
        
        # 估值指标
        self._calculate_valuation_metrics()
        
        # 检测异常
        self._detect_anomalies()
        
        print(f"  指标计算完成")

    def _calculate_growth_metrics(self):
        """计算增长能力指标"""
        metrics = {}
        
        # 方法1: 优先从financial_indicators_calculated.json获取同比数据（最准确）
        if self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '成长能力指标' in ci:
                growth_ci = ci['成长能力指标']
                if '净利润同比增长率' in growth_ci:
                    metrics['净利润同比增长率'] = growth_ci['净利润同比增长率']
                if '营收同比增长率' in growth_ci:
                    metrics['营收同比增长率'] = growth_ci['营收同比增长率']
                # 注意：不从这里读取环比数据，自己计算，因为文件中的环比数据可能错误
                # if '营收单季环比增长率' in growth_ci:
                #     metrics['营收单季环比增长率'] = growth_ci['营收单季环比增长率']
                # if '净利润单季环比增长率' in growth_ci:
                #     metrics['净利润单季环比增长率'] = growth_ci['净利润单季环比增长率']
                if '总资产同比增长率' in growth_ci:
                    metrics['总资产同比增长率'] = growth_ci['总资产同比增长率']
                if '净资产同比增长率' in growth_ci:
                    metrics['净资产同比增长率'] = growth_ci['净资产同比增长率']
        
        # 方法2: 从growth_ratio_data.csv的INTERFACE_TYPE=1计算同比和环比（备用/主要方式）
        if self.data['growth'] is not None and not self.data['growth'].empty:
            growth = self.data['growth']
            if 'REPORT_DATE' in growth.columns:
                growth = growth.sort_values('REPORT_DATE', ascending=False)
            
            # 获取绝对数值数据
            absolute_data = growth[growth.get('INTERFACE_TYPE', 0) == 1.0]
            
            # 先计算同比增长率（如果还没有）
            if '净利润同比增长率' not in metrics or '营收同比增长率' not in metrics:
                if not absolute_data.empty:
                    latest_report_name = absolute_data.iloc[0]['REPORT_DATE_NAME']
                    # 获取最近两期相同报告期数据
                    same_period = absolute_data[absolute_data['REPORT_DATE_NAME'] == latest_report_name]
                    
                    if len(same_period) >= 2:
                        same_period = same_period.sort_values('REPORT_DATE', ascending=False)
                        current = same_period.iloc[0]
                        prev = same_period.iloc[1]
                        
                        # 计算营收同比增长率
                        if '营收同比增长率' not in metrics:
                            rev_current = current.get('TOTAL_OPERATE_INCOME')
                            rev_prev = prev.get('TOTAL_OPERATE_INCOME')
                            if rev_prev and rev_prev != 0:
                                try:
                                    rev_growth = (float(rev_current) - float(rev_prev)) / float(rev_prev) * 100
                                    metrics['营收同比增长率'] = round(rev_growth, 2)
                                except:
                                    pass
                        
                        # 计算净利润同比增长率
                        if '净利润同比增长率' not in metrics:
                            prof_current = current.get('NETPROFIT')
                            prof_prev = prev.get('NETPROFIT')
                            if prof_prev and prof_prev != 0:
                                try:
                                    prof_growth = (float(prof_current) - float(prof_prev)) / float(prof_prev) * 100
                                    metrics['净利润同比增长率'] = round(prof_growth, 2)
                                except:
                                    pass
            
            # 计算环比增长率（QoQ）
            # 获取最新报告期名称
            if not absolute_data.empty:
                latest_report_name = absolute_data.iloc[0]['REPORT_DATE_NAME']
                latest = absolute_data.iloc[0]
                
                # 计算环比需要上一季度数据或年报数据
                q1_2026 = absolute_data[absolute_data['REPORT_DATE_NAME'] == '一季报'].iloc[0] if (len(absolute_data[absolute_data['REPORT_DATE_NAME'] == '一季报']) > 0) else None
                annual_2025 = absolute_data[absolute_data['REPORT_DATE_NAME'] == '年报'].iloc[0] if (len(absolute_data[absolute_data['REPORT_DATE_NAME'] == '年报']) > 0) else None
                q3_2025 = absolute_data[absolute_data['REPORT_DATE_NAME'] == '三季报'].iloc[0] if (len(absolute_data[absolute_data['REPORT_DATE_NAME'] == '三季报']) > 0) else None
                
                # 计算Q4 2025 = 年报2025 - 三季报2025
                if q1_2026 is not None and annual_2025 is not None and q3_2025 is not None:
                    # 计算营收环比
                    q4_2025_rev = annual_2025['TOTAL_OPERATE_INCOME'] - q3_2025['TOTAL_OPERATE_INCOME']
                    if q4_2025_rev != 0:
                        rev_qoq = (q1_2026['TOTAL_OPERATE_INCOME'] - q4_2025_rev) / q4_2025_rev * 100
                        metrics['营收单季环比增长率'] = round(rev_qoq, 2)
                    
                    # 计算净利润环比
                    q4_2025_prof = annual_2025['NETPROFIT'] - q3_2025['NETPROFIT']
                    if q4_2025_prof != 0:
                        prof_qoq = (q1_2026['NETPROFIT'] - q4_2025_prof) / q4_2025_prof * 100
                        metrics['净利润单季环比增长率'] = round(prof_qoq, 2)
        
        # 增加环比指标计算
        # 总资产环比增长率
        assets_qoq = self._calculate_assets_growth_qoq()
        if assets_qoq:
            metrics['总资产环比增长率'] = assets_qoq
        
        # 净资产环比增长率
        equity_qoq = self._calculate_equity_growth_qoq()
        if equity_qoq:
            metrics['净资产环比增长率'] = equity_qoq
        
        # 经营现金流环比增长率
        cashflow_qoq = self._calculate_cashflow_growth_qoq()
        if cashflow_qoq:
            metrics['经营现金流环比增长率'] = cashflow_qoq
        
        # 方法3: 如果增长率数据中没有营收增长率，从利润表计算
        if '营收同比增长率' not in metrics or metrics.get('营收同比增长率') == 'N/A':
            revenue_growth = self._calculate_revenue_growth_from_profit()
            if revenue_growth:
                metrics['营收同比增长率'] = revenue_growth
        
        # 方法4: 如果增长率数据中没有净利润增长率，从利润表计算
        if '净利润同比增长率' not in metrics or metrics.get('净利润同比增长率') == 'N/A':
            profit_growth = self._calculate_profit_growth_from_profit()
            if profit_growth:
                metrics['净利润同比增长率'] = profit_growth
        
        # 从东方财富财务指标获取最新EPS
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            profit_table = fi.get('profit_table', [])
            if profit_table:
                latest_profit = sorted(profit_table, key=lambda x: x.get('报告日', '0'), reverse=True)[0]
                eps = latest_profit.get('基本每股收益', 'N/A')
                if eps != 'N/A' and eps is not None:
                    metrics['基本每股收益'] = f"{eps}元"
        
        # 从主要财务指标获取最新数据（补充）
        if self.data['main'] is not None and not self.data['main'].empty:
            latest_main = self._get_latest_row(self.data['main'])
            if latest_main:
                if '基本每股收益' not in metrics:
                    eps_val = latest_main.get('EPSJB', 'N/A')
                    metrics['基本每股收益'] = f"{eps_val}元" if eps_val != 'N/A' else 'N/A元'
                bps_val = latest_main.get('BPS', 'N/A')
                metrics['每股净资产'] = f"{bps_val}元" if bps_val != 'N/A' else 'N/A元'
        
        if metrics:
            self.calculated_metrics['growth'] = metrics
            print(f"  增长能力指标: {metrics}")

    def _calculate_revenue_growth_from_profit(self):
        """从利润表计算同比营收增长率"""
        if self.data['financial_profit'] is None or self.data['financial_profit'].empty:
            return None
        
        df = self.data['financial_profit'].copy()
        df['报告日'] = df['报告日'].astype(str)
        
        # 获取最新季度数据
        latest = df.iloc[-1]
        latest_date = latest['报告日']
        latest_revenue = latest.get('营业总收入', 0)
        
        # 计算去年同期日期
        if len(latest_date) == 8:
            last_year_date = str(int(latest_date[:4]) - 1) + latest_date[4:]
        else:
            return None
        
        # 查找去年同期数据
        last_year_data = df[df['报告日'] == last_year_date]
        if last_year_data.empty:
            return None
        
        last_year_revenue = last_year_data.iloc[0].get('营业总收入', 0)
        
        if last_year_revenue == 0:
            return None
        
        growth_rate = (latest_revenue - last_year_revenue) / last_year_revenue * 100
        return f"{growth_rate:.2f}%"

    def _calculate_profit_growth_from_profit(self):
        """从利润表计算同比净利润增长率"""
        if self.data['financial_profit'] is None or self.data['financial_profit'].empty:
            return None
        
        df = self.data['financial_profit'].copy()
        df['报告日'] = df['报告日'].astype(str)
        
        # 获取最新季度数据
        latest = df.iloc[-1]
        latest_date = latest['报告日']
        latest_profit = latest.get('净利润', 0)
        
        # 计算去年同期日期
        if len(latest_date) == 8:
            last_year_date = str(int(latest_date[:4]) - 1) + latest_date[4:]
        else:
            return None
        
        # 查找去年同期数据
        last_year_data = df[df['报告日'] == last_year_date]
        if last_year_data.empty:
            return None
        
        last_year_profit = last_year_data.iloc[0].get('净利润', 0)
        
        if last_year_profit == 0:
            return None
        
        growth_rate = (latest_profit - last_year_profit) / abs(last_year_profit) * 100
        return f"{growth_rate:.2f}%"

    def _calculate_assets_growth_qoq(self):
        """从资产负债表计算总资产环比增长率"""
        if self.data['financial_balance'] is None or self.data['financial_balance'].empty:
            return None
        
        df = self.data['financial_balance'].copy()
        df['报告日'] = df['报告日'].astype(str)
        
        # 按日期排序
        df_sorted = df.sort_values('报告日', ascending=False)
        
        # 获取最近两个季度数据
        if len(df_sorted) < 2:
            return None
        
        latest = df_sorted.iloc[0]
        previous = df_sorted.iloc[1]
        
        latest_assets = latest.get('资产总计', 0)
        previous_assets = previous.get('资产总计', 0)
        
        if previous_assets == 0:
            return None
        
        growth_rate = (latest_assets - previous_assets) / previous_assets * 100
        return growth_rate

    def _calculate_equity_growth_qoq(self):
        """从资产负债表计算净资产环比增长率"""
        if self.data['financial_balance'] is None or self.data['financial_balance'].empty:
            return None
        
        df = self.data['financial_balance'].copy()
        df['报告日'] = df['报告日'].astype(str)
        
        # 按日期排序
        df_sorted = df.sort_values('报告日', ascending=False)
        
        # 获取最近两个季度数据
        if len(df_sorted) < 2:
            return None
        
        latest = df_sorted.iloc[0]
        previous = df_sorted.iloc[1]
        
        latest_equity = latest.get('所有者权益(或股东权益)合计', 0)
        if latest_equity == 0:
            latest_equity = latest.get('归属于母公司股东权益合计', 0)
        
        previous_equity = previous.get('所有者权益(或股东权益)合计', 0)
        if previous_equity == 0:
            previous_equity = previous.get('归属于母公司股东权益合计', 0)
        
        if previous_equity == 0:
            return None
        
        growth_rate = (latest_equity - previous_equity) / previous_equity * 100
        return growth_rate

    def _calculate_cashflow_growth_qoq(self):
        """计算经营现金流环比增长率 - 正确计算单季度数据"""
        # 需要从growth_ratio_data.csv获取累计数据来计算单季度
        if self.data.get('growth') is None or self.data['growth'].empty:
            return None
        
        growth = self.data['growth']
        absolute = growth[growth.get('INTERFACE_TYPE', 0) == 1.0]
        if absolute.empty:
            return None
        
        absolute = absolute.sort_values('REPORT_DATE', ascending=False)
        
        # 找到最新一季报、年报、三季报的数据
        q1 = absolute[absolute['REPORT_DATE_NAME'] == '一季报']
        annual = absolute[absolute['REPORT_DATE_NAME'] == '年报']
        q3 = absolute[absolute['REPORT_DATE_NAME'] == '三季报']
        
        if len(q1) == 0 or len(annual) == 0 or len(q3) == 0:
            return None
        
        # 计算2025Q4 = 2025年报 - 2025三季报
        latest_q1 = q1.iloc[0]
        latest_annual = annual.iloc[0]
        latest_q3 = q3.iloc[0]
        
        cashflow_q1 = latest_q1.get('经营活动现金流净额', None)
        cashflow_annual = latest_annual.get('经营活动现金流净额', None)
        cashflow_q3 = latest_q3.get('经营活动现金流净额', None)
        
        # 从growth_data.csv中查找正确的字段名
        for col in absolute.columns:
            if '经营活动' in col and '现金流' in col and '净额' in col:
                cashflow_q1 = latest_q1.get(col, None)
                cashflow_annual = latest_annual.get(col, None)
                cashflow_q3 = latest_q3.get(col, None)
                break
        
        # 如果还是找不到，从financial_indicators_calculated.json中查找
        if (cashflow_q1 is None or cashflow_annual is None or cashflow_q3 is None) and self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '现金流指标' in ci:
                cashflow_q1 = ci['现金流指标'].get('经营活动现金流量净额', None)
        
        # 如果都没有，从financial_indicators.json中查找并计算
        if (cashflow_q1 is None or cashflow_annual is None or cashflow_q3 is None) and self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            cash_list = fi.get('cash_flow', [])
            if len(cash_list) >= 3:
                cash_sorted = sorted(cash_list, key=lambda x: x.get('报告日', '0'), reverse=True)
                # cash_sorted[0] = 2026Q1, cash_sorted[1] = 2025年报, cash_sorted[2] = 2025Q3
                cashflow_q1 = cash_sorted[0].get('经营活动产生的现金流量净额', None)
                cashflow_annual = cash_sorted[1].get('经营活动产生的现金流量净额', None)
                cashflow_q3 = cash_sorted[2].get('经营活动产生的现金流量净额', None)
        
        # 计算单季度现金流
        try:
            if (cashflow_q1 is not None and cashflow_annual is not None and cashflow_q3 is not None and
                cashflow_q1 != 'N/A' and cashflow_annual != 'N/A' and cashflow_q3 != 'N/A'):
                
                # 计算2025Q4 = 2025年报 - 2025三季报
                q4_cashflow = float(cashflow_annual) - float(cashflow_q3)
                
                if q4_cashflow != 0:
                    qoq = (float(cashflow_q1) - q4_cashflow) / abs(q4_cashflow) * 100
                    return qoq
        except:
            pass
        
        return None


    def _calculate_profitability_metrics(self):
        """计算盈利能力指标"""
        metrics = {}
        
        # 从杜邦分析获取最新数据
        if self.data['dupont'] is not None and not self.data['dupont'].empty:
            latest_dupont = self._get_latest_row(self.data['dupont'])
            if latest_dupont:
                metrics['ROE'] = f"{latest_dupont.get('ROE', 'N/A')}%"
                metrics['销售净利率'] = f"{latest_dupont.get('SALE_NPR', 'N/A')}%"
                metrics['资产周转率'] = f"{latest_dupont.get('TOTAL_ASSETS_TR', 'N/A')}"
                metrics['权益乘数'] = f"{latest_dupont.get('EQUITY_MULTIPLIER', 'N/A')}"
        
        # 从主要财务指标获取最新数据
        if self.data['main'] is not None and not self.data['main'].empty:
            latest_main = self._get_latest_row(self.data['main'])
            if latest_main:
                metrics['ROE(加权)'] = f"{latest_main.get('ROEJQ', 'N/A')}%"
        
        # 从东方财富财务指标获取
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            profit = fi.get('profit_indicators', {})
            if profit:
                metrics['毛利率'] = f"{profit.get('毛利率', 'N/A')}%"
                metrics['净利率'] = f"{profit.get('净利率', 'N/A')}%"
            
            # 获取最新EPS
            profit_table = fi.get('profit_table', [])
            if profit_table:
                latest_profit = sorted(profit_table, key=lambda x: x.get('报告日', '0'), reverse=True)[0]
                eps = latest_profit.get('基本每股收益', 'N/A')
                if eps != 'N/A' and eps is not None:
                    metrics['基本每股收益'] = f"{eps}元"
        
        # 从计算后的指标获取
        if self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '盈利能力指标' in ci:
                for k, v in ci['盈利能力指标'].items():
                    if k in ['毛利率', '净利率', '营业利润率']:
                        metrics[k] = f"{v}%"
                    elif k in ['基本每股收益', '稀释每股收益']:
                        metrics[k] = f"{v}元"
                    else:
                        metrics[k] = str(v)
        
        if metrics:
            self.calculated_metrics['profitability'] = metrics
            print(f"  盈利能力指标: {metrics}")

    def _calculate_solvency_metrics(self):
        """计算偿债能力指标"""
        metrics = {}
        
        # 从主要财务指标获取最新数据
        if self.data['main'] is not None and not self.data['main'].empty:
            latest_main = self._get_latest_row(self.data['main'])
            if latest_main:
                zcfzl = latest_main.get('ZCFZL', 'N/A')
                metrics['资产负债率'] = f"{zcfzl}%" if zcfzl != 'N/A' else 'N/A'
        
        # 从东方财富财务指标获取
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            debt = fi.get('debt_indicators', {})
            if debt:
                cr = debt.get('流动比率', 'N/A')
                metrics['流动比率'] = f"{cr}%" if cr != 'N/A' else 'N/A'
                
                # 如果没有速动比率，尝试从资产负债表计算
                qr = debt.get('速动比率', None)
                if qr:
                    metrics['速动比率'] = f"{qr}%"
                else:
                    metrics['速动比率'] = self._calculate_quick_ratio()
        
        # 从计算后的指标获取
        if self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '偿债能力指标' in ci:
                for k, v in ci['偿债能力指标'].items():
                    if v != 'N/A' and v is not None:
                        if '率' in k:
                            metrics[k] = f"{v}%"
                        else:
                            metrics[k] = str(v)
        
        if metrics:
            self.calculated_metrics['solvency'] = metrics
            print(f"  偿债能力指标: {metrics}")

    def _calculate_quick_ratio(self):
        """从资产负债表计算速动比率 = (流动资产 - 存货) / 流动负债"""
        # 首先尝试从 financial_balance.csv 获取数据
        if self.data['financial_balance'] is not None and not self.data['financial_balance'].empty:
            latest_balance = self._get_latest_row(self.data['financial_balance'])
            if latest_balance:
                current_assets = latest_balance.get('流动资产合计', 0)
                inventory = latest_balance.get('存货', 0)
                current_liabilities = latest_balance.get('流动负债合计', 0)
                
                if current_liabilities != 0 and current_assets != 0:
                    quick_ratio = (current_assets - inventory) / current_liabilities
                    return f"{quick_ratio:.2f}%"
        
        # 尝试从 financial_indicators 的 balance_table 获取数据（备用）
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            balance_table = fi.get('balance_table', [])
            if balance_table:
                latest_balance = sorted(balance_table, key=lambda x: x.get('报告日', '0'), reverse=True)[0]
                current_assets = latest_balance.get('流动资产合计', 0)
                inventory = latest_balance.get('存货', 0)
                current_liabilities = latest_balance.get('流动负债合计', 0)
                
                if current_liabilities != 0 and current_assets != 0:
                    quick_ratio = (current_assets - inventory) / current_liabilities
                    return f"{quick_ratio:.2f}%"
        
        return 'N/A'

    def _calculate_cashflow_metrics(self):
        """计算现金流质量指标"""
        metrics = {}
        
        # 从东方财富财务指标获取现金流
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            cash_list = fi.get('cash_flow', [])
            
            if cash_list:
                latest_cash = sorted(cash_list, key=lambda x: x.get('报告日', '0'), reverse=True)[0]
                oc_net = latest_cash.get('经营活动产生的现金流量净额', 0)
                
                # 从main_financial_data.csv获取营业总收入
                operating_revenue = 1
                if self.data['main'] is not None and not self.data['main'].empty:
                    latest_main = self._get_latest_row(self.data['main'])
                    if latest_main:
                        operating_revenue = latest_main.get('TOTALOPERATEREVE', 1)
                        if operating_revenue is None or operating_revenue == 0:
                            operating_revenue = 1
                
                metrics['经营活动现金流净额'] = f"{oc_net:.2f}元"
                if operating_revenue != 0 and operating_revenue != 1:
                    metrics['现金流/营收比'] = f"{(oc_net / operating_revenue * 100):.2f}%"
        
        # 从计算后的指标获取
        if self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '现金流指标' in ci:
                for k, v in ci['现金流指标'].items():
                    if '率' in k:
                        metrics[k] = f"{v}"
                    else:
                        metrics[k] = str(v)
        
        if metrics:
            self.calculated_metrics['cashflow'] = metrics
            print(f"  现金流指标: {metrics}")

    def _calculate_dupont_metrics(self):
        """计算杜邦分析指标"""
        metrics = {}
        
        if self.data['dupont'] is not None and not self.data['dupont'].empty:
            latest_dupont = self._get_latest_row(self.data['dupont'])
            if latest_dupont:
                metrics['dupont_roe'] = f"{latest_dupont.get('ROE', 'N/A')}%"
                metrics['dupont_sale_npr'] = f"{latest_dupont.get('SALE_NPR', 'N/A')}%"
                metrics['dupont_assets_tr'] = f"{latest_dupont.get('TOTAL_ASSETS_TR', 'N/A')}"
                metrics['dupont_equity_multiplier'] = f"{latest_dupont.get('EQUITY_MULTIPLIER', 'N/A')}"
                
                # ROE拆解分析
                roe_val = float(latest_dupont.get('ROE', 0))
                if roe_val > 15:
                    metrics['dupont_assessment'] = '优秀（ROE超过15%，股东回报良好）'
                elif roe_val > 10:
                    metrics['dupont_assessment'] = '良好（ROE在10%-15%之间）'
                elif roe_val > 5:
                    metrics['dupont_assessment'] = '一般（ROE在5%-10%之间）'
                elif roe_val >= 0:
                    metrics['dupont_assessment'] = '较差（ROE低于5%）'
                else:
                    metrics['dupont_assessment'] = '亏损（ROE为负）'
        
        if metrics:
            self.calculated_metrics['dupont'] = metrics
            print(f"  杜邦分析指标: {metrics}")

    def _calculate_operation_metrics(self):
        """计算运营能力指标 - 从financial_indicators.json中正确获取"""
        metrics = {}
        
        # 优先从financial_indicators.json的营运能力指标中获取
        if self.data.get('financial_indicators'):
            fi = self.data['financial_indicators']
            
            # 查找financial_analysis数组中的营运能力指标
            if isinstance(fi, dict) and 'financial_analysis' in fi and isinstance(fi['financial_analysis'], list):
                for item in fi['financial_analysis']:
                    if isinstance(item, dict) and item.get('选项') == '营运能力':
                        indicator = item.get('指标', '')
                        # 查找20260331的数据
                        value = item.get('20260331', None)
                        if value is not None:
                            if indicator == '应收账款周转率':
                                metrics['应收账款周转率'] = round(float(value), 2)
                            elif indicator == '存货周转率':
                                metrics['存货周转率'] = round(float(value), 2)
                            elif indicator == '总资产周转率':
                                metrics['总资产周转率'] = round(float(value), 2)
        
        # 如果还缺数据，从financial_indicators_calculated.json获取
        if not metrics or len(metrics) < 3:
            if self.data.get('financial_indicators_calculated'):
                calc = self.data['financial_indicators_calculated']
                ci = calc.get('calculated_indicators', {})
                if '运营能力指标' in ci:
                    op_ci = ci['运营能力指标']
                    for k, v in op_ci.items():
                        if k not in metrics and k != '固定资产周转率':
                            metrics[k] = v
        
        # 从main_financial_data.csv获取固定资产周转率，或者计算年化的
        if self.data.get('main') is not None and not self.data['main'].empty:
            latest_main = self._get_latest_row(self.data['main'])
            if latest_main:
                # 首先尝试获取固定资产周转率
                fixed_asset_tr = latest_main.get('FIXED_ASSET_TR', None)
                # 获取营业收入
                revenue = latest_main.get('TOTALOPERATEREVE', None)
                
                if fixed_asset_tr is not None:
                    # 固定资产周转率已经存在，但需要乘以4来年化
                    try:
                        assets_tr = float(fixed_asset_tr) * 4
                        metrics['固定资产周转率'] = round(assets_tr, 2)
                    except:
                        pass
        
        if metrics:
            self.calculated_metrics['operation'] = metrics
            print(f"  运营能力指标: {metrics}")


    def _calculate_valuation_metrics(self):
        """获取估值指标 - 直接从valuation.csv读取"""
        metrics = {}
        
        # 优先从估值数据文件读取（最可靠）
        if self.data['valuation'] is not None and not self.data['valuation'].empty:
            latest_val = self.data['valuation'].iloc[-1]
            # 读取关键估值指标
            if 'PE(TTM)' in self.data['valuation'].columns:
                pe = latest_val.get('PE(TTM)', None)
                if pe is not None and pe != 'N/A' and pe != 'nan':
                    metrics['PE(TTM)'] = f"{pe:.2f}"
            
            if '市净率' in self.data['valuation'].columns:
                pb = latest_val.get('市净率', None)
                if pb is not None and pb != 'N/A' and pb != 'nan':
                    metrics['PB'] = f"{pb:.2f}"
            
            if 'PEG值' in self.data['valuation'].columns:
                peg = latest_val.get('PEG值', None)
                if peg is not None and peg != 'N/A' and peg != 'nan':
                    metrics['PEG'] = f"{peg:.2f}"
            
            if '市现率' in self.data['valuation'].columns:
                pcf = latest_val.get('市现率', None)
                if pcf is not None and pcf != 'N/A' and pcf != 'nan':
                    metrics['PCF'] = f"{pcf:.2f}"
            
            if '市销率' in self.data['valuation'].columns:
                ps = latest_val.get('市销率', None)
                if ps is not None and ps != 'N/A' and ps != 'nan':
                    metrics['PS'] = f"{ps:.2f}"
        
        # 备用：从行业信息获取估值数据
        if not metrics and self.data.get('industry_info') and 'industry_average' in self.data['industry_info']:
            ia = self.data['industry_info']['industry_average']
            for k, v in ia.items():
                if 'PE' in k or 'PB' in k or 'PS' in k or 'PEG' in k:
                    metrics[k] = str(v)
        
        # 备用：从计算后的指标获取
        if not metrics and self.data.get('financial_indicators_calculated'):
            calc = self.data['financial_indicators_calculated']
            ci = calc.get('calculated_indicators', {})
            if '估值指标' in ci:
                for k, v in ci['估值指标'].items():
                    metrics[k] = str(v)
        
        if metrics:
            self.calculated_metrics['valuation'] = metrics
            print(f"  估值指标: {metrics}")

    def _calculate_pe_ttm(self):
        """计算PE(TTM) = 市值 / TTM净利润"""
        # 优先从估值数据获取总股本和收盘价
        if self.data['valuation'] is not None and not self.data['valuation'].empty:
            latest_val = self.data['valuation'].iloc[-1]
            total_shares = latest_val.get('总股本', 0)
            close_price = latest_val.get('当日收盘价', 0)
        elif self.data['qfq'] is not None and not self.data['qfq'].empty:
            # 备用：从行情数据获取
            latest_qfq = self.data['qfq'].iloc[-1]
            total_shares = latest_qfq.get('outstanding_share', 0)
            close_price = latest_qfq.get('close', 0)
        else:
            return None
        
        if total_shares == 0 or close_price == 0:
            return None
        
        # 计算市值
        market_cap = close_price * total_shares
        
        # 计算TTM净利润（最近4个季度）
        ttm_profit = self._calculate_ttm_profit()
        if ttm_profit == 0:
            return None
        
        # 计算PE(TTM)
        pe_ttm = market_cap / ttm_profit
        return f"{pe_ttm:.2f}"

    def _calculate_pb(self):
        """计算PB = 市值 / 股东权益"""
        # 优先从估值数据获取总股本和收盘价
        if self.data['valuation'] is not None and not self.data['valuation'].empty:
            latest_val = self.data['valuation'].iloc[-1]
            total_shares = latest_val.get('总股本', 0)
            close_price = latest_val.get('当日收盘价', 0)
        elif self.data['qfq'] is not None and not self.data['qfq'].empty:
            # 备用：从行情数据获取
            latest_qfq = self.data['qfq'].iloc[-1]
            total_shares = latest_qfq.get('outstanding_share', 0)
            close_price = latest_qfq.get('close', 0)
        else:
            return None
        
        if total_shares == 0 or close_price == 0:
            return None
        
        # 计算市值
        market_cap = close_price * total_shares
        
        # 获取股东权益
        if self.data['financial_balance'] is None or self.data['financial_balance'].empty:
            return None
        
        latest_balance = self._get_latest_row(self.data['financial_balance'])
        if not latest_balance:
            return None
        
        equity = latest_balance.get('归属于母公司股东权益合计', 0)
        if equity == 0:
            return None
        
        # 计算PB
        pb = market_cap / equity
        return f"{pb:.2f}"

    def _calculate_ttm_profit(self):
        """计算TTM净利润（滚动12个月净利润）- 使用归属于母公司所有者的净利润"""
        if self.data['financial_profit'] is None or self.data['financial_profit'].empty:
            return 0
        
        df = self.data['financial_profit'].copy()
        df['报告日'] = df['报告日'].astype(str)
        
        # 按日期排序，取最近4个季度
        df_sorted = df.sort_values('报告日', ascending=False)
        last_4_quarters = df_sorted.head(4)
        
        # 优先使用归属于母公司所有者的净利润（PE(TTM)计算标准）
        if '归属于母公司所有者的净利润' in last_4_quarters.columns:
            ttm_profit = last_4_quarters['归属于母公司所有者的净利润'].sum()
        else:
            ttm_profit = last_4_quarters['净利润'].sum()
        
        return ttm_profit

    def _detect_anomalies(self):
        """检测异常情况并生成风险标签（使用中文字段名）"""
        self.anomalies = []
        self.risk_tags = []
        
        growth = self.calculated_metrics.get('growth', {})
        profitability = self.calculated_metrics.get('profitability', {})
        solvency = self.calculated_metrics.get('solvency', {})
        cashflow = self.calculated_metrics.get('cashflow', {})
        
        # 1. 检测净利润暴跌（超过-100%）
        profit_growth = self._get_numeric_value(growth, '净利润同比增长率')
        if profit_growth is not None:
            if profit_growth < -100:
                self._add_anomaly('利润暴跌', f"净利润同比下滑{abs(profit_growth):.1f}%，超过100%阈值", 'high')
                self._add_risk_tag('盈利恶化')
        
        # 2. 检测营收大幅下滑
        revenue_growth = self._get_numeric_value(growth, '营收同比增长率')
        if revenue_growth is not None:
            if revenue_growth < -30:
                self._add_anomaly('营收大幅下滑', f"营收同比下降{abs(revenue_growth):.1f}%，超过30%阈值", 'medium')
        
        # 3. 检测极端环比异常
        revenue_qoq = self._get_numeric_value(growth, '营收单季环比增长率')
        if revenue_qoq is not None:
            if abs(revenue_qoq) > 100:
                self._add_anomaly('营收环比异常', f"营收单季环比{revenue_qoq:.1f}%，波动超过100%，建议核实数据", 'high')
                self._add_risk_tag('数据异常')
        
        # 4. 检测ROE为负
        roe = self._get_numeric_value(profitability, 'ROE')
        if roe is not None:
            if roe < 0:
                self._add_anomaly('ROE为负', f"ROE为{roe:.2f}%，股东权益回报为负", 'high')
                self._add_risk_tag('ROE为负')
        
        # 5. 检测净利率为负
        net_margin = self._get_numeric_value(profitability, '净利率')
        if net_margin is not None:
            if net_margin < 0:
                self._add_anomaly('净利率为负', f"净利率为{net_margin:.2f}%，处于亏损状态", 'high')
                self._add_risk_tag('净利率为负')
        
        # 6. 检测利息保障倍数异常
        interest_coverage = self._get_numeric_value(solvency, '利息保障倍数')
        if interest_coverage is not None:
            if interest_coverage < 1:
                self._add_anomaly('利息覆盖不足', f"利息保障倍数{interest_coverage:.2f}，无法覆盖利息支出", 'high')
                self._add_risk_tag('财务风险')
        
        # 7. 检测流动性风险（速动比率<1）
        quick_ratio = self._get_numeric_value(solvency, '速动比率')
        if quick_ratio is not None:
            if quick_ratio < 1.0:
                self._add_anomaly('流动性风险', f"速动比率{quick_ratio:.2f}，低于1的警戒线", 'medium')
                self._add_risk_tag('流动性风险')
        
        # 8. 检测流动比率偏低
        current_ratio = self._get_numeric_value(solvency, '流动比率')
        if current_ratio is not None:
            if current_ratio < 1.2:
                self._add_anomaly('流动比率偏低', f"流动比率{current_ratio:.2f}，短期偿债能力承压", 'low')
        
        # 9. 检测现金流质量差
        cash_quality = cashflow.get('现金流质量', '')
        if cash_quality and 'weak' in cash_quality.lower():
            self._add_anomaly('现金流恶化', '经营现金流不足，盈利现金含量低', 'medium')
            self._add_risk_tag('现金流恶化')
        
        # 10. 检测高负债风险
        debt_ratio = self._get_numeric_value(solvency, '资产负债率')
        if debt_ratio is not None:
            if debt_ratio > 70:
                self._add_anomaly('高负债', f"资产负债率{debt_ratio:.1f}%，超过70%警戒线", 'high')
                self._add_risk_tag('高负债')
        
        # 11. 检测增长失速（净利润环比大幅下滑）
        profit_qoq = self._get_numeric_value(growth, '净利润单季环比增长率')
        if profit_qoq is not None:
            if profit_qoq < -50:
                self._add_anomaly('增长失速', f"净利润单季环比下降{abs(profit_qoq):.1f}%", 'medium')
                self._add_risk_tag('增长失速')
    
    def _get_numeric_value(self, metrics: dict, key: str):
        """安全地从字典中获取数值"""
        val = metrics.get(key)
        if val is None or val == 'N/A' or val == '':
            return None
        try:
            # 处理带%的字符串
            if isinstance(val, str):
                val = val.replace('%', '').strip()
            return float(val)
        except:
            return None
    
    def _add_anomaly(self, anomaly_type: str, detail: str, severity: str = 'medium'):
        """添加异常记录"""
        self.anomalies.append({
            'type': anomaly_type,
            'detail': detail,
            'severity': severity
        })
    
    def _add_risk_tag(self, tag: str):
        """添加风险标签（去重）"""
        if tag not in self.risk_tags:
            self.risk_tags.append(tag)
    
    def _extract_numeric_value(self, val):
        """将任意值转换为纯数字，去除单位和百分号"""
        if val is None or val == 'N/A' or val == '':
            return None
        try:
            # 处理字符串值
            if isinstance(val, str):
                # 去除百分号
                val = val.replace('%', '').strip()
                # 去除单位（如元）
                val = val.replace('元', '').strip()
                # 去除空格和其他字符
                val = val.replace(',', '').strip()
            # 转换为float
            num_val = float(val)
            # 四舍五入到合适的小数位
            if abs(num_val) >= 10000:
                return round(num_val, 2)  # 很大数值保留2位
            elif abs(num_val) >= 100:
                return round(num_val, 2)  # 较大数值保留2位
            elif abs(num_val) >= 1:
                return round(num_val, 2)  # 一般数值保留2位
            elif abs(num_val) >= 0.01:
                return round(num_val, 3)  # 小数值保留3位
            else:
                return round(num_val, 4)  # 极小数值保留4位
        except:
            return None
    
    def _calculate_data_completeness(self):
        """计算数据完整度评分（0-1）"""
        total_checks = 8
        completed = 0
        
        # 检查各指标类别是否有数据
        if self.calculated_metrics.get('growth'):
            completed += 1
        if self.calculated_metrics.get('profitability'):
            completed += 1
        if self.calculated_metrics.get('solvency'):
            completed += 1
        if self.calculated_metrics.get('cashflow'):
            completed += 1
        if self.calculated_metrics.get('dupont'):
            completed += 1
        if self.calculated_metrics.get('operation'):
            completed += 1
        if self.calculated_metrics.get('valuation'):
            completed += 1
        
        # 检查行业数据
        if self.data.get('industry_info'):
            completed += 1
        
        return completed / total_checks

    # ---------- 信号判定 ----------
    def determine_signal(self) -> Dict:
        """根据指标判定最终信号"""
        score = 0
        factors = []
        
        # 盈利能力评分
        profitability = self.calculated_metrics.get('profitability', {})
        roe = profitability.get('roe', 'N/A')
        if roe != 'N/A':
            try:
                roe_val = float(roe.replace('%', ''))
                if roe_val > 15:
                    score += 2
                    factors.append('ROE优秀')
                elif roe_val > 10:
                    score += 1
                    factors.append('ROE良好')
                elif roe_val < 0:
                    score -= 2
                    factors.append('ROE为负')
            except:
                pass
        
        # 净利率评分
        net_margin = profitability.get('net_margin', 'N/A')
        if net_margin != 'N/A':
            try:
                margin_val = float(net_margin.replace('%', ''))
                if margin_val >= 10:
                    score += 1
                    factors.append('净利率健康')
                elif margin_val < 0:
                    score -= 2
                    factors.append('净利率为负')
            except:
                pass
        
        # 增长能力评分
        growth = self.calculated_metrics.get('growth', {})
        profit_growth = growth.get('profit_growth_yoy', 'N/A')
        if profit_growth != 'N/A':
            try:
                val = float(profit_growth.replace('%', ''))
                if val > 20:
                    score += 2
                    factors.append('盈利增长强劲')
                elif val > 0:
                    score += 1
                    factors.append('盈利正增长')
                elif val < -30:
                    score -= 2
                    factors.append('盈利大幅下滑')
            except:
                pass
        
        # 现金流质量评分
        cashflow = self.calculated_metrics.get('cashflow', {})
        quality = cashflow.get('operating_cashflow_quality', '')
        if 'strong' in quality.lower():
            score += 2
            factors.append('现金流质量高')
        elif 'weak' in quality.lower():
            score -= 2
            factors.append('现金流质量差')
        
        # 偿债能力评分
        solvency = self.calculated_metrics.get('solvency', {})
        debt_ratio = solvency.get('debt_ratio', '')
        if debt_ratio != 'N/A':
            try:
                val = float(debt_ratio.replace('%', ''))
                if val < 50:
                    score += 1
                    factors.append('负债水平健康')
                elif val > 70:
                    score -= 2
                    factors.append('负债水平过高')
            except:
                pass
        
        # 杜邦分析评分
        dupont = self.calculated_metrics.get('dupont', {})
        assessment = dupont.get('dupont_assessment', '')
        if '优秀' in assessment:
            score += 2
            factors.append('杜邦分析优秀')
        elif '亏损' in assessment:
            score -= 2
            factors.append('杜邦分析显示亏损')
        
        # 异常数量扣分
        if len(self.anomalies) >= 2:
            score -= 2
            factors.append('多项异常指标')
        elif len(self.anomalies) == 1:
            score -= 1
            factors.append('存在异常指标')
        
        # 计算数据完整度
        data_completeness = self._calculate_data_completeness()
        
        # 确定最终信号和基础confidence
        if score >= 5:
            signal = 'BULLISH'
            base_confidence = 0.7
            summary = '财务状况良好，各项指标健康，建议关注'
        elif score >= 2:
            signal = 'NEUTRAL'
            base_confidence = 0.5
            summary = '财务状况一般，存在一些亮点和风险，建议观望'
        elif score >= -2:
            signal = 'NEUTRAL'
            base_confidence = 0.4
            summary = '财务状况偏弱，需谨慎评估'
        else:
            signal = 'BEARISH'
            base_confidence = 0.6
            summary = '财务状况较差，存在明显风险，建议回避'
        
        # 计算数据质量评分
        data_quality = 1.0
        extreme_anomaly_count = sum(1 for a in self.anomalies if a.get('severity') == 'high')
        if extreme_anomaly_count >= 2:
            data_quality = 0.5
        elif extreme_anomaly_count == 1:
            data_quality = 0.7
        
        # 最终confidence计算公式: confidence = base_confidence * data_completeness * data_quality
        # base_confidence由score决定，data_completeness基于关键指标存在性，data_quality基于高风险异常数量
        confidence = base_confidence * data_completeness * data_quality
        confidence = max(0.3, min(0.9, confidence))
        
        # 数据不足时返回中性
        if not self.calculated_metrics:
            signal = 'NEUTRAL'
            confidence = 0.2
            summary = '数据不足，无法生成有效分析'
        
        return {
            'signal': signal,
            'confidence': round(confidence, 2),
            'summary': summary,
            'factors': factors,
            'score': score,
            'confidence_breakdown': {
                'data_completeness': round(data_completeness, 2),
                'data_quality': round(data_quality, 2),
                'base_confidence': round(base_confidence, 2),
                'overall': round(confidence, 2)
            }
        }

    def _generate_industry_comparison(self):
        """生成行业对比数据"""
        industry_comparison = {}
        
        # 从industry_info获取行业数据
        if self.data.get('industry_info'):
            industry_info = self.data['industry_info']
            industry_avg = industry_info.get('industry_average', {})
            
            # 获取行业均值（匹配实际数据键名）
            industry_comparison['pe_industry_avg'] = industry_avg.get('平均市盈率TTM', None)
            industry_comparison['pb_industry_avg'] = industry_avg.get('平均市净率', None)
            industry_comparison['revenue_growth_industry_avg'] = industry_avg.get('平均营收增长率(09-30)(%)', None)
            industry_comparison['profit_growth_industry_avg'] = industry_avg.get('平均净利润增长率(09-30)(%)', None)
            industry_comparison['dividend_yield_industry_avg'] = industry_avg.get('平均股息率(%)', None)
            
            # 对比公司数据和行业均值
            valuation = self.calculated_metrics.get('valuation', {})
            pe_ttm = self._extract_numeric_value(valuation.get('PE(TTM)'))
            pb = self._extract_numeric_value(valuation.get('PB'))
            
            growth = self.calculated_metrics.get('growth', {})
            revenue_growth = self._extract_numeric_value(growth.get('营收同比增长率'))
            
            profitability = self.calculated_metrics.get('profitability', {})
            gross_margin = self._extract_numeric_value(profitability.get('毛利率'))
            
            solvency = self.calculated_metrics.get('solvency', {})
            debt_ratio = self._extract_numeric_value(solvency.get('资产负债率'))
            
            # 计算相对估值（使用申万行业阈值）
            industry_pe = industry_comparison.get('pe_industry_avg')
            if pe_ttm is not None and industry_pe is not None and industry_pe != 0:
                if self.industry_thresholds:
                    pe_low = self.industry_thresholds.get('pe_low', industry_pe * 0.7)
                    pe_high = self.industry_thresholds.get('pe_high', industry_pe * 1.5)
                    if pe_ttm < pe_low:
                        industry_comparison['relative_pe_percentile'] = '显著低估'
                        industry_comparison['threshold_source'] = '申万行业'
                    elif pe_ttm < industry_pe:
                        industry_comparison['relative_pe_percentile'] = '略微低估'
                        industry_comparison['threshold_source'] = '申万行业'
                    elif pe_ttm < pe_high:
                        industry_comparison['relative_pe_percentile'] = '正常'
                        industry_comparison['threshold_source'] = '申万行业'
                    elif pe_ttm < pe_high * 1.3:
                        industry_comparison['relative_pe_percentile'] = '略微高估'
                        industry_comparison['threshold_source'] = '申万行业'
                    else:
                        industry_comparison['relative_pe_percentile'] = '显著高估'
                        industry_comparison['threshold_source'] = '申万行业'
                else:
                    pe_ratio = pe_ttm / industry_pe
                    if pe_ratio < 0.5:
                        industry_comparison['relative_pe_percentile'] = '显著低估'
                    elif pe_ratio < 0.8:
                        industry_comparison['relative_pe_percentile'] = '略微低估'
                    elif pe_ratio < 1.2:
                        industry_comparison['relative_pe_percentile'] = '正常'
                    elif pe_ratio < 1.5:
                        industry_comparison['relative_pe_percentile'] = '略微高估'
                    else:
                        industry_comparison['relative_pe_percentile'] = '显著高估'
                    industry_comparison['threshold_source'] = '通用阈值'
            
            # 计算相对增长
            industry_revenue_growth = industry_comparison.get('revenue_growth_industry_avg')
            if revenue_growth is not None and industry_revenue_growth is not None:
                if revenue_growth > industry_revenue_growth + 10:
                    industry_comparison['relative_growth'] = '显著领先'
                elif revenue_growth > industry_revenue_growth:
                    industry_comparison['relative_growth'] = '略微领先'
                elif revenue_growth > industry_revenue_growth - 10:
                    industry_comparison['relative_growth'] = '正常'
                elif revenue_growth > industry_revenue_growth - 20:
                    industry_comparison['relative_growth'] = '略微落后'
                else:
                    industry_comparison['relative_growth'] = '严重落后'
        
        return industry_comparison
    
    def _generate_action_reason(self, signal, factors):
        """根据信号和因素生成更综合的操作理由"""
        reason_parts = []
        
        # 从各维度提取关键信息
        growth = self.calculated_metrics.get('growth', {})
        valuation = self.calculated_metrics.get('valuation', {})
        cashflow = self.calculated_metrics.get('cashflow', {})
        
        # 获取核心数值
        profit_growth = growth.get('净利润同比增长率')
        revenue_growth = growth.get('营收同比增长率')
        pe_ttm = valuation.get('PE(TTM)') if isinstance(valuation, dict) else None
        
        # 行业对比
        industry_comp = self._generate_industry_comparison()
        pe_status = industry_comp.get('relative_pe_percentile', '') if industry_comp else ''
        growth_status = industry_comp.get('relative_growth', '') if industry_comp else ''
        
        # 异常情况
        high_anomalies = [a for a in self.anomalies if a.get('severity') == 'high']
        
        if signal == 'BEARISH':
            reason_parts.append("盈利严重恶化")
            if profit_growth is not None:
                reason_parts.append(f"净利润同比{profit_growth:+.1f}%")
            
            if 'ROE为负' in factors:
                reason_parts.append("ROE为负，经营效率不足")
            if '净利率为负' in factors:
                reason_parts.append("处于亏损状态")
            if high_anomalies:
                reason_parts.append(f"触发{len(high_anomalies)}项高风险指标")
            
            # 添加矛盾点
            if pe_status and '低估' in pe_status:
                reason_parts.append(f"尽管估值{pe_status}")
            
            cash_quality = cashflow.get('现金流质量', '')
            if 'adequate' in str(cash_quality) or 'strong' in str(cash_quality):
                reason_parts.append("现金流尚未恶化")
            
            reason_parts.append("建议减仓观望，等待业绩企稳信号")
        
        elif signal == 'BULLISH':
            reason_parts.append("公司财务状况良好")
            if 'ROE优秀' in factors:
                reason_parts.append("ROE表现优秀")
            if '盈利增长强劲' in factors:
                reason_parts.append("盈利增长强劲")
            if '现金流质量高' in factors:
                reason_parts.append("现金流健康")
            reason_parts.append("建议关注或分批买入")
        
        else:  # NEUTRAL
            reason_parts.append("公司财务状况中性")
            positive_factors = [f for f in factors if '优秀' in f or '良好' in f or '健康' in f or '强劲' in f]
            negative_factors = [f for f in factors if '负' in f or '下滑' in f or '过高' in f or '异常' in f]
            
            if positive_factors:
                reason_parts.append(f"存在{','.join(positive_factors)}等亮点")
            if negative_factors:
                reason_parts.append(f"但也面临{','.join(negative_factors)}等风险")
            
            if pe_status and '低估' in pe_status:
                reason_parts.append("估值相对有吸引力")
            
            reason_parts.append("建议观望，等待进一步信号")
        
        return '，'.join(reason_parts)

    def _format_all_numeric_metrics(self, metrics_obj):
        """递归格式化所有数值字段，统一为纯数字并处理is_suspect标记"""
        if isinstance(metrics_obj, dict):
            result = {}
            for key, value in metrics_obj.items():
                if key.endswith('_备注') or key == '现金流质量':
                    # 保留注释字段
                    result[key] = value
                    continue
                if key == 'dupont_assessment':
                    # 删除重复的文本判断
                    continue
                # 处理数值
                if isinstance(value, (str, int, float)):
                    num_val = self._extract_numeric_value(value)
                    if num_val is not None:
                        # 检查极端值
                        is_suspect = '环比' in key and (num_val < -150 or num_val > 200)
                        if is_suspect:
                            # 极端值设为null，保留原始值在标记中
                            result[key] = None
                            result[f"{key}_is_suspect"] = True
                            result[f"{key}_raw"] = num_val
                        else:
                            result[key] = num_val
                    else:
                        result[key] = value
                else:
                    # 递归处理嵌套对象
                    result[key] = self._format_all_numeric_metrics(value)
            return result
        elif isinstance(metrics_obj, list):
            return [self._format_all_numeric_metrics(item) for item in metrics_obj]
        else:
            return metrics_obj
    
    # ---------- 生成结构化摘要 ----------
    def generate_structured_summary(self) -> Dict:
        """生成标准JSON格式的结构化摘要"""
        verdict = self.determine_signal()
        
        # 格式化所有指标为纯数字
        formatted_metrics = self._format_all_numeric_metrics(self.calculated_metrics)
        
        # 提取关键指标用于输出（使用中文字段名，直接从detailed_metrics复制）
        key_metrics = {}
        
        # 增长指标（从detailed_metrics复制，确保有值）
        growth = formatted_metrics.get('growth', {})
        key_metrics['营收同比增长率'] = self._extract_numeric_value(growth.get('营收同比增长率'))
        key_metrics['净利润同比增长率'] = self._extract_numeric_value(growth.get('净利润同比增长率'))
        
        # 盈利能力指标
        profitability = formatted_metrics.get('profitability', {})
        key_metrics['ROE'] = self._extract_numeric_value(profitability.get('ROE'))
        key_metrics['毛利率'] = self._extract_numeric_value(profitability.get('毛利率'))
        key_metrics['净利率'] = self._extract_numeric_value(profitability.get('净利率'))
        
        # 偿债能力指标
        solvency = formatted_metrics.get('solvency', {})
        key_metrics['资产负债率'] = self._extract_numeric_value(solvency.get('资产负债率'))
        key_metrics['速动比率'] = self._extract_numeric_value(solvency.get('速动比率'))
        key_metrics['流动比率'] = self._extract_numeric_value(solvency.get('流动比率'))
        
        # 现金流指标
        cashflow = formatted_metrics.get('cashflow', {})
        key_metrics['经营活动现金流净额'] = self._extract_numeric_value(cashflow.get('经营活动现金流净额'))
        
        # 估值指标
        valuation = formatted_metrics.get('valuation', {})
        key_metrics['PE(TTM)'] = self._extract_numeric_value(valuation.get('PE(TTM)'))
        key_metrics['PB'] = self._extract_numeric_value(valuation.get('PB'))
        
        # 建议操作
        suggested_action = 'HOLD'
        if verdict['signal'] == 'BULLISH':
            suggested_action = 'BUY'
        elif verdict['signal'] == 'BEARISH':
            suggested_action = 'SELL'
        
        # 生成行业对比数据
        industry_comparison = self._generate_industry_comparison()
        
        # 生成操作理由
        action_reason = self._generate_action_reason(verdict['signal'], verdict['factors'])
        
        # 构建最终摘要
        summary = {
            "module": "financial_analysis",
            "verdict": {
                "signal": verdict['signal'],
                "confidence": verdict['confidence'],
                "summary": verdict['summary'],
                "factors": verdict['factors'],
                "score": verdict['score'],
                "action_reason": action_reason,
                "confidence_breakdown": verdict.get('confidence_breakdown', {})
            },
            "key_metrics": key_metrics,
            "detailed_metrics": formatted_metrics,
            "major_anomalies": self.anomalies,
            "suggested_action": suggested_action,
            "risk_tags": list(set(self.risk_tags)),
            "industry_comparison": industry_comparison,
            "meta": {
                "ticker": self.ticker,
                "company_name": self.company_name,
                "generated_at": datetime.now().isoformat(),
                "data_sources_loaded": [k for k, v in self.data.items() if v is not None],
                "analysis_version": "v1.0"
            }
        }
        
        return summary

    # ---------- 保存结果 ----------
    def save_summary(self, summary: Dict) -> str:
        """保存摘要JSON文件"""
        os.makedirs(self.stock_dir, exist_ok=True)
        filename = f"{self.ticker}_financial_summary.json"
        filepath = os.path.join(self.stock_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
        print(f"  结构化摘要已保存至 {filepath}")
        return filepath

    # ---------- 主流程 ----------
    def run(self):
        print(f"\n{'='*60}")
        print(f"开始生成 {self.ticker} 财务结构化摘要")
        print(f"{'='*60}")

        if not self.load_all_data():
            print("没有加载到任何财务数据，退出。")
            return None

        self.calculate_all_metrics()
        
        summary = self.generate_structured_summary()
        filepath = self.save_summary(summary)
        
        print(f"\n{'='*60}")
        print(f"完成，输出文件: {filepath}")
        print(f"信号: {summary['verdict']['signal']} (置信度: {summary['verdict']['confidence']})")
        print(f"{'='*60}")
        
        return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="生成财务结构化摘要")
    parser.add_argument('--ticker', required=True, help="股票代码，如 300433.SZ")
    args = parser.parse_args()

    analyzer = FinancialStructuredAnalyzer(args.ticker)
    analyzer.run()


if __name__ == "__main__":
    main()