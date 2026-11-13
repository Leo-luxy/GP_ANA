# tests/test_data_freshness.py
# 数据更新后内容日期复核与时效分级的回归测试。
#
# 覆盖点：
#   * 更新命令返回 0 但内容日期没有前进 → 判失败并打印「命令成功但内容未更新」；
#   * 资金流等允许滞后 1 个交易日 → 刚好滞后 1 天视为达标，不再触发更新；
#   * 滞后超过分级阈值 → 判失败；
#   * 失败清单汇总后 main 返回非 0 退出码；
#   * 时效分级表（默认值/单项覆盖/--freshness-config）确实驱动判定；
#   * 交易日历钩子注入、16:00 与周末近似、无日历时打印提示；
#   * 各数据源内容日期列的解析、财务类按报告季度判定、mtime 兜底仅限允许的数据项。
#
# 全部用 tempfile 构造数据文件并 mock 命令执行，不写真实 data/ 目录，不联网。

import io
import json
import os
import shutil
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from datetime import date, datetime, timedelta
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import check_data_updates as cdu

TICKER = '000001.SZ'
EXPECTED = date(2026, 11, 12)      # 周四：期望交易日
PREV_TRADE_DAY = date(2026, 11, 11)  # 周三：滞后 1 个交易日
TWO_DAYS_BEFORE = date(2026, 11, 10)  # 周二：滞后 2 个交易日
STALE_DAY = date(2026, 11, 4)      # 明显滞后


