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

# 创建蓝图
backtest_bp = Blueprint('backtest', __name__)

# 任务队列和状态管理
backtest_task_queue = queue.Queue()
backtest_task_status = {}

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

def run_backtest_task(task_id, skip_data_update=False, use_simplified=False):
    """运行回测任务
    
    Args:
        task_id: 任务ID
        skip_data_update: 是否跳过数据更新步骤，默认为False（执行完整流程）
        use_simplified: 是否使用简化版策略，默认为False（使用原始版）
    """
    try:
        backtest_task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'messages': []
        }
        
        messages = []
        total_stocks = 0
        
        # 获取股票列表 - 自动检测data目录中的所有股票
        ticker_list = []
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
            
            if ticker_list:
                progress_step = 25 / total_stocks  # 数据更新占25%进度
                messages.append(f'检测到 {total_stocks} 只股票')
                
                for i, ticker in enumerate(ticker_list):
                    messages.append(f'更新股票 {ticker} ({i+1}/{total_stocks})')
                    backtest_task_status[task_id] = {
                        'status': 'running',
                        'progress': i * progress_step,
                        'messages': messages.copy()
                    }
                    
                    data_update_cmd = f'python check_data_updates.py --ticker {ticker}'
                    try:
                        process = subprocess.Popen(
                            data_update_cmd,
                            shell=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            bufsize=1
                        )
                        
                        for line in iter(process.stdout.readline, ''):
                            if line.strip():
                                messages.append(f'数据更新[{ticker}]: {line.strip()[:100]}')
                                backtest_task_status[task_id] = {
                                    'status': 'running',
                                    'progress': (i + 0.5) * progress_step,
                                    'messages': messages.copy()
                                }
                        
                        process.wait()
                        if process.returncode == 0:
                            messages.append(f'完成：股票 {ticker} 数据更新')
                        else:
                            messages.append(f'警告：股票 {ticker} 数据更新返回非零状态')
                    except Exception as e:
                        messages.append(f'股票 {ticker} 数据更新跳过: {str(e)}')
            else:
                messages.append('警告：未在data目录中检测到任何股票')
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
        backtest_cmd = f'python backtest_all_stocks.py {mode_flag}'
        try:
            process = subprocess.Popen(
                backtest_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                bufsize=1
            )
            
            progress = backtest_start_progress
            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    messages.append(f'回测: {line.strip()[:150]}')
                    # 更新进度
                    if '分析' in line:
                        progress = min(95, progress + 2)
                    elif '保存' in line:
                        progress = min(95, progress + 1)
                    backtest_task_status[task_id] = {
                        'status': 'running',
                        'progress': progress,
                        'messages': messages.copy()
                    }
            
            process.wait()
            if process.returncode == 0:
                messages.append('完成：策略回测')
            else:
                messages.append(f'错误：回测失败，返回码: {process.returncode}')
        except Exception as e:
            messages.append(f'回测失败: {str(e)}')
        
        backtest_task_status[task_id] = {
            'status': 'completed',
            'progress': 100,
            'messages': messages,
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

@backtest_bp.route('/get_stock_list')
def get_stock_list():
    """获取所有股票列表"""
    stocks = []
    if os.path.exists(DATA_DIR):
        for item in os.listdir(DATA_DIR):
            item_path = os.path.join(DATA_DIR, item)
            if os.path.isdir(item_path):
                # 检查是否有回测图表（排除简化版）
                png_files = []
                for f in os.listdir(item_path):
                    # 只选择标准回测图，排除简化版和其他类型
                    if f.endswith('.png') and 'backtest' in f and 'simplified' not in f:
                        png_files.append(f)
                
                if png_files:
                    # 按日期排序，取最新的
                    png_files.sort(reverse=True)
                    stocks.append({
                        'ticker': item,
                        'chart_path': f"{item}/{png_files[0]}"
                    })
    
    # 按股票代码升序排列
    stocks.sort(key=lambda x: x['ticker'])
    
    return jsonify({
        'success': True,
        'stocks': stocks
    })

@backtest_bp.route('/get_report')
def get_report():
    """获取最新的监控报告"""
    timestamp = time.strftime('%Y%m%d')
    report_path = os.path.join(DATA_DIR, f"monitor_report_{timestamp}.md")
    
    if not os.path.exists(report_path):
        # 如果今天的报告不存在，找最近的
        report_files = []
        for f in os.listdir(DATA_DIR):
            if f.startswith('monitor_report_') and f.endswith('.md'):
                report_files.append(f)
        
        if not report_files:
            return jsonify({
                'success': False,
                'message': '未找到监控报告'
            })
        
        report_files.sort(reverse=True)
        report_path = os.path.join(DATA_DIR, report_files[0])
    
    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    return jsonify({
        'success': True,
        'content': content,
        'filename': os.path.basename(report_path)
    })

@backtest_bp.route('/get_chart/<path:chart_path>')
def get_chart(chart_path):
    """获取回测图表"""
    full_path = os.path.join(DATA_DIR, chart_path)
    
    if not os.path.exists(full_path):
        return jsonify({
            'success': False,
            'message': '图表文件不存在'
        })
    
    return send_file(full_path, mimetype='image/png')

@backtest_bp.route('/get_backtest_results')
def get_backtest_results():
    """获取回测结果CSV"""
    timestamp = time.strftime('%Y%m%d')
    results_path = os.path.join(DATA_DIR, f"backtest_results_{timestamp}.csv")
    
    if not os.path.exists(results_path):
        # 如果今天的结果不存在，找最近的
        result_files = []
        for f in os.listdir(DATA_DIR):
            if f.startswith('backtest_results_') and f.endswith('.csv'):
                result_files.append(f)
        
        if not result_files:
            return jsonify({
                'success': False,
                'message': '未找到回测结果'
            })
        
        result_files.sort(reverse=True)
        results_path = os.path.join(DATA_DIR, result_files[0])
    
    df = pd.read_csv(results_path)
    return jsonify({
        'success': True,
        'data': df.to_dict('records')
    })