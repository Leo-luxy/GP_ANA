from flask import Blueprint, request, jsonify
import os
import sys
import subprocess
import threading
import time
import csv
import json
import hashlib
import io
import re
import uuid
from datetime import datetime

import pandas as pd
from stocks_filter.batch_backtest_filter import (atomic_status, expected_trade_asof,
    normalize_ticker, file_hash, get_params)
import backtest_artifacts
from config import DATA_DIR

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SELECTION_DIR = os.path.join(PROJECT_ROOT, "stocks_filter")


def _read_current_holdings(base_path=None, saved=None):
    '''展示最近一次最终持仓。

    规则：文件本身可信（CSV 指纹、计数、行身份一致）就展示；
    日期不是当前交易日、行情在结果之后更新过、参数版本变化等只作为提示返回，
    不再拒绝展示——用户要看到的是最近一次结果，而不是被报错挡住。
    '''
    base_path = base_path or SELECTION_DIR
    path = os.path.join(base_path, 'final_holdings.csv')
    status_path = os.path.join(base_path, 'final_holdings_status.json')
    warnings = []
    try:
        if saved is None:
            with open(status_path, encoding='utf-8') as fh:
                status = json.load(fh)
        else:
            status = saved['status']
        if not isinstance(status, dict):
            raise ValueError('状态文件格式损坏')
        if status.get('result_kind') == 'preliminary' or status.get('state') == 'preliminary':
            candidates = int(status.get('candidates') or 0)
            return {'success': False, 'stale': False, 'preliminary_only': True,
                    'candidates': candidates,
                    'message': ('本次只做了初步筛选，候选 %d 只；'
                                '尚未生成最终持仓（需要勾选“详细回测”再跑一次）' % candidates)}
        if (status.get('completed') is not True or status.get('valid') is not True
                or status.get('void') is not False
                or status.get('state') not in ('completed', 'degraded')):
            return {'success': False, 'stale': True, 'status': status,
                    'degraded': bool(status.get('degraded')),
                    'warnings': status.get('warnings', []),
                    'message': status.get('void_reason') or '上一轮批筛未成功完成，暂无可用结果'}
        if status.get('strategy') != 'simple' or status.get('params') != get_params('simple'):
            warnings.append('结果参数与当前预设不同，仅供参考')
        tickers = status.get('input_tickers')
        if not isinstance(tickers, list) or not tickers or any(normalize_ticker(t) != t for t in tickers):
            raise ValueError('输入股票身份缺失或非法')
        if len(tickers) != status.get('input_count') or len(set(tickers)) != len(tickers):
            raise ValueError('输入股票数量不符或重复')
        processed = status.get('processed_tickers')
        if (not isinstance(processed, list) or not processed
                or any(t not in tickers for t in processed)):
            raise ValueError('已处理股票清单缺失或非法')
        asof = status.get('data_asof')
        if not isinstance(asof, str) or len(asof) != 8:
            raise ValueError('结果缺少行情截止日')
        try:
            # 校验基准取"本地实际能取到的最新行情日期"：收盘后数据源常还没发布当天 K 线，
            # 这时不该把昨天算出的结果标成过期。
            from check_data_updates import get_latest_available_trade_date
            current_asof = pd.Timestamp(
                get_latest_available_trade_date(tickers)).strftime('%Y%m%d')
        except Exception as exc:  # 取不到当前交易日时仍然展示历史结果
            current_asof = None
            warnings.append('无法确定当前交易日：%s' % exc)
        if current_asof and asof != current_asof:
            warnings.append('数据截止 %s，当前交易日 %s；需要最新结果请重新批筛' % (asof, current_asof))
        name = status.get('input_file')
        if not isinstance(name, str) or name != os.path.basename(name):
            warnings.append('结果未记录候选池文件身份')
        else:
            try:
                if file_hash(os.path.join(base_path, name)) != status.get('input_sha256'):
                    warnings.append('候选池文件在本次结果之后变过，名单仅代表当时候选池')
            except OSError:
                warnings.append('候选池文件已不存在，无法复核来源')
        manifests = status.get('source_manifest')
        if not isinstance(manifests, dict) or set(manifests) != set(processed):
            warnings.append('来源清单不完整，无法复核行情版本')
        try:
            # 用"完成时间"作基准：本轮自身的行情/指标写入都发生在 generated_at 之后，
            # 若用开始时间会把本轮自己的更新误判成"结果之后又变过"。
            generated = datetime.fromisoformat(
                status.get('finished_at') or status.get('generated_at') or '')
        except (TypeError, ValueError):
            generated = None
            warnings.append('结果缺少生成时间')
        if generated is not None:
            drifted = 0
            for ticker in processed:
                indicator_path = os.path.join(DATA_DIR, ticker, '%s_indicators.csv' % ticker)
                try:
                    if os.path.getmtime(indicator_path) > generated.timestamp() + 1:
                        drifted += 1
                except OSError:
                    continue
            if drifted:
                warnings.append('%d 只股票的行情/指标在本次结果之后更新过（展示的是当时结果）' % drifted)
        if saved is None:
            with open(path, 'rb') as fh:
                payload = fh.read()
        else:
            payload = saved['csv'].encode('utf-8')
        if hashlib.sha256(payload).hexdigest() != status.get('csv_sha256'):
            raise ValueError('持仓 CSV 与状态内容指纹不匹配（文件被改动或写入不完整）')
        reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')))
        required = {'股票代码', '入场日期', '当前日期', '数据截止日', '离场类型'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('持仓 CSV 表头损坏')
        rows = list(reader)
        for row in rows:
            row_asof = str(row.get('数据截止日', ''))
            # 统一日期是内部完整性门禁：即使展示历史结果，也不能混日。
            if (row.get('股票代码') not in processed
                    or not row_asof.isdigit() or len(row_asof) != 8
                    or row_asof != asof
                    or str(row.get('当前日期', '')).replace('-', '')[:8] != row_asof
                    or row.get('离场类型') != 'final_close'):
                raise ValueError('持仓行身份或截止日与本轮记录不一致')
        if len(rows) != status.get('holdings'):
            raise ValueError('持仓数量与状态不符')
        counts = [status.get(k) for k in ('processed', 'input_count', 'holding', 'flat', 'failed', 'holdings')]
        if any(type(n) is not int or n < 0 for n in counts):
            raise ValueError('批筛计数缺失或损坏')
        if (status['input_count'] <= 0
                or status['processed'] != len(processed)
                or status['processed'] != status['holding'] + status['flat']
                or status['holding'] != status['holdings']
                or status['failed'] != status['input_count'] - status['processed']):
            raise ValueError('批筛计数与已处理清单不符')
        degraded = bool(status.get('degraded')) or status.get('state') == 'degraded'
        return {'success': True, 'data': rows, 'source': 'final_holdings.csv',
                'status': status, 'degraded': degraded,
                'warnings': list(status.get('warnings', [])) + warnings,
                'data_asof': asof, 'current_asof': current_asof,
                'is_current': bool(current_asof) and asof == current_asof,
                'excluded_bj': status.get('excluded_bj', [])}
    except (OSError, ValueError, TypeError, csv.Error) as exc:
        return {'success': False, 'stale': True, 'message': '无可验证的最终持仓: %s' % exc}


def read_final_holdings(base_path=None):
    """页面显示最近成功结果；当前任务的验收不使用历史回退。"""
    import selection_result_store as store
    base_path = base_path or SELECTION_DIR
    current = _read_current_holdings(base_path)
    if current.get('success'):
        return current
    try:
        with open(os.path.join(base_path, 'final_holdings_status.json'), encoding='utf-8') as fh:
            attempt = json.load(fh)
    except (OSError, ValueError):
        attempt = {}
    if attempt.get('valid') is True:
        return current  # 文件损坏不伪装为普通任务失败。
    try:
        with open(store.saved_path(os.path.join(base_path, 'final_holdings.csv')), encoding='utf-8') as fh:
            saved = json.load(fh)
        if saved.get('schema') != 1:
            return current
        result = _read_current_holdings(base_path, saved=saved)
        if result.get('success'):
            result['showing_saved_result'] = True
            result['latest_attempt'] = dict(state=attempt.get('state'), reason=attempt.get('void_reason'))
            result['warnings'].insert(0, '展示最近一次成功保存的选股结果；本次未完成的任务不会覆盖它')
            return result
    except (OSError, ValueError, KeyError, TypeError):
        pass
    # 兼容旧版本已经覆盖掉状态、但仍留下表格的情形：只能标为未核验历史展示。
    try:
        legacy_path = os.path.join(base_path, 'final_holdings_legacy_display.json')
        with open(legacy_path, encoding='utf-8') as fh:
            legacy = json.load(fh)
        payload = legacy['csv'].encode('utf-8')
        if hashlib.sha256(payload).hexdigest() != legacy.get('csv_sha256'):
            return current
        rows = list(csv.DictReader(io.StringIO(legacy['csv'])))
        dates = {row.get('数据截止日') for row in rows}
        if not rows or len(dates) != 1:
            return current
        asof = next(iter(dates))
        datetime.strptime(asof, '%Y%m%d')
        if any(normalize_ticker(row['股票代码']) != row['股票代码'] or
               row.get('离场类型') != 'final_close' or
               row.get('当前日期', '').replace('-', '')[:8] != asof for row in rows):
            return current
        return dict(success=True, data=rows, showing_saved_result=True, verified=False,
                    data_asof=asof, is_current=False, source='legacy_display',
                    warnings=['历史保存结果：旧批次状态已被覆盖，仅供查看；不代表本次任务成功或当天全市场数据已齐'])
    except (OSError, ValueError, KeyError, TypeError, csv.Error):
        return current


def invalidate_holdings(reason):
    import selection_result_store
    selection_result_store.preserve_existing(
        os.path.join(SELECTION_DIR, 'final_holdings.csv'),
        os.path.join(SELECTION_DIR, 'final_holdings_status.json'))
    legacy_path = os.path.join(SELECTION_DIR, 'final_holdings.csv')
    selection_result_store.preserve_legacy_display(legacy_path)
    selection_result_store.backfill_legacy(legacy_path)
    atomic_status(os.path.join(SELECTION_DIR, "final_holdings_status.json"),
                  {"void": True, "valid": False, "completed": False,
                   "void_reason": reason, "state": "running", "run_id": uuid.uuid4().hex})

stock_selection_bp = Blueprint('stock_selection', __name__)

selection_tasks = {}
selection_results = {}

_PROGRESS_RE = re.compile(r'\[(\d+)/(\d+)\]')


def _update_step_progress(task_id, line):
    """把子进程的 [i/N] 进度行换算成本步骤的百分比区间，供前端进度条使用。"""
    task = selection_tasks.get(task_id)
    if not task:
        return
    base, span = task.get('progress_base'), task.get('progress_span')
    match = _PROGRESS_RE.search(line or '')
    if base is None or span is None or not match:
        return
    done, total = int(match.group(1)), int(match.group(2))
    if total <= 0:
        return
    ratio = min(done, total) / total
    phase = ''
    if '预检行情' in line:
        ratio *= 0.3
        phase = '行情预检 '
    elif '统一截止' in line:
        ratio = 0.3 + 0.7 * ratio
        phase = '统一日期回测 '
    task['progress'] = max(task.get('progress', 0), max(0, min(99, int(base + span * ratio))))
    task['progress_label'] = f'{phase}（{done}/{total} 只）'


def _set_step_progress(task_id, value, label):
    """设置某个长步骤的进度与说明（没有 [i/N] 输出的步骤靠这个推进）。"""
    task = selection_tasks.get(task_id)
    if not task:
        return
    task['progress'] = max(0, min(99, int(value)))
    task['progress_label'] = label or ''


def run_command_with_output(task_id, cmd, cwd, description):
    messages = selection_tasks[task_id]['messages']
    messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description}")
    selection_tasks[task_id]['messages'] = messages.copy()
    
    try:
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            bufsize=1,
            universal_newlines=True,
            env=env
        )
        
        while True:
            line = process.stdout.readline()
            if line == '' and process.poll() is not None:
                break
            if line:
                messages.append(line.strip())
                selection_tasks[task_id]['messages'] = messages.copy()
                _update_step_progress(task_id, line)
        
        return_code = process.wait()
        if return_code == 0:
            messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 完成")
        else:
            messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 失败，返回码: {return_code}")
        
        selection_tasks[task_id]['messages'] = messages.copy()
        return return_code
    except Exception as e:
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 异常: {str(e)}")
        selection_tasks[task_id]['messages'] = messages.copy()
        return -1

