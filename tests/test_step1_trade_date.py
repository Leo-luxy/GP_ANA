"""初筛交易日探测：日历不可用时不能靠滞后的第三方接口悄悄退回前一天。"""
import pathlib
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
STEP1 = (PROJECT_ROOT / 'stocks_filter' / 'step1_daily.py').read_text()
STEP2 = (PROJECT_ROOT / 'stocks_filter' / 'step2_daily_basic.py').read_text()


class TradeDateProbeTest(unittest.TestCase):
    # 断言只给出简短原因，避免失败时把含 token 的源码打进日志。
    def test_probe_uses_same_api_as_fetch(self):
        self.assertTrue('trade_date=d, fields="ts_code"' in STEP1,
                        '探测未使用 Tushare daily 接口')

    def test_no_akshare_fallback_that_lags_one_day(self):
        # 历史故障：日历经限流后改用 akshare 探测 sz000001，该接口滞后一天。
        self.assertTrue('import akshare' not in STEP1 and 'ak.stock_zh_a_daily' not in STEP1,
                        '仍存在滞后一天的 akshare 探测兜底')

    def test_weekday_candidates_used_when_calendar_unavailable(self):
        self.assertTrue('_weekday_candidates(today)' in STEP1 and 'def _weekday_candidates(' in STEP1,
                        '日历不可用时的候选未走工作日生成')

    def test_stale_choice_is_warned(self):
        self.assertTrue('比当前期望交易日' in STEP1, '取到旧日期时没有告警')

    def test_step2_limits_advice_mentions_both_dates(self):
        self.assertTrue('_cached_date()' in STEP2 and '行情比已有的完整数据旧' in STEP2,
                        '限流中止时未给出可操作建议')


if __name__ == '__main__':
    unittest.main()
