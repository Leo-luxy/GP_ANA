# -*- coding:utf-8 -*-
"""data_collector 前复权一致性校验与整段重建的单元测试。

说明
----
新浪 / akshare 的前复权以最新价为基准，除权除息后整段历史会被重新缩放；
增量追加必须先用重叠区间核对基准，否则新旧片段拼接会凭空出现假跌/假涨。
本文件用 unittest.mock 替换真实抓取函数，不联网；数据目录与备份目录
都指向 tempfile 临时目录，不会写入真实 data/ 和 backup/。
"""

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

import pandas as pd

import data_collector as dc


TICKER = "000001.SZ"
OTHER_TICKER = "600000.SH"
COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount"]


def business_days(start, count):
    """从 start 起生成 count 个工作日（只跳过周末，够构造重叠区间）"""
    days = []
    current = start
    while len(days) < count:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def make_qfq_frame(dates, closes):
    """按日期与收盘价构造 OHLC 合法、日期升序的行情表（日期为 datetime.date）"""
    rows = []
    for day, close in zip(dates, closes):
        close = round(float(close), 2)
        open_price = round(close * 0.99, 2)
        high = round(max(open_price, close) * 1.02, 2)
        low = round(min(open_price, close) * 0.98, 2)
        rows.append({
            "date": day,
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": 1000000.0,
            "amount": 10000000.0,
        })
    return pd.DataFrame(rows, columns=COLUMNS)


def read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig")


