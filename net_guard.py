# net_guard.py
# -*- coding:utf-8 -*-
"""
网络代理守护模块

背景
----
Python 的 requests / urllib 默认会自动读取系统代理设置。一旦系统里残留了
一条指向某个本地代理端口的配置，而那个代理并没有在运行，所有请求都会
先撞到一个无人监听的端口，抛 ProxyError 而失败。

本项目的数据源全部是国内站点（新浪财经、东方财富、Tushare、同花顺、巨潮等），
本地 LLM 走 localhost，**没有任何一个需要经过代理**。

因此本模块的默认行为是：**所有进程一律直连，不使用系统代理**。
无论系统代理是开、是关、还是残留状态，抓取都不受影响。

使用方式
--------
    import net_guard
    net_guard.ensure_network_ready()          # 进程内直连（默认行为）

特殊情况
--------
  * 确实需要经过代理运行时（例如海外网络直连不到国内源）：
        设置环境变量 GP_ANA_NET_MODE=proxy
    此时优先走系统代理；代理连不上会自动回退直连并打印警告。
  * 命令行自检：
        python net_guard.py

注意：环境变量名不要以 `_proxy` 结尾，否则会被 urllib 当成代理配置读进去。
"""

import os
import socket
import sys
import urllib.request

_STATE = {
    'checked': False,   # 是否已初始化
    'mode': None,       # 见 _MODE_TEXT
    'targets': [],      # 系统配置的代理 (host, port)
    'detail': '',       # 说明文字
}

_MODE_TEXT = {
    'direct-default': '直连（默认：不使用系统代理）',
    'proxy-active': '使用系统代理（GP_ANA_NET_MODE=proxy）',
    'direct-fallback': '代理不可用 → 已回退直连',
    'proxy-none': '要求走代理但系统未配置代理 → 直连',
}

# 只承认这些 scheme，避免把无关的环境变量误当成代理配置
_KNOWN_SCHEMES = ('http', 'https', 'socks', 'socks5', 'all', 'ftp')

# 探测顺序：urllib 里对同一份代理配置会给出 http/https/socks 多个键
_DEFAULT_PORTS = {'http': 80, 'https': 443, 'socks': 1080, 'socks5': 1080,
                  'all': 1080, 'ftp': 21}

# 直连时清掉的环境变量
_PROXY_ENV_KEYS = (
    'http_proxy', 'https_proxy', 'all_proxy', 'ftp_proxy',
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'FTP_PROXY',
)

def _system_proxy_targets():
    """返回系统配置的代理 [(host, port), ...]（去重）"""
    try:
        proxies = urllib.request.getproxies()
    except Exception:
        return []

    targets = []
    for scheme, url in proxies.items():
        scheme = scheme.lower()
        if not url or scheme in ('no', 'no_proxy') or scheme not in _KNOWN_SCHEMES:
            continue
        netloc = url.split('//', 1)[1] if '//' in url else url
        netloc = netloc.rstrip('/')
        host, _, port = netloc.partition(':')
        if not host:
            continue
        port = int(port) if port.isdigit() else _DEFAULT_PORTS.get(scheme, 80)
        if (host, port) not in targets:
            targets.append((host, port))
    return targets


