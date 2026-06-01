# two_layer_decision_analyzer.py
# 功能：采用两层决策架构进行股票综合分析（五维度）
# 第一层：冲突检测与综合研判 - 识别各维度信号的主要矛盾，进行综合判断
# 第二层：结合持仓生成交易计划 - 根据综合研判和实际持仓情况生成可执行的交易计划
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TwoLayerDecisionAnalyzer:
    def __init__(self, ticker):
        self.ticker = ticker
        self.analysis_reports = {
            'financial': {},
            'sentiment': {},
            'technical': {},
            'shareholder': {},
            'research': {}
        }
        self.conflict_analysis = None
        self.trading_plan = None
        self.first_prompt = None
        self.second_prompt = None
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', ticker)
        self.strategy_prompt = None  # 交易策略提示

    def load_analysis_reports(self):
        """加载五份核心分析报告"""
        report_mapping = {
            'financial': f"{self.ticker}_financial_summary.json",
            'sentiment': f"{self.ticker}_sentiment_valuation.json",
            'technical': f"{self.ticker}_technical_trend_analysis.json",
            'shareholder': f"{self.ticker}_shareholder_structure.json",
            'research': f"{self.ticker}_research_report_analysis.json"
        }

        for report_type, filename in report_mapping.items():
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.analysis_reports[report_type] = json.load(f)
                    print(f"加载{report_type}分析报告: {file_path}")
                except Exception as e:
                    print(f"读取{report_type}分析报告时出错: {str(e)}")
            else:
                print(f"未找到{report_type}分析报告文件: {file_path}")

    def extract_layer1_data(self):
        """从五份JSON中提取第一层决策信号"""
        data = {}

        # 财务摘要
        if self.analysis_reports.get('financial'):
            fin = self.analysis_reports['financial']
            data['financial'] = {
                'signal': fin.get('verdict', {}).get('signal', 'UNKNOWN'),
                'confidence': fin.get('verdict', {}).get('confidence', 0),
                'summary': fin.get('verdict', {}).get('summary', ''),
                'major_anomalies': fin.get('major_anomalies', []),
                'key_metrics': fin.get('key_metrics', {}),
                'suggested_action': fin.get('suggested_action', '')
            }

        # 情绪估值摘要
        if self.analysis_reports.get('sentiment'):
            sent = self.analysis_reports['sentiment']
            data['sentiment'] = {
                'fund_flow_anomalies': sent.get('fund_flow', {}).get('major_anomalies', []),
                'sentiment_signal': sent.get('sentiment_signal', {}),
                'valuation_signal': sent.get('valuation_signal', {}),
                'comprehensive': sent.get('comprehensive_signal', {})
            }

        # 技术趋势摘要
        if self.analysis_reports.get('technical'):
            tech = self.analysis_reports['technical']
            data['technical'] = {
                'daily_trend': tech.get('multi_timeframe', {}).get('daily_trend', 'UNKNOWN'),
                'weekly_trend': tech.get('multi_timeframe', {}).get('weekly_trend', 'UNKNOWN'),
                'consistency_score': tech.get('consistency_score', 0),
                'trading_signal': tech.get('trading_signal', {}),
                'market_snapshot': tech.get('market_snapshot', ''),
                'indicator_labels': tech.get('indicator_labels', {}),
                'price_action': tech.get('price_action', {}),
                'technical_indicators': tech.get('technical_indicators', {})
            }

        # 股东结构摘要
        if self.analysis_reports.get('shareholder'):
            sh = self.analysis_reports['shareholder']
            data['shareholder'] = {
                'signal': sh.get('shareholder_signal', {}).get('信号方向', 'UNKNOWN'),
                'score': sh.get('shareholder_signal', {}).get('股东结构评分', 0),
                'bullish_signals': sh.get('shareholder_signal', {}).get('利多信号', []),
                'bearish_signals': sh.get('shareholder_signal', {}).get('利空信号', []),
                'major_anomalies': self._extract_shareholder_anomalies(sh),
                'comprehensive': sh.get('comprehensive_signal', {})
            }

        # 研报摘要
        if self.analysis_reports.get('research'):
            rr = self.analysis_reports['research']
            data['research'] = {
                'rating_summary': rr.get('rating_summary', {}),
                'earnings_forecast': rr.get('earnings_forecast', {}),
                'rating_anomalies': rr.get('rating_summary', {}).get('rating_anomalies', []),
                'earnings_anomalies': rr.get('earnings_forecast', {}).get('earnings_anomalies', []),
                'research_signal': rr.get('research_signal', {}),
                'comprehensive': rr.get('comprehensive_signal', {})
            }

        return data

    def _extract_shareholder_anomalies(self, sh_data):
        """提取股东结构异常"""
        anomalies = []
        if sh_data.get('main_shareholders', {}).get('major_anomalies'):
            anomalies.extend(sh_data['main_shareholders']['major_anomalies'])
        if sh_data.get('shareholder_num', {}).get('shareholder_anomalies'):
            anomalies.extend(sh_data['shareholder_num']['shareholder_anomalies'])
        if sh_data.get('institutional_holdings', {}).get('institutional_anomalies'):
            anomalies.extend(sh_data['institutional_holdings']['institutional_anomalies'])
        return anomalies

    def _format_anomalies(self, anomalies):
        """格式化异常列表"""
        if not anomalies:
            return "无"
        return "; ".join([f"{a.get('type')}: {a.get('detail')}" for a in anomalies])

    def _format_signals(self, signals):
        """格式化信号列表"""
        if not signals:
            return "无"
        return "; ".join(signals)

    def generate_first_layer_prompt(self, layer1_data):
        """生成第一层LLM提示词：五维冲突检测与综合研判"""
        fin = layer1_data.get('financial', {})
        sent = layer1_data.get('sentiment', {})
        tech = layer1_data.get('technical', {})
        sh = layer1_data.get('shareholder', {})
        rr = layer1_data.get('research', {})

        # 财务面关键指标
        fin_metrics = fin.get('key_metrics', {})
        fin_anomalies = self._format_anomalies(fin.get('major_anomalies', []))

        # 情绪估值面
        sentiment_signal = sent.get('sentiment_signal', {})
        valuation_signal = sent.get('valuation_signal', {})
        sent_comprehensive = sent.get('comprehensive', {})

        # 技术面
        tech_signal = tech.get('trading_signal', {})
        tech_indicators = tech.get('technical_indicators', {})

        # 股东结构面
        sh_anomalies = self._format_anomalies(sh.get('major_anomalies', []))

        # 研报面
        rating_summary = rr.get('rating_summary', {})
        earnings_forecast = rr.get('earnings_forecast', {})
        earnings_anomalies = self._format_anomalies(rr.get('earnings_anomalies', []))

        prompt = f"""【场景】你是一位对冲基金首席投资官。你的团队提供了五个维度的分析摘要，请识别矛盾点并给出综合判断。

【输入数据】
一、财务面
信号：{fin.get('signal', 'UNKNOWN')} (置信度 {fin.get('confidence', 0):.1f})
异常：{fin_anomalies}
关键指标：营收同比{fin_metrics.get('营收同比增长率', 'N/A')}%，净利润同比{fin_metrics.get('净利润同比增长率', 'N/A')}%，ROE{fin_metrics.get('ROE', 'N/A')}%，净利率{fin_metrics.get('净利率', 'N/A')}%，负债率{fin_metrics.get('资产负债率', 'N/A')}%，速动比率{fin_metrics.get('速动比率', 'N/A')}，PE/PB{fin_metrics.get('PE(TTM)', 'N/A')}/{fin_metrics.get('PB', 'N/A')}
建议：{fin.get('suggested_action', 'N/A')}

二、情绪与估值面
情绪评分{sentiment_signal.get('情绪评分', 'N/A')}/100，信号{sentiment_signal.get('信号方向', 'N/A')}；估值评分{valuation_signal.get('估值评分', 'N/A')}/100，信号{valuation_signal.get('信号方向', 'N/A')}
利空信号：{self._format_signals(sentiment_signal.get('利空信号', []))}
利多信号：{self._format_signals(sentiment_signal.get('利多信号', []))}
综合建议：{sent_comprehensive.get('建议操作', 'N/A')}
理由：{sent_comprehensive.get('action_reason', 'N/A')}

三、技术面
日趋势：{tech.get('daily_trend', 'N/A')}，周趋势：{tech.get('weekly_trend', 'N/A')}
指标一致性：{tech.get('consistency_score', 0)*100:.0f}%
交易信号：{tech_signal.get('action', 'N/A')} (置信度 {tech_signal.get('confidence', 0):.1f})
市场状态：{tech.get('market_snapshot', 'N/A')}
当前价：{tech_indicators.get('close', 'N/A')}元，布林带位置：{tech_indicators.get('BB_pctB', 'N/A')}

四、股东结构面
信号：{sh.get('signal', 'UNKNOWN')} (评分 {sh.get('score', 0)}/100)
利多：{self._format_signals(sh.get('bullish_signals', []))}
利空：{self._format_signals(sh.get('bearish_signals', []))}
异常：{sh_anomalies}
建议：{sh.get('comprehensive', {}).get('建议操作', 'N/A')}

五、机构研报面
评级分布：买入 {rating_summary.get('buy_ratio', 'N/A')}%，近三月 {rating_summary.get('reports_3m', 'N/A')} 篇报告
2026年一致预期EPS {earnings_forecast.get('eps_forecast', {}).get('eps_2026', {}).get('avg', 'N/A')}元，2027年增长{earnings_forecast.get('eps_growth_2027', 'N/A')}%
关键矛盾：{earnings_anomalies}
机构综合信号：{rr.get('comprehensive', {}).get('综合信号', 'N/A')}，建议：{rr.get('comprehensive', {}).get('建议操作', 'N/A')}

【要求】
请完成以下三项任务，只输出结果，不要展开叙述：
1. 指出五个维度之间的核心矛盾（至少列出两条）
2. 给出综合倾向评分（-10 到 +10，负数看空，正数看多）并解释主要理由
3. 列出扭转当前综合倾向需紧盯的 1-2 个最关键指标"""

        self.first_prompt = prompt
        return prompt

    def generate_second_layer_prompt(self, conflict_analysis, position_info, ai_config):
        """生成第二层LLM提示词：持仓融合与交易计划"""
        # 获取交易策略
        strategy_type = ai_config.get('trading_strategy', 'neutral')
        
        # 获取策略提示
        strategy_prompt = self._get_strategy_prompt(strategy_type)
        self.strategy_prompt = strategy_prompt

        # 判断持仓状态
        holding_shares = position_info.get('holding_shares', 0)
        unrealized_pnl_pct = position_info.get('unrealized_pnl_pct', 0)
        avg_cost = position_info.get('avg_cost', 0)
        current_price = position_info.get('current_price', 0)

        if holding_shares == 0:
            position_status = "空仓"
            position_desc = f"当前为空仓状态，尚未持有该股。"
        else:
            position_status = "持仓中"
            profit_status = "盈利" if unrealized_pnl_pct >= 0 else "亏损"
            position_desc = f"当前持有 {holding_shares} 股，成本 {avg_cost:.2f} 元，现价 {current_price:.2f} 元，{profit_status} {abs(unrealized_pnl_pct):.1f}%。"

        prompt = f"""【场景】你是客户的专业交易教练。以下是投资委员会的综合研判和客户当前持仓，请基于交易策略给出具体、可执行的交易计划。

【交易策略】
{strategy_prompt}

【综合研判】
{conflict_analysis}

【客户持仓状态】
股票：{position_info['ticker']}
状态：{position_status}
{position_desc}

【详细持仓信息】
- 持仓数量：{position_info['holding_shares']} 股
- 平均成本：{position_info['avg_cost']:.2f} 元
- 当前价格：{position_info['current_price']:.2f} 元
- 浮动盈亏：{position_info['unrealized_pnl_pct']:.1f}%
- 买入次数：{position_info['buy_count']} 次
- 卖出次数：{position_info['sell_count']} 次

【输出格式要求】
请按照以下格式输出，每项单独一行，不要使用列表符号：

操作方向：[加仓/减仓/清仓/持有不动/观望/建议介入]
操作理由：[详细说明操作理由，结合综合研判和持仓情况]
操作数量：[如果操作，具体数量或比例；如果观望，写"无"]
价格条件：[触发操作的具体价格条件，例如"若股价跌破 X 元则减仓至半仓"；如果观望，写"等待信号"]
监控指标：[未来1-2周需要监控的关键盘面信号，列出3-5个]
止损策略：[硬性止损线，具体价格或亏损百分比；如果观望，写"暂不适用"]
介入时机：[如果是空仓，说明什么情况下可以介入；如果有持仓，写"当前持仓中"]

【特别说明】
- 如果当前为空仓，请重点分析是否值得介入、什么条件下可以介入
- 如果当前有持仓，请明确建议是继续持有、止盈还是止损
- 所有建议必须基于综合研判和交易策略，逻辑清晰，可执行性强"""

        self.second_prompt = prompt
        return prompt

    def _get_strategy_prompt(self, strategy_type):
        """获取交易策略提示词"""
        strategy_prompts = {
            'trend_following': '''
【趋势跟踪策略】
核心思想：只在市场有明显趋势时交易，不预测顶底，不参与震荡。
关键规则：
- 趋势判断：参考ADX指标、均线排列方向
- 开仓条件：ADX > 25通常视为有趋势，结合波动率和价格行为灵活判断
- 无趋势处理：应建议"观望"或"减仓"，不应强行寻找反弹机会
- 止损：跌破趋势线或关键均线时止损
''',
            'mean_reversion': '''
【均值回归策略】
核心思想：价格会回归均值，在极端位置反向交易。
关键规则：
- 极端判断：RSI < 30或 > 70，CCI < -100或 > 100，布林带% B < 0或 > 1
- 反转确认：MACD柱状线缩短、KDJ金叉/死叉雏形
- 止损：突破布林带外侧1.5倍ATR时止损
- 目标：回归均值附近止盈
''',
            'swing': '''
【波段交易策略】
核心思想：持仓数天至数周，捕捉日线级别的上升/下降波段。
关键规则：
- 趋势共振：日线趋势与周线是否共振，共振时按方向交易，背离时降低仓位
- 入场点：回调至关键支撑/阻力位，结合KDJ或MACD转向信号
- 止盈：前高/前低附近或目标位
- 止损：关键支撑/阻力位突破
''',
            'neutral': '''
【中性策略】
核心思想：无预设策略偏好，基于技术指标给出客观、平衡的分析。
关键规则：
- 综合判断：考虑多空双方信号
- 趋势、动量、量能、波动率等因素综合考量
- 给出最适合当前技术状态的操作方向
'''
        }
        return strategy_prompts.get(strategy_type, strategy_prompts['neutral'])

    def get_position_info(self, trading_records):
        """获取持仓信息"""
        position_info = {
            'ticker': self.ticker,
            'holding_shares': 0,
            'avg_cost': 0,
            'current_price': 0,
            'unrealized_pnl_pct': 0,
            'buy_count': 0,
            'sell_count': 0
        }

        if self.ticker in trading_records:
            total_shares = 0
            total_cost = 0
            buy_ops = 0
            sell_ops = 0

            for operation in trading_records[self.ticker]:
                if operation['type'] == 'buy':
                    total_shares += operation['shares']
                    total_cost += operation['price'] * operation['shares']
                    buy_ops += 1
                elif operation['type'] == 'sell':
                    total_shares -= operation['shares']
                    total_cost -= operation['price'] * operation['shares']
                    sell_ops += 1

            position_info['holding_shares'] = total_shares
            position_info['buy_count'] = buy_ops
            position_info['sell_count'] = sell_ops

            if total_shares > 0:
                position_info['avg_cost'] = total_cost / total_shares

            position_info['current_price'] = self._get_current_price()

            if position_info['avg_cost'] > 0 and position_info['current_price'] > 0:
                position_info['unrealized_pnl_pct'] = (position_info['current_price'] - position_info['avg_cost']) / position_info['avg_cost'] * 100

        return position_info

    def _get_current_price(self):
        """获取当前价格"""
        valuation_file = os.path.join(self.data_dir, f"{self.ticker}_valuation.csv")

        if os.path.exists(valuation_file):
            try:
                df = pd.read_csv(valuation_file)
                if not df.empty:
                    return df.iloc[-1].get('当日收盘价', df.iloc[-1].get('close', df.iloc[-1].get('收盘价', 0)))
            except:
                pass

        return 0

    def get_ai_analysis(self, prompt, ai_config):
        """获取本地Ollama AI分析结果"""
        try:
            import ollama

            model = ai_config.get('model', 'qwen3.5:35b')
            temperature = ai_config.get('temperature', 0.3)
            max_tokens = ai_config.get('max_tokens', 4000)

            print(f"正在请求本地Ollama AI ({model})...")
            client = ollama.Client(host=ai_config.get('base_url', 'http://localhost:11434'))

            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的金融分析师，擅长股票分析和投资建议。请用中文回复。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            )

            return response['message']['content']
        except Exception as e:
            print(f"调用本地Ollama AI时出错: {str(e)}")
            return f"无法获取AI分析，请检查Ollama服务是否正常运行。错误: {str(e)}"

    def save_first_prompt(self):
        """保存第一层提示词（调用LLM前）"""
        if self.first_prompt:
            timestamp = datetime.now().strftime('%Y%m%d')
            first_file = os.path.join(self.data_dir, f"{self.ticker}_layer1_prompt_{timestamp}.txt")
            with open(first_file, 'w', encoding='utf-8') as f:
                f.write(self.first_prompt)
            print(f"第一层提示词已保存为: {first_file}")
            return first_file
        return None

    def save_second_prompt(self):
        """保存第二层提示词（调用LLM前）"""
        if self.second_prompt:
            timestamp = datetime.now().strftime('%Y%m%d')
            second_file = os.path.join(self.data_dir, f"{self.ticker}_layer2_prompt_{timestamp}.txt")
            with open(second_file, 'w', encoding='utf-8') as f:
                f.write(self.second_prompt)
            print(f"第二层提示词已保存为: {second_file}")
            return second_file
        return None

    def save_report(self, conflict_analysis, trading_plan):
        """保存最终报告"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_final_decision_{timestamp}.md"
        file_path = os.path.join(self.data_dir, filename)

        # 获取各维度摘要
        layer1_data = self.extract_layer1_data()

        md_content = f"""# {self.ticker} 五维综合决策报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 第一层：五维冲突检测与综合研判

