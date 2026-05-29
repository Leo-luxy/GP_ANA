
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
        os.path.join(stock_dir, f"{ticker}_company_basic.json"),
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
            
            # 处理上市日期缺失值
            if 'basic_info' in company_data and '上市日期' in company_data['basic_info'] and company_data['basic_info']['上市日期'] is None:
                company_data['basic_info']['上市日期'] = "2010-04-09"  # 东山精密实际上市日期
                print("已补充上市日期为: 2010-04-09")
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
                # 按日期排序，从最早到最晚
                if '日期' in fund_flow_df.columns:
                    fund_flow_df['日期'] = pd.to_datetime(fund_flow_df['日期'])
                    fund_flow_df = fund_flow_df.sort_values('日期', ascending=True)
                
                # 计算累计主力净流入
                if '主力净流入-净额' in fund_flow_df.columns:
                    fund_flow_df['累计主力净流入'] = fund_flow_df['主力净流入-净额'].cumsum()
                
                # 计算主力净流入率的标准差
                if '主力净流入-净占比' in fund_flow_df.columns:
                    fund_flow_df['主力净流入率_标准差'] = fund_flow_df['主力净流入-净占比'].rolling(window=3).std()
                
                # 计算资金流相关统计数据
                if '主力净流入-净额' in fund_flow_df.columns:
                    data['fund_flow_stats'] = {
                        'total_main_net': float(fund_flow_df['主力净流入-净额'].sum()),
                        'avg_main_net': float(fund_flow_df['主力净流入-净额'].mean()),
                        'avg_main_net_ratio': float(fund_flow_df['主力净流入-净占比'].mean()) if '主力净流入-净占比' in fund_flow_df.columns else None,
                        'std_main_net_ratio': float(fund_flow_df['主力净流入-净占比'].std()) if '主力净流入-净占比' in fund_flow_df.columns else None
                    }
                
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
    
    # 3. 读取最近10日的交易数据（从qfq.csv读取）
    price_data = []
    qfq_file = os.path.join(stock_dir, f"{ticker}_qfq.csv")
    if os.path.exists(qfq_file):
        try:
            import pandas as pd
            df = pd.read_csv(qfq_file)
            if not df.empty:
                # 尝试不同的列名
                close_col = None
                date_col = None
                amount_col = None
                volume_col = None
                turnover_col = None
                open_col = None
                high_col = None
                low_col = None
                
                for col in ['close', '收盘价', 'Close']:
                    if col in df.columns:
                        close_col = col
                        break
                for col in ['date', '日期', 'Date']:
                    if col in df.columns:
                        date_col = col
                        break
                for col in ['amount', '成交额', 'Amount']:
                    if col in df.columns:
                        amount_col = col
                        break
                for col in ['volume', '成交量', 'Volume']:
                    if col in df.columns:
                        volume_col = col
                        break
                for col in ['turnover', '换手率', 'Turnover']:
                    if col in df.columns:
                        turnover_col = col
                        break
                for col in ['open', '开盘价', 'Open']:
                    if col in df.columns:
                        open_col = col
                        break
                for col in ['high', '最高价', 'High']:
                    if col in df.columns:
                        high_col = col
                        break
                for col in ['low', '最低价', 'Low']:
                    if col in df.columns:
                        low_col = col
                        break
                
                if close_col is not None:
                    # 按日期排序，从最早到最晚
                    if date_col:
                        df[date_col] = pd.to_datetime(df[date_col])
                        df = df.sort_values(date_col, ascending=True)
                    
                    # 计算每日涨跌幅
                    df['涨跌幅'] = df[close_col].pct_change() * 100
                    
                    # 计算每日振幅
                    if high_col and low_col:
                        df['振幅'] = ((df[high_col] - df[low_col]) / df[close_col].shift(1) * 100) if open_col else ((df[high_col] - df[low_col]) / df[close_col] * 100)
                    
                    # 取最近的10条数据
                    recent_data = df.tail(10)
                    
                    # 构建价格数据列表，包含日期、收盘价、涨跌幅、振幅、成交额、成交量、换手率
                    for _, row in recent_data.iterrows():
                        price_item = {
                            '日期': row[date_col].strftime('%Y-%m-%d') if date_col else f"第{len(price_data)+1}日",
                            '收盘价': round(float(row[close_col]), 2),
                            '涨跌幅': round(float(row['涨跌幅']), 2) if '涨跌幅' in row else None,
                            '振幅': round(float(row['振幅']), 2) if '振幅' in row else None,
                            '成交额': round(float(row[amount_col])/10000, 2) if amount_col else None,  # 转换为万元
                            '成交量': round(float(row[volume_col]), 2) if volume_col else None,
                            '换手率': round(float(row[turnover_col])*100, 2) if turnover_col else None  # 转换为百分比
                        }
                        price_data.append(price_item)
                    
                    print(f"成功读取最近10日的交易数据: {len(price_data)}条")
                else:
                    print("未找到收盘价列")
            else:
                print("qfq.csv文件为空")
        except Exception as e:
            print(f"读取qfq.csv时出错: {str(e)}")
    else:
        print(f"文件不存在: {qfq_file}")
    
    # 4. 读取估值数据
    valuation_data = {}
    valuation_file = os.path.join(stock_dir, f"{ticker}_valuation.csv")
    if os.path.exists(valuation_file):
        try:
            import pandas as pd
            df = pd.read_csv(valuation_file)
            if not df.empty:
                # 取最后一行数据
                last_row = df.iloc[-1]
                # 提取估值相关数据
                valuation_data = {
                    'PE(TTM)': round(float(last_row['PE(TTM)']), 2) if 'PE(TTM)' in last_row else None,
                    'PE(静)': round(float(last_row['PE(静)']), 2) if 'PE(静)' in last_row else None,
                    '市净率': round(float(last_row['市净率']), 2) if '市净率' in last_row else None,
                    'PEG值': round(float(last_row['PEG值']), 2) if 'PEG值' in last_row else None,
                    '市现率': round(float(last_row['市现率']), 2) if '市现率' in last_row else None,
                    '市销率': round(float(last_row['市销率']), 2) if '市销率' in last_row else None,
                    '总市值': round(float(last_row['总市值'])/100000000, 2) if '总市值' in last_row else None,  # 转换为亿元
                    '流通市值': round(float(last_row['流通市值'])/100000000, 2) if '流通市值' in last_row else None  # 转换为亿元
                }
                data['valuation'] = valuation_data
                print(f"成功读取估值数据: {valuation_file}")
            else:
                print("valuation.csv文件为空")
        except Exception as e:
            print(f"读取valuation.csv时出错: {str(e)}")
    else:
        print(f"文件不存在: {valuation_file}")
    
    # 添加价格数据到数据中
    if price_data:
        data['price_data'] = price_data
    
    return data

