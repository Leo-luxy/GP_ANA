"""Tushare 主备 token：主 token 限流时自动切换，不能因此让整批取数失败。"""
import os
import unittest
from unittest import mock

import tushare_client as tc


class FakeApi:
    def __init__(self, token, limit_calls, fail_calls=0):
        self.token = token
        self.calls = 0
        self.limit_calls = limit_calls
        self.fail_calls = fail_calls

    def daily(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_calls:
            raise RuntimeError('网络异常')
        if self.calls <= self.fail_calls + self.limit_calls:
            raise Exception('抱歉，您访问接口(daily)频率超限(1次/分钟)')
        return {'token': self.token, 'kwargs': kwargs}


class TusharePoolTest(unittest.TestCase):
    def make_pool(self, behaviors, tokens=('primary', 'backup')):
        apis = {token: FakeApi(token, *behaviors[token]) for token in tokens}
        return tc.TusharePool(tokens=list(tokens)), apis

    def test_primary_rate_limited_falls_back_to_backup(self):
        pool, apis = self.make_pool({'primary': (1, 0), 'backup': (0, 0)})
        with mock.patch.object(tc.ts, 'pro_api', side_effect=lambda t: apis[t]):
            result = pool.daily(trade_date='20261113')
        self.assertEqual(result['token'], 'backup')
        self.assertEqual(result['kwargs']['trade_date'], '20261113')
        self.assertEqual(pool.token, 'backup')
        self.assertEqual(pool.switches, 1)

    def test_working_token_is_remembered(self):
        pool, apis = self.make_pool({'primary': (1, 0), 'backup': (0, 0)})
        with mock.patch.object(tc.ts, 'pro_api', side_effect=lambda t: apis[t]):
            pool.daily(trade_date='20261113')
            pool.daily(trade_date='20261112')
        # 已切到备用后不再回头撞主 token 的额度
        self.assertEqual(apis['primary'].calls, 1)
        self.assertEqual(apis['backup'].calls, 2)

    def test_all_tokens_limited_raises_rate_limit_error(self):
        pool, apis = self.make_pool({'primary': (5, 0), 'backup': (5, 0)})
        with mock.patch.object(tc.ts, 'pro_api', side_effect=lambda t: apis[t]):
            with self.assertRaises(Exception) as ctx:
                pool.daily(trade_date='20261113')
        # 上层（step2 复用同日缓存）依赖这个判定，必须仍是限流异常
        self.assertTrue(tc.is_rate_limit(ctx.exception))

    def test_non_rate_limit_error_is_not_swallowed(self):
        pool, apis = self.make_pool({'primary': (0, 1), 'backup': (0, 0)})
        with mock.patch.object(tc.ts, 'pro_api', side_effect=lambda t: apis[t]):
            with self.assertRaises(RuntimeError):
                pool.daily(trade_date='20261113')
        self.assertEqual(apis['backup'].calls, 0)

    def test_tokens_from_env_and_placeholder_ignored(self):
        with mock.patch.dict(os.environ, {'GP_TUSHARE_TOKENS': 'a,YOUR_TUSHARE_TOKEN,a,b'}, clear=False):
            self.assertEqual(tc.resolve_tokens(), ['a', 'b'])
        with mock.patch.dict(os.environ, {}, clear=True):
            # 发布版是占位符：未配置 token 时必须明确报错，而不是拿占位符去请求
            with self.assertRaises(RuntimeError):
                tc.resolve_tokens()


if __name__ == '__main__':
    unittest.main()
