# api/backtest.py
# 策略回测相关的API
import os
import sys
import subprocess
import json
import time
import pandas as pd
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file
import threading
import queue
import re
import shlex
from api.common import parse_data_status

# 创建蓝图
backtest_bp = Blueprint('backtest', __name__)

# 任务队列和状态管理
backtest_task_queue = queue.Queue()
backtest_task_status = {}

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

def _extract_date(filename):
    """从文件名中提取 8 位日期，用于按真实日期排序。

    ⚠️ 不能直接用字符串排序：'monitor_report_simplified_20260527.md' 中的
    's' 大于数字 '2'，字符串降序会把它排到 'monitor_report_20260928.md' 前面，
    导致页面显示几百天前的过时报告。
    """
    m = re.search(r'(\d{8})', filename)
    return m.group(1) if m else '00000000'

def _latest_file(files):
    """按真实日期取最新文件；日期相同时优先非简化版。"""
    return sorted(
        files,
        key=lambda f: (_extract_date(f), 0 if 'simplified' in f else 1),
        reverse=True
    )[0]

VALID_BACKTEST_MODES = ('full', 'simple')


def _requested_mode(default='full'):
    """读取前端策略；非法策略直接拒绝，不能冒充默认模式。"""
    mode = (request.args.get('mode') or default).strip().lower()
    if mode not in VALID_BACKTEST_MODES:
        raise ValueError('无效的回测策略')
    return mode


def _pick_by_mode(files, mode, prefer_date=None):
    """只允许显式策略名；报告有效性仍必须通过元数据校验。"""
    matches = [name for name in files if f'_{mode}_' in name]
    if prefer_date:
        matches = [name for name in matches if _extract_date(name) == prefer_date]
    return sorted(matches, reverse=True)[0] if matches else None


def _report_names(prefix, extension, mode):
    return [name for name in os.listdir(DATA_DIR)
            if re.fullmatch(re.escape(prefix) + '_' + mode + r'_\d{8}' +
                            re.escape(extension), name)]


def _current_report(prefix, extension, kind, mode):
    """优先返回身份完整的报告；没有就展示最近一份可读报告（标明未核验）。

    用户要的是“看到最近的报告”，身份校验只用于判断是否可信，不再直接挡住展示。
    """
    import backtest_all_stocks as reports
    if not os.path.isdir(DATA_DIR):
        raise ValueError('报告目录不存在，请运行回测')
    stocks = reports.get_all_stocks()
    try:
        asof = reports.expected_trade_date(stocks)
        identity_error = None
    except Exception as exc:
        asof, identity_error = None, str(exc)
    modes = [mode] + [m for m in VALID_BACKTEST_MODES if m != mode]
    for index, candidate in enumerate(modes):
        for name in sorted(_report_names(prefix, extension, candidate), reverse=True):
            path = os.path.join(DATA_DIR, name)
            if asof is None:
                break
            try:
                reports.validate_report_file(path, kind, candidate, asof, stocks)
                return path, dict(mode=candidate, verified=True,
                                  switched=(index > 0), reason='')
            except (OSError, ValueError, KeyError, TypeError, reports.MonitorDataError):
                continue
    # 兜底：任意模式里最近的一份，能读就展示。
    fallback = []
    for candidate in modes:
        fallback += [(name, candidate) for name in _report_names(prefix, extension, candidate)]
    if fallback:
        name, candidate = sorted(fallback, key=lambda item: _extract_date(item[0]), reverse=True)[0]
        reason = identity_error or '报告未通过身份校验（可能由旧版本生成或行情已更新）'
        return os.path.join(DATA_DIR, name), dict(mode=candidate, verified=False,
                                                  switched=candidate != mode, reason=reason)
    raise ValueError(f'暂无任何可展示的 {mode} 报告，请先运行回测')


def _report_warning(info):
    if info['verified']:
        return ''
    return ('当前展示的是最近一份报告，但' + info['reason'] +
            '；如需要当日结论请重跑回测。')


