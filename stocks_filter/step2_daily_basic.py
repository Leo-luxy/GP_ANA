"""
step2_daily_basic.py
功能：读取 step1 保存的临时行情 CSV，调用 Tushare pro.daily_basic()
      获取换手率、市值等指标，合并后保存为最终中文列名 CSV
运行时机：step1 运行完至少 1 小时后
"""

import tushare as ts
import pandas as pd
import datetime
import os

# ==================== 配置 ====================
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"              # 替换为真实 token
INPUT_TEMP = "stocks_daily_temp.csv"            # step1 生成的临时文件
OUTPUT_FINAL = "stocks_daily_full.csv"    # 最终输出文件
# =============================================

# 当前文件位于 stocks_filter 文件夹中，直接使用当前目录
STOCKS_FILTER_DIR = os.path.dirname(os.path.abspath(__file__))

pro = ts.pro_api(TUSHARE_TOKEN)

# 1. 读取 step1 的行情数据
input_path = os.path.join(STOCKS_FILTER_DIR, INPUT_TEMP)
print(f"读取临时文件：{input_path}")

if not os.path.exists(input_path):
    print(f"错误：未找到临时文件 {input_path}")
    print("程序将继续执行")
    exit(0)

df_daily = pd.read_csv(input_path)
if df_daily.empty:
    print("错误：临时文件为空，请确认 step1 是否成功运行。")
    print("程序将继续执行")
    exit(0)

# 获取数据日期（取 trade_date 的第一条）
trade_date = str(df_daily['trade_date'].iloc[0])
print(f"数据日期：{trade_date}")

# 2. 获取 daily_basic 数据
fields = ("ts_code,turnover_rate,turnover_rate_f,volume_ratio,"
          "pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,"
          "total_share,float_share,free_share,total_mv,circ_mv")
print("正在获取 daily_basic 数据...")

df_basic = None
try:
    df_basic = pro.daily_basic(trade_date=trade_date, fields=fields)
    print(f"获取到 {len(df_basic)} 条基础指标记录")
except Exception as e:
    error_msg = str(e)
    print(f"获取 daily_basic 数据失败: {error_msg}")
    
    # 检查是否是频率限制
    if "频率超限" in error_msg or "limit" in error_msg.lower():
        print("检测到 Tushare 访问频率限制，尝试读取历史数据...")
        
        # 尝试读取已有的完整数据文件
        output_path = os.path.join(STOCKS_FILTER_DIR, OUTPUT_FINAL)
        if os.path.exists(output_path):
            df_full = pd.read_csv(output_path)
            print(f"成功读取历史完整数据，共 {len(df_full)} 条记录")
            print(f"数据已保存至：{output_path}")
            # print("接下来所有筛选测试请直接读取该 CSV，无需再调用 Tushare API。")
            exit(0)
        else:
            print("未找到历史完整数据文件，程序将继续执行")
    else:
        print("程序将继续执行")

if df_basic is None or df_basic.empty:
    print("未能获取或读取 daily_basic 数据，但程序将继续执行")
    exit(0)

# 3. 合并（按 ts_code）
df_full = pd.merge(df_daily, df_basic, on='ts_code', how='inner')
print(f"合并后共 {len(df_full)} 条记录")

# 4. 列名中英文映射
COLUMN_MAP = {
    "ts_code": "股票代码",
    "trade_date": "交易日期",
    "open": "开盘价",
    "high": "最高价",
    "low": "最低价",
    "close": "收盘价",
    "pre_close": "前收盘价",
    "change": "涨跌额",
    "pct_chg": "涨跌幅(%)",
    "vol": "成交量(手)",
    "amount": "成交额(千元)",
    "turnover_rate": "换手率(%)",
    "turnover_rate_f": "自由流通换手率(%)",
    "volume_ratio": "量比",
    "pe": "市盈率(静态)",
    "pe_ttm": "市盈率(TTM)",
    "pb": "市净率",
    "ps": "市销率(静态)",
    "ps_ttm": "市销率(TTM)",
    "dv_ratio": "股息率(静态,%)",
    "dv_ttm": "股息率(TTM,%)",
    "total_share": "总股本(万股)",
    "float_share": "流通股本(万股)",
    "free_share": "自由流通股本(万股)",
    "total_mv": "总市值(万元)",
    "circ_mv": "流通市值(万元)",
}
# 只映射存在的列
existing = {k: v for k, v in COLUMN_MAP.items() if k in df_full.columns}
df_full.rename(columns=existing, inplace=True)

# 5. 数值列类型转换（防止字符串干扰筛选）
numeric_cols = [
    "收盘价", "最高价", "最低价", "开盘价", "前收盘价",
    "成交量(手)", "成交额(千元)", "换手率(%)", "量比",
    "总市值(万元)", "流通市值(万元)", "涨跌幅(%)"
]
for col in numeric_cols:
    if col in df_full.columns:
        df_full[col] = pd.to_numeric(df_full[col], errors='coerce')

# 6. 保存最终 CSV
output_path = os.path.join(STOCKS_FILTER_DIR, OUTPUT_FINAL)
df_full.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"完整数据已保存至：{output_path}")
print("接下来所有筛选测试请直接读取该 CSV，无需再调用 Tushare API。")