class CollectorTestBase(unittest.TestCase):
    """把抓取函数、随机 sleep、数据目录和备份目录都替换成临时实现"""

    def setUp(self):
        self.tmp_root = tempfile.mkdtemp(prefix="gpana_collector_")
        self.addCleanup(shutil.rmtree, self.tmp_root, True)
        self.data_dir = os.path.join(self.tmp_root, "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.backup_dir = os.path.join(self.tmp_root, "backup", "qfq")
        self.stock_dir = os.path.join(self.data_dir, TICKER)
        os.makedirs(self.stock_dir, exist_ok=True)
        self.qfq_file = os.path.join(self.stock_dir, f"{TICKER}_qfq.csv")

        self.config_tickers = {}
        self.fetch_calls = []
        self.fetch_result = pd.DataFrame()

        def fake_fetch(symbol, start_date, end_date, adjust=""):
            self.fetch_calls.append({
                "symbol": symbol,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
            })
            if isinstance(self.fetch_result, Exception):
                raise self.fetch_result
            return self.fetch_result.copy()

        patchers = [
            mock.patch.object(dc, "stock_zh_a_daily", side_effect=fake_fetch),
            mock.patch.object(dc, "_sleep_between_fetches"),
            mock.patch.object(dc, "BACKUP_DIR", self.backup_dir),
            mock.patch.object(
                dc, "_load_config",
                side_effect=lambda: (self.config_tickers, self.data_dir),
            ),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)

    # ---- 辅助方法 ----
    def write_local(self, frame):
        dc.write_qfq_frame(frame, self.qfq_file)
        return self.qfq_file

    def read_local(self):
        return read_csv(self.qfq_file)

    def file_bytes(self):
        with open(self.qfq_file, "rb") as handle:
            return handle.read()

    def run_main(self, argv):
        """调用命令行入口并捕获输出，返回 (退出码, 输出文本)"""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = dc.main(argv)
        return code, output.getvalue()

    def local_frame(self, start=date(2026, 9, 1), rows=40):
        return make_qfq_frame(
            business_days(start, rows),
            [10.0 + index * 0.1 for index in range(rows)],
        )


class IncrementalUpdateTest(CollectorTestBase):
    """增量路径：一致则追加且不重复，基准变化则拒绝并退出码 3"""

    def test_consistent_basis_appends_only_new_dates(self):
        local = self.local_frame()
        self.write_local(local)
        local_last = pd.to_datetime(local["date"].iloc[-1])

        overlap = local.iloc[-20:].copy()
        new_days = business_days(local_last.date() + timedelta(days=1), 5)
        new_closes = [10.0 + (len(local) + index) * 0.1 for index in range(5)]
        self.fetch_result = pd.concat(
            [overlap, make_qfq_frame(new_days, new_closes)], ignore_index=True
        )

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_OK, output)
        self.assertIn("复权基准一致", output)
        self.assertEqual(len(self.fetch_calls), 1)
        expected_start = (local_last - pd.Timedelta(days=dc.OVERLAP_DAYS)).strftime("%Y%m%d")
        self.assertEqual(self.fetch_calls[0]["start_date"], expected_start)
        self.assertEqual(self.fetch_calls[0]["adjust"], "qfq")
        self.assertEqual(self.fetch_calls[0]["symbol"], "sz000001")

        saved = self.read_local()
        self.assertEqual(len(saved), len(local) + 5)
        dates = pd.to_datetime(saved["date"])
        self.assertTrue(dates.is_unique)
        self.assertTrue(dates.is_monotonic_increasing)
        self.assertEqual(dates.iloc[-1].strftime("%Y-%m-%d"),
                         pd.to_datetime(new_days[-1]).strftime("%Y-%m-%d"))
        # 旧历史必须原样保留，不能被重新缩放
        self.assertEqual(saved["close"].iloc[:len(local)].round(2).tolist(),
                         local["close"].round(2).tolist())

    def test_second_incremental_run_does_not_duplicate(self):
        local = self.local_frame()
        self.write_local(local)
        before = self.file_bytes()
        # 只返回重叠区间、没有新日期，跑两次都不应改动文件
        self.fetch_result = local.iloc[-15:].copy()

        code1, output1 = self.run_main(["--ticker", TICKER])
        code2, output2 = self.run_main(["--ticker", TICKER])

        self.assertEqual(code1, dc.EXIT_OK, output1)
        self.assertEqual(code2, dc.EXIT_OK, output2)
        self.assertIn("没有新数据需要写入", output1)
        self.assertEqual(self.file_bytes(), before)
        saved = self.read_local()
        self.assertEqual(len(saved), len(local))
        self.assertEqual(len(saved["date"].unique()), len(saved))

    def test_basis_change_exits_3_without_touching_file(self):
        local = self.local_frame()
        self.write_local(local)
        before = self.file_bytes()

        # 模拟除权除息后整段历史按 1/1.4 重新缩放（与真实送转断点同性质）
        overlap = local.iloc[-20:].copy()
        for column in ("open", "high", "low", "close"):
            overlap[column] = (overlap[column] / 1.4).round(2)
        self.fetch_result = overlap

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_BASIS_CHANGED, output)
        self.assertIn("前复权基准变化", output)
        self.assertIn("受影响日期示例", output)
        self.assertIn("--rebuild", output)
        self.assertEqual(self.file_bytes(), before)
        self.assertEqual(len(self.read_local()), len(local))

    def test_first_fetch_writes_full_history(self):
        self.assertFalse(os.path.exists(self.qfq_file))
        days = business_days(date(2023, 1, 3), 30)
        self.fetch_result = make_qfq_frame(
            days, [12.0 + index * 0.1 for index in range(30)]
        )

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_OK, output)
        self.assertEqual(self.fetch_calls[0]["start_date"], dc.DEFAULT_START_DATE)
        saved = self.read_local()
        self.assertEqual(len(saved), 30)
        self.assertEqual(list(saved.columns), COLUMNS)
        self.assertIn("追加 30 条数据", output)

    def test_column_mismatch_exits_2_without_writing(self):
        local = self.local_frame()
        self.write_local(local)
        before = self.file_bytes()

        overlap = local.iloc[-10:].copy()
        local_last = pd.to_datetime(local["date"].iloc[-1]).date()
        new_rows = make_qfq_frame(
            business_days(local_last + timedelta(days=1), 3), [14.0, 14.1, 14.2]
        )
        mismatched = pd.concat([overlap, new_rows], ignore_index=True)
        mismatched["turnover"] = 0.01
        self.fetch_result = mismatched

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_FETCH_FAILED, output)
        self.assertIn("列结构", output)
        self.assertEqual(self.file_bytes(), before)

    def test_fetch_failure_exits_2_and_keeps_file(self):
        local = self.local_frame()
        self.write_local(local)
        before = self.file_bytes()
        self.fetch_result = pd.DataFrame()

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_FETCH_FAILED, output)
        self.assertIn("没有获取到数据", output)
        self.assertEqual(self.file_bytes(), before)

    def test_fetch_exception_exits_2_and_keeps_file(self):
        local = self.local_frame()
        self.write_local(local)
        before = self.file_bytes()
        self.fetch_result = RuntimeError("网络不可用")

        code, output = self.run_main(["--ticker", TICKER])

        self.assertEqual(code, dc.EXIT_FETCH_FAILED, output)
        self.assertIn("获取数据出错", output)
        self.assertEqual(self.file_bytes(), before)


