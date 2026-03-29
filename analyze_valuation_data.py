# analyze_valuation_data.py
# 功能：读取company_info.json文件中的估值数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的company_info.json文件
# 2. 提取其中的估值相关数据
# 3. 构建AI分析提示词
# 4. 通过API访问本地ollama
# 5. 获取AI分析结果
# 6. 将结果保存到该股票的文件夹里

import json
import os
import sys
import requests
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
        
        # 读取当前股价
        current_price = None
        indicator_file = os.path.join(stock_dir, f"{ticker}_indicators.csv")
        if os.path.exists(indicator_file):
            try:
                import pandas as pd
                df = pd.read_csv(indicator_file)
                if not df.empty:
                    last_row = df.iloc[-1]
                    # 尝试不同的收盘价列名
                    for col in ['close', '收盘价', 'Close']:
                        if col in last_row:
                            current_price = last_row[col]
                            break
                    if current_price is not None:
                        print(f"成功读取当前股价: {current_price}")
                    else:
                        print("未找到收盘价列")
                else:
                    print("indicator.csv文件为空")
            except Exception as e:
                print(f"读取indicator.csv时出错: {str(e)}")
        else:
            print(f"文件不存在: {indicator_file}")
        
        # 添加当前股价到数据中
        if current_price is not None:
            data['current_price'] = current_price
        
        return data
    except Exception as e:
        print(f"加载文件时出错: {str(e)}")
        return None

