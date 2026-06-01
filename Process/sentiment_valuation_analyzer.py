# sentiment_valuation_analyzer.py
"""
情绪估值分析器
功能：加载资金流、融资融券、估值三方数据，按模板生成JSON
三个子模块结果由程序计算关键指标（如主力净流入率、融资余额变化率、PEG）
"""

import json
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Any, List

# 添加父目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# 加载申万阈值配置
from shenwan_config import get_shenwan_thresholds

# 加载项目配置（使用别名避免与config包冲突）
import importlib.util
config_spec = importlib.util.spec_from_file_location("project_config",
    os.path.join(project_root, 'config.py'))
project_config = importlib.util.module_from_spec(config_spec)
config_spec.loader.exec_module(project_config)
DATA_DIR = project_config.DATA_DIR


class SentimentValuationAnalyzer:
    """情绪估值分析器"""
    
    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'fund_flow': None,
            'margin': None,
            'valuation': None,
            'company_basic': None
        }
        self.company_name = None
        self.result = {}
        self.shenwan_manager = get_shenwan_thresholds()
        self.industry_thresholds = None
    
    @staticmethod
    def format_decimal(value, places=2):
        """统一格式化小数位数"""
        if value is None or pd.isna(value):
            return 0.0
        try:
            num = float(value)
            return round(num, places)
        except (ValueError, TypeError):
            return 0.0
    
    @staticmethod
    def format_dict_decimals(data):
        """递归格式化字典中所有数值的小数位数"""
        if isinstance(data, dict):
            return {k: SentimentValuationAnalyzer.format_dict_decimals(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [SentimentValuationAnalyzer.format_dict_decimals(item) for item in data]
        elif isinstance(data, (int, float)) and not isinstance(data, bool):
            # 如果是整数或可以转换为整数的浮点数，保持为整数
            if isinstance(data, int):
                return data
            try:
                if data.is_integer():
                    return int(data)
            except (ValueError, TypeError):
                pass
            return SentimentValuationAnalyzer.format_decimal(data)
        else:
            return data
    
    def load_all_data(self) -> bool:
        """加载所有可用的情绪估值数据"""
        print(f"[{self.ticker}] 开始加载情绪估值数据...")
        
        # 加载资金流数据
        self._load_csv('fund_flow', f'{self.ticker}_fund_flow.csv')
        
        # 加载融资融券数据
        self._load_csv('margin', f'{self.ticker}_margin_data.csv')
        
        # 加载估值数据
        self._load_csv('valuation', f'{self.ticker}_valuation.csv')
        
        # 加载公司基本信息（用于获取行业）
        self._load_json('company_basic', f'{self.ticker}_company_basic.json')
        
        # 尝试从其他文件获取公司名称
        self._extract_company_name()
        
        # 获取申万行业阈值
        self._load_industry_thresholds()
        
        return any(v is not None for v in self.data.values())
    
    def _load_industry_thresholds(self):
        """从申万数据加载行业阈值"""
        company_basic = self.data.get('company_basic')
        if not company_basic:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            return

        basic_info = company_basic.get('basic_info', {})
        industry_level = basic_info.get('板块名称层级', '')

        if not industry_level:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            return

        industry_parts = industry_level.split('-')
        industry_name = industry_parts[-1].strip() if len(industry_parts) > 0 else ''

        if not industry_name:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            return

        # 首先尝试精确匹配
        level1_info = self.shenwan_manager.get_level1_industry_info(industry_name)

        # 如果精确匹配失败，使用一级行业名称
        if not level1_info:
            level1_name = industry_parts[0].strip() if len(industry_parts) > 0 else ''
            level1_info = self.shenwan_manager.get_level1_industry_info(level1_name)
            if level1_info:
                print(f"  精确匹配失败，使用一级行业: {level1_name}")

        if level1_info:
            self.industry_thresholds = self.shenwan_manager.get_industry_thresholds(
                industry_name=level1_info.get('行业名称')
            )
            print(f"  加载申万行业阈值成功: {level1_info.get('行业名称')}")
            print(f"    PE基准: {self.industry_thresholds.get('pe_medium', 'N/A')}")
            print(f"    PB基准: {self.industry_thresholds.get('pb_medium', 'N/A')}")
        else:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            print(f"  未找到申万行业数据，使用默认阈值")
    
    def _load_json(self, key: str, filename: str):
        """加载JSON数据文件"""
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    self.data[key] = json.load(f)
                print(f"  加载 {filename} 成功")
            except Exception as e:
                print(f"  加载 {filename} 失败: {e}")
        else:
            print(f"  文件不存在: {filename}")
    
    def _load_csv(self, key: str, filename: str):
        """加载CSV数据文件"""
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath)
                self.data[key] = df
                print(f"  加载 {filename} 成功，共 {len(df)} 条数据")
            except Exception as e:
                print(f"  加载 {filename} 失败: {e}")
        else:
            print(f"  文件不存在: {filename}")
    
    def _extract_company_name(self):
        """尝试从现有数据中提取公司名称"""
        # 从融资融券数据中提取
        if self.data.get('margin') is not None and len(self.data['margin']) > 0:
            if '证券简称' in self.data['margin'].columns:
                self.company_name = self.data['margin']['证券简称'].iloc[0]
                return
        
        # 尝试从公司基本信息文件获取
        basic_file = os.path.join(self.stock_dir, f'{self.ticker}_company_basic.json')
        if os.path.exists(basic_file):
            try:
                with open(basic_file, 'r', encoding='utf-8') as f:
                    basic_data = json.load(f)
                    if isinstance(basic_data, dict):
                        self.company_name = basic_data.get('company_name', basic_data.get('名称', None))
            except Exception:
                pass
        
        if not self.company_name:
            self.company_name = self.ticker
    
    def calculate_fund_flow_metrics(self) -> Dict[str, Any]:
        """计算资金流关键指标"""
        metrics = {}
        anomalies = []
        
        if self.data.get('fund_flow') is None or len(self.data['fund_flow']) == 0:
            return metrics
        
        df = self.data['fund_flow']
        df = df.copy()
        
        # 确保日期排序（最新在最前）
        if '日期' in df.columns:
            df = df.sort_values('日期', ascending=False)
        
        # 最新数据
        latest = df.iloc[0]
        latest_date = latest.get('日期', '未知')
        
        # 主力净流入相关指标
        if '主力净流入-净额' in df.columns and '主力净流入-净占比' in df.columns:
            metrics['最新日期'] = latest_date
            metrics['主力净流入净额'] = self.format_decimal(latest['主力净流入-净额'], 0)
            metrics['主力净流入净占比'] = self.format_decimal(latest['主力净流入-净占比'], 2)
            
            # 计算5日平均净流入率
            if len(df) >= 5:
                metrics['主力净流入5日平均净占比'] = self.format_decimal(df['主力净流入-净占比'].head(5).mean(), 2)
            
            # 计算20日平均净流入率
            if len(df) >= 20:
                metrics['主力净流入20日平均净占比'] = self.format_decimal(df['主力净流入-净占比'].head(20).mean(), 2)
            
            # 计算连续流入天数
            consecutive_inflow = 0
            for _, row in df.iterrows():
                if pd.notna(row['主力净流入-净额']) and row['主力净流入-净额'] > 0:
                    consecutive_inflow += 1
                else:
                    break
            metrics['主力连续流入天数'] = consecutive_inflow
        
        # 超大单、大单、中单、小单指标
        super_net = 0
        small_net = 0
        if '超大单净流入-净占比' in df.columns:
            super_net = self.format_decimal(latest['超大单净流入-净占比'], 2)
            metrics['超大单净流入净占比'] = super_net
        
        if '大单净流入-净占比' in df.columns:
            metrics['大单净流入净占比'] = self.format_decimal(latest['大单净流入-净占比'], 2)
        
        if '中单净流入-净占比' in df.columns:
            metrics['中单净流入净占比'] = self.format_decimal(latest['中单净流入-净占比'], 2)
        
        if '小单净流入-净占比' in df.columns:
            small_net = self.format_decimal(latest['小单净流入-净占比'], 2)
            metrics['小单净流入净占比'] = small_net
        
        # 涨跌幅
        if '涨跌幅' in df.columns:
            metrics['最新涨跌幅'] = self.format_decimal(latest['涨跌幅'], 2)
        
        # 检测资金流异常
        if metrics.get('主力净流入净占比', 0) < -5 and small_net > 5:
            anomalies.append({
                "type": "主力散户极端对立",
                "detail": f"主力净占比{metrics['主力净流入净占比']}%，散户净占比{small_net}%，形成镜像对立，典型出货结构",
                "severity": "high"
            })
        elif metrics.get('主力净流入净占比', 0) > 5 and small_net < -5:
            anomalies.append({
                "type": "主力吸筹散户卖出",
                "detail": f"主力净占比{metrics['主力净流入净占比']}%，散户净占比{small_net}%，主力吸筹特征明显",
                "severity": "medium"
            })
        
        if super_net < -3:
            anomalies.append({
                "type": "超大单大幅流出",
                "detail": f"超大单净占比{super_net}%，机构资金出逃",
                "severity": "high"
            })
        elif super_net > 3:
            anomalies.append({
                "type": "超大单大幅流入",
                "detail": f"超大单净占比{super_net}%，机构资金进场",
                "severity": "medium"
            })
        
        metrics['major_anomalies'] = anomalies
        
        return metrics
    
    def calculate_margin_metrics(self) -> Dict[str, Any]:
        """计算融资融券关键指标"""
        metrics = {}
        anomalies = []
        
        if self.data.get('margin') is None or len(self.data['margin']) == 0:
            return metrics
        
        df = self.data['margin']
        df = df.copy()
        
        # 确保日期排序（最新在最前）
        if 'date' in df.columns:
            df = df.sort_values('date', ascending=False)
        elif '日期' in df.columns:
            df = df.sort_values('日期', ascending=False)
        
        if len(df) == 0:
            return metrics
        
        latest = df.iloc[0]
        
        # 融资余额
        if '融资余额' in df.columns:
            metrics['融资余额'] = self.format_decimal(latest['融资余额'], 0)
            
            # 融资余额变化率（5日）
            if len(df) >= 5:
                prev5 = df['融资余额'].iloc[4] if pd.notna(df['融资余额'].iloc[4]) else metrics['融资余额']
                if prev5 > 0:
                    metrics['融资余额5日变化率'] = self.format_decimal(((metrics['融资余额'] - prev5) / prev5) * 100, 2)
            
            # 融资余额变化率（20日）
            if len(df) >= 20:
                prev20 = df['融资余额'].iloc[19] if pd.notna(df['融资余额'].iloc[19]) else metrics['融资余额']
                if prev20 > 0:
                    metrics['融资余额20日变化率'] = self.format_decimal(((metrics['融资余额'] - prev20) / prev20) * 100, 2)
        
        # 融资买入额
        if '融资买入额' in df.columns:
            metrics['融资买入额'] = self.format_decimal(latest['融资买入额'], 0)
            
            # 融资买入额5日平均
            if len(df) >= 5:
                metrics['融资买入额5日平均'] = self.format_decimal(df['融资买入额'].head(5).mean(), 0)
        
        # 融券余额
        if '融券余额' in df.columns:
            metrics['融券余额'] = self.format_decimal(latest['融券余额'], 0)
        
        # 融资融券余额
        if '融资融券余额' in df.columns:
            metrics['融资融券余额'] = self.format_decimal(latest['融资融券余额'], 0)
        
        # 融券余量
        if '融券余量' in df.columns:
            metrics['融券余量'] = self.format_decimal(latest['融券余量'], 0)
        
        # 检测融资融券异常
        margin_change_5d = metrics.get('融资余额5日变化率', 0)
        if margin_change_5d > 10:
            anomalies.append({
                "type": "融资余额激增",
                "detail": f"融资余额5日变化率{margin_change_5d}%，杠杆资金快速进场",
                "severity": "medium"
            })
        elif margin_change_5d < -10:
            anomalies.append({
                "type": "融资余额骤降",
                "detail": f"融资余额5日变化率{margin_change_5d}%，杠杆资金恐慌性出逃",
                "severity": "high"
            })
        
        metrics['margin_anomalies'] = anomalies
        
        return metrics
    
    def calculate_valuation_metrics(self) -> Dict[str, Any]:
        """计算估值关键指标"""
        metrics = {}
        anomalies = []
        is_profit_loss = False
        
        # 尝试加载财务数据判断盈利状态
        financial_summary_path = os.path.join(self.stock_dir, f'{self.ticker}_financial_summary.json')
        if os.path.exists(financial_summary_path):
            try:
                with open(financial_summary_path, 'r', encoding='utf-8') as f:
                    financial_data = json.load(f)
                    net_profit_growth = financial_data.get('key_metrics', {}).get('净利润同比增长率')
                    if net_profit_growth is not None and net_profit_growth < 0:
                        is_profit_loss = True
            except Exception:
                pass
        
        if self.data.get('valuation') is None or len(self.data['valuation']) == 0:
            return metrics
        
        df = self.data['valuation']
        df = df.copy()
        
        # 确保日期排序（最新在最前）
        if '数据日期' in df.columns:
            df = df.sort_values('数据日期', ascending=False)
        
        if len(df) == 0:
            return metrics
        
        latest = df.iloc[0]
        
        # PE相关
        pe_ttm = 0
        if 'PE(TTM)' in df.columns:
            pe_ttm = self.format_decimal(latest['PE(TTM)'], 2)
            metrics['PE_TTM'] = pe_ttm
        
        if 'PE(静)' in df.columns:
            metrics['PE_静'] = self.format_decimal(latest['PE(静)'], 2)
        
        # PB
        if '市净率' in df.columns:
            metrics['市净率'] = self.format_decimal(latest['市净率'], 2)
        
        # PEG
        peg = 0
        if 'PEG值' in df.columns:
            peg = self.format_decimal(latest['PEG值'], 2)
            metrics['PEG'] = peg
        
        # 市现率
        if '市现率' in df.columns:
            metrics['市现率'] = self.format_decimal(latest['市现率'], 2)
        
        # 市销率
        if '市销率' in df.columns:
            metrics['市销率'] = self.format_decimal(latest['市销率'], 2)
        
        # 市值相关
        if '总市值' in df.columns:
            metrics['总市值'] = self.format_decimal(latest['总市值'], 0)
        
        if '流通市值' in df.columns:
            metrics['流通市值'] = self.format_decimal(latest['流通市值'], 0)
        
        # 当日收盘价
        if '当日收盘价' in df.columns:
            metrics['当日收盘价'] = self.format_decimal(latest['当日收盘价'], 2)
        
        if '当日涨跌幅' in df.columns:
            metrics['当日涨跌幅'] = self.format_decimal(latest['当日涨跌幅'], 2)
        
        # 计算估值百分位（相对历史）
        history_period = "250交易日"
        pe_percentile = None
        pb_percentile = None
        if len(df) >= 60:  # 至少有60个交易日数据
            for col in ['PE(TTM)', '市净率']:
                if col in df.columns:
                    current_val = latest[col]
                    if pd.notna(current_val):
                        # 计算当前值在过去250个交易日中的百分位
                        hist_data = df[col].head(250).dropna()
                        if len(hist_data) > 0:
                            percentile = (hist_data >= current_val).mean() * 100
                            col_name = col.replace('(TTM)', '_TTM').replace('(', '_').replace(')', '')
                            metrics[f'{col_name}_历史百分位'] = self.format_decimal(percentile, 1)
                            metrics[f'{col_name}_百分位参照期'] = history_period
                            if col == 'PE(TTM)':
                                pe_percentile = percentile
                            elif col == '市净率':
                                pb_percentile = percentile
        
        # 检测估值异常
        if is_profit_loss and pe_ttm > 0:
            anomalies.append({
                "type": "PE失真",
                "detail": "PE(TTM)基于含去年全年的滚动盈利，最新季度已亏损，当前PE无参考意义",
                "severity": "high"
            })
        
        if peg > 2:
            anomalies.append({
                "type": "PEG高估",
                "detail": f"PEG {peg}远超合理阈值2.0，估值与成长性严重不匹配",
                "severity": "high"
            })
        elif 0 < peg < 1:
            anomalies.append({
                "type": "PEG低估",
                "detail": f"PEG {peg}低于合理区间，估值相对成长偏低",
                "severity": "low"
            })
        
        # 检测PE与PB百分位背离
        if pe_percentile is not None and pb_percentile is not None:
            # 如果PE百分位小于40%而PB百分位大于60%，说明有背离
            if pe_percentile < 40 and pb_percentile > 60:
                anomalies.append({
                    "type": "PE与PB百分位背离",
                    "detail": f"PE百分位{pe_percentile:.1f}%较低而PB百分位{pb_percentile:.1f}%较高，盈利下滑但净资产支撑的估值并不便宜",
                    "severity": "medium"
                })
        
        metrics['valuation_anomalies'] = anomalies
        metrics['is_profit_loss'] = is_profit_loss
        
        return metrics
    
    def generate_sentiment_signal(self, fund_flow_metrics: Dict, margin_metrics: Dict) -> Dict[str, Any]:
        """生成情绪信号（移除评分，保留数据供LLM分析）"""
        signal = {
            '情绪评分': 50,
            '情绪等级': '中性',
            '信号方向': 'NEUTRAL',
            'positive_signals': [],
            'negative_signals': [],
            'fund_flow_metrics': fund_flow_metrics,
            'margin_metrics': margin_metrics
        }
        
        return signal
    
    def generate_valuation_signal(self, valuation_metrics: Dict) -> Dict[str, Any]:
        """生成估值信号"""
        signal = {
            '估值评分': 50,
            '估值等级': '合理',
            '信号方向': 'NEUTRAL',
            '估值特征': []
        }
        
        score = 50
        features = []
        scoring_breakdown = []
        has_pe_distortion = False
        has_peg_high = False
        
        if not valuation_metrics:
            return signal
        
        # 检查估值异常
        valuation_anomalies = valuation_metrics.get('valuation_anomalies', [])
        for anomaly in valuation_anomalies:
            if anomaly['type'] == 'PE失真':
                has_pe_distortion = True
            if anomaly['type'] == 'PEG高估':
                has_peg_high = True
        
        # PE分析（如果没有失真）
        pe = valuation_metrics.get('PE_TTM', valuation_metrics.get('PE_静', 0))
        if not has_pe_distortion and pe > 0:
            if pe < 20:
                score += 20
                features.append('PE处于较低区间')
                scoring_breakdown.append({
                    'factor': 'PE(TTM)',
                    'value': pe,
                    'score_contribution': 20,
                    'weight': 35
                })
            elif pe < 40:
                score += 5
                features.append('PE处于合理区间')
                scoring_breakdown.append({
                    'factor': 'PE(TTM)',
                    'value': pe,
                    'score_contribution': 5,
                    'weight': 35
                })
            elif pe > 80:
                score -= 20
                features.append('PE处于较高区间')
                scoring_breakdown.append({
                    'factor': 'PE(TTM)',
                    'value': pe,
                    'score_contribution': -20,
                    'weight': 35
                })
            elif pe > 60:
                score -= 10
                features.append('PE处于偏高水平')
                scoring_breakdown.append({
                    'factor': 'PE(TTM)',
                    'value': pe,
                    'score_contribution': -10,
                    'weight': 35
                })
        
        # PB分析
        pb = valuation_metrics.get('市净率', 0)
        if pb > 0:
            if pb < 2:
                score += 15
                features.append('PB处于较低区间')
                scoring_breakdown.append({
                    'factor': '市净率',
                    'value': pb,
                    'score_contribution': 15,
                    'weight': 30
                })
            elif pb < 4:
                score += 5
                features.append('PB处于合理区间')
                scoring_breakdown.append({
                    'factor': '市净率',
                    'value': pb,
                    'score_contribution': 5,
                    'weight': 30
                })
            elif pb > 8:
                score -= 15
                features.append('PB处于较高区间')
                scoring_breakdown.append({
                    'factor': '市净率',
                    'value': pb,
                    'score_contribution': -15,
                    'weight': 30
                })
        
        # PEG分析
        peg = valuation_metrics.get('PEG', 0)
        if peg != 0 and not np.isnan(peg):
            if 0 < peg < 1:
                score += 10
                features.append('PEG显示估值相对盈利增速偏低')
                scoring_breakdown.append({
                    'factor': 'PEG',
                    'value': peg,
                    'score_contribution': 10,
                    'weight': 20
                })
            elif peg > 2:
                score -= 10
                features.append('PEG显示估值相对盈利增速偏高')
                scoring_breakdown.append({
                    'factor': 'PEG',
                    'value': peg,
                    'score_contribution': -10,
                    'weight': 20
                })
        
        # 历史百分位分析
        pe_percentile = valuation_metrics.get('PE_TTM_历史百分位')
        if pe_percentile is not None and not has_pe_distortion:
            if pe_percentile < 20:
                score += 10
                features.append('PE处于历史低位')
                scoring_breakdown.append({
                    'factor': 'PE历史百分位',
                    'value': pe_percentile,
                    'score_contribution': 10,
                    'weight': 15
                })
            elif pe_percentile > 80:
                score -= 10
                features.append('PE处于历史高位')
                scoring_breakdown.append({
                    'factor': 'PE历史百分位',
                    'value': pe_percentile,
                    'score_contribution': -10,
                    'weight': 15
                })
        
        pb_percentile = valuation_metrics.get('市净率_历史百分位')
        if pb_percentile is not None:
            if pb_percentile < 20:
                score += 10
                features.append('PB处于历史低位')
                scoring_breakdown.append({
                    'factor': 'PB历史百分位',
                    'value': pb_percentile,
                    'score_contribution': 10,
                    'weight': 15
                })
            elif pb_percentile > 80:
                score -= 10
                features.append('PB处于历史高位')
                scoring_breakdown.append({
                    'factor': 'PB历史百分位',
                    'value': pb_percentile,
                    'score_contribution': -10,
                    'weight': 15
                })
        
        # 确定估值等级和方向
        signal['估值评分'] = max(0, min(100, score))
        
        if has_pe_distortion or has_peg_high:
            signal['估值等级'] = '失真/偏高'
            signal['信号方向'] = 'BEARISH'
        elif score >= 70:
            signal['估值等级'] = '低估'
            signal['信号方向'] = 'BULLISH'
        elif score >= 55:
            signal['估值等级'] = '相对合理'
            signal['信号方向'] = 'MODERATE_BULLISH'
        elif score <= 30:
            signal['估值等级'] = '高估'
            signal['信号方向'] = 'BEARISH'
        elif score <= 45:
            signal['估值等级'] = '相对偏贵'
            signal['信号方向'] = 'MODERATE_BEARISH'
        
        signal['估值特征'] = features
        signal['valuation_anomalies'] = valuation_anomalies
        signal['scoring_breakdown'] = scoring_breakdown
        
        return signal
    
    def generate_comprehensive_signal(self, sentiment_signal: Dict, valuation_signal: Dict, fund_flow_metrics: Dict = None, margin_metrics: Dict = None, valuation_metrics: Dict = None) -> Dict[str, Any]:
        """生成综合信号"""
        sentiment_score = sentiment_signal.get('情绪评分', 50)
        valuation_score = valuation_signal.get('估值评分', 50)
        
        # 综合评分（情绪权重60%，估值权重40%）
        sentiment_weight = 0.6
        valuation_weight = 0.4
        composite_score = sentiment_score * sentiment_weight + valuation_score * valuation_weight
        
        signal = {
            '综合评分': float(composite_score),
            '情绪评分': sentiment_score,
            '估值评分': valuation_score,
            '综合信号': 'NEUTRAL',
            '建议操作': '观望'
        }
        
        # 构建推理说明
        action_reason_parts = []
        key_scenario = ''
        
        if sentiment_score < 40:
            action_reason_parts.append(f'资金面强烈看空（情绪评分{sentiment_score}）')
        elif sentiment_score > 60:
            action_reason_parts.append(f'资金面偏多（情绪评分{sentiment_score}）')
        
        valuation_anomalies = valuation_signal.get('valuation_anomalies', [])
        has_pe_distortion = any(a['type'] == 'PE失真' for a in valuation_anomalies)
        if has_pe_distortion:
            action_reason_parts.append('估值指标因盈利亏损而失真')
        elif valuation_score < 40:
            action_reason_parts.append(f'估值偏高（估值评分{valuation_score}）')
        elif valuation_score > 60:
            action_reason_parts.append(f'估值偏低（估值评分{valuation_score}）')
        
        # 检查融资余额风险场景
        if margin_metrics and valuation_metrics:
            margin_change_5d = margin_metrics.get('融资余额5日变化率', 0)
            margin_balance = margin_metrics.get('融资余额', 0)
            latest_close = valuation_metrics.get('当日收盘价', 0)
            support_level = None
            
            # 尝试从技术面分析文件获取真正的支撑位
            technical_file = os.path.join(self.stock_dir, f'{self.ticker}_technical_trend_analysis.json')
            if os.path.exists(technical_file):
                try:
                    with open(technical_file, 'r', encoding='utf-8') as f:
                        tech_data = json.load(f)
                        support_resistance = tech_data.get('indicator_trends', {}).get('Support_Resistance', '')
                        
                        # 尝试解析ATR通道支撑
                        import re
                        atr_match = re.search(r'ATR通道支撑[≈=:]\s*([\d.]+)', support_resistance)
                        if atr_match:
                            support_level = float(atr_match.group(1))
                        else:
                            # 如果没有ATR支撑，尝试找近期低点
                            low_match = re.search(r'低点[≈=:]\s*([\d.]+)', support_resistance)
                            if low_match:
                                support_level = float(low_match.group(1))
                except Exception:
                    pass
            
            # 如果没有找到技术面支撑位，才用简化方式
            if support_level is None and latest_close > 0:
                support_level = latest_close * 0.9
            
            if support_level and margin_balance > 0:
                support_level = self.format_decimal(support_level, 2)
                key_scenario = f'若股价跌破支撑位{support_level}元且融资余额单日下降超5%，可能触发融资盘连锁平仓'
        
        if not action_reason_parts:
            action_reason_parts.append('当前信号中性，建议观望')
        
        signal['action_reason'] = '，'.join(action_reason_parts) + '，综合判断为'
        
        if composite_score >= 70:
            signal['综合信号'] = 'BULLISH'
            signal['建议操作'] = '买入'
            signal['action_reason'] += '偏多'
        elif composite_score >= 55:
            signal['综合信号'] = 'MODERATE_BULLISH'
            signal['建议操作'] = '持有或轻仓'
            signal['action_reason'] += '偏多'
        elif composite_score <= 30:
            signal['综合信号'] = 'BEARISH'
            signal['建议操作'] = '卖出'
            signal['action_reason'] += '偏空'
        elif composite_score <= 45:
            signal['综合信号'] = 'MODERATE_BEARISH'
            signal['建议操作'] = '减仓或观望'
            signal['action_reason'] += '偏空'
        else:
            signal['action_reason'] += '中性'
        
        # 评分分解
        signal['scoring_breakdown'] = {
            '情绪分': {'score': sentiment_score, 'weight': sentiment_weight},
            '估值分': {'score': valuation_score, 'weight': valuation_weight}
        }
        
        # 关键场景
        if key_scenario:
            signal['key_scenario'] = key_scenario
        
        return signal
    
    def run(self) -> Dict[str, Any]:
        """主运行流程"""
        print(f"\n{'='*60}")
        print(f"开始分析 {self.ticker} 情绪估值数据")
        print(f"{'='*60}")
        
        # 加载数据
        if not self.load_all_data():
            print("未找到有效数据")
            return {}
        
        # 计算各模块指标
        print("\n计算资金流指标...")
        fund_flow_metrics = self.calculate_fund_flow_metrics()
        
        print("计算融资融券指标...")
        margin_metrics = self.calculate_margin_metrics()
        
        print("计算估值指标...")
        valuation_metrics = self.calculate_valuation_metrics()
        
        # 生成信号
        print("生成情绪信号...")
        sentiment_signal = self.generate_sentiment_signal(fund_flow_metrics, margin_metrics)
        
        print("生成估值信号...")
        valuation_signal = self.generate_valuation_signal(valuation_metrics)
        
        print("生成综合信号...")
        comprehensive_signal = self.generate_comprehensive_signal(sentiment_signal, valuation_signal, fund_flow_metrics, margin_metrics, valuation_metrics)
        
        # 构建结果
        self.result = {
            'meta': {
                'ticker': self.ticker,
                'company_name': self.company_name,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': ['fund_flow', 'margin', 'valuation']
            },
            'fund_flow': fund_flow_metrics,
            'margin': margin_metrics,
            'valuation': valuation_metrics,
            'sentiment_signal': sentiment_signal,
            'valuation_signal': valuation_signal,
            'comprehensive_signal': comprehensive_signal
        }
        
        # 统一格式化所有数值
        self.result = self.format_dict_decimals(self.result)
        
        # 保存结果
        self.save_result()
        
        # 打印摘要
        self.print_summary()
        
        return self.result
    
    def save_result(self):
        """保存分析结果到JSON文件"""
        output_file = os.path.join(self.stock_dir, f'{self.ticker}_sentiment_valuation.json')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(self.result, f, ensure_ascii=False, indent=2)
            print(f"\n分析结果已保存到: {output_file}")
        except Exception as e:
            print(f"保存结果失败: {e}")
    
    def print_summary(self):
        """打印分析摘要"""
        print(f"\n{'='*60}")
        print(f"{self.company_name}({self.ticker}) 情绪估值分析摘要")
        print(f"{'='*60}")
        
        composite = self.result.get('comprehensive_signal', {})
        sentiment = self.result.get('sentiment_signal', {})
        valuation = self.result.get('valuation_signal', {})
        
        print(f"\n综合评分: {composite.get('综合评分', 0):.1f}")
        print(f"建议操作: {composite.get('建议操作', '未知')}")
        print(f"情绪等级: {sentiment.get('情绪等级', '未知')}")
        print(f"估值等级: {valuation.get('估值等级', '未知')}")
        
        if sentiment.get('利多信号'):
            print(f"\n利多信号: {', '.join(sentiment['利多信号'])}")
        if sentiment.get('利空信号'):
            print(f"利空信号: {', '.join(sentiment['利空信号'])}")
        
        print(f"\n{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='情绪估值分析器')
    parser.add_argument('--ticker', required=True, help='股票代码，如 300433.SZ')
    args = parser.parse_args()
    
    analyzer = SentimentValuationAnalyzer(args.ticker)
    analyzer.run()


if __name__ == '__main__':
    main()
