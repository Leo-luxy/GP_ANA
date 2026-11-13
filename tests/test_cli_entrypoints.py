"""命令行入口冒烟：必须以"脚本方式"真实起子进程，才能发现导入顺序问题。

只在进程内 import 这些模块会掩盖 sys.path 缺陷——之前 stocks_filter 下的批筛
先 import 根目录模块、后补 sys.path，单独运行直接 ModuleNotFoundError 退出 1，
被接口误报成"批筛执行失败"。
"""
import os
import subprocess
import sys
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 子目录脚本：以脚本方式运行时 sys.path[0] 是脚本所在目录，不含项目根。
ENTRYPOINTS = [
    ('stocks_filter/step1_daily.py', 'stocks_filter'),
    ('trend_following_backtest.py', '.'),
    ('stocks_filter/batch_backtest_filter.py', 'stocks_filter'),
    ('daily/stock_daily_indicator_calculator.py', 'daily'),
    ('daily/strategy_optimization.py', 'daily'),
]


class CliEntrypointSmoke(unittest.TestCase):
    def test_scripts_import_own_dependencies(self):
        env = dict(os.environ)
        # 模拟用户直接运行：不依赖外部注入的 PYTHONPATH。
        env.pop('PYTHONPATH', None)
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        for script, workdir in ENTRYPOINTS:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, os.path.basename(script), '--help'],
                    cwd=os.path.join(PROJECT_ROOT, workdir),
                    capture_output=True, text=True, timeout=120, env=env)
                self.assertEqual(result.returncode, 0,
                                 f'{script} 无法以脚本方式启动:\n{result.stdout}\n{result.stderr}')
                self.assertNotIn('ModuleNotFoundError', result.stderr + result.stdout,
                                 f'{script} 导入顺序仍有问题')


if __name__ == '__main__':
    unittest.main()
