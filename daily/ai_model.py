# ai_model.py
# 功能：使用机器学习模型对股票价格进行预测和分析
# 实现原理：
# 1. 加载股票历史数据，包括价格和技术指标
# 2. 准备特征数据，包括滞后特征和技术指标
# 3. 训练多个机器学习模型（线性回归、随机森林、梯度提升）
# 4. 评估模型性能，计算MSE、RMSE和R²指标
# 5. 绘制预测结果和真实值的对比图表
# 6. 分析特征重要性，识别对预测最有影响的因素

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import os
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
from datetime import datetime
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import DATA_DIR, TECHNICAL_INDICATORS

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # 用于macOS的中文字体
plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号

class AIPredictor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.data = None
        self.ticker = None
        self.models = {}
        self.scaler = None
    
    def load_data(self):
        """加载数据"""
        print(f"加载数据文件: {self.file_path}")
        self.data = pd.read_csv(self.file_path)
        
        # 转换日期格式
        if 'date' in self.data.columns:
            self.data['date'] = pd.to_datetime(self.data['date'])
        
        # 获取股票代码
        if 'ticker' in self.data.columns:
            self.ticker = self.data['ticker'].iloc[0]
        
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
                         'ATR', 'RSI', 'CCI', 'ROC', 'OBV',
                         'VWAP', 'Volatility', 'BIAS5', 'BIAS10', 'WR', 'DMA']
        
        # 确保所有特征列都存在
        feature_columns = [col for col in feature_columns if col in self.data.columns]
        
        # 创建滞后特征
        lag_features = []
        for col in feature_columns:
            for i in range(1, lookback + 1):
                lag_feature = self.data[col].shift(i).rename(f'{col}_lag{i}')
                lag_features.append(lag_feature)
        
        # 一次性添加所有滞后特征
        if lag_features:
            lag_features_df = pd.concat(lag_features, axis=1)
            self.data = pd.concat([self.data, lag_features_df], axis=1)
        
        # 创建目标变量（下一天的收盘价）
        self.data['target'] = self.data['close'].shift(-1)
        
        # 移除含有NaN的行
        self.data = self.data.dropna()
        
        # 分离特征和目标变量
        feature_cols = [col for col in self.data.columns if 'lag' in col]
        X = self.data[feature_cols]
        y = self.data['target']
        
        return X, y
    
    def train_models(self, X, y):
        """训练多个机器学习模型"""
        print("\n=== 训练机器学习模型 ===")
        
        # 划分训练集和测试集
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        
        # 特征标准化
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # 训练线性回归模型
        print("训练线性回归模型...")
        lr_model = LinearRegression()
        lr_model.fit(X_train_scaled, y_train)
        self.models['LinearRegression'] = lr_model
        
        # 训练随机森林模型
        print("训练随机森林模型...")
        rf_model = RandomForestRegressor(n_estimators=100, random_state=42)
        rf_model.fit(X_train_scaled, y_train)
        self.models['RandomForest'] = rf_model
        
        # 训练梯度提升模型
        print("训练梯度提升模型...")
        gb_model = GradientBoostingRegressor(n_estimators=100, random_state=42)
        gb_model.fit(X_train_scaled, y_train)
        self.models['GradientBoosting'] = gb_model
        
        return X_train, X_test, y_train, y_test
    
    def evaluate_models(self, X_test, y_test):
        """评估模型性能"""
        print("\n=== 模型性能评估 ===")
        
        results = {}
        
        for model_name, model in self.models.items():
            # 预测
            X_test_scaled = self.scaler.transform(X_test)
            y_pred = model.predict(X_test_scaled)
            
            # 计算评估指标
            mse = mean_squared_error(y_test, y_pred)
            rmse = np.sqrt(mse)
            r2 = r2_score(y_test, y_pred)
            
            results[model_name] = {
                'MSE': mse,
                'RMSE': rmse,
                'R2': r2
            }
            
            print(f"{model_name}:")
            print(f"  MSE: {mse:.4f}")
            print(f"  RMSE: {rmse:.4f}")
            print(f"  R²: {r2:.4f}")
        
        return results
    
    def plot_predictions(self, X_test, y_test):
        """绘制预测结果"""
        # 确保数据目录存在
        stock_dir = os.path.join(DATA_DIR, self.ticker)
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        
        plt.figure(figsize=(15, 10))
        
        # 获取测试集的日期（使用X_test的索引直接访问）
        test_dates = self.data.loc[X_test.index, 'date']
        
        # 绘制真实值
        plt.plot(test_dates, y_test, label='真实收盘价', color='blue')
        
        # 绘制各模型的预测值
        colors = ['red', 'green', 'purple']
        for i, (model_name, model) in enumerate(self.models.items()):
            X_test_scaled = self.scaler.transform(X_test)
            y_pred = model.predict(X_test_scaled)
            plt.plot(test_dates, y_pred, label=f'{model_name}预测', color=colors[i], linestyle='--')
        
        plt.title(f'{self.ticker} 股价预测结果')
        plt.xlabel('日期')
        plt.ylabel('收盘价')
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        chart_path = os.path.join(stock_dir, f'{self.ticker}_ai_predictions.png')
        plt.savefig(chart_path)
        print(f"预测结果图表已保存为: {chart_path}")
    
    def feature_importance(self, X_train):
        """分析特征重要性"""
        if 'RandomForest' in self.models:
            # 确保数据目录存在
            stock_dir = os.path.join(DATA_DIR, self.ticker)
            if not os.path.exists(DATA_DIR):
                os.makedirs(DATA_DIR)
            if not os.path.exists(stock_dir):
                os.makedirs(stock_dir)
            
            print("\n=== 特征重要性分析 ===")
            
            # 获取随机森林模型的特征重要性
            importances = self.models['RandomForest'].feature_importances_
            feature_names = X_train.columns
            
            # 排序
            indices = np.argsort(importances)[::-1]
            
            # 打印前20个重要特征
            print("前20个重要特征:")
            for i in range(min(20, len(indices))):
                print(f"{feature_names[indices[i]]}: {importances[indices[i]]:.4f}")
            
            # 绘制特征重要性
            plt.figure(figsize=(12, 8))
            plt.title('特征重要性')
            plt.bar(range(min(20, len(indices))), importances[indices[:20]], align='center')
            plt.xticks(range(min(20, len(indices))), [feature_names[i] for i in indices[:20]], rotation=90)
            plt.tight_layout()
            chart_path = os.path.join(stock_dir, f'{self.ticker}_feature_importance.png')
            plt.savefig(chart_path)
            print(f"特征重要性图表已保存为: {chart_path}")
    
    def run_ai_analysis(self):
        """运行完整的AI分析"""
        self.load_data()
        X, y = self.prepare_features()
        X_train, X_test, y_train, y_test = self.train_models(X, y)
        results = self.evaluate_models(X_test, y_test)
        self.plot_predictions(X_test, y_test)
        self.feature_importance(X_train)
        print("\n=== AI模型分析完成 ===")
        return results

if __name__ == "__main__":
    import argparse
    
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="使用机器学习模型对股票价格进行预测和分析")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SS（上交所）、000001.SZ（深交所），默认使用config.py中的配置")
    args = parser.parse_args()
    
    # 从配置文件中获取股票代码
    from config import STOCK_TICKERS
    
    # 确定股票代码
    if args.ticker:
        ticker = args.ticker
        ticker_name = ticker
    else:
        # 使用第一个股票代码进行分析
        ticker_name, ticker = next(iter(STOCK_TICKERS.items()))
        print(f"使用配置文件中的股票代码: {ticker} ({ticker_name})")
    
    file_path = f'{DATA_DIR}/{ticker}/{ticker}_indicators.csv'
    print(f"分析股票: {ticker}")
    
    # 运行AI模型分析
    predictor = AIPredictor(file_path)
    results = predictor.run_ai_analysis()
