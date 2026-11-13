"""回测产物的身份、写入与读取（单一实现，避免"按文件名猜最新"）。

问题背景
--------
旧代码把所有 `*_backtest_*.csv` 丢进列表按字符串排序取最后一个。由于
`_backtest_simplified_20260525` 里的 "s" 大于数字，旧文件永远压过新日期文件，
导致 2026-11-13 的最终持仓里混进了 5 月 21 日的旧记录。

本模块把"哪份结果有效"从文件名排序改成显式身份 + 行情截止日校验：

* 新文件：`{ticker}_backtest_{strategy}_{data_asof}_{runid}.csv`
  例：`000001.SZ_backtest_full_20261112_20261113T091530.csv`
* 旧文件（仍可读，但必须能解析出日期）：
  `{ticker}_backtest_{YYYYMMDD}.csv` -> strategy=full
  `{ticker}_backtest_simplified_{YYYYMMDD}.csv` -> strategy=simple
* 每次写入同时生成 `*_meta.json`：策略、参数、参数指纹、行情截止日、生成时间。

规则：读取方必须给出期望的行情截止日（仅人工诊断可 allow_any_asof=True），
否则一律视为不可用并抛 StaleArtifactError，绝不静默读取旧结果。
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import math
import tempfile
from datetime import datetime
from uuid import uuid4

import pandas as pd

try:
    from config import DATA_DIR
except ImportError:  # pragma: no cover - 允许脱离 Flask 运行测试
    DATA_DIR = "./data"

META_SCHEMA = 2
STRATEGIES = ("full", "simple")

# {ticker}_backtest_{strategy}_{data_asof}_{runid}.csv  或  {ticker}_backtest[_simplified]_{YYYYMMDD}.csv
_NAME_RE = re.compile(
    r"^(?P<ticker>[0-9]{6}\.[A-Z]{2})_backtest"
    r"(?:_(?P<strategy>full|simple|simplified))?"
    r"_(?P<date>[0-9]{8})"
    r"(?:_(?P<run>[0-9]{8}T[0-9]{6}(?:[0-9]{6}-[a-f0-9]{8})?))?"
    r"\.csv$"
)


class StaleArtifactError(RuntimeError):
    """产物缺失、过期或身份不明时抛出。"""


def _norm_strategy(token: str | None) -> str:
    if token in (None, "", "full"):
        return "full"
    if token in ("simple", "simplified"):
        return "simple"
    raise ValueError(f"未知策略标识: {token}")


def parse_name(filename: str) -> dict | None:
    """解析回测文件名，返回 ticker / strategy / data_asof / run_id / legacy。"""
    m = _NAME_RE.match(os.path.basename(filename))
    if not m:
        return None
    return {
        "ticker": m.group("ticker"),
        "strategy": _norm_strategy(m.group("strategy")),
        "data_asof": m.group("date"),
        "run_id": m.group("run"),
        "legacy": m.group("run") is None,
        "path": filename,
        "filename": os.path.basename(filename),
    }


def meta_path(csv_path: str) -> str:
    return os.path.splitext(csv_path)[0] + "_meta.json"


def iter_artifacts(ticker: str):
    """列出某只股票的所有可解析回测产物（按 data_asof 升序）。"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    if not os.path.isdir(stock_dir):
        return []
    found = []
    for name in os.listdir(stock_dir):
        info = parse_name(name)
        if not info or info["ticker"] != ticker:
            continue
        info["path"] = os.path.join(stock_dir, name)
        info["meta"] = _load_meta(info["path"])
        info["mtime"] = os.path.getmtime(info["path"])
        found.append(info)
    found.sort(key=lambda i: (i["data_asof"], i["run_id"] or "", i["strategy"]))
    return found


