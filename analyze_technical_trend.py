#!/usr/bin/env python3
# analyze_technical_trend.py
# 功能：分析股票技术指标趋势，提供详细的趋势描述
# 实现原理：
# 1. 加载本地股票数据文件
# 2. 提取最近半个月或一个月的数据
# 3. 分析关键技术指标的趋势变化
# 4. 为每个指标生成趋势描述
# 5. 生成综合分析报告
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import json
import os
import sys

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR

class StockTechnicalTrendAnalyzer:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        self.recent_data = None
        self.technical_indicators = {}
        self.indicator_trends = {}
    
    def load_data(self):
        """加载数据"""
        print(f"加载数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
            # 按日期排序
            self.data = self.data.sort_values('date')
        
        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[0]
        else:
            # 从文件路径中提取股票代码
            file_name = os.path.basename(self.file_path)
            self.ticker = file_name.split('_')[0]
        
        # 获取最近30天的数据
        if 'date' in self.data.columns:
            # 计算30天前的日期
            end_date = self.data['date'].iloc[-1]
            start_date = end_date - timedelta(days=30)
            self.recent_data = self.data[self.data['date'] >= start_date]
        else:
            # 如果没有日期列，取最近30行
            self.recent_data = self.data.tail(30)
        
        print(f"加载了最近 {len(self.recent_data)} 条数据")
        return self.data
    
    def analyze_technical_indicators(self):
        """分析技术指标趋势"""
        if self.recent_data is None:
            print("数据未加载，无法分析技术指标")
            return
        
        # 获取最新数据
        latest = self.recent_data.iloc[-1]
        
        # 提取技术指标的最新值
        self.technical_indicators = {
            'MA5': round(latest.get('MA5', 0), 2),
            'MA10': round(latest.get('MA10', 0), 2),
            'MA20': round(latest.get('MA20', 0), 2),
            'RSI': round(latest.get('RSI', 0), 2),
            'MACD': round(latest.get('MACD', 0), 4),
            'MACD_signal': round(latest.get('MACD_signal', 0), 4),
            'KDJ_K': round(latest.get('K', 0), 2),
            'KDJ_D': round(latest.get('D', 0), 2),
            'KDJ_J': round(latest.get('J', 0), 2),
            'ATR': round(latest.get('ATR', 0), 2),
            'OBV': round(latest.get('OBV', 0), 2),
            'ADX': round(latest.get('ADX', 0), 2),
            'Volume': round(latest.get('volume', 0), 2)
        }
        
        # 分析各指标的趋势
        self.analyze_macd_trend()
        self.analyze_rsi_trend()
        self.analyze_kdj_trend()
        self.analyze_ma_trend()
        self.analyze_obv_trend()
        self.analyze_adx_trend()
        self.analyze_volume_trend()
    
    def analyze_macd_trend(self):
        """分析MACD趋势"""
        if 'MACD' not in self.recent_data.columns or 'MACD_signal' not in self.recent_data.columns:
            self.indicator_trends['MACD'] = "数据不足，无法分析趋势"
            return
        
        # 计算MACD柱状图
        macd = self.recent_data['MACD'].values
        macd_signal = self.recent_data['MACD_signal'].values
        macd_hist = macd - macd_signal
        
        # 分析趋势
        latest_macd = macd[-1]
        latest_macd_hist = macd_hist[-1]
        
        trend_description = f"最新值: {latest_macd:.4f}"
        
        # 分析柱状图趋势
        if len(macd_hist) >= 10:
            recent_hist = macd_hist[-10:]
            # 检查柱状图颜色变化
            if all(hist > 0 for hist in recent_hist):
                trend_description += "，近10天持续红柱，多头趋势"
            elif all(hist < 0 for hist in recent_hist):
                trend_description += "，近10天持续绿柱，空头趋势"
            else:
                # 检查最近的变化
                if latest_macd_hist > 0 and recent_hist[-2] < 0:
                    trend_description += "，最近由绿柱转为红柱，金叉形成"
                elif latest_macd_hist < 0 and recent_hist[-2] > 0:
                    trend_description += "，最近由红柱转为绿柱，死叉形成"
            
            # 检查柱状图大小变化（更详细的分析）
            if len(recent_hist) >= 8:
                # 分为前4天和后4天，比较变化趋势
                first_half = recent_hist[:4]
                second_half = recent_hist[4:]
                
                # 计算平均柱状图大小
                first_half_avg = np.mean(np.abs(first_half))
                second_half_avg = np.mean(np.abs(second_half))
                
                # 分析变化趋势
                if second_half_avg > first_half_avg * 1.2:
                    if latest_macd_hist > 0:
                        trend_description += "，红柱逐渐增大，多头力量持续增强"
                    else:
                        trend_description += "，绿柱逐渐增大，空头力量持续增强"
                elif second_half_avg < first_half_avg * 0.8:
                    if latest_macd_hist > 0:
                        trend_description += "，红柱逐渐减小，多头力量逐渐减弱"
                    else:
                        trend_description += "，绿柱逐渐减小，空头力量逐渐减弱"
                else:
                    if latest_macd_hist > 0:
                        trend_description += "，红柱大小相对稳定，多头力量保持"
                    else:
                        trend_description += "，绿柱大小相对稳定，空头力量保持"
        
        self.indicator_trends['MACD'] = trend_description
    
    def analyze_rsi_trend(self):
        """分析RSI趋势"""
        if 'RSI' not in self.recent_data.columns:
            self.indicator_trends['RSI'] = "数据不足，无法分析趋势"
            return
        
        rsi = self.recent_data['RSI'].values
        latest_rsi = rsi[-1]
        
        trend_description = f"最新值: {latest_rsi:.2f}"
        
        # 分析超买超卖状态
        if latest_rsi > 70:
            trend_description += "，处于超买区域，可能回调"
        elif latest_rsi < 30:
            trend_description += "，处于超卖区域，可能反弹"
        else:
            trend_description += "，处于正常区域"
        
        # 分析趋势变化（更详细）
        if len(rsi) >= 10:
            recent_rsi = rsi[-10:]
            # 分为前5天和后5天，比较变化趋势
            first_half = recent_rsi[:5]
            second_half = recent_rsi[5:]
            
            # 计算平均值
            first_half_avg = np.mean(first_half)
            second_half_avg = np.mean(second_half)
            
            # 分析变化趋势
            if second_half_avg > first_half_avg * 1.1:
                trend_description += "，近10天RSI持续上升，上涨动能增强"
            elif second_half_avg < first_half_avg * 0.9:
                trend_description += "，近10天RSI持续下降，下跌动能增强"
            else:
                trend_description += "，近10天RSI相对稳定，动能平衡"
        
        self.indicator_trends['RSI'] = trend_description
    
    def analyze_kdj_trend(self):
        """分析KDJ趋势"""
        if 'K' not in self.recent_data.columns or 'D' not in self.recent_data.columns:
            self.indicator_trends['KDJ'] = "数据不足，无法分析趋势"
            return
        
        k = self.recent_data['K'].values
        d = self.recent_data['D'].values
        latest_k = k[-1]
        latest_d = d[-1]
        
        trend_description = f"最新值: K={latest_k:.2f}, D={latest_d:.2f}"
        
        # 分析金叉死叉
        if len(k) >= 2:
            if latest_k > latest_d and k[-2] <= d[-2]:
                trend_description += "，最近形成金叉，买入信号"
            elif latest_k < latest_d and k[-2] >= d[-2]:
                trend_description += "，最近形成死叉，卖出信号"
        
        # 分析超买超卖
        if latest_k > 80 or latest_d > 80:
            trend_description += "，处于超买区域"
        elif latest_k < 20 or latest_d < 20:
            trend_description += "，处于超卖区域"
        
        # 分析KDJ趋势变化（更详细）
        if len(k) >= 8:
            # 分为前4天和后4天，比较变化趋势
            k_first_half = k[:4]
            k_second_half = k[4:]
            d_first_half = d[:4]
            d_second_half = d[4:]
            
            # 计算平均值
            k_first_avg = np.mean(k_first_half)
            k_second_avg = np.mean(k_second_half)
            d_first_avg = np.mean(d_first_half)
            d_second_avg = np.mean(d_second_half)
            
            # 分析K值趋势
            if k_second_avg > k_first_avg * 1.1:
                trend_description += "，K值持续上升，短期动能增强"
            elif k_second_avg < k_first_avg * 0.9:
                trend_description += "，K值持续下降，短期动能减弱"
            
            # 分析D值趋势
            if d_second_avg > d_first_avg * 1.1:
                trend_description += "，D值持续上升，中期趋势转强"
            elif d_second_avg < d_first_avg * 0.9:
                trend_description += "，D值持续下降，中期趋势转弱"
        
        self.indicator_trends['KDJ'] = trend_description
    
    def analyze_ma_trend(self):
        """分析移动平均线趋势"""
        has_ma5 = 'MA5' in self.recent_data.columns
        has_ma10 = 'MA10' in self.recent_data.columns
        has_ma20 = 'MA20' in self.recent_data.columns
        
        if not (has_ma5 and has_ma10 and has_ma20):
            self.indicator_trends['MA'] = "数据不足，无法分析趋势"
            return
        
        ma5 = self.recent_data['MA5'].values
        ma10 = self.recent_data['MA10'].values
        ma20 = self.recent_data['MA20'].values
        latest_ma5 = ma5[-1]
        latest_ma10 = ma10[-1]
        latest_ma20 = ma20[-1]
        
        trend_description = f"最新值: MA5={latest_ma5:.2f}, MA10={latest_ma10:.2f}, MA20={latest_ma20:.2f}"
        
        # 分析均线排列
        if latest_ma5 > latest_ma10 > latest_ma20:
            trend_description += "，呈多头排列，上涨趋势"
        elif latest_ma5 < latest_ma10 < latest_ma20:
            trend_description += "，呈空头排列，下跌趋势"
        else:
            trend_description += "，呈混乱排列，震荡趋势"
        
        # 分析短期均线与长期均线的关系
        if latest_ma5 > latest_ma20:
            trend_description += "，短期均线在长期均线上方"
        else:
            trend_description += "，短期均线在长期均线下方"
        
        # 分析均线趋势变化（更详细）
        if len(ma5) >= 10:
            # 分析MA5的变化趋势
            ma5_recent = ma5[-10:]
            ma5_slope = (ma5_recent[-1] - ma5_recent[0]) / ma5_recent[0]
            
            # 分析MA10的变化趋势
            ma10_recent = ma10[-10:]
            ma10_slope = (ma10_recent[-1] - ma10_recent[0]) / ma10_recent[0]
            
            # 分析MA20的变化趋势
            ma20_recent = ma20[-10:]
            ma20_slope = (ma20_recent[-1] - ma20_recent[0]) / ma20_recent[0]
            
            # 分析短期均线变化
            if ma5_slope > 0.02:
                trend_description += "，MA5快速上升，短期动能强劲"
            elif ma5_slope > 0:
                trend_description += "，MA5缓慢上升，短期动能温和"
            elif ma5_slope < -0.02:
                trend_description += "，MA5快速下降，短期动能疲软"
            elif ma5_slope < 0:
                trend_description += "，MA5缓慢下降，短期动能减弱"
            
            # 分析中长期均线变化
            if ma20_slope > 0.01:
                trend_description += "，MA20持续上升，长期趋势向好"
            elif ma20_slope > 0:
                trend_description += "，MA20缓慢上升，长期趋势稳定"
            elif ma20_slope < -0.01:
                trend_description += "，MA20持续下降，长期趋势走弱"
            elif ma20_slope < 0:
                trend_description += "，MA20缓慢下降，长期趋势转弱"
        
        self.indicator_trends['MA'] = trend_description
    
    def analyze_obv_trend(self):
        """分析OBV趋势"""
        if 'OBV' not in self.recent_data.columns:
            self.indicator_trends['OBV'] = "数据不足，无法分析趋势"
            return
        
        obv = self.recent_data['OBV'].values
        latest_obv = obv[-1]
        
        trend_description = f"最新值: {latest_obv:.2f}"
        
        # 分析OBV趋势
        if len(obv) >= 10:
            recent_obv = obv[-10:]
            # 检查趋势方向
            if recent_obv[-1] > recent_obv[0]:
                trend_description += "，近10天OBV呈上升趋势，资金流入"
            else:
                trend_description += "，近10天OBV呈下降趋势，资金流出"
            
            # 分析OBV变化强度
            obv_change = (recent_obv[-1] - recent_obv[0]) / abs(recent_obv[0])
            if abs(obv_change) > 0.1:
                if obv_change > 0:
                    trend_description += "，资金流入强度较大"
                else:
                    trend_description += "，资金流出强度较大"
            elif abs(obv_change) > 0.05:
                if obv_change > 0:
                    trend_description += "，资金流入强度中等"
                else:
                    trend_description += "，资金流出强度中等"
            else:
                trend_description += "，资金流入/流出强度较小"
            
            # 分析OBV与价格的关系
            if 'close' in self.recent_data.columns:
                close = self.recent_data['close'].values[-10:]
                price_change = (close[-1] - close[0]) / close[0]
                if obv_change > 0 and price_change > 0:
                    trend_description += "，价量配合良好，上涨动能充足"
                elif obv_change < 0 and price_change < 0:
                    trend_description += "，价量配合良好，下跌动能充足"
                elif obv_change > 0 and price_change < 0:
                    trend_description += "，量价背离，可能反弹"
                elif obv_change < 0 and price_change > 0:
                    trend_description += "，量价背离，可能回调"
        
        self.indicator_trends['OBV'] = trend_description
    
    def analyze_adx_trend(self):
        """分析ADX趋势"""
        if 'ADX' not in self.recent_data.columns:
            self.indicator_trends['ADX'] = "数据不足，无法分析趋势"
            return
        
        adx = self.recent_data['ADX'].values
        latest_adx = adx[-1]
        
        trend_description = f"最新值: {latest_adx:.2f}"
        
        # 分析趋势强度
        if latest_adx > 50:
            trend_description += "，趋势强度极强"
        elif latest_adx > 40:
            trend_description += "，趋势强度强"
        elif latest_adx > 30:
            trend_description += "，趋势强度中等"
        elif latest_adx > 20:
            trend_description += "，趋势强度弱"
        else:
            trend_description += "，无明显趋势"
        
        # 分析趋势变化（更详细）
        if len(adx) >= 10:
            recent_adx = adx[-10:]
            # 分为前5天和后5天，比较变化趋势
            first_half = recent_adx[:5]
            second_half = recent_adx[5:]
            
            # 计算平均值
            first_half_avg = np.mean(first_half)
            second_half_avg = np.mean(second_half)
            
            # 分析变化趋势
            if second_half_avg > first_half_avg * 1.2:
                trend_description += "，近10天趋势强度明显增强"
            elif second_half_avg > first_half_avg * 1.1:
                trend_description += "，近10天趋势强度有所增强"
            elif second_half_avg < first_half_avg * 0.8:
                trend_description += "，近10天趋势强度明显减弱"
            elif second_half_avg < first_half_avg * 0.9:
                trend_description += "，近10天趋势强度有所减弱"
            else:
                trend_description += "，近10天趋势强度相对稳定"
            
            # 分析ADX的具体走势
            if all(adx[i] < adx[i+1] for i in range(len(recent_adx)-1)):
                trend_description += "，ADX持续上升，趋势正在形成"
            elif all(adx[i] > adx[i+1] for i in range(len(recent_adx)-1)):
                trend_description += "，ADX持续下降，趋势正在减弱"
        
        self.indicator_trends['ADX'] = trend_description
    
    def analyze_volume_trend(self):
        """分析成交量趋势"""
        volume_col = None
        for col in ['volume', 'Volume', '成交量']:
            if col in self.recent_data.columns:
                volume_col = col
                break
        
        if volume_col is None:
            self.indicator_trends['Volume'] = "数据不足，无法分析趋势"
            return
        
        volume = self.recent_data[volume_col].values
        latest_volume = volume[-1]
        
        trend_description = f"最新值: {latest_volume:.2f}"
        
        # 分析成交量趋势
        if len(volume) >= 10:
            recent_volume = volume[-10:]
            avg_volume = np.mean(recent_volume)
            
            # 分析当前成交量相对于平均值的变化
            if latest_volume > avg_volume * 2:
                trend_description += "，成交量急剧放大"
            elif latest_volume > avg_volume * 1.5:
                trend_description += "，成交量明显放大"
            elif latest_volume > avg_volume * 1.2:
                trend_description += "，成交量有所放大"
            elif latest_volume < avg_volume * 0.3:
                trend_description += "，成交量极度萎缩"
            elif latest_volume < avg_volume * 0.5:
                trend_description += "，成交量明显缩小"
            elif latest_volume < avg_volume * 0.8:
                trend_description += "，成交量有所缩小"
            else:
                trend_description += "，成交量相对稳定"
            
            # 分析成交量的变化趋势
            first_half = recent_volume[:5]
            second_half = recent_volume[5:]
            first_half_avg = np.mean(first_half)
            second_half_avg = np.mean(second_half)
            
            if second_half_avg > first_half_avg * 1.5:
                trend_description += "，近10天成交量呈明显上升趋势"
            elif second_half_avg > first_half_avg * 1.2:
                trend_description += "，近10天成交量呈上升趋势"
            elif second_half_avg < first_half_avg * 0.5:
                trend_description += "，近10天成交量呈明显下降趋势"
            elif second_half_avg < first_half_avg * 0.8:
                trend_description += "，近10天成交量呈下降趋势"
            else:
                trend_description += "，近10天成交量相对稳定"
            
            # 分析成交量的波动情况
            volume_std = np.std(recent_volume)
            volume_cv = volume_std / avg_volume
            if volume_cv > 0.5:
                trend_description += "，成交量波动较大"
            elif volume_cv > 0.3:
                trend_description += "，成交量波动中等"
            else:
                trend_description += "，成交量波动较小"
        
        self.indicator_trends['Volume'] = trend_description
    
    def generate_trend_report(self):
        """生成趋势分析报告"""
        report = {
            'ticker': self.ticker,
            'analysis_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'technical_indicators': self.technical_indicators,
            'indicator_trends': self.indicator_trends,
            'recent_data_count': len(self.recent_data)
        }
        
        return report
    
    def save_report(self, report):
        """保存分析报告"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 生成固定文件名，去掉时间戳
        filename = f"{self.ticker}_technical_trend_analysis.json"
        file_path = os.path.join(stock_dir, filename)
        
        # 保存为JSON文件，直接覆盖
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        
        print(f"趋势分析报告已保存为: {file_path}")
        return file_path
    
    def print_report(self, report):
        """打印分析报告"""
        print(f"\n=== 股票技术指标趋势分析报告 ===")
        print(f"股票代码: {report['ticker']}")
        print(f"分析日期: {report['analysis_date']}")
        print(f"分析数据条数: {report['recent_data_count']}")
        
        print("\n=== 技术指标最新值 ===")
        for indicator, value in report['technical_indicators'].items():
            print(f"{indicator}: {value}")
        
        print("\n=== 技术指标趋势分析 ===")
        for indicator, trend in report['indicator_trends'].items():
            print(f"{indicator}: {trend}")
    
    def run_analysis(self):
        """运行完整分析"""
        self.load_data()
        self.analyze_technical_indicators()
        report = self.generate_trend_report()
        self.print_report(report)
        self.save_report(report)
        return report

def main():
    """主函数"""
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="分析股票技术指标趋势")
    parser.add_argument('--ticker', help="股票代码，例如：300433.SZ，若不指定则使用config.py中的第一个股票")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
    else:
        # 使用第一个股票代码进行分析
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker}")
    
    # 分析数据
    analyzer = StockTechnicalTrendAnalyzer(file_path)
    analyzer.run_analysis()

if __name__ == "__main__":
    main()