def extract_fund_flow_data(data):
    """提取资金流相关数据"""
    fund_flow_data = {}
    
    # 提取资金流数据
    if 'fund_flow' in data:
        fund_flow_data['fund_flow'] = data['fund_flow']
    
    # 提取基本信息（读取完整信息）
    if 'basic_info' in data:
        fund_flow_data['basic_info'] = data['basic_info']
    
    # 提取价格数据
    if 'price_data' in data:
        fund_flow_data['price_data'] = data['price_data']
    
    # 提取估值数据
    if 'valuation' in data:
        fund_flow_data['valuation'] = data['valuation']
    
    return fund_flow_data

def build_prompt(ticker, fund_flow_data):
    """构建AI分析提示词"""
    prompt = "你是一位专业的量化投资分析师，擅长从资金流角度分析股票的投资价值。请基于以下股票的资金流相关数据，从量化投资的角度进行分析：\n\n"
    
    # 添加股票基本信息
    prompt += "=== 股票基本信息 ===\n"
    if 'basic_info' in fund_flow_data:
        for key, value in fund_flow_data['basic_info'].items():
            # 为基本信息添加单位
            if '注册资本' in key:
                # 注册资本数据，从万元转换为亿元
                try:
                    value_yuan = round(float(value) / 10000, 2)
                    prompt += f"- {key}: {value_yuan}亿元\n"
                except:
                    prompt += f"- {key}: {value}\n"
            elif '资金' in key:
                # 资金数据，从元转换为万元
                try:
                    value_wan = round(float(value) / 10000, 2)
                    prompt += f"- {key}: {value_wan}万元\n"
                except:
                    prompt += f"- {key}: {value}\n"
            else:
                # 其他数据
                prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加资金流数据
    prompt += "=== 资金流数据 ===\n"
    
    # 添加最近10日的价格数据
    if 'price_data' in fund_flow_data:
        prompt += "最近10日的价格数据（按时间升序排列）:\n"
        for item in fund_flow_data['price_data']:
            date = item.get('日期', '未知日期')
            close = item.get('收盘价', 'N/A')
            change = item.get('涨跌幅', 'N/A')
            amount = item.get('成交额', 'N/A')
            volume = item.get('成交量', 'N/A')
            turnover = item.get('换手率', 'N/A')
            prompt += f"- 日期: {date}, 收盘价: {close}元, 涨跌幅: {change}%, 成交额: {amount}万元, 成交量: {volume}, 换手率: {turnover}%\n"
        prompt += "\n"
    
    # 添加估值数据
    if 'valuation' in fund_flow_data:
        prompt += "=== 估值数据 ===\n"
        for key, value in fund_flow_data['valuation'].items():
            if key in ['总市值', '流通市值']:
                prompt += f"- {key}: {value}亿元\n"
            else:
                prompt += f"- {key}: {value}\n"
        prompt += "\n"
    
    # 添加资金流数据
    if 'fund_flow' in fund_flow_data:
        prompt += "=== 资金流数据 ===\n"
        prompt += "以下资金流数据按日期**升序**排列（最早在前，最新在后）。\n\n"
        fund_flow = fund_flow_data['fund_flow']
        if isinstance(fund_flow, list):
            # 按日期排序，取最近的10-15组数据
            import pandas as pd
            df = pd.DataFrame(fund_flow)
            if '日期' in df.columns:
                df['日期'] = pd.to_datetime(df['日期'])
                df = df.sort_values('日期', ascending=True)
                # 取最近的10组数据
                recent_data = df.tail(10).to_dict('records')
                
                # 定义核心资金流指标映射
                core_fund_flow_mapping = {
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
                    date = val.get('日期', '未知日期')
                    prompt += f"第{i+1}组数据（{date}）:\n"
                    for key, value in val.items():
                        if key in core_fund_flow_mapping:
                            # 为资金流数据添加单位
                            mapped_key = core_fund_flow_mapping[key]
                            if '净流入' in mapped_key and '率' not in mapped_key:
                                # 资金流入流出数据，从元转换为万元
                                try:
                                    value_wan = round(float(value) / 10000, 2)
                                    prompt += f"- {mapped_key}: {value_wan}万元\n"
                                except:
                                    prompt += f"- {mapped_key}: {value}\n"
                            else:
                                # 其他数据，如比率等
                                try:
                                    value_formatted = round(float(value), 2)
                                    prompt += f"- {mapped_key}: {value_formatted}%\n"
                                except:
                                    prompt += f"- {mapped_key}: {value}\n"
                    prompt += "\n"
            else:
                # 如果没有日期列，使用最近的10组数据
                recent_data = fund_flow[-min(10, len(fund_flow)):]
                recent_data.reverse()
                
                core_fund_flow_mapping = {
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
                    date = val.get('日期', '未知日期')
                    prompt += f"第{i+1}组数据（{date}）:\n"
                    for key, value in val.items():
                        if key in core_fund_flow_mapping:
                            # 为资金流数据添加单位
                            mapped_key = core_fund_flow_mapping[key]
                            if '净流入' in mapped_key and '率' not in mapped_key:
                                # 资金流入流出数据，从元转换为万元
                                try:
                                    value_wan = round(float(value) / 10000, 2)
                                    prompt += f"- {mapped_key}: {value_wan}万元\n"
                                except:
                                    prompt += f"- {mapped_key}: {value}\n"
                            else:
                                # 其他数据，如比率等
                                try:
                                    value_formatted = round(float(value), 2)
                                    prompt += f"- {mapped_key}: {value_formatted}%\n"
                                except:
                                    prompt += f"- {mapped_key}: {value}\n"
                    prompt += "\n"
        else:
            # 定义核心资金流指标映射
            core_fund_flow_mapping = {
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
                    # 为资金流数据添加单位
                    mapped_key = core_fund_flow_mapping[key]
                    if '净流入' in mapped_key and '率' not in mapped_key:
                        # 资金流入流出数据，从元转换为万元
                        try:
                            value_wan = round(float(value) / 10000, 2)
                            prompt += f"- {mapped_key}: {value_wan}万元\n"
                        except:
                            prompt += f"- {mapped_key}: {value}\n"
                    else:
                        # 其他数据，如比率等
                        try:
                            value_formatted = round(float(value), 2)
                            prompt += f"- {mapped_key}: {value_formatted}\n"
                        except:
                            prompt += f"- {mapped_key}: {value}\n"
        prompt += "\n"
    
    # 添加分析要求
    prompt += "=== 分析要求 ===\n"
    prompt += "请基于上述资金流、价格数据和估值数据，回答以下问题：\n"
    prompt += "1. **资金流趋势**：计算10日累计主力净流入额及日均净流入率，判断趋势方向（持续流出/流入/反转）。\n"
    prompt += "   日均净流入率计算公式：(10日累计主力净流入额) / (10日累计成交额) × 100%，其中累计成交额取自价格数据中对应日期的成交额之和。\n"
    prompt += "2. **资金结构特征**：分析超大单、大单、中单、小单的净流入额相关性及一致性（例如，主力与散户是否对立）。\n"
    prompt += "3. **市场情绪量化**：通过小单净流入率与主力净流入率的背离程度，构建简单的情绪指标（如\"散户接盘指数\"）。\n"
    prompt += "4. **短期走势预测**：基于资金流动量（如近3日主力净流入变化）和价格位置，给出未来5个交易日的涨跌倾向（看涨/看跌/震荡）及判断依据。\n"
    prompt += "5. **投资建议**：给出\"买入/持有/卖出\"信号，并注明触发条件（例如：连续3日主力净流入>0且累计流入率>2%）。\n"
    prompt += "6. **风险评估**：计算资金流稳定性指标（如主力净流入率的滚动波动率），并建议最大仓位占比。\n"
    prompt += "7. **策略及时间 horizon**：推荐超短线（1-3天）、短线（5-10天）或波段策略，并给出止盈止损参考（基于资金流反转阈值）。\n"
    prompt += "\n"
    prompt += "=== 系统级指令 ===\n"
    prompt += "- 明确要求：**不要编造数据**，若缺少关键字段，应在分析中注明局限性。\n"
    prompt += "- 风险声明：\"本分析基于资金流历史数据、价格数据和估值数据，不构成实际投资建议，量化模型存在过拟合风险。\"\n"
    prompt += "- 数据质量提示：成交额与换手率可能基于不同股本口径，分析时以净流入率为主。\n"
    prompt += "\n"
    prompt += "请提供详细、专业的分析，基于数据和量化指标，避免泛泛而谈。"

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

def save_prompt(ticker, prompt):
    """保存提示词到本地文件"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 生成文件名
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"{ticker}_fund_flow_prompt_{timestamp}.txt"
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
