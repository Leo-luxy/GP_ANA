# check_data_updates.py
# 统一的数据更新检查入口
# --mode daily:    检查日更数据（qfq, fund_flow, margin_data, indicators, shareholder_num）
# --mode periodic: 检查低频数据（company_basic, financial_indicators, dupont, shareholder,
#                  ex_dividend, institutional, north_holdings）
# --mode all:      检查全部
#
# 判定规则（本轮收紧后的硬性规则）：
#   1. 一律读「内容日期」判定新鲜度（qfq 的最后一行日期、CSV 的业务日期列、JSON 的时间/报告期字段），
#      mtime 只在文件确实没有任何业务日期字段时兜底，且必须打印提示；
#   2. 更新命令返回 0 **不算成功**：必须重新读取被更新文件的内容日期，
#      达到该项的分级时效要求才算成功，否则记为失败并打印「命令成功但内容未更新」；
#   3. 时效按数据源分级，集中配置在 DEFAULT_FRESHNESS_RULES / FRESHNESS_RULES 表里，
#      每项可单独覆盖（configure_freshness_rule() 或 --freshness-config）：
#        - 行情 qfq、技术指标：必须等于期望交易日（滞后 0 个交易日）；
#        - 资金流、融资融券、估值：允许滞后 1 个交易日；
#        - 股东户数、机构持股等低频数据：允许滞后 5 个交易日；
#        - 财务类（财务指标、杜邦）：按报告季度判定，默认不允许落后于应披露季度（已含法定披露期宽限）；
#   4. 任一检查项失败 → main 汇总失败清单并返回非 0 退出码。
#
# 交易日与期望交易日的近似说明（本地没有 A 股交易日历表）：
#   * 默认按「周一至周五」估算交易日，无法识别法定节假日与调休；
#   * 18:00 之前当日日线还没落库，期望交易日回退到「前一工作日」，周末继续回退；
#   * 期望交易日取「日历推算」与「本地行情内容日期」中较晚者：
#       - 日历负责发现整库停更（本地数据都停在旧日期时仍要求补更）；
#       - 内容日期负责节假日兜底（行情已停在节前最后一个交易日时，不会被日历越判越旧）；
#   * 需要精确日历时用 set_trade_calendar_hook() 注入
#     fn(start_date, end_date) -> 交易日日期序列 的函数；未注入时会打印「本地无交易日历」提示。

import os
import sys
import copy
import json
import calendar
import hashlib
import tempfile
import subprocess
from datetime import datetime, timedelta, date
import pandas as pd

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR, STOCK_TICKERS


# ============================================================
# 时效分级表（默认值，集中配置；每项可单独覆盖）
# ============================================================
# kind='trading_days'：内容日期相对期望交易日最多允许滞后 max_lag_trading_days 个交易日
#                     （0 表示必须等于期望交易日）；
# kind='quarter'：     按报告季度判定，内容里的最新报告期最多允许落后 max_lag_quarters 个季度；
# date_columns：       CSV 里业务日期的候选列名（按顺序取第一个存在的列，再取该列最大日期）；
# json_date_keys：     JSON 里业务日期字段名（递归查找取最大日期），为空则用 timestamp 等时间字段；
# allow_mtime_fallback：完全读不到业务日期时，是否允许用文件修改时间兜底（仅用于确实没有业务日期的文件）；
# desc：               打印用的中文名称。
DEFAULT_FRESHNESS_RULES = {
    # ---- 日更：行情与技术指标必须等于期望交易日 ----
    'qfq': {
        'kind': 'trading_days', 'max_lag_trading_days': 0,
        'date_columns': ['date'], 'desc': '前复权行情',
    },
    'indicators': {
        'kind': 'trading_days', 'max_lag_trading_days': 0,
        'date_columns': ['date'], 'desc': '技术指标',
    },
    # ---- 日更：资金流/融资融券/估值允许滞后 1 个交易日 ----
    'fund_flow': {
        'kind': 'trading_days', 'max_lag_trading_days': 1,
        'date_columns': ['日期', 'date'], 'desc': '资金流',
    },
    'margin_data': {
        'kind': 'trading_days', 'max_lag_trading_days': 1,
        'date_columns': ['date', '日期'], 'desc': '融资融券',
    },
    # 估值即使与资金流同批产出，也必须独立复核。
    'valuation': {
        'kind': 'trading_days', 'max_lag_trading_days': 1,
        'date_columns': ['数据日期', 'date'], 'desc': '估值',
    },
    # ---- 低频：股东户数、机构持股等允许滞后 5 个交易日 ----
    'shareholder_num': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': ['END_DATE', '日期'], 'critical': False, 'desc': '股东户数',
    },
    'shareholder': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': ['END_DATE', 'REPORT_DATE'], 'critical': False, 'desc': '前十大股东',
    },
    'institutional': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': ['REPORT_DATE'], 'critical': False, 'desc': '机构持股',
    },
    'north_holdings': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': ['TRADE_DATE', 'CC_DATE', 'date'], 'critical': False, 'desc': '北向持仓',
    },
    'company_basic': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': [], 'critical': False, 'desc': '公司基本信息',
    },
    'ex_dividend': {
        'kind': 'trading_days', 'max_lag_trading_days': 5,
        'date_columns': [], 'allow_mtime_fallback': True, 'critical': False, 'desc': '除权除息',
    },
    # ---- 财务类：按季度（报告期） ----
    'financial_indicators': {
        'kind': 'quarter', 'max_lag_quarters': 0,
        'date_columns': [], 'json_date_keys': ['报告日', 'REPORT_DATE'], 'critical': False, 'desc': '财务指标',
    },
    'dupont': {
        'kind': 'quarter', 'max_lag_quarters': 0,
        'date_columns': ['REPORT_DATE'], 'critical': False, 'desc': '杜邦分析',
    },
}

