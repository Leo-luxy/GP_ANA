# research_report_analyzer.py
"""
机构观点分析器
功能：整合券商研报数据，计算关键指标，生成标准化JSON
特点：
1. 整合研报评级、盈利预测、PE预期等数据
2. 计算机构评级分布、盈利预期、目标价等指标
3. 检测评级分歧、预期偏差等异常情况
4. 生成BULLISH/NEUTRAL/BEARISH信号
5. 输出标准JSON格式，供多智能体决策系统使用
"""

import json
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, Optional, Any, List

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


class ResearchReportAnalyzer:
    """机构观点分析器"""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'research_reports': None,
            'company_basic': None
        }
        self.company_name = None
        self.result = {}

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

    def load_all_data(self) -> bool:
        """加载所有可用的研报数据"""
        print(f"[{self.ticker}] 开始加载研报数据...")

        self._load_csv('research_reports', f'{self.ticker}_research_reports.csv')
        self._load_json('company_basic', f'{self.ticker}_company_basic.json')
        self._load_csv('financial_data', f'{self.ticker}_main_financial_data.csv')

        self._extract_company_name()

        return any(v is not None for v in self.data.values())

    def get_q1_eps(self) -> float:
        """从财务数据获取最新Q1 EPS"""
        financial_df = self.data.get('financial_data')
        if financial_df is None or len(financial_df) == 0:
            return None

        df = financial_df.copy()
        if 'REPORT_TYPE' not in df.columns or 'EPSJB' not in df.columns:
            return None

        q1_df = df[df['REPORT_TYPE'] == '一季报']
        if len(q1_df) == 0:
            return None

        q1_df = q1_df.sort_values('REPORT_DATE', ascending=False)
        latest_q1_eps = q1_df.iloc[0]['EPSJB']

        if pd.isna(latest_q1_eps):
            return None

        return float(latest_q1_eps)

    def _load_csv(self, key: str, filename: str):
        """加载CSV数据文件"""
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                df = pd.read_csv(filepath, encoding='utf-8')
                self.data[key] = df
                print(f"  加载 {filename} 成功，共 {len(df)} 条数据")
            except Exception as e:
                print(f"  加载 {filename} 失败: {e}")
        else:
            print(f"  文件不存在: {filename}")

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

    def _extract_company_name(self):
        """从多个来源提取公司名称"""
        if self.data['company_basic']:
            if isinstance(self.data['company_basic'], dict):
                self.company_name = self.data['company_basic'].get('company_name', '')
                if not self.company_name and 'basic_info' in self.data['company_basic']:
                    self.company_name = self.data['company_basic']['basic_info'].get('公司简称', '')

        if not self.company_name:
            self.company_name = self.ticker

        print(f"  公司名称: {self.company_name}")

    def calculate_rating_metrics(self) -> Dict[str, Any]:
        """计算研报评级关键指标"""
        metrics = {
            'data_availability': 'unavailable',
            'data_updated_at': None,
            'data_frequency': 'continuous',
            'note': '该数据实时更新，研报发布即更新'
        }
        anomalies = []

        if self.data['research_reports'] is None or len(self.data['research_reports']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['research_reports'].copy()

        # 日期列处理
        if '日期' in df.columns:
            df['日期'] = pd.to_datetime(df['日期'], errors='coerce')
            df = df.dropna(subset=['日期'])
            df = df.sort_values('日期', ascending=False)

            if len(df) > 0:
                latest_date = df.iloc[0]['日期']
                metrics['latest_report_date'] = latest_date.strftime('%Y-%m-%d')
                metrics['data_availability'] = 'available'
                metrics['data_updated_at'] = latest_date.strftime('%Y-%m-%d')

        # 评级统计
        rating_map = {
            '买入': 5,
            '增持': 4,
            '中性': 3,
            '减持': 2,
            '卖出': 1
        }

        rating_names = {
            '买入': 'BUY',
            '增持': 'OVERWEIGHT',
            '中性': 'NEUTRAL',
            '减持': 'UNDERWEIGHT',
            '卖出': 'SELL'
        }

        if '东财评级' in df.columns:
            # 过滤有效评级
            valid_df = df[df['东财评级'].isin(rating_map.keys())]

            if len(valid_df) > 0:
                metrics['total_reports'] = len(valid_df)

                # 评级分布
                rating_counts = valid_df['东财评级'].value_counts().to_dict()
                metrics['rating_distribution'] = {
                    rating_names.get(rating, rating): count
                    for rating, count in rating_counts.items()
                }

                # 加权评分（买入=5, 增持=4, 中性=3, 减持=2, 卖出=1）
                weighted_sum = sum(rating_map.get(r, 3) for r in valid_df['东财评级'])
                avg_rating = weighted_sum / len(valid_df)
                metrics['weighted_avg_rating'] = self.format_decimal(avg_rating, 2)

                # 最新评级
                latest_rating = df.iloc[0].get('东财评级', '')
                if latest_rating in rating_names:
                    metrics['latest_rating'] = rating_names[latest_rating]
                else:
                    metrics['latest_rating'] = latest_rating

                # 买入评级占比
                buy_count = rating_counts.get('买入', 0)
                buy_ratio = buy_count / len(valid_df) * 100
                metrics['buy_ratio'] = self.format_decimal(buy_ratio, 2)

                # 超配评级（买入+增持）占比
                overweight_count = rating_counts.get('买入', 0) + rating_counts.get('增持', 0)
                overweight_ratio = overweight_count / len(valid_df) * 100
                metrics['overweight_ratio'] = self.format_decimal(overweight_ratio, 2)

                # 检测机构一致看好（优先级更高）
                if overweight_ratio >= 90:
                    anomalies.append({
                        'type': '机构一致看好',
                        'detail': f'{overweight_ratio:.1f}%机构给予买入或增持评级，机构高度看好',
                        'severity': 'low'
                    })
                elif overweight_ratio >= 70:
                    anomalies.append({
                        'type': '机构普遍看好',
                        'detail': f'{overweight_ratio:.1f}%机构给予买入或增持评级，机构看好',
                        'severity': 'low'
                    })

                # 检测评级分歧（仅当机构意见不统一时）
                if overweight_ratio < 70 and len(rating_counts) >= 3:
                    anomalies.append({
                        'type': '评级分歧较大',
                        'detail': f'存在{len(rating_counts)}种不同评级，机构观点分散，分歧较大',
                        'severity': 'medium'
                    })

                # 检测一致看空
                sell_count = rating_counts.get('减持', 0) + rating_counts.get('卖出', 0)
                sell_ratio = sell_count / len(valid_df) * 100
                if sell_ratio >= 30:
                    anomalies.append({
                        'type': '机构一致看空',
                        'detail': f'{sell_ratio:.1f}%机构给予减持或卖出评级，机构看空',
                        'severity': 'high'
                    })

        # 近三月报告数量
        if '日期' in df.columns:
            three_months_ago = pd.Timestamp.now() - pd.DateOffset(months=3)
            recent_reports = df[df['日期'] >= three_months_ago]
            metrics['reports_3m'] = len(recent_reports)

            # 近一月报告数量
            one_month_ago = pd.Timestamp.now() - pd.DateOffset(months=1)
            recent_1m = df[df['日期'] >= one_month_ago]
            metrics['reports_1m'] = len(recent_1m)

        metrics['rating_anomalies'] = anomalies
        return metrics

    def calculate_earnings_metrics(self) -> Dict[str, Any]:
        """计算盈利预测关键指标"""
        metrics = {
            'data_availability': 'unavailable',
            'data_frequency': 'quarterly',
            'note': '该数据随研报更新，盈利预测基于机构一致预期'
        }
        anomalies = []

        if self.data['research_reports'] is None or len(self.data['research_reports']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['research_reports'].copy()

        # EPS预测（2025-2028）
        eps_cols = ['2025-盈利预测-收益', '2026-盈利预测-收益', '2027-盈利预测-收益', '2028-盈利预测-收益']
        eps_data = {}

        for col in eps_cols:
            if col in df.columns:
                valid_eps = df[col].dropna()
                if len(valid_eps) > 0:
                    year = col.split('-')[0]
                    eps_data[f'eps_{year}'] = {
                        'avg': self.format_decimal(valid_eps.mean(), 3),
                        'min': self.format_decimal(valid_eps.min(), 3),
                        'max': self.format_decimal(valid_eps.max(), 3),
                        'count': len(valid_eps)
                    }

        if eps_data:
            metrics['eps_forecast'] = eps_data
            metrics['data_availability'] = 'available'

            # 盈利增长预测（使用相邻年份计算）
            if 'eps_2026' in eps_data and 'eps_2027' in eps_data:
                eps_2026 = eps_data['eps_2026']['avg']
                eps_2027 = eps_data['eps_2027']['avg']
                if eps_2026 > 0:
                    growth_2027 = ((eps_2027 - eps_2026) / eps_2026) * 100
                    metrics['eps_growth_2027'] = self.format_decimal(growth_2027, 2)

            if 'eps_2027' in eps_data and 'eps_2028' in eps_data:
                eps_2027 = eps_data['eps_2027']['avg']
                eps_2028 = eps_data['eps_2028']['avg']
                if eps_2027 > 0:
                    growth_2028 = ((eps_2028 - eps_2027) / eps_2027) * 100
                    metrics['eps_growth_2028'] = self.format_decimal(growth_2028, 2)

            # 检测机构预期与已实现业绩背离
            if 'eps_2026' in eps_data:
                eps_2026_avg = eps_data['eps_2026']['avg']
                q1_actual = self.get_q1_eps()
                
                if q1_actual is not None and q1_actual < 0 and eps_2026_avg > 0:
                    remaining_eps_needed = eps_2026_avg - q1_actual
                    anomalies.append({
                        'type': '机构预期与已实现业绩严重背离',
                        'detail': f'机构一致预期2026年EPS {eps_2026_avg:.2f}元，但Q1已亏损{q1_actual:.3f}元。未来三季需实现{remaining_eps_needed:.2f}元，达成难度极大',
                        'severity': 'high'
                    })

            # 2028年预测数据仅有少量机构参与，添加提示
            if 'eps_2028' in eps_data and eps_data['eps_2028']['count'] <= 5:
                anomalies.append({
                    'type': '2028年预测样本量不足',
                    'detail': f'仅{eps_data["eps_2028"]["count"]}家机构提供2028年EPS预测，参考价值有限',
                    'severity': 'low'
                })

        # PE预测
        pe_cols = ['2025-盈利预测-市盈率', '2026-盈利预测-市盈率', '2027-盈利预测-市盈率', '2028-盈利预测-市盈率']
        pe_data = {}

        for col in pe_cols:
            if col in df.columns:
                valid_pe = df[col].dropna()
                if len(valid_pe) > 0:
                    year = col.split('-')[0]
                    pe_data[f'pe_{year}'] = {
                        'avg': self.format_decimal(valid_pe.mean(), 2),
                        'min': self.format_decimal(valid_pe.min(), 2),
                        'max': self.format_decimal(valid_pe.max(), 2),
                        'count': len(valid_pe)
                    }

        if pe_data:
            metrics['pe_forecast'] = pe_data

        if anomalies:
            metrics['earnings_anomalies'] = anomalies

        return metrics

    def generate_research_signal(self, rating_metrics: Dict, earnings_metrics: Dict) -> Dict[str, Any]:
        """生成机构观点信号（移除评分，保留数据供LLM分析）"""
        signal = {
            '机构观点评分': 50,
            '机构观点等级': '中性',
            '信号方向': 'NEUTRAL',
            'rating_metrics': rating_metrics,
            'earnings_metrics': earnings_metrics
        }

        return signal

    def generate_comprehensive_signal(self, research_signal: Dict, rating_metrics: Dict,
                                       earnings_metrics: Dict) -> Dict[str, Any]:
        """生成综合信号"""
        research_score = research_signal.get('机构观点评分', 50)

        signal = {
            '综合评分': float(research_score),
            '机构观点评分': research_score,
            '综合信号': 'NEUTRAL',
            '建议操作': '观望'
        }

        action_reason_parts = []
        key_scenario = ''

        positives = research_signal.get('利多信号', [])
        negatives = research_signal.get('利空信号', [])

        if positives and not negatives:
            action_reason_parts.append("机构观点整体积极")
        elif negatives and not positives:
            action_reason_parts.append("机构观点整体谨慎")
        elif positives and negatives:
            action_reason_parts.append("机构观点多空交织")
        else:
            action_reason_parts.append("机构观点中性")

        # 关键场景提示
        buy_ratio = rating_metrics.get('buy_ratio', 0)
        overweight_ratio = rating_metrics.get('overweight_ratio', 0)
        growth_2027 = earnings_metrics.get('eps_growth_2027', 0)

        if overweight_ratio >= 80 and growth_2027 >= 20:
            key_scenario = f"机构高度看好（{overweight_ratio:.1f}%超配评级），且2027年盈利预期增长{growth_2027:.1f}%，成长动能强劲"
        elif overweight_ratio >= 70:
            key_scenario = f"机构普遍看好（{overweight_ratio:.1f}%超配评级），成长预期良好"
        elif overweight_ratio < 30:
            key_scenario = f"机构偏谨慎（仅{overweight_ratio:.1f}%超配评级），需关注盈利下滑风险"
        elif growth_2027 < 0:
            key_scenario = f"2027年盈利预期下降{abs(growth_2027):.1f}%，基本面存在压力"

        # 合并异常信息
        all_anomalies = []
        all_anomalies.extend(rating_metrics.get('rating_anomalies', []))
        all_anomalies.extend(earnings_metrics.get('earnings_anomalies', []))

        if all_anomalies:
            # 检查是否有高严重性异常
            high_severity = [a for a in all_anomalies if a.get('severity') == 'high']
            if high_severity:
                high_desc = '; '.join([a['detail'] for a in high_severity])
                key_scenario = f"⚠️ {high_desc}"
            elif not key_scenario:
                key_scenario = f"存在{len(all_anomalies)}项关注点，需持续跟踪"

        if not action_reason_parts:
            action_reason_parts.append("机构观点中性")

        signal['action_reason'] = '，'.join(action_reason_parts) + '，综合判断为'

        if research_score >= 70:
            signal['综合信号'] = 'BULLISH'
            signal['建议操作'] = '积极持有'
            signal['action_reason'] += '偏多'
        elif research_score >= 55:
            signal['综合信号'] = 'MODERATE_BULLISH'
            signal['建议操作'] = '持有'
            signal['action_reason'] += '偏多'
        elif research_score <= 30:
            signal['综合信号'] = 'BEARISH'
            signal['建议操作'] = '减持'
            signal['action_reason'] += '偏空'
        elif research_score <= 45:
            signal['综合信号'] = 'MODERATE_BEARISH'
            signal['建议操作'] = '谨慎'
            signal['action_reason'] += '偏空'
        else:
            signal['action_reason'] += '中性'

        signal['scoring_breakdown'] = {
            '机构观点评分': {'score': research_score, 'weight': 1.0}
        }

        if key_scenario:
            signal['key_scenario'] = key_scenario

        return signal

    def generate_output(self) -> Dict[str, Any]:
        """生成完整的分析输出"""
        output = {
            'meta': {
                'ticker': self.ticker,
                'company_name': self.company_name,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': ['research_reports']
            }
        }

        # 计算各项指标
        rating_metrics = self.calculate_rating_metrics()
        earnings_metrics = self.calculate_earnings_metrics()

        # 生成信号
        research_signal = self.generate_research_signal(rating_metrics, earnings_metrics)
        comprehensive_signal = self.generate_comprehensive_signal(
            research_signal, rating_metrics, earnings_metrics
        )

        output['rating_summary'] = rating_metrics
        output['earnings_forecast'] = earnings_metrics
        output['research_signal'] = research_signal
        output['comprehensive_signal'] = comprehensive_signal

        self.result = output
        return output

    def save_to_json(self, filepath: Optional[str] = None):
        """保存分析结果到JSON文件"""
        if filepath is None:
            filepath = os.path.join(self.stock_dir, f'{self.ticker}_research_report_analysis.json')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(filepath), exist_ok=True)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.result, f, ensure_ascii=False, indent=2)

        print(f"分析结果已保存到: {filepath}")

    def print_summary(self):
        """打印分析摘要"""
        print(f"\n{'='*60}")
        print(f"{self.company_name}({self.ticker}) 机构观点分析摘要")
        print(f"{'='*60}")

        research_signal = self.result.get('research_signal', {})
        comprehensive_signal = self.result.get('comprehensive_signal', {})
        rating_metrics = self.result.get('rating_summary', {})
        earnings_metrics = self.result.get('earnings_forecast', {})

        print(f"\n综合评分: {comprehensive_signal.get('综合评分', 0):.1f}")
        print(f"建议操作: {comprehensive_signal.get('建议操作', '观望')}")
        print(f"机构观点等级: {research_signal.get('机构观点等级', '中性')}")

        # 评级信息
        rating_dist = rating_metrics.get('rating_distribution', {})
        if rating_dist:
            print(f"\n【评级分布】")
            for rating, count in rating_dist.items():
                print(f"  {rating}: {count}家")

        # 盈利预测
        eps_forecast = earnings_metrics.get('eps_forecast', {})
        if eps_forecast:
            print(f"\n【盈利预测（均值）】")
            for year, data in eps_forecast.items():
                print(f"  {year[-4:]}: EPS {data['avg']:.3f}元")

        # 成长性
        growth_2027 = earnings_metrics.get('eps_growth_2027', 0)
        if growth_2027 != 0:
            print(f"\n  2027年盈利增长预期: {growth_2027:+.1f}%")

        # 信号
        positives = research_signal.get('利多信号', [])
        negatives = research_signal.get('利空信号', [])

        if positives:
            print(f"\n【利多信号】")
            for signal in positives:
                print(f"  • {signal}")

        if negatives:
            print(f"\n【利空信号】")
            for signal in negatives:
                print(f"  • {signal}")

        print(f"\n{'='*60}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='机构观点分析器')
    parser.add_argument('--ticker', type=str, required=True, help='股票代码，如 300433.SZ')
    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"开始分析 {args.ticker} 机构观点数据")
    print(f"{'='*60}\n")

    analyzer = ResearchReportAnalyzer(args.ticker)

    if analyzer.load_all_data():
        analyzer.generate_output()
        analyzer.save_to_json()
        analyzer.print_summary()
    else:
        print("数据加载失败，无法进行分析")


if __name__ == '__main__':
    main()
