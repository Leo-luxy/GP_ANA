# data_collector.py
# -*- coding:utf-8 -*-
"""
Date: 2026/1/9 22:00
Desc: 新浪财经-A股-实时行情数据和历史行情数据(包含前复权和后复权因子)
https://finance.sina.com.cn/realstock/company/sh689009/nc.shtml
"""

import argparse
import json
import os
import re
import random
import shutil
import sys
import time
from datetime import datetime
import pandas as pd
import py_mini_racer
import requests

# 网络代理守护：默认直连、不使用系统代理。否则系统代理（翻墙用）一旦没开，
# 新浪财经的请求就会全部抛 ProxyError，抓取静默失败。
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from net_guard import ensure_network_ready, retry_on_proxy_error

ensure_network_ready()

from akshare.stock.cons import (
    zh_sina_a_stock_payload,
    zh_sina_a_stock_url,
    zh_sina_a_stock_count_url,
    zh_sina_a_stock_hist_url,
    hk_js_decode,
    zh_sina_a_stock_hfq_url,
    zh_sina_a_stock_qfq_url,
    zh_sina_a_stock_amount_url,
)
from akshare.utils import demjson
from akshare.utils.tqdm import get_tqdm


def _get_zh_a_page_count() -> int:
    """
    所有股票的总页数
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 需要采集的股票总页数
    :rtype: int
    """
    res = requests.get(zh_sina_a_stock_count_url)
    page_count = int(re.findall(re.compile(r"\d+"), res.text)[0]) / 80
    if isinstance(page_count, int):
        return page_count
    else:
        return int(page_count) + 1


def stock_zh_a_spot() -> pd.DataFrame:
    """
    新浪财经-所有 A 股的实时行情数据; 重复运行本函数会被新浪暂时封 IP
    https://vip.stock.finance.sina.com.cn/mkt/#hs_a
    :return: 所有股票的实时行情数据
    :rtype: pandas.DataFrame
    """
    big_df = pd.DataFrame()
    page_count = _get_zh_a_page_count()
    zh_sina_stock_payload_copy = zh_sina_a_stock_payload.copy()
    tqdm = get_tqdm()
    for page in tqdm(
        range(1, page_count + 1), leave=False, desc="Please wait for a moment"
    ):
        zh_sina_stock_payload_copy.update({"page": page})
        r = requests.get(zh_sina_a_stock_url, params=zh_sina_stock_payload_copy)
        data_json = demjson.decode(r.text)
        big_df = pd.concat(objs=[big_df, pd.DataFrame(data_json)], ignore_index=True)

    big_df = big_df.astype(
        {
            "trade": "float",
            "pricechange": "float",
            "changepercent": "float",
            "buy": "float",
            "sell": "float",
            "settlement": "float",
            "open": "float",
            "high": "float",
            "low": "float",
            "volume": "float",
            "amount": "float",
            "per": "float",
            "pb": "float",
            "mktcap": "float",
            "nmc": "float",
            "turnoverratio": "float",
        }
    )
    big_df.columns = [
        "代码",
        "_",
        "名称",
        "最新价",
        "涨跌额",
        "涨跌幅",
        "买入",
        "卖出",
        "昨收",
        "今开",
        "最高",
        "最低",
        "成交量",
        "成交额",
        "时间戳",
        "_",
        "_",
        "_",
        "_",
        "_",
    ]
    big_df = big_df[
        [
            "代码",
            "名称",
            "最新价",
            "涨跌额",
            "涨跌幅",
            "买入",
            "卖出",
            "昨收",
            "今开",
            "最高",
            "最低",
            "成交量",
            "成交额",
            "时间戳",
        ]
    ]
    return big_df