# 运行期生效的时效表（默认等于上表，可用 configure_freshness_rule()/--freshness-config 覆盖）
FRESHNESS_RULES = copy.deepcopy(DEFAULT_FRESHNESS_RULES)

# 财务报告的法定披露截止日（按报告季度）：一季报 4/30、半年报 8/31、三季报 10/31、年报次年 4/30
FINANCIAL_REPORT_DEADLINES = {
    1: (4, 30),
    2: (8, 31),
    3: (10, 31),
    4: (4, 30),
}

# 可注入的交易日历钩子：fn(start_date, end_date) -> 升序交易日日期序列。
# 本地没有交易日历表，默认只用工作日近似；需要精确日历时由调用方注入。
TRADE_CALENDAR_HOOK = None

# 日更数据清单：数据项 -> (文件名模板, 更新命令模板)
# 注意：数据项名必须与 DEFAULT_FRESHNESS_RULES 的键一致，时效阈值只在上面的表里维护。
DAILY_DATA_FILES = {
    'qfq': ('{ticker}_qfq.csv', 'python data_collector.py --ticker {ticker}'),
    'fund_flow': ('{ticker}_fund_flow.csv', 'python stock_market_data_collector.py --ticker {ticker}'),
    'margin_data': ('{ticker}_margin_data.csv', 'python batch_margin_collector.py --ticker {ticker}'),
    'valuation': ('{ticker}_valuation.csv', 'python stock_market_data_collector.py --ticker {ticker}'),
    'indicators': ('{ticker}_indicators.csv', 'python daily/stock_daily_indicator_calculator.py --ticker {ticker}'),
    'shareholder_num': ('{ticker}_shareholder_num.csv', 'python shareholder_num_collector.py --ticker {ticker}'),
}

# 只影响行情/指标的清单：选股与回测只需要这两项，不抓资金流、融资融券等慢数据源。
PRICE_DATA_FILES = {name: DAILY_DATA_FILES[name] for name in ('qfq', 'indicators')}

# 低频数据清单：数据项 -> (文件名模板, 更新命令模板)
PERIODIC_DATA_FILES = {
    'company_basic': ('{ticker}_company_basic.json', 'python stock_company_info_collector.py --ticker {ticker}'),
    'financial_indicators': ('{ticker}_financial_indicators.json', 'python financial_indicators_collector.py --ticker {ticker}'),
    'dupont': ('{ticker}_dupont_data.csv', 'python em_financial_collector.py --ticker {ticker}'),
    'shareholder': ('{ticker}_historical_shareholders.csv', 'python shareholders_collector.py --ticker {ticker}'),
    'ex_dividend': ('{ticker}_ex_dividend.csv', 'python important_missing_data_collector.py --ticker {ticker}'),
    'institutional': ('{ticker}_institutional_holdings.csv', 'python org_hold_collector.py --ticker {ticker}'),
    'north_holdings': ('{ticker}_north_holdings.csv', 'python north_holdings.py --ticker {ticker}'),
}

# 通用日期列兜底（仅当规则没有指定或指定列不存在时使用）
_GENERIC_DATE_COLUMNS = ['date', '日期', '数据日期', '交易日期', 'TRADE_DATE', 'REPORT_DATE', 'END_DATE', '截至日期']


# ============================================================
# 工具函数
# ============================================================
def _tail_output(stdout, stderr, max_lines=5, max_chars=500):
    """取命令输出末尾若干行，作为失败原因一并返回。"""
    lines = []
    for text in (stdout or '', stderr or ''):
        for line in str(text).splitlines():
            if line.strip():
                lines.append(line.strip())
    tail = ' | '.join(lines[-max_lines:])
    return tail[-max_chars:]