class FreshnessTestBase(unittest.TestCase):
    """公共夹具：临时 data 目录 + 恢复时效表/日历钩子。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gpana_freshness_')
        self.saved_data_dir = cdu.DATA_DIR
        cdu.DATA_DIR = self.tmpdir
        cdu.reset_freshness_rules()
        cdu.clear_trade_calendar_hook()
        self.addCleanup(self._cleanup)
        # 本组仅测时效规则；来源版本门禁由 test_degraded_evidence 独立覆盖。
        self.provenance = mock.patch('indicator_provenance.validate_indicators', return_value={})
        self.provenance.start()
        self.addCleanup(self.provenance.stop)

    def _cleanup(self):
        cdu.DATA_DIR = self.saved_data_dir
        cdu.reset_freshness_rules()
        cdu.clear_trade_calendar_hook()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ---------- 构造测试数据文件 ----------
    def _stock_dir(self):
        path = os.path.join(self.tmpdir, TICKER)
        os.makedirs(path, exist_ok=True)
        return path

    def _write_csv(self, filename, rows, header):
        path = os.path.join(self._stock_dir(), filename)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(header + '\n')
            for row in rows:
                f.write(row + '\n')
        return path

    def _daily_file(self, item, content_date):
        """按数据项写日更 CSV，列名与真实数据源保持一致。"""
        mapping = {
            'qfq': (f'{TICKER}_qfq.csv', 'date,open,close', '{d},10,10.5'),
            'indicators': (f'{TICKER}_indicators.csv', 'date,close', '{d},10.5'),
            'fund_flow': (f'{TICKER}_fund_flow.csv', '日期,主力净流入-净额', '{d},100'),
            'margin_data': (f'{TICKER}_margin_data.csv', 'date,融资余额', '{d},100'),
            'valuation': (f'{TICKER}_valuation.csv', '数据日期,市盈率', '{d},10'),
            'shareholder_num': (f'{TICKER}_shareholder_num.csv', 'END_DATE,HOLDER_TOTAL_NUM', '{d},1000'),
        }
        filename, header, row_tpl = mapping[item]
        return self._write_csv(filename, [row_tpl.format(d=content_date.isoformat())], header)

    def _prepare_daily(self, overrides=None):
        """把 5 个日更文件都写成达标日期，再按 overrides 覆盖个别数据项。"""
        overrides = overrides or {}
        for item in cdu.DAILY_DATA_FILES:
            self._daily_file(item, overrides.get(item, EXPECTED))


class PostUpdateReverifyTest(FreshnessTestBase):
    """命令返回 0 不等于数据已更新，必须重新读取内容日期复核。"""

    def test_command_success_but_content_not_updated_is_failure(self):
        # 行情停在上一交易日；更新命令返回 0 却没有改写文件
        self._prepare_daily()
        self._daily_file('qfq', PREV_TRADE_DAY)
        output = io.StringIO()
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')):
            with redirect_stdout(output):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)

        self.assertEqual(len(failures), 1, failures)
        failure = failures[0]
        self.assertIn('qfq', failure)
        self.assertIn('命令成功但内容未更新', failure)
        self.assertIn(PREV_TRADE_DAY.isoformat(), failure)
        # 同时必须打印出来，不能只留在返回值里
        self.assertIn('命令成功但内容未更新', output.getvalue())

    def test_command_success_and_content_refreshed_passes(self):
        self._prepare_daily()
        self._daily_file('qfq', PREV_TRADE_DAY)

        def fake_run(cmd, cwd=None):
            # 模拟更新命令把行情补到期望交易日
            self._daily_file('qfq', EXPECTED)
            return True, ''

        with mock.patch.object(cdu, 'run_command', side_effect=fake_run):
            with redirect_stdout(io.StringIO()):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)
        self.assertEqual(failures, [])

    def test_command_failure_reported(self):
        self._prepare_daily()
        self._daily_file('qfq', PREV_TRADE_DAY)
        with mock.patch.object(cdu, 'run_command',
                               return_value=(False, 'returncode=2；输出末尾: 取数失败')):
            with redirect_stdout(io.StringIO()):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn('更新失败', failures[0])
        self.assertIn('returncode=2', failures[0])
        self.assertNotIn('命令成功但内容未更新', failures[0])

    def test_all_items_command_success_without_change_are_all_failures(self):
        # 5 项都明显过期，命令都返回 0 但内容不动 → 5 项全部进入失败清单
        self._prepare_daily(overrides={item: STALE_DAY for item in cdu.DAILY_DATA_FILES})
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')):
            with redirect_stdout(io.StringIO()):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)
        self.assertEqual(len(failures), len(cdu.DAILY_DATA_FILES))
        for failure in failures:
            self.assertIn('命令成功但内容未更新', failure)

    def test_periodic_financial_quarter_reverify(self):
        stock_dir = self._stock_dir()
        filename = f'{TICKER}_financial_indicators.json'
        file_path = os.path.join(stock_dir, filename)

        def write_report(report_day):
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump({'timestamp': '2026-05-11 10:08:12',
                           'cash_flow': [{'报告日': report_day}]}, f, ensure_ascii=False)

        # 只更新到半年报（Q2），应披露到三季报（Q3）→ 命令返回 0 也不算成功
        write_report('20260630')
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')):
            with redirect_stdout(io.StringIO()):
                failure = cdu.check_and_update_item(
                    TICKER, 'financial_indicators', filename, 'python financial_indicators_collector.py',
                    EXPECTED, stock_dir)
        self.assertIsNotNone(failure)
        self.assertIn('命令成功但内容未更新', failure)
        self.assertIn('报告期', failure)

        # 更新后补到三季报 → 复核通过
        write_report('20260630')

        def fake_run(cmd, cwd=None):
            write_report('20260930')
            return True, ''

        with mock.patch.object(cdu, 'run_command', side_effect=fake_run):
            with redirect_stdout(io.StringIO()):
                failure = cdu.check_and_update_item(
                    TICKER, 'financial_indicators', filename, 'python financial_indicators_collector.py',
                    EXPECTED, stock_dir)
        self.assertIsNone(failure)


class FreshnessLagTest(FreshnessTestBase):
    """分级滞后阈值：刚好 1 天通过、超过阈值失败。"""

    def test_one_trading_day_lag_is_allowed_and_skips_update(self):
        self._prepare_daily()
        self._daily_file('fund_flow', PREV_TRADE_DAY)  # 资金流允许滞后 1 个交易日
        with mock.patch.object(cdu, 'run_command',
                               side_effect=AssertionError('滞后 1 天内不应触发更新命令')):
            with redirect_stdout(io.StringIO()):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)
        self.assertEqual(failures, [])

    def test_lag_beyond_limit_is_failure(self):
        self._prepare_daily()
        self._daily_file('fund_flow', TWO_DAYS_BEFORE)  # 滞后 2 个交易日，超过允许的 1 天
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')):
            with redirect_stdout(io.StringIO()):
                failures = cdu.check_daily_data(TICKER, expected_date=EXPECTED)
        self.assertEqual(len(failures), 1, failures)
        self.assertIn('fund_flow', failures[0])
        self.assertIn('命令成功但内容未更新', failures[0])
        self.assertIn('滞后 2 个交易日', failures[0])

    def test_freshness_thresholds_by_item(self):
        # 同一个内容日期，不同分级的判定不同
        self.assertTrue(cdu.is_fresh(PREV_TRADE_DAY, EXPECTED, 'fund_flow')[0])
        self.assertTrue(cdu.is_fresh(PREV_TRADE_DAY, EXPECTED, 'valuation')[0])
        self.assertFalse(cdu.is_fresh(PREV_TRADE_DAY, EXPECTED, 'qfq')[0])
        self.assertFalse(cdu.is_fresh(PREV_TRADE_DAY, EXPECTED, 'indicators')[0])
        # 低频数据允许滞后 5 个交易日：2026-11-05 刚好差 5 个交易日
        five_days_before = date(2026, 11, 5)
        self.assertTrue(cdu.is_fresh(five_days_before, EXPECTED, 'shareholder_num')[0])
        self.assertFalse(cdu.is_fresh(STALE_DAY, EXPECTED, 'shareholder_num')[0])
        # 周末不算交易日：周五到周一算滞后 1 个交易日
        self.assertEqual(cdu.trading_days_lag(date(2026, 11, 6), date(2026, 11, 9)), 1)


class FreshnessTableTest(FreshnessTestBase):
    """时效分级表本身及单项配置覆盖。"""

    def test_default_tiers_match_policy(self):
        rules = cdu.DEFAULT_FRESHNESS_RULES
        self.assertEqual(rules['qfq']['max_lag_trading_days'], 0)
        self.assertEqual(rules['indicators']['max_lag_trading_days'], 0)
        for item in ('fund_flow', 'margin_data', 'valuation'):
            self.assertEqual(rules[item]['max_lag_trading_days'], 1, item)
        for item in ('shareholder_num', 'shareholder', 'institutional'):
            self.assertEqual(rules[item]['max_lag_trading_days'], 5, item)
        self.assertEqual(rules['financial_indicators']['kind'], 'quarter')
        self.assertEqual(rules['dupont']['kind'], 'quarter')
        self.assertEqual(rules['financial_indicators']['max_lag_quarters'], 0)

    def test_same_content_date_judged_by_table(self):
        fund_path = self._write_csv(f'{TICKER}_fund_flow.csv',
                                    [f'{PREV_TRADE_DAY.isoformat()},100'], '日期,主力净流入-净额')
        qfq_path = self._write_csv(f'{TICKER}_qfq.csv',
                                   [f'{PREV_TRADE_DAY.isoformat()},10,10.5'], 'date,open,close')
        with redirect_stdout(io.StringIO()):
            ok_fund, _ = cdu.check_file_freshness(fund_path, EXPECTED, cdu.get_freshness_rule('fund_flow'))
            ok_qfq, _ = cdu.check_file_freshness(qfq_path, EXPECTED, cdu.get_freshness_rule('qfq'))
        self.assertTrue(ok_fund)
        self.assertFalse(ok_qfq)

    def test_single_item_override_takes_effect(self):
        qfq_path = self._daily_file('qfq', PREV_TRADE_DAY)
        with redirect_stdout(io.StringIO()):
            ok_before, _ = cdu.check_file_freshness(qfq_path, EXPECTED, cdu.get_freshness_rule('qfq'))
        self.assertFalse(ok_before)

        cdu.configure_freshness_rule('qfq', max_lag_trading_days=1)
        with redirect_stdout(io.StringIO()):
            ok_after, _ = cdu.check_file_freshness(qfq_path, EXPECTED, cdu.get_freshness_rule('qfq'))
        self.assertTrue(ok_after)

        # 只覆盖了 qfq，其他项仍按默认值
        self.assertEqual(cdu.get_freshness_rule('fund_flow')['max_lag_trading_days'], 1)
        self.assertEqual(cdu.get_freshness_rule('indicators')['max_lag_trading_days'], 0)

        cdu.reset_freshness_rules()
        with redirect_stdout(io.StringIO()):
            ok_reset, _ = cdu.check_file_freshness(qfq_path, EXPECTED, cdu.get_freshness_rule('qfq'))
        self.assertFalse(ok_reset)

    def test_load_freshness_config_file(self):
        config_path = os.path.join(self.tmpdir, 'freshness.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'fund_flow': {'max_lag_trading_days': 2}}, f, ensure_ascii=False)

        cdu.load_freshness_config(config_path)
        self.assertEqual(cdu.get_freshness_rule('fund_flow')['max_lag_trading_days'], 2)

        # 覆盖后原本滞后 2 个交易日的资金流变为达标
        fund_path = self._write_csv(f'{TICKER}_fund_flow.csv',
                                    [f'{TWO_DAYS_BEFORE.isoformat()},100'], '日期,主力净流入-净额')
        with redirect_stdout(io.StringIO()):
            ok, _ = cdu.check_file_freshness(fund_path, EXPECTED, cdu.get_freshness_rule('fund_flow'))
        self.assertTrue(ok)
        # 行情项没有被覆盖，仍然要求等于期望交易日
        self.assertEqual(cdu.get_freshness_rule('qfq')['max_lag_trading_days'], 0)

    def test_invalid_freshness_config_rejected(self):
        with self.assertRaises(ValueError):
            cdu.configure_freshness_rule('not_exists', max_lag_trading_days=1)
        with self.assertRaises(ValueError):
            cdu.configure_freshness_rule('qfq', max_lag_trading_days=-1)
        config_path = os.path.join(self.tmpdir, 'bad.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('[1, 2, 3]')
        with self.assertRaises(ValueError):
            cdu.load_freshness_config(config_path)


class TradeCalendarTest(FreshnessTestBase):
    """期望交易日：18:00 切点、周末近似、内容日期兜底、可注入日历钩子。"""

    def test_publish_cutoff_and_weekend_approximation(self):
        # 18:00 之前当日日线尚未落库 → 回退到前一工作日（收盘后到发布前也算前一天）
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 10, 0)), date(2026, 11, 12))
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 17, 0)), date(2026, 11, 12))
        # 18:00 后 → 当日
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 18, 0)), date(2026, 11, 13))
        # 周六/周日 → 回退到周五
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 14, 10, 0)), date(2026, 11, 13))
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 15, 19, 0)), date(2026, 11, 13))

    def test_expected_date_uses_later_of_calendar_and_content(self):
        # 本地行情只到 11-06，日历已到 11-12 → 期望日期取较晚的 11-12
        self._daily_file('qfq', date(2026, 11, 6))
        output = io.StringIO()
        with redirect_stdout(output):
            expected = cdu.get_expected_trade_date([TICKER], now=datetime(2026, 11, 13, 13, 0))
        self.assertEqual(expected, date(2026, 11, 12))
        self.assertIn('本地无交易日历', output.getvalue())

    def test_early_today_data_does_not_raise_global_cutoff(self):
        self._daily_file('qfq', date(2026, 11, 13))
        for hour, minute, expected in [(17, 59, date(2026, 11, 12)),
                                        (18, 0, date(2026, 11, 13))]:
            with self.subTest(hour=hour, minute=minute):
                self.assertEqual(cdu.get_expected_trade_date(
                    [TICKER], now=datetime(2026, 11, 13, hour, minute)), expected)

    def test_successful_update_with_old_content_on_today_is_rejected(self):
        today = date.today()
        self._daily_file('qfq', today - timedelta(days=10))
        item = {'filename': f'{TICKER}_qfq.csv',
                'command': 'python data_collector.py --ticker {ticker}', 'critical': True}
        with mock.patch.object(cdu, 'run_command', return_value=(True, 'ok')):
            failure = cdu.check_and_update_item(TICKER, 'qfq', item['filename'],
                                                item['command'], today, self._stock_dir())
        self.assertIn('内容未更新', failure)

    def test_injected_calendar_hook_is_used(self):
        def hook(start, end):
            days = []
            cur = start
            while cur <= end:
                if cur.weekday() < 5 and cur != date(2026, 11, 12):
                    days.append(cur)
                cur += timedelta(days=1)
            return days

        cdu.set_trade_calendar_hook(hook)
        # 2026-11-12 被当作节假日 → 16:00 前的最近交易日为 11-11
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 10, 0)), date(2026, 11, 11))
        # 交易日计数也走注入日历：11-11 到 11-12 之间没有交易日
        self.assertEqual(cdu.trading_days_lag(date(2026, 11, 11), date(2026, 11, 12)), 0)

        output = io.StringIO()
        with redirect_stdout(output):
            expected = cdu.get_expected_trade_date([], now=datetime(2026, 11, 13, 10, 0))
        self.assertEqual(expected, date(2026, 11, 11))
        # 注入日历后不再打印「本地无交易日历」提示
        self.assertNotIn('本地无交易日历', output.getvalue())

    def test_quarter_requirement(self):
        # 2026-11-12 之前，三季报（9/30）已到披露截止日，必须包含 Q3
        self.assertTrue(cdu.is_fresh(date(2026, 9, 30), EXPECTED, 'financial_indicators')[0])
        self.assertFalse(cdu.is_fresh(date(2026, 6, 30), EXPECTED, 'financial_indicators')[0])
        # 披露截止日前不要求下一季度：2026-10-30 时三季报尚未到截止日（10/31）
        self.assertEqual(cdu.get_expected_report_quarter_end(date(2026, 10, 30)), date(2026, 6, 30))
        self.assertEqual(cdu.get_expected_report_quarter_end(date(2026, 11, 12)), date(2026, 9, 30))


class ContentDateReadTest(FreshnessTestBase):
    """按数据源读取内容日期列；财务 JSON 优先取报告期；mtime 兜底仅限允许项。"""

    def test_csv_date_columns_per_item(self):
        cases = [
            ('margin_data', f'{TICKER}_margin_data.csv', 'date,融资余额', '20260521', date(2026, 5, 21)),
            ('valuation', f'{TICKER}_valuation.csv', '数据日期,总市值', '2026-06-15', date(2026, 6, 15)),
            ('shareholder_num', f'{TICKER}_shareholder_num.csv', 'END_DATE,HOLDER_TOTAL_NUM',
             '2026-06-05 00:00:00', date(2026, 6, 5)),
        ]
        for item, filename, header, raw, expected in cases:
            path = self._write_csv(filename, [f'{raw},1'], header)
            content, source = cdu.read_content_date(path, cdu.get_freshness_rule(item))
            self.assertEqual(content, expected, item)
            self.assertIn('指定业务日期列', source)

    def test_financial_json_prefers_report_period_over_timestamp(self):
        path = os.path.join(self._stock_dir(), f'{TICKER}_financial_indicators.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'timestamp': '2026-05-11 10:08:12',
                       'cash_flow': [{'报告日': '20260331'}]}, f, ensure_ascii=False)
        content, source = cdu.read_content_date(path, cdu.get_freshness_rule('financial_indicators'))
        self.assertEqual(content, date(2026, 3, 31))
        self.assertIn('报告期字段', source)

    def test_mtime_fallback_only_when_rule_allows(self):
        # 除权除息文件没有业务日期列，允许 mtime 兜底
        path = self._write_csv(f'{TICKER}_ex_dividend.csv', ['000001,平安银行'], '代码,名称')
        ts = time.mktime(datetime(2026, 11, 5, 12, 0).timetuple())
        os.utime(path, (ts, ts))
        with redirect_stdout(io.StringIO()):
            ok_fallback, _ = cdu.check_file_freshness(path, EXPECTED, cdu.get_freshness_rule('ex_dividend'))
        self.assertTrue(ok_fallback)

        # 行情规则不允许 mtime 兜底：读不到业务日期直接判失败
        with redirect_stdout(io.StringIO()):
            ok_strict, _ = cdu.check_file_freshness(path, EXPECTED, cdu.get_freshness_rule('qfq'))
        self.assertFalse(ok_strict)


class MainExitCodeTest(FreshnessTestBase):
    """main 汇总失败清单并以非 0 退出码结束。"""

    def _run_main(self):
        argv = ['check_data_updates.py', '--ticker', TICKER, '--mode', 'daily']
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(cdu, 'get_expected_trade_date', return_value=EXPECTED), \
             redirect_stdout(output):
            code = cdu.main()
        return code, output.getvalue()

    def test_failure_list_returns_nonzero(self):
        self._prepare_daily()
        self._daily_file('qfq', PREV_TRADE_DAY)  # 命令成功但内容不更新
        with mock.patch.object(cdu, 'run_command', return_value=(True, '')):
            code, output = self._run_main()
        self.assertEqual(code, 1)
        self.assertIn('数据更新失败清单', output)
        self.assertIn('命令成功但内容未更新', output)
        self.assertIn('本次检查不通过', output)

    def test_all_fresh_returns_zero(self):
        self._prepare_daily()
        with mock.patch.object(cdu, 'run_command',
                               side_effect=AssertionError('数据已达标时不应执行更新命令')):
            code, output = self._run_main()
        self.assertEqual(code, 0)
        self.assertIn('内容日期均达到分级时效要求', output)

    def test_freshness_config_cli_override(self):
        # 通过 --freshness-config 把行情阈值放宽到 1 天，滞后 1 天不再触发更新
        self._prepare_daily()
        self._daily_file('qfq', PREV_TRADE_DAY)
        config_path = os.path.join(self.tmpdir, 'freshness.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump({'qfq': {'max_lag_trading_days': 1}}, f, ensure_ascii=False)
        argv = ['check_data_updates.py', '--ticker', TICKER, '--mode', 'daily',
                '--freshness-config', config_path]
        output = io.StringIO()
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(cdu, 'get_expected_trade_date', return_value=EXPECTED), \
             mock.patch.object(cdu, 'run_command',
                               side_effect=AssertionError('放宽阈值后不应触发更新命令')), \
             redirect_stdout(output):
            code = cdu.main()
        self.assertEqual(code, 0, output.getvalue())

    def test_bad_freshness_config_returns_nonzero(self):
        config_path = os.path.join(self.tmpdir, 'bad.json')
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write('{"qfq": {"max_lag_trading_days": "bad"}}')
        argv = ['check_data_updates.py', '--ticker', TICKER, '--mode', 'daily',
                '--freshness-config', config_path]
        with mock.patch.object(sys, 'argv', argv), redirect_stdout(io.StringIO()):
            code = cdu.main()
        self.assertEqual(code, 1)


class PriceModeAndMarginWindowTest(FreshnessTestBase):
    """选股/回测只查行情+指标；融资融券只在需要时补最近窗口。"""

    def test_price_mode_only_checks_quote_and_indicators(self):
        seen = []
        def fake_item(ticker, item_name, filename, command, expected_date, stock_dir):
            seen.append(item_name)
            return None
        argv = ['check_data_updates.py', '--ticker', TICKER, '--mode', 'price']
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(cdu, 'check_and_update_item', side_effect=fake_item), \
             mock.patch.object(cdu, 'get_expected_trade_date', return_value=EXPECTED), \
             redirect_stdout(io.StringIO()):
            self.assertEqual(cdu.main(), 0)
        self.assertEqual(seen, ['qfq', 'indicators'])

    def test_margin_update_uses_recent_window(self):
        commands = []
        def fake_run(command, cwd=None):
            commands.append(command)
            return False, 'returncode=2'
        argv = ['check_data_updates.py', '--ticker', TICKER]
        with mock.patch.object(cdu, 'run_command', side_effect=fake_run), \
             redirect_stdout(io.StringIO()):
            cdu.check_and_update_item(TICKER, 'margin_data', f'{TICKER}_margin_data.csv',
                                      f'python batch_margin_collector.py --ticker {TICKER}',
                                      EXPECTED, os.path.join(self.tmpdir, TICKER))
        self.assertEqual(len(commands), 1)
        expected_start = (EXPECTED - timedelta(days=10)).strftime('%Y%m%d')
        self.assertIn('--start_date ' + expected_start, commands[0])


if __name__ == '__main__':
    unittest.main()