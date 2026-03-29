#!/usr/bin/env python3
# analyze_shareholder_structure.py
# 功能：分析company_info.json文件中的股东结构数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的company_info.json文件
# 2. 提取其中的股东结构相关数据
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

def extract_shareholder_data(data):
    """提取股东结构相关数据"""
    shareholder_data = {}
    
    # 提取主要股东数据
    if 'main_shareholders' in data:
        shareholder_data['main_shareholders'] = data['main_shareholders']
    
    # 提取基本信息（只保留关键字段）
    if 'basic_info' in data:
        key_fields = ['公司简称', '主营业务', '所属行业']
        basic_info = {}
        for key in key_fields:
            if key in data['basic_info']:
                basic_info[key] = data['basic_info'][key]
        shareholder_data['basic_info'] = basic_info
    
    # 提取规模对比数据
    if 'scale_comparison' in data:
        shareholder_data['scale_comparison'] = data['scale_comparison']
    
    return shareholder_data

def build_prompt(ticker, shareholder_data):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从股东结构角度分析股票的投资价值。请基于以下股票的股东结构相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 股东结构数据 ===
"""
    
    # 添加基本信息
    if 'basic_info' in shareholder_data:
        prompt += "公司基本信息:\n"
        for key, value in shareholder_data['basic_info'].items():
            prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加规模对比数据
    if 'scale_comparison' in shareholder_data:
        prompt += "规模对比数据:\n"
        scale_comparison = shareholder_data['scale_comparison']
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
    
    # 添加主要股东数据
    if 'main_shareholders' in shareholder_data:
        prompt += "主要股东数据:\n"
        main_shareholders = shareholder_data['main_shareholders']
        if isinstance(main_shareholders, list):
            # 按持股比例排序，取前10大股东
            sorted_shareholders = sorted(main_shareholders, key=lambda x: float(x.get('持股比例', 0)), reverse=True)[:10]
            
            # 提取并显示核心股东指标
            for i, shareholder in enumerate(sorted_shareholders):
                prompt += f"第{i+1}大股东:\n"
                prompt += f"- 股东名称: {shareholder.get('股东名称', '未知')}\n"
                prompt += f"- 持股数量: {shareholder.get('持股数量', '未知')}\n"
                prompt += f"- 持股比例: {shareholder.get('持股比例', '未知')}%\n"
                prompt += f"- 股本性质: {shareholder.get('股本性质', '未知')}\n"
                if '截至日期' in shareholder:
                    prompt += f"- 截至日期: {shareholder['截至日期']}\n"
                if '股东总数' in shareholder:
                    prompt += f"- 股东总数: {shareholder['股东总数']}\n"
                if '平均持股数' in shareholder:
                    prompt += f"- 平均持股数: {shareholder['平均持股数']}\n"
                prompt += "\n"
        else:
            # 处理非列表格式的股东数据
            prompt += f"- 股东名称: {main_shareholders.get('股东名称', '未知')}\n"
            prompt += f"- 持股数量: {main_shareholders.get('持股数量', '未知')}\n"
            prompt += f"- 持股比例: {main_shareholders.get('持股比例', '未知')}%\n"
            prompt += f"- 股本性质: {main_shareholders.get('股本性质', '未知')}\n"
            if '截至日期' in main_shareholders:
                prompt += f"- 截至日期: {main_shareholders['截至日期']}\n"
            if '股东总数' in main_shareholders:
                prompt += f"- 股东总数: {main_shareholders['股东总数']}\n"
            if '平均持股数' in main_shareholders:
                prompt += f"- 平均持股数: {main_shareholders['平均持股数']}\n"
        prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于股东结构数据，分析公司的股权集中度和控制权结构
2. 分析主要股东的背景和持股稳定性
3. 评估股东结构对公司治理和决策的影响
4. 分析股东数量和平均持股数的变化趋势及其含义
5. 基于股东结构分析，评估股票的投资价值和风险
6. 与同行业公司相比，该股票的股东结构有何特点
7. 基于股东结构分析，给出具体的投资建议（买入、持有、卖出）
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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从股东结构角度分析股票的投资价值。"},
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
    filename = f"{ticker}_shareholder_structure_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 股东结构分析报告

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
    parser = argparse.ArgumentParser(description="分析股票股东结构数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载公司信息
    company_info = load_company_info(ticker)
    if not company_info:
        return
    
    # 提取股东结构数据
    shareholder_data = extract_shareholder_data(company_info)
    if not shareholder_data:
        print("未找到股东结构数据")
        return
    
    # 构建提示词
    prompt = build_prompt(ticker, shareholder_data)
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
