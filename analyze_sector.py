# analyze_sector.py
# 板块分析引擎
# 功能：加载板块行情数据，计算技术指标，调用本地 AI 生成分析报告
# 分析模式：single（单板块深度分析）、broad（大盘全景分析）
# 所有分析均通过 Ollama LLM 生成

import os
import sys
import json
import argparse
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import talib
except ImportError:
    print("警告：TA-Lib 未安装，部分指标计算将使用简化方法")
    talib = None

try:
    from config import DATA_DIR, AI_CONFIG
except ImportError:
    DATA_DIR = "./data"
    AI_CONFIG = {
        'base_url': 'http://localhost:11434',
        'model': 'qwen3.6:35b-a3b-mlx-bf16',
        'temperature': 0.3,
        'max_tokens': 8192,
    }

# 板块数据根目录
SECTOR_DATA_DIR = os.path.join(DATA_DIR, 'sector')
REPORT_DIR = os.path.join(SECTOR_DATA_DIR, 'reports')

# 大盘指数列表（用于大盘全景分析）
BROAD_INDEX_LIST = [
    # 传统大盘指数
    {'code': 'sh000001', 'name': '上证指数'},
    {'code': 'sz399001', 'name': '深证成指'},
    {'code': 'sz399006', 'name': '创业板指'},
    {'code': 'sh000688', 'name': '科创50'},
    {'code': 'sh000300', 'name': '沪深300'},
    {'code': 'sh000016', 'name': '上证50'},
    {'code': 'sh000905', 'name': '中证500'},
    {'code': 'sh000852', 'name': '中证1000'},
]

# 分析周期映射
PERIOD_MAP = {
    'recent':  {'days': 5,   'label': '近5日'},
    'month':   {'days': 20,  'label': '近20日(月度)'},
    'quarter': {'days': 60,  'label': '近60日(季度)'},
    'year':    {'days': 250, 'label': '近250日(年度)'},
}