class CompareQfqCloseTest(unittest.TestCase):
    """判定阈值：重叠行数不足不判定；不一致比例必须严格大于 2%"""

    def test_min_overlap_rows_required(self):
        days = business_days(date(2026, 1, 5), 9)
        comparison = dc.compare_qfq_close(
            make_qfq_frame(days, [10.0] * 9),
            make_qfq_frame(days, [9.0] * 9),
        )
        self.assertEqual(comparison["overlap_rows"], 9)
        self.assertFalse(comparison["enough"])
        self.assertFalse(comparison["changed"])

        days = business_days(date(2026, 1, 5), 10)
        comparison = dc.compare_qfq_close(
            make_qfq_frame(days, [10.0] * 10),
            make_qfq_frame(days, [9.0] * 10),
        )
        self.assertEqual(comparison["overlap_rows"], 10)
        self.assertTrue(comparison["enough"])
        self.assertTrue(comparison["changed"])

    def test_diff_ratio_threshold_is_strict(self):
        days = business_days(date(2026, 1, 5), 100)
        local = make_qfq_frame(days, [10.0] * 100)

        closes = [10.0] * 100
        closes[0] = 10.2
        closes[1] = 10.2
        comparison = dc.compare_qfq_close(local, make_qfq_frame(days, closes))
        self.assertEqual(comparison["diff_rows"], 2)
        self.assertAlmostEqual(comparison["diff_ratio"], 0.02)
        self.assertFalse(comparison["changed"])  # 恰好 2% 不判定，必须大于阈值

        closes[2] = 10.2
        comparison = dc.compare_qfq_close(local, make_qfq_frame(days, closes))
        self.assertEqual(comparison["diff_rows"], 3)
        self.assertTrue(comparison["changed"])
        self.assertLessEqual(len(comparison["examples"]), 5)
        self.assertEqual(len(comparison["examples"][0]), 4)


class ValidateRebuildFrameTest(unittest.TestCase):
    """重建数据校验：行数 90% 边界、OHLC 包络、日期唯一升序"""

    def test_row_count_boundary(self):
        old = make_qfq_frame(business_days(date(2023, 3, 1), 100), [10.0] * 100)
        exact = make_qfq_frame(business_days(date(2023, 1, 3), 90), [10.0] * 90)
        self.assertEqual(dc.validate_rebuild_frame(exact, old), [])
        shorter = make_qfq_frame(business_days(date(2023, 1, 3), 89), [10.0] * 89)
        self.assertTrue(dc.validate_rebuild_frame(shorter, old))

    def test_invalid_ohlc_and_duplicate_dates(self):
        frame = make_qfq_frame(business_days(date(2023, 1, 3), 20), [10.0] * 20)
        bad_high = frame.copy()
        bad_high.loc[0, "high"] = bad_high.loc[0, "close"] - 1.0
        errors = dc.validate_rebuild_frame(bad_high)
        self.assertTrue(any("high" in message for message in errors), errors)

        duplicate = frame.copy()
        duplicate.loc[1, "date"] = duplicate.loc[0, "date"]
        errors = dc.validate_rebuild_frame(duplicate)
        self.assertTrue(any("日期重复" in message for message in errors), errors)


