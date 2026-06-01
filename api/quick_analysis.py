# api/quick_analysis.py
# 快速分析 API — 仅 K 线技术面，不做基本面分析
# 仅支持 task_type=daily（每日更新）
# strategy_mode 映射到 K 线分析视角:
#   short  → trend_following (趋势跟踪，短线信号)
#   medium → swing (波段交易，中线节奏)
#   long   → neutral (客观均衡，长线参考)
# 端点: /api/quick_analyze /api/quick_task_status /api/quick_report
import os
import time
from flask import Blueprint, request, jsonify

from .common import (
    get_exchange_suffix,
    quick_queue,
    task_status,
    QUICK_STRATEGY_MAP,
)

quick_analysis_bp = Blueprint('quick_analysis', __name__)


@quick_analysis_bp.route('/quick_analyze', methods=['POST'])
def quick_analyze():
    """
    快速分析 — 仅 K 线技术数据 + 技术趋势 AI 分析。
    不抓取基本面数据，不生成财务/股东/研报 JSON。
    仅支持每日更新（不支持新股票初始化，初始化请用 /api/analyze）。

    JSON body:
        stock_code:   6位数字股票代码（必填）
        task_type:    'daily'（仅支持 daily）
        strategy_mode: 'short' | 'medium' | 'long'（默认 'short'）
            short  → 趋势跟踪视角，关注突破/止损信号
            medium → 波段交易视角，关注支撑/阻力位
            long   → 均衡视角，多空兼顾
    """
    data = request.json or {}
    stock_code = data.get('stock_code', '').strip()
    task_type = data.get('task_type', 'daily')
    strategy_mode = data.get('strategy_mode', 'short')

    if task_type != 'daily':
        return jsonify({
            'success': False,
            'message': '快速分析仅支持 task_type=daily。新股票初始化请使用 /api/analyze (task_type=init)'
        })

    valid_modes = ['short', 'medium', 'long']
    if strategy_mode not in valid_modes:
        return jsonify({'success': False, 'message': f'无效策略模式，可选: {valid_modes}'})

    if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({'success': False, 'message': '请输入6位数字的股票代码'})

    task_id = f"quick_{stock_code}_{strategy_mode}_{int(time.time())}"
    task_status[task_id] = {
        'status': 'pending', 'progress': 0,
        'messages': ['快速分析任务已加入队列（仅K线技术面）']
    }
    quick_queue.put((task_id, stock_code, task_type, strategy_mode))

    mode_names = {'short': '短期交易', 'medium': '中期持仓', 'long': '长期投资'}
    kline_view = QUICK_STRATEGY_MAP.get(strategy_mode, 'trend_following')
    return jsonify({
        'success': True,
        'task_id': task_id,
        'strategy_mode': strategy_mode,
        'kline_perspective': kline_view,
        'message': f'快速分析已启动(K线技术面): {stock_code}{get_exchange_suffix(stock_code)} [{mode_names[strategy_mode]} → {kline_view}]'
    })


@quick_analysis_bp.route('/quick_task_status/<task_id>')
def get_quick_task_status(task_id):
    """查询快速分析任务状态"""
    status = task_status.get(task_id, {
        'status': 'not_found', 'progress': 0, 'messages': ['任务不存在']
    })
    return jsonify(status)


@quick_analysis_bp.route('/quick_report/<stock_code>')
def get_quick_report(stock_code):
    """
    获取最新技术趋势分析报告。
    快速分析只生成 K 线技术趋势报告，不生成策略/综合报告。
    """
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(project_root, 'data', full_stock_code)

    if not os.path.exists(data_dir):
        return jsonify({'success': False, 'message': '股票数据不存在'})

    # 快速分析产出的报告类型（技术趋势为主）
    priority_keywords = ['technical_trend_analysis', 'technical_trend', 'trend_analysis']
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

    # 回退：如果没找到技术趋势报告，返回最新的任意 MD 报告
    if not best_report:
        for file in os.listdir(data_dir):
            if file.endswith('.md'):
                file_path = os.path.join(data_dir, file)
                mtime = os.path.getmtime(file_path)
                if mtime > best_time:
                    best_time = mtime
                    best_report = file

    if not best_report:
        return jsonify({'success': False, 'message': '尚未生成技术趋势分析报告'})

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
