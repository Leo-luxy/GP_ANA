
# analyze_financial_statements.py
# 功能：分析company_info.json文件中的财务报表数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的company_info.json文件
# 2. 提取其中的财务报表相关数据
# 3. 构建AI分析提示词
# 4. 通过API访问本地ollama
# 5. 获取AI分析结果
# 6. 将结果保存到该股票的文件夹里

import json
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG

def load_company_info(ticker):
    """加载公司信息文件"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    
    # 加载公司基本信息
    basic_info_file = os.path.join(stock_dir, f"{ticker}_company_basic.json")
    if not os.path.exists(basic_info_file):
        print(f"公司基本信息文件不存在: {basic_info_file}")
        return None
    
    try:
        with open(basic_info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {ticker} 的公司基本信息文件: {basic_info_file}")
    except Exception as e:
        print(f"加载公司基本信息文件时出错: {str(e)}")
        return None
    
    # 加载财务报表数据
    import pandas as pd
    
    # 加载利润表数据
    profit_file = os.path.join(stock_dir, f"{ticker}_financial_profit.csv")
    if os.path.exists(profit_file):
        try:
            profit_df = pd.read_csv(profit_file)
            data['financial_report'] = data.get('financial_report', {})
            data['financial_report']['profit'] = profit_df.to_dict('records')
            print(f"成功加载 {ticker} 的利润表数据: {profit_file}")
        except Exception as e:
            print(f"加载利润表数据时出错: {str(e)}")
    
    # 加载资产负债表数据
    balance_file = os.path.join(stock_dir, f"{ticker}_financial_balance.csv")
    if os.path.exists(balance_file):
        try:
            balance_df = pd.read_csv(balance_file)
            data['financial_report'] = data.get('financial_report', {})
            data['financial_report']['balance'] = balance_df.to_dict('records')
            print(f"成功加载 {ticker} 的资产负债表数据: {balance_file}")
        except Exception as e:
            print(f"加载资产负债表数据时出错: {str(e)}")
    
    # 加载计算的财务指标数据
    financial_indicators_file = os.path.join(stock_dir, f"{ticker}_financial_indicators_calculated.json")
    if os.path.exists(financial_indicators_file):
        try:
            with open(financial_indicators_file, 'r', encoding='utf-8') as f:
                financial_indicators_data = json.load(f)
            data['financial_indicators_calculated'] = financial_indicators_data
            print(f"成功加载 {ticker} 的计算财务指标数据: {financial_indicators_file}")
        except Exception as e:
            print(f"加载计算财务指标数据时出错: {str(e)}")
    
    # 加载行业信息数据
    industry_info_file = os.path.join(stock_dir, f"{ticker}_industry_info.json")
    if os.path.exists(industry_info_file):
        try:
            with open(industry_info_file, 'r', encoding='utf-8') as f:
                industry_info_data = json.load(f)
            data['industry_info'] = industry_info_data
            print(f"成功加载 {ticker} 的行业信息数据: {industry_info_file}")
        except Exception as e:
            print(f"加载行业信息数据时出错: {str(e)}")
    
    return data

def extract_financial_data(data):
    """提取财务报表相关数据"""
    financial_data = {}
    
    # 提取财务报表数据
    if 'financial_report' in data:
        financial_data['financial_report'] = data['financial_report']
    
    # 提取完整的公司基本信息
    if 'basic_info' in data:
        financial_data['basic_info'] = data['basic_info']
    
    # 提取规模对比数据
    if 'scale_comparison' in data:
        financial_data['scale_comparison'] = data['scale_comparison']
    
    # 提取财务摘要数据（取最近8组）
    if 'financial_abstract' in data:
        financial_abstract = data['financial_abstract']
        if isinstance(financial_abstract, dict):
            # 转换为列表并按日期排序
            abstract_list = []
            for date, value in financial_abstract.items():
                abstract_list.append({'日期': date, '值': value})
            # 按日期降序排序
            abstract_list.sort(key=lambda x: x['日期'], reverse=True)
            # 取最近8组
            financial_data['financial_abstract'] = abstract_list[:8]
        else:
            financial_data['financial_abstract'] = financial_abstract
    
    # 提取计算的财务指标数据
    if 'financial_indicators_calculated' in data:
        financial_data['financial_indicators_calculated'] = data['financial_indicators_calculated']
    
    # 提取行业信息数据
    if 'industry_info' in data:
        financial_data['industry_info'] = data['industry_info']
    
    return financial_data

def build_prompt(ticker, financial_data):
    """构建AI分析提示词"""
    # 添加时效性提示
    current_date = datetime.now().strftime('%Y%m%d')
    prompt = f"""【时效性警告】数据截止20250930，当前为{current_date}，分析时请考虑时效性对投资决策的影响