class SectorAnalyzer:
    """板块分析引擎"""

    def __init__(self):
        self.data_root = SECTOR_DATA_DIR
        os.makedirs(REPORT_DIR, exist_ok=True)

    # ==================== LLM 调用 ====================

    def get_ai_analysis(self, prompt):
        """调用本地 Ollama AI 生成分析报告

        Args:
            prompt: 分析提示词

        Returns:
            str: AI 分析内容
        """
        try:
            import ollama

            model = AI_CONFIG.get('model', 'qwen3.6:35b')
            temperature = AI_CONFIG.get('temperature', 0.3)
            max_tokens = AI_CONFIG.get('max_tokens', 8192)

            print(f"  正在请求本地 Ollama AI ({model})...")
            client = ollama.Client(host=AI_CONFIG.get('base_url', 'http://localhost:11434'))

            response = client.chat(
                model=model,
                messages=[
                    {"role": "system", "content": "你是一位专业的金融分析师，擅长板块/指数的技术分析和趋势判断。请基于提供的技术指标数据，给出专业、客观的分析。"},
                    {"role": "user", "content": prompt}
                ],
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            )

            return response['message']['content']
        except Exception as e:
            print(f"  调用本地 Ollama AI 时出错: {str(e)}")
            return f"⚠️ 无法获取 AI 分析，请检查 Ollama 服务是否正常运行。\n\n错误信息: {str(e)}"

    def build_single_sector_prompt(self, sector_name, sector_code, sector_type_cn,
                                    perf_summary, trend, latest_indicators, comparison):
        """构建单板块 LLM 分析提示词

        Args:
            sector_name: 板块名称
            sector_code: 板块代码
            sector_type_cn: 板块类型中文名
            perf_summary: 各周期表现 dict
            trend: 趋势评估 dict
            latest_indicators: 最新技术指标 dict
            comparison: 大盘对比 dict

        Returns:
            str: 完整提示词
        """
        type_label_map = {'broad_index': '大盘指数', 'hk_index': '港股指数', 'industry': '行业板块', 'concept': '概念板块'}

        prompt = f"""请对以下板块/指数进行专业的技术面分析：

## 基本信息
- 板块名称: {sector_name}
- 板块代码: {sector_code}
- 板块类型: {type_label_map.get(sector_type_cn, sector_type_cn)}

## 各周期区间表现
| 周期 | 涨跌幅(%) | 最大回撤(%) |
|------|----------|------------|
"""
        for pk, pv in perf_summary.items():
            prompt += f"| {pv['label']} | {pv['change_pct']:+.2f} | {pv['max_drawdown']:.2f} |\n"

        prompt += f"""
## 趋势评估
- 趋势方向: {trend.get('direction', 'N/A')}
- 均线排列: {trend.get('ma_status', 'N/A')}
- MACD 状态: {trend.get('macd_status', 'N/A')}
- RSI 状态: {trend.get('rsi_status', 'N/A')}
- 布林带: {trend.get('bb_status', 'N/A')}

## 关键技术指标（最新交易日）
"""
        for k, v in latest_indicators.items():
            prompt += f"- {k}: {v}\n"

        if comparison and 'error' not in comparison:
            prompt += f"""
## 与 {comparison.get('broad_index_name', '大盘')} 对比（相对强弱）
"""
            for label, comp in comparison.get('period_comparisons', {}).items():
                rs = '强于' if comp['alpha'] > 0 else ('弱于' if comp['alpha'] < 0 else '持平')
                prompt += f"- {label}: 板块 {comp['sector_return']:+.2f}% vs 大盘 {comp['market_return']:+.2f}% (超额: {comp['alpha']:+.2f}%, {rs}大盘)\n"

        prompt += """
---
请从以下维度输出分析报告（Markdown 格式）：

### 1. 趋势判断
- 当前处于什么趋势阶段（上升/下降/震荡，初期/中期/末期）
- 均线系统状态分析
- MACD 信号解读

### 2. 关键价位
- 支撑位（基于均线、布林带下轨、前低等）
- 阻力位（基于均线、布林带上轨、前高等）

### 3. 多周期展望
- 短线（5-10日）预判
- 中线（20-60日）预判
- 长线（250日）预判

### 4. 风险提示
- 当前主要风险点
- 需要关注的技术信号

### 5. 综合总结
- 一句话核心结论
- 操作建议（仅技术面参考，不构成投资建议）

注意：仅基于技术面分析，不涉及基本面。使用客观中性的语言。
"""
        return prompt

    def build_broad_market_prompt(self, index_data):
        """构建大盘全景 LLM 分析提示词

        Args:
            index_data: list[dict], 各指数数据

        Returns:
            str: 完整提示词
        """
        prompt = """请对以下 A 股主要大盘指数进行全景技术分析：

## 各指数表现对比

| 指数 | 最新价 | 5日涨跌(%) | 20日涨跌(%) | 60日涨跌(%) | 250日涨跌(%) | 趋势 |
|------|--------|-----------|------------|------------|------------|------|
"""
        for idx in index_data:
            perf = idx['perf']
            prompt += f"| {idx['name']} | {idx['close']:.2f} | "
            prompt += f"{perf.get('recent', '-'):+.2f} | " if isinstance(perf.get('recent'), (int, float)) else "- | "
            prompt += f"{perf.get('month', '-'):+.2f} | " if isinstance(perf.get('month'), (int, float)) else "- | "
            prompt += f"{perf.get('quarter', '-'):+.2f} | " if isinstance(perf.get('quarter'), (int, float)) else "- | "
            prompt += f"{perf.get('year', '-'):+.2f} | " if isinstance(perf.get('year'), (int, float)) else "- | "
            prompt += f"{idx['trend']['direction']} |\n"

        prompt += """
## 各指数技术状态详情
"""
        for idx in index_data:
            t = idx['trend']
            prompt += f"""
### {idx['name']} ({idx['close']:.2f})
- 趋势: {t['direction']}
- 均线: {t.get('ma_status', 'N/A')}
- MACD: {t.get('macd_status', 'N/A')}
- RSI: {t.get('rsi_status', 'N/A')}
"""

        prompt += """
---
请从以下维度输出分析报告（Markdown 格式）：

### 1. 市场整体格局
- 当前市场处于什么状态（强势多头/震荡分化/弱势空头）
- 各指数之间的共振或背离情况

### 2. 指数强弱排序
- 按技术面强度对各指数排序
- 最强的指数及其驱动因素
- 最弱的指数及其压力因素

### 3. 关键信号
- 值得关注的技术信号（金叉/死叉、突破/破位等）
- 成交量配合情况（如有数据）

### 4. 后市展望
- 短期（1-2周）市场预判
- 中期（1-3个月）趋势推演

### 5. 综合总结
- 一句话市场定调
- 仓位建议参考（仅技术面）

注意：仅基于技术面分析，不构成投资建议。
"""
        return prompt

    # ==================== 数据加载 ====================

    def load_sector_data(self, sector_type, code):
        """加载单个板块的日线数据

        Args:
            sector_type: 'broad_index' | 'industry' | 'concept'
            code: 板块代码

        Returns:
            (pd.DataFrame, dict): (行情数据, 元数据)
        """
        csv_path = os.path.join(self.data_root, sector_type, code, f'{code}_daily.csv')
        meta_path = os.path.join(self.data_root, sector_type, code, f'{code}_meta.json')

        if not os.path.exists(csv_path):
            print(f"  数据文件不存在: {csv_path}")
            return None, None

        df = pd.read_csv(csv_path)
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)

        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)

        return df, meta

    def get_available_sectors(self, sector_type='all'):
        """获取所有可分析的板块列表

        Args:
            sector_type: 'broad_index' | 'industry' | 'concept' | 'all'

        Returns:
            list[dict]: 板块列表
        """
        sectors = []
        type_dirs = []
        if sector_type in ('broad_index', 'all'):
            type_dirs.append('broad_index')
        if sector_type in ('hk_index', 'all'):
            type_dirs.append('hk_index')
        if sector_type in ('industry', 'all'):
            type_dirs.append('industry')
        if sector_type in ('concept', 'all'):
            type_dirs.append('concept')

        for stype in type_dirs:
            type_dir = os.path.join(self.data_root, stype)
            if not os.path.exists(type_dir):
                continue
            for code in sorted(os.listdir(type_dir)):
                code_path = os.path.join(type_dir, code)
                if not os.path.isdir(code_path):
                    continue
                meta_file = os.path.join(code_path, f'{code}_meta.json')
                daily_file = os.path.join(code_path, f'{code}_daily.csv')
                if not os.path.exists(daily_file):
                    continue
                meta = {}
                if os.path.exists(meta_file):
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                sectors.append({
                    'code': code,
                    'name': meta.get('name', code),
                    'type': stype,
                    'last_updated': meta.get('last_updated', ''),
                    'data_rows': meta.get('data_rows', 0),
                    'data_end': meta.get('data_end', ''),
                })
        return sectors

    # ==================== 技术指标计算 ====================

    def compute_technical_indicators(self, df):
        """计算所有技术指标（复用 calculate_technical_trend_ds.py 的模式）

        Args:
            df: OHLCV DataFrame (需含 close, high, low, volume 列)

        Returns:
            pd.DataFrame: 添加指标列后的DataFrame
        """
        if df is None or df.empty:
            return df

        close = df['close'].values.astype(np.float64)
        high = df['high'].values.astype(np.float64) if 'high' in df.columns else close
        low = df['low'].values.astype(np.float64) if 'low' in df.columns else close
        volume = df['volume'].values.astype(np.float64) if 'volume' in df.columns else np.ones_like(close)

        # ----- 均线 (MA) -----
        for period in [5, 10, 20, 60]:
            df[f'MA{period}'] = pd.Series(close).rolling(window=period).mean().values

        # ----- MACD -----
        if talib:
            df['DIF'], df['DEA'], df['MACD_hist'] = talib.MACD(close)
        else:
            # 简化MACD计算
            ema12 = pd.Series(close).ewm(span=12, adjust=False).mean()
            ema26 = pd.Series(close).ewm(span=26, adjust=False).mean()
            df['DIF'] = (ema12 - ema26).values
            df['DEA'] = ema12.ewm(span=9, adjust=False).mean().values  # 实际应该是DIF的9日EMA，简化为close的
            df['DEA'] = df['DIF'].ewm(span=9, adjust=False).mean().values  # 修正
            df['MACD_hist'] = (df['DIF'] - df['DEA']) * 2

        # ----- RSI (14日) -----
        if talib:
            df['RSI'] = talib.RSI(close, timeperiod=14)
        else:
            delta = pd.Series(close).diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
            avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
            rs = avg_gain / avg_loss.replace(0, 1e-10)
            df['RSI'] = (100 - 100 / (1 + rs)).values

        # ----- KDJ -----
        if talib:
            df['K'], df['D'] = talib.STOCH(high, low, close)
            df['J'] = 3 * df['K'] - 2 * df['D']
        else:
            low_min = pd.Series(low).rolling(window=9).min()
            high_max = pd.Series(high).rolling(window=9).max()
            rsv = (close - low_min) / (high_max - low_min).replace(0, 1e-10) * 100
            df['K'] = rsv.ewm(alpha=1/3, adjust=False).mean().values
            df['D'] = df['K'].ewm(alpha=1/3, adjust=False).mean().values
            df['J'] = 3 * df['K'] - 2 * df['D']

        # ----- BOLL (20日) -----
        ma20 = pd.Series(close).rolling(window=20).mean()
        std20 = pd.Series(close).rolling(window=20).std()
        df['BB_upper'] = (ma20 + 2 * std20).values
        df['BB_middle'] = ma20.values
        df['BB_lower'] = (ma20 - 2 * std20).values
        df['BB_width'] = (df['BB_upper'] - df['BB_lower']) / df['BB_middle'].replace(0, 1)
        df['BB_pctB'] = (close - df['BB_lower']) / (df['BB_upper'] - df['BB_lower']).replace(0, 1)

        # ----- WR (威廉指标10日) -----
        if talib:
            df['WR'] = talib.WILLR(high, low, close, timeperiod=10)
        else:
            high_10 = pd.Series(high).rolling(window=10).max()
            low_10 = pd.Series(low).rolling(window=10).min()
            df['WR'] = ((high_10 - close) / (high_10 - low_10).replace(0, 1e-10) * -100).values

        # ----- CCI (14日) -----
        if talib:
            df['CCI'] = talib.CCI(high, low, close, timeperiod=14)
        else:
            tp = (high + low + close) / 3
            ma_tp = pd.Series(tp).rolling(window=14).mean()
            md_tp = pd.Series(tp).rolling(window=14).apply(lambda x: np.abs(x - x.mean()).mean())
            df['CCI'] = ((tp - ma_tp) / (0.015 * md_tp)).values

        # ----- 成交量指标 -----
        vol_ma5 = pd.Series(volume).rolling(window=5).mean()
        df['Volume_Ratio'] = (volume / vol_ma5.replace(0, 1)).values

        return df

    # ==================== 表现指标计算 ====================

    def compute_performance(self, df, period_days=5):
        """计算板块在指定周期的表现指标

        Args:
            df: 含OHLCV和技术指标的DataFrame
            period_days: 分析周期（天数）

        Returns:
            dict: 表现指标
        """
        if df is None or df.empty or len(df) < period_days:
            return None

        recent = df.tail(period_days)
        full = df

        close_values = full['close'].values
        current_close = close_values[-1]

        # 涨跌幅
        start_close = close_values[-period_days] if len(close_values) >= period_days else close_values[0]
        change_pct = (current_close - start_close) / start_close * 100 if start_close != 0 else 0

        # 区间最高/最低
        period_high = np.max(full['high'].values[-period_days:]) if 'high' in full.columns else np.max(close_values[-period_days:])
        period_low = np.min(full['low'].values[-period_days:]) if 'low' in full.columns else np.min(close_values[-period_days:])

        # 最大回撤
        cummax = pd.Series(close_values[-period_days:]).cummax()
        max_drawdown = ((cummax - close_values[-period_days:]) / cummax).max() * 100

        # 年化波动率（简化）
        returns = pd.Series(close_values[-period_days:]).pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) * 100 if len(returns) > 1 else 0

        # 最新技术指标
        latest = full.iloc[-1]
        indicators = {}
        for col in ['MA5', 'MA10', 'MA20', 'MA60', 'DIF', 'DEA', 'MACD_hist',
                     'RSI', 'K', 'D', 'J', 'BB_upper', 'BB_middle', 'BB_lower',
                     'BB_pctB', 'WR', 'CCI', 'Volume_Ratio']:
            if col in latest.index and pd.notna(latest[col]):
                indicators[col] = round(float(latest[col]), 2)

        # 趋势判断
        trend = self._assess_trend(df)

        return {
            'current_close': round(float(current_close), 2),
            'change_pct': round(change_pct, 2),
            'period_high': round(float(period_high), 2),
            'period_low': round(float(period_low), 2),
            'max_drawdown': round(max_drawdown, 2),
            'volatility': round(volatility, 2),
            'latest_indicators': indicators,
            'trend': trend,
        }

    def _assess_trend(self, df):
        """评估板块当前趋势状态

        Returns:
            dict: 趋势评估结果
        """
        if df is None or df.empty or len(df) < 60:
            return {'direction': '数据不足', 'strength': 'unknown', 'description': '数据不足'}

        latest = df.iloc[-1]

        # 均线排列
        ma5 = latest.get('MA5', 0)
        ma10 = latest.get('MA10', 0)
        ma20 = latest.get('MA20', 0)
        ma60 = latest.get('MA60', 0)

        if ma5 > ma10 > ma20 > ma60:
            ma_status = '多头排列'
            direction = '上升趋势'
        elif ma5 < ma10 < ma20 < ma60:
            ma_status = '空头排列'
            direction = '下降趋势'
        else:
            ma_status = '均线交织'
            direction = '震荡'

        # MACD
        dif = latest.get('DIF', 0)
        dea = latest.get('DEA', 0)
        macd_hist = latest.get('MACD_hist', 0)
        if dif > dea and macd_hist > 0:
            macd_status = 'MACD金叉红柱，多头'
        elif dif < dea and macd_hist < 0:
            macd_status = 'MACD死叉绿柱，空头'
        else:
            macd_status = 'MACD信号混合'

        # RSI
        rsi = latest.get('RSI', 50)
        if rsi > 70:
            rsi_status = f'RSI={rsi:.1f}，超买区域'
        elif rsi < 30:
            rsi_status = f'RSI={rsi:.1f}，超卖区域'
        elif rsi > 50:
            rsi_status = f'RSI={rsi:.1f}，偏强'
        else:
            rsi_status = f'RSI={rsi:.1f}，偏弱'

        # 布林带位置
        close = latest.get('close', 0)
        bb_upper = latest.get('BB_upper', 0)
        bb_lower = latest.get('BB_lower', 0)
        bb_middle = latest.get('BB_middle', 0)
        if close > bb_upper:
            bb_status = '价格在上轨之上，强势'
        elif close < bb_lower:
            bb_status = '价格在下轨之下，弱势'
        elif close > bb_middle:
            bb_status = '价格在中轨上方，偏强'
        else:
            bb_status = '价格在中轨下方，偏弱'

        return {
            'direction': direction,
            'ma_status': ma_status,
            'macd_status': macd_status,
            'rsi_status': rsi_status,
            'bb_status': bb_status,
            'strength': 'strong' if direction == '上升趋势' else ('weak' if direction == '下降趋势' else 'neutral'),
            'description': f"{direction}，{ma_status}，{macd_status}，{rsi_status}，{bb_status}",
        }

    # ==================== 大盘对比 ====================

    def compare_sector_vs_broad_market(self, sector_code, sector_type='industry',
                                        broad_index='sh000001'):
        """对比板块 vs 大盘指数表现

        Args:
            sector_code: 板块代码
            sector_type: 板块类型
            broad_index: 大盘指数代码 (默认上证指数)

        Returns:
            dict: 对比结果
        """
        # 加载板块数据
        s_df, s_meta = self.load_sector_data(sector_type, sector_code)
        # 加载大盘数据
        b_df, b_meta = self.load_sector_data('broad_index', broad_index)

        if s_df is None or b_df is None:
            return {'error': '数据加载失败'}

        # 按日期对齐
        s_df = s_df.set_index('date')
        b_df = b_df.set_index('date')
        common_dates = s_df.index.intersection(b_df.index)

        if len(common_dates) < 20:
            return {'error': '共同交易日不足20天'}

        s_close = s_df.loc[common_dates, 'close']
        b_close = b_df.loc[common_dates, 'close']

        # 各周期相对强弱
        periods = {'5日': 5, '10日': 10, '20日': 20, '60日': 60}
        comparisons = {}
        for label, days in periods.items():
            if len(s_close) >= days:
                s_ret = (s_close.iloc[-1] - s_close.iloc[-days]) / s_close.iloc[-days] * 100
                b_ret = (b_close.iloc[-1] - b_close.iloc[-days]) / b_close.iloc[-days] * 100
                alpha = s_ret - b_ret  # 超额收益
                comparisons[label] = {
                    'sector_return': round(s_ret, 2),
                    'market_return': round(b_ret, 2),
                    'alpha': round(alpha, 2),
                    'relative_strength': '强于大盘' if alpha > 0 else ('弱于大盘' if alpha < 0 else '持平'),
                }

        return {
            'sector_name': s_meta.get('name', sector_code),
            'broad_index_name': b_meta.get('name', broad_index),
            'common_days': len(common_dates),
            'period_comparisons': comparisons,
        }

    # ==================== 报告生成 ====================

    def generate_single_sector_report(self, sector_code, sector_type='industry'):
        """生成单板块 LLM 深度分析报告

        Args:
            sector_code: 板块代码
            sector_type: 板块类型

        Returns:
            str: Markdown 报告内容（AI 分析 + 数据附录）
        """
        df, meta = self.load_sector_data(sector_type, sector_code)
        if df is None:
            return f"## 板块分析报告\n\n**数据不存在**: {sector_code}，请先运行数据采集。\n"

        # 计算技术指标
        df = self.compute_technical_indicators(df)

        # 各周期表现
        perf_summary = {}
        for period_key in ['recent', 'month', 'quarter', 'year']:
            period_info = PERIOD_MAP[period_key]
            if len(df) >= period_info['days']:
                perf = self.compute_performance(df, period_info['days'])
                if perf:
                    perf_summary[period_key] = {
                        'label': period_info['label'],
                        'change_pct': perf['change_pct'],
                        'max_drawdown': perf['max_drawdown'],
                    }

        # 趋势评估
        trend = self._assess_trend(df)

        # 对比上证指数
        comparison = self.compare_sector_vs_broad_market(sector_code, sector_type, 'sh000001')

        # 提取最新技术指标
        latest = df.iloc[-1]
        latest_indicators = {}
        for col in ['MA5', 'MA10', 'MA20', 'MA60', 'DIF', 'DEA', 'MACD_hist',
                     'RSI', 'K', 'D', 'J', 'BB_upper', 'BB_middle', 'BB_lower',
                     'BB_pctB', 'WR', 'CCI', 'Volume_Ratio']:
            if col in latest.index and pd.notna(latest[col]):
                latest_indicators[col] = round(float(latest[col]), 2)

        sector_name = meta.get('name', sector_code)
        data_end = df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else ''
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 构建 LLM 提示词
        prompt = self.build_single_sector_prompt(
            sector_name, sector_code, sector_type,
            perf_summary, trend, latest_indicators, comparison
        )

        # 调用 Ollama
        print(f"\n  开始 AI 分析 {sector_name}({sector_code})...")
        ai_analysis = self.get_ai_analysis(prompt)

        # 组装最终报告
        lines = []
        lines.append(f"# {sector_name} 板块技术分析报告")
        lines.append(f"**板块代码**: {sector_code}  |  **数据截止**: {data_end}  |  **生成时间**: {now_str}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 🤖 AI 技术分析")
        lines.append("")
        lines.append(ai_analysis)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 📋 技术数据附录")
        lines.append("")
        # 区间表现
        lines.append("### 区间表现")
        lines.append("")
        lines.append("| 周期 | 涨跌幅(%) | 最大回撤(%) |")
        lines.append("|------|----------|------------|")
        for pk, pv in perf_summary.items():
            lines.append(f"| {pv['label']} | **{pv['change_pct']:+.2f}** | {pv['max_drawdown']:.2f} |")
        lines.append("")
        # 趋势状态
        lines.append("### 趋势状态")
        lines.append("")
        lines.append(f"- **方向**: {trend['direction']}")
        lines.append(f"- **均线**: {trend.get('ma_status', 'N/A')}")
        lines.append(f"- **MACD**: {trend.get('macd_status', 'N/A')}")
        lines.append(f"- **RSI**: {trend.get('rsi_status', 'N/A')}")
        lines.append(f"- **布林带**: {trend.get('bb_status', 'N/A')}")
        lines.append("")
        # 技术指标
        lines.append("### 关键技术指标")
        lines.append("")
        lines.append("| 指标 | 数值 | 指标 | 数值 |")
        lines.append("|------|------|------|------|")
        ind_keys = list(latest_indicators.keys())
        for i in range(0, len(ind_keys), 2):
            left_name = ind_keys[i]
            left_val = latest_indicators[left_name]
            if i + 1 < len(ind_keys):
                right_name = ind_keys[i + 1]
                right_val = latest_indicators[right_name]
                lines.append(f"| {left_name}={left_val:.2f} | {right_name}={right_val:.2f} |")
            else:
                lines.append(f"| {left_name}={left_val:.2f} | |")
        lines.append("")
        # 与大盘对比
        if comparison and 'error' not in comparison:
            lines.append("### 与大盘对比")
            lines.append(f"基准: {comparison.get('broad_index_name', '上证指数')}")
            lines.append("")
            lines.append("| 周期 | 板块涨跌(%) | 大盘涨跌(%) | 超额(%) | 相对强弱 |")
            lines.append("|------|------------|------------|--------|---------|")
            for label, comp in comparison.get('period_comparisons', {}).items():
                e = '✅' if comp['alpha'] > 0 else '❌'
                lines.append(f"| {label} | {comp['sector_return']:+.2f} | "
                             f"{comp['market_return']:+.2f} | **{comp['alpha']:+.2f}** | "
                             f"{e} {comp['relative_strength']} |")
            lines.append("")

        lines.append("---")
        lines.append("*报告由 板块分析引擎 + Ollama AI 自动生成，仅作技术面参考，不构成投资建议*")
        lines.append("")

        return '\n'.join(lines)

    def generate_broad_market_report(self):
        """生成大盘指数全景 LLM 分析报告

        Returns:
            str: Markdown 报告内容（AI 分析 + 数据附录）
        """
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

        # 加载所有大盘指数数据
        index_data = []
        for idx in BROAD_INDEX_LIST:
            df, meta = self.load_sector_data('broad_index', idx['code'])
            if df is None or df.empty:
                continue

            # 计算技术指标
            df = self.compute_technical_indicators(df)

            # 各周期表现
            perf = {}
            for pk, pv in PERIOD_MAP.items():
                if len(df) >= pv['days']:
                    close = df['close'].values
                    chg = (close[-1] - close[-pv['days']]) / close[-pv['days']] * 100
                    perf[pk] = round(chg, 2)

            # 趋势
            trend = self._assess_trend(df)

            latest = df.iloc[-1]
            index_data.append({
                'code': idx['code'],
                'name': idx['name'],
                'close': round(float(latest['close']), 2),
                'perf': perf,
                'trend': trend,
                'data_end': df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else '',
            })

        if not index_data:
            return "## 大盘指数全景分析\n\n**暂无数据**，请先运行数据采集。\n"

        # 构建 LLM 提示词
        prompt = self.build_broad_market_prompt(index_data)

        # 调用 Ollama
        print(f"\n  开始 AI 大盘全景分析...")
        ai_analysis = self.get_ai_analysis(prompt)

        # 组装最终报告
        lines = []
        lines.append(f"# 大盘指数全景技术分析")
        lines.append(f"**生成时间**: {now_str}")
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 🤖 AI 全景分析")
        lines.append("")
        lines.append(ai_analysis)
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## 📋 数据附录")
        lines.append("")

        # 表现对比表
        lines.append("### 各指数表现对比")
        lines.append("")
        header = "| 指数 | 最新价 |"
        sep = "|------|--------|"
        for pk, pv in PERIOD_MAP.items():
            header += f" {pv['label']}(%) |"
            sep += "------|"
        header += " 趋势 |"
        sep += "------|"
        lines.append(header)
        lines.append(sep)

        for idx in index_data:
            row = f"| {idx['name']} | {idx['close']:.2f} |"
            for pk in PERIOD_MAP:
                val = idx['perf'].get(pk, '-')
                if isinstance(val, (int, float)):
                    row += f" {val:+.2f} |"
                else:
                    row += f" {val} |"
            row += f" {idx['trend']['direction']} |"
            lines.append(row)
        lines.append("")

        # 各指数详细状态
        lines.append("### 各指数技术状态")
        lines.append("")
        for idx in index_data:
            t = idx['trend']
            lines.append(f"- **{idx['name']}** ({idx['close']:.2f}): {t['direction']} | "
                         f"均线: {t.get('ma_status', 'N/A')} | "
                         f"MACD: {t.get('macd_status', 'N/A')} | "
                         f"RSI: {t.get('rsi_status', 'N/A')}")
        lines.append("")

        # 统计
        bullish = sum(1 for d in index_data if d['trend']['direction'] == '上升趋势')
        bearish = sum(1 for d in index_data if d['trend']['direction'] == '下降趋势')
        lines.append(f"**统计**: 上升 {bullish}/{len(index_data)}, 下降 {bearish}/{len(index_data)}, "
                     f"震荡 {len(index_data) - bullish - bearish}/{len(index_data)}")
        lines.append("")

        lines.append("---")
        lines.append("*报告由 板块分析引擎 + Ollama AI 自动生成，仅作技术面参考，不构成投资建议*")
        lines.append("")

        return '\n'.join(lines)

    # ==================== 综合入口 ====================

    def run_analysis(self, mode='single', sector_code=None, sector_type='industry',
                     period='recent', top_n=30):
        """执行分析并保存报告

        Args:
            mode: 'single' | 'broad'
            sector_code: 板块代码 (single模式)
            sector_type: 板块类型
            period: 分析周期（broad模式使用）

        Returns:
            str: 报告文件路径
        """
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        if mode == 'single':
            if not sector_code:
                print("错误：single模式需要指定 --sector 参数")
                return None
            content = self.generate_single_sector_report(sector_code, sector_type)
            filename = f"sector_single_{sector_code}_{timestamp}.md"

        elif mode == 'broad':
            content = self.generate_broad_market_report()
            filename = f"broad_market_{timestamp}.md"

        else:
            print(f"错误：未知分析模式 '{mode}'，支持 single / broad")
            return None

        # 保存报告到分类子目录
        if mode == 'broad':
            report_dir = os.path.join(REPORT_DIR, 'broad_market')
        else:
            report_dir = os.path.join(REPORT_DIR, sector_type, sector_code)
        os.makedirs(report_dir, exist_ok=True)
        report_path = os.path.join(report_dir, filename)
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"\n报告已保存: {report_path}")
        return report_path

    def list_reports(self):
        """列出所有已保存的分析报告（递归扫描子目录）"""
        if not os.path.exists(REPORT_DIR):
            return []
        reports = []
        for root, dirs, files in os.walk(REPORT_DIR):
            for f in files:
                if f.endswith('.md'):
                    fpath = os.path.join(root, f)
                    # 报告名 = 相对 REPORT_DIR 的路径
                    rel_path = os.path.relpath(fpath, REPORT_DIR)
                    reports.append({
                        'name': rel_path,
                        'size': os.path.getsize(fpath),
                        'mtime': datetime.fromtimestamp(os.path.getmtime(fpath)).strftime('%Y-%m-%d %H:%M'),
                    })
        # 按修改时间降序
        reports.sort(key=lambda x: x['mtime'], reverse=True)
        return reports


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description='板块分析引擎')
    parser.add_argument('--mode', type=str,
                        choices=['single', 'broad'],
                        default='single',
                        help='分析模式 (默认: single)')
    parser.add_argument('--sector', type=str, help='板块代码 (single模式)')
    parser.add_argument('--type', type=str,
                        choices=['broad_index', 'hk_index', 'industry', 'concept'],
                        default='industry',
                        help='板块类型 (默认: industry)')
    parser.add_argument('--period', type=str,
                        choices=['recent', 'month', 'quarter', 'year'],
                        default='recent',
                        help='分析周期 (默认: recent)')
    parser.add_argument('--top', type=int, default=30,
                        help='排名数量 (默认: 30)')
    parser.add_argument('--list', action='store_true',
                        help='列出历史报告')
    parser.add_argument('--list-sectors', action='store_true',
                        help='列出可分析板块')
    parser.add_argument('--output', type=str, help='报告输出路径')
    args = parser.parse_args()

    analyzer = SectorAnalyzer()

    if args.list:
        reports = analyzer.list_reports()
        if reports:
            print(f"\n历史报告 (共 {len(reports)} 个):")
            for r in reports:
                print(f"  {r['name']} ({r['size']/1024:.1f}KB) - {r['mtime']}")
        else:
            print("\n暂无历史报告")
        return

    if args.list_sectors:
        sectors = analyzer.get_available_sectors(args.type)
        print(f"\n可分析板块 (共 {len(sectors)} 个):")
        for s in sectors:
            print(f"  [{s['type']}] {s['code']} - {s['name']} "
                  f"(数据量: {s['data_rows']}, 更新: {s['last_updated']})")
        return

    # 执行分析
    report_path = analyzer.run_analysis(
        mode=args.mode,
        sector_code=args.sector,
        sector_type=args.type,
        period=args.period,
        top_n=args.top,
    )

    if report_path and args.output:
        # 复制到指定路径
        import shutil
        shutil.copy(report_path, args.output)
        print(f"已复制到: {args.output}")


if __name__ == '__main__':
    main()