def _load_meta(csv_path: str) -> dict | None:
    path = meta_path(csv_path)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def latest(ticker, strategy=None, data_asof=None, allow_stale=False,
           require_meta=True, expect_fingerprint=None,
           allow_any_asof=False, allow_legacy=False, expect_params=None,
           expect_source_fingerprint=None, expect_source_manifest=None):
    """读取指定身份的最新产物；无效的新产物不能回退到更早的有效文件。

    allow_stale 仅把验收失败改为 None，不取消截止日要求。
    allow_any_asof / allow_legacy / require_meta=False 仅供人工诊断。
    生产消费方同时提供行情指纹、参数及完整来源清单。
    """
    if data_asof is None and not allow_any_asof:
        raise ValueError(f"{ticker}: 必须给期望行情截止日 data_asof；仅诊断可 allow_any_asof=True")
    if strategy is not None and strategy not in STRATEGIES:
        raise ValueError(f"未知策略 {strategy!r}")
    items = iter_artifacts(ticker)
    if strategy is not None:
        items = [i for i in items if i['strategy'] == strategy]
    if data_asof is not None:
        items = [i for i in items if i['data_asof'] == str(data_asof)]
    try:
        if not items:
            raise StaleArtifactError(f"{ticker}: 没有行情截止日 {data_asof} 的回测结果，拒绝使用旧结果")
        info = items[-1]
        meta = info['meta']
        diagnostic_legacy = allow_legacy and info['legacy'] and meta is None
        if require_meta and not diagnostic_legacy:
            if not isinstance(meta, dict) or meta.get('schema') != META_SCHEMA:
                raise StaleArtifactError(f"{ticker}: 缺少可用元数据或版本过旧，视为身份不明")
            for key in ('ticker', 'strategy', 'data_asof', 'run_id'):
                if meta.get(key) != info[key]:
                    raise StaleArtifactError(f"{ticker}: 元数据身份不一致或缺失：{key}")
            if not isinstance(meta.get('params'), dict) or not meta.get('params_sha1'):
                raise StaleArtifactError(f"{ticker}: 元数据缺少参数身份")
            if params_fingerprint(meta['params']) != meta['params_sha1']:
                raise StaleArtifactError(f"{ticker}: 参数内容与参数指纹不一致")
            if meta.get('valid') is not True or meta.get('void') is not False:
                raise StaleArtifactError(f"{ticker}: 产物未完成或已作废")
            if not meta.get('csv_sha256') or file_sha256(info['path']) != meta['csv_sha256']:
                raise StaleArtifactError(f"{ticker}: CSV内容与元数据不一致")
        meta = meta if isinstance(meta, dict) else {}
        if expect_fingerprint is not None and meta.get('data_fingerprint') != expect_fingerprint:
            raise StaleArtifactError(f"{ticker}: 行情内容指纹不一致，拒绝使用旧结果")
        if expect_params is not None and meta.get('params_sha1') != params_fingerprint(expect_params):
            raise StaleArtifactError(f"{ticker}: 参数与当前预设不一致，请重跑回测")
        manifest = meta.get('source_manifest') or {}
        if expect_source_fingerprint is not None and manifest.get('source_sha256') != expect_source_fingerprint:
            raise StaleArtifactError(f"{ticker}: 原始行情来源版本不一致")
        if expect_source_manifest is not None and manifest != expect_source_manifest:
            raise StaleArtifactError(f"{ticker}: 行情/指标来源清单不一致，请重算指标和回测")
        return info
    except (StaleArtifactError, OSError) as exc:
        if allow_stale:
            return None
        if isinstance(exc, StaleArtifactError):
            raise
        raise StaleArtifactError(f"{ticker}: 产物读取失败：{exc}") from exc



def _fingerprint_of(info):
    meta = info.get("meta") or {}
    return meta.get("data_fingerprint")


def load_signals(csv_path: str) -> pd.DataFrame:
    if not os.path.exists(csv_path):
        raise StaleArtifactError(f"回测文件不存在: {csv_path}")
    return pd.read_csv(csv_path, encoding="utf-8-sig")