def load_valuation_csv(ticker):
    """从CSV文件中加载估值数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    valuation_file = os.path.join(stock_dir, f"{ticker}_valuation.csv")
    
    if not os.path.exists(valuation_file):
        print(f"估值数据文件不存在: {valuation_file}")
        return None
    
    try:
        import pandas as pd
        df = pd.read_csv(valuation_file)
        if df.empty:
            print("估值数据文件为空")
            return None
        
        # 转换为字典列表
        valuation_data = df.to_dict('records')
        print(f"成功加载 {len(valuation_data)} 条估值数据")
        return valuation_data
    except Exception as e:
        print(f"读取估值数据文件时出错: {str(e)}")
        return None

def extract_valuation_data(data, ticker):
    """提取估值相关数据"""
    valuation_data = {}
    
    # 从CSV文件中读取估值数据
    csv_valuation_data = load_valuation_csv(ticker)
    if csv_valuation_data:
        valuation_data['valuation'] = csv_valuation_data
    
    # 只提取最核心的财务摘要（如果有）
    if 'financial_abstract' in data:
        valuation_data['financial_abstract'] = data['financial_abstract']
    
    # 只提取最基本的公司信息（如果有）
    if 'basic_info' in data:
        valuation_data['basic_info']  = data['basic_info']
    
    # 提取当前股价
    if 'current_price' in data:
        valuation_data['current_price'] = data['current_price']
    
    # 提取balance数据并处理
    if 'balance' in data:
        balance_data = data['balance']
        if isinstance(balance_data, list) and balance_data:
            # 获取最新的balance数据
            latest_balance = balance_data[-1]
            # 过滤掉含有"NAN"的内容
            filtered_balance = {}
            for key, value in latest_balance.items():
                if value != 'NAN' and value != 'NaN' and value != 'nan' and value is not None:
                    filtered_balance[key] = value
            if filtered_balance:
                valuation_data['balance'] = filtered_balance
    
    # 提取scale_comparison字段
    if 'scale_comparison' in data:
        valuation_data['scale_comparison'] = data['scale_comparison']
    
    return valuation_data

def build_prompt(ticker, valuation_data):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从数据角度分析公司估值和投资价值。请基于以下股票的估值相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 估值数据 ===
"""
    
    # 添加当前股价
    if 'current_price' in valuation_data:
        prompt += f"当前股价: {valuation_data['current_price']}\n\n"
    
    # 添加估值数据
    if 'valuation' in valuation_data:
        prompt += "估值指标:\n"
        if isinstance(valuation_data['valuation'], list):
            # 显示最近的5-10组按周或月抽样的估值数据
            if valuation_data['valuation']:
                import pandas as pd
                from datetime import datetime
                
                # 转换为DataFrame并按日期排序
                df = pd.DataFrame(valuation_data['valuation'])
                if '数据日期' in df.columns:
                    df['数据日期'] = pd.to_datetime(df['数据日期'])
                    df = df.sort_values('数据日期')
                    
                    # 按周抽样
                    df['week'] = df['数据日期'].dt.to_period('W')
                    sampled_df = df.groupby('week').last().reset_index()
                    
                    # 如果数据量不足，使用按月抽样
                    if len(sampled_df) < 5:
                        df['month'] = df['数据日期'].dt.to_period('M')
                        sampled_df = df.groupby('month').last().reset_index()
                    
                    # 确保至少有5组数据，最多10组
                    if len(sampled_df) > 10:
                        sampled_df = sampled_df.tail(10)
                    elif len(sampled_df) < 5 and len(df) > 5:
                        # 如果抽样后数据不足，直接取最近的5-10组
                        sampled_df = df.tail(min(10, len(df)))
                    
                    # 转换回列表格式
                    recent_data = sampled_df.to_dict('records')
                    
                    # 定义核心估值指标映射，支持中英文字段名
                    core_valuation_mapping = {
                        'PE(TTM)': 'PE(TTM)',
                        'PE(静)': 'PE(静)',
                        '市净率': '市净率',
                        '市销率': '市销率',
                        '市现率': '市现率',
                        'PEG值': 'PEG值',
                        '总市值': '总市值',
                        '数据日期': '数据日期',
                        'pe_ttm': 'PE(TTM)',
                        'pe_static': 'PE(静)',
                        'pb': '市净率',
                        'ps': '市销率',
                        'pcf': '市现率',
                        'peg': 'PEG值',
                        'date': '数据日期'
                    }
                    
                    # 提取并显示核心估值指标
                    for i, val in enumerate(recent_data):
                        date_str = val.get('数据日期', '未知日期')
                        if isinstance(date_str, pd.Period):
                            date_str = date_str.strftime('%Y-%m-%d')
                        elif isinstance(date_str, pd.Timestamp):
                            date_str = date_str.strftime('%Y-%m-%d')
                        prompt += f"第{i+1}组数据（{date_str}）:\n"
                        for key, value in val.items():
                            if key in core_valuation_mapping:
                                prompt += f"- {core_valuation_mapping[key]}: {value}\n"
                        prompt += "\n"
                else:
                    # 如果没有日期列，使用最近的5-10组数据
                    recent_data = valuation_data['valuation'][-min(10, len(valuation_data['valuation'])):]
                    recent_data.reverse()
                    
                    core_valuation_mapping = {
                        'PE(TTM)': 'PE(TTM)',
                        'PE(静)': 'PE(静)',
                        '市净率': '市净率',
                        '市销率': '市销率',
                        '市现率': '市现率',
                        'PEG值': 'PEG值',
                        '总市值': '总市值',
                        '数据日期': '数据日期',
                        'pe_ttm': 'PE(TTM)',
                        'pe_static': 'PE(静)',
                        'pb': '市净率',
                        'ps': '市销率',
                        'pcf': '市现率',
                        'peg': 'PEG值',
                        'date': '数据日期'
                    }
                    
                    for i, val in enumerate(recent_data):
                        prompt += f"第{i+1}组数据（{val.get('数据日期', '未知日期')}）:\n"
                        for key, value in val.items():
                            if key in core_valuation_mapping:
                                prompt += f"- {core_valuation_mapping[key]}: {value}\n"
                        prompt += "\n"
        else:
            # 定义核心估值指标映射，支持中英文字段名
            core_valuation_mapping = {
                'PE(TTM)': 'PE(TTM)',
                'PE(静)': 'PE(静)',
                '市净率': '市净率',
                '市销率': '市销率',
                '市现率': '市现率',
                'PEG值': 'PEG值',
                '总市值': '总市值',
                'pe_ttm': 'PE(TTM)',
                'pe_static': 'PE(静)',
                'pb': '市净率',
                'ps': '市销率',
                'pcf': '市现率',
                'peg': 'PEG值'
            }
            # 提取并显示核心估值指标
            for key, value in valuation_data['valuation'].items():
                if key in core_valuation_mapping:
                    prompt += f"- {core_valuation_mapping[key]}: {value}\n"
        prompt += "\n"
    
    # 添加scale_comparison字段
    if 'scale_comparison' in valuation_data:
        prompt += "规模对比数据:\n"
        scale_comparison = valuation_data['scale_comparison']
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
    
    # 添加财务摘要（只显示关键指标）
    if 'financial_abstract' in valuation_data:
        prompt += "财务摘要:\n"
        financial_abstract = valuation_data['financial_abstract']
        for key, value in financial_abstract.items():
            prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加balance数据
    if 'balance' in valuation_data:
        prompt += "最新资产负债数据:\n"
        balance = valuation_data['balance']
        # 只显示关键的balance指标
        key_balance_fields = ['total_assets', 'total_liabilities', 'net_assets', '流动资产', '流动负债', '资产总计', '负债总计', '所有者权益']
        for key, value in balance.items():
            if key in key_balance_fields:
                prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加基本信息（只保留关键字段）
    if 'basic_info' in valuation_data:
        prompt += "公司基本信息:\n"
        # 只保留用户指定的字段
        key_fields = ['公司简称', '主营业务', '注册资本', '实际发行数量', '发行价格', '实际募集资金净额', '发行后市盈率', '网上发行成功率', '所属行业']
        for key in key_fields:
            if key in valuation_data['basic_info']:
                prompt += f"- {key}: {valuation_data['basic_info'][key]}\n"
        prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于估值数据，分析公司的估值水平是否合理
