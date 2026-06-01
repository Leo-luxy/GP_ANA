# multi_strategy_analyzer.py
# 功能：采用"技术为主，其他避雷"的权重架构进行股票综合分析
# 支持三种交易模式：短期交易、中期持仓、长期投资
# 决策逻辑：技术决定方向与时机，其他维度作为风险过滤器/避雷机制
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class MultiStrategyAnalyzer:
    def __init__(self, ticker, trading_mode='short'):
        self.ticker = ticker
        self.trading_mode = trading_mode  # short, medium, long
        self.data_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data', ticker)
        
        # 五维度数据
        self.analysis_data = {
            'technical': {},
            'financial': {},
            'sentiment': {},
            'shareholder': {},
            'research': {}
        }
        
        # 决策结果
        self.final_signal = None
        self.risk_factors = []
        self.buy_factors = []
        self.prompt = None
        self.stock_info = {
            'name': '',
            'industry': '',
            'pe': '',
            'pb': '',
            'market_cap': ''
        }
        
        # 交易记录和持仓
        self.trading_records = []
        self.position = {
            'total_shares': 0,
            'avg_cost': 0,
            'buy_operations': 0,
            'sell_operations': 0
        }
    
    def get_trading_mode_config(self):
        """获取不同交易模式的权重配置"""
        mode_configs = {
            'short': {
                'name': '短期交易',
                'timeframe': '<1个月',
                'weights': {
                    'technical': 80,
                    'sentiment': 20,
                    'financial': 0,
                    'shareholder': 0,
                    'research': 0
                },
                'description': '以技术趋势和资金流为主，追求短期波段收益',
                'risk_filters': {
                    'peg_threshold': 3.0,
                    'pe_threshold': 150,
                    'debt_ratio': 0.8,
                    'net_cash_flow': False
                }
            },
            'medium': {
                'name': '中期持仓',
                'timeframe': '1-6个月',
                'weights': {
                    'technical': 60,
                    'financial': 30,
                    'shareholder': 10,
                    'sentiment': 0,
                    'research': 0
                },
                'description': '技术面与基本面结合，把握中期趋势',
                'risk_filters': {
                    'peg_threshold': 2.5,
                    'pe_threshold': 100,
                    'debt_ratio': 0.7,
                    'net_cash_flow': True
                }
            },
            'long': {
                'name': '长期投资',
                'timeframe': '>6个月',
                'weights': {
                    'financial': 50,
                    'shareholder': 30,
                    'technical': 20,
                    'sentiment': 0,
                    'research': 0
                },
                'description': '以基本面分析为主，关注公司长期价值',
                'risk_filters': {
                    'peg_threshold': 2.0,
                    'pe_threshold': 80,
                    'debt_ratio': 0.6,
                    'net_cash_flow': True
                }
            }
        }
        return mode_configs.get(self.trading_mode, mode_configs['short'])
    
    def load_all_data(self):
        """加载五维度分析数据"""
        data_mapping = {
            'technical': f"{self.ticker}_technical_trend_analysis.json",
            'financial': f"{self.ticker}_financial_summary.json",
            'sentiment': f"{self.ticker}_sentiment_valuation.json",
            'shareholder': f"{self.ticker}_shareholder_structure.json",
            'research': f"{self.ticker}_research_report_analysis.json"
        }
        
        for data_type, filename in data_mapping.items():
            file_path = os.path.join(self.data_dir, filename)
            if os.path.exists(file_path):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        self.analysis_data[data_type] = json.load(f)
                    print(f"加载{data_type}数据: {file_path}")
                except Exception as e:
                    print(f"读取{data_type}数据时出错: {str(e)}")
            else:
                print(f"未找到{data_type}数据文件: {file_path}")
        
        # 加载股票基本信息
        self.load_stock_info()
    
    def load_stock_info(self):
        """加载股票基本信息"""
        info_file = os.path.join(self.data_dir, f"{self.ticker}_company_basic.json")
        if os.path.exists(info_file):
            with open(info_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'basic_info' in data:
                    self.stock_info['name'] = data['basic_info'].get('公司简称', '')
                    self.stock_info['industry'] = data['basic_info'].get('板块名称层级', '')
        
        # 加载估值信息
        valuation_file = os.path.join(self.data_dir, f"{self.ticker}_valuation.csv")
        if os.path.exists(valuation_file):
            try:
                df = pd.read_csv(valuation_file)
                if not df.empty:
                    latest = df.iloc[0]
                    self.stock_info['pe'] = latest.get('市盈率(TTM)', latest.get('pe_ttm', ''))
                    self.stock_info['pb'] = latest.get('市净率', latest.get('pb', ''))
                    self.stock_info['market_cap'] = latest.get('总市值', '')
            except Exception as e:
                print(f"读取估值CSV时出错: {str(e)}")
    
    def load_trading_records(self, trading_records):
        """加载交易记录"""
        self.trading_records = trading_records.get(self.ticker, [])
        self.calculate_position()
    
    def calculate_position(self):
        """计算当前持仓"""
        total_shares = 0
        total_cost = 0
        buy_ops = 0
        sell_ops = 0
        
        for op in self.trading_records:
            if op['type'] == 'buy':
                total_shares += op['shares']
                total_cost += op['price'] * op['shares']
                buy_ops += 1
            elif op['type'] == 'sell':
                total_shares -= op['shares']
                total_cost -= op['price'] * op['shares']
                sell_ops += 1
        
        self.position = {
            'total_shares': total_shares,
            'avg_cost': total_cost / total_shares if total_shares > 0 else 0,
            'buy_operations': buy_ops,
            'sell_operations': sell_ops
        }
    
    def extract_technical_signal(self):
        """提取技术面信号"""
        tech = self.analysis_data.get('technical', {})
        signal = {
            'action': tech.get('trading_signal', {}).get('action', 'HOLD'),
            'confidence': tech.get('trading_signal', {}).get('confidence', 0),
            'trend_confidence': tech.get('trend_confidence', {}),
            'consistency_score': tech.get('consistency_score', 0),
            'daily_trend': tech.get('multi_timeframe', {}).get('daily_trend', 'UNKNOWN'),
            'weekly_trend': tech.get('multi_timeframe', {}).get('weekly_trend', 'UNKNOWN'),
            'market_snapshot': tech.get('market_snapshot', ''),
            'indicators': tech.get('technical_indicators', {}),
            'overbought': self._is_overbought(tech),
            'oversold': self._is_oversold(tech)
        }
        return signal
    
    def _is_overbought(self, tech_data):
        """判断是否超买"""
        indicators = tech_data.get('technical_indicators', {})
        rsi = indicators.get('RSI', 0)
        cci = indicators.get('CCI', 0)
        bb_pctb = indicators.get('BB_pctB', 0)
        
        if rsi > 75 or cci > 150 or bb_pctb > 1.0:
            return True
        return False
    
    def _is_oversold(self, tech_data):
        """判断是否超卖"""
        indicators = tech_data.get('technical_indicators', {})
        rsi = indicators.get('RSI', 0)
        cci = indicators.get('CCI', 0)
        bb_pctb = indicators.get('BB_pctB', 0)
        
        if rsi < 25 or cci < -150 or bb_pctb < 0:
            return True
        return False
    
    def extract_financial_risk(self):
        """提取财务风险信号（避雷机制）"""
        fin = self.analysis_data.get('financial', {})
        risk_factors = []
        buy_factors = []

        key_metrics = fin.get('key_metrics', {})
        detailed_metrics = fin.get('detailed_metrics', {})
        valuation_metrics = detailed_metrics.get('valuation', {})
        cashflow_metrics = detailed_metrics.get('cashflow', {})

        pe = float(key_metrics.get('PE(TTM)', 0) or 0)
        pb = float(key_metrics.get('PB', 0) or 0)
        roe = float(key_metrics.get('ROE', 0) or 0)
        net_profit_margin = float(key_metrics.get('净利率', 0) or 0)
        debt_ratio = float(key_metrics.get('资产负债率', 0) or 0)
        revenue_growth = float(key_metrics.get('营收同比增长率', 0) or 0)
        profit_growth = float(key_metrics.get('净利润同比增长率', 0) or 0)
        peg = float(valuation_metrics.get('PEG', 0) or 0)
        operating_cashflow = float(cashflow_metrics.get('经营活动现金流净额', 0) or 0)

        config = self.get_trading_mode_config()

        # 估值风险
        if pe > config['risk_filters']['pe_threshold']:
            risk_factors.append(f"PE({pe:.1f})过高，超过阈值{config['risk_filters']['pe_threshold']}")
        if pb > 10:
            risk_factors.append(f"PB({pb:.1f})过高")
        if peg > 0 and peg > 2.0:
            risk_factors.append(f"PEG({peg:.2f})过高，超过合理阈值2.0")

        # 盈利能力风险
        if net_profit_margin < 5:
            risk_factors.append(f"净利率({net_profit_margin:.1f}%)低于5%")
        if roe < 8:
            risk_factors.append(f"ROE({roe:.1f}%)低于8%")

        # 负债风险 - debt_ratio已经是百分比形式（如33.9表示33.9%），阈值转为百分比形式比较
        debt_threshold_pct = config['risk_filters']['debt_ratio'] * 100
        if debt_ratio > debt_threshold_pct:
            risk_factors.append(f"资产负债率({debt_ratio:.1f}%)过高")

        # 现金流风险
        if operating_cashflow < 0:
            risk_factors.append(f"经营活动现金流为负({operating_cashflow:.0f})")

        # 增长风险
        if profit_growth < -20:
            risk_factors.append(f"净利润同比下降({profit_growth:.1f}%)")

        # 利好因素
        if revenue_growth > 20:
            buy_factors.append(f"营收增长强劲({revenue_growth:.1f}%)")
        if profit_growth > 20:
            buy_factors.append(f"净利润增长强劲({profit_growth:.1f}%)")
        if roe > 15:
            buy_factors.append(f"ROE优良({roe:.1f}%)")
        if peg > 0 and peg < 1.5:
            buy_factors.append(f"PEG合理({peg:.2f})，估值与成长性匹配")

        return {
            'risk_factors': risk_factors,
            'buy_factors': buy_factors,
            'signal': fin.get('verdict', {}).get('signal', 'NEUTRAL'),
            'confidence': fin.get('verdict', {}).get('confidence', 0),
            'peg': peg,
            'pe': pe,
            'operating_cashflow': operating_cashflow
        }
    
    def extract_sentiment_signal(self):
        """提取情绪/资金流信号"""
        sent = self.analysis_data.get('sentiment', {})
        sentiment_signal = sent.get('sentiment_signal', {})
        valuation_signal = sent.get('valuation_signal', {})
        
        risk_factors = []
        buy_factors = []
        
        # 资金流异常
        fund_flow = sent.get('fund_flow', {})
        anomalies = fund_flow.get('major_anomalies', [])
        for anomaly in anomalies:
            if anomaly.get('type') == 'risk':
                risk_factors.append(anomaly.get('detail', ''))
        
        # 主力连续流出检测
        main_flow_days = fund_flow.get('主力连续流入天数', 0)
        if main_flow_days == 0:
            main_net_5d_avg = fund_flow.get('主力净流入5日平均净占比', 0)
            if main_net_5d_avg < -0.5:
                risk_factors.append(f"主力连续流出，5日平均净占比{main_net_5d_avg:.2f}%")
        
        # 融资余额风险
        margin_data = sent.get('margin', {})
        margin_ratio = margin_data.get('融资余额5日变化率', 0)
        if margin_ratio > 5:
            risk_factors.append(f"融资余额快速上升，5日变化率{margin_ratio:.2f}%")
        
        # 主力资金流出
        if sentiment_signal.get('信号方向') == 'BEARISH':
            risk_factors.extend(sentiment_signal.get('利空信号', []))
        
        if sentiment_signal.get('信号方向') == 'BULLISH':
            buy_factors.extend(sentiment_signal.get('利多信号', []))
        
        return {
            'risk_factors': risk_factors,
            'buy_factors': buy_factors,
            'sentiment_score': sentiment_signal.get('情绪评分', 50),
            'valuation_score': valuation_signal.get('估值评分', 50),
            'signal': sentiment_signal.get('信号方向', 'NEUTRAL'),
            'main_flow_days': main_flow_days,
            'main_net_5d_avg': fund_flow.get('主力净流入5日平均净占比', 0)
        }
    
    def extract_shareholder_risk(self):
        """提取股东结构风险信号"""
        sh = self.analysis_data.get('shareholder', {})
        signal = sh.get('shareholder_signal', {})
        
        risk_factors = []
        buy_factors = []
        
        # 股权集中度风险
        if signal.get('股权集中度', '') == '高度集中':
            risk_factors.append("股权高度集中")
        
        # 机构参与度
        if signal.get('机构参与度', '') == '低':
            risk_factors.append("机构参与度低")
        
        # 股东人数异常
        anomalies = sh.get('shareholder_num', {}).get('shareholder_anomalies', [])
        for anomaly in anomalies:
            risk_factors.append(anomaly.get('detail', ''))
        
        # 利好因素
        buy_factors.extend(signal.get('利多信号', []))
        
        return {
            'risk_factors': risk_factors,
            'buy_factors': buy_factors,
            'score': signal.get('股东结构评分', 50),
            'signal': signal.get('信号方向', 'NEUTRAL')
        }
    
    def extract_research_signal(self):
        """提取研报信号（弱参考）"""
        rr = self.analysis_data.get('research', {})
        rating_summary = rr.get('rating_summary', {})
        
        buy_ratio = float(rating_summary.get('buy_ratio', 0) or 0)
        reports_count = rating_summary.get('reports_3m', 0)
        
        return {
            'buy_ratio': buy_ratio,
            'reports_count': reports_count,
            'signal': 'BUY' if buy_ratio > 70 else 'NEUTRAL'
        }
    
    def extract_support_resistance(self):
        """提取关键支撑位和阻力位"""
        tech = self.analysis_data.get('technical', {})
        indicators = tech.get('technical_indicators', {})
        
        # 从布林带和均线提取关键价位
        support = indicators.get('BB_lower', 0)
        resistance = indicators.get('BB_upper', 0)
        current = indicators.get('close', 0)
        ma20 = indicators.get('MA20', 0)
        
        return {
            'current_price': current,
            'support': support,
            'resistance': resistance,
            'ma20': ma20
        }
    
    def calculate_programmatic_signal(self):
        """
        程序化决策引擎：根据技术面和风险过滤器计算信号
        遵循方案中描述的逻辑
        """
        tech_signal = self.extract_technical_signal()
        fin_risk = self.extract_financial_risk()
        sent_risk = self.extract_sentiment_signal()
        sh_risk = self.extract_shareholder_risk()
        risk_check = self.check_risk_filters()
        
        tech_action = tech_signal['action']
        tech_confidence = tech_signal['confidence']
        is_overbought = tech_signal['overbought']
        is_oversold = tech_signal['oversold']
        
        risk_level = risk_check['risk_level']
        risk_status = risk_check['risk_status']
        num_risk_factors = len(risk_check['triggered_filters'])
        
        # 决策逻辑
        final_signal = 'HOLD'
        confidence = 0.5
        reasoning = []
        
        # 情况1：技术面是STRONG_BULLISH且无风险
        if tech_action == 'BUY' and tech_confidence >= 0.7 and risk_status == 'LOW':
            final_signal = 'BUY'
            confidence = min(tech_confidence, 0.8)
            reasoning.append("技术面强劲，无风险过滤器触发")
        
        # 情况2：技术面是BULLISH但短期超买
        elif tech_action in ['BUY', 'HOLD'] and is_overbought:
            final_signal = 'HOLD'
            confidence = 0.7
            reasoning.append("短期超买，等待回调")
        
        # 情况3：技术面是BEARISH或有严重风险
        elif tech_action == 'SELL' or risk_status == 'HIGH':
            final_signal = 'SELL'
            confidence = max(tech_confidence if tech_action == 'SELL' else 0.6, 0.6)
            if risk_status == 'HIGH':
                reasoning.append(f"风险等级高({num_risk_factors}个风险触发)")
            if tech_action == 'SELL':
                reasoning.append("技术面看空")
        
        # 情况4：维度严重矛盾
        elif (tech_action in ['BUY', 'STRONG_BUY'] and num_risk_factors >= 2) or \
             (tech_action == 'SELL' and sent_risk['signal'] == 'BULLISH'):
            final_signal = 'HOLD'
            confidence = 0.5
            reasoning.append("多维度信号矛盾，观望为主")
        
        # 情况5：其他情况，以技术面为主
        else:
            final_signal = tech_action
            confidence = tech_confidence
            reasoning.append(f"以技术面信号为主，伴随{num_risk_factors}个风险")
        
        return {
            'signal': final_signal,
            'confidence': confidence,
            'reasoning': reasoning,
            'tech_action': tech_action,
            'risk_status': risk_status,
            'num_risk_factors': num_risk_factors
        }
    
    def check_risk_filters(self):
        """检查风险过滤器是否触发"""
        risk_level = 0
        triggered_filters = []
        
        # 财务风险
        fin_risk = self.extract_financial_risk()
        if fin_risk['risk_factors']:
            risk_level += len(fin_risk['risk_factors']) * 2
            triggered_filters.extend([f"财务: {r}" for r in fin_risk['risk_factors']])
        
        # 情绪风险
        sent_risk = self.extract_sentiment_signal()
        if sent_risk['risk_factors']:
            risk_level += len(sent_risk['risk_factors'])
            triggered_filters.extend([f"情绪: {r}" for r in sent_risk['risk_factors']])
        
        # 股东风险
        sh_risk = self.extract_shareholder_risk()
        if sh_risk['risk_factors']:
            risk_level += len(sh_risk['risk_factors'])
            triggered_filters.extend([f"股东: {r}" for r in sh_risk['risk_factors']])
        
        return {
            'risk_level': risk_level,
            'triggered_filters': triggered_filters,
            'risk_status': 'HIGH' if risk_level >= 5 else 'MEDIUM' if risk_level >= 2 else 'LOW'
        }
    
    def generate_analysis_prompt(self):
        """生成综合分析提示词"""
        tech = self.extract_technical_signal()
        fin = self.extract_financial_risk()
        sent = self.extract_sentiment_signal()
        sh = self.extract_shareholder_risk()
        rr = self.extract_research_signal()
        risk_check = self.check_risk_filters()
        sr = self.extract_support_resistance()
        programmatic = self.calculate_programmatic_signal()
        
        mode_config = self.get_trading_mode_config()
        
        prompt = f"""你是一位专业的股票投资分析师。请基于以下数据，按照【{mode_config['name']}】模式进行分析。

【交易模式配置】
- 模式名称：{mode_config['name']}
- 时间框架：{mode_config['timeframe']}
- 核心描述：{mode_config['description']}
- 权重架构：技术{mode_config['weights']['technical']}%、财务{mode_config['weights']['financial']}%、股东{mode_config['weights']['shareholder']}%、情绪{mode_config['weights']['sentiment']}%、研报{mode_config['weights']['research']}%

【程序化决策参考】
- 程序化信号：{programmatic['signal']} (信心度: {programmatic['confidence']:.2f})
- 决策逻辑：{'; '.join(programmatic['reasoning'])}

【决策原则】
技术面决定方向与时机，其他维度作为风险过滤器：
1. 若技术信号为STRONG_BULLISH且无风险过滤器触发 → 买入/加仓
2. 若技术信号为BULLISH但短期超买(RSI>75或CCI>150) → 等待回调(HOLD)
3. 若技术信号为BEARISH或财务避雷触发(PE过高、负债>70%、净现金流为负) → 减仓/卖出
4. 若维度严重矛盾 → 观望，等待技术面与资金流共振

【股票基本信息】
- 股票代码：{self.ticker}
- 股票名称：{self.stock_info['name']}
- 所属行业：{self.stock_info['industry']}
- PE(TTM)：{self.stock_info['pe']}
- PB：{self.stock_info['pb']}

【技术面分析】
- 交易信号：{tech['action']} (信心度: {tech['confidence']:.1f})
- 日趋势：{tech['daily_trend']}，周趋势：{tech['weekly_trend']}
- 指标一致性：{tech['consistency_score']*100:.0f}%
- 超买超卖：超买={tech['overbought']}，超卖={tech['oversold']}
- 市场快照：{tech['market_snapshot']}
- 关键指标：RSI={tech['indicators'].get('RSI', 'N/A')}, MACD_DIF={tech['indicators'].get('DIF', 'N/A')}, ATR={tech['indicators'].get('ATR', 'N/A')}, 现价={tech['indicators'].get('close', 'N/A')}
- 关键价位：支撑位{sr['support']:.2f}，阻力位{sr['resistance']:.2f}，MA20={sr['ma20']:.2f}

【财务风险检查】
- 信号：{fin['signal']}
- 风险因素：{'; '.join(fin['risk_factors']) if fin['risk_factors'] else '无'}
- 利好因素：{'; '.join(fin['buy_factors']) if fin['buy_factors'] else '无'}

【情绪/资金流】
- 情绪评分：{sent['sentiment_score']}/100，估值评分：{sent['valuation_score']}/100
- 信号方向：{sent['signal']}
- 风险因素：{'; '.join(sent['risk_factors']) if sent['risk_factors'] else '无'}
- 利好因素：{'; '.join(sent['buy_factors']) if sent['buy_factors'] else '无'}

【股东结构】
- 信号：{sh['signal']}，评分：{sh['score']}/100
- 风险因素：{'; '.join(sh['risk_factors']) if sh['risk_factors'] else '无'}
- 利好因素：{'; '.join(sh['buy_factors']) if sh['buy_factors'] else '无'}

【机构研报】
- 买入评级占比：{rr['buy_ratio']}%，近三月报告数：{rr['reports_count']}篇
- 信号：{rr['signal']}

【风险过滤器汇总】
- 风险等级：{risk_check['risk_status']}
- 触发的过滤器：{'; '.join(risk_check['triggered_filters']) if risk_check['triggered_filters'] else '无'}

【当前持仓】
- 持仓数量：{self.position['total_shares']}股
- 平均成本：{self.position['avg_cost']:.2f}元
- 当前价格：{tech['indicators'].get('close', 0):.2f}元
- 浮动盈亏：{((tech['indicators'].get('close', 0) - self.position['avg_cost']) / self.position['avg_cost'] * 100) if self.position['avg_cost'] > 0 else 0:.1f}%

【输出要求】
请按照以下格式输出详细分析：

## 主信号
[BUY/HOLD/SELL]

## 避雷触发项
[列出所有触发的风险过滤器，若无则写"无"]

## 核心逻辑
[解释技术信号与风险过滤器的相互作用]

## 具体操作建议
- 行动：[买入/卖出/持有/观望]
- 价位区间：[建议买入/卖出的价格区间]
- 仓位建议：[占总资金的百分比或具体股数]
- 关键价位：支撑位和阻力位
- 止损策略：具体止损价或止损条件

## 监控要点
[未来需要重点关注的1-3个指标或事件]"""
        
        self.prompt = prompt
        return prompt
    
    def save_prompt(self):
        """保存提示词到本地"""
        if self.prompt:
            timestamp = datetime.now().strftime('%Y%m%d')
            filename = f"{self.ticker}_{self.trading_mode}_strategy_prompt_{timestamp}.txt"
            file_path = os.path.join(self.data_dir, filename)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self.prompt)
            print(f"分析提示词已保存为: {file_path}")
            return file_path
        return None
    
    def get_ai_analysis(self, prompt, ai_config):
        """获取AI分析结果，支持自动尝试多个备用模型"""
        try:
            import ollama
            
            temperature = ai_config.get('temperature', 0.3)
            max_tokens = ai_config.get('max_tokens', 16000)
            base_url = ai_config.get('base_url', 'http://localhost:11434')
            
            # 收集要尝试的模型列表
            models_to_try = [ai_config.get('model', 'gemma3:latest')]
            fallback_models = ai_config.get('fallback_models', [])
            for m in fallback_models:
                if m not in models_to_try:
                    models_to_try.append(m)
            
            print(f"正在请求本地Ollama AI...")
            print(f"  - 服务地址: {base_url}")
            print(f"  - 将尝试 {len(models_to_try)} 个模型: {models_to_try}")
            
            client = ollama.Client(host=base_url)
            
            for i, model in enumerate(models_to_try):
                try:
                    print(f"\n  [尝试 {i+1}/{len(models_to_try)}] 模型: {model}")
                    print("    发送请求中...")
                    
                    # 构建 options 字典 - 注意：某些模型不设置 num_predict 更好
                    options_dict = {"temperature": temperature}
                    
                    # 对某些模型不设置 num_predict，因为设置过小会导致空输出
                    # gemma4, qwen3.5 等模型最好不设置 num_predict
                    if not (model.startswith('gemma4') or model.startswith('qwen3.5')):
                        options_dict["num_predict"] = max_tokens
                    
                    response = client.chat(
                        model=model,
                        messages=[
                            {"role": "system", "content": "你是一位专业的金融分析师，擅长股票技术分析和投资建议。请用中文回复。"},
                            {"role": "user", "content": prompt}
                        ],
                        options=options_dict
                    )
                    
                    ai_content = response['message']['content']
                    
                    if ai_content and len(ai_content.strip()) > 20:
                        print(f"    ✓ AI响应成功! 长度: {len(ai_content)} 字符")
                        return ai_content
                    else:
                        print(f"    ⚠ 响应过短或为空，尝试下一个模型...")
                        
                except Exception as model_error:
                    print(f"    ✗ 模型 '{model}' 失败: {model_error}")
                    continue
            
            # 所有模型都失败了，使用程序化分析
            print("\n  所有AI模型都失败了，使用程序化分析作为备用方案")
            return self._generate_programmatic_fallback_analysis()
            
        except Exception as e:
            print(f"  ❌ 调用本地Ollama AI时出错: {e}")
            print(f"  - 使用程序化分析作为备用方案")
            return self._generate_programmatic_fallback_analysis()
    
    def _generate_programmatic_fallback_analysis(self):
        """生成程序化分析报告（AI调用失败时的备用方案）"""
        tech = self.extract_technical_signal()
        fin = self.extract_financial_risk()
        sent = self.extract_sentiment_signal()
        sh = self.extract_shareholder_risk()
        risk_check = self.check_risk_filters()
        programmatic = self.calculate_programmatic_signal()
        sr = self.extract_support_resistance()
        
        # 生成主信号
        signal = programmatic['signal']
        
        # 整理避雷项
        risk_list = risk_check['triggered_filters']
        risk_text = '\n'.join([f"{i+1}. {r}" for i, r in enumerate(risk_list)]) if risk_list else "无"
        
        # 生成操作建议
        action_advice = {
            'BUY': '分批买入',
            'HOLD': '观望等待',
            'SELL': '减仓或卖出'
        }.get(signal, '观望等待')
        
        # 核心逻辑
        core_logic = f"程序化决策结果：{signal}（信心度：{programmatic['confidence']:.2f}）\n"
        core_logic += f"决策逻辑：{', '.join(programmatic['reasoning'])}\n\n"
        core_logic += f"技术面信号：{tech['action']}（信心度：{tech['confidence']:.1f}）\n"
        core_logic += f"风险等级：{risk_check['risk_status']}（{len(risk_list)}个风险触发）\n"
        
        # 价位建议
        support = sr['support']
        resistance = sr['resistance']
        current = tech['indicators'].get('close', 0)
        
        if signal == 'BUY':
            price_range = f"{support:.2f} - {sr['ma20']:.2f}"
        elif signal == 'SELL':
            price_range = f"{sr['ma20']:.2f} - {resistance:.2f}"
        else:
            price_range = f"{support:.2f} - {resistance:.2f}"
        
        # 仓位建议
        if risk_check['risk_status'] == 'LOW':
            position = "建议仓位：30-50%"
        elif risk_check['risk_status'] == 'MEDIUM':
            position = "建议仓位：10-30%"
        else:
            position = "建议仓位：0-10%"
        
        # 止损策略
        if self.position['total_shares'] > 0:
            stop_loss = f"止损价：{support * 0.95:.2f}"
        else:
            stop_loss = "暂不设置止损，等待入场信号"
        
        # 监控要点
        monitor = [
            "RSI指标变化，观察是否突破超买/超卖区间",
            "主力资金流向变化",
            "成交量配合情况"
        ]
        monitor_text = '\n'.join([f"{i+1}. {item}" for i, item in enumerate(monitor)])
        
        return f"""## 主信号
{signal}

## 避雷触发项
{risk_text}

## 核心逻辑
{core_logic}

## 具体操作建议
- **行动**：{action_advice}
- **价位区间**：{price_range}
- **仓位建议**：{position}
- **关键价位**：
  - 支撑位：{support:.2f}
  - 阻力位：{resistance:.2f}
  - MA20：{sr['ma20']:.2f}
  - 当前价：{current:.2f}
- **止损策略**：{stop_loss}

## 监控要点
{monitor_text}

---

⚠️ **说明**：此为程序化生成的分析结果（AI调用失败时的备用方案），建议手动审核后使用。"""
    
    def save_analysis_report(self, analysis_content):
        """保存分析报告"""
        timestamp = datetime.now().strftime('%Y%m%d')
        filename = f"{self.ticker}_{self.trading_mode}_strategy_analysis_{timestamp}.md"
        file_path = os.path.join(self.data_dir, filename)
        
        mode_config = self.get_trading_mode_config()
        
        md_content = f"""# {self.stock_info['name']} ({self.ticker}) 综合策略分析报告

## 基本信息
- **股票代码**: {self.ticker}
- **股票名称**: {self.stock_info['name']}
- **所属行业**: {self.stock_info['industry']}
- **分析模式**: {mode_config['name']} ({mode_config['timeframe']})
- **分析时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 权重架构
| 维度 | 权重 | 作用 |
|------|------|------|
| 技术趋势 | {mode_config['weights']['technical']}% | 主要决策依据 |
| 财务估值 | {mode_config['weights']['financial']}% | 风险过滤器 |
| 股东结构 | {mode_config['weights']['shareholder']}% | 避雷机制 |
| 情绪/资金流 | {mode_config['weights']['sentiment']}% | 辅助验证 |
| 机构研报 | {mode_config['weights']['research']}% | 弱参考 |

## 决策原则
- 技术面决定方向与时机
- 其他维度作为风险过滤器/避雷机制
- 技术信号与多个过滤器冲突时，优先采取谨慎动作

---

## AI分析结果

{analysis_content}

---

## 数据来源
- 技术趋势: {self.ticker}_technical_trend_analysis.json
- 财务分析: {self.ticker}_financial_summary.json
- 情绪估值: {self.ticker}_sentiment_valuation.json
- 股东结构: {self.ticker}_shareholder_structure.json
- 研究报告: {self.ticker}_research_report_analysis.json

---

**风险提示**: 本报告仅供参考，不构成投资建议。投资有风险，入市需谨慎。"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(md_content)
        
        print(f"综合策略分析报告已保存为: {file_path}")
        return file_path
    
    def run_analysis(self, ai_config, trading_records):
        """运行完整分析"""
        print("=" * 70)
        print(f"开始 {self.ticker} 的【{self.get_trading_mode_config()['name']}】分析")
        print("=" * 70)
        
        # 加载数据
        self.load_all_data()
        self.load_trading_records(trading_records)
        
        # 生成提示词
        prompt = self.generate_analysis_prompt()
        print(f"\n提示词长度: {len(prompt)} 字符")
        
        # 保存提示词
        self.save_prompt()
        
        # 获取AI分析
        print("\n正在调用AI进行分析...")
        analysis_result = self.get_ai_analysis(prompt, ai_config)
        
        print("\n" + "=" * 70)
        print("AI分析结果")
        print("=" * 70)
        print(analysis_result)
        
        # 保存报告
        self.save_analysis_report(analysis_result)
        
        print("\n" + "=" * 70)
        print("分析完成！")
        print("=" * 70)
        
        return analysis_result

if __name__ == "__main__":
    import argparse
    import importlib.util
    
    parser = argparse.ArgumentParser(description="多策略股票综合分析器（支持短期/中期/长期模式）")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：688981.SH")
    parser.add_argument('--mode', choices=['short', 'medium', 'long'], default='short', 
                        help="交易模式：short(短期交易)、medium(中期持仓)、long(长期投资)")
    args = parser.parse_args()
    
    # 动态导入配置
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
    
    # 创建分析器并运行
    analyzer = MultiStrategyAnalyzer(args.ticker, args.mode)
    analyzer.run_analysis(AI_CONFIG, TRADING_RECORDS)