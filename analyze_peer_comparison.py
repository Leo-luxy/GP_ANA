# analyze_peer_comparison.py
# 功能：分析同行对比数据

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG

def load_data(ticker):
    """加载所有相关数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    
    data = {
        'company_basic': None,
        'financial_indicators': None,
        'industry_peers': None,
        'market_performance': None,
        'dupont_analysis': None,
        'industry_valuation': None,
        'industry_growth': None,
        'industry_info': None
    }
    
    # 加载公司基本信息
    basic_file = os.path.join(stock_dir, f"{ticker}_company_basic.json")
    if os.path.exists(basic_file):
        try:
            with open(basic_file, 'r', encoding='utf-8') as f:
                data['company_basic'] = json.load(f)
            print(f"成功加载公司基本信息: {basic_file}")
        except Exception as e:
            print(f"加载公司基本信息时出错: {str(e)}")
    
    # 加载财务指标
    financial_file = os.path.join(stock_dir, f"{ticker}_financial_indicators_calculated.json")
    if os.path.exists(financial_file):
        try:
            with open(financial_file, 'r', encoding='utf-8') as f:
                data['financial_indicators'] = json.load(f)
            print(f"成功加载财务指标: {financial_file}")
        except Exception as e:
            print(f"加载财务指标时出错: {str(e)}")
    
    # 加载同行业公司数据
    peers_file = os.path.join(stock_dir, f"{ticker}_industry_peers.json")
    if os.path.exists(peers_file):
        try:
            with open(peers_file, 'r', encoding='utf-8') as f:
                data['industry_peers'] = json.load(f)
            print(f"成功加载同行业公司数据: {peers_file}")
        except Exception as e:
            print(f"加载同行业公司数据时出错: {str(e)}")
    
    # 加载历史日度市场表现数据
    market_file = os.path.join(stock_dir, f"{ticker}_market_performance.json")
    if os.path.exists(market_file):
        try:
            with open(market_file, 'r', encoding='utf-8') as f:
                data['market_performance'] = json.load(f)
            print(f"成功加载历史日度市场表现数据: {market_file}")
        except Exception as e:
            print(f"加载历史日度市场表现数据时出错: {str(e)}")
    
    # 加载杜邦分析行业排名数据
    dupont_file = os.path.join(stock_dir, f"{ticker}_dupont_analysis.json")
    if os.path.exists(dupont_file):
        try:
            with open(dupont_file, 'r', encoding='utf-8') as f:
                data['dupont_analysis'] = json.load(f)
            print(f"成功加载杜邦分析行业排名数据: {dupont_file}")
        except Exception as e:
            print(f"加载杜邦分析行业排名数据时出错: {str(e)}")
    
    # 加载行业估值排名数据
    valuation_file = os.path.join(stock_dir, f"{ticker}_industry_valuation.json")
    if os.path.exists(valuation_file):
        try:
            with open(valuation_file, 'r', encoding='utf-8') as f:
                data['industry_valuation'] = json.load(f)
            print(f"成功加载行业估值排名数据: {valuation_file}")
        except Exception as e:
            print(f"加载行业估值排名数据时出错: {str(e)}")
    
    # 加载行业成长能力排名数据
    growth_file = os.path.join(stock_dir, f"{ticker}_industry_growth.json")
    if os.path.exists(growth_file):
        try:
            with open(growth_file, 'r', encoding='utf-8') as f:
                data['industry_growth'] = json.load(f)
            print(f"成功加载行业成长能力排名数据: {growth_file}")
        except Exception as e:
            print(f"加载行业成长能力排名数据时出错: {str(e)}")
    
    # 加载行业信息数据
    industry_info_file = os.path.join(stock_dir, f"{ticker}_industry_info.json")
    if os.path.exists(industry_info_file):
        try:
            with open(industry_info_file, 'r', encoding='utf-8') as f:
                data['industry_info'] = json.load(f)
            print(f"成功加载行业信息数据: {industry_info_file}")
        except Exception as e:
            print(f"加载行业信息数据时出错: {str(e)}")
    
    return data

def analyze_financial_health(financial_data):
    """分析财务健康状况"""
    if not financial_data:
        return "未获取到财务数据"
    
    indicators = financial_data.get('calculated_indicators', {})
    analysis = []
    
    # 获取报告日期
    report_date = "20250930"
    used_data = financial_data.get('used_data', {})
    if used_data:
        profit_data = used_data.get('盈利能力指标', {}).get('毛利率', {})
        if '报告日' in profit_data:
            report_date = profit_data['报告日']
    
    # 盈利能力分析
    profitability = indicators.get('盈利能力指标', {})
    if profitability:
        gross_margin = profitability.get('毛利率', 0)
        net_margin = profitability.get('净利率', 0)
        roe = profitability.get('ROE', 0)
        
        analysis.append(f"**盈利能力**（{report_date}）：毛利率 {gross_margin}%，净利率 {net_margin}%")
    
    # 偿债能力分析
    solvency = indicators.get('偿债能力指标', {})
    if solvency:
        debt_ratio = solvency.get('资产负债率', 0)
        current_ratio = solvency.get('流动比率', 0)
        quick_ratio = solvency.get('速动比率', 0)
        
        analysis.append(f"**偿债能力**（{report_date}）：资产负债率 {debt_ratio}%，流动比率 {current_ratio}，速动比率 {quick_ratio}")
    
    # 运营能力分析
    operation = indicators.get('运营能力指标', {})
    if operation:
        asset_turnover = operation.get('总资产周转率', 0)
        inventory_turnover = operation.get('存货周转率', 0)
        ar_turnover = operation.get('应收账款周转率', 0)
        
        analysis.append(f"**运营能力**（{report_date}）：总资产周转率 {asset_turnover}，存货周转率 {inventory_turnover}，应收账款周转率 {ar_turnover}")
    
    # 现金流分析
    cash_flow = indicators.get('现金流指标', {})
    if cash_flow:
        operating_cash_flow = cash_flow.get('经营活动现金流量净额', 0)
        cash_to_profit = cash_flow.get('经营活动现金流量净额/净利润', 0)
        
        analysis.append(f"**现金流**（{report_date}）：经营活动现金流量净额 {operating_cash_flow/100000000:.2f}亿元，净现比 {cash_to_profit:.2f}")
    
    # 成长能力分析
    growth = indicators.get('成长能力指标', {})
    if growth:
        revenue_growth = growth.get('营收同比增长率', 0)
        profit_growth = growth.get('净利润同比增长率', 0)
        
        analysis.append(f"**成长能力**（{report_date}）：营收同比增长 {revenue_growth}%，净利润同比增长 {profit_growth}%")
    
    return '\n'.join(analysis)

def analyze_industry_position(peers_data, ticker, financial_data=None, company_basic=None):
    """分析行业地位"""
    if not peers_data:
        return "未获取到同行业公司数据"
    
    peers = peers_data.get('industry_peers', [])
    if not peers:
        return "未获取到同行业公司数据"
    
    analysis = []
    
    # 获取报告日期
    report_date = "20250930"
    if financial_data:
        used_data = financial_data.get('used_data', {})
        if used_data:
            profit_data = used_data.get('盈利能力指标', {}).get('毛利率', {})
            if '报告日' in profit_data:
                report_date = profit_data['报告日']
    
    # 获取被分析股票的数据
    target_stock_data = None
    # 首先尝试通过stock_code匹配
    for peer in peers:
        if peer['stock_code'] == ticker.split('.')[0]:
            target_stock_data = peer
            break
    # 如果没找到，尝试通过ticker匹配
    if not target_stock_data:
        for peer in peers:
            if peer['ticker'] == ticker:
                target_stock_data = peer
                break
    
    # 从公司基本信息的scale_comparison中获取数据
    target_company_name = ticker
    target_net_profit = None
    target_total_income = None
    target_market_cap = None
    target_net_profit_rank = None
    target_operating_income_rank = None
    target_total_cap_rank = None
    
    if company_basic:
        scale_comparison = company_basic.get('scale_comparison', [])
        if scale_comparison:
            for item in scale_comparison:
                if item.get('代码') == ticker.split('.')[0] or item.get('简称') == company_basic.get('basic_info', {}).get('公司简称'):
                    target_company_name = item.get('简称', ticker)
                    target_net_profit = item.get('净利润', None)
                    if target_net_profit:
                        target_net_profit = target_net_profit / 100000000  # 转换为亿元
                    target_total_income = item.get('营业收入', None)
                    if target_total_income:
                        target_total_income = target_total_income / 100000000  # 转换为亿元
                    target_market_cap = item.get('总市值', None)
                    if target_market_cap:
                        target_market_cap = target_market_cap / 100000000  # 转换为亿元
                    target_net_profit_rank = item.get('净利润排名', None)
                    target_operating_income_rank = item.get('营业收入排名', None)
                    target_total_cap_rank = item.get('总市值排名', None)
                    break
    
    # 如果scale_comparison中没有数据，从财务指标数据中获取
    if not target_net_profit or not target_total_income:
        if financial_data:
            # 获取公司名称
            target_company_name = financial_data.get('ticker', ticker)
            
            # 从income_statement_summary中获取净利润和营业收入
            income_summary = financial_data.get('income_statement_summary', {})
            if income_summary:
                # 直接获取数据，因为已经是亿元单位
                if not target_net_profit:
                    target_net_profit = income_summary.get('净利润', None)
                if not target_total_income:
                    target_total_income = income_summary.get('营业总收入', None)
            
            # 如果没找到，尝试从used_data中获取
            if (not target_net_profit or target_net_profit == 0) or (not target_total_income or target_total_income == 0):
                used_data = financial_data.get('used_data', {})
                if used_data:
                    # 获取净利润
                    profitability = used_data.get('盈利能力指标', {})
                    if profitability:
                        net_profit_data = profitability.get('净利率', {})
                        if net_profit_data and not target_net_profit:
                            target_net_profit = net_profit_data.get('净利润', None)
                            if target_net_profit:
                                target_net_profit = target_net_profit / 100000000  # 转换为亿元
                    
                    # 获取营业收入
                    revenue_data = profitability.get('毛利率', {})
                    if revenue_data and not target_total_income:
                        target_total_income = revenue_data.get('营业收入', None)
                        if target_total_income:
                            target_total_income = target_total_income / 100000000  # 转换为亿元
    
    # 净利润排名
    net_profit_ranks = [(peer['stock_name'], peer['net_profit'], peer['net_profit_rank']) for peer in peers]
    analysis.append(f"**同行业净利润排名**（{report_date}）：")
    # 先添加被分析股票的数据
    if target_stock_data:
        analysis.append(f"- {target_stock_data['stock_name']}：{target_stock_data['net_profit']:.2f}亿元（排名第{target_stock_data['net_profit_rank']}）")
    elif target_net_profit:
        if target_net_profit_rank:
            analysis.append(f"- {target_company_name}：{target_net_profit:.2f}亿元（排名第{target_net_profit_rank}）")
        else:
            analysis.append(f"- {target_company_name}：{target_net_profit:.2f}亿元（排名：未知）")
    else:
        # 如果没有被分析股票的数据，添加一个占位符
        analysis.append(f"- {target_company_name}：数据缺失")
    # 再添加其他公司的数据
    for name, profit, rank in net_profit_ranks:
        if not target_stock_data or name != target_stock_data['stock_name']:
            analysis.append(f"- {name}：{profit:.2f}亿元（排名第{rank}）")
    
    # 市值对比
    market_cap_ranks = [(peer['stock_name'], peer['total_market_cap'], peer['total_cap_rank']) for peer in peers]
    analysis.append(f"\n**同行业市值排名**（{report_date}）：")
    # 先添加被分析股票的数据
    if target_stock_data:
        analysis.append(f"- {target_stock_data['stock_name']}：{target_stock_data['total_market_cap']:.2f}亿元（排名第{target_stock_data['total_cap_rank']}）")
    elif target_market_cap:
        if target_total_cap_rank:
            analysis.append(f"- {target_company_name}：{target_market_cap:.2f}亿元（排名第{target_total_cap_rank}）")
        else:
            analysis.append(f"- {target_company_name}：{target_market_cap:.2f}亿元（排名：未知）")
    else:
        # 如果没有被分析股票的数据，添加一个占位符
        analysis.append(f"- {target_company_name}：数据缺失")
    # 再添加其他公司的数据
    for name, market_cap, rank in market_cap_ranks:
        if not target_stock_data or name != target_stock_data['stock_name']:
            analysis.append(f"- {name}：{market_cap:.2f}亿元（排名第{rank}）")
    
    # 营业收入对比
    income_ranks = [(peer['stock_name'], peer['total_operating_income'], peer['operating_income_rank']) for peer in peers]
    analysis.append(f"\n**同行业营业收入排名**（{report_date}）：")
    # 先添加被分析股票的数据
    if target_stock_data:
        analysis.append(f"- {target_stock_data['stock_name']}：{target_stock_data['total_operating_income']:.2f}亿元（排名第{target_stock_data['operating_income_rank']}）")
    elif target_total_income:
        if target_operating_income_rank:
            analysis.append(f"- {target_company_name}：{target_total_income:.2f}亿元（排名第{target_operating_income_rank}）")
        else:
            analysis.append(f"- {target_company_name}：{target_total_income:.2f}亿元（排名：未知）")
    else:
        # 如果没有被分析股票的数据，添加一个占位符
        analysis.append(f"- {target_company_name}：数据缺失")
    # 再添加其他公司的数据
    for name, income, rank in income_ranks:
        if not target_stock_data or name != target_stock_data['stock_name']:
            analysis.append(f"- {name}：{income:.2f}亿元（排名第{rank}）")
    
    return '\n'.join(analysis)

def analyze_market_performance(market_data):
    """分析市场表现"""
    if not market_data:
        return "未获取到市场表现数据"
    
    performance = market_data.get('market_performance', [])
    if not performance:
        return "未获取到市场表现数据"
    
    analysis = []
    
    # 确定基准日（最早的日期，CHANGERATE为0）
    base_date = None
    for item in reversed(performance):
        if item['change_rate'] == 0:
            base_date = item['trade_date'].split(' ')[0]
            break
    
    # 最近10个交易日表现
    recent_data = performance[:10]
    analysis.append("**最近10个交易日表现（从基准日开始的累计涨幅）**：")
    if base_date:
        analysis.append(f"- 基准日：{base_date}")
    
    # 提取最近10天的涨跌幅数据
    for item in recent_data:
        date = item['trade_date'].split(' ')[0]
        change = item['change_rate']
        analysis.append(f"- {date}：{change:.2f}%（累计涨幅）")
    
    # 计算最近10个交易日的实际累计涨跌幅
    # 由于CHANGERATE是从基准日开始的累计涨跌幅，我们需要计算两个时间点的差值
    if len(recent_data) >= 2:
        # 最新日期的累计涨跌幅
        latest_change = recent_data[0]['change_rate']
        # 10天前的累计涨跌幅
        ten_days_ago_change = recent_data[-1]['change_rate']
        # 计算实际的10天累计涨跌幅
        actual_10day_change = latest_change - ten_days_ago_change
        analysis.append(f"\n**最近10个交易日期间的累计涨跌幅**：{actual_10day_change:.2f}%")
    else:
        analysis.append("\n**最近10个交易日期间的累计涨跌幅**：数据不足")
    
    # 与行业板块对比
    if recent_data:
        board_name = recent_data[0]['board_name']
        # 计算行业板块的实际10天累计涨跌幅
        if len(recent_data) >= 2:
            latest_board_change = recent_data[0]['board_change_rate']
            ten_days_ago_board_change = recent_data[-1]['board_change_rate']
            actual_board_change = latest_board_change - ten_days_ago_board_change
            analysis.append(f"**行业板块（{board_name}）期间累计涨跌幅**：{actual_board_change:.2f}%")
        else:
            analysis.append(f"**行业板块（{board_name}）期间累计涨跌幅**：数据不足")
    
    return '\n'.join(analysis)

def analyze_dupont_analysis(dupont_data):
    """分析杜邦分析行业排名数据"""
    if not dupont_data:
        return "未获取到杜邦分析行业排名数据"
    
    dupont_analysis = dupont_data.get('dupont_analysis', {})
    if not dupont_analysis:
        return "未获取到杜邦分析行业排名数据"
    
    analysis = []
    
    # 获取报告日期
    report_date = "2024-12-31"
    company_data = dupont_analysis.get('company_data')
    if company_data and 'REPORT_DATE' in company_data:
        report_date = company_data['REPORT_DATE']
    
    # 公司数据
    if company_data:
        analysis.append(f"**公司杜邦分析数据**（{report_date}）：")
        analysis.append(f"- ROE行业排名：第{company_data.get('PAIMING', '未知')}名")
        analysis.append(f"- 平均ROE：{company_data.get('ROE_AVG', 0):.2f}%")
        analysis.append(f"- 平均净利率：{company_data.get('XSJLL_AVG', 0):.2f}%")
        analysis.append(f"- 平均总资产周转率：{company_data.get('TOAZZL_AVG', 0):.2f}%")
        analysis.append(f"- 平均权益乘数：{company_data.get('QYCS_AVG', 0):.2f}%")
    
    # 行业平均数据
    industry_average = dupont_analysis.get('industry_average')
    if industry_average:
        analysis.append(f"\n**行业平均数据**（{report_date}）：")
        analysis.append(f"- 平均ROE：{industry_average.get('ROE_AVG', 0):.2f}%")
        analysis.append(f"- 平均净利率：{industry_average.get('XSJLL_AVG', 0):.2f}%")
        analysis.append(f"- 平均总资产周转率：{industry_average.get('TOAZZL_AVG', 0):.2f}%")
        analysis.append(f"- 平均权益乘数：{industry_average.get('QYCS_AVG', 0):.2f}%")
    
    # 行业中值数据
    industry_median = dupont_analysis.get('industry_median')
    if industry_median:
        analysis.append(f"\n**行业中值数据**（{report_date}）：")
        analysis.append(f"- 平均ROE：{industry_median.get('ROE_AVG', 0):.2f}%")
        analysis.append(f"- 平均净利率：{industry_median.get('XSJLL_AVG', 0):.2f}%")
        analysis.append(f"- 平均总资产周转率：{industry_median.get('TOAZZL_AVG', 0):.2f}%")
        analysis.append(f"- 平均权益乘数：{industry_median.get('QYCS_AVG', 0):.2f}%")
    
    # 行业前5名公司
    top_companies = dupont_analysis.get('top_companies')
    if top_companies:
        analysis.append(f"\n**行业前5名公司**（{report_date}）：")
        for company in top_companies:
            analysis.append(f"- {company.get('stock_name')}（排名第{company.get('PAIMING')}）：ROE {company.get('ROE_AVG', 0):.2f}%")
    
    return '\n'.join(analysis)

def analyze_industry_valuation(valuation_data):
    """分析行业估值排名数据"""
    if not valuation_data:
        return "未获取到行业估值排名数据"
    
    industry_valuation = valuation_data.get('industry_valuation', {})
    if not industry_valuation:
        return "未获取到行业估值排名数据"
    
    analysis = []
    
    # 获取报告日期
    report_date = "2024-12-31"
    company_data = industry_valuation.get('company_data')
    if company_data and 'REPORT_DATE' in company_data:
        report_date = company_data['REPORT_DATE']
    
    # 公司数据
    if company_data:
        analysis.append(f"**公司估值数据**（{report_date}）：")
        analysis.append(f"- 行业排名：第{company_data.get('PAIMING', '未知')}名")
        analysis.append(f"- PE：{company_data.get('PE', 0):.2f}")
        analysis.append(f"- PE_TTM：{company_data.get('PE_TTM', 0):.2f}")
        analysis.append(f"- PB：{company_data.get('PB', 0):.2f}")
        analysis.append(f"- PEG：{company_data.get('PEG', 0):.2f}")
    
    # 行业平均数据
    industry_average = industry_valuation.get('industry_average')
    if industry_average:
        analysis.append(f"\n**行业平均估值**（{report_date}）：")
        analysis.append(f"- PE：{industry_average.get('PE', 0):.2f}")
        analysis.append(f"- PE_TTM：{industry_average.get('PE_TTM', 0):.2f}")
        analysis.append(f"- PB：{industry_average.get('PB', 0):.2f}")
        analysis.append(f"- PEG：{industry_average.get('PEG', 0):.2f}")
    
    # 行业中值数据
    industry_median = industry_valuation.get('industry_median')
    if industry_median:
        analysis.append(f"\n**行业中值估值**（{report_date}）：")
        analysis.append(f"- PE：{industry_median.get('PE', 0):.2f}")
        analysis.append(f"- PE_TTM：{industry_median.get('PE_TTM', 0):.2f}")
        analysis.append(f"- PB：{industry_median.get('PB', 0):.2f}")
        analysis.append(f"- PEG：{industry_median.get('PEG', 0):.2f}")
    
    # 行业前5名公司
    top_companies = industry_valuation.get('top_companies')
    if top_companies:
        analysis.append(f"\n**行业前5名公司估值**（{report_date}）：")
        for company in top_companies:
            analysis.append(f"- {company.get('stock_name')}（排名第{company.get('PAIMING')}）：PE {company.get('PE', 0):.2f}，PB {company.get('PB', 0):.2f}，PEG {company.get('PEG', 0):.2f}")
    
    return '\n'.join(analysis)

def analyze_industry_growth(growth_data):
    """分析行业成长能力排名数据"""
    if not growth_data:
        return "未获取到行业成长能力排名数据"
    
    industry_growth = growth_data.get('industry_growth', {})
    if not industry_growth:
        return "未获取到行业成长能力排名数据"
    
    analysis = []
    
    # 获取报告日期
    report_date = "2024-12-31"
    company_data = industry_growth.get('company_data')
    if company_data and 'REPORT_DATE' in company_data:
        report_date = company_data['REPORT_DATE']
    
    # 公司数据
    if company_data:
        analysis.append(f"**公司成长能力数据**（{report_date}）：")
        analysis.append(f"- 行业排名：第{company_data.get('PAIMING', '未知')}名")
        analysis.append(f"- 营业收入同比：{company_data.get('YYSRTB', 0):.2f}%")
        analysis.append(f"- 净利润同比：{company_data.get('JLRTB', 0):.2f}%")
        analysis.append(f"- 每股收益同比：{company_data.get('MGSYTB', 0):.2f}%")
        analysis.append(f"- 净利润3年复合增长率：{company_data.get('JLR_3Y', 0):.2f}%")
        analysis.append(f"- 营业收入3年复合增长率：{company_data.get('YYSR_3Y', 0):.2f}%")
        analysis.append(f"- 净利润1年预测增长率：{company_data.get('JLR_1E', 0) or 0:.2f}%")
        analysis.append(f"- 净利润2年预测增长率：{company_data.get('JLR_2E', 0) or 0:.2f}%")
        analysis.append(f"- 净利润3年预测增长率：{company_data.get('JLR_3E', 0) or 0:.2f}%")
    
    # 行业平均数据
    industry_average = industry_growth.get('industry_average')
    if industry_average:
        analysis.append(f"\n**行业平均成长能力**（{report_date}）：")
        analysis.append(f"- 营业收入同比：{industry_average.get('YYSRTB', 0) or 0:.2f}%")
        analysis.append(f"- 净利润同比：{industry_average.get('JLRTB', 0) or 0:.2f}%")
        analysis.append(f"- 净利润3年复合增长率：{industry_average.get('JLR_3Y', 0) or 0:.2f}%")
        analysis.append(f"- 营业收入3年复合增长率：{industry_average.get('YYSR_3Y', 0) or 0:.2f}%")
    
    # 行业中值数据
    industry_median = industry_growth.get('industry_median')
    if industry_median:
        analysis.append(f"\n**行业中值成长能力**（{report_date}）：")
        analysis.append(f"- 营业收入同比：{industry_median.get('YYSRTB', 0) or 0:.2f}%")
        analysis.append(f"- 净利润同比：{industry_median.get('JLRTB', 0) or 0:.2f}%")
        analysis.append(f"- 净利润3年复合增长率：{industry_median.get('JLR_3Y', 0) or 0:.2f}%")
        analysis.append(f"- 营业收入3年复合增长率：{industry_median.get('YYSR_3Y', 0) or 0:.2f}%")
    
    # 行业前5名公司
    top_companies = industry_growth.get('top_companies')
    if top_companies:
        analysis.append(f"\n**行业前5名公司成长能力**（{report_date}）：")
        for company in top_companies:
            analysis.append(f"- {company.get('stock_name')}（排名第{company.get('PAIMING')}）：营业收入同比 {company.get('YYSRTB', 0) or 0:.2f}%，净利润同比 {company.get('JLRTB', 0) or 0:.2f}%，净利润3年复合增长率 {company.get('JLR_3Y', 0) or 0:.2f}%")
    
    return '\n'.join(analysis)

def generate_analysis_report(ticker, data):
    """生成综合分析报告"""
    report = f"# {ticker} 综合分析报告\n\n"
    
    # 时效性警告
    current_date = datetime.now().strftime('%Y%m%d')
    # 确定数据截止日期
    data_cutoff_date = "20250930"  # 默认值
    if data['financial_indicators']:
        used_data = data['financial_indicators'].get('used_data', {})
        if used_data:
            profit_data = used_data.get('盈利能力指标', {}).get('毛利率', {})
            if '报告日' in profit_data:
                data_cutoff_date = profit_data['报告日']
    report += f"【时效性警告】数据截止{data_cutoff_date}，当前为{current_date}，分析时请考虑时效性对投资决策的影响\n\n"
    
    # 报告时间
    report += f"## 分析时间\n{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
    
    # 公司基本信息
    if data['company_basic']:
        basic_info = data['company_basic'].get('basic_info', {})
        financial_abstract = data['company_basic'].get('financial_abstract', [])
        scale_comparison = data['company_basic'].get('scale_comparison', [])
        
        report += "## 公司基本信息\n"
        
        # 输出基本信息的所有字段
        for key, value in basic_info.items():
            if value is not None:
                report += f"- {key}：{value}\n"
        
        # 输出最近8个季度的财务摘要
        if financial_abstract:
            report += "\n## 最近8个季度财务摘要\n"
            # 检查financial_abstract的类型
            if isinstance(financial_abstract, list):
                recent_quarters = financial_abstract[:8]  # 取最近的8个季度
                for quarter in recent_quarters:
                    report += f"- {quarter.get('quarter', '未知')}：\n"
                    report += f"  营业总收入：{quarter.get('revenue', '未知')}亿元\n"
                    report += f"  净利润：{quarter.get('net_profit', '未知')}亿元\n"
                    report += f"  同比增长：{quarter.get('growth_rate', '未知')}%\n"
            elif isinstance(financial_abstract, dict):
                # 提取季度数据
                quarter_data = {}
                for key, value in financial_abstract.items():
                    # 检查是否是季度数据（格式：YYYYMMDD）
                    if len(key) == 8 and key.isdigit():
                        quarter_data[key] = value
                
                # 按季度降序排序
                sorted_quarters = sorted(quarter_data.keys(), reverse=True)
                # 取最近8个季度
                recent_quarters = sorted_quarters[:8]
                
                # 输出最近8个季度的数据
                for quarter in recent_quarters:
                    value = quarter_data[quarter]
                    # 转换为亿元单位
                    value_in_yuan = value / 100000000
                    report += f"- {quarter}：{value_in_yuan:.2f}亿元\n"
        
        # 输出规模对比信息
        if scale_comparison:
            report += "\n## 规模对比信息\n"
            # 检查scale_comparison的类型
            if isinstance(scale_comparison, list):
                for company in scale_comparison:
                    report += f"- {company.get('简称', '未知')}：\n"
                    report += f"  总市值：{company.get('总市值', '未知')/100000000 if isinstance(company.get('总市值'), (int, float)) else company.get('总市值')}亿元\n"
                    report += f"  总市值排名：{company.get('总市值排名', '未知')}\n"
                    report += f"  流通市值：{company.get('流通市值', '未知')}亿元\n"
                    report += f"  流通市值排名：{company.get('流通市值排名', '未知')}\n"
                    report += f"  营业收入：{company.get('营业收入', '未知')/100000000 if isinstance(company.get('营业收入'), (int, float)) else company.get('营业收入')}亿元\n"
                    report += f"  营业收入排名：{company.get('营业收入排名', '未知')}\n"
                    report += f"  净利润：{company.get('净利润', '未知')/100000000 if isinstance(company.get('净利润'), (int, float)) else company.get('净利润')}亿元\n"
                    report += f"  净利润排名：{company.get('净利润排名', '未知')}\n"
            elif isinstance(scale_comparison, dict):
                # 如果是字典，直接输出所有内容
                for key, value in scale_comparison.items():
                    report += f"- {key}：{value}\n"
        
        report += "\n"
    
    # 财务健康分析
    report += "## 财务健康分析\n"
    report += analyze_financial_health(data['financial_indicators'])
    report += "\n\n"
    
    # 行业地位分析
    report += "## 行业地位分析\n"
    report += analyze_industry_position(data['industry_peers'], ticker, data['financial_indicators'], data['company_basic'])
    report += "\n\n"
    
    # 市场表现分析
    report += "## 市场表现分析\n"
    report += analyze_market_performance(data['market_performance'])
    report += "\n\n"
    
    # 杜邦分析行业排名
    report += "## 杜邦分析行业排名\n"
    report += analyze_dupont_analysis(data['dupont_analysis'])
    report += "\n\n"
    
    # 行业估值排名
    report += "## 行业估值排名\n"
    report += analyze_industry_valuation(data['industry_valuation'])
    report += "\n\n"
    
    # 行业成长能力排名
    report += "## 行业成长能力排名\n"
    report += analyze_industry_growth(data['industry_growth'])
    report += "\n\n"
    
    # 综合评估
    report += "## 综合评估\n"
    report += "### 优势\n"
    report += "1. 财务状况稳健，现金流状况良好\n"
    report += "2. 在同行业中具有较强的竞争力\n"
    report += "3. 市场表现相对行业板块具有一定优势\n\n"
    
    report += "### 风险\n"
    report += "1. 行业竞争激烈，需关注市场份额变化\n"
    report += "2. 宏观经济环境变化可能影响公司业绩\n"
    report += "3. 需关注行业政策变化带来的影响\n\n"
    
    report += "### 投资建议\n"
    report += "基于综合分析，建议投资者：\n"
    report += "1. 密切关注公司季度业绩变化\n"
    report += "2. 关注同行业竞争格局变化\n"
    report += "3. 结合市场环境和个人风险偏好做出投资决策\n"
    
    return report

def save_prompt(ticker, prompt):
    """保存提示词"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    filename = f"{ticker}_peer_comparison_prompt.txt"
    file_path = os.path.join(stock_dir, filename)
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"提示词已保存到: {file_path}")
    return file_path

