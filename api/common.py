# api/common.py
# API 模块共享代码：交易所映射、任务队列管理
import os
import sys
import json
import signal
import subprocess
import time
import threading
import queue

# 添加项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# ============================================================
# 任务状态持久化（避免重启后任务丢失）
# ============================================================
TASK_STATUS_FILE = os.path.join(project_root, '.task_status_cache.json')

def _load_task_status():
    """从文件加载已保存的任务状态"""
    if os.path.exists(TASK_STATUS_FILE):
        try:
            with open(TASK_STATUS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"  加载任务状态缓存失败: {e}")
    return {}

def _save_task_status():
    """将 task_status 持久化到文件"""
    try:
        # 只保存非 running 状态的任务（running 的任务重启后无法恢复）
        saved = {k: v for k, v in task_status.items()
                 if v.get('status') in ('completed', 'failed', 'not_found')}
        with open(TASK_STATUS_FILE, 'w', encoding='utf-8') as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  保存任务状态缓存失败: {e}")

# ============================================================
# 股票代码 → 交易所后缀
# ============================================================
SSE_PREFIXES = ['600', '601', '603', '605', '688']  # 上海证券交易所（含 605 主板）
SZSE_PREFIXES = ['000', '001', '002', '300']  # 深圳证券交易所

def get_exchange_suffix(stock_code: str) -> str:
    """根据6位数字股票代码返回交易所后缀"""
    prefix = stock_code[:3]
    if prefix in SSE_PREFIXES:
        return '.SH'
    elif prefix in SZSE_PREFIXES:
        return '.SZ'
    else:
        return '.SZ'  # 默认深圳

# ============================================================
# 统一任务队列和状态管理
# ============================================================
task_queue = queue.Queue()
task_status = _load_task_status()

def _terminate_process_group(process):
    """终止子进程及其派生的整棵进程树（进程组），用于超时清理。"""
    try:
        if os.name == 'posix':
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass
    except Exception:
        try:
            process.kill()
        except Exception:
            pass
    try:
        process.wait(timeout=5)
    except Exception:
        pass


def _close_process_output(process):
    """关闭子进程输出管道，避免文件描述符泄漏。"""
    try:
        if process.stdout:
            process.stdout.close()
    except Exception:
        pass


STATUS_PREFIX = 'GP_DATA_STATUS='


def parse_data_status(line):
    text = line.strip()
    if not text.startswith(STATUS_PREFIX):
        return None
    try:
        status = json.loads(text[len(STATUS_PREFIX):])
        if not isinstance(status, dict) or not isinstance(status.get('warnings', []), list) or not isinstance(status.get('critical_failures', []), list):
            raise ValueError('invalid status schema')
        return status
    except (ValueError, TypeError):
        return {'critical_failures': ['无效的数据状态协议'], 'warnings': []}


def execute_step(step_name: str, command: str, cwd: str, messages: list, timeout_seconds: int = 300) -> tuple:
    """
    执行单个 shell 步骤，实时捕获输出。
    返回 (success: bool, detail: str)

    输出由后台线程读入队列，主线程只做带超时的等待，避免子进程长时间
    不输出时 readline 阻塞、令超时判断失效。超时会杀掉整个进程组
    （shell 及其派生的所有子进程），返回 False、detail='timeout'。

    Args:
        step_name: 步骤名称
        command: 要执行的命令
        cwd: 工作目录
        messages: 消息列表（用于记录输出）
        timeout_seconds: 超时时间（秒），默认5分钟
    """
    if not command:
        messages.append(f'  跳过: {step_name}')
        return True, 'skipped'

    # 步骤命令里写的是裸 python；Web 进程的 PATH 未必指向本项目环境，
    # 这里统一换成当前解释器，避免子步骤用错 conda 环境而静默失败。
    if command.startswith('python '):
        command = f'"{sys.executable}" ' + command[len('python '):]

    try:
        env = os.environ.copy()
        env.setdefault('PYTHONUNBUFFERED', '1')
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',
            bufsize=1,
            cwd=cwd,
            env=env,
            start_new_session=True,  # 独立进程组，超时可整组终止
        )

        output_queue = queue.Queue()
        reader_done = threading.Event()

        def _reader():
            """后台逐行读取子进程输出，主线程不再直接阻塞在管道上。"""
            try:
                for line in process.stdout:
                    output_queue.put(line)
            except Exception:
                pass
            finally:
                reader_done.set()

        reader_thread = threading.Thread(target=_reader, name='step-output-reader', daemon=True)
        reader_thread.start()

        data_warnings, data_failures = [], []
        deadline = time.monotonic() + float(timeout_seconds)
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process_group(process)
                _close_process_output(process)
                messages.append(f'  ⚠️ 步骤超时({timeout_seconds}秒)，已终止进程组')
                return False, 'timeout'

            try:
                line = output_queue.get(timeout=min(0.1, remaining))
            except queue.Empty:
                if process.poll() is not None and reader_done.is_set():
                    break
                continue

            if line is None:
                break
            if line.strip():
                messages.append(f'  {line.strip()}')
                status = parse_data_status(line)
                if status is not None:
                    data_warnings.extend(str(w) for w in status.get('warnings', []))
                    data_failures.extend(str(w) for w in status.get('critical_failures', []))
                    if status.get('degraded') and not status.get('warnings'):
                        data_warnings.append('子进程报告数据降级')

        returncode = process.wait()
        _close_process_output(process)
        if data_failures:
            return False, '; '.join(data_failures)
        if returncode == 0:
            if data_warnings:
                return True, STATUS_PREFIX + json.dumps({'degraded': True, 'warnings': data_warnings}, ensure_ascii=False)
            return True, 'success'
        return False, f'returncode={returncode}'
    except Exception as e:
        return False, str(e)

