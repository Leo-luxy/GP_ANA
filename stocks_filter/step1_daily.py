"""
step1_daily.py
功能：调用 Tushare pro.daily()，获取全市场日线行情，保存为临时 CSV
运行时机：收盘后（15:30 之后）
注意：运行后请等待至少 1 小时，再运行 step2_daily_basic.py
"""

import tushare as ts
import akshare as ak
import pandas as pd
import datetime
import os

# ==================== 配置 ====================
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"          # 替换为真实 token
OUTPUT_TEMP = "stocks_daily_temp.csv"       # 临时文件
# =============================================

pro = ts.pro_api(TUSHARE_TOKEN)

def get_latest_trade_date():
    """自动获取最近一个交易日"""
    today = datetime.date.today()
    for i in range(10):
        test_date = (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        try:
            df_test = ak.stock_zh_a_daily(symbol="sz000001", start_date=test_date, end_date=test_date, adjust="qfq")
            if not df_test.empty:
                return test_date
        except:
            continue
    raise RuntimeError("找不到最近交易日，请手动指定日期")

trade_date = get_latest_trade_date()
print(f"交易日：{trade_date}")

# 当前文件位于 stocks_filter 文件夹中，直接使用当前目录
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

# 获取日线行情
fields = ("ts_code,trade_date,open,high,low,close,pre_close,"
          "change,pct_chg,vol,amount")
print("正在获取 daily 数据...")

df_daily = None
try:
    df_daily = pro.daily(trade_date=trade_date, fields=fields)
    print(f"获取到 {len(df_daily)} 条行情记录")
except Exception as e:
    error_msg = str(e)
    print(f"获取 daily 数据失败: {error_msg}")
    
    # 检查是否是频率限制
    if "频率超限" in error_msg or "limit" in error_msg.lower():
        print("检测到 Tushare 访问频率限制，尝试读取历史数据...")
        
        # 尝试读取已有的临时文件
        output_path = os.path.join(SAVE_DIR, OUTPUT_TEMP)
        if os.path.exists(output_path):
            df_daily = pd.read_csv(output_path)
            print(f"成功读取历史数据，共 {len(df_daily)} 条记录")
        else:
            print("未找到历史数据文件，程序将继续执行")

if df_daily is not None and not df_daily.empty:
    # 构建完整的保存路径
    output_path = os.path.join(SAVE_DIR, OUTPUT_TEMP)
    
    # 保存临时 CSV（不在此处改列名，合并后再统一）
    df_daily.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"临时文件已保存至：{output_path}")
    print("请等待 1 小时后运行 step2_daily_basic.py 完成数据合并。")
else:
    print("未能获取或读取数据，但程序将继续执行")