def get_ai_analysis(ticker, prompt):
    """获取AI分析结果"""
    try:
        import ollama
        
        print(f"正在请求本地Ollama AI ({AI_CONFIG['model']})...")
        client = ollama.Client(host=AI_CONFIG['base_url'])
        
        response = client.chat(
            model=AI_CONFIG['model'],
            messages=[
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从多个维度分析股票的投资价值。"},
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

def save_report(ticker, report):
    """保存分析报告"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"{ticker}_peer_comparison_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"综合分析报告已保存到: {file_path}")
    return file_path

def build_prompt(ticker, data):
    """构建综合分析提示词"""
    # 时效性警告
    current_date = datetime.now().strftime('%Y%m%d')
    # 确定数据截止日期
    data_cutoff_date = "20250930"  # 默认值
    if data['financial_indicators']:
        used_data = data['financial_indicators'].get('used_data', {})
        if used_data:
            profit_data = used_data.get('盈利能力指标', {}).get('毛利率', {})
            if '报告日' in profit_data:
                data_cutoff_date = profit_data['报告日']
    prompt = f"【时效性警告】数据截止{data_cutoff_date}，当前为{current_date}，分析时请考虑时效性对投资决策的影响\n\n"
    prompt += f"你是一位专业的量化投资分析师，擅长从多个维度分析股票的投资价值。请基于以下股票的综合数据，进行全面的投资分析：\n\n"
    
    prompt += f"=== 股票基本信息 ===\n"
    prompt += f"股票代码: {ticker}\n"
    
    # 添加公司基本信息
    if data['company_basic']:
        basic_info = data['company_basic'].get('basic_info', {})
        financial_abstract = data['company_basic'].get('financial_abstract', [])
        scale_comparison = data['company_basic'].get('scale_comparison', [])
        
        prompt += "\n=== 公司基本信息 ===\n"
        # 输出基本信息的所有字段
        for key, value in basic_info.items():
            if value is not None:
                prompt += f"{key}：{value}\n"
        
        # 输出最近8个季度的财务摘要
        if financial_abstract:
            prompt += "\n=== 最近8个季度财务摘要 ===\n"
            # 检查financial_abstract的类型
            if isinstance(financial_abstract, list):
                recent_quarters = financial_abstract[:8]  # 取最近的8个季度
                for quarter in recent_quarters:
                    prompt += f"{quarter.get('quarter', '未知')}：\n"
                    prompt += f"  营业总收入：{quarter.get('revenue', '未知')}亿元\n"
                    prompt += f"  净利润：{quarter.get('net_profit', '未知')}亿元\n"
                    prompt += f"  同比增长：{quarter.get('growth_rate', '未知')}%\n"
            elif isinstance(financial_abstract, dict):
                # 提取季度数据
                quarter_data = {}
                for key, value in financial_abstract.items():
                    # 检查是否是季度数据（格式：YYYYMMDD）
                    if len(key) == 8 and key.isdigit():
                        quarter_data[key] = value
                
                # 按季度降序排序
                sorted_quarters = sorted(quarter_data.keys(), reverse=True)
                # 取最近8个季度
                recent_quarters = sorted_quarters[:8]
                
                # 输出最近8个季度的数据
                for quarter in recent_quarters:
                    value = quarter_data[quarter]
                    # 转换为亿元单位
                    value_in_yuan = value / 100000000
                    prompt += f"{quarter}：{value_in_yuan:.2f}亿元\n"
        
        # 输出规模对比信息
        if scale_comparison:
            prompt += "\n=== 规模对比信息 ===\n"
            # 检查scale_comparison的类型
            if isinstance(scale_comparison, list):
                for company in scale_comparison:
                    prompt += f"{company.get('简称', '未知')}：\n"
                    prompt += f"  总市值：{company.get('总市值', '未知')/100000000 if isinstance(company.get('总市值'), (int, float)) else company.get('总市值')}亿元\n"
                    prompt += f"  总市值排名：{company.get('总市值排名', '未知')}\n"
                    prompt += f"  流通市值：{company.get('流通市值', '未知')}亿元\n"
                    prompt += f"  流通市值排名：{company.get('流通市值排名', '未知')}\n"
                    prompt += f"  营业收入：{company.get('营业收入', '未知')/100000000 if isinstance(company.get('营业收入'), (int, float)) else company.get('营业收入')}亿元\n"
                    prompt += f"  营业收入排名：{company.get('营业收入排名', '未知')}\n"
                    prompt += f"  净利润：{company.get('净利润', '未知')/100000000 if isinstance(company.get('净利润'), (int, float)) else company.get('净利润')}亿元\n"
                    prompt += f"  净利润排名：{company.get('净利润排名', '未知')}\n"
            elif isinstance(scale_comparison, dict):
                # 如果是字典，直接输出所有内容
                for key, value in scale_comparison.items():
                    prompt += f"{key}：{value}\n"
    
    # 添加行业信息
    if data['industry_info']:
        industry_info = data['industry_info']
        prompt += "\n=== 行业信息 ===\n"
        prompt += f"行业层级：{industry_info.get('industry_level', '未知')}\n"
        prompt += f"一级行业：{industry_info.get('level1_industry', '未知')}\n"
        prompt += f"二级行业：{industry_info.get('level2_industry', '未知')}\n"
        prompt += f"三级行业：{industry_info.get('level3_industry', '未知')}\n"
        prompt += f"行业代码：{industry_info.get('industry_code', '未知')}\n"
        prompt += f"行业名称：{industry_info.get('industry_name', '未知')}\n"
        
        # 输出行业平均信息
        industry_average = industry_info.get('industry_average', {})
        if industry_average:
            prompt += "\n=== 行业平均信息 ===\n"
            prompt += f"平均市值：{industry_average.get('平均市值(亿元)', '未知')}亿元\n"
            prompt += f"平均市盈率：{industry_average.get('平均市盈率', '未知')}\n"
            prompt += f"平均市盈率TTM：{industry_average.get('平均市盈率TTM', '未知')}\n"
            prompt += f"平均市净率：{industry_average.get('平均市净率', '未知')}\n"
            prompt += f"平均股息率：{industry_average.get('平均股息率(%)', '未知')}%\n"
            prompt += f"平均价格：{industry_average.get('平均价格(元)', '未知')}元\n"
            prompt += f"平均营收增长率(09-30)：{industry_average.get('平均营收增长率(09-30)(%)', '未知')}%\n"
            prompt += f"平均净利润增长率(09-30)：{industry_average.get('平均净利润增长率(09-30)(%)', '未知')}%\n"
            prompt += f"平均营收增长率(06-30)：{industry_average.get('平均营收增长率(06-30)(%)', '未知')}%\n"
            prompt += f"平均净利润增长率(06-30)：{industry_average.get('平均净利润增长率(06-30)(%)', '未知')}%\n"
    
    # 添加财务健康分析
    prompt += "\n=== 财务健康分析 ===\n"
    prompt += analyze_financial_health(data['financial_indicators'])
    prompt += "\n"
    
    # 添加行业地位分析
    prompt += "\n=== 行业地位分析 ===\n"
    prompt += analyze_industry_position(data['industry_peers'], ticker, data['financial_indicators'], data['company_basic'])
    prompt += "\n"
    
    # 添加市场表现分析
    prompt += "\n=== 市场表现分析 ===\n"
    prompt += analyze_market_performance(data['market_performance'])
    prompt += "\n"
    
    # 添加杜邦分析行业排名
    prompt += "\n=== 杜邦分析行业排名 ===\n"
    prompt += analyze_dupont_analysis(data['dupont_analysis'])
    prompt += "\n"
    
    # 添加行业估值排名
    prompt += "\n=== 行业估值排名 ===\n"
    prompt += analyze_industry_valuation(data['industry_valuation'])
    prompt += "\n"
    
    # 添加行业成长能力排名
    prompt += "\n=== 行业成长能力排名 ===\n"
    prompt += analyze_industry_growth(data['industry_growth'])
    prompt += "\n"
    
    # 添加分析要求
    prompt += "\n=== 分析要求 ===\n"
    prompt += "**数据说明**：上文数据可能存在个别冲突情况，主要是由于不同数据源的统计口径不同所致。例如市值排名中可能出现相同排名的情况，这属于正常现象。\n\n"
    prompt += "请从以下几个方面进行综合分析：\n"
    prompt += "1. 公司基本面分析：财务状况、业务模式、竞争优势\n"
    prompt += "2. 行业分析：行业地位、竞争格局、发展趋势\n"
    prompt += "3. 市场表现分析：股价走势、相对大盘表现\n"
    prompt += "4. 估值分析：与行业平均水平对比，估值合理性\n"
    prompt += "5. 成长能力分析：历史增长趋势、未来增长预期\n"
    prompt += "6. 风险评估：行业风险、公司特有风险\n"
    prompt += "7. 投资建议：基于综合分析的投资策略建议\n"
    prompt += "8. 结论：总结公司的投资价值和风险\n"
    prompt += "\n请提供详细、专业的分析，基于数据和量化指标，避免泛泛而谈。"
    
    return prompt

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="整合数据并生成综合分析报告")
    parser.add_argument('--ticker', default='002384.SZ', help="股票代码，例如：002384.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"处理股票: {ticker}")
    
    # 加载数据
    data = load_data(ticker)
    
    # 构建提示词
    prompt = build_prompt(ticker, data)
    
    # 保存提示词
    save_prompt(ticker, prompt)
    
    # 生成分析报告
    report = generate_analysis_report(ticker, data)
    
    # 获取AI分析
    ai_analysis = get_ai_analysis(ticker, prompt)
    
    # 合并分析结果
    # final_report = report + "\n## 人工智能深度分析\n" + ai_analysis
    final_report = ai_analysis
    # 保存报告
    save_report(ticker, final_report)
    
    print("\n综合分析报告生成完成！")

if __name__ == "__main__":
    main()