OPTIONAL_STEP_MARKER = '[可选]'


def _normalize_step(step):
    """规范化步骤声明，返回 (名称, 命令, 是否关键步骤)。

    支持三种写法：
        (名称, 命令)                          —— 关键步骤
        (名称, 命令, {'critical': False})     —— 可选步骤
        名称以 [可选] 开头                     —— 可选步骤
    """
    if not isinstance(step, (tuple, list)) or len(step) < 2:
        raise ValueError(f'步骤声明格式错误: {step!r}')
    name, command = step[0], step[1]
    options = step[2] if len(step) > 2 and isinstance(step[2], dict) else {}
    optional = (not bool(options.get('critical', True))) or str(name).startswith(OPTIONAL_STEP_MARKER)
    if str(name).startswith(OPTIONAL_STEP_MARKER):
        name = name[len(OPTIONAL_STEP_MARKER):].strip()
    return name, command, not optional


def _step_timeout_seconds(step_name):
    """根据步骤类型设置不同的超时时间（秒）。"""
    if step_name.startswith('[采集]'):
        return 300  # 数据采集：5分钟
    if step_name.startswith('[计算]'):
        return 180  # 本地计算：3分钟
    if step_name.startswith('[分析]'):
        return 600  # 普通分析：10分钟
    if step_name.startswith('[摘要]'):
        return 900  # LLM摘要：15分钟
    if step_name.startswith('[决策]'):
        return 1200  # LLM决策：20分钟
    if step_name.startswith('[综合]'):
        return 1800  # AI综合分析：30分钟
    return 300  # 默认5分钟


def _execute_steps(task_id, full_stock_code, steps, label):
    """执行步骤列表的通用逻辑。

    关键步骤失败：立即停止后续步骤，任务 status='failed'，消息写明失败步骤与原因。
    可选步骤失败：继续执行，任务最终 status='completed' 但带 degraded=True 和 warnings，
    前端据此显式展示「已完成但有降级项」，不会看起来完全成功。

    返回 True 表示全部关键步骤成功（可能出现降级），False 表示关键步骤失败。
    """
    messages = []
    data_dir = os.path.join(project_root, 'data', full_stock_code)
    os.makedirs(data_dir, exist_ok=True)

    task_status[task_id] = {
        'status': 'running', 'progress': 0, 'messages': [],
        'stock_code': full_stock_code
    }
    _save_task_status()
    messages.append(label)
    total_steps = len(steps)
    messages.append(f"共 {total_steps} 个步骤，按顺序执行")

    normalized_steps = [_normalize_step(step) for step in steps]
    warnings = []

    for i, (step_name, command, critical) in enumerate(normalized_steps):
        display_name = step_name if critical else f'{OPTIONAL_STEP_MARKER} {step_name}'
        messages.append(f'【{i+1}/{total_steps}】{display_name}')
        task_status[task_id] = {
            'status': 'running',
            'progress': int((i / total_steps) * 100),
            'messages': messages.copy(),
            'stock_code': full_stock_code
        }
        _save_task_status()

        success, result = execute_step(step_name, command, project_root, messages,
                                       _step_timeout_seconds(step_name))
        if success:
            status = parse_data_status(result)
            if status:
                warnings.extend(str(w) for w in status.get('warnings', []))
            messages.append(f'  ✅ {display_name} 完成')
        elif critical:
            messages.append(f'  ❌ {display_name} 失败：{result}')
            messages.append(f'关键步骤失败，已停止后续 {total_steps - i - 1} 个步骤')
            task_status[task_id] = {
                'status': 'failed',
                'progress': int(((i + 1) / total_steps) * 100),
                'messages': messages.copy(),
                'stock_code': full_stock_code,
                'failed_step': display_name,
                'reason': result
            }
            _save_task_status()
            return False
        else:
            messages.append(f'  ⚠️ {display_name} 失败：{result}（可选步骤，继续执行）')
            warnings.append(f'{display_name}: {result}')

        task_status[task_id] = {
            'status': 'running',
            'progress': int(((i + 1) / total_steps) * 100),
            'messages': messages.copy(),
            'stock_code': full_stock_code
        }
        _save_task_status()

    if warnings:
        messages.append('========== 分析完成（降级：以下可选步骤未成功，相关证据可能缺失） ==========')
        for warning in warnings:
            messages.append(f'  - {warning}')
        task_status[task_id] = {
            'status': 'completed', 'progress': 100,
            'messages': messages, 'stock_code': full_stock_code,
            'degraded': True, 'warnings': warnings
        }
    else:
        messages.append("========== 分析完成 ==========")
        task_status[task_id] = {
            'status': 'completed', 'progress': 100,
            'messages': messages, 'stock_code': full_stock_code
        }
    _save_task_status()
    return True