def _reachable(host, port, timeout=0.8):
    """TCP 探测代理端口是否真的有人监听"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def force_direct():
    """
    让本进程（及其子进程）内的 requests / urllib 全部直连。

    只影响当前进程树，不会改动 macOS 的系统代理设置，也不影响浏览器和 git。
    """
    os.environ['no_proxy'] = '*'
    os.environ['NO_PROXY'] = '*'
    for key in _PROXY_ENV_KEYS:
        os.environ.pop(key, None)

    # 兜底：系统代理（macOS 系统设置）不走环境变量，requests 通过 getproxies() 读取，
    # 这里直接替换掉，确保任何路径都不会再挂到那个代理端口上。
    try:
        import requests.utils as requests_utils
        requests_utils.getproxies = lambda: {}
    except Exception:
        pass
    try:
        urllib.request.getproxies = lambda: {}
    except Exception:
        pass


def is_proxy_error(exc):
    """判断异常是否由代理不可用引起"""
    text = f'{type(exc).__name__}: {exc}'.lower()
    return 'proxy' in text


def _use_proxy_requested():
    """只有显式声明 GP_ANA_NET_MODE=proxy 时才考虑使用系统代理"""
    return os.environ.get('GP_ANA_NET_MODE', '').strip().lower() == 'proxy'


def ensure_network_ready(verbose=False):
    """
    初始化本进程的网络模式。幂等，可重复调用。

    默认直接直连；只有显式设置 GP_ANA_NET_MODE=proxy 时才考虑使用系统代理。

    返回 'direct-default' | 'proxy-active' | 'direct-fallback' | 'proxy-none'
    """
    if _STATE['checked']:
        return _STATE['mode']

    _STATE['checked'] = True
    _STATE['targets'] = _system_proxy_targets()

    if not _use_proxy_requested():
        force_direct()
        _STATE['mode'] = 'direct-default'
        _STATE['detail'] = '默认直连，不使用系统代理'
        _announce(verbose)
        return _STATE['mode']

    targets = _STATE['targets']
    if not targets:
        force_direct()
        _STATE['mode'] = 'proxy-none'
        _STATE['detail'] = 'GP_ANA_NET_MODE=proxy，但系统未配置代理，按直连处理'
        _announce(verbose)
        return _STATE['mode']

    dead = [f'{h}:{p}' for h, p in targets if not _reachable(h, p)]
    if dead:
        force_direct()
        _STATE['mode'] = 'direct-fallback'
        _STATE['detail'] = 'GP_ANA_NET_MODE=proxy，但系统代理无法连接（%s），已回退直连' % ', '.join(dead)
    else:
        _STATE['mode'] = 'proxy-active'
        _STATE['detail'] = '按要求使用系统代理：' + ', '.join(f'{h}:{p}' for h, p in targets)
    _announce(verbose)
    return _STATE['mode']


def _announce(verbose):
    # 默认直连是正常状态，不打印，避免批量抓取时每个子进程都刷一行；
    # 「要求走代理却连不上」属于异常，一定打印出来。
    if verbose or _STATE['mode'] == 'direct-fallback':
        print(f"[net_guard] {_STATE['detail']}", flush=True)


def retry_on_proxy_error(func, *args, **kwargs):
    """
    调用 func；若因代理问题失败，则切换为直连后重试一次。

    正常情况下进程启动时已经是直连，这里是双保险（例如进程启动后才打开代理、
    或 GP_ANA_NET_MODE=proxy 但代理中途挂掉）。
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        if not is_proxy_error(exc):
            raise
        if _STATE['mode'] in ('direct-default', 'direct-fallback', 'proxy-none'):
            raise
        force_direct()
        _STATE['checked'] = True
        _STATE['mode'] = 'direct-fallback'
        _STATE['detail'] = '代理请求失败，已自动改为直连后重试'
        _announce(True)
        return func(*args, **kwargs)


def status():
    """返回当前网络模式的可读信息（供自检与排查）"""
    ensure_network_ready()
    return dict(_STATE)


def _main():
    info = status()
    print('网络模式自检：')
    print(f"  系统代理配置：{info['targets'] or '无'}")
    print(f"  当前模式：{_MODE_TEXT.get(info['mode'], info['mode'])}")
    print(f"  说明：{info['detail']}")

    # 验证一个国内数据源是否真的通
    ok = True
    for name, url in (('Tushare', 'http://api.tushare.pro'),
                      ('新浪财经', 'https://finance.sina.com.cn/realstock/company/sh600048/hisdata_klc2/klc_kl.js')):
        try:
            import requests
            resp = requests.get(url, timeout=15)
            print(f"  连通性测试：{name} → HTTP {resp.status_code}")
        except Exception as exc:
            ok = False
            print(f"  连通性测试：{name} → 失败 {type(exc).__name__}: {str(exc)[:120]}")
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(_main())