def run_command(cmd, cwd=None):
    """执行命令并返回 (success, detail)。

    只有退出码为 0 才算成功；失败时把 returncode 与输出末尾原因带出，
    由调用方汇总到失败清单，绝不把非 0 当成「警告」放行。
    注意：退出码 0 也不代表数据已更新，调用方还必须复核内容日期。
    """
    if cmd.startswith('python '):
        cmd = f'"{sys.executable}" ' + cmd[len('python '):]
    print(f"执行命令: {cmd}")
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=cwd)
        if result.stdout:
            print(f"标准输出: {result.stdout}")
        if result.stderr:
            print(f"标准错误: {result.stderr}")
        from api.common import parse_data_status
        statuses = [parse_data_status(line) for line in (result.stdout or '').splitlines()]
        statuses = [s for s in statuses if s is not None]
        child_failures = [str(w) for s in statuses for w in s.get('critical_failures', [])]
        child_warnings = [str(w) for s in statuses for w in s.get('warnings', [])]
        if child_failures:
            return False, '; '.join(child_failures)
        if result.returncode == 0:
            if child_warnings or any(s.get('degraded') for s in statuses):
                return True, STATUS_PREFIX + json.dumps({'degraded': True, 'warnings': child_warnings or ['子进程数据降级']}, ensure_ascii=False)
            return True, ''
        detail = f'returncode={result.returncode}'
        tail = _tail_output(result.stdout, result.stderr)
        if tail:
            detail = f'{detail}；输出末尾: {tail}'
        return False, detail
    except Exception as e:
        print(f"执行命令出错: {e}")
        return False, f'执行异常: {e}'


