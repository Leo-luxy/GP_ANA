# calculate_technical_trend_ds.py
# 功能：从已包含技术指标的CSV文件中加载数据，分析各指标趋势，生成结构化报告
# 实现原理：
# 1. 加载本地股票数据文件（包含OHLCV及各类技术指标）
# 2. 提取最近30-60天的数据
# 3. 分析关键技术指标的趋势变化（直接使用已有指标列）
# 4. 为每个指标生成趋势描述，并检测信号矛盾
# 5. 生成分组JSON报告
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

class StockTechnicalTrendAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        self.recent_data = None
        self.technical_indicators = {}
        self.indicator_trends = {}
        self.signal_conflicts = []
        self.meta = {}
        # 新增存储扩展分析结果
        self.trend_scores = {}
        self.trading_signal = {}
        self.indicator_changes = {}
        self.risk_metrics = {}
        self.multi_timeframe = {}
        self.consistency_score = 0.0

    # ---------- 工具函数 ----------
    def _safe_series(self, col_name, default=None):
        if col_name in self.recent_data.columns:
            return self.recent_data[col_name].values
        return default

    def _safe_full_series(self, col_name, default=None):
        if col_name in self.data.columns:
            return self.data[col_name].values
        return default

    def _convert_to_native(self, obj):
        """递归将 numpy 类型转换为 Python 原生类型，以便 JSON 序列化"""
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {k: self._convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._convert_to_native(i) for i in obj]
        else:
            return obj

    # ---------- 数据加载 ----------
    def load_data(self):
        """加载CSV数据，并识别已有的技术指标列"""
        print(f"加载数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)

        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
            self.data = self.data.sort_values('date')
            self.meta['last_date'] = self.data['date'].iloc[-1].strftime('%Y-%m-%d')
            self.meta['data_days'] = len(self.data)
        else:
            self.meta['last_date'] = datetime.now().strftime('%Y-%m-%d')
            self.meta['data_days'] = len(self.data)
            print("警告: 数据缺少日期列，无法准确判断时间窗口")

        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[-1]
        elif '股票代码' in self.data.columns:
            self.ticker = self.data['股票代码'].iloc[-1]
        else:
            file_name = os.path.basename(self.file_path)
            self.ticker = file_name.split('_')[0]

        # 取最近60天数据（确保有足够样本计算趋势）
        if 'date' in self.data.columns:
            end_date = self.data['date'].iloc[-1]
            start_date = end_date - timedelta(days=90)  # 取90天窗口，实际条数可能更多
            self.recent_data = self.data[self.data['date'] >= start_date]
        else:
            self.recent_data = self.data.tail(60)

        self.meta['recent_days'] = len(self.recent_data)
        print(f"加载完成，共 {len(self.data)} 条数据，最近 {len(self.recent_data)} 条用于分析")

        # 检查必要的基本列是否存在
        required_cols = ['close', 'high', 'low', 'volume']
        missing = [c for c in required_cols if c not in self.data.columns]
        if missing:
            print(f"警告: 数据缺少基本列 {missing}，部分分析可能受限")

        return self.data

    def _safe_series(self, col_name, default=None):
        """安全获取列数据，若不存在返回None"""
        if col_name in self.recent_data.columns:
            return self.recent_data[col_name].values
        return default

    def _safe_full_series(self, col_name, default=None):
        """获取全量数据列，用于时间序列计算"""
        if col_name in self.data.columns:
            return self.data[col_name].values
        return default

    # ==================== 新增分析方法 ====================
    def compute_numerical_trend_scores(self):
        """计算数值化的趋势评分 (0~1)"""
        scores = {}

        # 1. 均线多头排列强度 (MA5>MA10>MA20>MA60)
        ma5 = self.technical_indicators.get('MA5', 0)
        ma10 = self.technical_indicators.get('MA10', 0)
        ma20 = self.technical_indicators.get('MA20', 0)
        ma60 = self.technical_indicators.get('MA60', 0)
        if ma5 and ma10 and ma20 and ma60:
            # 计算排序正确性得分
            correct_order = 0
            if ma5 > ma10:
                correct_order += 1
            if ma10 > ma20:
                correct_order += 1
            if ma20 > ma60:
                correct_order += 1
            scores['ma_bullish_score'] = correct_order / 3.0
            print(f"MA多头排列计算: MA5={ma5}, MA10={ma10}, MA20={ma20}, MA60={ma60}, correct_order={correct_order}, score={scores['ma_bullish_score']}")
        else:
            scores['ma_bullish_score'] = 0.5
            print(f"MA数据不完整: MA5={ma5}, MA10={ma10}, MA20={ma20}, MA60={ma60}")

        # 2. MACD 多头动能强度 (基于红柱大小与趋势)
        macd_hist = self.technical_indicators.get('MACD_hist', 0)
        if macd_hist > 0:
            # 归一化到 0~1，使用历史数据动态调整
            hist_series = self._safe_series('MACD_hist')
            if hist_series is not None and len(hist_series) > 0:
                max_hist = max(abs(hist_series))
                scores['macd_power'] = min(1.0, macd_hist / max_hist) if max_hist > 0 else 0.5
            else:
                scores['macd_power'] = 0.5
        else:
            # 绿柱时，返回较低的动量强度
            # 即使绿柱缩短，只要在零轴下方，动量强度应该较低
            hist_series = self._safe_series('MACD_hist')
            if hist_series is not None and len(hist_series) > 0:
                # 计算绿柱的相对强度
                min_hist = min(hist_series)
                if min_hist < 0:
                    # 绿柱越接近零，强度越高，但最高不超过0.4
                    green_strength = min(0.4, 1.0 - (abs(macd_hist) / abs(min_hist)))
                    scores['macd_power'] = green_strength
                else:
                    scores['macd_power'] = 0.2
            else:
                scores['macd_power'] = 0.2

        # 3. ADX 趋势强度 (直接使用归一化值，通常 ADX 0-100)
        adx = self.technical_indicators.get('ADX', 20)
        scores['adx_trend_strength'] = min(1.0, adx / 100.0)

        # 4. 超买超卖评分 (RSI)
        rsi = self.technical_indicators.get('RSI', 50)
        # 50为中性，越靠近70越超买(正向)，越靠近30越超卖(负向)
        if rsi >= 70:
            overbought = (rsi - 70) / 30.0  # 70->0, 100->1
            scores['overbought_oversold'] = min(1.0, overbought)
        elif rsi <= 30:
            oversold = (30 - rsi) / 30.0
            scores['overbought_oversold'] = -min(1.0, oversold)
        else:
            scores['overbought_oversold'] = 0.0

        # 5. 成交量资金流强度 (基于 Volume_Ratio 和 OBV 变化)
        vol_ratio = self.technical_indicators.get('Volume_Ratio', 1.0)
        obv = self.technical_indicators.get('OBV', 0)
        obv_series = self._safe_series('OBV')
        volume_flow = 0.0
        
        # 基于量比
        if vol_ratio > 1.2:
            volume_flow += min(0.5, (vol_ratio - 1.0) / 2.0)
        elif vol_ratio < 0.8:
            volume_flow -= min(0.5, (1.0 - vol_ratio) / 1.0)
        
        # 基于OBV变化
        if obv_series is not None and len(obv_series) >= 10:
            obv_change = (obv_series[-1] - obv_series[-10]) / abs(obv_series[-10]) if obv_series[-10] != 0 else 0
            volume_flow += min(0.5, max(-0.5, obv_change))
        
        scores['volume_flow'] = volume_flow

        # 6. 价格动量强度 (基于价格变化率)
        close_series = self._safe_series('close')
        if close_series is not None and len(close_series) >= 10:
            # 使用5日价格变化率，与return_5d一致
            price_change = (close_series[-1] - close_series[-5]) / close_series[-5] if close_series[-5] != 0 else 0
            # 归一化到 -1~1，负收益对应负动量
            momentum = min(1.0, max(-1.0, price_change * 10))
            scores['price_momentum'] = momentum
        else:
            scores['price_momentum'] = 0.0

        # 7. 指标背离检测
        divergence_score = 1.0  # 默认为无背离
        has_divergence = False
        close_series = self._safe_series('close')
        rsi_series = self._safe_series('RSI')
        macd_hist_series = self._safe_series('MACD_hist')
        
        if close_series is not None and rsi_series is not None and len(close_series) >= 16:
            # 检测价格创新高但RSI未创新高的顶背离
            recent_high = max(close_series[-16:])
            high_idx = np.argmax(close_series[-16:]) + len(close_series) - 16
            if high_idx == len(close_series) - 1:  # 当前价格是近16日高点
                rsi_high = max(rsi_series[-16:])
                rsi_high_idx = np.argmax(rsi_series[-16:]) + len(rsi_series) - 16
                if rsi_high_idx < len(rsi_series) - 4:  # RSI高点出现在至少4天前
                    divergence_score = 0.3  # 顶背离，降低趋势可信度
                    has_divergence = True
        
        if close_series is not None and macd_hist_series is not None and len(close_series) >= 16:
            # 检测价格创新高但MACD未创新高的顶背离
            recent_high = max(close_series[-16:])
            high_idx = np.argmax(close_series[-16:]) + len(close_series) - 16
            if high_idx == len(close_series) - 1:  # 当前价格是近16日高点
                macd_high = max(macd_hist_series[-16:])
                macd_high_idx = np.argmax(macd_hist_series[-16:]) + len(macd_hist_series) - 16
                if macd_high_idx < len(macd_hist_series) - 4:  # MACD高点出现在至少4天前
                    divergence_score = 0.3  # 顶背离，降低趋势可信度
                    has_divergence = True
        
        scores['divergence_score'] = divergence_score
        scores['has_divergence'] = has_divergence

        self.trend_scores = scores

    def compute_indicator_changes(self):
        """计算各指标在5日和10日的变化量"""
        changes = {}
        # 定义需要计算的指标及其列名
        indicators = {
            'RSI': 'RSI',
            'MACD_hist': 'MACD_hist',
            'Volume_Ratio': 'Volume_Ratio',
            'K': 'K',
            'D': 'D',
            'ADX': 'ADX'
        }
        for name, col in indicators.items():
            series = self._safe_series(col)
            if series is not None and len(series) >= 10:
                # 显式转换为 Python float
                val = float(series[-1])
                change_5d = float(series[-1] - series[-5]) if len(series) >= 5 else None
                change_10d = float(series[-1] - series[-10]) if len(series) >= 10 else None
                changes[name] = {
                    'value': round(val, 4),
                    'change_5d': round(change_5d, 4) if change_5d is not None else None,
                    'change_10d': round(change_10d, 4) if change_10d is not None else None
                }
            else:
                changes[name] = {'value': None, 'change_5d': None, 'change_10d': None}
        self.indicator_changes = changes

    def compute_risk_metrics(self):
        """计算波动率、最大回撤、ATR百分比、布林带宽度分位数"""
        metrics = {}
        close = self._safe_full_series('close')
        if close is not None and len(close) >= 20:
            # 20日波动率（年化，日收益率标准差 * sqrt(252)）
            returns = pd.Series(close).pct_change().dropna()
            vol_20d = returns.tail(20).std() * np.sqrt(252)
            metrics['volatility_20d'] = round(float(vol_20d), 4)
            cummax = pd.Series(close).cummax()
            drawdown = (cummax - close) / cummax
            metrics['max_drawdown_20d'] = round(float(drawdown.tail(20).max()), 4)
        else:
            metrics['volatility_20d'] = None
            metrics['max_drawdown_20d'] = None

        # ATR百分比 (ATR / 收盘价)
        atr = self.technical_indicators.get('ATR', 0)
        close_price = self.technical_indicators.get('close', 1)
        if atr and close_price:
            metrics['atr_percent'] = round(atr / close_price * 100, 2)
        else:
            metrics['atr_percent'] = None

        # 布林带宽度分位数（基于历史）
        bb_width = self._safe_series('BB_width')
        if bb_width is not None and len(bb_width) > 0:
            current_width = bb_width[-1]
            # 计算当前宽度在历史中的分位数
            percentile = (bb_width <= current_width).sum() / len(bb_width)
            metrics['bb_width_percentile'] = round(float(percentile), 4)
        else:
            metrics['bb_width_percentile'] = None

        self.risk_metrics = metrics

    def multi_timeframe_analysis(self):
        """多周期分析：周线级别"""
        if 'date' not in self.data.columns:
            self.multi_timeframe = {'weekly_trend': 'UNKNOWN', 'daily_trend': 'UNKNOWN', 'divergence': False}
            return

        # 复制数据并设置日期索引
        df = self.data.copy()
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        # 周线重采样（取每周五收盘价，或最后一天）
        weekly = df.resample('W-FRI').agg({
            'close': 'last',
            'high': 'max',
            'low': 'min',
            'volume': 'sum'
        }).dropna()
        if len(weekly) < 20:
            self.multi_timeframe = {'weekly_trend': 'INSUFFICIENT_DATA', 'daily_trend': 'UNKNOWN', 'divergence': False}
            return

        # 计算周线均线
        weekly['MA5'] = weekly['close'].rolling(5).mean()
        weekly['MA10'] = weekly['close'].rolling(10).mean()
        weekly['MA20'] = weekly['close'].rolling(20).mean()
        latest = weekly.iloc[-1]
        if latest['MA5'] > latest['MA10'] > latest['MA20']:
            weekly_trend = 'BULLISH'
        elif latest['MA5'] < latest['MA10'] < latest['MA20']:
            weekly_trend = 'BEARISH'
        else:
            weekly_trend = 'NEUTRAL'

        # 日线趋势（基于最近MA排列）
        daily_ma5 = self.technical_indicators.get('MA5', 0)
        daily_ma10 = self.technical_indicators.get('MA10', 0)
        daily_ma20 = self.technical_indicators.get('MA20', 0)
        if daily_ma5 > daily_ma10 > daily_ma20:
            daily_trend = 'BULLISH'
        elif daily_ma5 < daily_ma10 < daily_ma20:
            daily_trend = 'BEARISH'
        else:
            daily_trend = 'NEUTRAL'

        divergence = bool((weekly_trend == 'BULLISH' and daily_trend == 'BEARISH') or
                          (weekly_trend == 'BEARISH' and daily_trend == 'BULLISH'))

        self.multi_timeframe = {
            'weekly_trend': weekly_trend,
            'daily_trend': daily_trend,
            'divergence': divergence
        }

    def compute_consistency_score(self):
        """计算各指标方向一致性评分 (0~1)"""
        # 定义指标方向信号：1=多头/看涨， -1=空头/看跌， 0=中性
        signals = []

        # 1. 均线方向
        ma5 = self.technical_indicators.get('MA5', 0)
        ma10 = self.technical_indicators.get('MA10', 0)
        ma20 = self.technical_indicators.get('MA20', 0)
        if ma5 > ma10 > ma20:
            signals.append(1)
        elif ma5 < ma10 < ma20:
            signals.append(-1)
        else:
            signals.append(0)

        # 2. MACD 方向
        macd_hist = self.technical_indicators.get('MACD_hist', 0)
        if macd_hist > 0:
            signals.append(1)
        elif macd_hist < 0:
            signals.append(-1)
        else:
            signals.append(0)

        # 3. RSI 方向 (超买区视为潜在回调，方向偏空；超卖区偏多)
        rsi = self.technical_indicators.get('RSI', 50)
        if rsi > 70:
            signals.append(-1)   # 超买，看回调
        elif rsi < 30:
            signals.append(1)    # 超卖，看反弹
        else:
            signals.append(0)

        # 4. ADX 趋势方向 (ADX<25视为无趋势，返回中性)
        adx = self.technical_indicators.get('ADX', 20)
        close = self.technical_indicators.get('close', 0)
        if adx >= 25:
            if close > ma20:
                signals.append(1)
            elif close < ma20:
                signals.append(-1)
            else:
                signals.append(0)
        else:
            signals.append(0)  # ADX<25视为无趋势

        # 5. KDJ 方向 (K>D 为多头)
        k = self.technical_indicators.get('K', 50)
        d = self.technical_indicators.get('D', 50)
        if k > d:
            signals.append(1)
        elif k < d:
            signals.append(-1)
        else:
            signals.append(0)

        # 6. CCI 方向 (超买区偏空，超卖区偏多)
        cci = self.technical_indicators.get('CCI', 0)
        if cci > 100:
            signals.append(-1)  # 超买，看回调
        elif cci < -100:
            signals.append(1)   # 超卖，看反弹
        else:
            signals.append(0)

        # 7. MFI 方向 (超买区偏空，超卖区偏多)
        mfi = self.technical_indicators.get('MFI', 50)
        if mfi > 80:
            signals.append(-1)  # 超买，资金流出风险
        elif mfi < 20:
            signals.append(1)   # 超卖，资金流入机会
        else:
            signals.append(0)

        # 8. 布林带方向 (%B>0.7偏多，%B<0.3偏空)
        bb_pctb = self.technical_indicators.get('BB_pctB', 0.5)
        if bb_pctb > 0.7:
            signals.append(1)
        elif bb_pctb < 0.3:
            signals.append(-1)
        else:
            signals.append(0)

        # 9. VW_MACD 方向
        vw_macd = self.technical_indicators.get('VW_MACD', 0)
        vw_macd_hist = self.technical_indicators.get('VW_MACD_Hist', 0)
        if vw_macd > 0 and vw_macd_hist > 0:
            signals.append(1)
        elif vw_macd < 0 and vw_macd_hist < 0:
            signals.append(-1)
        else:
            signals.append(0)

        # 计算一致性: 统计同向比例，忽略中性信号(0)
        non_zero = [s for s in signals if s != 0]
        if len(non_zero) == 0:
            self.consistency_score = 0.5
        else:
            positive = sum(1 for s in non_zero if s > 0)
            negative = sum(1 for s in non_zero if s < 0)
            max_dir = max(positive, negative)
            # 计算基本一致性
            basic_consistency = max_dir / len(non_zero)
            
            # 调整一致性评分，考虑多空信号混杂的情况
            # 如果多空信号都存在，降低一致性评分
            if positive > 0 and negative > 0:
                # 计算信号强度差异
                signal_diff = abs(positive - negative) / len(non_zero)
                # 根据差异调整一致性评分
                self.consistency_score = basic_consistency * (0.6 + 0.4 * signal_diff)
            else:
                self.consistency_score = basic_consistency
        
        # 限制一致性分数范围
        self.consistency_score = max(0.0, min(1.0, self.consistency_score))

    def generate_trading_signal(self):
        """生成明确的交易信号 (BUY/SELL/HOLD) 及置信度"""
        # 综合各项评分和趋势
        # 规则示例（可自定义）
        # 中期看多条件：均线多头 + MACD红柱 + ADX>25
        medium_bullish = (self.trend_scores.get('ma_bullish_score', 0) > 0.6 and
                          self.trend_scores.get('macd_power', 0) > 0.5 and
                          self.trend_scores.get('adx_trend_strength', 0) > 0.25)
        # 短期超买条件：RSI>70 或 KDJ死叉
        short_overbought = (self.technical_indicators.get('RSI', 0) > 70 or
                            (self.technical_indicators.get('K', 0) < self.technical_indicators.get('D', 0) and
                             self.technical_indicators.get('K', 0) > 80))

        # 信号决策
        if medium_bullish and not short_overbought:
            action = 'BUY'
            confidence = min(0.9, 0.6 + self.trend_scores.get('ma_bullish_score', 0) * 0.3)
            reason = "中期看多且无短期超买"
        elif medium_bullish and short_overbought:
            action = 'HOLD'
            confidence = 0.65
            reason = "中期看多但短期超买，等待回调"
        elif not medium_bullish and short_overbought:
            action = 'SELL'
            confidence = 0.7
            # 提供更具体的理由
            rsi = self.technical_indicators.get('RSI', 50)
            k = self.technical_indicators.get('K', 50)
            d = self.technical_indicators.get('D', 50)
            macd_hist = self.technical_indicators.get('MACD_hist', 0)
            
            specific_reason = "短期超买"  # 基础理由
            
            # 检查具体指标状态
            if rsi > 70:
                specific_reason += "，RSI进入超买区域"
            if k < d and k > 80:
                specific_reason += "，KDJ形成高位死叉"
            if macd_hist < 0:
                specific_reason += "，MACD转为绿柱"
            
            reason = f"{specific_reason}，建议暂时卖出以规避回调风险"
        else:
            action = 'HOLD'
            confidence = 0.5
            reason = "信号不明确，建议观望"

        confidence = min(0.95, confidence * (0.5 + self.consistency_score * 0.5))
        self.trading_signal = {
            'action': action,
            'confidence': round(confidence, 2),
            'reason': reason,
            'components': {
                'medium_term': 'BULLISH' if medium_bullish else 'NEUTRAL/BEARISH',
                'short_term': 'OVERBOUGHT' if short_overbought else 'NEUTRAL',
                'conflict': bool(medium_bullish and short_overbought)
            }
        }

    # ==================== 原有分析方法（保持不变，但可增加数值化调用） ====================
    def calculate_ema(self, data, period):
        """计算指数移动平均线"""
        return data.ewm(span=period, adjust=False).mean()

    def calculate_ad_line(self, data):
        """计算积累/派发线 (A/D Line)"""
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']
        
        # 计算资金流量乘数（使用向量化操作）
        high_low_diff = high - low
        # 创建一个掩码，处理high_low_diff为0的情况
        mask = high_low_diff != 0
        money_flow_multiplier = pd.Series(0, index=data.index)
        money_flow_multiplier[mask] = ((close[mask] - low[mask]) - (high[mask] - close[mask])) / high_low_diff[mask]
        # 计算资金流量
        money_flow_volume = money_flow_multiplier * volume
        # 计算A/D线
        ad_line = money_flow_volume.cumsum()
        return ad_line

    def calculate_chaikin_mf(self, data, period=20):
        """计算柴金资金流量 (Chaikin Money Flow)"""
        high = data['high']
        low = data['low']
        close = data['close']
        volume = data['volume']
        
        # 计算典型价格
        typical_price = (high + low + close) / 3
        # 计算资金流量
        money_flow = typical_price * volume
        # 计算资金流量乘数（使用向量化操作）
        high_low_diff = high - low
        # 创建一个掩码，处理high_low_diff为0的情况
        mask = high_low_diff != 0
        money_flow_multiplier = pd.Series(0, index=data.index)
        money_flow_multiplier[mask] = ((close[mask] - low[mask]) - (high[mask] - close[mask])) / high_low_diff[mask]
        # 计算资金流量
        money_flow_volume = money_flow_multiplier * volume
        # 计算CMF
        cmf = money_flow_volume.rolling(period).sum() / volume.rolling(period).sum()
        return cmf

    def analyze_technical_indicators(self):
        """主控函数：从数据中提取最新指标并分析趋势"""
        if self.recent_data is None or len(self.recent_data) == 0:
            print("数据未加载或为空")
            return

        latest = self.recent_data.iloc[-1]

        # 提取最新值（优先使用标准命名，兼容中英文）
        self.technical_indicators = {
            'close': round(latest.get('close', 0), 2),
            'volume': int(latest.get('volume', 0)),
            'MA5': round(latest.get('MA5', 0), 2),
            'MA10': round(latest.get('MA10', 0), 2),
            'MA20': round(latest.get('MA20', 0), 2),
            'MA60': round(latest.get('MA60', 0), 2) if 'MA60' in latest else 0,
            'MA120': round(latest.get('MA120', 0), 2) if 'MA120' in latest else 0,
            'RSI': round(latest.get('RSI', 0), 2),
            'DIF': round(latest.get('DIF', 0), 4),
            'DEA': round(latest.get('DEA', 0), 4),
            'MACD_hist': round(latest.get('MACD_hist', 0), 4),
            'K': round(latest.get('K', 0), 2),
            'D': round(latest.get('D', 0), 2),
            'J': round(latest.get('J', 0), 2),
            'ATR': round(latest.get('ATR', 0), 2),
            'OBV': round(latest.get('OBV', 0), 2),
            'ADX': round(latest.get('ADX', 0), 2),
            'CCI': round(latest.get('CCI', 0), 2) if 'CCI' in latest else 0,
            'MFI': round(latest.get('MFI', 0), 2) if 'MFI' in latest else 0,
            'Volume_Ratio': round(latest.get('Volume_Ratio', 0), 2),
            'BB_upper': round(latest.get('BB_upper', 0), 2),
            'BB_middle': round(latest.get('BB_middle', 0), 2),
            'BB_lower': round(latest.get('BB_lower', 0), 2),
            'BB_width': round(latest.get('BB_width', 0), 4),
            'BB_pctB': round(latest.get('BB_pctB', 0), 4),
        }

        # 计算并添加缺失的指标
        if 'high' in self.data.columns and 'low' in self.data.columns and 'close' in self.data.columns and 'volume' in self.data.columns:
            # 计算EMA
            if 'close' in self.data.columns:
                self.data['EMA5'] = self.calculate_ema(self.data['close'], 5)
                self.data['EMA10'] = self.calculate_ema(self.data['close'], 10)
                self.data['EMA20'] = self.calculate_ema(self.data['close'], 20)
                self.technical_indicators['EMA5'] = round(self.data['EMA5'].iloc[-1], 2)
                self.technical_indicators['EMA10'] = round(self.data['EMA10'].iloc[-1], 2)
                self.technical_indicators['EMA20'] = round(self.data['EMA20'].iloc[-1], 2)
            
            # 计算A/D Line
            ad_line = self.calculate_ad_line(self.data)
            self.technical_indicators['AD_Line'] = round(ad_line.iloc[-1], 2)
            
            # 计算Chaikin Money Flow
            cmf = self.calculate_chaikin_mf(self.data)
            self.technical_indicators['Chaikin_MF'] = round(cmf.iloc[-1], 4)
            
            # 计算成交量加权MACD
            if 'close' in self.data.columns and 'volume' in self.data.columns:
                # 计算成交量加权价格
                self.data['VWAP'] = (self.data['close'] * self.data['volume']).cumsum() / self.data['volume'].cumsum()
                # 计算VWAP的MACD
                exp1 = self.calculate_ema(self.data['VWAP'], 12)
                exp2 = self.calculate_ema(self.data['VWAP'], 26)
                vw_macd = exp1 - exp2
                vw_signal = self.calculate_ema(vw_macd, 9)
                vw_hist = vw_macd - vw_signal
                self.technical_indicators['VW_MACD'] = round(vw_macd.iloc[-1], 4)
                self.technical_indicators['VW_MACD_Signal'] = round(vw_signal.iloc[-1], 4)
                self.technical_indicators['VW_MACD_Hist'] = round(vw_hist.iloc[-1], 4)

        # 分析各个指标的趋势
        self.analyze_ma_trend()
        self.analyze_macd_trend()
        self.analyze_rsi_trend()
        self.analyze_kdj_trend()
        self.analyze_obv_trend()
        self.analyze_adx_trend()
        self.analyze_volume_trend()
        self.analyze_bollinger_trend()
        self.analyze_cci_trend()
        self.analyze_mfi_trend()
        self.analyze_vw_macd_trend()
        self.analyze_support_resistance()

        # 检测信号矛盾
        self.detect_conflicts()

        # ========== 新增数值化分析 ==========
        self.compute_numerical_trend_scores()
        self.compute_indicator_changes()
        self.compute_risk_metrics()
        self.multi_timeframe_analysis()
        self.compute_consistency_score()
        self.generate_trading_signal()

    # ==================== 以下原有方法保持不变 ====================
    def analyze_ma_trend(self):
        """分析移动平均线趋势（短期+长期）"""
        ma5 = self._safe_series('MA5')
        ma10 = self._safe_series('MA10')
        ma20 = self._safe_series('MA20')
        ma60 = self._safe_series('MA60')
        ma120 = self._safe_series('MA120')

        if ma5 is None or ma10 is None or ma20 is None:
            self.indicator_trends['MA'] = "数据不足，无法分析均线趋势"
            return

        latest_ma5 = ma5[-1]
        latest_ma10 = ma10[-1]
        latest_ma20 = ma20[-1]
        latest_ma60 = ma60[-1] if ma60 is not None else None
        latest_ma120 = ma120[-1] if ma120 is not None else None

        desc = f"最新值: MA5={latest_ma5:.2f}, MA10={latest_ma10:.2f}, MA20={latest_ma20:.2f}"
        if latest_ma60:
            desc += f", MA60={latest_ma60:.2f}"
        if latest_ma120:
            desc += f", MA120={latest_ma120:.2f}"

        # 排列状态
        if latest_ma5 > latest_ma10 > latest_ma20:
            desc += "，呈多头排列，上涨趋势"
        elif latest_ma5 < latest_ma10 < latest_ma20:
            desc += "，呈空头排列，下跌趋势"
        else:
            desc += "，呈混乱排列，震荡趋势"

        # 短期相对长期位置
        if latest_ma5 > latest_ma20:
            desc += "，短期均线在长期均线上方"
        else:
            desc += "，短期均线在长期均线下方"

        # 均线斜率（最近10天）
        if len(ma5) >= 10:
            ma5_slope = (ma5[-1] - ma5[-10]) / ma5[-10] if ma5[-10] != 0 else 0
            ma20_slope = (ma20[-1] - ma20[-10]) / ma20[-10] if ma20[-10] != 0 else 0
            if ma5_slope > 0.02:
                desc += "，MA5快速上升，短期动能强劲"
            elif ma5_slope > 0:
                desc += "，MA5缓慢上升"
            elif ma5_slope < -0.02:
                desc += "，MA5快速下降，短期动能疲软"
            elif ma5_slope < 0:
                desc += "，MA5缓慢下降"

            if ma20_slope > 0.01:
                desc += "，MA20持续上升，中期趋势向好"
            elif ma20_slope < -0.01:
                desc += "，MA20持续下降，中期趋势走弱"

        self.indicator_trends['MA'] = desc

    def analyze_macd_trend(self):
        """分析MACD趋势（DIF, DEA, 柱状图）"""
        dif = self._safe_series('DIF')
        dea = self._safe_series('DEA')
        hist = self._safe_series('MACD_hist')

        if dif is None or dea is None:
            self.indicator_trends['MACD'] = "数据不足，无法分析MACD"
            return

        latest_dif = dif[-1]
        latest_hist = hist[-1] if hist is not None else dif[-1] - dea[-1]

        desc = f"最新值: DIF={latest_dif:.4f}, DEA={dea[-1]:.4f}, 柱状值={latest_hist:.4f}"

        # 金叉死叉判断
        if len(dif) >= 2:
            if dif[-1] > dea[-1] and dif[-2] <= dea[-2]:
                desc += "，最近形成金叉，买入信号"
            elif dif[-1] < dea[-1] and dif[-2] >= dea[-2]:
                desc += "，最近形成死叉，卖出信号"

        # 柱状图趋势（最近10天）
        if hist is not None and len(hist) >= 10:
            recent_hist = hist[-10:]
            first_half = np.mean(np.abs(recent_hist[:5]))
            second_half = np.mean(np.abs(recent_hist[5:]))
            if second_half > first_half * 1.2:
                if latest_hist > 0:
                    desc += "，红柱逐渐增大，多头力量持续增强"
                else:
                    desc += "，绿柱逐渐增大，空头力量持续增强"
            elif second_half < first_half * 0.8:
                if latest_hist > 0:
                    desc += "，红柱逐渐减小，多头力量减弱"
                else:
                    desc += "，绿柱逐渐减小，空头力量减弱"
            else:
                if latest_hist > 0:
                    desc += "，红柱大小稳定，多头力量保持"
                else:
                    desc += "，绿柱大小稳定，空头力量保持"

        self.indicator_trends['MACD'] = desc

    def analyze_rsi_trend(self):
        """分析RSI趋势"""
        rsi = self._safe_series('RSI')
        if rsi is None:
            self.indicator_trends['RSI'] = "数据不足"
            return

        latest_rsi = rsi[-1]
        desc = f"最新值: {latest_rsi:.2f}"

        if latest_rsi > 70:
            desc += "，处于超买区域，可能回调"
        elif latest_rsi < 30:
            desc += "，处于超卖区域，可能反弹"
        else:
            desc += "，处于正常区域"

        if len(rsi) >= 10:
            recent = rsi[-10:]
            first_avg = np.mean(recent[:5])
            second_avg = np.mean(recent[5:])
            if second_avg > first_avg * 1.1:
                desc += "，近10天RSI持续上升，上涨动能增强"
            elif second_avg < first_avg * 0.9:
                desc += "，近10天RSI持续下降，下跌动能增强"
            else:
                desc += "，近10天RSI相对稳定"

        self.indicator_trends['RSI'] = desc

    def analyze_kdj_trend(self):
        """分析KDJ趋势"""
        k = self._safe_series('K')
        d = self._safe_series('D')
        if k is None or d is None:
            self.indicator_trends['KDJ'] = "数据不足"
            return

        latest_k = k[-1]
        latest_d = d[-1]
        desc = f"最新值: K={latest_k:.2f}, D={latest_d:.2f}"

        if len(k) >= 2:
            if latest_k > latest_d and k[-2] <= d[-2]:
                desc += "，最近形成金叉，买入信号"
            elif latest_k < latest_d and k[-2] >= d[-2]:
                desc += "，最近形成死叉，卖出信号"

        if latest_k > 80 or latest_d > 80:
            desc += "，处于超买区域"
        elif latest_k < 20 or latest_d < 20:
            desc += "，处于超卖区域"

        if len(k) >= 8:
            k_first = np.mean(k[-8:-4])
            k_second = np.mean(k[-4:])
            d_first = np.mean(d[-8:-4])
            d_second = np.mean(d[-4:])
            if k_second > k_first * 1.1:
                desc += "，K值持续上升，短期动能增强"
            elif k_second < k_first * 0.9:
                desc += "，K值持续下降，短期动能减弱"
            if d_second > d_first * 1.1:
                desc += "，D值持续上升，中期趋势转强"
            elif d_second < d_first * 0.9:
                desc += "，D值持续下降，中期趋势转弱"

        self.indicator_trends['KDJ'] = desc

    def analyze_obv_trend(self):
        """分析OBV趋势"""
        obv = self._safe_series('OBV')
        if obv is None:
            self.indicator_trends['OBV'] = "数据不足"
            return

        latest_obv = obv[-1]
        desc = f"最新值: {latest_obv:.2f}"

        if len(obv) >= 10:
            recent = obv[-10:]
            change = (recent[-1] - recent[0]) / abs(recent[0]) if recent[0] != 0 else 0
            if change > 0:
                desc += "，近10天OBV上升，资金流入"
            else:
                desc += "，近10天OBV下降，资金流出"

            if abs(change) > 0.1:
                desc += "，资金流强度较大"
            elif abs(change) > 0.05:
                desc += "，资金流强度中等"
            else:
                desc += "，资金流强度较小"

            # 与价格关系
            close = self._safe_series('close')
            if close is not None and len(close) >= 10:
                price_change = (close[-1] - close[-10]) / close[-10] if close[-10] != 0 else 0
                if change > 0 and price_change > 0:
                    desc += "，价量配合良好"
                elif change < 0 and price_change < 0:
                    desc += "，价量配合良好"
                elif change > 0 and price_change < 0:
                    desc += "，量价背离，可能反弹"
                elif change < 0 and price_change > 0:
                    desc += "，量价背离，可能回调"

        self.indicator_trends['OBV'] = desc

    def analyze_adx_trend(self):
        """分析ADX趋势强度"""
        adx = self._safe_series('ADX')
        if adx is None:
            self.indicator_trends['ADX'] = "数据不足"
            return

        latest_adx = adx[-1]
        desc = f"最新值: {latest_adx:.2f}"

        if latest_adx > 50:
            desc += "，趋势强度极强"
        elif latest_adx > 40:
            desc += "，趋势强度强"
        elif latest_adx > 30:
            desc += "，趋势强度中等"
        elif latest_adx > 20:
            desc += "，趋势强度弱"
        else:
            desc += "，无明显趋势"

        if len(adx) >= 10:
            first_avg = np.mean(adx[-10:-5])
            second_avg = np.mean(adx[-5:])
            if second_avg > first_avg * 1.2:
                desc += "，近10天趋势强度明显增强"
            elif second_avg > first_avg * 1.1:
                desc += "，近10天趋势强度有所增强"
            elif second_avg < first_avg * 0.8:
                desc += "，近10天趋势强度明显减弱"
            elif second_avg < first_avg * 0.9:
                desc += "，近10天趋势强度有所减弱"
            else:
                desc += "，近10天趋势强度稳定"

        self.indicator_trends['ADX'] = desc

    def analyze_volume_trend(self):
        """分析成交量趋势（使用Volume_Ratio或直接volume）"""
        vol_ratio = self._safe_series('Volume_Ratio')
        volume = self._safe_series('volume')
        if vol_ratio is not None:
            latest_ratio = vol_ratio[-1]
            desc = f"量比: {latest_ratio:.2f}"
            if latest_ratio > 1.5:
                desc += "，成交量显著放大"
            elif latest_ratio > 1.2:
                desc += "，成交量温和放大"
            elif latest_ratio < 0.6:
                desc += "，成交量明显萎缩"
            elif latest_ratio < 0.8:
                desc += "，成交量温和萎缩"
            else:
                desc += "，成交量相对正常"

            if len(vol_ratio) >= 10:
                if np.mean(vol_ratio[-5:]) > np.mean(vol_ratio[-10:-5]) * 1.2:
                    desc += "，近10天量比呈上升趋势"
                elif np.mean(vol_ratio[-5:]) < np.mean(vol_ratio[-10:-5]) * 0.8:
                    desc += "，近10天量比呈下降趋势"
        elif volume is not None:
            latest_vol = volume[-1]
            avg_vol = np.mean(volume[-10:]) if len(volume) >= 10 else latest_vol
            desc = f"最新成交量: {latest_vol:.0f}"
            if latest_vol > avg_vol * 1.5:
                desc += "，成交量显著放大"
            elif latest_vol < avg_vol * 0.5:
                desc += "，成交量显著萎缩"
            else:
                desc += "，成交量相对稳定"
        else:
            self.indicator_trends['Volume'] = "数据不足"
            return

        self.indicator_trends['Volume'] = desc

    def analyze_bollinger_trend(self):
        """分析布林带"""
        upper = self._safe_series('BB_upper')
        middle = self._safe_series('BB_middle')
        lower = self._safe_series('BB_lower')
        pctB = self._safe_series('BB_pctB')
        close = self._safe_series('close')

        if upper is None or middle is None or lower is None or close is None:
            self.indicator_trends['Bollinger'] = "数据不足"
            return

        latest_close = close[-1]
        latest_upper = upper[-1]
        latest_lower = lower[-1]
        latest_pctB = pctB[-1] if pctB is not None else (latest_close - latest_lower) / (latest_upper - latest_lower) if latest_upper != latest_lower else 0.5

        desc = f"最新值: 上轨={latest_upper:.2f}, 中轨={middle[-1]:.2f}, 下轨={latest_lower:.2f}, %B={latest_pctB:.2f}"

        if latest_close > latest_upper:
            desc += "，价格突破上轨，超强多头，可能回调"
        elif latest_close < latest_lower:
            desc += "，价格跌破下轨，超强空头，可能反弹"
        elif latest_close > middle[-1]:
            desc += "，价格位于中轨上方，多头占优"
        else:
            desc += "，价格位于中轨下方，空头占优"

        # 带宽变化
        bandwidth = self._safe_series('BB_width')
        if bandwidth is not None and len(bandwidth) >= 10:
            if bandwidth[-1] < bandwidth[-10] * 0.8:
                desc += "，布林带收窄，可能酝酿突破"
            elif bandwidth[-1] > bandwidth[-10] * 1.2:
                desc += "，布林带扩张，波动加剧"

        self.indicator_trends['Bollinger'] = desc

    def analyze_cci_trend(self):
        """分析CCI指标"""
        cci = self._safe_series('CCI')
        if cci is None:
            self.indicator_trends['CCI'] = "数据不足"
            return

        latest_cci = cci[-1]
        desc = f"最新值: {latest_cci:.2f}"

        if latest_cci > 100:
            desc += "，处于超买区域，可能回调"
        elif latest_cci < -100:
            desc += "，处于超卖区域，可能反弹"
        else:
            desc += "，处于正常区域"

        if len(cci) >= 10:
            if cci[-1] > cci[-10] * 1.2:
                desc += "，近10天CCI快速上升"
            elif cci[-1] < cci[-10] * 0.8:
                desc += "，近10天CCI快速下降"

        self.indicator_trends['CCI'] = desc

    def analyze_mfi_trend(self):
        """分析MFI资金流量指标"""
        mfi = self._safe_series('MFI')
        if mfi is None:
            self.indicator_trends['MFI'] = "数据不足"
            return

        latest_mfi = mfi[-1]
        desc = f"最新值: {latest_mfi:.2f}"

        if latest_mfi > 80:
            desc += "，超买，资金流出风险"
        elif latest_mfi < 20:
            desc += "，超卖，资金流入机会"
        else:
            desc += "，资金流向正常"

        if len(mfi) >= 10:
            if mfi[-1] > mfi[-10] * 1.1:
                desc += "，近10天MFI上升，资金流入增强"
            elif mfi[-1] < mfi[-10] * 0.9:
                desc += "，近10天MFI下降，资金流出增强"

        self.indicator_trends['MFI'] = desc

    def analyze_vw_macd_trend(self):
        """分析成交量加权MACD趋势"""
        # 从技术指标中获取VW_MACD值，而不是从原始数据列
        vw_macd = self.technical_indicators.get('VW_MACD', 0)
        vw_macd_signal = self.technical_indicators.get('VW_MACD_Signal', 0)
        vw_macd_hist = self.technical_indicators.get('VW_MACD_Hist', 0)
        
        if vw_macd == 0 or vw_macd_signal == 0:
            self.indicator_trends['VW_MACD'] = "数据不足"
            return

        desc = f"最新值: VW_MACD={vw_macd:.4f}, 柱状值={vw_macd_hist:.4f}"

        # 金叉死叉判断
        if vw_macd > vw_macd_signal:
            desc += "，金叉状态，多头信号"
        else:
            desc += "，死叉状态，空头信号"

        # 柱状图分析
        if vw_macd_hist > 0:
            desc += "，红柱，多头占优"
        else:
            desc += "，绿柱，空头占优"

        self.indicator_trends['VW_MACD'] = desc

    def analyze_support_resistance(self):
        """计算支撑阻力（基于近期高低点和ATR）"""
        high = self._safe_series('high')
        low = self._safe_series('low')
        close = self._safe_series('close')
        atr = self._safe_series('ATR')

        if high is None or low is None or close is None:
            self.indicator_trends['Support_Resistance'] = "数据不足"
            return

        # 最近20日高低点
        lookback = min(20, len(high))
        recent_high = np.max(high[-lookback:])
        recent_low = np.min(low[-lookback:])
        current_price = close[-1]
        percentile = (current_price - recent_low) / (recent_high - recent_low) if recent_high != recent_low else 0.5

        desc = f"近{lookback}日高点: {recent_high:.2f}, 低点: {recent_low:.2f}, 当前价格位于区间{percentile*100:.1f}%分位"

        if atr is not None:
            atr_val = atr[-1]
            support = current_price - atr_val
            resistance = current_price + atr_val
            desc += f"，ATR通道支撑≈{support:.2f}，阻力≈{resistance:.2f}"

        self.indicator_trends['Support_Resistance'] = desc

    def detect_conflicts(self):
        """检测技术指标之间的信号矛盾"""
        conflicts = []
        # 获取主要信号
        rsi = self.technical_indicators.get('RSI', 50)
        macd_hist = self.technical_indicators.get('MACD_hist', 0)
        k = self.technical_indicators.get('K', 50)
        d = self.technical_indicators.get('D', 50)
        adx = self.technical_indicators.get('ADX', 20)
        cci = self.technical_indicators.get('CCI', 0)
        mfi = self.technical_indicators.get('MFI', 50)

        # RSI超买 vs MACD红柱缩小
        if rsi > 70 and macd_hist > 0 and ('MACD' in self.indicator_trends and '红柱逐渐减小' in self.indicator_trends['MACD']):
            conflicts.append("RSI超买但MACD红柱缩小，上涨动能可能衰竭")

        # KDJ高位死叉 vs MACD仍红
        if k < d and k > 80 and macd_hist > 0:
            conflicts.append("KDJ高位死叉但MACD仍为红柱，短期回调与中期多头矛盾")

        # ADX弱趋势但价格创新高/低
        if adx < 25 and (self.technical_indicators.get('close', 0) > self.technical_indicators.get('MA20', 0) * 1.05):
            conflicts.append("ADX显示弱趋势，但价格明显偏离均线，可能处于震荡末期")

        # CCI与RSI方向背离（简化）
        if len(self._safe_series('CCI')) >= 5 and len(self._safe_series('RSI')) >= 5:
            cci_series = self._safe_series('CCI')
            rsi_series = self._safe_series('RSI')
            if cci_series is not None and rsi_series is not None:
                if cci_series[-1] > cci_series[-5] and rsi_series[-1] < rsi_series[-5]:
                    conflicts.append("CCI上升但RSI下降，短期动量背离")

        # 价格与指标的顶/底背离检测
        close_series = self._safe_series('close')
        rsi_series = self._safe_series('RSI')
        macd_hist_series = self._safe_series('MACD_hist')
        
        if close_series is not None and rsi_series is not None and len(close_series) >= 20:
            # 检测价格创新高但RSI未创新高的顶背离
            recent_high = max(close_series[-20:])
            high_idx = np.argmax(close_series[-20:]) + len(close_series) - 20
            if high_idx == len(close_series) - 1:  # 当前价格是近20日高点
                rsi_high = max(rsi_series[-20:])
                rsi_high_idx = np.argmax(rsi_series[-20:]) + len(rsi_series) - 20
                if rsi_high_idx < len(rsi_series) - 5:  # RSI高点出现在至少5天前
                    conflicts.append("价格创新高但RSI未创新高，可能形成顶背离")
        
        if close_series is not None and macd_hist_series is not None and len(close_series) >= 20:
            # 检测价格创新高但MACD未创新高的顶背离
            recent_high = max(close_series[-20:])
            high_idx = np.argmax(close_series[-20:]) + len(close_series) - 20
            if high_idx == len(close_series) - 1:  # 当前价格是近20日高点
                macd_high = max(macd_hist_series[-20:])
                macd_high_idx = np.argmax(macd_hist_series[-20:]) + len(macd_hist_series) - 20
                if macd_high_idx < len(macd_hist_series) - 5:  # MACD高点出现在至少5天前
                    conflicts.append("价格创新高但MACD未创新高，可能形成顶背离")

        if len(conflicts) > 0:
            self.signal_conflicts = conflicts
            self.indicator_trends['Signal_Conflicts'] = "；".join(conflicts)
        else:
            self.indicator_trends['Signal_Conflicts'] = "无明显信号矛盾"

    def generate_market_snapshot(self):
        """生成市场状态快照"""
        close = self.technical_indicators.get('close', 0)
        rsi = self.technical_indicators.get('RSI', 50)
        macd_hist = self.technical_indicators.get('MACD_hist', 0)
        bb_pctb = self.technical_indicators.get('BB_pctB', 0.5)
        mfi = self.technical_indicators.get('MFI', 50)
        ma5 = self.technical_indicators.get('MA5', 0)
        ma10 = self.technical_indicators.get('MA10', 0)
        ma20 = self.technical_indicators.get('MA20', 0)
        
        # 构建快照文本
        snapshot = "当前处于"
        
        # 趋势判断
        if ma5 > ma10 > ma20:
            snapshot += "强势多头趋势中"
        elif ma5 < ma10 < ma20:
            snapshot += "强势空头趋势中"
        else:
            snapshot += "震荡趋势中"
        
        # 价格位置
        if bb_pctb > 0.8:
            snapshot += "，价格接近布林带上轨"
        elif bb_pctb < 0.2:
            snapshot += "，价格接近布林带下轨"
        else:
            snapshot += "，价格位于布林带中轨附近"
        
        # 超买超卖
        if rsi > 70 or mfi > 80:
            snapshot += "，RSI与MFI均进入超买区，短期存在回调压力"
        elif rsi < 30 or mfi < 20:
            snapshot += "，RSI与MFI均进入超卖区，短期存在反弹机会"
        else:
            snapshot += "，RSI与MFI处于正常区间"
        
        # 中期趋势
        if macd_hist > 0:
            snapshot += "，但中期趋势未破"
        else:
            snapshot += "，中期趋势走弱"
        
        return snapshot

    def generate_indicator_labels(self):
        """生成指标标签"""
        labels = {}
        
        # RSI标签
        rsi = self.technical_indicators.get('RSI', 50)
        if rsi > 70:
            labels['RSI'] = "超买(>70)，需警惕回调"
        elif rsi < 30:
            labels['RSI'] = "超卖(<30)，可能反弹"
        else:
            labels['RSI'] = "正常区间(30-70)"
        
        # ADX标签
        adx = self.technical_indicators.get('ADX', 20)
        if adx > 40:
            labels['ADX'] = "强趋势区间(>40)，方向明确"
        elif adx > 25:
            labels['ADX'] = "趋势启动区间(25-40)"
        else:
            labels['ADX'] = "无明显趋势(<25)"
        
        # MFI标签
        mfi = self.technical_indicators.get('MFI', 50)
        if mfi > 80:
            labels['MFI'] = "超买(>80)，资金可能流出"
        elif mfi < 20:
            labels['MFI'] = "超卖(<20)，资金可能流入"
        else:
            labels['MFI'] = "资金流向正常(20-80)"
        
        # MACD标签
        macd_hist = self.technical_indicators.get('MACD_hist', 0)
        if macd_hist > 0:
            labels['MACD'] = "红柱，多头占优"
        else:
            labels['MACD'] = "绿柱，空头占优"
        
        # 布林带标签
        bb_pctb = self.technical_indicators.get('BB_pctB', 0.5)
        if bb_pctb > 1:
            labels['Bollinger'] = "突破上轨，超强多头"
        elif bb_pctb < 0:
            labels['Bollinger'] = "突破下轨，超强空头"
        elif bb_pctb > 0.7:
            labels['Bollinger'] = "接近上轨，多头占优"
        elif bb_pctb < 0.3:
            labels['Bollinger'] = "接近下轨，空头占优"
        else:
            labels['Bollinger'] = "位于中轨附近，震荡"
        
        # VW_MACD标签
        vw_macd = self.technical_indicators.get('VW_MACD', 0)
        vw_macd_signal = self.technical_indicators.get('VW_MACD_Signal', 0)
        vw_macd_hist = self.technical_indicators.get('VW_MACD_Hist', 0)
        if vw_macd > vw_macd_signal and vw_macd_hist > 0:
            labels['VW_MACD'] = "金叉，红柱，多头占优"
        elif vw_macd > vw_macd_signal and vw_macd_hist < 0:
            labels['VW_MACD'] = "金叉，绿柱，信号矛盾"
        elif vw_macd < vw_macd_signal and vw_macd_hist < 0:
            labels['VW_MACD'] = "死叉，绿柱，空头占优"
        elif vw_macd < vw_macd_signal and vw_macd_hist > 0:
            labels['VW_MACD'] = "死叉，红柱，信号矛盾"
        else:
            labels['VW_MACD'] = "信号不明确"
        
        return labels

    def compute_price_action(self):
        """计算价格行为指标"""
        price_action = {}
        close = self._safe_full_series('close')
        if close is not None and len(close) >= 20:
            # 5日和20日收益率
            price_action['return_5d'] = round(float((close[-1] - close[-5]) / close[-5] * 100), 2)
            price_action['return_20d'] = round(float((close[-1] - close[-20]) / close[-20] * 100), 2)
            
            # 最近20日高低点
            recent_high = max(close[-20:])
            recent_low = min(close[-20:])
            price_action['gap_from_20d_high'] = round(float((close[-1] - recent_high) / recent_high * 100), 2)
            price_action['gap_from_20d_low'] = round(float((close[-1] - recent_low) / recent_low * 100), 2)
            
            # 相对于MA20的位置
            ma20 = self.technical_indicators.get('MA20', close[-1])
            if ma20 > 0:
                price_action['above_ma20_percent'] = round(float((close[-1] - ma20) / ma20 * 100), 2)
            else:
                price_action['above_ma20_percent'] = 0
            
            # 波动率状态
            returns = pd.Series(close).pct_change().dropna()
            if len(returns) >= 20:
                current_vol = returns.tail(20).std() * np.sqrt(252)
                # 计算历史波动率分位
                if len(returns) >= 252:
                    historical_vol = returns.tail(252).std() * np.sqrt(252)
                    vol_percentile = (current_vol / historical_vol) * 100
                    if vol_percentile > 150:
                        volatility_regime = f"极高波动期 (20日波动率{current_vol:.2f}，位于历史150%以上)"
                    elif vol_percentile > 120:
                        volatility_regime = f"高波动期 (20日波动率{current_vol:.2f}，位于历史120-150%)"
                    elif vol_percentile > 80:
                        volatility_regime = f"正常波动期 (20日波动率{current_vol:.2f}，位于历史80-120%)"
                    else:
                        volatility_regime = f"低波动期 (20日波动率{current_vol:.2f}，位于历史80%以下)"
                else:
                    volatility_regime = f"20日波动率{current_vol:.2f}"
                price_action['volatility_regime'] = volatility_regime
        else:
            price_action['return_5d'] = None
            price_action['return_20d'] = None
            price_action['gap_from_20d_high'] = None
            price_action['gap_from_20d_low'] = None
            price_action['above_ma20_percent'] = None
            price_action['volatility_regime'] = None
        return price_action

    def generate_trend_report(self):
        """生成最终报告JSON（包含新增结构化字段）"""
        # 计算额外指标
        price_action = self.compute_price_action()
        indicator_labels = self.generate_indicator_labels()
        market_snapshot = self.generate_market_snapshot()
        
        # 优化trend_scores为trend_confidence，并降低小数精度
        # 确保has_divergence与multi_timeframe.divergence保持一致
        has_divergence = self.trend_scores.get('has_divergence', False) or self.multi_timeframe.get('divergence', False)
        
        trend_confidence = {
            'ma_bullish_alignment': round(self.trend_scores.get('ma_bullish_score', 0.5), 2),
            'macd_momentum_strength': round(self.trend_scores.get('macd_power', 0.5), 2),
            'adx_trend_presence': round(self.trend_scores.get('adx_trend_strength', 0.2), 2),
            'overbought_risk': round(abs(self.trend_scores.get('overbought_oversold', 0)), 2),
            'volume_momentum': round(self.trend_scores.get('volume_flow', 0), 2),
            'price_momentum': round(self.trend_scores.get('price_momentum', 0.5), 2),
            'divergence_score': round(self.trend_scores.get('divergence_score', 1.0), 2),
            'has_divergence': has_divergence
        }
        
        # 确保divergence_score与has_divergence保持一致
        if has_divergence and trend_confidence['divergence_score'] >= 0.5:
            trend_confidence['divergence_score'] = 0.4  # 如果存在背离，将divergence_score设为低于0.5
        
        # 扩充trading_signal的reason
        if self.trading_signal.get('reason') == "中期走弱且短期超买":
            self.trading_signal['reason'] = "中期趋势走弱，且RSI与MFI均进入超买区域，短期存在回调压力"
        
        # 为indicator_changes添加close的涨跌幅
        close_series = self._safe_series('close')
        if close_series is not None and len(close_series) >= 10:
            close_val = float(close_series[-1])
            close_change_5d = float(close_series[-1] - close_series[-5]) if len(close_series) >= 5 else None
            close_change_10d = float(close_series[-1] - close_series[-10]) if len(close_series) >= 10 else None
            self.indicator_changes['close'] = {
                'value': round(close_val, 2),
                'change_5d': round(close_change_5d, 2) if close_change_5d is not None else None,
                'change_10d': round(close_change_10d, 2) if close_change_10d is not None else None
            }
        
        report = {
            'meta': {
                'ticker': self.ticker,
                'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_window_days': self.meta.get('recent_days', len(self.recent_data)),
                'last_data_date': self.meta.get('last_date', ''),
                'field_notes': {
                    'Volume_Ratio': '当日成交量 / 过去5日均量（量比）',
                    'trend_confidence': '0~1，数值越大表示该维度信号越强',
                    'ma_bullish_alignment': '0~1，均线多头排列强度，1表示完全多头排列',
                    'macd_momentum_strength': '0~1，MACD动量强度，基于柱状图大小和趋势',
                    'adx_trend_presence': '0~1，ADX趋势强度，基于ADX指标值归一化',
                    'overbought_risk': '0~1，超买超卖风险，基于RSI指标',
                    'volume_momentum': '0~1，成交量动量，基于量比和OBV变化',
                    'price_momentum': '0~1，价格动量强度，基于价格变化率',
                    'divergence_score': '0~1，指标背离程度，1表示无背离，低于0.5表示存在背离',
                    'has_divergence': '布尔值，是否存在指标背离',
                    'BB_pctB': '价格在布林带中的位置，>1 突破上轨，<0 突破下轨',
                    'MFI': '资金流量指标，>80超买，<20超卖',
                    'ATR': '平均真实波幅，衡量价格波动幅度',
                    'consistency_score': '0~1，各技术指标方向一致性的比例，1 表示完全一致（全看多或全看空），考虑了均线、MACD、RSI、ADX、KDJ、CCI、MFI、布林带等8个指标'
                }
            },
            'technical_indicators': self.technical_indicators,
            'indicator_labels': indicator_labels,
            'indicator_trends': self.indicator_trends,      # 保留文本描述
            'signal_conflicts': self.signal_conflicts,
            # 新增结构化数据
            'trend_confidence': trend_confidence,
            'trading_signal': self.trading_signal,
            'indicator_changes': self.indicator_changes,
            'risk_metrics': self.risk_metrics,
            'price_action': price_action,
            'multi_timeframe': self.multi_timeframe,
            'consistency_score': self.consistency_score,
            'market_snapshot': market_snapshot
        }
        # 递归转换所有 numpy 类型为 Python 原生类型
        return self._convert_to_native(report)

    def save_report(self, report):
        """保存报告为JSON"""
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        os.makedirs(stock_dir, exist_ok=True)

        filename = f"{self.ticker}_technical_trend_analysis.json"
        file_path = os.path.join(stock_dir, filename)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"趋势分析报告已保存: {file_path}")
        return file_path

    def print_report(self, report):
        """打印报告摘要（可扩展显示新增内容）"""
        print(f"\n=== 股票技术指标趋势分析报告 ===")
        print(f"股票代码: {report['meta']['ticker']}")
        print(f"分析日期: {report['meta']['analysis_date']}")
        print(f"数据窗口: {report['meta']['data_window_days']} 天")
        print("\n=== 最新技术指标值 ===")
        for k, v in report['technical_indicators'].items():
            print(f"{k}: {v}")
        print("\n=== 指标趋势分析 ===")
        for k, v in report['indicator_trends'].items():
            print(f"{k}: {v}")
        # 打印新增关键信息
        print("\n=== 交易信号 ===")
        sig = report.get('trading_signal', {})
        print(f"操作: {sig.get('action')}, 置信度: {sig.get('confidence')}, 原因: {sig.get('reason')}")
        print(f"一致性评分: {report.get('consistency_score')}")

    def run_analysis(self):
        """运行完整分析流程"""
        self.load_data()
        self.analyze_technical_indicators()
        report = self.generate_trend_report()
        self.print_report(report)
        self.save_report(report)
        return report

def main():
    import argparse
    parser = argparse.ArgumentParser(description="分析股票技术指标趋势")
    parser.add_argument('--ticker', help="股票代码，例如：002384.SZ")
    args = parser.parse_args()

    if args.ticker:
        ticker = args.ticker
    else:
        # 尝试从config读取第一个股票
        try:
            from config import STOCK_TICKERS
            ticker = next(iter(STOCK_TICKERS.values()))
            print(f"使用配置文件中的股票代码: {ticker}")
        except ImportError:
            print("未指定股票代码，请使用 --ticker 参数")
            return

    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker}, 数据文件: {file_path}")

    analyzer = StockTechnicalTrendAnalyzer(file_path)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()