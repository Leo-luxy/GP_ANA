"""Tushare 客户端：主 token 被限流时自动切换备用 token。

免费额度是「按 token 计」的，所以主 token 撞到每分钟/每小时上限时，
换用备用 token 可以继续取数，不必等额度恢复。

替换 token 只需改本文件顶部两个常量，或在环境变量
GP_TUSHARE_TOKENS="主token,备用token" 中覆盖（逗号分隔，可写多个）。
"""
import os

import tushare as ts

# ==================== 配置 ====================
PRIMARY_TOKEN = "YOUR_TUSHARE_TOKEN"      # 主 token（去 https://tushare.pro 个人主页获取）
BACKUP_TOKENS = [
    # 可选：填入其它账号的 token；主 token 命中频率超限时会自动切换
]
# =============================================

PLACEHOLDER = 'YOUR_TUSHARE_TOKEN'


def is_rate_limit(exc):
    """Tushare 频率超限（免费额度常见：daily_basic 每分钟/每小时 1 次）。"""
    text = str(exc)
    return ('频率超限' in text or '每分钟' in text or '每小时' in text
            or '频次' in text or 'limit' in text.lower())


def resolve_tokens():
    """环境变量优先，其次使用上面的常量；占位符一律忽略。"""
    env = os.environ.get('GP_TUSHARE_TOKENS', '')
    values = [t.strip() for t in env.split(',')] if env.strip() else [PRIMARY_TOKEN, *BACKUP_TOKENS]
    tokens = []
    for value in values:
        if value and value != PLACEHOLDER and value not in tokens:
            tokens.append(value)
    if not tokens:
        raise RuntimeError('未配置 Tushare token：请在 tushare_client.py 填写，'
                           '或设置环境变量 GP_TUSHARE_TOKENS')
    return tokens


class TusharePool:
    """代理 ts.pro_api(...)：调用失败且属于限流时，换下一个 token 重试同一请求。"""

    def __init__(self, tokens=None):
        self.tokens = list(tokens) if tokens else resolve_tokens()
        self._apis = {}
        self._index = 0
        self.switches = 0

    @property
    def token(self):
        return self.tokens[self._index]

    @property
    def token_label(self):
        return f'第 {self._index + 1}/{len(self.tokens)} 个'

    def _api(self, index):
        if index not in self._apis:
            self._apis[index] = ts.pro_api(self.tokens[index])
        return self._apis[index]

    def _call(self, name, *args, **kwargs):
        last_error = None
        for offset in range(len(self.tokens)):
            index = (self._index + offset) % len(self.tokens)
            try:
                result = getattr(self._api(index), name)(*args, **kwargs)
            except Exception as exc:
                if not is_rate_limit(exc):
                    raise
                last_error = exc
                continue
            if index != self._index:
                self._index = index
                self.switches += 1
                print(f"提示：Tushare {name} 触发限流，已切换到备用 token（{self.token_label}）")
            return result
        print(f"警告：{len(self.tokens)} 个 Tushare token 全部限流，本次 {name} 调用失败")
        raise last_error

    def __getattr__(self, name):
        if name.startswith('_'):
            raise AttributeError(name)
        return lambda *args, **kwargs: self._call(name, *args, **kwargs)
