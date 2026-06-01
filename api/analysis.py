# api/analysis.py
# 完整分析 API — 全量数据采集 + 五维度 JSON + 两层决策
# 仅支持新股票初始化（init），每日快速查看请用 /api/quick_analyze
import os
import time
from flask import Blueprint, request, jsonify

from .common import (
    get_exchange_suffix,
    analysis_queue,
    task_status,
)

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/analyze', methods=['POST'])
def analyze():
    """
    完整分析 — 从零开始，全量数据采集 + 五维度 JSON + 两层决策 LLM。

    五维度均参与决策：
      财务(25%) + 情绪估值(15%) + 技术趋势(40%) + 股东结构(10%) + 研报观点(10%)
      第一层：冲突检测与综合研判
      第二层：结合持仓生成交易计划

    JSON body:
        stock_code: 6位数字股票代码（必填）
    """
    data = request.json or {}
    stock_code = data.get('stock_code', '').strip()

    if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({'success': False, 'message': '请输入6位数字的股票代码'})

    task_id = f"full_{stock_code}_{int(time.time())}"
    task_status[task_id] = {
        'status': 'pending', 'progress': 0,
        'messages': ['完整分析任务已加入队列（五维度两层决策）']
    }
    analysis_queue.put((task_id, stock_code, 'init'))

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'完整分析已启动: {stock_code}{get_exchange_suffix(stock_code)}'
    })


@analysis_bp.route('/task_status/<task_id>')
def get_task_status(task_id):
    status = task_status.get(task_id, {
        'status': 'not_found', 'progress': 0, 'messages': ['任务不存在']
    })
    return jsonify(status)


@analysis_bp.route('/reports/<stock_code>')
def get_reports(stock_code):
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    data_dir = os.path.join('data', full_stock_code)

    if not os.path.exists(data_dir):
        return jsonify({'success': False, 'message': '股票数据不存在'})

    reports = []
    for file in sorted(os.listdir(data_dir), reverse=True):
        if not file.endswith('.md'):
            continue
        file_path = os.path.join(data_dir, file)
        reports.append({
            'name': file,
            'path': os.path.join(full_stock_code, file),
            'size': os.path.getsize(file_path),
            'mtime': os.path.getmtime(file_path),
        })

    return jsonify({'success': True, 'reports': reports})


@analysis_bp.route('/report/<path:report_path>')
def get_report_content(report_path):
    file_path = os.path.join('data', report_path)
    if not os.path.exists(file_path):
        return jsonify({'success': False, 'message': '报告文件不存在'})

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({'success': True, 'content': content})
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取报告失败：{str(e)}'})


@analysis_bp.route('/latest_report/<stock_code>')
def get_latest_report(stock_code):
    """获取最新分析报告"""
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    data_dir = os.path.join('data', full_stock_code)

    if not os.path.exists(data_dir):
        return jsonify({'success': False, 'message': '股票数据不存在'})

    priority_keywords = ['final_decision', 'two_layer', 'strategy_analysis', 'comprehensive_analysis']
    best_report = None
    best_time = 0

    for file in os.listdir(data_dir):
        if not file.endswith('.md'):
            continue
        file_path = os.path.join(data_dir, file)
        mtime = os.path.getmtime(file_path)
        for kw in priority_keywords:
            if kw in file and mtime > best_time:
                best_time = mtime
                best_report = file
                break

    if not best_report:
        return jsonify({'success': False, 'message': '尚未生成分析报告'})

    try:
        with open(os.path.join(data_dir, best_report), 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'success': True,
            'report_path': best_report,
            'report_content': content,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': f'读取报告失败：{str(e)}'})