def _fail_selection(task_id, messages, reason):
    """取数失败时中止任务：绝不让旧数据被当成今天的结果展示"""
    messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务中止：{reason}")
    messages.append("本轮结果无效，已禁止展示旧持仓或不完整名单。")
    selection_results.pop(task_id, None)
    selection_tasks[task_id]['status'] = 'failed'
    selection_tasks[task_id]['messages'] = messages.copy()
    return False


def run_selection(task_id, preliminary, detailed):
    # 当前文件位于 api 目录，需要获取项目根目录，然后定位到 stocks_filter
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    base_path = SELECTION_DIR
    forced_asof = None
    messages = []
    
    selection_tasks[task_id] = {'status': 'running', 'progress': 0, 'messages': messages}
    selection_results.pop(task_id, None)
    try:
        invalidate_holdings('新选股任务运行中，旧结果已作废')
        
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 开始市场选股任务 ==========")
        selection_tasks[task_id]['messages'] = messages.copy()
        
        # 进度区间：初筛占 0-40%，最终持仓占其余部分；批筛内部按 [i/N] 行细化。
        if preliminary:
            selection_tasks[task_id].update(progress_base=0, progress_span=15)
            _set_step_progress(task_id, 1, '获取全市场日线行情')
            return_code = run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step1_daily.py')],
                base_path,
                "执行 step1_daily.py - 获取全市场日线行情"
            )
            if return_code != 0:
                return _fail_selection(task_id, messages,
                    f"step1_daily.py 未取到行情数据（返回码 {return_code}；常见原因：系统代理未启动导致断网、Tushare 限流或权限问题），已中止")
            
            temp_path = os.path.join(base_path, 'stocks_daily_temp.csv')
            if os.path.isfile(temp_path):
                temp = pd.read_csv(temp_path, dtype=str)
                temp_dates = set(temp['trade_date'].astype(str))
                if len(temp_dates) != 1:
                    return _fail_selection(task_id, messages, '初筛行情日期混杂，禁止继续')
                forced_asof = next(iter(temp_dates))
            selection_tasks[task_id].update(progress_base=15, progress_span=15)
            _set_step_progress(task_id, 16, '获取基础指标并合并')
            return_code = run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step2_daily_basic.py')],
                base_path,
                "执行 step2_daily_basic.py - 获取基础指标并合并"
            )
            if return_code == 4:
                # 基础指标返回不全属于发布未齐；只允许当日整体回退一次。
                import selection_snapshot
                temp = pd.read_csv(os.path.join(base_path, 'stocks_daily_temp.csv'), dtype=str)
                source_day = str(temp['trade_date'].iloc[0])
                if source_day != datetime.now().strftime('%Y%m%d'):
                    return _fail_selection(task_id, messages, '前一交易日基础指标仍未齐，停止选股，不继续回退')
                forced_asof = selection_snapshot.previous_trade_asof(source_day)
                messages.append(f'基础指标未齐，整批初筛和回测统一回退 {forced_asof}')
                for script, extra in [('step1_daily.py', ['--trade-date', forced_asof]),
                                      ('step2_daily_basic.py', [])]:
                    return_code = run_command_with_output(task_id,
                        [sys.executable, os.path.join(base_path, script)] + extra,
                        base_path, f'按 {forced_asof} 重建 {script}')
                    if return_code != 0:
                        break
            if return_code != 0:
                return _fail_selection(task_id, messages,
                    f"step2_daily_basic.py 未取到基础指标数据（返回码 {return_code}），已中止")
            
            selection_tasks[task_id].update(progress_base=30, progress_span=10)
            _set_step_progress(task_id, 31, '条件筛选')
            return_code = run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step3_filter.py')],
                base_path,
                "执行 step3_filter.py - 执行初步筛选"
            )
            if return_code != 0:
                return _fail_selection(task_id, messages,
                    f"step3_filter.py 执行失败（返回码 {return_code}），已中止")
        
        if detailed:
            selection_tasks[task_id].update(progress_base=40 if preliminary else 0,
                                            progress_span=55 if preliminary else 95)
            _set_step_progress(task_id, 40 if preliminary else 1, '批量回测筛选（逐只处理）')
            return_code = run_command_with_output(task_id,
                # --skip-indicators 只在来源/内容/版本全部校验通过时复用指标，
                # 行情有更新会验证失败并自动重算，既省时间又不牺牲正确性。
                [sys.executable, os.path.join(base_path, 'batch_backtest_filter.py'),
                 '--skip-indicators'] + (['--asof', forced_asof] if forced_asof else []),
                base_path,
                "执行 batch_backtest_filter.py - 批量回测筛选"
            )
            if return_code != 0:
                # 返回码约定：1=列表缺失或整批失败；2=结果身份/时效异常（必须中断）。
                # 脚本自身的报错已在输出消息里原样展示，这里再给出明确的失败原因。
                if return_code == 2:
                    reason = "batch_backtest_filter.py 返回码 2：结果身份或时效异常（可能未生成本轮有效结果），已中止"
                elif return_code == 3:
                    reason = ("batch_backtest_filter.py 返回码 3：系统性失败（全部失败或失败过半），"
                              "本轮结果不可用，请先排查数据与回测")
                else:
                    reason = f"batch_backtest_filter.py 执行失败（返回码 {return_code}），已中止"
                return _fail_selection(task_id, messages, reason)
            _set_step_progress(task_id, 99, '读取结果')

        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 读取市场选股结果 ==========")
        
        if detailed:
            result = _read_current_holdings(base_path)
            selection_tasks[task_id].update(degraded=result.get('degraded', False),
                                            warnings=result.get('warnings', []),
                                            result_status=result.get('status', {}))
            if not result['success']:
                if result.get('degraded'):
                    selection_tasks[task_id].update(status='degraded', progress=100)
                    messages.append(result['message'])
                    selection_tasks[task_id]['messages'] = messages.copy()
                    return
                return _fail_selection(task_id, messages, result['message'])
            selection_results[task_id] = result['data']
        else:
            # 初筛只是候选池，不得进入当前最终持仓缓存或 get_result。
            candidate_path = os.path.join(base_path, 'stocks_daily_filtered.csv')
            with open(candidate_path, encoding='utf-8-sig') as fh:
                candidates = list(csv.DictReader(fh))
            selection_tasks[task_id].update(result_kind='preliminary', candidates=candidates)
            # 明确记录"这轮只做了初筛"，避免查询接口把旧的最终持仓或过期结果当成当前持仓
            atomic_status(os.path.join(base_path, 'final_holdings_status.json'),
                          {'void': True, 'valid': False, 'completed': False,
                           'result_kind': 'preliminary', 'candidates': len(candidates),
                           'state': 'preliminary', 'run_id': uuid.uuid4().hex,
                           'void_reason': f'本次只做了初筛，候选 {len(candidates)} 只，未生成最终持仓'})
            messages.append(f'初筛完成，候选 {len(candidates)} 只；尚未生成最终持仓')

        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 市场选股任务完成 ==========")
        if detailed and selection_tasks[task_id].get('degraded'):
            messages.append('注意：本轮有股票未处理成功，名单为部分结果，页面以黄色降级提示展示')
            selection_tasks[task_id]['status'] = 'degraded'
            selection_tasks[task_id]['progress'] = 100
        else:
            selection_tasks[task_id]['status'] = 'completed'
        selection_tasks[task_id]['progress'] = 100
        selection_tasks[task_id]['progress'] = 100
        selection_tasks[task_id]['messages'] = messages.copy()
        
    except Exception as e:
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务执行异常: {str(e)}")
        selection_tasks[task_id]['status'] = 'failed'
        selection_tasks[task_id]['messages'] = messages.copy()

