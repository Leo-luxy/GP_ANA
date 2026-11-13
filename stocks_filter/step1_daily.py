"""
step1_daily.py
功能：调用 Tushare pro.daily()，获取全市场日线行情，保存为临时 CSV
运行时机：收盘后（15:30 之后）
说明：step2_daily_basic.py 抓取的是同一个交易日的基础指标，本步骤跑完可直接接着运行；
      若该日 daily_basic 尚未发布，稍后重跑 step2 即可（无需刻意等待）。

取数失败时以非 0 退出码结束，调用方（web 选股任务）必须停下，
不能拿上一次的旧数据继续筛选。
"""

import os
import sys
import datetime
import argparse
import time


# 网络代理守护：默认直连、不使用系统代理，必须在联网请求之前导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from net_guard import ensure_network_ready, retry_on_proxy_error, is_proxy_error

ensure_network_ready()

# ==================== 配置 ====================
# token 统一在项目根 tushare_client.py 配置（主 token + 备用 token，限流自动切换）
OUTPUT_TEMP = "stocks_daily_temp.csv"       # 临时文件
# =============================================

parser = argparse.ArgumentParser(description='全市场单交易日行情初筛')
parser.add_argument('--trade-date', help='冻结交易日 YYYYMMDD，用于整批日期回退重建')
args = parser.parse_args()

from tushare_client import TusharePool  # noqa: E402  (需在 sys.path 补充项目根之后导入)

pro = TusharePool()


def _weekday_candidates(today, days=12):
    """交易日历不可用时的候选：按工作日倒推，节假日由行情探测自然跳过。"""
    values = []
    cursor = today
    while len(values) < days:
        if cursor.weekday() < 5:
            values.append(cursor.strftime('%Y%m%d'))
        cursor -= datetime.timedelta(days=1)
    return values


def get_latest_trade_date():
    """
    自动获取最近一个「行情已经发布」的交易日。

    先用 Tushare 交易日历确定候选交易日，再逐日探测是否已有数据；
    交易日历不可用时按工作日生成候选，仍用 Tushare 行情探测（与真正取数同一接口）。

    与旧实现的区别：网络/代理故障会直接抛异常，不会 `except: continue`
    静默退回到更早的日期（那正是「抓到昨天数据」的根源）。
    """
    from check_data_updates import get_calendar_trade_date
    today = get_calendar_trade_date()
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
        print("提示：交易日历接口暂时不可用（Tushare 有频次限制），改用行情探测确定交易日，不影响本次结果。")
        print(f"      接口返回：{e}")

    if not candidates:
        # 交易日历取不到时，用工作日生成候选，仍然走 Tushare 行情探测：
        # 探测接口就是真正取数接口，探测成功即代表能取到，不会像 akshare 那样滞后一天。
        print("提示：交易日历不可用，改用工作日候选 + Tushare 行情探测确定交易日。")
        candidates = _weekday_candidates(today)

    if candidates:
        for index, d in enumerate(candidates):
            # 最新候选多试一次：接口偶发返回空，不能因此悄悄退回旧交易日。
            for attempt in range(2 if index == 0 else 1):
                df = retry_on_proxy_error(pro.daily, trade_date=d, fields="ts_code")
                if df is not None and not df.empty:
                    return d
                if attempt == 0:
                    print(f"提示：{d} 行情首次返回为空，2 秒后重试一次")
                    time.sleep(2)
        raise RuntimeError(
            f"最近 20 天的交易日（{start}~{end}）都没有取到行情数据，请检查网络/Tushare 权限"
        )

    raise RuntimeError("找不到最近交易日，请检查网络/Tushare 权限后重试")


try:
    trade_date = args.trade_date or get_latest_trade_date()
    datetime.datetime.strptime(trade_date, '%Y%m%d')
    from check_data_updates import get_calendar_trade_date
    expected_date = get_calendar_trade_date().strftime('%Y%m%d')
    if trade_date < expected_date:
        print(f"⚠️ 警告：本次使用 {trade_date} 行情，比当前期望交易日 {expected_date} 旧；"
              f"可能是当日行情尚未发布或接口瞬时失败，如需当日数据请稍后重跑。")
except Exception as e:
    print(f"确定最近交易日失败: {e}")
    print("本步骤未取得数据，已中止，避免用旧数据继续筛选。")
    sys.exit(2)
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

if trade_date == datetime.date.today().strftime('%Y%m%d'):
    from selection_snapshot import (evaluate_market_gap, previous_trade_asof,
                                    missing_market_codes)
    previous_day = previous_trade_asof(trade_date)
    try:
        baseline = retry_on_proxy_error(pro.daily, trade_date=previous_day, fields=fields)
    except Exception as exc:
        print(f'全市场覆盖核验取数失败，停止而非伪装未齐：{exc}')
        sys.exit(2)
    if baseline is None or baseline.empty or set(baseline['trade_date'].astype(str)) != {previous_day}:
        print('无法证明上一交易日全市场覆盖，停止初筛')
        sys.exit(2)
    missing = missing_market_codes(df_daily, baseline)
    accept_today, gap_reason = evaluate_market_gap(missing, len(baseline))
    print(f'全市场覆盖核验：{gap_reason}')
    if not accept_today:
        if args.trade_date:
            sys.exit(4)  # 调用方将整套初筛和详细回测统一回退。
        print(f'整批回退到 {previous_day}')
        trade_date, df_daily = previous_day, baseline

if set(df_daily['trade_date'].astype(str)) != {trade_date} or df_daily['ts_code'].duplicated().any():
    print('行情响应日期不一致或代码重复，禁止发布混合日期初筛')
    sys.exit(2)

# 构建完整的保存路径
output_path = os.path.join(SAVE_DIR, OUTPUT_TEMP)

# 保存临时 CSV（不在此处改列名，合并后再统一）
df_daily.to_csv(output_path, index=False, encoding="utf-8-sig")
print(f"临时文件已保存至：{output_path}")
print("step1 完成。可直接运行 step2_daily_basic.py 完成数据合并。")
