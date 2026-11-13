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


# 报告读取的安全边界：只允许 data/ 目录内、且扩展名在白名单内的文件
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
ALLOWED_REPORT_EXTENSIONS = ('.md', '.json', '.csv', '.txt')


def _resolve_report_path(report_path):
    """校验并解析报告路径，返回可读取的绝对路径；不合法时抛 ValueError。

    约束：
        * 禁止绝对路径与 '..' 路径段；
        * realpath 解析（含符号链接）后必须位于 data/ 目录内；
        * 扩展名必须在白名单内。
    """
    if not report_path or report_path.startswith(('/', '\\')):
        raise ValueError('报告路径不能为空且不能是绝对路径')
    if '\x00' in report_path:
        raise ValueError('报告路径包含非法字符')

    normalized = report_path.replace('\\', '/')
    if any(segment == '..' for segment in normalized.split('/')):
        raise ValueError('报告路径不允许包含 ..')

    data_root = os.path.realpath(DATA_ROOT)
    candidate = os.path.realpath(os.path.join(data_root, report_path))
    if candidate != data_root and not candidate.startswith(data_root + os.sep):
        raise ValueError('报告路径超出 data 目录范围')
    if os.path.splitext(candidate)[1].lower() not in ALLOWED_REPORT_EXTENSIONS:
        raise ValueError(f"不允许读取该类型文件（仅支持 {'/'.join(ALLOWED_REPORT_EXTENSIONS)}）")
    return candidate


@analysis_bp.route('/report/<path:report_path>')
def get_report_content(report_path):
    try:
        file_path = _resolve_report_path(report_path)
    except ValueError as e:
        return jsonify({'success': False, 'message': f'非法报告路径：{e}'})

    if not os.path.isfile(file_path):
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