{conflict_analysis}

---

## 第二层：交易计划

{trading_plan}

---

## 各维度摘要

### 一、财务分析摘要
- 信号: {layer1_data.get('financial', {}).get('signal', 'N/A')}
- 置信度: {layer1_data.get('financial', {}).get('confidence', 0):.1f}
- 建议: {layer1_data.get('financial', {}).get('suggested_action', 'N/A')}
- 关键异常: {self._format_anomalies(layer1_data.get('financial', {}).get('major_anomalies', []))}

### 二、情绪估值摘要
- 情绪评分: {layer1_data.get('sentiment', {}).get('sentiment_signal', {}).get('情绪评分', 'N/A')}/100
- 情绪信号: {layer1_data.get('sentiment', {}).get('sentiment_signal', {}).get('信号方向', 'N/A')}
- 估值评分: {layer1_data.get('sentiment', {}).get('valuation_signal', {}).get('估值评分', 'N/A')}/100
- 估值信号: {layer1_data.get('sentiment', {}).get('valuation_signal', {}).get('信号方向', 'N/A')}
- 综合建议: {layer1_data.get('sentiment', {}).get('comprehensive', {}).get('建议操作', 'N/A')}

### 三、技术趋势摘要
- 日趋势: {layer1_data.get('technical', {}).get('daily_trend', 'N/A')}
- 周趋势: {layer1_data.get('technical', {}).get('weekly_trend', 'N/A')}
- 指标一致性: {layer1_data.get('technical', {}).get('consistency_score', 0)*100:.0f}%
- 交易信号: {layer1_data.get('technical', {}).get('trading_signal', {}).get('action', 'N/A')}
- 市场状态: {layer1_data.get('technical', {}).get('market_snapshot', 'N/A')}

