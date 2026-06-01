# shareholder_structure_analyzer.py
"""
股东结构分析器
功能：整合多方股东数据，计算关键指标，生成标准化JSON
特点：
1. 整合前十大股东、股东户数、机构持仓等数据源
2. 计算股权集中度（HHI）、股东变化、机构持仓等指标
3. 检测异常情况（股权过度集中/分散、大幅增减持等）
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


class ShareholderStructureAnalyzer:
    """股东结构分析器"""

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        self.data = {
            'main_shareholders': None,
            'shareholder_num': None,
            'institutional_holdings': None,
            'northbound': None,
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
            return {k: ShareholderStructureAnalyzer.format_dict_decimals(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [ShareholderStructureAnalyzer.format_dict_decimals(item) for item in data]
        elif isinstance(data, (int, float)) and not isinstance(data, bool):
            if isinstance(data, int):
                return data
            try:
                if data.is_integer():
                    return int(data)
            except (ValueError, TypeError):
                pass
            return ShareholderStructureAnalyzer.format_decimal(data)
        else:
            return data

    def load_all_data(self) -> bool:
        """加载所有可用的股东数据"""
        print(f"[{self.ticker}] 开始加载股东数据...")

        # 1. 前十大股东 - 使用 historical_shareholders.csv（替代 main_shareholders.csv）
        self._load_csv('main_shareholders', f'{self.ticker}_historical_shareholders.csv')

        # 2. 股东户数
        self._load_csv('shareholder_num', f'{self.ticker}_shareholder_num.csv')

        # 3. 机构持仓
        self._load_csv('institutional_holdings', f'{self.ticker}_institutional_holdings.csv')

        # 4. 北向资金
        self._load_csv('northbound', f'{self.ticker}_north_holdings.csv')

        # 5. 公司基本信息
        self._load_json('company_basic', f'{self.ticker}_company_basic.json')

        # 提取公司名称
        self._extract_company_name()

        # 6. 获取申万行业阈值
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
        else:
            self.industry_thresholds = self.shenwan_manager._get_default_thresholds()
            print(f"  未找到申万行业数据，使用默认阈值")

    def _load_csv(self, key: str, filename: str, skip_bad_lines=False):
        """加载CSV数据文件"""
        filepath = os.path.join(self.stock_dir, filename)
        if os.path.exists(filepath):
            try:
                if skip_bad_lines:
                    df = pd.read_csv(filepath, on_bad_lines='skip')
                else:
                    df = pd.read_csv(filepath)
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

    def calculate_hhi_index(self, ratios: List[float]) -> float:
        """计算 HHI 指数（赫芬达尔-赫希曼指数）"""
        if not ratios:
            return 0.0
        # ratios是百分比数值（如81.18表示81.18%），需要先除以100
        hhi = sum((ratio / 100) ** 2 for ratio in ratios if pd.notna(ratio))
        return self.format_decimal(hhi * 10000, 2)  # 转换为标准 HHI 格式

    def get_concentration_rating(self, hhi: float) -> str:
        """根据 HHI 指数判断股权集中度评级"""
        if hhi >= 2500:
            return "高度集中"
        elif hhi >= 1800:
            return "中度集中"
        elif hhi >= 1000:
            return "低度集中"
        else:
            return "分散"

    def calculate_main_shareholders_metrics(self) -> Dict[str, Any]:
        """计算前十大股东关键指标 - 从 historical_shareholders.csv 获取数据"""
        metrics = {
            'data_availability': 'unavailable',
            'data_updated_at': None,
            'data_frequency': 'quarterly',
            'note': '该数据为季度更新，时效性一般，仅供参考'
        }
        anomalies = []

        if self.data['main_shareholders'] is None or len(self.data['main_shareholders']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['main_shareholders'].copy()

        # 获取有效报告期（使用 historical_shareholders.csv 的字段 END_DATE）
        if 'END_DATE' in df.columns:
            df['END_DATE'] = pd.to_datetime(df['END_DATE'], errors='coerce')
            df = df.dropna(subset=['END_DATE'])

            # 优先选择最新报告期，然后检查数据完整性
            sorted_dates = sorted(df['END_DATE'].unique(), reverse=True)
            
            latest_date = None
            for date in sorted_dates:
                date_data = df[df['END_DATE'] == date]
                if 'HOLD_NUM_RATIO' in date_data.columns:
                    valid_count = date_data['HOLD_NUM_RATIO'].notna().sum()
                    # 要求至少8条有效数据，确保包含主要股东
                    if valid_count >= 8:
                        latest_date = date
                        break
            
            if latest_date is None:
                latest_date = df['END_DATE'].max()

            latest_df = df[df['END_DATE'] == latest_date].copy()
            metrics['latest_report_date'] = latest_date.strftime('%Y-%m-%d')
            metrics['data_availability'] = 'available'
            metrics['data_updated_at'] = latest_date.strftime('%Y-%m-%d')

            # 计算前十大股东数据（使用 historical_shareholders.csv 的字段）
            if 'HOLD_NUM_RATIO' in latest_df.columns:
                # 过滤有效数据
                valid_data = latest_df.dropna(subset=['HOLDER_NAME', 'HOLD_NUM_RATIO'])
                valid_data = valid_data[valid_data['HOLD_NUM_RATIO'] > 0]
                valid_data = valid_data.sort_values('HOLD_NUM_RATIO', ascending=False)

                # 前十大股东
                top10 = valid_data.head(10)

                if len(top10) > 0:
                    top10_ratios = top10['HOLD_NUM_RATIO'].tolist()
                    top10_total_ratio = sum(top10_ratios)
                    top1_ratio = top10_ratios[0] if top10_ratios else 0

                    metrics['top10_holding_ratio'] = self.format_decimal(top10_total_ratio, 2)
                    metrics['largest_holder_ratio'] = self.format_decimal(top1_ratio, 2)

                    # 计算 HHI 指数
                    hhi = self.calculate_hhi_index(top10_ratios)
                    metrics['hhi_index'] = hhi
                    metrics['concentration_rating'] = self.get_concentration_rating(hhi)

                    # 第一大股东信息
                    top1_row = top10.iloc[0]
                    metrics['largest_holder_name'] = str(top1_row.get('HOLDER_NAME', ''))

                    # 前五大股东合计
                    if len(top10_ratios) >= 5:
                        top5_total_ratio = sum(top10_ratios[:5])
                        metrics['top5_holding_ratio'] = self.format_decimal(top5_total_ratio, 2)

                    # 实际控制人
                    if self.data['company_basic']:
                        basic_info = self.data['company_basic'].get('basic_info', {})
                        actual_controller = basic_info.get('实际控制人', '')
                        if actual_controller:
                            metrics['actual_controller'] = str(actual_controller)

                    # 前十大股东列表
                    top10_list = []
                    for idx, row in top10.iterrows():
                        shareholder_info = {
                            'rank': len(top10_list) + 1,
                            'name': str(row.get('HOLDER_NAME', '')) if pd.notna(row.get('HOLDER_NAME')) else '',
                            'ratio': self.format_decimal(row.get('HOLD_NUM_RATIO', 0), 2),
                            'amount': self.format_decimal(row.get('HOLD_NUM', 0), 0),
                            'type': str(row.get('SHARES_TYPE', '')) if pd.notna(row.get('SHARES_TYPE')) else ''
                        }
                        top10_list.append(shareholder_info)
                    metrics['top10_shareholders'] = top10_list

                    # 股权集中度判断和异常
                    if top1_ratio > 50:
                        metrics['ownership_concentration'] = "高度集中"
                        anomalies.append({
                            'type': "股权高度集中",
                            'detail': f"第一大股东持股{top1_ratio:.2f}%，股权极度集中，存在一言堂风险",
                            'severity': "medium"
                        })
                    elif top1_ratio < 10 and top10_total_ratio < 20:
                        metrics['ownership_concentration'] = "过度分散"
                        anomalies.append({
                            'type': "股权过度分散",
                            'detail': f"第一大股东持股{top1_ratio:.2f}%，前十大合计{top10_total_ratio:.2f}%，缺乏实际控制人",
                            'severity': "medium"
                        })
                    else:
                        metrics['ownership_concentration'] = "适度分散"

        metrics['major_anomalies'] = anomalies
        return metrics

    def calculate_shareholder_num_metrics(self) -> Dict[str, Any]:
        """计算股东户数关键指标"""
        metrics = {
            'data_availability': 'unavailable',
            'data_updated_at': None,
            'data_frequency': '10-day',
            'note': '该数据为每10天更新，时效性一般，仅供参考'
        }
        anomalies = []

        if self.data['shareholder_num'] is None or len(self.data['shareholder_num']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['shareholder_num'].copy()

        # 确保日期排序（最新在最前）
        if 'END_DATE' in df.columns:
            df['END_DATE'] = pd.to_datetime(df['END_DATE'], errors='coerce')
            df = df.dropna(subset=['END_DATE'])
            df = df.sort_values('END_DATE', ascending=False)

        if len(df) == 0:
            metrics['data_availability'] = 'no_valid_data'
            return metrics

        latest = df.iloc[0]
        metrics['latest_report_date'] = latest['END_DATE'].strftime('%Y-%m-%d')
        metrics['data_availability'] = 'available'
        metrics['data_updated_at'] = latest['END_DATE'].strftime('%Y-%m-%d')

        # 最新股东户数
        if 'HOLDER_TOTAL_NUM' in df.columns:
            latest_num = latest['HOLDER_TOTAL_NUM']
            if pd.notna(latest_num):
                metrics['shareholder_num'] = int(latest_num)

            # 持股集中度
            if 'HOLD_FOCUS' in df.columns:
                hold_focus = latest['HOLD_FOCUS']
                if pd.notna(hold_focus):
                    metrics['hold_focus'] = str(hold_focus)

            # 户均持股
            if 'AVG_FREE_SHARES' in df.columns:
                avg_free = latest['AVG_FREE_SHARES']
                if pd.notna(avg_free):
                    metrics['avg_free_shares'] = self.format_decimal(avg_free, 0)

            # 股东户数变化
            if len(df) >= 2:
                prev = df.iloc[1]
                prev_num = prev['HOLDER_TOTAL_NUM']
                if pd.notna(prev_num) and prev_num > 0 and pd.notna(latest_num):
                    num_change = ((latest_num - prev_num) / prev_num) * 100
                    metrics['shareholder_num_change'] = self.format_decimal(num_change, 2)

            # 长期变化趋势（对比 2024 年底）
            if len(df) >= 10:
                df_2024_end = df[df['END_DATE'] <= pd.Timestamp('2024-12-31')]
                if len(df_2024_end) > 0:
                    end_2024 = df_2024_end.iloc[0]
                    end_2024_num = end_2024['HOLDER_TOTAL_NUM']
                    if pd.notna(end_2024_num) and end_2024_num > 0 and pd.notna(latest_num):
                        long_term_change = ((latest_num - end_2024_num) / end_2024_num) * 100
                        metrics['shareholder_num_change_1y'] = self.format_decimal(long_term_change, 2)

                        # 检测筹码极度分散异常
                        if latest_num > 200000 and abs(long_term_change) > 50:
                            anomalies.append({
                                'type': "筹码极度分散",
                                'detail': f"股东户数{latest_num:,}户，较2024年底的{int(end_2024_num):,}户变化{long_term_change:+.2f}%，筹码快速散户化",
                                'severity': "medium"
                            })

            # 近几期变化趋势
            if len(df) >= 4:
                recent_changes = []
                for i in range(min(4, len(df) - 1)):
                    curr = df.iloc[i]
                    prev = df.iloc[i + 1]
                    curr_num = curr['HOLDER_TOTAL_NUM']
                    prev_num_val = prev['HOLDER_TOTAL_NUM']
                    if pd.notna(prev_num_val) and prev_num_val > 0 and pd.notna(curr_num):
                        change = ((curr_num - prev_num_val) / prev_num_val) * 100
                        recent_changes.append({
                            'date': curr['END_DATE'].strftime('%Y-%m-%d'),
                            'change': self.format_decimal(change, 2)
                        })
                if recent_changes:
                    metrics['recent_changes'] = recent_changes

        metrics['shareholder_anomalies'] = anomalies
        return metrics

    def calculate_institutional_metrics(self) -> Dict[str, Any]:
        """计算机构持仓关键指标"""
        metrics = {
            'data_availability': 'unavailable',
            'data_updated_at': None,
            'data_frequency': 'quarterly',
            'note': '该数据为季度更新，时效性一般，仅供参考'
        }
        anomalies = []

        if self.data['institutional_holdings'] is None or len(self.data['institutional_holdings']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['institutional_holdings'].copy()

        # 获取最新报告期
        if 'REPORT_DATE' in df.columns:
            df['REPORT_DATE'] = pd.to_datetime(df['REPORT_DATE'], errors='coerce')
            df = df.dropna(subset=['REPORT_DATE'])
            if len(df) == 0:
                metrics['data_availability'] = 'no_valid_data'
                return metrics

            latest_date = df['REPORT_DATE'].max()
            latest_df = df[df['REPORT_DATE'] == latest_date].copy()
            metrics['latest_report_date'] = latest_date.strftime('%Y-%m-%d')
            metrics['data_availability'] = 'available'
            metrics['data_updated_at'] = latest_date.strftime('%Y-%m-%d')

            # 机构合计持仓
            if 'TOTALSHARES_RATIO' in latest_df.columns:
                valid_ratios = latest_df['TOTALSHARES_RATIO'].dropna()
                total_institutional_ratio = valid_ratios.sum()
                metrics['total_institutional_ratio'] = self.format_decimal(total_institutional_ratio, 2)

                # 机构数量
                metrics['institutional_count'] = len(latest_df)

                # 前五大机构
                if len(latest_df) >= 5:
                    top5_institutions = latest_df.nlargest(5, 'TOTALSHARES_RATIO')
                    top5_list = []
                    etf_count = 0
                    for idx, row in top5_institutions.iterrows():
                        name = row.get('HOLDER_NAME', '')
                        if pd.notna(name) and ('ETF' in str(name) or '交易型开放式' in str(name)):
                            etf_count += 1

                        inst_info = {
                            'name': str(name) if pd.notna(name) else '',
                            'ratio': self.format_decimal(row.get('TOTALSHARES_RATIO', 0), 2),
                            'shares': self.format_decimal(row.get('TOTAL_SHARES', 0), 0)
                        }
                        top5_list.append(inst_info)
                    metrics['top5_institutions'] = top5_list

                    # 检测被动资金主导
                    if etf_count >= 4:
                        metrics['institutional_type'] = "被动ETF为主"
                        anomalies.append({
                            'type': "被动资金主导",
                            'detail': f"前5大机构中{etf_count}家为ETF，主动管理型基金占比极低，缺乏主动资金护盘",
                            'severity': "medium"
                        })
                    else:
                        metrics['institutional_type'] = "多元配置"

                # 检测机构持仓情况
                if total_institutional_ratio > 15:
                    metrics['institutional_attention'] = "高度关注"
                elif total_institutional_ratio > 8:
                    metrics['institutional_attention'] = "适度关注"
                elif total_institutional_ratio > 5:
                    metrics['institutional_attention'] = "一般关注"
                else:
                    metrics['institutional_attention'] = "关注度较低"
                    anomalies.append({
                        'type': "机构持仓较低",
                        'detail': f"机构合计持仓{total_institutional_ratio:.2f}%，机构关注度较低",
                        'severity': "low"
                    })

        metrics['institutional_anomalies'] = anomalies
        return metrics

    def calculate_northbound_metrics(self) -> Dict[str, Any]:
        """计算北向资金关键指标"""
        metrics = {
            'data_availability': 'unavailable',
            'data_updated_at': None,
            'data_frequency': 'quarterly',
            'note': '该数据为季度更新，时效性一般，仅供参考'
        }

        if self.data['northbound'] is None or len(self.data['northbound']) == 0:
            metrics['data_availability'] = 'file_not_found'
            return metrics

        df = self.data['northbound'].copy()

        # 获取最新报告期
        date_columns = ['TRADE_DATE', 'DATE']
        date_col = None
        for col in date_columns:
            if col in df.columns:
                date_col = col
                break

        if date_col:
            df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
            df = df.dropna(subset=[date_col])
            df = df.sort_values(date_col, ascending=False)

            if len(df) > 0:
                latest = df.iloc[0]
                metrics['latest_report_date'] = latest[date_col].strftime('%Y-%m-%d')
                metrics['data_availability'] = 'available'
                metrics['data_updated_at'] = latest[date_col].strftime('%Y-%m-%d')

                # 持股比例
                ratio_col = None
                for col in ['TOTAL_SHARES_RATIO', 'FREE_SHARES_RATIO']:
                    if col in df.columns:
                        ratio_col = col
                        break

                if ratio_col:
                    holding_ratio = latest.get(ratio_col, 0)
                    if pd.notna(holding_ratio):
                        metrics['holding_ratio'] = self.format_decimal(holding_ratio, 2)

                # 持股数量
                shares_col = None
                for col in ['HOLD_SHARES', 'FREE_SHARES']:
                    if col in df.columns:
                        shares_col = col
                        break

                if shares_col:
                    hold_shares = latest.get(shares_col, 0)
                    if pd.notna(hold_shares):
                        metrics['hold_shares'] = self.format_decimal(hold_shares, 0)

                # 季度变化 - 优先使用 HOLDSHARES_CHANGE_TOTALRATIO 字段
                if 'HOLDSHARES_CHANGE_TOTALRATIO' in df.columns:
                    # 直接使用数据中已有的变化率
                    change_ratio = latest.get('HOLDSHARES_CHANGE_TOTALRATIO', 0)
                    if pd.notna(change_ratio):
                        metrics['change_ratio_qoq'] = self.format_decimal(change_ratio, 2)
                elif len(df) >= 2 and ratio_col:
                    # 如果没有变化率字段，再手动计算
                    prev = df.iloc[1]
                    curr_ratio = latest.get(ratio_col, 0)
                    prev_ratio = prev.get(ratio_col, 0)
                    if pd.notna(curr_ratio) and pd.notna(prev_ratio):
                        change_ratio = curr_ratio - prev_ratio
                        metrics['change_ratio_qoq'] = self.format_decimal(change_ratio, 2)
                else:
                    change_ratio = 0

                # 调整趋势描述，使其更符合数据
                if change_ratio > 0.1:
                    metrics['trend'] = "近一季度小幅增持，态度偏暖"
                elif change_ratio > 0:
                    metrics['trend'] = "近一季度微幅增持，态度偏中性"
                elif change_ratio < -0.1:
                    metrics['trend'] = "近一季度小幅减持，态度偏谨慎"
                elif change_ratio < 0:
                    metrics['trend'] = "近一季度微幅减持，态度偏中性"
                else:
                    metrics['trend'] = "持仓保持稳定"

        return metrics

    def generate_shareholder_signal(self, main_metrics: Dict, num_metrics: Dict,
                                   inst_metrics: Dict, northbound_metrics: Dict) -> Dict[str, Any]:
        """生成股东结构信号（移除评分，保留数据供LLM分析）"""
        signal = {
            '股东结构评分': 50,
            '股东结构等级': '中性',
            '信号方向': 'NEUTRAL',
            'main_metrics': main_metrics,
            'num_metrics': num_metrics,
            'inst_metrics': inst_metrics,
            'northbound_metrics': northbound_metrics
        }

        return signal

    def generate_comprehensive_signal(self, shareholder_signal: Dict, main_metrics: Dict,
                                     num_metrics: Dict, inst_metrics: Dict) -> Dict[str, Any]:
        """生成综合信号"""
        shareholder_score = shareholder_signal.get('股东结构评分', 50)

        signal = {
            '综合评分': float(shareholder_score),
            '股东结构评分': shareholder_score,
            '综合信号': 'NEUTRAL',
            '建议操作': '观望'
        }

        # 构建推理说明
        action_reason_parts = []
        key_scenario = ''

        positives = shareholder_signal.get('利多信号', [])
        negatives = shareholder_signal.get('利空信号', [])

        if positives and not negatives:
            action_reason_parts.append("股东结构整体向好")
        elif negatives and not positives:
            action_reason_parts.append("股东结构存在风险")
        elif positives and negatives:
            action_reason_parts.append("股东结构多空因素交织")
        else:
            action_reason_parts.append("股东结构中性")

        # 关键场景提示 - 优先检测最关键的风险组合
        has_scatter_anomaly = False
        has_passive_anomaly = False

        # 检查是否有筹码极度分散和被动资金主导的组合
        if num_metrics:
            num_anomalies = num_metrics.get('shareholder_anomalies', [])
            for anomaly in num_anomalies:
                if "筹码极度分散" in anomaly.get('type', ''):
                    has_scatter_anomaly = True
                    break

        if inst_metrics:
            inst_anomalies = inst_metrics.get('institutional_anomalies', [])
            for anomaly in inst_anomalies:
                if "被动资金主导" in anomaly.get('type', ''):
                    has_passive_anomaly = True
                    break

        if has_scatter_anomaly and has_passive_anomaly:
            key_scenario = "筹码极度分散且机构以被动资金为主，若股价继续下跌且股东户数未降，散户踩踏风险将加大，缺乏机构资金承接"
        elif main_metrics:
            concentration = main_metrics.get('ownership_concentration', '')
            hhi = main_metrics.get('hhi_index', 0)
            if concentration == "高度集中" and hhi >= 2500:
                key_scenario = f"股权高度集中（HHI {hhi:.2f}），第一大股东持股超50%，控制权稳固但需关注治理风险"
            elif concentration == "过度分散":
                key_scenario = "股权过度分散，缺乏实际控制人，需关注公司治理风险"

        if num_metrics and not key_scenario:
            num_change = num_metrics.get('shareholder_num_change', 0)
            if num_change < -10:
                key_scenario = f"股东户数大幅下降{abs(num_change):.1f}%，筹码快速集中，可能有主力资金介入"
            elif num_change > 10:
                key_scenario = f"股东户数大幅增加{num_change:.1f}%，筹码快速分散，需警惕主力出货"

        # 合并异常信息
        all_anomalies = []
        all_anomalies.extend(main_metrics.get('major_anomalies', []))
        all_anomalies.extend(num_metrics.get('shareholder_anomalies', []))
        all_anomalies.extend(inst_metrics.get('institutional_anomalies', []))

        if all_anomalies and not key_scenario:
            key_scenario = f"存在{len(all_anomalies)}项风险信号，需密切关注"

        if not action_reason_parts:
            action_reason_parts.append("股东结构中性")

        signal['action_reason'] = '，'.join(action_reason_parts) + '，综合判断为'

        if shareholder_score >= 70:
            signal['综合信号'] = 'BULLISH'
            signal['建议操作'] = '持有'
            signal['action_reason'] += '偏多'
        elif shareholder_score >= 55:
            signal['综合信号'] = 'MODERATE_BULLISH'
            signal['建议操作'] = '谨慎持有'
            signal['action_reason'] += '偏多'
        elif shareholder_score <= 30:
            signal['综合信号'] = 'BEARISH'
            signal['建议操作'] = '减持'
            signal['action_reason'] += '偏空'
        elif shareholder_score <= 45:
            signal['综合信号'] = 'MODERATE_BEARISH'
            signal['建议操作'] = '观望'
            signal['action_reason'] += '偏空'
        else:
            signal['action_reason'] += '中性'

        # 评分分解
        signal['scoring_breakdown'] = {
            '股东结构评分': {'score': shareholder_score, 'weight': 1.0}
        }

        if key_scenario:
            signal['key_scenario'] = key_scenario

        return signal

    def run(self) -> Dict[str, Any]:
        """主运行流程"""
        print(f"\n{'='*60}")
        print(f"开始分析 {self.ticker} 股东结构数据")
        print(f"{'='*60}")

        # 加载数据
        if not self.load_all_data():
            print("未找到有效数据")
            return {}

        # 计算各模块指标
        print("\n计算前十大股东指标...")
        main_metrics = self.calculate_main_shareholders_metrics()

        print("计算股东户数指标...")
        num_metrics = self.calculate_shareholder_num_metrics()

        print("计算机构持仓指标...")
        inst_metrics = self.calculate_institutional_metrics()

        print("计算北向资金指标...")
        northbound_metrics = self.calculate_northbound_metrics()

        # 生成信号
        print("生成股东结构信号...")
        shareholder_signal = self.generate_shareholder_signal(main_metrics, num_metrics, inst_metrics, northbound_metrics)

        print("生成综合信号...")
        comprehensive_signal = self.generate_comprehensive_signal(shareholder_signal, main_metrics, num_metrics, inst_metrics)

        # 构建结果
        self.result = {
            'meta': {
                'ticker': self.ticker,
                'company_name': self.company_name,
                'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_source': ['main_shareholders', 'shareholder_num', 'institutional_holdings', 'northbound']
            },
            'main_shareholders': main_metrics,
            'shareholder_num': num_metrics,
            'institutional_holdings': inst_metrics,
            'northbound': northbound_metrics,
            'shareholder_signal': shareholder_signal,
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
        output_file = os.path.join(self.stock_dir, f'{self.ticker}_shareholder_structure.json')
        
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
        print(f"{self.company_name}({self.ticker}) 股东结构分析摘要")
        print(f"{'='*60}")

        comprehensive = self.result.get('comprehensive_signal', {})
        shareholder = self.result.get('shareholder_signal', {})

        print(f"\n综合评分: {comprehensive.get('综合评分', 0):.1f}")
        print(f"建议操作: {comprehensive.get('建议操作', '未知')}")
        print(f"股东结构等级: {shareholder.get('股东结构等级', '未知')}")

        main = self.result.get('main_shareholders', {})
        if main and main.get('data_availability') == 'available':
            print(f"\n前十大股东合计持股: {main.get('top10_holding_ratio', 0)}%")
            print(f"第一大股东: {main.get('largest_holder_name', '未知')}")
            print(f"第一大股东持股: {main.get('largest_holder_ratio', 0)}%")
            print(f"HHI指数: {main.get('hhi_index', 0)}")
            print(f"股权集中度: {main.get('concentration_rating', '未知')}")

        num = self.result.get('shareholder_num', {})
        if num and num.get('data_availability') == 'available':
            print(f"\n最新股东户数: {num.get('shareholder_num', 0):,}户")
            if 'shareholder_num_change' in num:
                print(f"股东户数变化: {num.get('shareholder_num_change', 0):+.2f}%")

        inst = self.result.get('institutional_holdings', {})
        if inst and inst.get('data_availability') == 'available':
            print(f"\n机构合计持仓: {inst.get('total_institutional_ratio', 0)}%")
            print(f"机构数量: {inst.get('institutional_count', 0)}家")
            print(f"机构类型: {inst.get('institutional_type', '未知')}")

        nb = self.result.get('northbound', {})
        if nb and nb.get('data_availability') == 'available':
            print(f"\n北向资金持股: {nb.get('holding_ratio', 0)}%")
            if 'change_ratio_qoq' in nb:
                print(f"北向资金变化: {nb.get('change_ratio_qoq', 0):+.2f}%")
            if 'trend' in nb:
                print(f"北向资金趋势: {nb.get('trend', '未知')}")

        if shareholder.get('利多信号'):
            print(f"\n利多信号: {', '.join(shareholder['利多信号'])}")
        if shareholder.get('利空信号'):
            print(f"利空信号: {', '.join(shareholder['利空信号'])}")

        print(f"\n{'='*60}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='股东结构分析器')
    parser.add_argument('--ticker', required=True, help='股票代码，如 300433.SZ')
    args = parser.parse_args()

    analyzer = ShareholderStructureAnalyzer(args.ticker)
    analyzer.run()


if __name__ == '__main__':
    main()