def get_company_name(ticker):
    """获取股票的公司简称"""
    company_file = os.path.join(DATA_DIR, ticker, f"{ticker}_company_basic.json")
    if os.path.exists(company_file):
        try:
            with open(company_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if 'basic_info' in data and '公司简称' in data['basic_info']:
                    return data['basic_info']['公司简称']
        except Exception:
            pass
    return ticker

def _run_command_stream(command, cwd, messages, prefix='', max_line_len=150, on_line=None):
    """执行子命令并逐行回传输出，返回真实退出码（启动异常返回 -1）。

    逐行读取只是为了前端能看到实时日志；退出码由调用方检查，
    非 0 一律按失败处理，不能降级成「警告」。
    """
    try:
        data_failures = []
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=cwd,
            bufsize=1
        )
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                status = parse_data_status(line)
                if status:
                    data_failures.extend(status.get('critical_failures', []))
                messages.append(f'{prefix}{line.strip()[:max_line_len]}')
                if on_line:
                    on_line(line)
        returncode = process.wait()
        return returncode or (1 if data_failures else 0)
    except Exception as e:
        messages.append(f'{prefix}执行异常: {e}')
        return -1


def run_backtest_task(task_id, skip_data_update=False, use_simplified=False):
    """运行回测任务

    Args:
        task_id: 任务ID
        skip_data_update: 是否跳过数据更新步骤，默认为False（执行完整流程）
        use_simplified: 是否使用简化版策略，默认为False（使用原始版）

    数据更新或回测子进程返回非 0 时任务直接 failed 并停止后续步骤：
    不允许在未更新的旧数据上继续跑回测，也不把失败当警告放行。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        backtest_task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'messages': []
        }

        messages = []
        total_stocks = 0
        warnings = []

        def _on_data_line(line):
            status = parse_data_status(line)
            if status:
                warnings.extend(str(item) for item in status.get('warnings', []))
                if status.get('degraded') and not status.get('warnings'):
                    warnings.append('数据检查返回降级状态')

        # 获取股票列表 - 优先从关注列表读取
        ticker_list = []
        try:
            from watchlist import WATCHLIST
            ticker_list = [item[0] for item in WATCHLIST]
            messages.append(f'从关注列表读取到 {len(ticker_list)} 只股票')
        except ImportError:
            messages.append('未找到 watchlist.py，从 data 目录获取股票')
            # 降级方案：从data目录获取
            if os.path.exists(DATA_DIR):
                for item in os.listdir(DATA_DIR):
                    item_path = os.path.join(DATA_DIR, item)
                    if os.path.isdir(item_path):
                        qfq_file = os.path.join(item_path, f"{item}_qfq.csv")
                        if os.path.exists(qfq_file):
                            ticker_list.append(item)
        ticker_list.sort()
        total_stocks = len(ticker_list)

        # 步骤1：数据更新（可选）
        if not skip_data_update:
            messages.append('开始：更新股票数据')
            backtest_task_status[task_id] = {
                'status': 'running',
                'progress': 0,
                'messages': messages.copy()
            }

            if not ticker_list:
                messages.append('失败：未在 data 目录中检测到任何股票，无法更新数据与回测')
                backtest_task_status[task_id] = {
                    'status': 'failed',
                    'progress': 100,
                    'messages': messages.copy(),
                    'timestamp': datetime.now().strftime('%Y%m%d')
                }
                return

            progress_step = 25 / total_stocks  # 数据更新占25%进度
            messages.append(f'检测到 {total_stocks} 只股票')

            for i, ticker in enumerate(ticker_list):
                messages.append(f'更新股票 {ticker} ({i+1}/{total_stocks})')
                backtest_task_status[task_id] = {
                    'status': 'running',
                    'progress': i * progress_step,
                    'messages': messages.copy()
                }

                # 回测只依赖行情与技术指标：只更新这两项。
                # 资金流/融资融券/估值只服务于完整分析报告，不在这里逐只抓取。
                data_update_cmd = (f'{shlex.quote(sys.executable)} check_data_updates.py '
                                   f'--mode price --ticker {shlex.quote(ticker)}')
                returncode = _run_command_stream(
                    data_update_cmd, project_root, messages,
                    prefix=f'数据更新[{ticker}]: ', max_line_len=100, on_line=_on_data_line
                )
                if returncode != 0:
                    messages.append(f'失败：股票 {ticker} 数据更新返回码 {returncode}，'
                                    f'已中止回测（不允许在未更新的旧数据上回测）')
                    backtest_task_status[task_id] = {
                        'status': 'failed',
                        'progress': 100,
                        'messages': messages.copy(),
                        'timestamp': datetime.now().strftime('%Y%m%d')
                    }
                    return
                messages.append(f'完成：股票 {ticker} 数据更新')
        else:
            messages.append('跳过：数据更新（用户选择跳过）')

        backtest_task_status[task_id] = {
            'status': 'running',
            'progress': 25 if not skip_data_update else 0,
            'messages': messages.copy()
        }

        # 步骤2：运行回测
        strategy_name = '简化版策略(MA5>MA20)' if use_simplified else '完整版策略(MA5>MA10>MA20>MA60)'
        messages.append(f'开始：运行策略回测 ({strategy_name})')
        # 根据是否跳过数据更新，设置不同的起始进度
        backtest_start_progress = 30 if not skip_data_update else 5
        backtest_task_status[task_id] = {
            'status': 'running',
            'progress': backtest_start_progress,
            'messages': messages.copy()
        }

        # 使用统一回测模块，通过 --mode 控制策略
        mode_flag = '--mode simple' if use_simplified else '--mode full'
        backtest_cmd = f'{shlex.quote(sys.executable)} backtest_all_stocks.py {mode_flag}'
        progress = backtest_start_progress

        def _on_backtest_line(line):
            nonlocal progress
            if '分析' in line:
                progress = min(95, progress + 2)
            elif '保存' in line:
                progress = min(95, progress + 1)
            backtest_task_status[task_id] = {
                'status': 'running',
                'progress': progress,
                'messages': messages.copy()
            }

        returncode = _run_command_stream(
            backtest_cmd, project_root, messages,
            prefix='回测: ', max_line_len=150, on_line=_on_backtest_line
        )
        if returncode != 0:
            summary = (f'回测未完成（返回码 {returncode}）：存在行情/指标或产物校验失败。'
                       '未把不完整报告当作有效结果；详情见日志。')
            messages.append(f'失败：回测失败，返回码: {returncode}')
            backtest_task_status[task_id] = {
                'status': 'failed',
                'error_summary': summary,
                'progress': 100,
                'messages': messages.copy(),
                'timestamp': datetime.now().strftime('%Y%m%d')
            }
            return
        messages.append('完成：策略回测')

        backtest_task_status[task_id] = {
            'status': 'completed',
            'progress': 100,
            'messages': messages,
            'degraded': bool(warnings),
            'warnings': warnings,
            'timestamp': datetime.now().strftime('%Y%m%d')
        }
    except Exception as e:
        backtest_task_status[task_id] = {
            'status': 'failed',
            'progress': 100,
            'messages': [f'任务执行失败：{str(e)}']
        }

def backtest_worker():
    """回测任务工作线程"""
    while True:
        task = backtest_task_queue.get()
        if task is None:
            break
        task_id, skip_data_update, use_simplified = task
        run_backtest_task(task_id, skip_data_update, use_simplified)
        backtest_task_queue.task_done()

# 启动工作线程
backtest_worker_thread = threading.Thread(target=backtest_worker, daemon=True)
backtest_worker_thread.start()

@backtest_bp.route('/run_backtest', methods=['POST'])
def run_backtest():
    """启动回测任务
    
    请求参数（JSON）：
        skip_data_update: bool, 可选，是否跳过数据更新步骤，默认false（完整流程）
        use_simplified: bool, 可选，是否使用简化版策略，默认false（使用原始版）
    
    两种流程模式：
        1. 完整流程（skip_data_update=false）：数据更新层 → 回测执行层 → 报告生成层
        2. 快速回测（skip_data_update=true）：回测执行层 → 报告生成层
    
    两种策略版本：
        1. 完整版策略（use_simplified=false）：MA5>MA10>MA20>MA60 多重过滤
        2. 简化版策略（use_simplified=true）：仅 MA5>MA20 简单判断
    """
    data = request.get_json() or {}
    skip_data_update = data.get('skip_data_update', False)
    use_simplified = data.get('use_simplified', False)
    
    task_id = f"backtest_{int(time.time())}"
    
    flow_mode = '快速回测' if skip_data_update else '完整流程'
    strategy_mode = '简化版策略' if use_simplified else '完整版策略'
    
    backtest_task_status[task_id] = {
        'status': 'pending',
        'progress': 0,
        'messages': ['任务已加入队列，等待处理'],
        'mode': f'{flow_mode} - {strategy_mode}'
    }
    
    backtest_task_queue.put((task_id, skip_data_update, use_simplified))
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': '回测任务已启动'
    })

@backtest_bp.route('/task_status/<task_id>')
def get_backtest_task_status(task_id):
    """获取回测任务状态"""
    status = backtest_task_status.get(task_id, {
        'status': 'not_found',
        'progress': 0,
        'messages': ['任务不存在']
    })
    return jsonify(status)

def _validated_chart(chart_path, mode, asof, stocks):
    import backtest_all_stocks as reports
    match = re.fullmatch(r'([0-9]{6}\.[A-Z]{2})/([0-9]{6}\.[A-Z]{2})_backtest_'
                         + re.escape(mode) + r'_([0-9]{8})\.png', chart_path)
    if not match or match.group(1) != match.group(2) or match.group(1) not in stocks:
        raise ValueError('图表路径或策略身份无效')
    ticker = match.group(1)
    full_path = os.path.realpath(os.path.join(DATA_DIR, chart_path))
    root = os.path.realpath(DATA_DIR)
    if os.path.commonpath([root, full_path]) != root:
        raise ValueError('图表路径越界')
    reports.validate_report_file(full_path, 'chart', mode, asof, [ticker])
    return full_path


def _first_valid_chart(ticker, directory, modes, asof, tickers):
    import backtest_all_stocks as reports
    if asof is None:
        return None
    for candidate in modes:
        names = [name for name in os.listdir(directory) if re.fullmatch(
            re.escape(ticker) + '_backtest_' + candidate + r'_\d{8}\.png', name)]
        for name in sorted(names, reverse=True):
            chart_path = f'{ticker}/{name}'
            try:
                _validated_chart(chart_path, candidate, asof, tickers)
                return chart_path
            except (OSError, ValueError, KeyError, TypeError, reports.MonitorDataError):
                continue
    return None


def _latest_chart(ticker, directory):
    names = [name for name in os.listdir(directory) if re.fullmatch(
        re.escape(ticker) + r'_backtest_(full|simple)_\d{8}\.png', name)]
    if not names:
        return None
    return f'{ticker}/' + sorted(names, key=_extract_date, reverse=True)[0]


@backtest_bp.route('/get_stock_list')
def get_stock_list():
    """优先列身份完整图表；没有再列各票最近的图表（标未核验），不空着。"""
    import backtest_all_stocks as reports
    try:
        mode = _requested_mode()
        tickers = reports.get_all_stocks()
        try:
            asof = reports.expected_trade_date(tickers)
        except Exception:
            asof = None
        modes = [mode] + [m for m in VALID_BACKTEST_MODES if m != mode]
        stocks = []
        verified = True
        for ticker in tickers:
            if not re.fullmatch(r'[0-9]{6}\.[A-Z]{2}', ticker):
                continue
            directory = os.path.join(DATA_DIR, ticker)
            if not os.path.isdir(directory):
                continue
            picked = _first_valid_chart(ticker, directory, modes, asof, tickers)
            if picked is None:
                picked = _latest_chart(ticker, directory)
                if picked:
                    verified = False
            if picked:
                stocks.append(dict(ticker=ticker, chart_path=picked))
        return jsonify(success=True, stocks=sorted(stocks, key=lambda item: item['ticker']),
                       mode=mode, verified=verified,
                       warning='' if verified else '部分图表来自另一策略或未通过身份校验，仅供参考')
    except Exception as exc:
        return jsonify(success=False, stocks=[], message=str(exc))



@backtest_bp.route('/get_report')
def get_report():
    """仅返回当前策略、期望交易日及完整来源身份匹配的报告。"""
    try:
        path, info = _current_report('monitor_report', '.md', 'monitor', _requested_mode())
        with open(path, encoding='utf-8') as stream:
            content = stream.read()
        return jsonify(success=True, content=add_company_names_to_report(content),
                       filename=os.path.basename(path), mode=info['mode'],
                       verified=info['verified'], warning=_report_warning(info))
    except Exception as exc:
        return jsonify(success=False, message=str(exc))


def add_company_names_to_report(content):
    """在监控报告表格中添加公司简称"""
    lines = content.split('\n')
    new_lines = []
    in_table = False
    has_company_column = False

    for line in lines:
        if '| 股票代码 |' in line:
            if '| 公司简称 |' in line:
                has_company_column = True
            else:
                line = line.replace('| 股票代码 |', '| 股票代码 | 公司简称 |', 1)
            in_table = True
            new_lines.append(line)
        elif in_table and line.startswith('| :---') and not has_company_column:
            line = line.replace('| :--- |', '| :--- | :--- |', 1)
            new_lines.append(line)
        elif in_table and line.startswith('| ') and '|' in line and not has_company_column:
            parts = line.split('|')
            if len(parts) >= 3:
                ticker = parts[1].strip()
                if re.match(r'^\d{6}\.[SHSZ]{2}$', ticker):
                    company_name = get_company_name(ticker)
                    new_line = '|'.join([parts[0], parts[1], f' {company_name} '] + parts[2:])
                    new_lines.append(new_line)
                    continue
            new_lines.append(line)
        else:
            if in_table and not line.startswith('|'):
                in_table = False
            new_lines.append(line)

    return '\n'.join(new_lines)

def _safe_chart_path(chart_path, stocks):
    """只做安全与存在性检查；身份校验失败时用它兜底展示。"""
    match = re.fullmatch(r'([0-9]{6}\.[A-Z]{2})/([0-9]{6}\.[A-Z]{2})_backtest_'
                         r'(full|simple)_([0-9]{8})\.png', chart_path)
    if not match or match.group(1) != match.group(2) or match.group(1) not in stocks:
        raise ValueError('图表路径或策略身份无效')
    full_path = os.path.realpath(os.path.join(DATA_DIR, chart_path))
    root = os.path.realpath(DATA_DIR)
    if os.path.commonpath([root, full_path]) != root:
        raise ValueError('图表路径越界')
    if not os.path.isfile(full_path):
        raise ValueError('图表文件不存在')
    return full_path


@backtest_bp.route('/get_chart/<path:chart_path>')
def get_chart(chart_path):
    """图表能读就返回；身份校验失败只记标记，不再 404 挡住查看。"""
    import backtest_all_stocks as reports
    try:
        mode = _requested_mode()
        stocks = reports.get_all_stocks()
        try:
            asof = reports.expected_trade_date(stocks)
        except Exception:
            asof = None
        verified = True
        try:
            if asof is None:
                raise ValueError('无法确定期望交易日')
            full_path = _validated_chart(chart_path, mode, asof, stocks)
        except (OSError, ValueError, KeyError, TypeError, reports.MonitorDataError):
            verified = False
            full_path = _safe_chart_path(chart_path, stocks)
        response = send_file(full_path, mimetype='image/png', conditional=False, max_age=0)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Chart-Verified'] = 'true' if verified else 'false'
        return response
    except Exception as exc:
        return jsonify(success=False, message=f'图表已失效或身份不明：{exc}'), 404

@backtest_bp.route('/get_backtest_results')
def get_backtest_results():
    """拒绝历史、缺元数据、跨策略与来源失效的汇总。"""
    try:
        path, _info = _current_report('backtest_results', '.csv', 'batch_summary',
                                      _requested_mode())
        df = pd.read_csv(path)
        return jsonify(success=True, data=df.to_dict('records'))
    except Exception as exc:
        return jsonify(success=False, message=str(exc))