你是一位专业的量化投资分析师，擅长从财务报表角度分析股票的投资价值。请基于以下股票的财务报表相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 财务报表数据 ===
"""
    
    # 添加基本信息
    if 'basic_info' in financial_data:
        prompt += "公司基本信息:\n"
        for key, value in financial_data['basic_info'].items():
            if key == '注册资本' and isinstance(value, (int, float)):
                # 注册资本单位为万元
                if value > 10000:
                    value_billion = round(value / 10000, 2)
                    prompt += f"- {key}(亿元): {value_billion}\n"
                else:
                    prompt += f"- {key}(万元): {value}\n"
            else:
                prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加规模对比数据
    if 'scale_comparison' in financial_data:
        prompt += "规模对比数据:\n"
        scale_comparison = financial_data['scale_comparison']
        if isinstance(scale_comparison, list):
            for i, item in enumerate(scale_comparison):
                if isinstance(item, dict):
                    prompt += f"第{i+1}组规模对比数据:\n"
                    for key, value in item.items():
                        # 转换单位为亿元
                        if isinstance(value, (int, float)) and abs(value) > 100000000:
                            value = round(value / 100000000, 2)
                            prompt += f"- {key}（亿元）: {value}\n"
                        else:
                            prompt += f"- {key}: {value}\n"
                    prompt += "\n"
        elif isinstance(scale_comparison, dict):
            for key, value in scale_comparison.items():
                # 转换单位为亿元
                if isinstance(value, (int, float)):
                    if key in ['总市值', '流通市值', '营业收入', '净利润']:
                        if abs(value) > 100000000:
                            value = round(value / 100000000, 2)
                        prompt += f"- {key}（亿元）: {value}\n"
                    else:
                        prompt += f"- {key}: {value}\n"
                else:
                    prompt += f"- {key}: {value}\n"
            prompt += "\n"
    
    # 添加财务摘要数据
    if 'financial_abstract' in financial_data:
        prompt += "财务摘要数据（亿元）:\n"
        financial_abstract = financial_data['financial_abstract']
        if isinstance(financial_abstract, list):
            # 财务摘要已处理为最近8组
            for item in financial_abstract:
                date = item.get('日期', '未知日期')
                value = item.get('值', '未知值')
                # 转换单位为亿元
                if isinstance(value, (int, float)) and abs(value) > 100000000:
                    value = round(value / 100000000, 2)
                prompt += f"- {date}: {value}\n"
        elif isinstance(financial_abstract, dict):
            # 提取最近的8个季度数据
            import pandas as pd
            # 转换为DataFrame
            df = pd.DataFrame(list(financial_abstract.items()), columns=['日期', '值'])
            # 按日期排序
            df = df.sort_values('日期', ascending=False)
            # 取最近的8个季度
            recent_data = df.head(8).to_dict('records')
            
            for item in recent_data:
                # 转换单位为亿元
                value = item['值']
                if isinstance(value, (int, float)) and abs(value) > 100000000:
                    value = round(value / 100000000, 2)
                prompt += f"- {item['日期']}: {value}\n"
        prompt += "\n"
    
    # 添加财务报表数据
    if 'financial_report' in financial_data:
        financial_report = financial_data['financial_report']
        
        # 添加利润表数据
        if 'profit' in financial_report:
            prompt += "利润表数据（亿元）:\n"
            profit_data = financial_report['profit']
            if isinstance(profit_data, list):
                # 按报告日排序，取最近的3个报告期
                import pandas as pd
                df = pd.DataFrame(profit_data)
                if '报告日' in df.columns:
                    df = df.sort_values('报告日', ascending=False)
                    # 取最近的3个报告期
                    recent_data = df.head(3).to_dict('records')
                    
                    for i, item in enumerate(recent_data):
                        report_date = item.get('报告日', '未知日期')
                        prompt += f"第{i+1}期（{report_date}）:\n"
                        # 提取核心利润表指标
                        key_profit_fields = [
                            '营业总收入', '营业收入', '营业总成本', '营业成本', 
                            '研发费用', '销售费用', '管理费用', '财务费用',
                            '投资收益', '营业利润', '利润总额', '净利润',
                            '归属于母公司所有者的净利润'
                        ]
                        for field in key_profit_fields:
                            if field in item:
                                value = item[field]
                                # 转换单位为亿元
                                if isinstance(value, (int, float)):
                                    # 对于所有财务指标，统一转换为亿元
                                    value = round(value / 100000000, 2)
                                if field == '营业总成本':
                                    prompt += f"- {field}: {value}（包含税金及附加等未列示项目）\n"
                                else:
                                    prompt += f"- {field}: {value}\n"
                        prompt += "\n"
            prompt += "\n"
        
        # 添加资产负债表数据
        if 'balance' in financial_report:
            prompt += "资产负债表数据（亿元）:\n"
            balance_data = financial_report['balance']
            if isinstance(balance_data, list):
                # 按报告日排序，取最近的3个报告期
                import pandas as pd
                df = pd.DataFrame(balance_data)
                if '报告日' in df.columns:
                    df = df.sort_values('报告日', ascending=False)
                    # 取最近的3个报告期
                    recent_data = df.head(3).to_dict('records')
                    
                    for i, item in enumerate(recent_data):
                        report_date = item.get('报告日', '未知日期')
                        prompt += f"第{i+1}期（{report_date}）:\n"
                        # 提取核心资产负债表指标
                        key_balance_fields = [
                            '资产总计', '负债总计', '所有者权益(或股东权益)合计',
                            '流动资产合计', '流动负债合计', '非流动资产合计', '非流动负债合计'
                        ]
                        for field in key_balance_fields:
                            if field in item:
                                value = item[field]
                                # 转换单位为亿元
                                if isinstance(value, (int, float)) and abs(value) > 100000000:
                                    value = round(value / 100000000, 2)
                                prompt += f"- {field}: {value}\n"
                        prompt += "\n"
            prompt += "\n"
    
    # 添加计算的财务指标数据
    if 'financial_indicators_calculated' in financial_data:
        prompt += "计算的财务指标数据:\n"
        financial_indicators = financial_data['financial_indicators_calculated']
        
        # 获取数据时间
        data_time = ""
        if 'used_data' in financial_indicators:
            used_data = financial_indicators['used_data']
            if '盈利能力指标' in used_data and '毛利率' in used_data['盈利能力指标']:
                data_time = used_data['盈利能力指标']['毛利率'].get('报告日', '')
        # 如果没有获取到时间，尝试从其他数据中获取
        if not data_time and 'financial_report' in financial_data:
            financial_report = financial_data['financial_report']
            if 'profit' in financial_report and isinstance(financial_report['profit'], list) and financial_report['profit']:
                # 取最新的报告日
                import pandas as pd
                df = pd.DataFrame(financial_report['profit'])
                if '报告日' in df.columns:
                    df = df.sort_values('报告日', ascending=False)
                    data_time = df.iloc[0]['报告日'] if not df.empty else ''
        # 如果仍然没有获取到时间，使用当前年份的9月30日
        if not data_time:
            current_year = datetime.now().year
            data_time = f"{current_year}0930"
        
        # 添加计算的指标
        if 'calculated_indicators' in financial_indicators:
            calculated_indicators = financial_indicators['calculated_indicators']
            
            # 盈利能力指标
            if '盈利能力指标' in calculated_indicators:
                prompt += f"盈利能力指标（{data_time}）:\n"
                for key, value in calculated_indicators['盈利能力指标'].items():
                    # 为比率添加%
                    if key in ['毛利率', '净利率', '营业利润率', '营收同比增长率', '净利润同比增长率']:
                        prompt += f"- {key}: {value}%\n"
                    else:
                        # 转换单位为亿元
                        if isinstance(value, (int, float)) and key == 'EBITDA':
                            value = round(value / 100000000, 2)
                            prompt += f"- {key}（亿元）: {value}\n"
                        elif key in ['基本每股收益', '稀释每股收益']:
                            prompt += f"- {key}（元）: {value}\n"
                        else:
                            prompt += f"- {key}: {value}\n"
                # 从数据中计算ROE和ROA
                if 'used_data' in financial_indicators:
                    used_data = financial_indicators['used_data']
                    # 计算ROE和ROA
                    if '盈利能力指标' in used_data and '净利率' in used_data['盈利能力指标'] and '偿债能力指标' in used_data:
                        net_profit = used_data['盈利能力指标']['净利率'].get('净利润', 0)
                        total_assets = used_data['偿债能力指标'].get('资产负债率', {}).get('资产总计', 0)
                        equity = total_assets - used_data['偿债能力指标'].get('资产负债率', {}).get('负债合计', 0)
                        if net_profit and total_assets and equity:
                            # 转换为亿元
                            net_profit_billion = net_profit / 100000000
                            total_assets_billion = total_assets / 100000000
                            equity_billion = equity / 100000000
                            # 计算ROE和ROA（前三季度累计）
                            roe = (net_profit_billion / equity_billion) * 100
                            roa = (net_profit_billion / total_assets_billion) * 100
                            prompt += f"- ROE (2025年前三季度累计): {round(roe, 2)}%\n"
                            prompt += f"- ROA (2025年前三季度累计): {round(roa, 2)}%\n"
                            prompt += f"- 所有者权益合计（亿元）: {round(equity_billion, 2)}\n"
                prompt += "\n"
            
            # 偿债能力指标
            if '偿债能力指标' in calculated_indicators:
                prompt += f"偿债能力指标（{data_time}）:\n"
                for key, value in calculated_indicators['偿债能力指标'].items():
                    # 为比率添加%
                    if key in ['资产负债率']:
                        prompt += f"- {key}: {value}%\n"
                    elif key == '利息保障倍数':
                        prompt += f"- {key}（倍）: {value}\n"
                    else:
                        prompt += f"- {key}: {value}\n"
                prompt += "\n"
            
            # 运营能力指标
            if '运营能力指标' in calculated_indicators:
                prompt += f"运营能力指标（{data_time}）:\n"
                for key, value in calculated_indicators['运营能力指标'].items():
                    # 为周转率添加单位（次）
                    if '周转率' in key:
                        prompt += f"- {key}（次）: {value}\n"
                    else:
                        prompt += f"- {key}: {value}\n"
                prompt += "\n"
            
            # 现金流指标
            if '现金流指标' in calculated_indicators:
                prompt += f"现金流指标（{data_time}）:\n"
                for key, value in calculated_indicators['现金流指标'].items():
                    # 为比率添加单位
                    if key == '经营活动现金流量净额/净利润':
                        # 经营活动现金流量净额/净利润是倍数
                        prompt += f"- {key}: {value}（倍）\n"
                    elif key == '经营活动现金流量净额/营业收入':
                        # 经营活动现金流量净额/营业收入是比值
                        prompt += f"- {key}: {value}\n"
                    else:
                        # 转换单位为亿元
                        if isinstance(value, (int, float)) and abs(value) > 100000000:
                            value = round(value / 100000000, 2)
                        prompt += f"- {key}: {value}\n"
                prompt += "\n"
            
            # 成长能力指标
            if '成长能力指标' in calculated_indicators:
                prompt += f"成长能力指标（{data_time}）:\n"
                for key, value in calculated_indicators['成长能力指标'].items():
                    # 为比率添加%
                    if '增长率' in key:
                        # 明确时间口径
                        if '单季' in key:
                            prompt += f"- {key} (单季): {value}%\n"
                        else:
                            prompt += f"- {key} (累计): {value}%\n"
                    else:
                        prompt += f"- {key}: {value}\n"
                prompt += "\n"
        
        # 添加历史趋势
        if 'historical_trends' in financial_indicators:
            prompt += "历史趋势数据:\n"
            historical_trends = financial_indicators['historical_trends']
            for key, value in historical_trends.items():
                prompt += f"{key}:\n"
                for period, val in value.items():
                    prompt += f"- {period}: {val}\n"
                prompt += "\n"
        
        # 添加行业基准
        if 'industry_info' in financial_data and 'industry_average' in financial_data['industry_info']:
            industry_average = financial_data['industry_info']['industry_average']
            industry_name = financial_data['industry_info'].get('industry_name', '行业')
            prompt += f"行业基准（{industry_name}）:\n"
            for key, value in industry_average.items():
                # 直接输出，因为字段名已经包含了单位
                prompt += f"- {key}: {value}\n"
            prompt += "\n"
        elif 'industry_benchmark_note' in financial_indicators:
            # 兼容旧格式，当没有行业信息时使用旧的行业基准
            prompt += f"行业基准: {financial_indicators['industry_benchmark_note']}\n\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于财务报表数据和计算的财务指标，分析公司的盈利能力、运营能力、偿债能力和成长能力
2. 分析关键财务指标（ROE、ROA、毛利率、净利率、资产负债率等）的变化趋势
3. 分析公司的收入结构和成本构成
4. 评估公司的财务健康状况和现金流质量
5. 基于财务报表分析和行业对比，评估股票的投资价值和风险
6. 与同行业公司相比，该公司的财务表现如何
7. 基于财务报表分析，给出具体的投资建议（买入、持有、卖出）
8. 风险评估和资金管理建议
9. 基于历史趋势数据，分析公司的发展轨迹和未来潜力
10. 结合行业基准，评估公司在行业中的竞争地位

请提供详细、专业的分析，基于数据和量化指标，避免泛泛而谈。"""
    
    return prompt