def stock_zh_a_daily(
    symbol: str = "sh603843",
    start_date: str = "19900101",
    end_date: str = "21000118",
    adjust: str = "",
) -> pd.DataFrame:
    """
    新浪财经-A 股-个股的历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh603843/nc.shtml
    :param symbol: sh600000
    :type symbol: str
    :param start_date: 20201103; 开始日期
    :type start_date: str
    :param end_date: 20201103; 结束日期
    :type end_date: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据; hfq-factor: 返回后复权因子; qfq-factor: 返回前复权因子
    :type adjust: str
    :return: 行情数据
    :rtype: pandas.DataFrame
    """

    def _fq_factor(method: str) -> pd.DataFrame:
        if method == "hfq":
            r = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
            hfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if hfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            hfq_factor_df.columns = ["date", "hfq_factor"]
            hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
            del hfq_factor_df["date"]
            hfq_factor_df.reset_index(inplace=True)
            return hfq_factor_df
        else:
            r = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
            qfq_factor_df = pd.DataFrame(
                eval(r.text.split("=")[1].split("\n")[0])["data"]
            )
            if qfq_factor_df.shape[0] == 0:
                raise ValueError("sina hfq factor not available")
            qfq_factor_df.columns = ["date", "qfq_factor"]
            qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
            del qfq_factor_df["date"]
            qfq_factor_df.reset_index(inplace=True)
            return qfq_factor_df

    if adjust in ("hfq-factor", "qfq-factor"):
        return _fq_factor(adjust.split("-")[0])

    r = requests.get(zh_sina_a_stock_hist_url.format(symbol))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", r.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df.index = pd.to_datetime(data_df["date"]).dt.date
    del data_df["date"]
    try:
        del data_df["prevclose"]
    except:  # noqa: E722
        pass
    try:
        del data_df["postVol"]
        del data_df["postAmt"]
    except:  # noqa: E722
        pass
    data_df = data_df.astype("float")
    r = requests.get(zh_sina_a_stock_amount_url.format(symbol, symbol))
    amount_data_json = demjson.decode(r.text[r.text.find("[") : r.text.rfind("]") + 1])
    amount_data_df = pd.DataFrame(amount_data_json)
    amount_data_df.columns = ["date", "outstanding_share"]
    amount_data_df.index = pd.to_datetime(amount_data_df.date)
    del amount_data_df["date"]
    temp_df = pd.merge(
        data_df, amount_data_df, left_index=True, right_index=True, how="outer"
    )
    try:
        # try for pandas >= 2.1.0
        temp_df.ffill(inplace=True)
    except Exception:
        try:
            temp_df.fillna(method="ffill", inplace=True)
        except Exception as e:
            print("Error:", e)

    temp_df = temp_df.astype(float)
    temp_df["outstanding_share"] = temp_df["outstanding_share"] * 10000
    temp_df["turnover"] = temp_df["volume"] / temp_df["outstanding_share"]
    temp_df.columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "amount",
        "outstanding_share",
        "turnover",
    ]
    if adjust == "":
        temp_df = temp_df[start_date:end_date]
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df
    if adjust == "hfq":
        res = requests.get(zh_sina_a_stock_hfq_url.format(symbol))
        hfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        hfq_factor_df.columns = ["date", "hfq_factor"]
        hfq_factor_df.index = pd.to_datetime(hfq_factor_df.date)
        del hfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df,
            hfq_factor_df,
            left_index=True,
            right_index=True,
            how="outer",
        )
        try:
            # try for pandas >= 2.1.0
            temp_df.ffill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="ffill", inplace=True)
            except Exception as e:
                print("Error:", e)
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = temp_df["open"] * temp_df["hfq_factor"]
        temp_df["high"] = temp_df["high"] * temp_df["hfq_factor"]
        temp_df["close"] = temp_df["close"] * temp_df["hfq_factor"]
        temp_df["low"] = temp_df["low"] * temp_df["hfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df

    if adjust == "qfq":
        res = requests.get(zh_sina_a_stock_qfq_url.format(symbol))
        qfq_factor_df = pd.DataFrame(
            eval(res.text.split("=")[1].split("\n")[0])["data"]
        )
        qfq_factor_df.columns = ["date", "qfq_factor"]
        qfq_factor_df.index = pd.to_datetime(qfq_factor_df.date)
        del qfq_factor_df["date"]
        temp_df = pd.merge(
            temp_df,
            qfq_factor_df,
            left_index=True,
            right_index=True,
            how="outer",
        )
        try:
            # try for pandas >= 2.1.0
            temp_df.ffill(inplace=True)
        except Exception:
            try:
                # try for pandas < 2.1.0
                temp_df.fillna(method="ffill", inplace=True)
            except Exception as e:
                print("Error:", e)
        temp_df = temp_df.astype(float)
        temp_df.dropna(inplace=True)
        temp_df.drop_duplicates(
            subset=["open", "high", "low", "close", "volume", "amount"], inplace=True
        )
        temp_df["open"] = temp_df["open"] / temp_df["qfq_factor"]
        temp_df["high"] = temp_df["high"] / temp_df["qfq_factor"]
        temp_df["close"] = temp_df["close"] / temp_df["qfq_factor"]
        temp_df["low"] = temp_df["low"] / temp_df["qfq_factor"]
        temp_df = temp_df.iloc[:, :-1]
        temp_df = temp_df[start_date:end_date]
        temp_df["open"] = round(temp_df["open"], 2)
        temp_df["high"] = round(temp_df["high"], 2)
        temp_df["low"] = round(temp_df["low"], 2)
        temp_df["close"] = round(temp_df["close"], 2)
        temp_df.dropna(inplace=True)
        temp_df.reset_index(inplace=True)
        temp_df["date"] = pd.to_datetime(temp_df["date"], errors="coerce").dt.date
        return temp_df


def stock_zh_a_cdr_daily(
    symbol: str = "sh689009",
    start_date: str = "19900101",
    end_date: str = "22201116",
) -> pd.DataFrame:
    """
    新浪财经-A股-CDR个股的历史行情数据, 大量抓取容易封 IP
    https://finance.sina.com.cn/realstock/company/sh689009/nc.shtml
    :param start_date: 20201103; 开始日期
    :type start_date: str
    :param end_date: 20201103; 结束日期
    :type end_date: str
    :param symbol: sh689009
    :type symbol: str
    :return: specific data
    :rtype: pandas.DataFrame
    """
    res = requests.get(zh_sina_a_stock_hist_url.format(symbol))
    js_code = py_mini_racer.MiniRacer()
    js_code.eval(hk_js_decode)
    dict_list = js_code.call(
        "d", res.text.split("=")[1].split(";")[0].replace('"', "")
    )  # 执行js解密代码
    data_df = pd.DataFrame(dict_list)
    data_df.index = pd.to_datetime(data_df["date"])
    del data_df["date"]
    data_df = data_df.astype("float")
    temp_df = data_df[start_date:end_date].copy()
    temp_df["open"] = pd.to_numeric(temp_df["open"])
    temp_df["high"] = pd.to_numeric(temp_df["high"])
    temp_df["low"] = pd.to_numeric(temp_df["low"])
    temp_df["close"] = pd.to_numeric(temp_df["close"])
    temp_df.reset_index(inplace=True)
    temp_df["date"] = temp_df["date"].dt.date
    return temp_df


def stock_zh_a_minute(
    symbol: str = "sh600519", period: str = "1", adjust: str = ""
) -> pd.DataFrame:
    """
    股票及股票指数历史行情数据-分钟数据
    https://finance.sina.com.cn/realstock/company/sh600519/nc.shtml
    :param symbol: sh000300
    :type symbol: str
    :param period: 1, 5, 15, 30, 60 分钟的数据
    :type period: str
    :param adjust: 默认为空: 返回不复权的数据; qfq: 返回前复权后的数据; hfq: 返回后复权后的数据;
    :type adjust: str
    :return: specific data
    :rtype: pandas.DataFrame
    """
    url = (
        "https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData"
    )
    params = {
        "symbol": symbol,
        "scale": period,
        "ma": "no",
        "datalen": "1970",
    }
    r = requests.get(url, params=params)
    data_text = r.text
    try:
        data_json = json.loads(data_text.split("=(")[1].split(");")[0])
        temp_df = pd.DataFrame(data_json).iloc[:, :7]
    except:  # noqa: E722
        url = f"https://quotes.sina.cn/cn/api/jsonp_v2.php/var%20_{symbol}_{period}_1658852984203=/CN_MarketDataService.getKLineData"
        params = {
            "symbol": symbol,
            "scale": period,
            "ma": "no",
            "datalen": "1970",
        }
        r = requests.get(url, params=params)
        data_text = r.text
        data_json = json.loads(data_text.split("=(")[1].split(");")[0])
        temp_df = pd.DataFrame(data_json).iloc[:, :7]
    if temp_df.empty:
        print(f"{symbol} 股票数据不存在，请检查是否已退市")
        return pd.DataFrame()
    try:
        stock_zh_a_daily(symbol=symbol, adjust="qfq")
    except:  # noqa: E722
        return temp_df

    if adjust == "":
        return temp_df

    if adjust == "qfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_a_daily_qfq_df = stock_zh_a_daily(symbol=symbol, adjust="qfq")
        stock_zh_a_daily_qfq_df.index = pd.to_datetime(stock_zh_a_daily_qfq_df["date"])
        result_df = stock_zh_a_daily_qfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume", "amount"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    if adjust == "hfq":
        temp_df[["date", "time"]] = temp_df["day"].str.split(" ", expand=True)
        # 处理没有最后一分钟的情况
        need_df = temp_df[
            [
                True if "09:31:00" <= item <= "15:00:00" else False
                for item in temp_df["time"]
            ]
        ]
        need_df.drop_duplicates(subset=["date"], keep="last", inplace=True)
        need_df.index = pd.to_datetime(need_df["date"])
        stock_zh_a_daily_hfq_df = stock_zh_a_daily(symbol=symbol, adjust="hfq")
        stock_zh_a_daily_hfq_df.index = pd.to_datetime(stock_zh_a_daily_hfq_df["date"])
        result_df = stock_zh_a_daily_hfq_df.iloc[-len(need_df) :, :]["close"].astype(
            float
        ) / need_df["close"].astype(float)
        temp_df.index = pd.to_datetime(temp_df["date"])
        merged_df = pd.merge(temp_df, result_df, left_index=True, right_index=True)
        merged_df["open"] = merged_df["open"].astype(float) * merged_df["close_y"]
        merged_df["high"] = merged_df["high"].astype(float) * merged_df["close_y"]
        merged_df["low"] = merged_df["low"].astype(float) * merged_df["close_y"]
        merged_df["close"] = merged_df["close_x"].astype(float) * merged_df["close_y"]
        temp_df = merged_df[["day", "open", "high", "low", "close", "volume", "amount"]]
        temp_df.reset_index(drop=True, inplace=True)
        return temp_df
    else:
        return pd.DataFrame()


# ============================================================
# 前复权一致性校验与整段重建
# ============================================================
# akshare / 新浪的前复权（qfq）是「以最新价为基准」的复权：除权除息后整段历史
# 都会被重新缩放。如果只在本地文件末尾追加新抓到的片段，新旧片段就是两套基准，
# 拼在一起会凭空出现一天暴跌（2026-06-11 300502.SZ 的 -31.91% 就是送转造成的）。
#
# 所以增量路径必须先抓一段重叠区间核对基准：抓取起点提前到本地末日之前，
# 若重叠日期的收盘价大面积不一致，就判定基准已经变化，拒绝追加并提示用 --rebuild；
# 重建则用同一个 qfq 基准一次抓全历史，校验通过后备份旧文件、原子替换。

OVERLAP_DAYS = 30                    # 增量抓取向前多覆盖的自然日数（约 15~20 个交易日）
MIN_OVERLAP_ROWS = 10                # 至少这么多重叠交易日才足以判定基准是否变化
CLOSE_REL_DIFF_THRESHOLD = 0.005     # 单日收盘价相对差 > 0.5% 记为不一致
BASIS_CHANGE_RATIO_THRESHOLD = 0.02  # 不一致行占重叠行的比例 > 2% 判定基准变化
MIN_REBUILD_ROW_RATIO = 0.9          # 重建后行数不得少于旧文件行数的 90%
DEFAULT_START_DATE = "20230101"      # 本地没有历史文件时的默认起始日

# 退出码约定：0 成功；1 参数不合法；2 取数/写入失败（原有语义）；
# 3 前复权基准变化，已拒绝追加；4 重建数据未通过校验，旧文件未动。
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_FETCH_FAILED = 2
EXIT_BASIS_CHANGED = 3
EXIT_REBUILD_INVALID = 4

QFQ_REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume", "amount")
QFQ_NUMERIC_COLUMNS = ("open", "high", "low", "close", "volume", "amount")

# 旧文件备份目录：GP_ANA_test/backup/qfq/（backup/ 已在 .gitignore 中）
BACKUP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backup", "qfq")


def load_local_qfq(qfq_file):
    """读取本地前复权文件；文件不存在或为空返回 None，解析失败抛异常"""
    if not os.path.exists(qfq_file) or os.path.getsize(qfq_file) == 0:
        return None
    df = pd.read_csv(qfq_file)
    return None if df.empty else df


def normalize_qfq_frame(df):
    """统一日期类型、按日期升序并去重，返回新表（不改入参）"""
    if df is None or df.empty:
        return df
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce")
    out = out[out["date"].notna()]
    out = out.sort_values("date", ascending=True)
    out = out.drop_duplicates(subset=["date"], keep="last")
    return out.reset_index(drop=True)


def compare_qfq_close(local_df, fetched_df, tolerance=CLOSE_REL_DIFF_THRESHOLD,
                      min_rows=MIN_OVERLAP_ROWS):
    """按日期对齐本地数据与本次抓取数据，比较重叠交易日的收盘价。

    返回 dict：
      overlap_rows 重叠交易日数；diff_rows 不一致行数；
      diff_ratio 不一致行占重叠行比例；enough 重叠行数是否达到判定门槛；
      changed 是否判定为前复权基准变化；
      examples 不一致日期示例 [(日期, 本地收盘, 本次抓取收盘, 相对差百分比)]
    """
    result = {"overlap_rows": 0, "diff_rows": 0, "diff_ratio": 0.0,
              "enough": False, "changed": False, "examples": []}
    if local_df is None or fetched_df is None:
        return result
    if local_df.empty or fetched_df.empty:
        return result
    if "date" not in local_df.columns or "close" not in local_df.columns:
        return result
    if "date" not in fetched_df.columns or "close" not in fetched_df.columns:
        return result

    local = pd.DataFrame({
        "date": pd.to_datetime(local_df["date"], errors="coerce"),
        "close": pd.to_numeric(local_df["close"], errors="coerce"),
    }).dropna(subset=["date", "close"])
    fetched = pd.DataFrame({
        "date": pd.to_datetime(fetched_df["date"], errors="coerce"),
        "close": pd.to_numeric(fetched_df["close"], errors="coerce"),
    }).dropna(subset=["date", "close"])
    local = local.drop_duplicates(subset=["date"], keep="last")
    fetched = fetched.drop_duplicates(subset=["date"], keep="last")
    merged = local.merge(fetched, on="date", how="inner", suffixes=("_old", "_new"))

    overlap_rows = len(merged)
    result["overlap_rows"] = overlap_rows
    if overlap_rows == 0:
        return result

    old_close = merged["close_old"].astype(float)
    new_close = merged["close_new"].astype(float)
    # 旧收盘价非正或新值为空时无法比较，按不一致处理
    rel_diff = pd.Series(float("inf"), index=merged.index, dtype=float)
    comparable = (old_close > 0) & new_close.notna()
    rel_diff[comparable] = ((new_close - old_close).abs() / old_close)[comparable]
    mismatch = rel_diff > tolerance

    diff_rows = int(mismatch.sum())
    result["diff_rows"] = diff_rows
    result["diff_ratio"] = diff_rows / overlap_rows
    result["enough"] = overlap_rows >= min_rows
    result["changed"] = bool(result["enough"]
                             and result["diff_ratio"] > BASIS_CHANGE_RATIO_THRESHOLD)
    for _, row in merged[mismatch].sort_values("date").head(5).iterrows():
        old_value = float(row["close_old"])
        new_value = float(row["close_new"])
        pct = (new_value / old_value - 1.0) * 100 if old_value > 0 else float("inf")
        result["examples"].append(
            (row["date"].strftime("%Y-%m-%d"), old_value, new_value, pct)
        )
    return result


def validate_rebuild_frame(new_df, old_df=None):
    """校验准备替换旧文件的重建数据，返回错误信息列表（空列表表示通过）。

    检查项：核心列齐全、日期可解析且唯一升序、核心列无缺失/非数值、
    OHLC 价格为正且满足 high/low 包络关系、行数不少于旧文件的 90%。
    """
    errors = []
    if new_df is None or len(new_df) == 0:
        return ["重建数据为空"]

    missing = [column for column in QFQ_REQUIRED_COLUMNS if column not in new_df.columns]
    if missing:
        return [f"缺少核心列：{', '.join(missing)}"]

    dates = pd.to_datetime(new_df["date"], errors="coerce")
    bad_dates = int(dates.isna().sum())
    if bad_dates:
        errors.append(f"日期无法解析的行数：{bad_dates}")
    else:
        duplicated = int(dates.duplicated(keep=False).sum())
        if duplicated:
            examples = dates[dates.duplicated(keep=False)].dt.strftime("%Y-%m-%d").unique()[:3]
            errors.append(f"日期重复 {duplicated} 行，示例：{', '.join(examples)}")
        if not dates.is_monotonic_increasing:
            errors.append("日期不是严格升序")

    numeric = {}
    for column in QFQ_NUMERIC_COLUMNS:
        values = pd.to_numeric(new_df[column], errors="coerce")
        numeric[column] = values
        invalid = int(values.isna().sum())
        if invalid:
            errors.append(f"列 {column} 存在 {invalid} 行缺失/非数值")

    ohlc = pd.DataFrame({column: numeric[column]
                         for column in ("open", "high", "low", "close")}).dropna()
    if len(ohlc):
        non_positive = int((ohlc <= 0).any(axis=1).sum())
        if non_positive:
            errors.append(f"OHLC 存在 {non_positive} 行非正价格")
        bad_high = int((ohlc["high"] + 1e-6
                        < ohlc[["open", "close", "low"]].max(axis=1)).sum())
        bad_low = int((ohlc["low"] - 1e-6
                       > ohlc[["open", "close", "high"]].min(axis=1)).sum())
        if bad_high:
            errors.append(f"high 小于 open/close/low 的行数：{bad_high}")
        if bad_low:
            errors.append(f"low 大于 open/close/high 的行数：{bad_low}")

    if old_df is not None and len(old_df) > 0:
        old_rows = len(old_df)
        min_rows = old_rows * MIN_REBUILD_ROW_RATIO
        if len(new_df) < min_rows:
            errors.append(
                f"行数不足：重建 {len(new_df)} 行，少于旧文件 {old_rows} 行的"
                f" {MIN_REBUILD_ROW_RATIO:.0%}（{min_rows:.1f} 行）"
            )
    return errors


def rebuild_start_date(local_df):
    """重建起点：本地首日与默认起点 20230101 取更早者"""
    if local_df is None or len(local_df) == 0 or "date" not in local_df.columns:
        return DEFAULT_START_DATE
    dates = pd.to_datetime(local_df["date"], errors="coerce").dropna()
    if len(dates) == 0:
        return DEFAULT_START_DATE
    local_first = dates.min().strftime("%Y%m%d")
    return local_first if local_first < DEFAULT_START_DATE else DEFAULT_START_DATE


def _fetch_qfq_history(stock_symbol, start_date, end_date):
    """抓取一只股票指定区间的前复权行情（代理异常由 net_guard 切换直连后重试）"""
    return retry_on_proxy_error(
        stock_zh_a_daily,
        symbol=stock_symbol,
        start_date=start_date,
        end_date=end_date,
        adjust="qfq",
    )


def _sleep_between_fetches():
    """随机间隔，避免被新浪封 IP"""
    time.sleep(random.uniform(2, 4))


def write_qfq_frame(df, path, header=True, mode="w"):
    """按现有文件格式写出前复权行情（日期 YYYY-MM-DD，utf-8-sig 编码）"""
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    out.to_csv(path, index=False, header=header, encoding="utf-8-sig", mode=mode)


def backup_old_qfq(qfq_file, ticker_code, local_df, backup_dir=None):
    """备份旧前复权文件到 backup/qfq/，返回备份路径；没有旧文件返回 None"""
    if not os.path.exists(qfq_file) or os.path.getsize(qfq_file) == 0:
        return None
    backup_dir = backup_dir or BACKUP_DIR
    if local_df is None or len(local_df) == 0:
        last_text = "unknown"
    else:
        dates = pd.to_datetime(local_df["date"], errors="coerce").dropna()
        last_text = dates.max().strftime("%Y%m%d") if len(dates) else "unknown"
    os.makedirs(backup_dir, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = os.path.join(backup_dir, f"{ticker_code}_{last_text}_{stamp}.csv")
    suffix = 1
    while os.path.exists(backup_file):
        backup_file = os.path.join(
            backup_dir, f"{ticker_code}_{last_text}_{stamp}_{suffix}.csv"
        )
        suffix += 1
    shutil.copy2(qfq_file, backup_file)
    return backup_file


def update_ticker_incremental(ticker_code, qfq_file, stock_symbol, end_date):
    """增量更新一只股票的前复权行情，返回退出码。

    抓取起点提前到本地末日之前，用重叠区间的收盘价核对复权基准；
    基准发生变化时整段历史都被重新缩放，此时追加会产生假跌/假涨，
    因此不写任何数据并返回 EXIT_BASIS_CHANGED，提示用 --rebuild 重建。
    """
    try:
        local_df = load_local_qfq(qfq_file)
    except Exception as exc:
        print(f"读取本地文件失败: {exc}，无法校验复权基准；请用 --rebuild 重建")
        return EXIT_FETCH_FAILED
    if local_df is not None:
        normalized = normalize_qfq_frame(local_df)
        if normalized is None or normalized.empty:
            print("本地文件没有可用日期，无法校验复权基准；请用 --rebuild 重建")
            return EXIT_FETCH_FAILED
        local_df = normalized

    if local_df is not None:
        last_date = local_df["date"].iloc[-1]
        start_date = (last_date - pd.Timedelta(days=OVERLAP_DAYS)).strftime("%Y%m%d")
        print(f"本地末日 {last_date.strftime('%Y-%m-%d')}，向前 {OVERLAP_DAYS} 自然日抓取"
              f"（起点 {start_date}）以核对复权基准")
    else:
        start_date = DEFAULT_START_DATE
        print(f"本地无历史文件，从 {start_date} 开始抓取")

    if start_date > end_date:
        print(f"起始日期 {start_date} 大于结束日期 {end_date}，跳过")
        return EXIT_OK

    _sleep_between_fetches()
    try:
        fetched_df = _fetch_qfq_history(stock_symbol, start_date, end_date)
    except Exception as exc:
        print(f"获取数据出错: {exc}")
        return EXIT_FETCH_FAILED
    if fetched_df is None or len(fetched_df) == 0:
        print("没有获取到数据")
        return EXIT_FETCH_FAILED

    fetched_df = normalize_qfq_frame(fetched_df)
    if fetched_df is None or fetched_df.empty:
        print("获取到的数据没有可用日期")
        return EXIT_FETCH_FAILED

    if local_df is not None:
        comparison = compare_qfq_close(local_df, fetched_df)
        print(f"复权基准核对：重叠 {comparison['overlap_rows']} 个交易日，"
              f"收盘价不一致 {comparison['diff_rows']} 行"
              f"（{comparison['diff_ratio']:.2%}）")
        if comparison["changed"]:
            print("判定为前复权基准变化：本次抓取的收盘价与本地历史在重叠区间大面积不一致")
            print(f"  判定标准：重叠 >= {MIN_OVERLAP_ROWS} 行且不一致比例"
                  f" > {BASIS_CHANGE_RATIO_THRESHOLD:.0%}"
                  f"（单行相对差 > {CLOSE_REL_DIFF_THRESHOLD:.1%} 记为不一致）")
            for date_text, old_close, new_close, pct in comparison["examples"]:
                print(f"  受影响日期示例 {date_text}: 本地 {old_close:.2f}"
                      f" → 本次抓取 {new_close:.2f}（{pct:+.2f}%）")
            print("  本次不追加任何数据；请执行重建："
                  f"python data_collector.py --ticker {ticker_code} --rebuild")
            return EXIT_BASIS_CHANGED
        if not comparison["enough"]:
            print(f"重叠交易日少于 {MIN_OVERLAP_ROWS} 行，本次跳过复权基准判定"
                  "（若怀疑除权除息导致基准变化，请用 --rebuild 重建）")
        new_rows = fetched_df[fetched_df["date"] > local_df["date"].iloc[-1]]
    else:
        new_rows = fetched_df

    new_rows = new_rows.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    if new_rows.empty:
        print("没有新数据需要写入")
        return EXIT_OK

    # 追加前核对列结构，避免两套列顺序拼进同一个文件
    if local_df is not None and list(new_rows.columns) != list(local_df.columns):
        print("本地文件列结构与本次抓取不一致（"
              f"本地 {len(local_df.columns)} 列 / 本次抓取 {len(new_rows.columns)} 列），"
              "拒绝追加；请用 --rebuild 重建")
        return EXIT_FETCH_FAILED

    try:
        write_qfq_frame(new_rows, qfq_file, header=local_df is None, mode="a")
    except Exception as exc:
        print(f"写入文件失败: {exc}")
        return EXIT_FETCH_FAILED

    first_new = new_rows["date"].iloc[0].strftime("%Y-%m-%d")
    last_new = new_rows["date"].iloc[-1].strftime("%Y-%m-%d")
    print(f"复权基准一致，追加 {len(new_rows)} 条数据到 {qfq_file}（{first_new} 至 {last_new}）")
    return EXIT_OK


def rebuild_ticker(ticker_code, qfq_file, stock_symbol, end_date, backup_dir=None):
    """用统一 qfq 基准重抓一只股票的完整历史，校验后备份旧文件并原子替换，返回退出码。

    抓取起点取「本地首日」与默认起点 20230101 中更早的一个，保证重建覆盖原有历史；
    新数据先写 <qfq>.tmp，校验通过才备份旧文件并 os.replace，校验失败旧文件保持不变。
    """
    try:
        old_df = load_local_qfq(qfq_file)
    except Exception as exc:
        print(f"读取旧文件失败: {exc}，无法做行数与备份校验，本次不执行重建")
        return EXIT_REBUILD_INVALID
    if old_df is not None:
        normalized = normalize_qfq_frame(old_df)
        old_df = normalized if normalized is not None and not normalized.empty else None

    start_date = rebuild_start_date(old_df)
    print(f"重建 {ticker_code}：从 {start_date} 到 {end_date} 抓取完整前复权历史")
    if start_date > end_date:
        print(f"起始日期 {start_date} 大于结束日期 {end_date}，跳过")
        return EXIT_OK

    _sleep_between_fetches()
    try:
        fetched_df = _fetch_qfq_history(stock_symbol, start_date, end_date)
    except Exception as exc:
        print(f"获取数据出错: {exc}")
        return EXIT_FETCH_FAILED
    if fetched_df is None or len(fetched_df) == 0:
        print("没有获取到数据")
        return EXIT_FETCH_FAILED

    tmp_file = qfq_file + ".tmp"
    backup_file = None
    try:
        try:
            write_qfq_frame(fetched_df, tmp_file)
        except Exception as exc:
            print(f"重建校验失败：临时文件写入失败（{exc}），旧文件保持不变")
            return EXIT_REBUILD_INVALID

        try:
            written_df = pd.read_csv(tmp_file, encoding="utf-8-sig")
        except Exception as exc:
            print(f"重建校验失败：临时文件无法读回（{exc}），旧文件保持不变")
            return EXIT_REBUILD_INVALID

        errors = validate_rebuild_frame(written_df, old_df)
        if errors:
            print("重建校验失败，旧文件保持不变，原因：")
            for message in errors:
                print(f"  - {message}")
            return EXIT_REBUILD_INVALID

        comparison = compare_qfq_close(old_df, written_df)
        if comparison["overlap_rows"]:
            print(f"重建数据与旧文件重叠 {comparison['overlap_rows']} 个交易日，"
                  f"收盘价不同 {comparison['diff_rows']} 行"
                  "（新旧复权基准差异，属预期）")

        try:
            backup_file = backup_old_qfq(qfq_file, ticker_code, old_df, backup_dir)
            os.replace(tmp_file, qfq_file)
        except Exception as exc:
            print(f"重建失败：备份或替换文件时出错（{exc}），旧文件保持不变")
            return EXIT_REBUILD_INVALID
    finally:
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass

    rows = len(written_df)
    first_date = pd.to_datetime(written_df["date"].iloc[0]).strftime("%Y-%m-%d")
    last_date = pd.to_datetime(written_df["date"].iloc[-1]).strftime("%Y-%m-%d")
    if backup_file:
        print(f"重建成功：{rows} 条（{first_date} 至 {last_date}）；"
              f"旧文件已备份到 {backup_file}，新文件已原子替换")
    else:
        print(f"重建成功：{rows} 条（{first_date} 至 {last_date}）；本地原先没有旧文件")
    return EXIT_OK


def _load_config():
    """延迟导入配置，便于测试注入临时数据目录"""
    from config import STOCK_TICKERS, DATA_DIR
    return STOCK_TICKERS, DATA_DIR


def _resolve_ticker_name(ticker_code, stock_tickers):
    """在配置中查找股票名称，找不到就用代码本身"""
    for name, code in stock_tickers.items():
        if code == ticker_code:
            return name
    return ticker_code


def _build_stock_symbol(ticker_code):
    """把 600519.SH 这类代码转换成新浪接口使用的 sh600519 / sz000001"""
    short_code = ticker_code.split(".")[0]
    market = "sh" if ticker_code.endswith(".SH") else "sz"
    return f"{market}{short_code}"


def _summarize_exit_code(results, ticker_list, rebuild, single):
    """汇总各股票的处理结果，返回进程退出码（3 优先于 2，4 优先于 2）"""
    basis_changed = [t for t, code in results if code == EXIT_BASIS_CHANGED]
    invalid = [t for t, code in results if code == EXIT_REBUILD_INVALID]
    failed = [t for t, code in results if code == EXIT_FETCH_FAILED]

    if rebuild:
        if invalid:
            print(f"重建校验失败 {len(invalid)} 只：{invalid}（旧文件均未被替换）")
        if failed:
            print(f"取数失败 {len(failed)} 只：{failed}")
        if invalid:
            return EXIT_REBUILD_INVALID
        if failed:
            return EXIT_FETCH_FAILED
        return EXIT_OK

    if basis_changed:
        print(f"复权基准变化 {len(basis_changed)} 只：{basis_changed}；"
              "这些股票未追加新数据，请用 --rebuild 重建")
    if failed:
        print(f"取数失败 {len(failed)} 只：{failed}")
    if basis_changed:
        return EXIT_BASIS_CHANGED
    # 保持原有语义：单只模式失败即非 0，批量模式仅在全部失败时非 0
    if failed and (single or len(failed) == len(ticker_list)):
        return EXIT_FETCH_FAILED
    return EXIT_OK


def main(argv=None):
    parser = argparse.ArgumentParser(description="股票数据收集器")
    parser.add_argument('--ticker', help="股票代码，例如：600519.SH（上交所）、000001.SZ（深交所），默认处理所有股票")
    parser.add_argument('--rebuild', action='store_true', help="用统一前复权基准重建指定股票的完整历史（需配合 --ticker）")
    parser.add_argument('--rebuild-all', action='store_true', help="重建配置中全部股票的完整历史；批量操作必须再加 --yes")
    parser.add_argument('--yes', action='store_true', help="确认执行 --rebuild-all 批量重建")
    args = parser.parse_args(argv)

    try:
        stock_tickers, data_dir = _load_config()
    except Exception as exc:
        print(f"读取配置失败: {exc}")
        return EXIT_USAGE

    if args.rebuild_all:
        if args.ticker:
            print("--rebuild-all 会处理配置中的全部股票，不能同时指定 --ticker")
            return EXIT_USAGE
        if not args.yes:
            print("批量重建会重抓配置中全部股票的历史数据，请显式加 --yes 确认")
            return EXIT_USAGE
        ticker_list = list(dict.fromkeys(stock_tickers.values()))
        rebuild = True
        print(f"批量重建模式，共 {len(ticker_list)} 只股票")
    elif args.rebuild:
        if not args.ticker:
            print("--rebuild 默认只重建单只股票，请用 --ticker 指定；"
                  "批量重建请用 --rebuild-all --yes")
            return EXIT_USAGE
        ticker_list = [args.ticker]
        rebuild = True
    else:
        rebuild = False
        if args.ticker:
            ticker_list = [args.ticker]
        else:
            ticker_list = list(stock_tickers.values())
            print(f"批量处理所有股票，共 {len(ticker_list)} 只")

    if not ticker_list:
        print("没有需要处理的股票")
        return EXIT_OK

    results = []
    for ticker_code in ticker_list:
        ticker_name = _resolve_ticker_name(ticker_code, stock_tickers)
        print(f"处理股票: {ticker_code} ({ticker_name})")

        stock_symbol = _build_stock_symbol(ticker_code)
        stock_dir = os.path.join(data_dir, ticker_code)
        if not os.path.exists(stock_dir):
            os.makedirs(stock_dir)
        qfq_file = os.path.join(stock_dir, f"{ticker_code}_qfq.csv")
        end_date = datetime.now().strftime("%Y%m%d")

        if rebuild:
            code = rebuild_ticker(ticker_code, qfq_file, stock_symbol, end_date)
        else:
            code = update_ticker_incremental(ticker_code, qfq_file, stock_symbol, end_date)
        results.append((ticker_code, code))

        print()  # 空行分隔不同股票的输出

    return _summarize_exit_code(results, ticker_list, rebuild, single=bool(args.ticker))


if __name__ == "__main__":
    sys.exit(main())
