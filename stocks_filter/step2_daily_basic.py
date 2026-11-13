"""
step2_daily_basic.py
功能：读取 step1 保存的临时行情 CSV，调用 Tushare pro.daily_basic()
      获取换手率、市值等指标，合并后保存为最终中文列名 CSV
运行时机：step1 之后直接运行（读取 temp 中的 trade_date，抓取同一天的基础指标）

取数失败时以非 0 退出码结束（旧版本用 exit(0)，导致调用方以为这步成功了）。
"""

import os
import sys
import datetime

import pandas as pd

# 网络代理守护：默认直连、不使用系统代理，必须在联网请求之前导入
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from net_guard import ensure_network_ready, retry_on_proxy_error

ensure_network_ready()

# ==================== 配置 ====================
# token 统一在项目根 tushare_client.py 配置（主 token + 备用 token，限流自动切换）
INPUT_TEMP = "stocks_daily_temp.csv"            # step1 生成的临时文件
OUTPUT_FINAL = "stocks_daily_full.csv"    # 最终输出文件
# =============================================

# 当前文件位于 stocks_filter 文件夹中，直接使用当前目录
STOCKS_FILTER_DIR = os.path.dirname(os.path.abspath(__file__))

from tushare_client import TusharePool, is_rate_limit  # noqa: E402

pro = TusharePool()

OUTPUT_PATH = os.path.join(STOCKS_FILTER_DIR, OUTPUT_FINAL)


def _cached_date():
    """只读缓存里已合并数据的交易日期，用于给出可操作的重跑建议。"""
    if not os.path.exists(OUTPUT_PATH):
        return None
    try:
        df = pd.read_csv(OUTPUT_PATH, usecols=['交易日期'], dtype=str)
    except Exception:
        return None
    dates = {str(v) for v in df['交易日期'].dropna().unique()}
    return dates.pop() if len(dates) == 1 else None


def load_cached_same_date(trade_date, df_daily):
    """
    加载已有的完整数据，但**只在与本次交易日完全相同**时才返回。

    频率受限时复用同一个交易日的缓存，与重新获取完全等价，不会引入旧数据；
    日期不同则返回 None —— 绝不拿别的交易日的数据顶替。
    """
    if not os.path.exists(OUTPUT_PATH):
        return None
    try:
        df = pd.read_csv(OUTPUT_PATH)
    except Exception:
        return None
    if df.empty or '交易日期' not in df.columns or '股票代码' not in df.columns:
        return None

    cached_dates = {str(v) for v in df['交易日期'].dropna().unique()}
    if cached_dates != {trade_date}:
        return None

    # 覆盖率校验：必须覆盖本次全部行情股票，不能以部分发布冒充全量。
    missing = set(df_daily['ts_code']) - set(df['股票代码'])
    if missing or df['股票代码'].duplicated().any():
        return None
    return df


# 1. 读取 step1 的行情数据
input_path = os.path.join(STOCKS_FILTER_DIR, INPUT_TEMP)
print(f"读取临时文件：{input_path}")

if not os.path.exists(input_path):
    print(f"错误：未找到临时文件 {input_path}，请先成功运行 step1_daily.py")
    sys.exit(2)

df_daily = pd.read_csv(input_path)
# 从 CSV 读回的 trade_date 是整数，必须与接口返回的字符串统一，否则 merge 会类型冲突。
df_daily['trade_date'] = df_daily['trade_date'].astype(str)
# 北交所不参与选股，也不以其基础指标缺失阻塞沪深整批日期判定。
df_daily = df_daily[~df_daily['ts_code'].astype(str).str.endswith('.BJ')].copy()
if df_daily.empty:
    print("错误：临时文件为空，请先成功运行 step1_daily.py")
    sys.exit(2)

# 获取数据日期（取 trade_date 的第一条）
trade_date = str(df_daily['trade_date'].iloc[0])
if set(df_daily['trade_date'].astype(str)) != {trade_date} or df_daily['ts_code'].duplicated().any():
    print('初筛行情日期混杂或代码重复，禁止合并')
    sys.exit(2)
print(f"数据日期：{trade_date}")

# 2. 获取 daily_basic 数据
fields = ("ts_code,trade_date,turnover_rate,turnover_rate_f,volume_ratio,"
          "pe,pe_ttm,pb,ps,ps_ttm,dv_ratio,dv_ttm,"
          "total_share,float_share,free_share,total_mv,circ_mv")
print("正在获取 daily_basic 数据...")

try:
    df_basic = retry_on_proxy_error(pro.daily_basic, trade_date=trade_date, fields=fields)
    df_basic['trade_date'] = df_basic['trade_date'].astype(str)
    print(f"获取到 {len(df_basic)} 条基础指标记录")
except Exception as e:
    # 频率受限时，允许复用「同一个交易日」的完整数据（与重新获取等价），
    # 但日期不同一律中止 —— 绝不拿别的交易日的数据顶替。
    if is_rate_limit(e):
        cached = load_cached_same_date(trade_date, df_daily)
        if cached is not None:
            print(f"提示：Tushare 接口频次受限，但已有的完整数据正是交易日 {trade_date}，直接复用（与重新获取等价），不影响本次结果。")
            print(f"      完整数据已就绪：{OUTPUT_PATH}")
            sys.exit(0)
        cached_date = _cached_date()
        print(f"提示：Tushare 接口频次受限，且现有完整数据（{cached_date or '无'}）不是本轮交易日 {trade_date}，本次已中止。")
        print(f"      接口返回：{e}")
        if cached_date and cached_date > trade_date:
            print(f"      行情比已有的完整数据旧：请重跑 step1_daily.py 取到 {cached_date} 后，再跑 step2。")
        print("      请等待额度恢复后重试（daily_basic 免费额度很小，常见为每分钟 1 次）。")
        sys.exit(2)

    print(f"获取 daily_basic 数据失败: {e}")
    print("本步骤未取得数据，已中止，避免用旧数据继续筛选。")
    sys.exit(2)

if df_basic is None or df_basic.empty:
    print(f"交易日 {trade_date} 未取到 daily_basic 数据，已中止，避免用旧数据继续筛选。")
    print("      数据请求成功但基础指标尚未发布，需整批回退而非混用日期。")
    sys.exit(4)

# 3. 合并（按 ts_code）
if set(df_basic['trade_date'].astype(str)) != {trade_date} or df_basic['ts_code'].duplicated().any():
    print('基础指标响应日期不一致或代码重复，禁止发布')
    sys.exit(2)
missing = set(df_daily['ts_code']) - set(df_basic['ts_code'])
if missing:
    print(f'基础指标未齐：{len(missing)} 只缺失，需整批回退，禁止静默缩小初筛全集')
    sys.exit(4)
df_full = pd.merge(df_daily, df_basic, on=['ts_code', 'trade_date'], how='inner', validate='one_to_one')
print(f"合并后共 {len(df_full)} 条记录")

if df_full.empty:
    print("错误：合并后为空，行情与基础指标日期可能不一致。")
    sys.exit(2)

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