def get_ai_analysis(prompt):
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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从财务报表角度分析股票的投资价值。"},
                {"role": "user", "content": prompt}
            ],
            options={
                "temperature": temperature,  # 降低随机性，提高准确性
                "max_tokens": int(max_tokens/2)  # 足够的响应长度
            }
        )
        
        return response['message']['content']
    except Exception as e:
        print(f"调用本地Ollama AI时出错: {str(e)}")
        return "无法获取AI分析，请检查Ollama服务是否正常运行。"

def save_prompt(ticker, prompt):
    """保存提示词"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"{ticker}_financial_prompt_{timestamp}.txt"
    file_path = os.path.join(stock_dir, filename)
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    
    print(f"提示词已保存到: {file_path}")
    return file_path

def save_analysis_result(ticker, analysis_content):
    """保存分析结果"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"{ticker}_financial_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 财务报表分析报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## AI分析结果
{analysis_content}
"""
    
    # 保存文件
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"分析报告已保存到: {file_path}")
    return file_path

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="分析股票财务报表数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载公司信息
    company_info = load_company_info(ticker)
    if not company_info:
        return
    
    # 提取财务报表数据
    financial_data = extract_financial_data(company_info)
    if not financial_data:
        print("未找到财务报表数据")
        return
    
    # 构建提示词
    prompt = build_prompt(ticker, financial_data)
    print("生成分析提示词...")
    
    # 保存提示词
    save_prompt(ticker, prompt)
    
    # 获取AI分析结果
    ai_analysis = get_ai_analysis(prompt)
    print("\n=== AI分析结果 ===")
    print(ai_analysis)
    
    # 保存分析结果
    save_analysis_result(ticker, ai_analysis)
    
    print("\n分析完成！")


if __name__ == "__main__":
    main()
