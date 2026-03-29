# weekly_stock_prediction.py
# 功能：基于周线历史数据，预测股票未来价格并生成交易建议
# 实现原理：
# 1. 加载周线历史数据
# 2. 计算技术指标（通过utils.py中的calculate_technical_indicators函数）
# 3. 准备特征数据，包括滞后特征
# 4. 使用随机森林模型训练和预测
# 5. 分析当前技术指标信号
# 6. 生成交易建议
# 7. 绘制预测结果图表并保存到按股票代码命名的子目录中
# 8. 支持从config.py中读取技术指标配置
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from datetime import datetime, timedelta
import logging
from utils import calculate_technical_indicators
from config import DATA_DIR, TECHNICAL_INDICATORS

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class WeeklyStockPredictor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        self.model = None
        self.scaler = None
    
    def load_data(self):
        """加载周线数据"""
        print(f"加载周线数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
            print(f"数据日期范围: {self.data['date'].min()} 到 {self.data['date'].max()}")
        
        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[0]
            print(f"股票代码: {self.ticker}")
        else:
            # 从文件路径中提取股票代码
            import os
            file_name = os.path.basename(self.file_path)
            self.ticker = file_name.split('_')[0]
            print(f"股票代码: {self.ticker}")
        
        return self.data
    
    def prepare_features(self, lookback=None):
        """准备特征数据"""
        # 使用配置文件中的lookback值
        if lookback is None:
            lookback = TECHNICAL_INDICATORS['lookback']
        
        # 选择特征列
        feature_columns = ['open', 'high', 'low', 'close', 'volume',
                         'MA5', 'MA10', 'MA20', 'MA50', 'MA60',
                         'VOL5', 'VOL10', 'Volume_Ratio',
                         'K', 'D', 'J',
                         'MACD', 'MACD_signal', 'MACD_hist',
                         'BB_upper', 'BB_middle', 'BB_lower',
                         'ATR', 'RSI_6', 'CCI', 'ROC', 'OBV',
                         'VWAP', 'Volatility', 'BIAS5', 'BIAS10', 'WR', 'DMA']
        
        # 确保所有特征列都存在
        feature_columns = [col for col in feature_columns if col in self.data.columns]
        
        print(f"可用的特征列: {feature_columns}")
        print(f"数据行数: {len(self.data)}")
        
        # 如果数据量不足，减少lookback
        if len(self.data) < lookback + 1:
            lookback = min(lookback, len(self.data) - 1)
            if lookback < 1:
                lookback = 1
            print(f"数据量不足，调整lookback为: {lookback}")
        
        # 创建滞后特征
        for col in feature_columns:
            for i in range(1, lookback + 1):
                self.data[f'{col}_lag{i}'] = self.data[col].shift(i)
        
        # 创建目标变量（下一周的收盘价）
        self.data['target'] = self.data['close'].shift(-1)
        
        # 移除含有NaN的行
        self.data = self.data.dropna()
        
        print(f"处理后的数据行数: {len(self.data)}")
        
        # 如果没有数据，使用基本特征且不创建滞后
        if len(self.data) == 0:
            print("处理后没有数据，使用基本特征")
            # 恢复原始数据
            self.data = pd.read_csv(self.file_path)
            if 'date' in self.data.columns:
                self.data['date'] = pd.to_datetime(self.data['date'])
            # 使用基本特征，不创建滞后
            feature_cols = feature_columns[:5]  # 使用前5个基本特征
            X = self.data[feature_cols]
            # 使用当前收盘价作为目标变量（简化处理）
            y = self.data['close']
        else:
            # 分离特征和目标变量
            feature_cols = [col for col in self.data.columns if 'lag' in col]
            print(f"特征列数量: {len(feature_cols)}")
            
            if len(feature_cols) == 0:
                # 如果没有特征列，使用基本特征
                feature_cols = feature_columns[:5]  # 使用前5个基本特征
                X = self.data[feature_cols]
            else:
                X = self.data[feature_cols]
            
            y = self.data['target']
        
        print(f"特征数组形状: {X.shape}")
        print(f"目标变量形状: {y.shape}")
        
        return X, y
    
    def train_model(self, X, y):
        """训练预测模型"""
        print("训练预测模型...")
        
        # 特征标准化
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        
        # 训练随机森林模型
        self.model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.model.fit(X_scaled, y)
        
        print("模型训练完成")
        return self.model
    
    def predict_future(self, weeks=5):
        """预测未来几周的股价"""
        print(f"预测未来 {weeks} 周的股价...")
        
        # 获取最新的特征数据
        latest_data = self.data.iloc[-1]
        
        predictions = []
        current_data = latest_data.copy()
        
        # 检查使用的特征类型
        lag_columns = [col for col in self.data.columns if 'lag' in col]
        
        if len(lag_columns) > 0:
            # 使用滞后特征
            print("使用滞后特征进行预测")
            # 选择特征列
            feature_columns = ['open', 'high', 'low', 'close', 'volume',
                             'MA5', 'MA10', 'MA20', 'MA50', 'MA60',
                             'VOL5', 'VOL10', 'Volume_Ratio',
                             'K', 'D', 'J',
                             'MACD', 'MACD_signal', 'MACD_hist',
                             'BB_upper', 'BB_middle', 'BB_lower',
                             'ATR', 'RSI_6', 'CCI', 'ROC', 'OBV',
                             'VWAP', 'Volatility', 'BIAS5', 'BIAS10', 'WR', 'DMA']
            feature_columns = [col for col in feature_columns if col in self.data.columns]
            
            # 预测未来几周
            for i in range(weeks):
                # 准备特征数据
                features = []
                for col in feature_columns:
                    for lag in range(1, 4):  # 使用3周滞后
                        feature_name = f'{col}_lag{lag}'
                        if feature_name in current_data.index:
                            features.append(current_data[feature_name])
                        else:
                            features.append(current_data[col])
                
                # 标准化特征
                features_scaled = self.scaler.transform([features])
                
                # 预测
                prediction = self.model.predict(features_scaled)[0]
                predictions.append(prediction)
                
                # 更新当前数据（简化处理，实际应更新所有指标）
                for col in feature_columns:
                    for lag in range(4, 1, -1):
                        if f'{col}_lag{lag}' in current_data.index:
                            current_data[f'{col}_lag{lag}'] = current_data[f'{col}_lag{lag-1}']
                    current_data[f'{col}_lag1'] = current_data[col]
                current_data['close'] = prediction
        else:
            # 使用基本特征
            print("使用基本特征进行预测")
            # 使用前5个基本特征
            basic_features = ['open', 'high', 'low', 'close', 'volume']
            basic_features = [col for col in basic_features if col in self.data.columns]
            
            # 预测未来几周
            for i in range(weeks):
                # 准备特征数据
                features = [current_data[col] for col in basic_features]
                
                # 标准化特征
                features_scaled = self.scaler.transform([features])
                
                # 预测
                prediction = self.model.predict(features_scaled)[0]
                predictions.append(prediction)
                
                # 更新当前数据
                current_data['close'] = prediction
        
        return predictions
    
    def analyze_current_signals(self):
        """分析当前技术指标信号"""
        print("分析当前技术指标信号...")
        
        # 获取最新数据
        latest = self.data.iloc[-1]
        
        signals = {}
        
        # RSI信号（使用RSI_6更适合周线分析）
        if latest['RSI_6'] < 25:
            signals['RSI'] = '超卖，可能反弹'
        elif latest['RSI_6'] > 65:
            signals['RSI'] = '超买，可能回调'
        else:
            signals['RSI'] = '正常区间'
        
        # MACD信号
        if latest['MACD'] > latest['MACD_signal']:
            signals['MACD'] = '金叉，看涨'
        else:
            signals['MACD'] = '死叉，看跌'
        
        # 布林带信号
        if latest['close'] < latest['BB_lower']:
            signals['布林带'] = '突破下轨，可能反弹'
        elif latest['close'] > latest['BB_upper']:
            signals['布林带'] = '突破上轨，可能回调'
        else:
            signals['布林带'] = '在轨道内，震荡'
        
        # MA交叉信号
        if latest['MA5'] > latest['MA20']:
            signals['MA'] = 'MA5上穿MA20，看涨'
        else:
            signals['MA'] = 'MA5下穿MA20，看跌'
        
        # KDJ信号
        if latest['K'] > latest['D']:
            signals['KDJ'] = 'K上穿D，金叉，看涨'
        else:
            signals['KDJ'] = 'K下穿D，死叉，看跌'
        
        return signals
    
    def generate_trading_advice(self, predictions):
        """生成交易建议"""
        print("生成交易建议...")
        
        # 获取最新数据
        latest = self.data.iloc[-1]
        current_price = latest['close']
        
        # 分析信号
        signals = self.analyze_current_signals()
        
        # 计算预测趋势
        trend = '上涨' if predictions[-1] > current_price else '下跌'
        price_change = ((predictions[-1] - current_price) / current_price) * 100
        
        # 生成建议
        advice = {
            '当前价格': current_price,
            '预测趋势': trend,
            '预测5周后价格': predictions[-1],
            '预测涨幅': price_change,
            '技术指标信号': signals,
            '买入建议': '',
            '卖出建议': ''
        }
        
        # 买入建议
        buy_conditions = [
            signals['RSI'] == '超卖，可能反弹',
            signals['布林带'] == '突破下轨，可能反弹',
            signals['MA'] == 'MA5上穿MA20，看涨',
            signals['MACD'] == '金叉，看涨'
        ]
        
        if sum(buy_conditions) >= 2:
            advice['买入建议'] = f'建议买入，支撑位: {latest["BB_lower"]:.2f}，止损位: {latest["BB_lower"] * 0.98:.2f}'
        else:
            advice['买入建议'] = '暂不建议买入，等待更明确的买入信号'
        
        # 卖出建议
        sell_conditions = [
            signals['RSI'] == '超买，可能回调',
            signals['布林带'] == '突破上轨，可能回调',
            signals['MA'] == 'MA5下穿MA20，看跌',
            signals['MACD'] == '死叉，看跌'
        ]
        
        if sum(sell_conditions) >= 2:
            advice['卖出建议'] = f'建议卖出，压力位: {latest["BB_upper"]:.2f}，止盈位: {latest["BB_upper"] * 1.02:.2f}'
        else:
            advice['卖出建议'] = '暂不建议卖出，持有观望'
        
        return advice
    
    def plot_prediction(self, predictions):
        """绘制预测结果"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        # 准备数据
        historical_dates = self.data['date']
        historical_prices = self.data['close']
        
        # 生成未来日期
        last_date = historical_dates.iloc[-1]
        future_dates = [last_date + timedelta(weeks=i+1) for i in range(len(predictions))]
        
        # 绘制图表
        plt.figure(figsize=(15, 8))
        
        # 绘制历史价格
        plt.plot(historical_dates, historical_prices, label='历史价格', color='blue')
        
        # 绘制预测价格
        plt.plot(future_dates, predictions, label='预测价格', color='red', linestyle='--', marker='o')
        
        # 绘制当前价格
        plt.scatter([last_date], [historical_prices.iloc[-1]], color='green', s=100, label='当前价格')
        
        plt.title(f'{self.ticker} 周线股价预测')
        plt.xlabel('日期')
        plt.ylabel('价格')
        plt.legend()
        plt.grid(True)
        
        # 保存图表
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_weekly_prediction.png')
        plt.savefig(chart_path)
        print(f"周线预测图表已保存为: {chart_path}")
    
    def run_prediction(self):
        """运行完整的预测"""
        self.load_data()
        X, y = self.prepare_features()
        self.train_model(X, y)
        predictions = self.predict_future(weeks=5)
        advice = self.generate_trading_advice(predictions)
        self.plot_prediction(predictions)
        
        return predictions, advice

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="基于周线历史数据，预测股票未来价格并生成交易建议")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认使用config.py中的配置")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
        ticker_name = ticker
    else:
        # 使用第一个股票代码进行预测
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_weekly_data.csv'
    print(f"分析股票: {ticker}")
    
    # 运行预测
    predictor = WeeklyStockPredictor(file_path)
    predictions, advice = predictor.run_prediction()
    
    # 打印结果
    print(f"\n=== {ticker} 周线预测与建议 ===")
    print(f"当前日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"当前价格: {advice['当前价格']:.2f}")
    print(f"预测趋势: {advice['预测趋势']}")
    print(f"预测5周后价格: {advice['预测5周后价格']:.2f}")
    print(f"预测涨幅: {advice['预测涨幅']:.2f}%")
    
    print("\n技术指标信号:")
    for indicator, signal in advice['技术指标信号'].items():
        print(f"  {indicator}: {signal}")
    
    print("\n交易建议:")
    print(f"  买入建议: {advice['买入建议']}")
    print(f"  卖出建议: {advice['卖出建议']}")
    
    print("\n预测价格走势:")
    for i, (price, date) in enumerate(zip(predictions, [datetime.now() + timedelta(weeks=i+1) for i in range(5)])):
        print(f"  {date.strftime('%Y-%m-%d')}: {price:.2f}")