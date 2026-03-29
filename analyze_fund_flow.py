#!/usr/bin/env python3
# analyze_fund_flow.py
# 功能：读取company_info.json文件中的资金流数据，发送给本地ollama进行分析，并保存结果
# 实现原理：
# 1. 读取指定股票的company_info.json文件
# 2. 提取其中的资金流相关数据
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
    """加载公司信息文件和资金流数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    
    # 初始化数据字典
    data = {}
    
    # 1. 加载公司基本信息文件
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
    
    if info_file:
        try:
            with open(info_file, 'r', encoding='utf-8') as f:
                company_data = json.load(f)
            print(f"成功加载 {ticker} 的公司信息文件: {info_file}")
            # 合并公司信息到数据字典
            data.update(company_data)
        except Exception as e:
            print(f"加载公司信息文件时出错: {str(e)}")
    else:
        print(f"公司信息文件不存在: {info_files}")
    
    # 2. 加载资金流数据
    fund_flow_file = os.path.join(stock_dir, f"{ticker}_fund_flow.csv")
    if os.path.exists(fund_flow_file):
        try:
            import pandas as pd
            fund_flow_df = pd.read_csv(fund_flow_file)
            if not fund_flow_df.empty:
                # 将资金流数据转换为字典列表
                fund_flow_data = fund_flow_df.to_dict('records')
                data['fund_flow'] = fund_flow_data
                print(f"成功加载 {ticker} 的资金流数据: {fund_flow_file}")
                print(f"资金流数据条数: {len(fund_flow_data)}")
            else:
                print("资金流文件为空")
        except Exception as e:
            print(f"读取资金流文件时出错: {str(e)}")
    else:
        print(f"资金流文件不存在: {fund_flow_file}")
    
    # 3. 读取当前股价
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

def extract_fund_flow_data(data):
    """提取资金流相关数据"""
    fund_flow_data = {}
    
    # 提取资金流数据
    if 'fund_flow' in data:
        fund_flow_data['fund_flow'] = data['fund_flow']
    
    # 提取基本信息（只保留关键字段）
    if 'basic_info' in data:
        key_fields = ['公司简称', '主营业务', '注册资本', '实际发行数量', '发行价格', '实际募集资金净额', '发行后市盈率', '网上发行成功率', '所属行业']
        basic_info = {}
        for key in key_fields:
            if key in data['basic_info']:
                basic_info[key] = data['basic_info'][key]
        fund_flow_data['basic_info'] = basic_info
    
    # 提取规模对比数据
    if 'scale_comparison' in data:
        fund_flow_data['scale_comparison'] = data['scale_comparison']
    
    # 提取当前股价
    if 'current_price' in data:
        fund_flow_data['current_price'] = data['current_price']
    
    return fund_flow_data

def build_prompt(ticker, fund_flow_data):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从资金流角度分析股票的投资价值。请基于以下股票的资金流相关数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}

=== 资金流数据 ===
"""
    
    # 添加当前股价
    if 'current_price' in fund_flow_data:
        prompt += f"当前股价: {fund_flow_data['current_price']}\n\n"
    
    # 添加资金流数据
    if 'fund_flow' in fund_flow_data:
        prompt += "资金流数据:\n"
        fund_flow = fund_flow_data['fund_flow']
        if isinstance(fund_flow, list):
            # 按日期排序，取最近的10-15组数据
            import pandas as pd
            df = pd.DataFrame(fund_flow)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期', ascending=False)
                # 取最近的10组数据
                recent_data = df.head(10).to_dict('records')
                
                # 定义核心资金流指标映射
                core_fund_flow_mapping = {
                    '日期': '日期',
                    '主力净流入-净额': '主力净流入',
                    '超大单净流入-净额': '超大单净流入',
                    '大单净流入-净额': '大单净流入',
                    '中单净流入-净额': '中单净流入',
                    '小单净流入-净额': '小单净流入',
                    '主力净流入-净占比': '主力净流入率',
                    '超大单净流入-净占比': '超大单净流入率',
                    '大单净流入-净占比': '大单净流入率',
                    '中单净流入-净占比': '中单净流入率',
                    '小单净流入-净占比': '小单净流入率'
                }
                
                # 提取并显示核心资金流指标
                for i, val in enumerate(recent_data):
                    prompt += f"第{i+1}组数据（{val.get('日期', '未知日期')}）:\n"
                    for key, value in val.items():
                        if key in core_fund_flow_mapping:
                            prompt += f"- {core_fund_flow_mapping[key]}: {value}\n"
                    prompt += "\n"
            else:
                # 如果没有日期列，使用最近的10组数据
                recent_data = fund_flow[-min(10, len(fund_flow)):]
                recent_data.reverse()
                
                core_fund_flow_mapping = {
                    '日期': '日期',
                    '主力净流入-净额': '主力净流入',
                    '超大单净流入-净额': '超大单净流入',
                    '大单净流入-净额': '大单净流入',
                    '中单净流入-净额': '中单净流入',
                    '小单净流入-净额': '小单净流入',
                    '主力净流入-净占比': '主力净流入率',
                    '超大单净流入-净占比': '超大单净流入率',
                    '大单净流入-净占比': '大单净流入率',
                    '中单净流入-净占比': '中单净流入率',
                    '小单净流入-净占比': '小单净流入率'
                }
                
                for i, val in enumerate(recent_data):
                    prompt += f"第{i+1}组数据（{val.get('日期', '未知日期')}）:\n"
                    for key, value in val.items():
                        if key in core_fund_flow_mapping:
                            prompt += f"- {core_fund_flow_mapping[key]}: {value}\n"
                    prompt += "\n"
        else:
            # 定义核心资金流指标映射
            core_fund_flow_mapping = {
                '日期': '日期',
                '主力净流入-净额': '主力净流入',
                '超大单净流入-净额': '超大单净流入',
                '大单净流入-净额': '大单净流入',
                '中单净流入-净额': '中单净流入',
                '小单净流入-净额': '小单净流入',
                '主力净流入-净占比': '主力净流入率',
                '超大单净流入-净占比': '超大单净流入率',
                '大单净流入-净占比': '大单净流入率',
                '中单净流入-净占比': '中单净流入率',
                '小单净流入-净占比': '小单净流入率'
            }
            # 提取并显示核心资金流指标
            for key, value in fund_flow.items():
                if key in core_fund_flow_mapping:
                    prompt += f"- {core_fund_flow_mapping[key]}: {value}\n"
        prompt += "\n"
    
    # 添加规模对比数据
    if 'scale_comparison' in fund_flow_data:
        prompt += "规模对比数据:\n"
        scale_comparison = fund_flow_data['scale_comparison']
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
    
    # 添加基本信息
    if 'basic_info' in fund_flow_data:
        prompt += "公司基本信息:\n"
        for key, value in fund_flow_data['basic_info'].items():
            prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于资金流数据，分析公司的资金流入流出趋势
2. 分析主力资金、超大单、大单、中单、小单的流向特征
3. 结合资金流数据，评估股票的市场情绪和资金关注度
4. 从资金流角度，评估股票的投资价值和短期走势
5. 与同行业公司相比，该公司的资金流表现如何
6. 基于资金流分析，给出具体的投资建议（买入、持有、卖出）
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
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从资金流角度分析股票的投资价值。"},
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
    filename = f"{ticker}_fund_flow_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 资金流分析报告

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
    parser = argparse.ArgumentParser(description="分析股票资金流数据并获取AI分析结果")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"分析股票: {ticker}")
    
    # 加载公司信息
    company_info = load_company_info(ticker)
    if not company_info:
        return
    
    # 提取资金流数据
    fund_flow_data = extract_fund_flow_data(company_info)
    if not fund_flow_data:
        print("未找到资金流数据")
        return
    
    # 构建提示词
    prompt = build_prompt(ticker, fund_flow_data)
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
