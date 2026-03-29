import akshare as ak
import pandas as pd
import random
import time

# 打印akshare版本
try:
    df = ak.stock_zh_a_daily(symbol="SH600313", start_date="20250101", end_date="20250316")
    print(df.empty)           # 是否为空
    if not df.empty:
        # 重命名列名，统一格式
        print(df.head())          # 查看前几行
        print(df.columns)
except Exception as e:
    print(f"获取数据时出错: {str(e)}")


# stock_zh_a_hist_tx_df = ak.stock_zh_a_hist_tx(symbol="sz000001", start_date="20260101", end_date="20260316", adjust="")
# print(stock_zh_a_hist_tx_df)


if not df.empty:
    # 重命名列名，统一格式
    df = df.rename(columns={
        '日期': 'date',
        '股票代码': '股票代码',
        '开盘': 'open',
        '最高': 'high',
        '最低': 'low',
        '收盘': 'close',
        '成交量': 'volume',
        '成交额': '成交额',
        '振幅': '振幅',
        '涨跌幅': '涨跌幅',
        '涨跌额': '涨跌额',
        '换手率': '换手率'
    })
    data = df.sort_values('date', ascending=True)
    df = pd.DataFrame(data)
    df.to_csv("data/600313.SH.csv", index=False, header=False, encoding='utf-8-sig')

