from flask import Blueprint, request, jsonify
import os
import sys
import subprocess
import threading
import time
import csv

stock_selection_bp = Blueprint('stock_selection', __name__)

selection_tasks = {}
selection_results = {}

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
        
        return_code = process.wait()
        if return_code == 0:
            messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 完成")
        else:
            messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 失败，返回码: {return_code}")
        
        selection_tasks[task_id]['messages'] = messages.copy()
        return return_code == 0
    except Exception as e:
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {description} 异常: {str(e)}")
        selection_tasks[task_id]['messages'] = messages.copy()
        return False

def run_selection(task_id, preliminary, detailed):
    # 当前文件位于 api 目录，需要获取项目根目录，然后定位到 stocks_filter
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    base_path = os.path.join(project_root, 'stocks_filter')
    messages = []
    
    try:
        selection_tasks[task_id] = {
            'status': 'running',
            'progress': 0,
            'messages': messages
        }
        
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 开始市场选股任务 ==========")
        selection_tasks[task_id]['messages'] = messages.copy()
        
        if preliminary:
            run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step1_daily.py')],
                base_path,
                "执行 step1_daily.py - 获取全市场日线行情"
            )
            
            run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step2_daily_basic.py')],
                base_path,
                "执行 step2_daily_basic.py - 获取基础指标并合并"
            )
            
            run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'step3_filter.py')],
                base_path,
                "执行 step3_filter.py - 执行初步筛选"
            )
        
        if detailed:
            run_command_with_output(task_id,
                [sys.executable, os.path.join(base_path, 'batch_backtest_filter.py')],
                base_path,
                "执行 batch_backtest_filter.py - 批量回测筛选"
            )
        
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 读取市场选股结果 ==========")
        
        result_file = None
        if detailed:
            result_file = os.path.join(base_path, 'final_holdings.csv')
        elif preliminary:
            result_file = os.path.join(base_path, 'stocks_daily_filtered.csv')
        
        if result_file and os.path.exists(result_file):
            with open(result_file, 'r', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f)
                selection_results[task_id] = list(reader)
            messages.append(f"成功读取 {len(selection_results[task_id])} 条记录")
        else:
            selection_results[task_id] = []
            messages.append(f"未找到结果文件: {result_file}")
        
        messages.append(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] ========== 市场选股任务完成 ==========")
        
        selection_tasks[task_id]['status'] = 'completed'
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
    # 始终从磁盘直接读取（最可靠，不受进程生命周期影响）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    base_path = os.path.join(project_root, 'stocks_filter')

    # 读取最终持仓结果
    for filename in ['final_holdings.csv', 'stocks_daily_filtered.csv']:
        result_file = os.path.join(base_path, filename)
        if os.path.exists(result_file):
            try:
                with open(result_file, 'r', encoding='utf-8-sig') as f:
                    reader = csv.DictReader(f)
                    data = list(reader)
                if data:
                    return jsonify({'success': True, 'data': data, 'source': filename})
            except Exception:
                continue

    return jsonify({'success': False, 'message': '未找到选股结果，请先运行选股任务'})