# ============================================================
# 完整分析管道（/api/analyze）
# 全量数据采集 → 五维度 JSON → 两层决策 LLM
# 五维度均参与：财务 + 情绪估值 + 技术趋势 + 股东结构 + 研报观点
# 第一层：冲突检测与综合研判 → 第二层：结合持仓生成交易计划
# ============================================================
def run_analysis_task(task_id: str, stock_code: str, task_type: str):
    """完整分析：全量数据 + 五维度 JSON + 两层决策（仅支持 init）"""
    full_stock_code = stock_code + get_exchange_suffix(stock_code)

    try:
        if task_type != 'init':
            task_status[task_id] = {
                'status': 'failed', 'progress': 100,
                'messages': ['完整分析仅支持 task_type=init。每日快速查看请用 /api/quick_analyze']
            }
            return

        label = "========== 完整分析 · 五维度两层决策 =========="
        # 补充性质的数据源用第三项 {'critical': False} 标注：失败不阻断主流程，
        # 但任务最终会带 degraded=True + warnings，前端显式展示降级。
        steps = [
            # --- 数据采集 ---
            ('[采集] 低频数据', f'python stock_company_info_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 北向资金', f'python north_holdings.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 财务指标', f'python financial_indicators_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 东方财富财务', f'python em_financial_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 计算财务指标', f'python calculate_financial_indicators.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 日更数据', f'python check_data_updates.py --ticker {full_stock_code}'),
            ('[采集] 业绩预告与分红', f'python important_missing_data_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 前十大股东', f'python shareholders_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 股东户数', f'python shareholder_num_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 机构持股', f'python org_hold_collector.py --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 市场表现', f'python eastmoney_fetcher.py --type market_performance --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 行业估值', f'python eastmoney_fetcher.py --type industry_valuation --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 同行业公司', f'python eastmoney_fetcher.py --type industry_peers --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 行业成长', f'python eastmoney_fetcher.py --type industry_growth --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 杜邦分析', f'python eastmoney_fetcher.py --type dupont --ticker {full_stock_code}', {'critical': False}),
            ('[采集] 申万行业', f'python shenwan_industry_collector.py --ticker {full_stock_code}', {'critical': False}),
            # 所有采集完成后统一复核，先写完整证据状态，再生成任何维度报告。
            ('[采集] 全量证据复核', f'python check_data_updates.py --mode all --ticker {full_stock_code}'),
            # --- 技术指标 ---
            ('[计算] 技术趋势数据', f'python calculate_technical_trend_ds.py --ticker {full_stock_code}'),
            # --- 各方面详细分析报告（MD） ---
            ('[分析] 财务报表分析', f'python analyze_financial_statements.py --ticker {full_stock_code}'),
            ('[分析] 研报分析', f'python analyze_research_reports.py --ticker {full_stock_code}'),
            ('[分析] 东方财富财务分析', f'python analyze_em_financial.py --ticker {full_stock_code}'),
            ('[分析] 业绩预告与分红分析', f'python analyze_performance_forecast.py --ticker {full_stock_code}'),
            ('[分析] 股东结构分析', f'python analyze_shareholder_structure.py --ticker {full_stock_code}'),
            ('[分析] 同行对比分析', f'python analyze_peer_comparison.py --ticker {full_stock_code}'),
            ('[分析] 资金流向分析', f'python analyze_fund_flow.py --ticker {full_stock_code}'),
            ('[分析] 融资融券分析', f'python analyze_margin_data.py --ticker {full_stock_code}'),
            ('[分析] 估值分析', f'python analyze_valuation_data.py --ticker {full_stock_code}'),
            ('[分析] 技术趋势AI分析', f'python analyze_technical_trend.py --ticker {full_stock_code}'),
            # --- 五维度 JSON 摘要 ---
            ('[摘要] 财务结构化', f'python Process/financial_structured_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 情绪估值', f'python Process/sentiment_valuation_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 股东结构', f'python Process/shareholder_structure_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 研报观点', f'python Process/research_report_analyzer.py --ticker {full_stock_code}'),
            # --- 两层决策（五维度冲突检测 + 交易计划） ---
            ('[决策] 五维度两层决策', f'python Process/two_layer_decision_analyzer.py --ticker {full_stock_code}'),
            # --- AI 综合分析 ---
            ('[综合] AI综合分析', f'python stock_ai_comprehensive_analyzer.py --ticker {full_stock_code}'),
        ]

        _execute_steps(task_id, full_stock_code, steps, label)
    except Exception as e:
        task_status[task_id] = {'status': 'failed', 'progress': 100, 'messages': [f'任务执行失败：{str(e)}']}
        _save_task_status()


