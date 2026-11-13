# tests/test_api_pipeline.py
# -*- coding: utf-8 -*-
"""API 执行链路回归测试。

覆盖：
    * execute_step 超时真正生效，并杀掉整个进程组；
    * 关键步骤失败 → 任务 failed 且后续步骤不再执行；
    * 可选步骤失败 → 任务降级（completed + degraded + warnings）但继续执行；
    * check_data_updates 检查命令退出码、按内容日期判断、失败时非 0 返回；
    * 报告读取路径越界 / 绝对路径 / 非白名单扩展名被拒绝；
    * web_ui 默认只绑定 127.0.0.1 且关闭 debug。

全部用例都不启动真实 Flask 监听、不联网、不写 data/ 目录。
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from datetime import date, datetime
from unittest import mock

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

import api.common as api_common
import check_data_updates as cdu


def _pid_exists(pid):
    """判断进程是否仍然存在。"""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _wait_pid_file(pid_file, timeout=2.0):
    """等待子进程写出自己的 pid（避免与子进程启动竞态）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with open(pid_file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if content:
                return int(content)
        except (FileNotFoundError, ValueError):
            time.sleep(0.05)
    return None


class ExecuteStepTest(unittest.TestCase):
    """execute_step 的超时与退出码语义。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gpana_exec_')
        self.addCleanup(shutil.rmtree, self.tmpdir, True)

    def test_timeout_kills_whole_process_group(self):
        """0.3 秒超时必须立即返回 False，并杀掉 shell 及其子进程。"""
        pid_file = os.path.join(self.tmpdir, 'child.pid')
        script = os.path.join(self.tmpdir, 'sleeper.py')
        with open(script, 'w', encoding='utf-8') as f:
            f.write(
                "import os\n"
                "import sys\n"
                "import time\n"
                "with open(sys.argv[1], 'w', encoding='utf-8') as fh:\n"
                "    fh.write(str(os.getpid()))\n"
                "time.sleep(30)\n"
            )
        # 后台子进程 + wait：确保被测的是「shell + 其子进程」整棵进程树
        command = f'{sys.executable} "{script}" "{pid_file}" & wait'

        messages = []
        started = time.monotonic()
        ok, detail = api_common.execute_step('超时用例', command, self.tmpdir, messages, timeout_seconds=0.3)
        elapsed = time.monotonic() - started

        self.assertFalse(ok)
        self.assertEqual(detail, 'timeout')
        self.assertLess(elapsed, 5.0, f'超时判定耗时 {elapsed:.2f}s，超时未真正生效')
        self.assertTrue(any('超时' in msg for msg in messages))

        child_pid = _wait_pid_file(pid_file)
        self.assertIsNotNone(child_pid, '子进程未写出 pid，无法验证是否被杀')
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and _pid_exists(child_pid):
            time.sleep(0.05)
        self.assertFalse(_pid_exists(child_pid), '超时后子进程仍存活，未终止整个进程组')

    def test_returns_real_exit_status(self):
        """成功 / 非 0 退出码要如实返回，不能吞成成功。"""
        messages = []
        ok, detail = api_common.execute_step('成功用例', 'echo hello-from-step', self.tmpdir, messages, 5)
        self.assertTrue(ok)
        self.assertEqual(detail, 'success')
        self.assertTrue(any('hello-from-step' in msg for msg in messages))

        messages = []
        ok, detail = api_common.execute_step(
            '失败用例',
            f'{sys.executable} -c "import sys; sys.exit(3)"',
            self.tmpdir,
            messages,
            5,
        )
        self.assertFalse(ok)
        self.assertIn('returncode=3', detail)


class ExecuteStepsTest(unittest.TestCase):
    """_execute_steps 的关键步骤失败 / 可选步骤降级语义。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gpana_steps_')
        self.saved_project_root = api_common.project_root
        self.saved_task_status_file = api_common.TASK_STATUS_FILE
        self.saved_execute_step = api_common.execute_step
        self.saved_task_status = dict(api_common.task_status)
        # 重定向到临时目录，避免测试写项目 data/ 与状态缓存
        api_common.project_root = self.tmpdir
        api_common.TASK_STATUS_FILE = os.path.join(self.tmpdir, '.task_status_cache.json')
        api_common.task_status.clear()

    def tearDown(self):
        api_common.execute_step = self.saved_execute_step
        api_common.project_root = self.saved_project_root
        api_common.TASK_STATUS_FILE = self.saved_task_status_file
        api_common.task_status.clear()
        api_common.task_status.update(self.saved_task_status)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _install_fake_execute(self, fail_names):
        calls = []

        def fake_execute(step_name, command, cwd, messages, timeout_seconds=300):
            calls.append(step_name)
            if step_name in fail_names:
                return False, 'returncode=2'
            return True, 'success'

        api_common.execute_step = fake_execute
        return calls

    def test_critical_failure_stops_following_steps(self):
        calls = self._install_fake_execute({('[采集] 失败步骤')})
        steps = [
            ('[采集] 正常步骤', 'cmd-1'),
            ('[采集] 失败步骤', 'cmd-2'),
            ('[分析] 不应执行', 'cmd-3'),
        ]
        result = api_common._execute_steps('task-critical-fail', '000001.SZ', steps, '测试标签')
        status = api_common.task_status['task-critical-fail']

        self.assertFalse(result)
        self.assertEqual(status['status'], 'failed')
        self.assertEqual(calls, ['[采集] 正常步骤', '[采集] 失败步骤'])
        self.assertEqual(status['failed_step'], '[采集] 失败步骤')
        self.assertIn('returncode=2', status['reason'])
        self.assertTrue(any('停止后续 1 个步骤' in msg for msg in status['messages']))

    def test_optional_failure_degrades_but_continues(self):
        calls = self._install_fake_execute({('[采集] 补充数据')})
        steps = [
            ('[采集] 核心数据', 'cmd-1'),
            ('[采集] 补充数据', 'cmd-2', {'critical': False}),
            ('[分析] 后续分析', 'cmd-3'),
        ]
        result = api_common._execute_steps('task-degraded', '000001.SZ', steps, '测试标签')
        status = api_common.task_status['task-degraded']

        self.assertTrue(result)
        self.assertEqual(status['status'], 'completed')
        # 必须显式降级，不能看起来完全成功
        self.assertTrue(status.get('degraded'))
        self.assertEqual(len(status.get('warnings', [])), 1)
        self.assertIn('补充数据', status['warnings'][0])
        self.assertEqual(calls, ['[采集] 核心数据', '[采集] 补充数据', '[分析] 后续分析'])
        self.assertTrue(any('降级' in msg for msg in status['messages']))

        # 降级状态要能被前端轮询接口读到（已持久化）
        with open(api_common.TASK_STATUS_FILE, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        self.assertTrue(saved['task-degraded']['degraded'])
        self.assertEqual(len(saved['task-degraded']['warnings']), 1)

    def test_optional_marker_prefix_is_recognized(self):
        calls = self._install_fake_execute({('[采集] 补充北向')})
        steps = [
            ('[可选][采集] 补充北向', 'cmd-1'),
            ('[采集] 核心数据', 'cmd-2'),
        ]
        result = api_common._execute_steps('task-optional-marker', '000001.SZ', steps, '测试标签')
        status = api_common.task_status['task-optional-marker']

        self.assertTrue(result)
        self.assertEqual(status['status'], 'completed')
        self.assertTrue(status.get('degraded'))
        self.assertEqual(calls, ['[采集] 补充北向', '[采集] 核心数据'])

    def test_all_success_has_no_degraded_flag(self):
        self._install_fake_execute(set())
        steps = [('[采集] 步骤A', 'cmd-1'), ('[分析] 步骤B', 'cmd-2')]
        result = api_common._execute_steps('task-success', '000001.SZ', steps, '测试标签')
        status = api_common.task_status['task-success']

        self.assertTrue(result)
        self.assertEqual(status['status'], 'completed')
        self.assertNotIn('degraded', status)


class CheckDataUpdatesTest(unittest.TestCase):
    """check_data_updates 的命令退出码、内容日期与整体退出码。"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix='gpana_check_')
        self.saved_data_dir = cdu.DATA_DIR
        cdu.DATA_DIR = self.tmpdir
        self.addCleanup(self._restore)

    def _restore(self):
        cdu.DATA_DIR = self.saved_data_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_calendar_trade_date(self):
        # 2026-11-13 是周五：18:00 前（含收盘后未发布时段）期望前一交易日，18:00 后期望当日
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 10, 0)), date(2026, 11, 12))
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 17, 0)), date(2026, 11, 12))
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 13, 18, 0)), date(2026, 11, 13))
        # 周六回退到周五
        self.assertEqual(cdu.get_calendar_trade_date(datetime(2026, 11, 14, 10, 0)), date(2026, 11, 13))

    def test_content_date_beats_mtime(self):
        csv_path = os.path.join(self.tmpdir, '000001.SZ_qfq.csv')
        with open(csv_path, 'w', encoding='utf-8') as f:
            f.write('date,open,close\n')
            f.write('2026-11-05,10,10.5\n')
            f.write('2026-11-12,10.5,11\n')
        self.assertEqual(cdu.get_last_data_date(csv_path), date(2026, 11, 12))
        self.assertTrue(cdu.is_latest_date('2026-11-12', date(2026, 11, 12)))
        self.assertFalse(cdu.is_latest_date('2026-11-05', date(2026, 11, 12)))
        # 文件 mtime 很新但内容日期旧 → 仍判定为不是最新
        self.assertTrue(cdu.check_file_up_to_date(csv_path, date(2026, 11, 12)))
        self.assertFalse(cdu.check_file_up_to_date(csv_path, date(2026, 11, 13)))

    def test_expected_trade_date_uses_newer_of_calendar_and_content(self):
        # 本地只有旧行情 → 期望日期按日历补更
        stock_dir = os.path.join(self.tmpdir, '000001.SZ')
        os.makedirs(stock_dir)
        qfq_path = os.path.join(stock_dir, '000001.SZ_qfq.csv')
        with open(qfq_path, 'w', encoding='utf-8') as f:
            f.write('date,open,close\n2026-11-05,10,10.5\n')
        expected = cdu.get_expected_trade_date(['000001.SZ'], now=datetime(2026, 11, 13, 13, 0))
        self.assertEqual(expected, date(2026, 11, 12))

    def test_run_command_checks_returncode(self):
        failed = subprocess.CompletedProcess(args='x', returncode=2, stdout='', stderr='取不到行情数据')
        with mock.patch.object(cdu.subprocess, 'run', return_value=failed):
            ok, detail = cdu.run_command('python data_collector.py --ticker 000001.SZ')
        self.assertFalse(ok)
        self.assertIn('returncode=2', detail)
        self.assertIn('取不到行情数据', detail)

        succeeded = subprocess.CompletedProcess(args='x', returncode=0, stdout='ok', stderr='')
        with mock.patch.object(cdu.subprocess, 'run', return_value=succeeded):
            ok, detail = cdu.run_command('python data_collector.py --ticker 000001.SZ')
        self.assertTrue(ok)
        self.assertEqual(detail, '')

    def test_daily_check_collects_update_failures(self):
        with mock.patch.object(cdu, 'check_file_up_to_date', return_value=False), \
             mock.patch.object(cdu, 'run_command', return_value=(False, 'returncode=2；输出末尾: 取数失败')):
            failures = cdu.check_daily_data('000001.SZ', expected_date=date(2026, 11, 12))
        self.assertEqual(len(failures), len(cdu.DAILY_DATA_FILES))
        self.assertTrue(all('returncode=2' in item for item in failures))

    def test_main_returns_nonzero_on_failure(self):
        argv = ['check_data_updates.py', '--ticker', '000001.SZ', '--mode', 'daily']
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(cdu, 'get_expected_trade_date', return_value=date(2026, 11, 12)), \
             mock.patch.object(cdu, 'check_daily_data', return_value=['000001.SZ qfq 更新失败: returncode=2']):
            self.assertEqual(cdu.main(), 1)

    def test_main_returns_zero_on_success(self):
        argv = ['check_data_updates.py', '--ticker', '000001.SZ', '--mode', 'daily']
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(cdu, 'get_expected_trade_date', return_value=date(2026, 11, 12)), \
             mock.patch.object(cdu, 'check_daily_data', return_value=[]):
            self.assertEqual(cdu.main(), 0)


class ReportPathSecurityTest(unittest.TestCase):
    """api/analysis.py 报告读取路径安全约束。"""

    @classmethod
    def setUpClass(cls):
        from flask import Flask
        import api.analysis as analysis_module

        cls.analysis = analysis_module
        app = Flask(__name__)
        app.register_blueprint(analysis_module.analysis_bp, url_prefix='/api')
        cls.app = app
        cls.client = app.test_client()

    def _call(self, report_path):
        with self.app.test_request_context('/'):
            response = self.analysis.get_report_content(report_path)
            return response.get_json()

    @staticmethod
    def _find_data_file(exts, limit_dirs=80):
        data_root = os.path.join(PROJECT_ROOT, 'data')
        if not os.path.isdir(data_root):
            # 干净仓库没有 data/（gitignore），这类“读取真实报告”的用例直接跳过
            raise unittest.SkipTest('本地没有 data/ 目录，跳过真实报告读取用例')
        count = 0
        for ticker in sorted(os.listdir(data_root)):
            ticker_dir = os.path.join(data_root, ticker)
            if not os.path.isdir(ticker_dir):
                continue
            count += 1
            if count > limit_dirs:
                break
            for filename in sorted(os.listdir(ticker_dir)):
                if os.path.splitext(filename)[1].lower() in exts:
                    return f'{ticker}/{filename}'
        return None

    def test_valid_report_can_be_read(self):
        sample = self._find_data_file(('.md',))
        self.assertIsNotNone(sample, 'data/ 下没有可用于测试的报告文件')
        data = self._call(sample)
        self.assertTrue(data['success'], data.get('message'))
        self.assertTrue(data['content'])

        resp = self.client.get('/api/report/' + sample)
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()['success'])

    def test_traversal_path_rejected(self):
        for bad_path in ('../../config.py', '000001.SZ/../../../config.py', '..'):
            data = self._call(bad_path)
            self.assertFalse(data['success'], bad_path)
            self.assertIn('非法报告路径', data['message'])

    def test_absolute_path_rejected(self):
        outside = os.path.join(os.path.dirname(os.path.dirname(PROJECT_ROOT)), 'config.py')
        for bad_path in ('/etc/passwd', outside):
            data = self._call(bad_path)
            self.assertFalse(data['success'], bad_path)
            self.assertIn('非法报告路径', data['message'])

    def test_non_whitelisted_extension_rejected(self):
        for bad_path in ('000001.SZ/evil.py', '000001.SZ/run.sh'):
            data = self._call(bad_path)
            self.assertFalse(data['success'], bad_path)
            self.assertIn('不允许读取该类型文件', data['message'])

        # 真实存在的非白名单文件（png）同样要拒绝
        sample = self._find_data_file(('.png',))
        if sample:
            data = self._call(sample)
            self.assertFalse(data['success'])
            self.assertIn('不允许读取该类型文件', data['message'])

    def test_resolve_rejects_outside_data_dir(self):
        with self.assertRaises(ValueError):
            self.analysis._resolve_report_path('../../config.py')
        with self.assertRaises(ValueError):
            self.analysis._resolve_report_path('/etc/passwd')


class WebUIRunConfigTest(unittest.TestCase):
    """web_ui 默认只监听本机、关闭 debug，可被环境变量覆盖。"""

    def test_default_host_is_loopback(self):
        import web_ui
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('GP_ANA_WEB_HOST', None)
            os.environ.pop('GP_ANA_WEB_DEBUG', None)
            host, port, debug = web_ui.get_run_config()
        self.assertEqual(host, '127.0.0.1')
        self.assertEqual(port, 8081)
        self.assertFalse(debug)

    def test_env_override(self):
        import web_ui
        with mock.patch.dict(os.environ, {'GP_ANA_WEB_HOST': '0.0.0.0', 'GP_ANA_WEB_DEBUG': '1'},
                             clear=False):
            host, port, debug = web_ui.get_run_config()
        self.assertEqual(host, '0.0.0.0')
        self.assertTrue(debug)

    def test_debug_disabled_override(self):
        import web_ui
        with mock.patch.dict(os.environ, {'GP_ANA_WEB_DEBUG': 'false'}, clear=False):
            _, _, debug = web_ui.get_run_config()
        self.assertFalse(debug)


class BacktestTaskFailureTest(unittest.TestCase):
    """api/backtest.py 的数据更新 / 回测失败必须让任务 failed。"""

    def setUp(self):
        import api.backtest as bt
        self.bt = bt
        self.saved_run_command_stream = bt._run_command_stream
        self.saved_status = dict(bt.backtest_task_status)
        bt.backtest_task_status.clear()
        self.saved_watchlist = sys.modules.get('watchlist')
        fake_watchlist = types.ModuleType('watchlist')
        fake_watchlist.WATCHLIST = [('000001.SZ', '测试股票')]
        sys.modules['watchlist'] = fake_watchlist

    def tearDown(self):
        self.bt._run_command_stream = self.saved_run_command_stream
        self.bt.backtest_task_status.clear()
        self.bt.backtest_task_status.update(self.saved_status)
        if self.saved_watchlist is not None:
            sys.modules['watchlist'] = self.saved_watchlist
        else:
            sys.modules.pop('watchlist', None)

    def _install_fake_stream(self, data_code=0, backtest_code=0):
        commands = []

        def fake_stream(command, cwd, messages, prefix='', max_line_len=150, on_line=None):
            commands.append(command)
            messages.append(f'{prefix}模拟命令输出')
            return data_code if 'check_data_updates' in command else backtest_code

        self.bt._run_command_stream = fake_stream
        return commands

    def test_data_update_failure_aborts_before_backtest(self):
        commands = self._install_fake_stream(data_code=2, backtest_code=0)
        self.bt.run_backtest_task('bt-update-fail')
        status = self.bt.backtest_task_status['bt-update-fail']

        self.assertEqual(status['status'], 'failed')
        self.assertEqual(len(commands), 1)
        self.assertIn('check_data_updates', commands[0])
        self.assertIn('--mode price', commands[0])
        self.assertNotIn('batch_margin_collector', commands[0])
        self.assertTrue(any('数据更新返回码 2' in msg for msg in status['messages']))
        self.assertFalse(any('backtest_all_stocks' in cmd for cmd in commands))

    def test_backtest_failure_marks_task_failed(self):
        commands = self._install_fake_stream(data_code=0, backtest_code=1)
        self.bt.run_backtest_task('bt-run-fail')
        status = self.bt.backtest_task_status['bt-run-fail']

        self.assertEqual(status['status'], 'failed')
        self.assertEqual(len(commands), 2)
        self.assertTrue(any('backtest_all_stocks' in cmd for cmd in commands))
        self.assertTrue(any('回测失败，返回码: 1' in msg for msg in status['messages']))

    def test_success_marks_task_completed(self):
        self._install_fake_stream(data_code=0, backtest_code=0)
        self.bt.run_backtest_task('bt-success')
        status = self.bt.backtest_task_status['bt-success']

        self.assertEqual(status['status'], 'completed')
        self.assertEqual(status['progress'], 100)

    def test_latest_report_uses_real_date_not_string_order(self):
        # 文件名里的 's' 大于数字 '2'，按字符串排序会选错旧文件
        files = ['monitor_report_simplified_20260527.md', 'monitor_report_20260928.md']
        self.assertEqual(self.bt._latest_file(files), 'monitor_report_20260928.md')
        self.assertEqual(self.bt._extract_date('monitor_report_simplified_20260527.md'), '20260527')


if __name__ == '__main__':
    unittest.main()
