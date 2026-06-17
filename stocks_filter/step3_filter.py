"""
step3_filter.py
功能：读取合并后的全市场数据，执行第一步筛选，结果保存为 CSV
使用：修改下方文件名和参数后直接运行
"""

import pandas as pd
import os

# ==================== 配置 ====================
INPUT_FILE = "stocks_daily_full.csv"      # 上一步合并的完整数据
OUTPUT_FILE = "stocks_daily_filtered.csv"       # 筛选结果保存文件
# =============================================

# 当前文件位于 stocks_filter 文件夹中，直接使用当前目录
STOCKS_FILTER_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. 读取数据
input_path = os.path.join(STOCKS_FILTER_DIR, INPUT_FILE)
df = pd.read_csv(input_path)
print(f"原始数据 {len(df)} 行")

# 2. 数值列二次确认（防止意外字符串）
numeric_cols = [
    "收盘价", "最高价", "最低价", "前收盘价",
    "成交额(千元)", "换手率(%)", "总市值(万元)", "涨跌幅(%)"
]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors='coerce')

# 3. 计算振幅（以昨收为基准更合理）
df['振幅'] = (df['最高价'] - df['最低价']) / df['前收盘价'] * 100

# 4. 筛选条件（均衡型参数，可根据需要调整）
qualified = df.copy()
print(f"初始股票数量: {len(qualified)}")

qualified = qualified[qualified['收盘价'] >= 3].copy()
print(f"条件1 - 收盘价 >= 6元: {len(qualified)}")

qualified = qualified[qualified['成交额(千元)'] >= 150000].copy()  # 1.5 亿元
print(f"条件2 - 成交额 >= 1.5亿元: {len(qualified)}")

qualified = qualified[qualified['换手率(%)'].between(2, 10)].copy()  # 换手率 2% ~ 10%
print(f"条件3 - 换手率 2%~10%: {len(qualified)}")

qualified = qualified[qualified['总市值(万元)'] >= 800000].copy()  # 总市值 >= 80 亿
print(f"条件4 - 总市值 >= 80亿: {len(qualified)}")

qualified = qualified[qualified['振幅'] >= 3.5].copy()
print(f"条件5 - 振幅 >= 3.5%: {len(qualified)}")

qualified = qualified[qualified['涨跌幅(%)'] > 0].copy()  # 当日收涨
print(f"条件6 - 当日收涨: {len(qualified)}")

print(f"\n最终筛选后 {len(qualified)} 只股票")

# 5. 保存到 CSV
output_path = os.path.join(STOCKS_FILTER_DIR, OUTPUT_FILE)
qualified.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"结果已保存至 {output_path}")