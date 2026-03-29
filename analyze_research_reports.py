#!/opt/anaconda3/envs/PythonProject/bin/python
# analyze_research_reports.py
# 功能：分析company_info.json文件中的研究报告数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的company_info.json文件
# 2. 提取其中的研究报告相关数据
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

def extract_research_reports_data(data):
    """提取研究报告相关数据"""
    research_data = {}
    
    # 提取研究报告数据
    if 'research_reports' in data:
        research_data['research_reports'] = data['research_reports']
    
    # 提取基本信息（只保留关键字段）
    if 'basic_info' in data:
        key_fields = ['公司简称', '主营业务', '所属行业']
        basic_info = {}
        for key in key_fields:
            if key in data['basic_info']:
                basic_info[key] = data['basic_info'][key]
        research_data['basic_info'] = basic_info
    
    # 提取规模对比数据
    if 'scale_comparison' in data:
        research_data['scale_comparison'] = data['scale_comparison']
    
    return research_data

def build_prompt(ticker, research_data):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从研究报告角度分析股票的投资价值。请基于以下股票的研究报告相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 研究报告数据 ===
"""
    
    # 添加基本信息
    if 'basic_info' in research_data:
        prompt += "公司基本信息:\n"
        for key, value in research_data['basic_info'].items():
            prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加规模对比数据
    if 'scale_comparison' in research_data:
        prompt += "规模对比数据:\n"
        scale_comparison = research_data['scale_comparison']
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
    
    # 添加研究报告数据
    if 'research_reports' in research_data:
        prompt += "研究报告数据:\n"
        research_reports = research_data['research_reports']
        if isinstance(research_reports, list):
            # 按日期排序，取最近的10份研报
            import pandas as pd
            df = pd.DataFrame(research_reports)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期', ascending=False)
                # 取最近的10份研报
                recent_reports = df.head(10).to_dict('records')
                
                # 提取并显示核心研究报告指标
                for i, report in enumerate(recent_reports):
                    prompt += f"第{i+1}份研报（{report.get('日期', '未知日期')}）:\n"
                    prompt += f"- 报告名称: {report.get('报告名称', '未知')}\n"
                    prompt += f"- 机构: {report.get('机构', '未知')}\n"
                    prompt += f"- 东财评级: {report.get('东财评级', '未知')}\n"
                    if '2025-盈利预测-收益' in report:
                        prompt += f"- 2025年盈利预测: {report['2025-盈利预测-收益']}\n"
                    if '2025-盈利预测-市盈率' in report:
                        prompt += f"- 2025年预测市盈率: {report['2025-盈利预测-市盈率']}\n"
                    if '2026-盈利预测-收益' in report:
                        prompt += f"- 2026年盈利预测: {report['2026-盈利预测-收益']}\n"
                    if '2026-盈利预测-市盈率' in report:
                        prompt += f"- 2026年预测市盈率: {report['2026-盈利预测-市盈率']}\n"
                    if '2027-盈利预测-收益' in report:
                        prompt += f"- 2027年盈利预测: {report['2027-盈利预测-收益']}\n"
                    if '2027-盈利预测-市盈率' in report:
                        prompt += f"- 2027年预测市盈率: {report['2027-盈利预测-市盈率']}\n"
                    prompt += "\n"
            else:
                # 如果没有日期列，使用最近的10份研报
                recent_reports = research_reports[-min(10, len(research_reports)):]
                recent_reports.reverse()
                
                for i, report in enumerate(recent_reports):
                    prompt += f"第{i+1}份研报:\n"
                    prompt += f"- 报告名称: {report.get('报告名称', '未知')}\n"
                    prompt += f"- 机构: {report.get('机构', '未知')}\n"
                    prompt += f"- 东财评级: {report.get('东财评级', '未知')}\n"
                    if '2025-盈利预测-收益' in report:
                        prompt += f"- 2025年盈利预测: {report['2025-盈利预测-收益']}\n"
                    if '2025-盈利预测-市盈率' in report:
                        prompt += f"- 2025年预测市盈率: {report['2025-盈利预测-市盈率']}\n"
                    if '2026-盈利预测-收益' in report:
                        prompt += f"- 2026年盈利预测: {report['2026-盈利预测-收益']}\n"
                    if '2026-盈利预测-市盈率' in report:
                        prompt += f"- 2026年预测市盈率: {report['2026-盈利预测-市盈率']}\n"
                    if '2027-盈利预测-收益' in report:
                        prompt += f"- 2027年盈利预测: {report['2027-盈利预测-收益']}\n"
                    if '2027-盈利预测-市盈率' in report:
                        prompt += f"- 2027年预测市盈率: {report['2027-盈利预测-市盈率']}\n"
                    prompt += "\n"
        else:
            # 处理非列表格式的研究报告数据
            prompt += f"- 报告名称: {research_reports.get('报告名称', '未知')}\n"
            prompt += f"- 机构: {research_reports.get('机构', '未知')}\n"
            prompt += f"- 东财评级: {research_reports.get('东财评级', '未知')}\n"
            if '2025-盈利预测-收益' in research_reports:
                prompt += f"- 2025年盈利预测: {research_reports['2025-盈利预测-收益']}\n"
            if '2025-盈利预测-市盈率' in research_reports:
                prompt += f"- 2025年预测市盈率: {research_reports['2025-盈利预测-市盈率']}\n"
            if '2026-盈利预测-收益' in research_reports:
                prompt += f"- 2026年盈利预测: {research_reports['2026-盈利预测-收益']}\n"
            if '2026-盈利预测-市盈率' in research_reports:
                prompt += f"- 2026年预测市盈率: {research_reports['2026-盈利预测-市盈率']}\n"
            if '2027-盈利预测-收益' in research_reports:
                prompt += f"- 2027年盈利预测: {research_reports['2027-盈利预测-收益']}\n"
            if '2027-盈利预测-市盈率' in research_reports:
                prompt += f"- 2027年预测市盈率: {research_reports['2027-盈利预测-市盈率']}\n"
        prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于研究报告数据，分析机构对该股票的整体看法和评级分布
2. 分析机构对未来3年（2025-2027）的盈利预测和估值预期
3. 评估研究报告中的关键投资逻辑和催化剂
4. 分析机构预期与当前市场价格的差异
5. 基于研究报告分析，评估股票的投资价值和风险
6. 与同行业公司相比，该股票的研究报告评价如何
7. 基于研究报告分析，给出具体的投资建议（买入、持有、卖出）
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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从研究报告角度分析股票的投资价值。"},
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
    filename = f"{ticker}_research_reports_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 研究报告分析报告

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
    parser = argparse.ArgumentParser(description="分析股票研究报告数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载公司信息
    company_info = load_company_info(ticker)
    if not company_info:
        return
    
    # 提取研究报告数据
    research_data = extract_research_reports_data(company_info)
    if not research_data:
        print("未找到研究报告数据")
        return
    
    # 构建提示词
    prompt = build_prompt(ticker, research_data)
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