### 四、股东结构摘要
- 信号: {layer1_data.get('shareholder', {}).get('signal', 'N/A')}
- 评分: {layer1_data.get('shareholder', {}).get('score', 0)}/100
- 建议: {layer1_data.get('shareholder', {}).get('comprehensive', {}).get('建议操作', 'N/A')}

### 五、研报分析摘要
- 买入占比: {layer1_data.get('research', {}).get('rating_summary', {}).get('buy_ratio', 'N/A')}%
- 近三月报告数: {layer1_data.get('research', {}).get('rating_summary', {}).get('reports_3m', 'N/A')}
- 2026年EPS预期: {layer1_data.get('research', {}).get('earnings_forecast', {}).get('eps_forecast', {}).get('eps_2026', {}).get('avg', 'N/A')}元
- 信号: {layer1_data.get('research', {}).get('comprehensive', {}).get('综合信号', 'N/A')}

---

## 数据来源
- 财务分析: {self.ticker}_financial_summary.json
- 情绪估值: {self.ticker}_sentiment_valuation.json
- 技术趋势: {self.ticker}_technical_trend_analysis.json
- 股东结构: {self.ticker}_shareholder_structure.json
- 研究报告: {self.ticker}_research_report_analysis.json

---

**报告说明**: 本报告采用两层决策架构，第一层进行五维冲突检测与综合研判，第二层结合持仓信息生成具体交易计划。"""

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)

        print(f"综合决策报告已保存为: {file_path}")
        return file_path

    def run_analysis(self, ai_config, trading_records):
        """运行完整的两层决策分析"""
        print("=" * 60)
        print(f"开始 {self.ticker} 的五维两层决策分析")
        print("=" * 60)

        # 加载数据
        self.load_analysis_reports()

        # 提取核心信息
        layer1_data = self.extract_layer1_data()
        print("\n=== 五维度核心信号 ===")
        print(f"财务: {layer1_data.get('financial', {}).get('signal', 'N/A')}")
        print(f"情绪: {layer1_data.get('sentiment', {}).get('sentiment_signal', {}).get('信号方向', 'N/A')}")
        print(f"技术: {layer1_data.get('technical', {}).get('daily_trend', 'N/A')}")
        print(f"股东: {layer1_data.get('shareholder', {}).get('signal', 'N/A')}")
        print(f"研报: {layer1_data.get('research', {}).get('comprehensive', {}).get('综合信号', 'N/A')}")

        # 第一层：冲突检测与综合研判
        print("\n" + "=" * 60)
        print("第一层：五维冲突检测与综合研判")
        print("=" * 60)
        first_prompt = self.generate_first_layer_prompt(layer1_data)
        print(f"提示词长度: {len(first_prompt)} 字符")

        # 先保存第一层提示词，再调用LLM
        self.save_first_prompt()
        print("正在调用LLM进行第一层分析...")

        self.conflict_analysis = self.get_ai_analysis(first_prompt, ai_config)
        print("\n【冲突分析结果】")
        print(self.conflict_analysis)

        # 第二层：结合持仓生成交易计划
        print("\n" + "=" * 60)
        print("第二层：结合持仓生成交易计划")
        print("=" * 60)
        position_info = self.get_position_info(trading_records)
        print(f"持仓信息: {position_info}")

        # 新增：获取交易策略配置
        strategy_type = ai_config.get('trading_strategy', 'neutral')
        print(f"交易策略: {strategy_type}")

        second_prompt = self.generate_second_layer_prompt(self.conflict_analysis, position_info, ai_config)
        print(f"提示词长度: {len(second_prompt)} 字符")

        # 先保存第二层提示词，再调用LLM
        self.save_second_prompt()
        print("正在调用LLM进行第二层分析...")

        self.trading_plan = self.get_ai_analysis(second_prompt, ai_config)
        print("\n【交易计划】")
        print(self.trading_plan)

        # 保存最终报告
        self.save_report(self.conflict_analysis, self.trading_plan)

        print("\n" + "=" * 60)
        print("分析完成！")
        print("=" * 60)

        return {
            'conflict_analysis': self.conflict_analysis,
            'trading_plan': self.trading_plan
        }

if __name__ == "__main__":
    import argparse
    import importlib.util

    parser = argparse.ArgumentParser(description="使用两层决策架构进行股票综合分析（五维度）")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, 'config.py')
    trading_records_path = os.path.join(project_root, 'trading_records.py')

    spec = importlib.util.spec_from_file_location("config_module", config_path)
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    AI_CONFIG = config_module.AI_CONFIG

    spec2 = importlib.util.spec_from_file_location("trading_records_module", trading_records_path)
    trading_records_module = importlib.util.module_from_spec(spec2)
    spec2.loader.exec_module(trading_records_module)
    TRADING_RECORDS = trading_records_module.TRADING_RECORDS

    analyzer = TwoLayerDecisionAnalyzer(args.ticker)
    analyzer.run_analysis(AI_CONFIG, TRADING_RECORDS)