2. 分析估值数据的变化趋势及其含义
3. 结合财务数据，评估公司的财务健康状况
4. 从量化指标角度，评估公司的投资价值
5. 与同行业公司相比，该公司的估值优势和劣势
6. 基于量化分析，给出具体的投资建议（买入、持有、卖出）
7. 风险评估和资金管理建议
8. 适合的投资策略和时间 horizon

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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从数据角度分析公司估值和投资价值。"},
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
    filename = f"{ticker}_valuation_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 估值分析报告

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
    parser = argparse.ArgumentParser(description="分析股票估值数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载公司信息
    company_info = load_company_info(ticker)
    if not company_info:
        return
    
    # 提取估值数据
    valuation_data = extract_valuation_data(company_info, ticker)
    if not valuation_data:
        print("未找到估值数据")
        return
    
    # 构建提示词
    prompt = build_prompt(ticker, valuation_data)
    print("生成分析提示词...")
    
    # 提示词保存功能已屏蔽
    # stock_dir = os.path.join(DATA_DIR, ticker)
    # os.makedirs(stock_dir, exist_ok=True)
    # timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    # prompt_filename = f"{ticker}_valuation_analysis_prompt_{timestamp}.txt"
    # prompt_file_path = os.path.join(stock_dir, prompt_filename)
    # with open(prompt_file_path, 'w', encoding='utf-8') as f:
    #     f.write(prompt)
    # print(f"提示词已保存到: {prompt_file_path}")
    print("提示词生成完成")
    
    # 获取AI分析结果
    ai_analysis = get_ai_analysis(prompt)
    print("\n=== AI分析结果 ===")
    print(ai_analysis)
    
    # 保存分析结果
    save_analysis_result(ticker, ai_analysis)
    
    print("\n分析完成！")


if __name__ == "__main__":
    main()