# ============================================================
# 快速分析管道（/api/quick_analyze）
# 仅 K 线数据 + 技术指标 → 技术趋势 AI，不做基本面
# 策略模式 → K线分析视角映射:
#   short  → trend_following (趋势跟踪)
#   medium → swing (波段交易)
#   long   → neutral (客观均衡)
# ============================================================
QUICK_STRATEGY_MAP = {
    'short': 'trend_following',
    'medium': 'swing',
    'long': 'neutral',
}

def run_quick_task(task_id: str, stock_code: str, task_type: str, strategy_mode: str = 'short'):
    """快速分析：仅 K 线 → 技术趋势 AI，仅支持每日更新"""
    mode_names = {'short': '短期交易', 'medium': '中期持仓', 'long': '长期投资'}
    mode_name = mode_names.get(strategy_mode, strategy_mode)
    kline_strategy = QUICK_STRATEGY_MAP.get(strategy_mode, 'trend_following')
    full_stock_code = stock_code + get_exchange_suffix(stock_code)

    try:
        if task_type != 'daily':
            task_status[task_id] = {
                'status': 'failed', 'progress': 100,
                'messages': ['快速分析仅支持 task_type=daily（每日K线更新+技术趋势分析）']
            }
            return

        label = f"========== 快速分析 · 每日更新（{mode_name}，K线视角: {kline_strategy}） =========="
        steps = [
            ('日更K线数据更新', f'python check_data_updates.py --mode daily --ticker {full_stock_code}'),
            ('计算技术趋势数据', f'python calculate_technical_trend_ds.py --ticker {full_stock_code}'),
            ('K线技术趋势AI分析', f'python analyze_technical_trend.py --strategy {kline_strategy} --ticker {full_stock_code}'),
        ]

        _execute_steps(task_id, full_stock_code, steps, label)
    except Exception as e:
        task_status[task_id] = {'status': 'failed', 'progress': 100, 'messages': [f'任务执行失败：{str(e)}']}
        _save_task_status()


# ============================================================
# 双队列：深度分析 / 快速分析
# ============================================================
analysis_queue = queue.Queue()   # 深度分析队列
quick_queue = queue.Queue()      # 快速分析队列

def _analysis_worker():
    """深度分析后台线程（无策略模式，固定中期权重）"""
    while True:
        task = analysis_queue.get()
        if task is None:
            break
        task_id, stock_code, task_type = task
        run_analysis_task(task_id, stock_code, task_type)
        analysis_queue.task_done()

def _quick_worker():
    """快速分析后台线程"""
    while True:
        task = quick_queue.get()
        if task is None:
            break
        task_id, stock_code, task_type, strategy_mode = task
        run_quick_task(task_id, stock_code, task_type, strategy_mode)
        quick_queue.task_done()

# 启动两个独立的后台线程
_analysis_thread = threading.Thread(target=_analysis_worker, daemon=True)
_analysis_thread.start()
_quick_thread = threading.Thread(target=_quick_worker, daemon=True)
_quick_thread.start()