def parse_date_str(value):
    """统一解析日期字符串/数值"""
    if isinstance(value, datetime):
        return value.date()
    if hasattr(value, 'date'):
        return value.date()
    s = str(value)
    for fmt in ["%Y-%m-%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(s.split(' ')[0], fmt).date()
        except (ValueError, IndexError):
            continue
    return None


def _normalize_date(value):
    """把 str/datetime/pandas.Timestamp 统一成 datetime.date。"""
    if value is None:
        return None
    d = parse_date_str(value)
    return d


def _parse_date_series(series):
    """解析一列日期，返回可用的 datetime 序列（可能为空）。"""
    s = series.dropna()
    if s.empty:
        return None
    # 纯数字列（如 20260521）必须先转字符串，否则 pandas 会按纳秒时间戳解释
    if pd.api.types.is_numeric_dtype(s):
        s = s.astype('int64').astype(str)
    else:
        s = s.astype(str)
    parsed = pd.to_datetime(s, errors='coerce').dropna()
    return parsed if len(parsed) else None


def is_latest_date(last_date_val, expected_date):
    """兼容旧接口：内容日期是否已达到期望的最近交易日（严格口径，滞后 0）。"""
    try:
        content_date = parse_date_str(last_date_val)
        if not content_date:
            return False
        return content_date >= expected_date
    except Exception:
        return False


# ============================================================
# 交易日历（默认工作日近似 + 可注入钩子）
# ============================================================
def set_trade_calendar_hook(hook):
    """注入交易日历函数：fn(start_date, end_date) -> 交易日日期序列（升序，区间闭合）。

    注入后 get_trading_days / get_calendar_trade_date 都改走该日历，
    可用于替换「工作日近似」以正确处理法定节假日与调休。
    """
    global TRADE_CALENDAR_HOOK
    TRADE_CALENDAR_HOOK = hook


def get_trade_calendar_hook():
    """返回当前注入的交易日历钩子（未注入返回 None）。"""
    return TRADE_CALENDAR_HOOK


def clear_trade_calendar_hook():
    """清除已注入的交易日历钩子，恢复工作日近似。"""
    global TRADE_CALENDAR_HOOK
    TRADE_CALENDAR_HOOK = None


def _weekday_range(start_date, end_date):
    """工作日近似：返回 [start_date, end_date] 内所有周一至周五。"""
    days = []
    cur = start_date
    while cur <= end_date:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def get_trading_days(start_date, end_date):
    """返回 [start_date, end_date] 内的交易日（升序）。

    优先使用注入的交易日历钩子；未注入或钩子异常时按工作日近似（节假日无法识别）。
    """
    if end_date < start_date:
        return []
    hook = get_trade_calendar_hook()
    if hook is not None:
        try:
            raw = hook(start_date, end_date) or []
            days = sorted({_normalize_date(d) for d in raw if _normalize_date(d)})
            return [d for d in days if start_date <= d <= end_date]
        except Exception as e:
            print(f"交易日历钩子调用失败，回退工作日近似: {e}")
    return _weekday_range(start_date, end_date)


def trading_days_lag(content_date, expected_date):
    """内容日期相对期望交易日的滞后交易日数（内容日期本身算 0）。

    例：期望 2026-11-12，内容 2026-11-11 → 滞后 1 个交易日；
        期望 2026-11-09（周一），内容 2026-11-06（周五）→ 滞后 1 个交易日。
    """
    if content_date is None or expected_date is None:
        return None
    if content_date >= expected_date:
        return 0
    return len(get_trading_days(content_date + timedelta(days=1), expected_date))


def _prev_weekday(value):
    """回退到最近的工作日（不含节假日表）。"""
    while value.weekday() >= 5:
        value -= timedelta(days=1)
    return value


# 数据源发布当日日线的切点（小时，本地时间）。18:00 之前一律按前一交易日处理，
# 避免收盘后到发布前这段时间把整条链路误判成"数据过期"。
DATA_PUBLISH_HOUR = 18


def get_calendar_trade_date(now=None):
    """按日历推算最近交易日。

    近似规则（本地无交易日历表时）：
      * 18:00 之前当日日线尚未落库 → 期望日期回退到前一工作日；
      * 之后遇周末继续回退到最近工作日；
      * 无法识别法定节假日与调休（由内容日期兜底，见 get_expected_trade_date）。
    注入交易日历钩子后，改为「钩子返回的最后一个不晚于目标日的交易日」。
    """
    now = now or datetime.now()
    value = now.date()
    if now.hour < DATA_PUBLISH_HOUR:
        value -= timedelta(days=1)
    hook = get_trade_calendar_hook()
    if hook is not None:
        days = get_trading_days(value - timedelta(days=40), value)
        if days:
            return days[-1]
        print(f"交易日历钩子未返回 {value} 之前的交易日，回退工作日近似")
    return _prev_weekday(value)


def get_last_data_date(file_path):
    """读取文件内容中的最后一条业务日期，用于判断数据是否最新（不看 mtime）。

    日更 CSV 取最后一行的日期列；JSON 走 get_latest_data_date 的通用解析。
    该函数只返回「最后一行」的日期；需要取整列最大日期请用 read_content_date()。
    """
    if not os.path.exists(file_path):
        return None
    try:
        if file_path.endswith('.json'):
            return get_latest_data_date(file_path)
        df = pd.read_csv(file_path)
        if df.empty:
            return None
        for col in ['date', '日期', '数据日期', '交易日期', 'TRADE_DATE']:
            if col in df.columns:
                return parse_date_str(df.iloc[-1][col])
        return None
    except Exception as e:
        print(f"读取文件内容日期出错: {e}")
        return None


def get_market_latest_date(tickers):
    """从本地 qfq 内容日期推断最近交易日（只读文件内容，不看 mtime）。"""
    latest = None
    for ticker in tickers:
        qfq_file = os.path.join(DATA_DIR, ticker, f"{ticker}_qfq.csv")
        content_date = get_last_data_date(qfq_file)
        if content_date and (latest is None or content_date > latest):
            latest = content_date
    return latest


def get_expected_trade_date(tickers, now=None):
    """统一时效门槛：18:00 前为前一交易日，此后为当日。

    本地某只股票提前发布的当日线不能抬高所有股票的更新门槛；
    行情实际日期及来源身份另行校验，旧库也不能降低此门槛。
    """
    value = get_calendar_trade_date(now)
    if get_trade_calendar_hook() is None:
        print(f"提示：本地无交易日历（未注入日历钩子），按工作日近似；"
              f"18:00 切点，期望交易日 {value}")
    return value


def get_latest_available_trade_date(tickers, now=None):
    """本地实际能取到的最新行情日期（用于"验证"而不是"触发更新"）。

    收盘后日历会认为今天是交易日，但数据源往往还没发布当日 K 线；
    这时用本地最新内容日期作为校验基准，配合 LAG_WARNINGS 提示即可，
    不必把整条链路判成失败。
    """
    market_date = get_market_latest_date(tickers)
    if market_date:
        return market_date
    return get_expected_trade_date(tickers, now=now)


# 数据源尚未发布当日行情时的提示（不判失败，但要暴露给上游显示降级）
LAG_WARNINGS = []


def reset_lag_warnings():
    LAG_WARNINGS.clear()


# ============================================================
# 财务类「按季度」判定
# ============================================================
def get_quarter_end(value):
    """返回 value 所在季度的季末日期。"""
    q = (value.month - 1) // 3 + 1
    last_month = q * 3
    last_day = calendar.monthrange(value.year, last_month)[1]
    return date(value.year, last_month, last_day)


def get_quarter_index(value):
    """季度的连续编号，用于计算季度差。"""
    q = (value.month - 1) // 3 + 1
    return value.year * 4 + q


def get_report_deadline(quarter_end):
    """报告季度对应的法定披露截止日（年报顺延到次年 4/30）。"""
    q = (quarter_end.month - 1) // 3 + 1
    month, day = FINANCIAL_REPORT_DEADLINES[q]
    year = quarter_end.year + (1 if q == 4 else 0)
    return date(year, month, day)


def get_prev_quarter_end(quarter_end):
    """返回 quarter_end 所在季度的上一季度末。"""
    q = (quarter_end.month - 1) // 3 + 1
    year = quarter_end.year
    if q == 1:
        prev_q, year = 4, year - 1
    else:
        prev_q = q - 1
    last_month = prev_q * 3
    last_day = calendar.monthrange(year, last_month)[1]
    return date(year, last_month, last_day)


def get_expected_report_quarter_end(expected_date):
    """按法定披露截止日推算「截至期望交易日应当已披露的最近报告期末」。"""
    quarter_end = get_quarter_end(expected_date)
    for _ in range(12):
        if get_report_deadline(quarter_end) <= expected_date:
            return quarter_end
        quarter_end = get_prev_quarter_end(quarter_end)
    return quarter_end


# ============================================================
# 时效分级表读取/覆盖
# ============================================================
def _validate_freshness_rule(item_name, rule):
    """校验单条时效规则，配置错误时抛 ValueError。"""
    kind = rule.get('kind', 'trading_days')
    if kind not in ('trading_days', 'quarter'):
        raise ValueError(f"{item_name}: kind 只能是 trading_days 或 quarter，收到 {kind!r}")
    if kind == 'trading_days':
        lag = rule.get('max_lag_trading_days')
        if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
            raise ValueError(f"{item_name}: max_lag_trading_days 必须是非负整数，收到 {lag!r}")
    else:
        lag = rule.get('max_lag_quarters')
        if isinstance(lag, bool) or not isinstance(lag, int) or lag < 0:
            raise ValueError(f"{item_name}: max_lag_quarters 必须是非负整数，收到 {lag!r}")


def get_freshness_rule(item_name):
    """取某项数据当前生效的时效规则。"""
    if item_name not in FRESHNESS_RULES:
        raise KeyError(f"未知数据项: {item_name}（时效表里没有这一项）")
    return FRESHNESS_RULES[item_name]


def configure_freshness_rule(item_name, **overrides):
    """单独覆盖某项数据的时效阈值（未覆盖字段沿用默认值）。"""
    if item_name not in DEFAULT_FRESHNESS_RULES:
        raise ValueError(
            f"未知数据项: {item_name}（可选: {', '.join(DEFAULT_FRESHNESS_RULES)}）"
        )
    rule = copy.deepcopy(FRESHNESS_RULES.get(item_name, DEFAULT_FRESHNESS_RULES[item_name]))
    rule.update(overrides)
    _validate_freshness_rule(item_name, rule)
    FRESHNESS_RULES[item_name] = rule
    return rule


def reset_freshness_rules():
    """把运行期时效表恢复成模块顶部默认值。"""
    FRESHNESS_RULES.clear()
    FRESHNESS_RULES.update(copy.deepcopy(DEFAULT_FRESHNESS_RULES))


def load_freshness_config(config_path):
    """从 JSON 文件加载时效覆盖配置：{"数据项": {"字段": 值, ...}, ...}。"""
    with open(config_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError('时效配置必须是 JSON 对象，形如 {"fund_flow": {"max_lag_trading_days": 2}}')
    for item_name, overrides in data.items():
        if not isinstance(overrides, dict):
            raise ValueError(f"{item_name} 的配置必须是对象")
        configure_freshness_rule(item_name, **overrides)


def format_freshness_rules():
    """返回时效分级表的可读描述行（供 main 打印）。"""
    lines = []
    for name, rule in FRESHNESS_RULES.items():
        desc = rule.get('desc', name)
        if rule.get('kind', 'trading_days') == 'trading_days':
            lag = rule.get('max_lag_trading_days', 0)
            requirement = '必须等于期望交易日' if lag == 0 else f'允许滞后 {lag} 个交易日'
        else:
            requirement = f"按报告季度判定，允许滞后 {rule.get('max_lag_quarters', 0)} 个季度"
        lines.append(f"{name}（{desc}）：{requirement}")
    return lines


# ============================================================
# 内容日期读取（CSV 业务日期列 / JSON 时间与报告期字段）
# ============================================================
def _collect_json_dates(obj, keys, max_depth=5, depth=0):
    """递归查找 JSON 里指定字段的日期，返回 date 列表。"""
    found = []
    if depth > max_depth:
        return found
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys:
                d = parse_date_str(value)
                if d:
                    found.append(d)
            if isinstance(value, (dict, list)):
                found.extend(_collect_json_dates(value, keys, max_depth, depth + 1))
    elif isinstance(obj, list):
        for item in obj[:200]:
            if isinstance(item, (dict, list)):
                found.extend(_collect_json_dates(item, keys, max_depth, depth + 1))
    return found


def _read_csv_content_date(file_path, rule):
    """从 CSV 业务日期列取最大日期。"""
    df = pd.read_csv(file_path)
    if df.empty:
        return None, '文件为空'
    candidates = list(rule.get('date_columns') or []) + _GENERIC_DATE_COLUMNS
    seen = set()
    for col in candidates:
        if col in seen or col not in df.columns:
            continue
        seen.add(col)
        parsed = _parse_date_series(df[col])
        if parsed is None:
            continue
        source = '指定业务日期列' if col in (rule.get('date_columns') or []) else '通用日期列'
        return parsed.max().date(), f'{source} {col}'
    return None, f'未找到可解析的业务日期列（候选 {candidates}）'


def _read_json_content_date(file_path, rule):
    """从 JSON 取业务日期：优先规则指定的报告期字段，其次 timestamp 等时间字段。"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, dict):
        return None, 'JSON 顶层不是对象'
    keys = set(rule.get('json_date_keys') or [])
    if keys:
        dates = _collect_json_dates(data, keys)
        if dates:
            return max(dates), f'报告期字段 {"/".join(sorted(keys))}'
    for key in ('timestamp', 'update_time', 'data_date', '数据日期'):
        if data.get(key):
            d = parse_date_str(data[key])
            if d:
                return d, f'时间字段 {key}'
    d = get_latest_data_date(file_path)
    if d:
        return d, '通用日期字段'
    return None, '未找到可解析的时间/报告期字段'


def read_content_date(file_path, rule):
    """读取数据文件内容里的业务日期，返回 (date 或 None, 来源说明)。

    只认文件内容，不看 mtime（mtime 兜底由 check_file_freshness 按规则单独处理）。
    """
    if not os.path.exists(file_path):
        return None, '文件不存在'
    try:
        if file_path.lower().endswith('.json'):
            return _read_json_content_date(file_path, rule)
        return _read_csv_content_date(file_path, rule)
    except Exception as e:
        print(f"读取内容日期出错: {file_path}: {e}")
        return None, f'读取异常: {e}'


def is_fresh(content_date, expected_date, rule):
    """按规则判断内容日期是否达标，返回 (ok, 原因说明)。"""
    if isinstance(rule, str):
        rule = get_freshness_rule(rule)
    if content_date is None:
        return False, '内容日期缺失'
    if content_date >= expected_date:
        return True, f'内容日期 {content_date} 不早于期望交易日 {expected_date}'
    if rule.get('kind', 'trading_days') == 'trading_days':
        lag = trading_days_lag(content_date, expected_date)
        allowed = rule.get('max_lag_trading_days', 0)
        if lag <= allowed:
            return True, f'滞后 {lag} 个交易日（允许 ≤ {allowed}）'
        return False, f'滞后 {lag} 个交易日，超过允许的 {allowed} 个交易日'
    content_quarter = get_quarter_end(content_date)
    expected_quarter = get_expected_report_quarter_end(expected_date)
    lag = get_quarter_index(expected_quarter) - get_quarter_index(content_quarter)
    allowed = rule.get('max_lag_quarters', 0)
    if lag <= allowed:
        return True, f'报告期 {content_quarter}，不早于应披露报告期 {expected_quarter}（允许滞后 ≤ {allowed} 个季度）'
    return False, f'报告期 {content_quarter}，落后应披露报告期 {expected_quarter} 共 {lag} 个季度，超过允许的 {allowed} 个季度'


# ============================================================
# 检查逻辑
# ============================================================
def get_file_modification_date(file_path):
    """文件修改日期（只在完全读不到业务日期时作兜底）。"""
    if os.path.exists(file_path):
        return date.fromtimestamp(os.path.getmtime(file_path))
    return None


def check_file_freshness(file_path, expected_date, rule, item_name=None):
    """检查单个文件的内容日期是否达到分级时效要求，返回 (ok, 原因)。

    内容日期读不到时，只有规则 allow_mtime_fallback=True 才用 mtime 兜底并打印提示。
    """
    label = item_name or rule.get('desc') or os.path.basename(file_path)
    content_date, source = read_content_date(file_path, rule)
    if content_date is None:
        if rule.get('allow_mtime_fallback'):
            mod_date = get_file_modification_date(file_path)
            if mod_date is not None:
                print(f"  提示：{label} 读不到业务日期（{source}），按文件修改时间 {mod_date} 兜底（较弱判定）")
                content_date, source = mod_date, '文件修改时间（兜底）'
            else:
                print(f"  {label} 文件不存在且读不到业务日期: {file_path}")
                return False, '文件不存在且无业务日期'
        else:
            print(f"  {label} 读不到内容日期（{source}）: {file_path}")
            return False, f'读不到内容日期（{source}）'
    ok, reason = is_fresh(content_date, expected_date, rule)
    if ok and (item_name == 'indicators' or os.path.basename(file_path).endswith('_indicators.csv')):
        try:
            from indicator_provenance import validate_indicators
            ticker = os.path.basename(file_path).removesuffix('_indicators.csv')
            # 上面的 is_fresh 检查最低时效；来源必须精确匹配文件实际日期。
            # 不能把18点前的昨日门槛误当成实际截止日，拒绝已更新到今日的指标。
            validate_indicators(ticker, data_dir=os.path.dirname(os.path.dirname(file_path)),
                                expected_asof=content_date.isoformat())
        except Exception as exc:
            ok, reason = False, f'指标来源版本无效: {exc}'
    if ok:
        print(f"  {label} 内容日期达标: {content_date}（来源：{source}；{reason}）")
    else:
        print(f"  {label} 内容日期不达标: {content_date}（来源：{source}；{reason}）")
    return ok, reason


def get_last_date(file_path):
    """兼容旧调用：返回文件最后一行日期列的原值。"""
    try:
        df = pd.read_csv(file_path)
        if df.empty:
            return None
        for col in ['date', '日期', '数据日期', '交易日期', 'TRADE_DATE']:
            if col in df.columns:
                return df.iloc[-1][col]
        return None
    except Exception as e:
        print(f"读取文件出错: {e}")
        return None


def check_file_up_to_date(file_path, expected_date):
    """兼容旧接口：按「内容日期必须等于期望交易日」的严格口径判断。"""
    strict_rule = {'kind': 'trading_days', 'max_lag_trading_days': 0, 'date_columns': []}
    ok, _ = check_file_freshness(file_path, expected_date, strict_rule, item_name=os.path.basename(file_path))
    return ok


def get_latest_data_date(file_path):
    """兼容旧接口：读 JSON/CSV 里的通用日期（timestamp、研报日期、股东截至日期等）。"""
    try:
        if file_path.endswith('.json'):
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if 'timestamp' in data:
                d = parse_date_str(data['timestamp'])
                if d:
                    return d
            # 研报中的最新日期
            for report in data.get('research_reports', []) or []:
                if '日期' in report:
                    d = parse_date_str(report['日期'])
                    if d:
                        return d
            # 股东中的最新日期
            for sh in data.get('main_shareholders', []) or []:
                if '截至日期' in sh:
                    d = parse_date_str(sh['截至日期'])
                    if d:
                        return d
        elif file_path.endswith('.csv'):
            df = pd.read_csv(file_path)
            for col in ['REPORT_DATE', 'date', '截至日期', '日期']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
                    if not df[col].dropna().empty:
                        return df[col].max().date()
        return None
    except Exception as e:
        print(f"获取文件数据日期时出错: {e}")
        return None


def is_file_need_update(file_path, update_frequency_days):
    """兼容旧接口：按自然日频率判断是否需要更新（已弃用，检查流程改走分级时效表）。"""
    if not os.path.exists(file_path):
        print(f"文件不存在，需要更新: {file_path}")
        return True
    latest = get_latest_data_date(file_path)
    if latest:
        days_since = (date.today() - latest).days
        if days_since >= update_frequency_days:
            print(f"数据已超过 {update_frequency_days} 天未更新 ({latest}，距今 {days_since} 天)")
            return True
    else:
        # mtime 只作辅助：文件里读不到业务日期时才用它估算
        mod_date = get_file_modification_date(file_path)
        if not mod_date:
            return True
        days_since = (date.today() - mod_date).days
        if days_since >= update_frequency_days:
            print(f"无法解析数据日期，按修改时间估算已超过 {update_frequency_days} 天: {file_path}")
            return True
    print(f"数据是最新的: {file_path}")
    return False


def check_and_update_item(ticker, item_name, filename, command, expected_date, stock_dir):
    """检查单项数据；不达标则更新，并在命令成功后强制复核内容日期。

    返回失败描述（成功返回 None）。命令退出码 0 不算成功，
    只有更新后内容日期达到分级时效要求才算成功。
    """
    rule = get_freshness_rule(item_name)
    # 核心项失败=必须中止；非核心项（长期披露口径的数据）失败只作警告，
    # 否则会天天误判、把正常分析任务一起卡死。
    tag = '[核心]' if rule.get('critical', True) else '[非核心]'
    file_path = os.path.join(stock_dir, filename)
    fresh, _ = check_file_freshness(file_path, expected_date, rule, item_name=item_name)
    if fresh:
        return None

    # 融资融券是"按交易日抓全市场"的接口，一天约 20 秒且带休眠；
    # 时效检查只需要补齐最近的空档，不必把几个月的历史全抓回来。
    if item_name == 'margin_data' and '--start_date' not in command:
        start = expected_date - timedelta(days=10)
        command = f"{command} --start_date {start.strftime('%Y%m%d')}"

    before_date, _ = read_content_date(file_path, rule)
    print(f"  {filename} 不达标（更新前内容日期 {before_date if before_date else '无法读取'}），执行更新命令: {command}")
    ok, detail = run_command(command)
    if item_name == 'qfq' and not ok and 'returncode=3' in str(detail):
        # 退出码 3 = 前复权基准变化（除权除息）。增量拒绝追加是对的，
        # 但必须用统一基准重建，否则该股票会永远更新失败。
        print(f"  {ticker} 前复权基准变化，自动重建完整历史")
        ok, detail = run_command(f'python data_collector.py --ticker {ticker} --rebuild')
    if not ok or detail.startswith(STATUS_PREFIX):
        failure = f"{tag} {ticker} {item_name} ({filename}) 更新失败: {detail}"
        print(f"  ❌ {failure}")
        return failure

    # 命令返回 0 后必须重新读取内容日期复核，防止「命令成功、数据没更新」继续往下走
    after_date, after_source = read_content_date(file_path, rule)
    after_ok, after_reason = check_file_freshness(file_path, expected_date, rule, item_name=item_name)
    if after_ok:
        print(f"  ✅ {item_name} 更新后复核通过: {after_date}（来源：{after_source}；{after_reason}）")
        return None
    # 已延迟到18:00切换；此后内容仍不达标必须失败，不放行任意旧行情。
    failure = (
        f"{tag} {ticker} {item_name} ({filename}) 命令成功但内容未更新: "
        f"更新前 {before_date if before_date else '无法读取'}，"
        f"更新后 {after_date if after_date else '无法读取'}（{after_source}），{after_reason}"
    )
    print(f"  ❌ {failure}")
    return failure


STATUS_PREFIX = 'GP_DATA_STATUS='


def source_digest(path):
    try:
        with open(path, 'rb') as stream:
            return hashlib.sha256(stream.read()).hexdigest()
    except OSError:
        return None


def write_evidence_state(ticker, expected_date, items):
    """保存已核验的来源身份；未完成的检查不得作为有效证据。"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    path = os.path.join(stock_dir, f'{ticker}_data_freshness.json')
    state = {'schema_version': 1, 'ticker': ticker, 'items': {}}
    try:
        with open(path, encoding='utf-8') as stream:
            previous = json.load(stream)
        if previous.get('expected_date') == expected_date.isoformat():
            state['items'] = previous.get('items', {})
    except (OSError, ValueError):
        pass
    state.update(expected_date=expected_date.isoformat(), checked_at=datetime.now().isoformat())
    state['items'].update(items)
    fd, temporary = tempfile.mkstemp(dir=stock_dir, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(state, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return state


def _check_group(ticker, expected_date, files):
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    expected_date = expected_date or get_expected_trade_date([ticker])
    failures, items = [], {}
    # 执行任何子命令前，先将本组的旧证据标为失效。
    for name, (filename, _) in files.items():
        items[name] = {'valid': False, 'reason': '检查未完成', 'filename': filename.format(ticker=ticker)}
    write_evidence_state(ticker, expected_date, items)
    for name, (filename, command) in files.items():
        filename = filename.format(ticker=ticker)
        try:
            failure = check_and_update_item(ticker, name, filename, command.format(ticker=ticker), expected_date, stock_dir)
        except Exception as exc:
            tag = '[核心]' if get_freshness_rule(name).get('critical', True) else '[非核心]'
            failure = f'{tag} {ticker} {name} 检查异常: {exc}'
        if failure:
            failures.append(failure)
        items[name] = {'valid': not bool(failure), 'reason': failure or '', 'filename': filename,
                       'sha256': source_digest(os.path.join(stock_dir, filename)),
                       'checked_at': datetime.now().isoformat()}
        write_evidence_state(ticker, expected_date, items)
    return failures


def check_daily_data(ticker, expected_date=None):
    return _check_group(ticker, expected_date, DAILY_DATA_FILES)


def check_price_data(ticker, expected_date=None):
    """只检查行情与技术指标（选股/回测的最小依赖）。"""
    return _check_group(ticker, expected_date, PRICE_DATA_FILES)


def check_periodic_data(ticker, expected_date=None):
    return _check_group(ticker, expected_date, PERIODIC_DATA_FILES)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="统一数据更新检查")
    parser.add_argument('--ticker', help="股票代码，如 300433.SZ（不指定则处理全部）")
    parser.add_argument('--mode', choices=['price', 'daily', 'periodic', 'all'], default='daily',
                        help="更新模式：price=仅行情+指标（选股/回测用）；daily=日更；periodic=低频；all=全部 (default: daily)")
    parser.add_argument('--freshness-config', dest='freshness_config',
                        help="可选的时效覆盖配置（JSON 文件，形如 {\"fund_flow\": {\"max_lag_trading_days\": 2}}）")
    args = parser.parse_args()

    if args.freshness_config:
        try:
            load_freshness_config(args.freshness_config)
            print(f"已加载时效覆盖配置: {args.freshness_config}")
        except (OSError, ValueError) as e:
            print(f"❌ 加载时效覆盖配置失败: {e}")
            return 1

    tickers = [args.ticker] if args.ticker else list(STOCK_TICKERS.values())
    if not args.ticker:
        print(f"批量处理 {len(tickers)} 只股票")

    expected_date = get_expected_trade_date(tickers)
    print(f"最近交易日（期望数据日期）: {expected_date}")
    print("数据时效分级:")
    for line in format_freshness_rules():
        print(f"  - {line}")

    reset_lag_warnings()
    failures = []
    for t in tickers:
        try:
            if args.mode == 'price':
                failures.extend(check_price_data(t, expected_date))
            if args.mode in ('daily', 'all'):
                failures.extend(check_daily_data(t, expected_date))
            if args.mode in ('periodic', 'all'):
                failures.extend(check_periodic_data(t, expected_date))
        except Exception as e:
            failures.append(f"{t} 检查过程异常: {e}")

    # 未打标签的一律按核心处理（保守默认），只有显式标了 [非核心] 才降级为警告
    warnings = [f for f in failures if f.startswith('[非核心]')]
    warnings.extend(LAG_WARNINGS)
    critical = [f for f in failures if not f.startswith('[非核心]')]

    if failures:
        print("\n========== 数据更新失败清单 ==========")
        for failure in failures:
            print(f"  ❌ {failure}")

    if warnings:
        print(f"\n⚠️  {len(warnings)} 项非核心数据未达标（不阻塞流程，但相关分析维度应视为缺失）：")
        for warning in warnings:
            print(f"  - {warning}")

    print(STATUS_PREFIX + json.dumps({'schema_version': 1, 'degraded': bool(warnings),
                                     'warnings': warnings, 'critical_failures': critical}, ensure_ascii=False))
    if critical:
        print(f"\n共 {len(critical)} 项核心数据失败，本次检查不通过")
        return 1

    print("\n所有核心数据均达到分级时效要求（内容日期均达到分级时效要求）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
