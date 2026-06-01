
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
        os.path.join(stock_dir, f"{ticker}_margin_data.csv"),
        os.path.join(stock_dir, f"{ticker}_margin_data_*.csv"),
        os.path.join(stock_dir, f"{ticker}_margin.csv")
    ]
    
    margin_file = None
    # 使用glob模式匹配文件
    import glob
    for pattern in margin_files:
        files = glob.glob(pattern)
        if files:
            # 按修改时间排序，取最新的文件
            files.sort(key=os.path.getmtime, reverse=True)
            margin_file = files[0]
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
        
        # 按日期排序
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'])
            df = df.sort_values('日期', ascending=True)
        
        return df
    except Exception as e:
        print(f"加载文件时出错: {str(e)}")
        return None

def load_price_data(ticker):
    """加载股票交易数据（从qfq.csv读取）"""
    stock_dir = os.path.join(DATA_DIR, ticker)
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
                    
                    # 取最近的20条数据
                    recent_data = df.tail(20)
                    
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
    
    return price_data

def extract_margin_data(df):
    """提取融资融券相关数据"""
    if df is None:
        return {}
    
    margin_data = {}
    
    # 转换为字典格式
    raw_data = df.to_dict('records')
    
    # 计算融资偿还额和融券偿还量
    if len(raw_data) > 1:
        # 计算融资偿还额
        if '融资余额' in df.columns and '融资买入额' in df.columns:
            for i in range(1, len(raw_data)):
                prev_balance = df['融资余额'].iloc[i-1]
                curr_balance = df['融资余额'].iloc[i]
                purchase = df['融资买入额'].iloc[i]
                repayment = prev_balance + purchase - curr_balance
                raw_data[i]['融资偿还额'] = repayment
        
        # 计算融券偿还量
        if '融券余量' in df.columns and '融券卖出量' in df.columns:
            for i in range(1, len(raw_data)):
                prev_short_balance = df['融券余量'].iloc[i-1]
                curr_short_balance = df['融券余量'].iloc[i]
                short_sale = df['融券卖出量'].iloc[i]
                short_repayment = prev_short_balance + short_sale - curr_short_balance
                raw_data[i]['融券偿还量'] = short_repayment
    
    margin_data['raw_data'] = raw_data
    
    # 计算一些统计指标
    margin_data['statistics'] = {}
    
    # 计算融资余额相关指标
    if '融资余额' in df.columns:
        margin_balance = df['融资余额']
        margin_data['statistics']['融资余额均值'] = margin_balance.mean()
        margin_data['statistics']['融资余额最大值'] = margin_balance.max()
        margin_data['statistics']['融资余额最小值'] = margin_balance.min()
        margin_data['statistics']['融资余额变化'] = margin_balance.iloc[-1] - margin_balance.iloc[0]
        margin_data['statistics']['融资余额变化率'] = (margin_balance.iloc[-1] - margin_balance.iloc[0]) / margin_balance.iloc[0] * 100
    
    # 计算融券余额相关指标
    if '融券余额' in df.columns:
        short_balance = df['融券余额']
        margin_data['statistics']['融券余额均值'] = short_balance.mean()
        margin_data['statistics']['融券余额最大值'] = short_balance.max()
        margin_data['statistics']['融券余额最小值'] = short_balance.min()
        margin_data['statistics']['融券余额变化'] = short_balance.iloc[-1] - short_balance.iloc[0]
        margin_data['statistics']['融券余额变化率'] = (short_balance.iloc[-1] - short_balance.iloc[0]) / short_balance.iloc[0] * 100
    
    # 计算融资融券总额
    if '融资融券余额' in df.columns:
        total_balance = df['融资融券余额']
        margin_data['statistics']['融资融券总额均值'] = total_balance.mean()
        margin_data['statistics']['融资融券总额最大值'] = total_balance.max()
        margin_data['statistics']['融资融券总额最小值'] = total_balance.min()
    
    # 计算融资买入额相关指标
    if '融资买入额' in df.columns:
        margin_purchase = df['融资买入额']
        margin_data['statistics']['融资买入额均值'] = margin_purchase.mean()
        margin_data['statistics']['融资买入额最大值'] = margin_purchase.max()
        margin_data['statistics']['融资买入额总计'] = margin_purchase.sum()
    
    # 计算融券卖出量相关指标
    if '融券卖出量' in df.columns:
        short_sale = df['融券卖出量']
        margin_data['statistics']['融券卖出量均值'] = short_sale.mean()
        margin_data['statistics']['融券卖出量最大值'] = short_sale.max()
        margin_data['statistics']['融券卖出量总计'] = short_sale.sum()
    
    # 计算融券余量相关指标
    if '融券余量' in df.columns:
        short_balance_shares = df['融券余量']
        margin_data['statistics']['融券余量均值'] = short_balance_shares.mean()
        margin_data['statistics']['融券余量最大值'] = short_balance_shares.max()
        margin_data['statistics']['融券余量最小值'] = short_balance_shares.min()
    
    # 计算融资偿还额相关指标
    repayment_values = [item.get('融资偿还额', 0) for item in raw_data if '融资偿还额' in item]
    if repayment_values:
        margin_data['statistics']['融资偿还额均值'] = sum(repayment_values) / len(repayment_values)
        margin_data['statistics']['融资偿还额最大值'] = max(repayment_values)
        margin_data['statistics']['融资偿还额总计'] = sum(repayment_values)
    
    # 计算融券偿还量相关指标
    short_repayment_values = [item.get('融券偿还量', 0) for item in raw_data if '融券偿还量' in item]
    if short_repayment_values:
        margin_data['statistics']['融券偿还量均值'] = sum(short_repayment_values) / len(short_repayment_values)
        margin_data['statistics']['融券偿还量最大值'] = max(short_repayment_values)
        margin_data['statistics']['融券偿还量总计'] = sum(short_repayment_values)
    
    return margin_data