class RebuildTest(CollectorTestBase):
    """--rebuild：成功时备份并原子替换；校验失败时旧文件字节不变且无 tmp"""

    def old_frame(self):
        return make_qfq_frame(
            business_days(date(2023, 3, 1), 60),
            [20.0 + index * 0.02 for index in range(60)],
        )

    def full_rebuild_frame(self, rows=200, base=18.0):
        return make_qfq_frame(
            business_days(date(2023, 1, 3), rows),
            [base + index * 0.02 for index in range(rows)],
        )

    def test_rebuild_success_backs_up_and_replaces(self):
        old = self.old_frame()
        self.write_local(old)
        old_bytes = self.file_bytes()
        self.fetch_result = self.full_rebuild_frame()

        code, output = self.run_main(["--ticker", TICKER, "--rebuild"])

        self.assertEqual(code, dc.EXIT_OK, output)
        self.assertIn("重建成功", output)
        self.assertEqual(self.fetch_calls[0]["start_date"], dc.DEFAULT_START_DATE)
        self.assertEqual(self.fetch_calls[0]["adjust"], "qfq")

        saved = self.read_local()
        self.assertEqual(len(saved), 200)
        self.assertEqual(list(saved.columns), COLUMNS)
        dates = pd.to_datetime(saved["date"])
        self.assertTrue(dates.is_unique)
        self.assertTrue(dates.is_monotonic_increasing)

        backups = os.listdir(self.backup_dir)
        self.assertEqual(len(backups), 1, backups)
        old_last = pd.to_datetime(old["date"].iloc[-1]).strftime("%Y%m%d")
        self.assertTrue(backups[0].startswith(f"{TICKER}_{old_last}_"), backups[0])
        self.assertTrue(backups[0].endswith(".csv"))
        with open(os.path.join(self.backup_dir, backups[0]), "rb") as handle:
            self.assertEqual(handle.read(), old_bytes)
        self.assertFalse(os.path.exists(self.qfq_file + ".tmp"))

    def test_rebuild_start_uses_earlier_local_first(self):
        old = make_qfq_frame(business_days(date(2022, 6, 1), 20), [15.0] * 20)
        self.write_local(old)
        self.fetch_result = make_qfq_frame(
            business_days(date(2022, 6, 1), 120), [14.0] * 120
        )

        code, output = self.run_main(["--ticker", TICKER, "--rebuild"])

        self.assertEqual(code, dc.EXIT_OK, output)
        self.assertEqual(self.fetch_calls[0]["start_date"], "20220601")

    def test_backup_without_parseable_dates_still_copies(self):
        self.write_local(self.local_frame(rows=5))
        backup_path = dc.backup_old_qfq(self.qfq_file, TICKER, None, self.backup_dir)
        self.assertIsNotNone(backup_path)
        self.assertIn("_unknown_", os.path.basename(backup_path))
        self.assertTrue(os.path.exists(backup_path))

    def test_rebuild_validation_failure_keeps_old_file(self):
        old = self.old_frame()
        self.write_local(old)
        old_bytes = self.file_bytes()
        valid = self.full_rebuild_frame()

        too_few = valid.iloc[:20].copy()
        duplicate = valid.copy()
        duplicate.loc[1, "date"] = duplicate.loc[0, "date"]
        bad_ohlc = valid.copy()
        bad_ohlc.loc[3, "high"] = bad_ohlc.loc[3, "close"] - 1.0
        missing_column = valid.drop(columns=["amount"])
        not_ascending = valid.copy()
        not_ascending.loc[0, "date"], not_ascending.loc[1, "date"] = (
            not_ascending.loc[1, "date"], not_ascending.loc[0, "date"])

        variants = {
            "行数不足": too_few,
            "日期重复": duplicate,
            "OHLC非法": bad_ohlc,
            "缺少核心列": missing_column,
            "日期乱序": not_ascending,
        }
        for name, frame in variants.items():
            with self.subTest(name=name):
                self.fetch_result = frame
                code, output = self.run_main(["--ticker", TICKER, "--rebuild"])
                self.assertEqual(code, dc.EXIT_REBUILD_INVALID, output)
                self.assertIn("重建校验失败", output)
                self.assertEqual(self.file_bytes(), old_bytes)
                self.assertFalse(os.path.exists(self.qfq_file + ".tmp"))
                self.assertFalse(os.path.exists(self.backup_dir))


class CliGuardTest(CollectorTestBase):
    """命令行保护：批量重建必须显式 --yes；--rebuild 必须指定单只"""

    def test_rebuild_all_requires_yes(self):
        code, output = self.run_main(["--rebuild-all"])
        self.assertEqual(code, dc.EXIT_USAGE)
        self.assertIn("--yes", output)
        self.assertEqual(self.fetch_calls, [])

    def test_rebuild_requires_ticker(self):
        code, output = self.run_main(["--rebuild"])
        self.assertEqual(code, dc.EXIT_USAGE)
        self.assertIn("--ticker", output)
        self.assertEqual(self.fetch_calls, [])

    def test_rebuild_all_with_yes_processes_configured_tickers(self):
        self.config_tickers = {"a": TICKER, "b": OTHER_TICKER}
        self.fetch_result = make_qfq_frame(
            business_days(date(2023, 1, 3), 80),
            [10.0 + index * 0.01 for index in range(80)],
        )

        code, output = self.run_main(["--rebuild-all", "--yes"])

        self.assertEqual(code, dc.EXIT_OK, output)
        self.assertEqual(len(self.fetch_calls), 2)
        for ticker in (TICKER, OTHER_TICKER):
            path = os.path.join(self.data_dir, ticker, f"{ticker}_qfq.csv")
            self.assertTrue(os.path.exists(path), path)
            self.assertEqual(len(read_csv(path)), 80)


if __name__ == "__main__":
    unittest.main()
