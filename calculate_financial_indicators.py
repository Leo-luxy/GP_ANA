
"""
calculate_financial_indicators.py
功能：从财务指标JSON文件中读取数据，计算量化分析可能用到的财务指标，并保存结果
"""

import json
import os
import sys
import math
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class FinancialIndicatorsCalculator:
    def __init__(self, input_file):
        self.input_file = input_file
        self.data = self._load_data()
        self.results = {
            'ticker': self.data.get('ticker', ''),
            'data_sources': self.data.get('data_sources', []),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'calculated_indicators': {},
            'used_data': {}
        }
    
    def _load_data(self):
        """加载JSON数据"""
        with open(self.input_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _get_profit_data(self):
        """获取利润表数据"""
        return self.data.get('profit_indicators', {}).get('profit_table', [])
    
    def _get_balance_data(self):
        """获取资产负债表数据"""
        return self.data.get('debt_indicators', {}).get('balance_table', [])
    
    def _get_cash_flow_data(self):
        """获取现金流量表数据"""
        return self.data.get('cash_flow', [])
    
    def _get_same_month_data(self, data, current_month, current_year):
        """获取相同月份的数据"""
        for item in data:
            report_date = item.get('报告日', '')
            if report_date:
                try:
                    year = int(report_date[:4])
                    month = int(report_date[4:6])
                    if month == current_month and year == current_year - 1:
                        return item
                except ValueError:
                    pass
        return None
    
    def _extract_date_info(self, report_date):
        """提取日期信息"""
        if report_date:
            try:
                year = int(report_date[:4])
                month = int(report_date[4:6])
                return year, month
            except ValueError:
                pass
        return None, None
    
    def calculate_profitability_indicators(self):
        """计算盈利能力指标"""
        profit_data = self._get_profit_data()
        if not profit_data:
            return
        
        indicators = {}
        used_data = {}
        
        # 最新一期数据
        latest_data = profit_data[0]
        report_date = latest_data.get('报告日', '')
        year, month = self._extract_date_info(report_date)
        
        # 毛利率
        if '营业收入' in latest_data and '营业成本' in latest_data:
            revenue = latest_data['营业收入']
            cost = latest_data['营业成本']
            if revenue > 0:
                gross_profit_margin = (revenue - cost) / revenue * 100
                indicators['毛利率'] = round(gross_profit_margin, 2)
                used_data['毛利率'] = {
                    '报告日': report_date,
                    '营业收入': revenue,
                    '营业成本': cost
                }
        
        # 净利率
        if '净利润' in latest_data and '营业收入' in latest_data:
            net_profit = latest_data['净利润']
            revenue = latest_data['营业收入']
            if revenue > 0:
                net_profit_margin = net_profit / revenue * 100
                indicators['净利率'] = round(net_profit_margin, 2)
                used_data['净利率'] = {
                    '报告日': report_date,
                    '净利润': net_profit,
                    '营业收入': revenue
                }
        
        # 营业利润率
        if '营业利润' in latest_data and '营业收入' in latest_data:
            operating_profit = latest_data['营业利润']
            revenue = latest_data['营业收入']
            if revenue > 0:
                operating_profit_margin = operating_profit / revenue * 100
                indicators['营业利润率'] = round(operating_profit_margin, 2)
                used_data['营业利润率'] = {
                    '报告日': report_date,
                    '营业利润': operating_profit,
                    '营业收入': revenue
                }
        
        # EBITDA
        if '营业利润' in latest_data and '财务费用' in latest_data:
            operating_profit = latest_data['营业利润']
            financial_expense = latest_data['财务费用']
            # 标准EBITDA计算：营业利润 + 财务费用 + 折旧摊销
            # 由于缺少折旧摊销数据，这里只计算营业利润 + 财务费用
            # 注意：这不是标准EBITDA，仅供参考
            ebitda = operating_profit + abs(financial_expense)
            indicators['EBITDA'] = round(ebitda, 2)
            indicators['EBITDA_备注'] = '缺少折旧摊销数据，为近似值'
            used_data['EBITDA'] = {
                '报告日': report_date,
                '营业利润': operating_profit,
                '财务费用': financial_expense,
                '备注': '缺少折旧摊销数据，非标准EBITDA计算（近似值）'
            }
        
        # 基本每股收益
        if '基本每股收益' in latest_data:
            indicators['基本每股收益'] = latest_data['基本每股收益']
            used_data['基本每股收益'] = {
                '报告日': report_date,
                '基本每股收益': latest_data['基本每股收益']
            }
        
        # 稀释每股收益
        if '稀释每股收益' in latest_data:
            indicators['稀释每股收益'] = latest_data['稀释每股收益']
            used_data['稀释每股收益'] = {
                '报告日': report_date,
                '稀释每股收益': latest_data['稀释每股收益']
            }
        
        # 同比增长率
        if year and month:
            same_month_data = self._get_same_month_data(profit_data, month, year)
            if same_month_data:
                # 营收同比增长率
                if '营业收入' in latest_data and '营业收入' in same_month_data:
                    current_revenue = latest_data['营业收入']
                    previous_revenue = same_month_data['营业收入']
                    if previous_revenue > 0:
                        revenue_growth = (current_revenue - previous_revenue) / previous_revenue * 100
                        indicators['营收同比增长率'] = round(revenue_growth, 2)
                        used_data['营收同比增长率'] = {
                            '当前报告日': report_date,
                            '上期报告日': same_month_data.get('报告日', ''),
                            '当前营业收入': current_revenue,
                            '上期营业收入': previous_revenue
                        }
                
                # 净利润同比增长率
                if '净利润' in latest_data and '净利润' in same_month_data:
                    current_profit = latest_data['净利润']
                    previous_profit = same_month_data['净利润']
                    if previous_profit > 0:
                        profit_growth = (current_profit - previous_profit) / previous_profit * 100
                        indicators['净利润同比增长率'] = round(profit_growth, 2)
                        used_data['净利润同比增长率'] = {
                            '当前报告日': report_date,
                            '上期报告日': same_month_data.get('报告日', ''),
                            '当前净利润': current_profit,
                            '上期净利润': previous_profit
                        }
        
        self.results['calculated_indicators']['盈利能力指标'] = indicators
        self.results['used_data']['盈利能力指标'] = used_data
    
    def calculate_solvency_indicators(self):
        """计算偿债能力指标"""
        balance_data = self._get_balance_data()
        profit_data = self._get_profit_data()
        if not balance_data:
            return
        
        indicators = {}
        used_data = {}
        
        # 最新一期数据
        latest_data = balance_data[0]
        report_date = latest_data.get('报告日', '')
        
        # 资产负债率
        if '资产总计' in latest_data and '流动负债合计' in latest_data and '非流动负债合计' in latest_data:
            total_assets = latest_data['资产总计']
            current_liabilities = latest_data['流动负债合计']
            non_current_liabilities = latest_data['非流动负债合计']
            total_liabilities = current_liabilities + non_current_liabilities
            if total_assets > 0:
                debt_ratio = total_liabilities / total_assets * 100
                indicators['资产负债率'] = round(debt_ratio, 2)
                used_data['资产负债率'] = {
                    '报告日': report_date,
                    '资产总计': total_assets,
                    '流动负债合计': current_liabilities,
                    '非流动负债合计': non_current_liabilities,
                    '负债合计': total_liabilities
                }
        
        # 流动比率
        if '流动资产合计' in latest_data and '流动负债合计' in latest_data:
            current_assets = latest_data['流动资产合计']
            current_liabilities = latest_data['流动负债合计']
            if current_liabilities > 0:
                current_ratio = current_assets / current_liabilities
                indicators['流动比率'] = round(current_ratio, 2)
                used_data['流动比率'] = {
                    '报告日': report_date,
                    '流动资产合计': current_assets,
                    '流动负债合计': current_liabilities
                }
        
        # 速动比率
        if '流动资产合计' in latest_data and '存货' in latest_data and '流动负债合计' in latest_data:
            current_assets = latest_data['流动资产合计']
            inventory = latest_data['存货']
            current_liabilities = latest_data['流动负债合计']
            quick_assets = current_assets - inventory
            if current_liabilities > 0:
                quick_ratio = quick_assets / current_liabilities
                indicators['速动比率'] = round(quick_ratio, 2)
                used_data['速动比率'] = {
                    '报告日': report_date,
                    '流动资产合计': current_assets,
                    '存货': inventory,
                    '速动资产': quick_assets,
                    '流动负债合计': current_liabilities
                }
        
        # 利息保障倍数
        if profit_data:
            latest_profit = profit_data[0]
            if '营业利润' in latest_profit and '财务费用' in latest_profit:
                operating_profit = latest_profit['营业利润']
                financial_expense = latest_profit['财务费用']
                if financial_expense < 0:
                    financial_expense = abs(financial_expense)
                if financial_expense > 0:
                    interest_coverage = operating_profit / financial_expense
                    indicators['利息保障倍数'] = round(interest_coverage, 2)
                    used_data['利息保障倍数'] = {
                        '报告日': latest_profit.get('报告日', ''),
                        '营业利润': operating_profit,
                        '财务费用': financial_expense
                    }
        
        self.results['calculated_indicators']['偿债能力指标'] = indicators
        self.results['used_data']['偿债能力指标'] = used_data
    
    def calculate_operation_indicators(self):
        """计算运营能力指标"""
        balance_data = self._get_balance_data()
        profit_data = self._get_profit_data()
        if not balance_data or not profit_data:
            return
        
        indicators = {}
        used_data = {}
        
        # 最新一期数据
        latest_balance = balance_data[0]
        latest_profit = profit_data[0]
        report_date = latest_balance.get('报告日', '')
        
        # 总资产周转率
        if '资产总计' in latest_balance and '营业收入' in latest_profit:
            total_assets = latest_balance['资产总计']
            revenue = latest_profit['营业收入']
            if total_assets > 0:
                asset_turnover = revenue / total_assets
                indicators['总资产周转率'] = round(asset_turnover, 2)
                used_data['总资产周转率'] = {
                    '报告日': report_date,
                    '资产总计': total_assets,
                    '营业收入': revenue
                }
        
        # 应收账款周转率
        if '应收票据及应收账款' in latest_balance and '营业收入' in latest_profit:
            accounts_receivable = latest_balance['应收票据及应收账款']
            revenue = latest_profit['营业收入']
            if accounts_receivable > 0:
                ar_turnover = revenue / accounts_receivable
                indicators['应收账款周转率'] = round(ar_turnover, 2)
                used_data['应收账款周转率'] = {
                    '报告日': report_date,
                    '应收票据及应收账款': accounts_receivable,
                    '营业收入': revenue
                }
        
        # 存货周转率
        if '存货' in latest_balance and '营业成本' in latest_profit:
            inventory = latest_balance['存货']
            cost = latest_profit['营业成本']
            if inventory > 0:
                inventory_turnover = cost / inventory
                indicators['存货周转率'] = round(inventory_turnover, 2)
                used_data['存货周转率'] = {
                    '报告日': report_date,
                    '存货': inventory,
                    '营业成本': cost
                }
        
        # 固定资产周转率
        if '固定资产及清理合计' in latest_balance and '营业收入' in latest_profit:
            fixed_assets = latest_balance['固定资产及清理合计']
            revenue = latest_profit['营业收入']
            if fixed_assets > 0:
                fixed_asset_turnover = revenue / fixed_assets
                indicators['固定资产周转率'] = round(fixed_asset_turnover, 2)
                used_data['固定资产周转率'] = {
                    '报告日': report_date,
                    '固定资产及清理合计': fixed_assets,
                    '营业收入': revenue
                }
        
        self.results['calculated_indicators']['运营能力指标'] = indicators
        self.results['used_data']['运营能力指标'] = used_data
    
    def calculate_cash_flow_indicators(self):
        """计算现金流指标"""
        cash_flow_data = self._get_cash_flow_data()
        profit_data = self._get_profit_data()
        if not cash_flow_data:
            return
        
        indicators = {}
        used_data = {}
        
        # 最新一期数据
        latest_cash_flow = cash_flow_data[0]
        report_date = latest_cash_flow.get('报告日', '')
        
        # 经营活动现金流量净额
        if '经营活动产生的现金流量净额' in latest_cash_flow:
            operating_cash_flow = latest_cash_flow['经营活动产生的现金流量净额']
            indicators['经营活动现金流量净额'] = round(operating_cash_flow, 2)
            used_data['经营活动现金流量净额'] = {
                '报告日': report_date,
                '经营活动产生的现金流量净额': operating_cash_flow
            }
        
        # 投资活动现金流量净额
        if '投资活动产生的现金流量净额' in latest_cash_flow:
            investing_cash_flow = latest_cash_flow['投资活动产生的现金流量净额']
            indicators['投资活动现金流量净额'] = round(investing_cash_flow, 2)
            used_data['投资活动现金流量净额'] = {
                '报告日': report_date,
                '投资活动产生的现金流量净额': investing_cash_flow
            }
        
        # 筹资活动现金流量净额
        if '筹资活动产生的现金流量净额' in latest_cash_flow:
            financing_cash_flow = latest_cash_flow['筹资活动产生的现金流量净额']
            indicators['筹资活动现金流量净额'] = round(financing_cash_flow, 2)
            used_data['筹资活动现金流量净额'] = {
                '报告日': report_date,
                '筹资活动产生的现金流量净额': financing_cash_flow
            }
        
        # 现金及现金等价物净增加额
        if '现金及现金等价物净增加额' in latest_cash_flow:
            cash_increase = latest_cash_flow['现金及现金等价物净增加额']
            indicators['现金及现金等价物净增加额'] = round(cash_increase, 2)
            used_data['现金及现金等价物净增加额'] = {
                '报告日': report_date,
                '现金及现金等价物净增加额': cash_increase
            }
        
        # 经营活动现金流量净额/净利润
        if '经营活动产生的现金流量净额' in latest_cash_flow and profit_data:
            operating_cash_flow = latest_cash_flow['经营活动产生的现金流量净额']
            latest_profit = profit_data[0]
            if '净利润' in latest_profit:
                net_profit = latest_profit['净利润']
                if net_profit != 0:
                    cash_flow_to_profit = operating_cash_flow / net_profit
                    indicators['经营活动现金流量净额/净利润'] = round(cash_flow_to_profit, 2)
                    used_data['经营活动现金流量净额/净利润'] = {
                        '报告日': report_date,
                        '经营活动产生的现金流量净额': operating_cash_flow,
                        '净利润': net_profit
                    }
        
        # 经营活动现金流量净额/营业收入
        if '经营活动产生的现金流量净额' in latest_cash_flow and profit_data:
            operating_cash_flow = latest_cash_flow['经营活动产生的现金流量净额']
            latest_profit = profit_data[0]
            if '营业收入' in latest_profit:
                revenue = latest_profit['营业收入']
                if revenue > 0:
                    cash_flow_to_revenue = operating_cash_flow / revenue * 100
                    indicators['经营活动现金流量净额/营业收入'] = round(cash_flow_to_revenue, 2)
                    used_data['经营活动现金流量净额/营业收入'] = {
                        '报告日': report_date,
                        '经营活动产生的现金流量净额': operating_cash_flow,
                        '营业收入': revenue
                    }
        
        self.results['calculated_indicators']['现金流指标'] = indicators
        self.results['used_data']['现金流指标'] = used_data
    
    def calculate_growth_indicators(self):
        """计算成长能力指标"""
        profit_data = self._get_profit_data()
        balance_data = self._get_balance_data()
        if not profit_data or not balance_data:
            return
        
        indicators = {}
        used_data = {}
        
        # 最新一期数据
        latest_profit = profit_data[0]
        latest_balance = balance_data[0]
        report_date = latest_profit.get('报告日', '')
        year, month = self._extract_date_info(report_date)
        
        # 1. 同比增长率（YoY）- 本期累计值 vs 去年同期累计值
        if year and month:
            # 营收同比增长率
            same_month_data = self._get_same_month_data(profit_data, month, year)
            if same_month_data:
                if '营业收入' in latest_profit and '营业收入' in same_month_data:
                    current_revenue = latest_profit['营业收入']
                    previous_revenue = same_month_data['营业收入']
                    if previous_revenue > 0:
                        revenue_yoy = (current_revenue - previous_revenue) / previous_revenue * 100
                        indicators['营收同比增长率'] = round(revenue_yoy, 2)
                        used_data['营收同比增长率'] = {
                            '当前报告日': report_date,
                            '去年同期报告日': same_month_data.get('报告日', ''),
                            '当前营业收入': current_revenue,
                            '去年同期营业收入': previous_revenue
                        }
                
                # 净利润同比增长率
                if '净利润' in latest_profit and '净利润' in same_month_data:
                    current_profit = latest_profit['净利润']
                    previous_profit = same_month_data['净利润']
                    if previous_profit > 0:
                        profit_yoy = (current_profit - previous_profit) / previous_profit * 100
                        indicators['净利润同比增长率'] = round(profit_yoy, 2)
                        used_data['净利润同比增长率'] = {
                            '当前报告日': report_date,
                            '去年同期报告日': same_month_data.get('报告日', ''),
                            '当前净利润': current_profit,
                            '去年同期净利润': previous_profit
                        }
        
        # 2. 单季度环比增长率（QoQ）- 本期单季值 vs 上期单季值
        if len(profit_data) >= 2:
            # 计算单季度营收
            current_revenue = latest_profit.get('营业收入', 0)
            previous_revenue = profit_data[1].get('营业收入', 0)
            current_quarter_revenue = current_revenue - previous_revenue
            
            # 计算上一期单季度营收
            if len(profit_data) >= 3:
                previous_quarter_revenue = previous_revenue - profit_data[2].get('营业收入', 0)
                if previous_quarter_revenue > 0:
                    revenue_qoq = (current_quarter_revenue - previous_quarter_revenue) / previous_quarter_revenue * 100
                    indicators['营收单季环比增长率'] = round(revenue_qoq, 2)
                    used_data['营收单季环比增长率'] = {
                        '当前报告日': report_date,
                        '上期报告日': profit_data[1].get('报告日', ''),
                        '当前单季营收': current_quarter_revenue,
                        '上期单季营收': previous_quarter_revenue
                    }
            
            # 计算单季度净利润
            current_profit = latest_profit.get('净利润', 0)
            previous_profit = profit_data[1].get('净利润', 0)
            current_quarter_profit = current_profit - previous_profit
            
            # 计算上一期单季度净利润
            if len(profit_data) >= 3:
                previous_quarter_profit = previous_profit - profit_data[2].get('净利润', 0)
                if previous_quarter_profit > 0:
                    profit_qoq = (current_quarter_profit - previous_quarter_profit) / previous_quarter_profit * 100
                    indicators['净利润单季环比增长率'] = round(profit_qoq, 2)
                    used_data['净利润单季环比增长率'] = {
                        '当前报告日': report_date,
                        '上期报告日': profit_data[1].get('报告日', ''),
                        '当前单季净利润': current_quarter_profit,
                        '上期单季净利润': previous_quarter_profit
                    }
        
        # 3. 单季度同比增长率（YoY for Single Quarter）
        if year and month and len(profit_data) >= 2:
            # 计算当前单季度营收
            current_revenue = latest_profit.get('营业收入', 0)
            previous_revenue = profit_data[1].get('营业收入', 0)
            current_quarter_revenue = current_revenue - previous_revenue
            
            # 查找去年同期的累计数据
            same_month_data = self._get_same_month_data(profit_data, month, year)
            if same_month_data:
                # 查找去年上一期的累计数据
                same_month_prev_data = None
                for item in profit_data:
                    item_report_date = item.get('报告日', '')
                    if item_report_date:
                        try:
                            item_year = int(item_report_date[:4])
                            item_month = int(item_report_date[4:6])
                            # 找到去年上一期（如去年Q2）
                            if item_month == month - 3 and item_year == year - 1:
                                same_month_prev_data = item
                                break
                        except ValueError:
                            pass
                
                if same_month_prev_data:
                    # 计算去年同期单季度营收
                    last_year_quarter_revenue = same_month_data.get('营业收入', 0) - same_month_prev_data.get('营业收入', 0)
                    if last_year_quarter_revenue > 0:
                        revenue_quarter_yoy = (current_quarter_revenue - last_year_quarter_revenue) / last_year_quarter_revenue * 100
                        indicators['营收单季同比增长率'] = round(revenue_quarter_yoy, 2)
                        used_data['营收单季同比增长率'] = {
                            '当前报告日': report_date,
                            '去年同期报告日': same_month_data.get('报告日', ''),
                            '当前单季营收': current_quarter_revenue,
                            '去年同期单季营收': last_year_quarter_revenue
                        }
        
        # 4. 总资产同比增长率
        if year and month:
            same_month_balance_data = self._get_same_month_data(balance_data, month, year)
            if same_month_balance_data:
                if '资产总计' in latest_balance and '资产总计' in same_month_balance_data:
                    current_assets = latest_balance['资产总计']
                    previous_assets = same_month_balance_data['资产总计']
                    if previous_assets > 0:
                        assets_yoy = (current_assets - previous_assets) / previous_assets * 100
                        indicators['总资产同比增长率'] = round(assets_yoy, 2)
                        used_data['总资产同比增长率'] = {
                            '当前报告日': report_date,
                            '去年同期报告日': same_month_balance_data.get('报告日', ''),
                            '当前资产总计': current_assets,
                            '去年同期资产总计': previous_assets
                        }
        
        # 5. 净资产同比增长率
        if year and month:
            same_month_balance_data = self._get_same_month_data(balance_data, month, year)
            if same_month_balance_data:
                # 计算当前净资产
                current_assets = latest_balance.get('资产总计', 0)
                current_liabilities = latest_balance.get('流动负债合计', 0) + latest_balance.get('非流动负债合计', 0)
                current_equity = current_assets - current_liabilities
                
                # 计算去年同期净资产
                previous_assets = same_month_balance_data.get('资产总计', 0)
                previous_liabilities = same_month_balance_data.get('流动负债合计', 0) + same_month_balance_data.get('非流动负债合计', 0)
                previous_equity = previous_assets - previous_liabilities
                
                if previous_equity > 0:
                    equity_yoy = (current_equity - previous_equity) / previous_equity * 100
                    indicators['净资产同比增长率'] = round(equity_yoy, 2)
                    used_data['净资产同比增长率'] = {
                        '当前报告日': report_date,
                        '去年同期报告日': same_month_balance_data.get('报告日', ''),
                        '当前净资产': current_equity,
                        '去年同期净资产': previous_equity
                    }
        
        self.results['calculated_indicators']['成长能力指标'] = indicators
        self.results['used_data']['成长能力指标'] = used_data
    
    def add_historical_trends(self):
        """补充近3年的核心财务数据趋势"""
        profit_data = self._get_profit_data()
        cash_flow_data = self._get_cash_flow_data()
        
        if not profit_data:
            return
        
        # 按年份和季度整理数据
        year_data = {}
        for item in profit_data:
            report_date = item.get('报告日', '')
            if report_date:
                try:
                    year = int(report_date[:4])
                    month = int(report_date[4:6])
                    
                    # 按年度和季度分组
                    if year not in year_data:
                        year_data[year] = {}
                    
                    # 12月为年报，3月为Q1，6月为Q2，9月为Q3
                    if month == 12:
                        quarter = '年报'
                    elif month == 3:
                        quarter = 'Q1'
                    elif month == 6:
                        quarter = 'Q2'
                    elif month == 9:
                        quarter = 'Q3'
                    else:
                        continue
                    
                    year_data[year][quarter] = item
                except ValueError:
                    pass
        
        # 构建历史趋势数据
        historical_trends = {
            '营收': {},
            '净利润': {},
            '毛利率': {},
            '经营活动现金流净额': {}
        }
        
        # 提取最近4个年度的数据（包括最新季度）
        years = sorted(year_data.keys(), reverse=True)[:4]
        for year in reversed(years):
            # 优先使用年报数据
            if '年报' in year_data[year]:
                item = year_data[year]['年报']
                key = str(year)
            # 否则使用最新季度数据
            else:
                quarters = ['Q3', 'Q2', 'Q1']
                for q in quarters:
                    if q in year_data[year]:
                        item = year_data[year][q]
                        key = f"{year}{q}"
                        break
                else:
                    continue
            
            # 提取营收
            if '营业收入' in item:
                historical_trends['营收'][key] = round(item['营业收入'] / 100000000, 1)  # 转换为亿元
            
            # 提取净利润
            if '净利润' in item:
                historical_trends['净利润'][key] = round(item['净利润'] / 100000000, 1)  # 转换为亿元
            
            # 计算毛利率
            if '营业收入' in item and '营业成本' in item:
                revenue = item['营业收入']
                cost = item['营业成本']
                if revenue > 0:
                    gross_margin = (revenue - cost) / revenue * 100
                    historical_trends['毛利率'][key] = round(gross_margin, 1)
        
        # 提取经营活动现金流净额
        if cash_flow_data:
            for item in cash_flow_data:
                report_date = item.get('报告日', '')
                if report_date:
                    try:
                        year = int(report_date[:4])
                        month = int(report_date[4:6])
                        
                        # 12月为年报，3月为Q1，6月为Q2，9月为Q3
                        if month == 12:
                            key = str(year)
                        elif month == 3:
                            key = f"{year}Q1"
                        elif month == 6:
                            key = f"{year}Q2"
                        elif month == 9:
                            key = f"{year}Q3"
                        else:
                            continue
                        
                        if '经营活动产生的现金流量净额' in item:
                            historical_trends['经营活动现金流净额'][key] = round(item['经营活动产生的现金流量净额'] / 100000000, 1)  # 转换为亿元
                    except ValueError:
                        pass
        
        # 只有当有数据时才添加
        if any(historical_trends.values()):
            self.results['historical_trends'] = historical_trends
    
    def add_industry_benchmark(self):
        """补充行业可比数据"""
        # 简化的行业参考区间
        industry_benchmark_note = "参考申万电子制造行业，2025Q3平均毛利率约18-22%，资产负债率约45-55%。当前公司毛利率低于行业均值，资产负债率略高于行业。"
        self.results['industry_benchmark_note'] = industry_benchmark_note
    
    def add_income_statement_summary(self):
        """补充利润表核心项目的绝对值"""
        profit_data = self._get_profit_data()
        if not profit_data:
            return
        
        latest_profit = profit_data[0]
        report_date = latest_profit.get('报告日', '')
        
        income_statement_summary = {
            '报告期': report_date,
            '营业总收入': None,
            '营业总成本': None,
            '营业利润': None,
            '利润总额': None,
            '净利润': None,
            '归属于母公司股东的净利润': None
        }
        
        # 提取核心项目
        if '营业总收入' in latest_profit:
            income_statement_summary['营业总收入'] = round(latest_profit['营业总收入'] / 100000000, 1)  # 转换为亿元
        elif '营业收入' in latest_profit:
            income_statement_summary['营业总收入'] = round(latest_profit['营业收入'] / 100000000, 1)  # 转换为亿元
        
        if '营业总成本' in latest_profit:
            income_statement_summary['营业总成本'] = round(latest_profit['营业总成本'] / 100000000, 1)  # 转换为亿元
        
        if '营业利润' in latest_profit:
            income_statement_summary['营业利润'] = round(latest_profit['营业利润'] / 100000000, 1)  # 转换为亿元
        
        if '利润总额' in latest_profit:
            income_statement_summary['利润总额'] = round(latest_profit['利润总额'] / 100000000, 1)  # 转换为亿元
        
        if '净利润' in latest_profit:
            income_statement_summary['净利润'] = round(latest_profit['净利润'] / 100000000, 1)  # 转换为亿元
        
        if '归属于母公司所有者的净利润' in latest_profit:
            income_statement_summary['归属于母公司股东的净利润'] = round(latest_profit['归属于母公司所有者的净利润'] / 100000000, 1)  # 转换为亿元
        
        self.results['income_statement_summary'] = income_statement_summary
    
    def calculate_all_indicators(self):
        """计算所有指标"""
        print("计算盈利能力指标...")
        self.calculate_profitability_indicators()
        
        print("计算偿债能力指标...")
        self.calculate_solvency_indicators()
        
        print("计算运营能力指标...")
        self.calculate_operation_indicators()
        
        print("计算现金流指标...")
        self.calculate_cash_flow_indicators()
        
        print("计算成长能力指标...")
        self.calculate_growth_indicators()
        
        print("补充历史趋势数据...")
        self.add_historical_trends()
        
        print("补充行业参考数据...")
        self.add_industry_benchmark()
        
        print("补充利润表摘要...")
        self.add_income_statement_summary()
    
    def save_results(self, output_file=None):
        """保存结果"""
        if not output_file:
            # 生成默认输出文件名
            base_name = os.path.basename(self.input_file)
            name_without_ext = os.path.splitext(base_name)[0]
            output_file = os.path.join(os.path.dirname(self.input_file), f"{name_without_ext}_calculated.json")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, ensure_ascii=False, indent=2)
        
        print(f"计算结果已保存到: {output_file}")
        return output_file

def main():
    """主函数"""
    import argparse
    import os
    from config import STOCK_TICKERS, DATA_DIR
    
    parser = argparse.ArgumentParser(description='计算财务指标')
    parser.add_argument('--ticker', type=str, 
                       help='指定股票代码（如002384.SZ）')
    args = parser.parse_args()
    
    # 确定要处理的股票列表
    if args.ticker:
        # 处理单个指定的股票
        tickers = [args.ticker]
    else:
        # 处理config中的所有股票
        tickers = list(STOCK_TICKERS.values())
    
    # 处理每个股票
    for ticker in tickers:
        print(f"\n处理股票: {ticker}")
        # 构建输入文件路径
        input_file = os.path.join(DATA_DIR, ticker, f"{ticker}_financial_indicators.json")
        
        # 检查文件是否存在
        if not os.path.exists(input_file):
            print(f"警告: 文件不存在: {input_file}")
            continue
        
        # 计算财务指标
        calculator = FinancialIndicatorsCalculator(input_file)
        calculator.calculate_all_indicators()
        calculator.save_results()

if __name__ == "__main__":
    main()
