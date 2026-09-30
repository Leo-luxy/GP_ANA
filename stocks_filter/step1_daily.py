"""
step1_daily.py
功能：调用 Tushare pro.daily()，获取全市场日线行情，保存为临时 CSV
运行时机：收盘后（15:30 之后）
注意：运行后请等待至少 1 小时，再运行 step2_daily_basic.py

取数失败时以非 0 退出码结束，调用方（web 选股任务）必须停下，
不能拿上一次的旧数据继续筛选。
"""

import os
import sys
import datetime

import tushare as ts
import akshare as ak

# 网络代理守护：默认直连、不使用系统代理，必须在联网请求之前导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from net_guard import ensure_network_ready, retry_on_proxy_error, is_proxy_error

ensure_network_ready()

# ==================== 配置 ====================
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"          # 替换为真实 token
OUTPUT_TEMP = "stocks_daily_temp.csv"       # 临时文件
# =============================================

pro = ts.pro_api(TUSHARE_TOKEN)


def get_latest_trade_date():
    """
    自动获取最近一个「行情已经发布」的交易日。

    先用 Tushare 交易日历确定候选交易日，再逐日探测是否已有数据；
    交易日历不可用时退回 akshare 探测。

    与旧实现的区别：网络/代理故障会直接抛异常，不会 `except: continue`
    静默退回到更早的日期（那正是「抓到昨天数据」的根源）。
    """
    today = datetime.date.today()
    start = (today - datetime.timedelta(days=20)).strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")

    candidates = []
    try:
        cal = retry_on_proxy_error(
            pro.trade_cal, exchange="SSE", start_date=start, end_date=end,
            is_open="1", fields="cal_date",
        )
        candidates = sorted(cal["cal_date"].tolist(), reverse=True)
    except Exception as e:
        if is_proxy_error(e):
            raise
        print(f"交易日历获取失败（{e}），改用行情探测")

    if candidates:
        for d in candidates:
            df = retry_on_proxy_error(pro.daily, trade_date=d, fields="ts_code")
            if df is not None and not df.empty:
                return d
        raise RuntimeError(
            f"最近 20 天的交易日（{start}~{end}）都没有取到行情数据，请检查网络/Tushare 权限"
        )

    # 兜底：逐日探测 akshare（交易日历接口不可用时启用）
    last_error = None
    for i in range(10):
        test_date = (today - datetime.timedelta(days=i)).strftime("%Y%m%d")
        try:
            df_test = retry_on_proxy_error(
                ak.stock_zh_a_daily,
                symbol="sz000001", start_date=test_date, end_date=test_date, adjust="qfq",
            )
            if not df_test.empty:
                return test_date
        except Exception as e:
            if is_proxy_error(e):
                raise
            last_error = e
            continue
    raise RuntimeError(f"找不到最近交易日，请检查网络后重试（最后错误：{last_error}）")


trade_date = get_latest_trade_date()
print(f"交易日：{trade_date}")

# 当前文件位于 stocks_filter 文件夹中，直接使用当前目录
SAVE_DIR = os.path.dirname(os.path.abspath(__file__))

# 获取日线行情
fields = ("ts_code,trade_date,open,high,low,close,pre_close,"
          "change,pct_chg,vol,amount")
print("正在获取 daily 数据...")

try:
    df_daily = retry_on_proxy_error(pro.daily, trade_date=trade_date, fields=fields)
    print(f"获取到 {len(df_daily)} 条行情记录")
except Exception as e:
    print(f"获取 daily 数据失败: {e}")
    print("本步骤未取得数据，已中止，避免用旧数据继续筛选。")
    sys.exit(2)

if df_daily is None or df_daily.empty:
    print(f"交易日 {trade_date} 未取到行情数据，已中止，避免用旧数据继续筛选。")
    sys.exit(2)

# 构建完整的保存路径
output_path = os.path.join(SAVE_DIR, OUTPUT_TEMP)

# 保存临时 CSV（不在此处改列名，合并后再统一）
df_daily.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"临时文件已保存至：{output_path}")
print("请等待 1 小时后运行 step2_daily_basic.py 完成数据合并。")
