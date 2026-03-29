#!/usr/bin/env python3
# analyze_margin_data.py
# 功能：分析股票的融资融券数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的融资融券数据文件
# 2. 提取其中的融资融券相关数据
# 3. 构建AI分析提示词
# 4. 通过API访问本地ollama
# 5. 获取AI分析结果
# 6. 将结果保存到该股票的文件夹里

import json
import os
import sys
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG

def load_margin_data(ticker):
    """加载融资融券数据文件"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    # 尝试不同的文件名格式
    margin_files = [
        os.path.join(stock_dir, f"{ticker}_margin_data_20260216_20260318.csv"),
        os.path.join(stock_dir, f"{ticker}_margin_data.csv")
    ]
    
    margin_file = None
    for f in margin_files:
        if os.path.exists(f):
            margin_file = f
            break
    
    if not margin_file:
        print(f"文件不存在: {margin_files}")
        return None
    
    try:
        # 读取CSV文件
        df = pd.read_csv(margin_file)
        print(f"成功加载 {ticker} 的融资融券数据文件: {margin_file}")
        print(f"数据形状: {df.shape}")
        print(f"数据列: {list(df.columns)}")
        return df
    except Exception as e:
        print(f"加载文件时出错: {str(e)}")
        return None

def extract_margin_data(df):
    """提取融资融券相关数据"""
    if df is None:
        return {}
    
    margin_data = {}
    
    # 转换为字典格式
    margin_data['raw_data'] = df.to_dict('records')
    
    # 计算一些统计指标
    margin_data['statistics'] = {}
    
    # 计算融资余额相关指标
    if '融资余额(元)' in df.columns:
        margin_balance = df['融资余额(元)']
        margin_data['statistics']['融资余额均值'] = margin_balance.mean()
        margin_data['statistics']['融资余额最大值'] = margin_balance.max()
        margin_data['statistics']['融资余额最小值'] = margin_balance.min()
        margin_data['statistics']['融资余额变化'] = margin_balance.iloc[-1] - margin_balance.iloc[0]
        margin_data['statistics']['融资余额变化率'] = (margin_balance.iloc[-1] - margin_balance.iloc[0]) / margin_balance.iloc[0] * 100
    
    # 计算融券余额相关指标
    if '融券余额(元)' in df.columns:
        short_balance = df['融券余额(元)']
        margin_data['statistics']['融券余额均值'] = short_balance.mean()
        margin_data['statistics']['融券余额最大值'] = short_balance.max()
        margin_data['statistics']['融券余额最小值'] = short_balance.min()
        margin_data['statistics']['融券余额变化'] = short_balance.iloc[-1] - short_balance.iloc[0]
        margin_data['statistics']['融券余额变化率'] = (short_balance.iloc[-1] - short_balance.iloc[0]) / short_balance.iloc[0] * 100
    
    # 计算融资融券总额
    if '融资余额(元)' in df.columns and '融券余额(元)' in df.columns:
        total_balance = df['融资余额(元)'] + df['融券余额(元)']
        margin_data['statistics']['融资融券总额均值'] = total_balance.mean()
        margin_data['statistics']['融资融券总额最大值'] = total_balance.max()
        margin_data['statistics']['融资融券总额最小值'] = total_balance.min()
    
    # 计算融资买入额相关指标
    if '融资买入额(元)' in df.columns:
        margin_purchase = df['融资买入额(元)']
        margin_data['statistics']['融资买入额均值'] = margin_purchase.mean()
        margin_data['statistics']['融资买入额最大值'] = margin_purchase.max()
        margin_data['statistics']['融资买入额总计'] = margin_purchase.sum()
    
    # 计算融券卖出量相关指标
    if '融券卖出量(股)' in df.columns:
        short_sale = df['融券卖出量(股)']
        margin_data['statistics']['融券卖出量均值'] = short_sale.mean()
        margin_data['statistics']['融券卖出量最大值'] = short_sale.max()
        margin_data['statistics']['融券卖出量总计'] = short_sale.sum()
    
    # 计算融券余量相关指标
    if '融券余量(股)' in df.columns:
        short_balance_shares = df['融券余量(股)']
        margin_data['statistics']['融券余量均值'] = short_balance_shares.mean()
        margin_data['statistics']['融券余量最大值'] = short_balance_shares.max()
        margin_data['statistics']['融券余量最小值'] = short_balance_shares.min()
    
    return margin_data

def load_company_info(ticker):
    """加载公司信息文件，获取基本信息"""
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
        print(f"公司信息文件不存在: {info_files}")
        return None
    
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {ticker} 的公司信息文件: {info_file}")
        return data
    except Exception as e:
        print(f"加载公司信息文件时出错: {str(e)}")
        return None

def build_prompt(ticker, margin_data, company_info=None):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从融资融券数据角度分析股票的投资价值。请基于以下股票的融资融券数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}
"""
    
    # 添加公司基本信息
    if company_info and 'basic_info' in company_info:
        prompt += "公司基本信息:\n"
        key_fields = ['公司简称', '主营业务', '所属行业']
        for key in key_fields:
            if key in company_info['basic_info']:
                prompt += f"- {key}: {company_info['basic_info'][key]}\n"
        prompt += "\n"
    
    # 添加融资融券统计数据
    if 'statistics' in margin_data:
        prompt += "融资融券统计数据:\n"
        for key, value in margin_data['statistics'].items():
            if isinstance(value, (int, float)):
                if '率' in key:
                    prompt += f"- {key}: {value:.2f}%\n"
                else:
                    prompt += f"- {key}: {value:.2f}\n"
            else:
                prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加最近的融资融券数据
    if 'raw_data' in margin_data and margin_data['raw_data']:
        prompt += "最近的融资融券数据:\n"
        # 取最近的10条数据
        recent_data = margin_data['raw_data'][-10:]
        for i, item in enumerate(recent_data):
            prompt += f"第{i+1}条:\n"
            for key, value in item.items():
                prompt += f"- {key}: {value}\n"
            prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于融资融券数据，分析市场对该股票的多空情绪
2. 分析融资余额和融券余额的变化趋势及其含义
3. 分析融资买入额和融券卖出量的变化趋势
4. 评估融资融券数据对股票价格的影响
5. 基于融资融券数据，评估股票的流动性和市场活跃度
6. 分析融资融券数据与股票价格的相关性
7. 基于融资融券数据，给出具体的投资建议（买入、持有、卖出）
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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从融资融券数据角度分析股票的投资价值。"},
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
    filename = f"{ticker}_margin_data_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 融资融券数据分析报告

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
    parser = argparse.ArgumentParser(description="分析股票融资融券数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载融资融券数据
    margin_df = load_margin_data(ticker)
    if margin_df is None:
        return
    
    # 提取融资融券数据
    margin_data = extract_margin_data(margin_df)
    if not margin_data:
        print("未找到融资融券数据")
        return
    
    # 加载公司信息（可选）
    company_info = load_company_info(ticker)
    
    # 构建提示词
    prompt = build_prompt(ticker, margin_data, company_info)
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