def load_company_info(ticker):
    """加载公司信息文件，获取基本信息"""
    stock_dir = os.path.join(DATA_DIR, ticker)
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
    
    if not info_file:
        print(f"公司信息文件不存在: {info_files}")
        return None
    
    try:
        with open(info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {ticker} 的公司信息文件: {info_file}")
        
        # 读取估值数据
        valuation_file = os.path.join(stock_dir, f"{ticker}_valuation.csv")
        if os.path.exists(valuation_file):
            try:
                import pandas as pd
                df = pd.read_csv(valuation_file)
                if not df.empty:
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
        
        return data
    except Exception as e:
        print(f"加载公司信息文件时出错: {str(e)}")
        return None

def build_prompt(ticker, margin_data, company_info=None, price_data=None):
    """构建AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从融资融券数据角度分析股票的投资价值。请基于以下股票的融资融券数据和交易数据，从量化投资的角度进行分析：

=== 股票基本信息 ===
股票代码: {ticker}
"""
    
    # 添加公司基本信息
    if company_info and 'basic_info' in company_info:
        prompt += "公司基本信息:\n"
        exclude_keys = ['成立日期', '上市日期', '地址', '证券代码', 'A股名称', '证券类型', '省份', '公司简介']
        for key, value in company_info['basic_info'].items():
            if key in exclude_keys:
                continue
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
    
    # 添加最近20日的交易数据
    if price_data:
        prompt += "=== 最近20日的交易数据 ===\n"
        prompt += "以下交易数据按日期**升序**排列（最早在前，最新在后）:\n\n"
        for item in price_data:
            date = item.get('日期', '未知日期')
            close = item.get('收盘价', 'N/A')
            change = item.get('涨跌幅', 'N/A')
            amplitude = item.get('振幅', 'N/A')
            amount = item.get('成交额', 'N/A')
            volume = item.get('成交量', 'N/A')
            turnover = item.get('换手率', 'N/A')
            prompt += f"- 日期: {date}, 收盘价: {close}元, 涨跌幅: {change}%, 振幅: {amplitude}%, 成交额: {amount}万元, 成交量: {volume}, 换手率: {turnover}%\n"
        prompt += "\n"
    
    # 添加估值数据
    if company_info and 'valuation' in company_info:
        prompt += "=== 估值数据 ===\n"
        valuation_data = company_info['valuation']
        for key, value in valuation_data.items():
            if value is not None:
                if '市值' in key:
                    prompt += f"- {key}: {value}亿元\n"
                else:
                    prompt += f"- {key}: {value}\n"
        prompt += "\n"
    

    
    # 添加融资融券统计数据（全部数据的均值）
    if 'statistics' in margin_data:
        # 计算时间范围
        start_date = None
        end_date = None
        if 'raw_data' in margin_data and margin_data['raw_data']:
            # 尝试获取日期范围
            for item in margin_data['raw_data']:
                if 'date' in item:
                    date_str = str(int(item['date'])) if isinstance(item['date'], float) else str(item['date'])
                    if len(date_str) == 8:
                        date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                    if not start_date:
                        start_date = date_str
                    end_date = date_str
        
        prompt += "=== 融资融券统计数据（全部数据均值） ===\n"
        if start_date and end_date:
            prompt += f"统计时间范围: {start_date} 至 {end_date}\n\n"

        for key, value in margin_data['statistics'].items():
            if '率' in key:
                prompt += f"- {key}: {value:.2f}%\n"
            elif '量' in key:
                # 融券相关的股数数据，添加股单位
                prompt += f"- {key}: {value:.2f}股\n"
            else:
                value_wan = round(value / 10000, 2)
                prompt += f"- {key}: {value_wan}万元\n"
        prompt += "\n"        
    
    # 添加最近的融资融券数据
    if 'raw_data' in margin_data and margin_data['raw_data']:
        prompt += "=== 最近20日的融资融券数据 ===\n"
        prompt += "以下融资融券数据按日期**升序**排列（最早在前，最新在后）。\n\n"
        # 取最近的20条数据
        recent_data = margin_data['raw_data'][-20:]
        for i, item in enumerate(recent_data):
            prompt += f"第{i+1}条数据:\n"
            seen_keys = set()  # 初始化seen_keys集合
            for key, value in item.items():
                # 跳过重复或无效字段
                if key == 'date' and 'date' in seen_keys:
                    continue
                if key == '证券代码' and '证券代码' in seen_keys:
                    continue
                
                seen_keys.add(key)
                
                if key == '证券代码':
                    # 证券代码格式修正，确保前面的00不省略
                    try:
                        code = str(int(value))
                        # 确保代码长度正确
                        if len(code) < 6:
                            code = code.zfill(6)
                        prompt += f"- {key}: {code}\n"
                    except:
                        prompt += f"- {key}: {value}\n"
                elif key == 'date' or key == '日期':
                    # 日期格式修正，去除.00
                    try:
                        if isinstance(value, float):
                            date_str = str(int(value))
                            # 尝试解析日期格式
                            if len(date_str) == 8:
                                date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:]}"
                            prompt += f"- {key}: {date_str}\n"
                        else:
                            prompt += f"- {key}: {value}\n"
                    except:
                        prompt += f"- {key}: {value}\n"
                elif key == '融资偿还额':
                    # 融资偿还额的单位是元，转换为万元
                    try:
                        value_wan = round(float(value) / 10000, 2)
                        prompt += f"- {key}: {value_wan}万元\n"
                    except:
                        prompt += f"- {key}: {value}\n"
                elif key == '融券偿还量':
                    # 融券偿还量的单位是股
                    try:
                        prompt += f"- {key}: {float(value):.2f}股\n"
                    except:
                        prompt += f"- {key}: {value}\n"
                elif isinstance(value, (int, float)):
                    # 处理其他数据类型
                    if '卖出量' in key or '余量' in key:
                        # 融券卖出量和融券余量的单位是股
                        prompt += f"- {key}: {value:.2f}股\n"
                    else:
                        # 资金数据，从元转换为万元
                        value_wan = round(value / 10000, 2)
                        prompt += f"- {key}: {value_wan}万元\n"
                else:
                    prompt += f"- {key}: {value}\n"
            prompt += "\n"
    
    # 添加分析要求
    prompt += """=== 分析要求 ===
请从量化投资的角度分析以下内容：
1. 基于融资融券数据，分析市场对该股票的多空情绪
2. 分析融资余额和融券余额的变化趋势及其含义
3. 分析融资买入额和融券卖出量的变化趋势
4. 基于融资融券数据，评估股票的流动性和市场活跃度
5. 分析融资融券数据与股票价格变动的关联关系（仅基于统计相关性，不推断因果）
   - 计算融资余额日变化率与当日股价涨跌幅的Pearson相关系数（及p值）
   - 计算前一日融资买入额占成交额比例与当日涨跌幅的相关系数（检验领先性）
   - 若相关性不显著（p>0.05），明确说明
6. 基于融资融券数据，给出具体的投资建议（买入、持有、卖出）
7. 风险评估和资金管理建议

=== 系统级指令 ===
- 明确要求：**不要编造数据**，若缺少关键字段，应在分析中注明局限性。
- 风险声明："本分析基于融资融券历史数据，不构成实际投资建议，量化模型存在过拟合风险。"

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
                "num_predict": max_tokens  # 足够的响应长度
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
    filename = f"{ticker}_margin_data_prompt_{timestamp}.txt"
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
    
    # 加载交易数据
    price_data = load_price_data(ticker)
    
    # 构建提示词
    prompt = build_prompt(ticker, margin_data, company_info, price_data)
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
