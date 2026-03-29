#!/usr/bin/env python3
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
    # 尝试不同的文件名格式
    info_files = [
        os.path.join(stock_dir, f"{ticker}_company_info.json"),
        os.path.join(stock_dir, "company_info.json")
    ]
    
    info_file = None
    for f in info_files:
        if os.path.exists(f):
            info_file = f
            break
    
    if not info_file:
        print(f"文件不存在: {info_files}")
        return None
    
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {ticker} 的公司信息文件: {info_file}")
        return data
    except Exception as e:
        print(f"加载文件时出错: {str(e)}")
        return None

def extract_financial_data(data):
    """提取财务报表相关数据"""
    financial_data = {}
    
    # 提取财务报表数据
    if 'financial_report' in data:
        financial_data['financial_report'] = data['financial_report']
    
    # 提取基本信息（只保留关键字段）
    if 'basic_info' in data:
        key_fields = ['公司简称', '主营业务', '所属行业']
        basic_info = {}
        for key in key_fields:
            if key in data['basic_info']:
                basic_info[key] = data['basic_info'][key]
        financial_data['basic_info'] = basic_info
    
    # 提取规模对比数据
    if 'scale_comparison' in data:
        financial_data['scale_comparison'] = data['scale_comparison']
    
    # 提取财务摘要数据
    if 'financial_abstract' in data:
        financial_data['financial_abstract'] = data['financial_abstract']
    
    return financial_data

def build_prompt(ticker, financial_data):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从财务报表角度分析股票的投资价值。请基于以下股票的财务报表相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 财务报表数据 ===
"""
    
    # 添加基本信息
    if 'basic_info' in financial_data:
        prompt += "公司基本信息:\n"
        for key, value in financial_data['basic_info'].items():
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
                        prompt += f"- {key}: {value}\n"
                    prompt += "\n"
        elif isinstance(scale_comparison, dict):
            for key, value in scale_comparison.items():
                prompt += f"- {key}: {value}\n"
            prompt += "\n"
    
    # 添加财务摘要数据
    if 'financial_abstract' in financial_data:
        prompt += "财务摘要数据:\n"
        financial_abstract = financial_data['financial_abstract']
        if isinstance(financial_abstract, dict):
            # 提取最近的8个季度数据
            import pandas as pd
            # 转换为DataFrame
            df = pd.DataFrame(list(financial_abstract.items()), columns=['日期', '归母净利润'])
            # 按日期排序
            df = df.sort_values('日期', ascending=False)
            # 取最近的8个季度
            recent_data = df.head(8).to_dict('records')
            
            for item in recent_data:
                prompt += f"- {item['日期']}: {item['归母净利润']}\n"
        prompt += "\n"
    
    # 添加财务报表数据
    if 'financial_report' in financial_data:
        financial_report = financial_data['financial_report']
        
        # 添加利润表数据
        if 'profit' in financial_report:
            prompt += "利润表数据:\n"
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
                        prompt += f"第{i+1}期（{item.get('报告日', '未知日期')}）:\n"
                        # 提取核心利润表指标
                        key_profit_fields = [
                            '营业总收入', '营业收入', '营业总成本', '营业成本', 
                            '研发费用', '销售费用', '管理费用', '财务费用',
                            '投资收益', '营业利润', '利润总额', '净利润',
                            '归属于母公司所有者的净利润'
                        ]
                        for field in key_profit_fields:
                            if field in item:
                                prompt += f"- {field}: {item[field]}\n"
                        prompt += "\n"
            prompt += "\n"
        
        # 添加资产负债表数据
        if 'balance' in financial_report:
            prompt += "资产负债表数据:\n"
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
                        prompt += f"第{i+1}期（{item.get('报告日', '未知日期')}）:\n"
                        # 提取核心资产负债表指标
                        key_balance_fields = [
                            '资产总计', '负债总计', '所有者权益(或股东权益)合计',
                            '流动资产合计', '流动负债合计', '非流动资产合计', '非流动负债合计'
                        ]
                        for field in key_balance_fields:
                            if field in item:
                                prompt += f"- {field}: {item[field]}\n"
                        prompt += "\n"
            prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于财务报表数据，分析公司的盈利能力、运营能力、偿债能力和成长能力
2. 计算关键财务指标（ROE、ROA、毛利率、净利率、资产负债率等）并分析其变化趋势
3. 分析公司的收入结构和成本构成
4. 评估公司的财务健康状况和现金流质量
5. 基于财务报表分析，评估股票的投资价值和风险
6. 与同行业公司相比，该公司的财务表现如何
7. 基于财务报表分析，给出具体的投资建议（买入、持有、卖出）
8. 风险评估和资金管理建议

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

def save_analysis_result(ticker, analysis_content):
    """保存分析结果"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{ticker}_financial_statements_analysis_{timestamp}.md"
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
    
    # 获取AI分析结果
    ai_analysis = get_ai_analysis(prompt)
    print("\n=== AI分析结果 ===")
    print(ai_analysis)
    
    # 保存分析结果
    save_analysis_result(ticker, ai_analysis)
    
    print("\n分析完成！")


if __name__ == "__main__":
    main()
