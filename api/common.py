# api/common.py
# API 模块共享代码：交易所映射、任务队列管理
import os
import sys
import subprocess
import time
import threading
import queue

# 添加项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

# ============================================================
# 股票代码 → 交易所后缀
# ============================================================
SSE_PREFIXES = ['600', '601', '603', '688']  # 上海证券交易所
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
task_status = {}

def execute_step(step_name: str, command: str, cwd: str, messages: list) -> tuple:
    """
    执行单个 shell 步骤，实时捕获输出。
    返回 (success: bool, detail: str)
    """
    if not command:
        messages.append(f'  跳过: {step_name}')
        return True, 'skipped'

    try:
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            cwd=cwd
        )
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                messages.append(f'  {line.strip()}')
        process.wait()
        if process.returncode == 0:
            return True, 'success'
        else:
            return False, f'returncode={process.returncode}'
    except Exception as e:
        return False, str(e)

def _execute_steps(task_id, full_stock_code, steps, label):
    """执行步骤列表的通用逻辑"""
    messages = []
    data_dir = os.path.join(project_root, 'data', full_stock_code)
    os.makedirs(data_dir, exist_ok=True)

    task_status[task_id] = {'status': 'running', 'progress': 0, 'messages': []}
    messages.append(label)
    total_steps = len(steps)
    messages.append(f"共 {total_steps} 个步骤，按顺序执行")

    for i, (step_name, command) in enumerate(steps):
        messages.append(f'【{i+1}/{total_steps}】{step_name}')
        task_status[task_id] = {
            'status': 'running',
            'progress': int((i / total_steps) * 100),
            'messages': messages.copy()
        }
        success, result = execute_step(step_name, command, project_root, messages)
        if success:
            messages.append(f'  ✅ {step_name} 完成')
        else:
            messages.append(f'  ⚠️ {step_name} 完成（警告: {result}）')
        task_status[task_id] = {
            'status': 'running',
            'progress': int(((i + 1) / total_steps) * 100),
            'messages': messages.copy()
        }

    task_status[task_id] = {
        'status': 'completed', 'progress': 100,
        'messages': messages, 'stock_code': full_stock_code
    }
    messages.append("========== 分析完成 ==========")


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
        steps = [
            # --- 数据采集 ---
            ('[采集] 低频数据', f'python stock_company_info_collector.py --ticker {full_stock_code}'),
            ('[采集] 北向资金', f'python north_holdings.py --ticker {full_stock_code}'),
            ('[采集] 财务指标', f'python financial_indicators_collector.py --ticker {full_stock_code}'),
            ('[采集] 东方财富财务', f'python em_financial_collector.py --ticker {full_stock_code}'),
            ('[采集] 计算财务指标', f'python calculate_financial_indicators.py --ticker {full_stock_code}'),
            ('[采集] 日更数据', f'python check_data_updates.py --ticker {full_stock_code}'),
            ('[采集] 业绩预告与分红', f'python important_missing_data_collector.py --ticker {full_stock_code}'),
            ('[采集] 前十大股东', f'python shareholders_collector.py --ticker {full_stock_code}'),
            ('[采集] 股东户数', f'python shareholder_num_collector.py --ticker {full_stock_code}'),
            ('[采集] 机构持股', f'python org_hold_collector.py --ticker {full_stock_code}'),
            ('[采集] 市场表现', f'python eastmoney_fetcher.py --type market_performance --ticker {full_stock_code}'),
            ('[采集] 行业估值', f'python eastmoney_fetcher.py --type industry_valuation --ticker {full_stock_code}'),
            ('[采集] 同行业公司', f'python eastmoney_fetcher.py --type industry_peers --ticker {full_stock_code}'),
            ('[采集] 行业成长', f'python eastmoney_fetcher.py --type industry_growth --ticker {full_stock_code}'),
            ('[采集] 杜邦分析', f'python eastmoney_fetcher.py --type dupont --ticker {full_stock_code}'),
            ('[采集] 申万行业', f'python shenwan_industry_collector.py --ticker {full_stock_code}'),
            # --- 技术指标 ---
            ('[计算] 技术趋势数据', f'python calculate_technical_trend_ds.py --ticker {full_stock_code}'),
            # --- 五维度 JSON 摘要 ---
            ('[摘要] 财务结构化', f'python Process/financial_structured_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 情绪估值', f'python Process/sentiment_valuation_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 股东结构', f'python Process/shareholder_structure_analyzer.py --ticker {full_stock_code}'),
            ('[摘要] 研报观点', f'python Process/research_report_analyzer.py --ticker {full_stock_code}'),
            # --- 两层决策（五维度冲突检测 + 交易计划） ---
            ('[决策] 五维度两层决策', f'python Process/two_layer_decision_analyzer.py --ticker {full_stock_code}'),
        ]

        _execute_steps(task_id, full_stock_code, steps, label)
    except Exception as e:
        task_status[task_id] = {'status': 'failed', 'progress': 100, 'messages': [f'任务执行失败：{str(e)}']}


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