def write_result(ticker, strategy, params, data_asof, signals_df,
                 initial_capital=1000000, position_ratio=0.8,
                 extra=None, run_id=None, data_fingerprint=None, source_manifest=None):
    """写入一份带身份的回测结果，返回 (csv_path, meta_path)。

    signals_df 允许为空（例如该股票本期零交易）；空结果同样落盘，
    这样"本期没交易"会显式覆盖旧结论，而不是让旧文件继续冒充最新。
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy 必须是 {STRATEGIES} 之一，收到 {strategy!r}")
    data_asof = str(data_asof)
    if not re.fullmatch(r"[0-9]{8}", data_asof):
        raise ValueError(f"data_asof 必须是 YYYYMMDD，收到 {data_asof!r}")
    run_id = run_id or (datetime.now().strftime("%Y%m%dT%H%M%S%f") + "-" + uuid4().hex[:8])
    if not re.fullmatch(r"[0-9]{8}T[0-9]{6}(?:[0-9]{6}-[a-f0-9]{8})?", run_id):
        raise ValueError("无效的run_id")
    if not re.fullmatch(r"[0-9]{6}\.[A-Z]{2}", str(ticker)):
        raise ValueError("无效的ticker")

    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    csv_path = os.path.join(
        stock_dir, f"{ticker}_backtest_{strategy}_{data_asof}_{run_id}.csv"
    )
    df = signals_df if signals_df is not None else pd.DataFrame()
    if os.path.exists(csv_path):
        raise FileExistsError(f"运行身份已存在，禁止覆盖：{csv_path}")
    atomic_write_csv(csv_path, df)

    meta = {
        "schema": META_SCHEMA,
        "ticker": ticker,
        "strategy": strategy,
        "params": _canonical_params(params or {}),
        "params_sha1": params_fingerprint(params),
        "data_asof": data_asof,
        "run_id": run_id,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "initial_capital": float(initial_capital),
        "position_ratio": float(position_ratio),
        "rows": int(len(df)),
        "trades": int((df["signal_type"] == "sell").sum()) if "signal_type" in df else 0,
        "data_fingerprint": data_fingerprint,
        "source_manifest": source_manifest,
        "csv_sha256": file_sha256(csv_path),
        "valid": True,
        "void": False,
    }
    if extra:
        if set(extra) & set(meta):
            raise ValueError("extra禁止覆盖核心身份字段")
        meta.update(extra)
    atomic_write_json(meta_path(csv_path), meta)
    return csv_path, meta_path(csv_path)


def _canonical_params(value):
    if isinstance(value, dict):
        return {str(k): _canonical_params(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_canonical_params(v) for v in value]
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError('参数必须为有限值')
        return float(value)
    raise ValueError(f'参数类型不支持：{type(value).__name__}')


def params_fingerprint(params) -> str:
    """统一数值口径，写入前后整数/浮点参数的指纹一致。"""
    payload = json.dumps(_canonical_params(params or {}), sort_keys=True, ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()[:24]


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_write_json(path, value):
    """同目录唯一临时文件原子替换；读者不会读到半份状态。"""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.json-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as fh:
            json.dump(value, fh, ensure_ascii=False, indent=2, allow_nan=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_csv(path, df):
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.csv-', dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8-sig', newline='') as fh:
            df.to_csv(fh, index=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


MARKET_COLUMNS = ('date', 'open', 'high', 'low', 'close', 'volume')
FINGERPRINT_COLUMNS = MARKET_COLUMNS + ('ATR', 'ADX', 'MACD_hist', 'RSI', 'BB_lower', 'BB_upper')


def fingerprint_frame(df, columns=FINGERPRINT_COLUMNS) -> str:
    """完整OHLCV及回测消费指标的规范指纹；来源整文件校验另由provenance负责。"""
    if df is None or len(df) == 0:
        raise ValueError('无法对空行情计算指纹')
    missing = set(MARKET_COLUMNS) - set(df.columns)
    if missing:
        raise ValueError(f'行情缺少必要列：{sorted(missing)}')
    cols = [c for c in columns if c in df.columns]
    dates = pd.to_datetime(df['date'], errors='raise')
    if dates.isna().any() or dates.duplicated().any() or not dates.is_monotonic_increasing:
        raise ValueError('行情日期必须有序、唯一且非空')
    values = []
    for col in cols:
        if col == 'date':
            values.append(dates.dt.strftime('%Y-%m-%d').tolist())
            continue
        numeric = pd.to_numeric(df[col], errors='raise')
        output = []
        for val in numeric:
            if pd.isna(val):
                if col in MARKET_COLUMNS:
                    raise ValueError(f'行情 {col} 含空值')
                output.append(None)
            elif not math.isfinite(float(val)):
                raise ValueError(f'行情 {col} 含非有限值')
            else:
                if col in ('open', 'high', 'low', 'close') and float(val) <= 0:
                    raise ValueError(f'行情 {col} 必须为正数')
                if col == 'volume' and float(val) < 0:
                    raise ValueError('成交量不得为负数')
                output.append(format(float(val), '.17g'))
        values.append(output)
    high, low = pd.to_numeric(df['high']), pd.to_numeric(df['low'])
    if ((low > high) | (pd.to_numeric(df['open']) < low) | (pd.to_numeric(df['open']) > high)
            | (pd.to_numeric(df['close']) < low) | (pd.to_numeric(df['close']) > high)).any():
        raise ValueError('行情OHLC区间无效')
    payload = json.dumps({'version': 2, 'columns': cols, 'values': values}, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def fingerprint_csv(path, columns=FINGERPRINT_COLUMNS):
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path, usecols=lambda c: c in set(columns), float_precision='round_trip')
    return fingerprint_frame(df, columns)


def source_manifest(ticker, data_dir=None):
    """完整输入来源；验证失败必须中止，不能回退仅日期校验。"""
    from indicator_provenance import validate_indicators
    meta = validate_indicators(ticker, data_dir=DATA_DIR if data_dir is None else data_dir)
    return {key: meta[key] for key in
            ('source_sha256', 'indicators_sha256', 'calculator_version', 'data_asof')}


def data_asof_from_frame(df: pd.DataFrame, column: str = "date"):
    """从行情/指标表取最后一行的交易日，作为 data_asof。"""
    if df is None or len(df) == 0:
        raise ValueError("无法从空表推断 data_asof")
    value = pd.to_datetime(df[column].iloc[-1])
    return value.strftime("%Y%m%d")


def summarize_staleness(ticker, expected_asof):
    """给监控/筛选用的诊断摘要：那些产物是新的，那些是旧的。"""
    rows = []
    for info in iter_artifacts(ticker):
        rows.append({
            "file": info["filename"],
            "strategy": info["strategy"],
            "data_asof": info["data_asof"],
            "fresh": info["data_asof"] == str(expected_asof),
            "has_meta": info["meta"] is not None,
        })
    return rows