@stock_selection_bp.route('/stock_selection/run', methods=['POST'])
def run_stock_selection():
    data = request.get_json()
    preliminary = data.get('preliminary', False)
    detailed = data.get('detailed', False)
    
    if not preliminary and not detailed:
        return jsonify({'success': False, 'message': '请至少选择一种选股模式'})
    
    task_id = f"selection_{int(time.time())}"
    selection_tasks[task_id] = {
        'status': 'pending',
        'progress': 0,
        'messages': ['任务已创建，等待执行...']
    }
    
    thread = threading.Thread(target=run_selection, args=(task_id, preliminary, detailed))
    thread.daemon = True
    thread.start()
    
    return jsonify({'success': True, 'task_id': task_id})

@stock_selection_bp.route('/stock_selection/task_status/<task_id>')
def get_task_status(task_id):
    if task_id not in selection_tasks:
        return jsonify({'status': 'not_found'})
    
    return jsonify(selection_tasks[task_id])

@stock_selection_bp.route('/stock_selection/get_result')
def get_selection_result():
    return jsonify(read_final_holdings())
@stock_selection_bp.route('/stock_selection/history')
def selection_history():
    import selection_result_store as store
    path = os.path.join(SELECTION_DIR, 'final_holdings.csv')
    try:
        dates = store.history_index(path)
    except OSError as exc:
        return jsonify({'success': False, 'message': f'读取历史目录失败：{exc}'})
    return jsonify({'success': True, 'dates': dates})


@stock_selection_bp.route('/stock_selection/history/<date>')
def selection_history_detail(date):
    import selection_result_store as store
    path = os.path.join(SELECTION_DIR, 'final_holdings.csv')
    try:
        payload, status = store.read_history(path, date)
        rows = list(csv.DictReader(io.StringIO(payload.decode('utf-8-sig'))))
    except (OSError, ValueError) as exc:
        return jsonify({'success': False, 'message': f'读取 {date} 历史结果失败：{exc}'})
    warnings = ['查看的是 ' + date + ' 留存的最终名单，用于复盘当时预测，不代表当前行情']
    if status.get('degraded'):
        warnings.append('该日结果有股票未处理成功，名单不完整')
    return jsonify({'success': True, 'data': rows, 'status': status,
                    'data_asof': date, 'is_current': False, 'history': True,
                    'source': f'selection_history/{date}', 'warnings': warnings})
