# api/analysis.py
# 股票分析相关的API
import os
import sys
import subprocess
import json
import time
from flask import Blueprint, request, jsonify
import threading
import queue

# 创建蓝图
analysis_bp = Blueprint('analysis', __name__)

# 任务队列和状态管理
task_queue = queue.Queue()
task_status = {}

# 股票代码交易所映射
SSE_PREFIXES = ['600', '601', '603', '688']  # 上海证券交易所
SZSE_PREFIXES = ['000', '001', '002', '300']  # 深圳证券交易所

def get_exchange_suffix(stock_code):
    """根据股票代码获取交易所后缀"""
    prefix = stock_code[:3]
    if prefix in SSE_PREFIXES:
        return '.SH'
    elif prefix in SZSE_PREFIXES:
        return '.SZ'
    else:
        return '.SZ'  # 默认返回深圳

def run_task(task_id, stock_code, task_type):
    """运行任务"""
    try:
        task_status[task_id] = {
            'status': 'running',
            'progress': 0,
            'messages': []
        }
        
        full_stock_code = stock_code + get_exchange_suffix(stock_code)
        messages = []
        
        if task_type == 'init':
            # 新股票初始化流程
            steps = [
                # 详细模式中所有数据类型的抓取程序
                ('低频数据抓取', f'python stock_company_info_collector.py --ticker {full_stock_code}'),
                ('北向资金数据抓取', f'python north_holdings.py --ticker {full_stock_code}'),
                ('财务指标数据抓取', f'python financial_indicators_collector.py --ticker {full_stock_code}'),
                ('东方财富财务数据抓取', f'python em_financial_collector.py --ticker {full_stock_code}'),
                ('计算财务指标', f'python calculate_financial_indicators.py --ticker {full_stock_code}'),
                ('日更数据抓取', f'python check_data_updates.py --ticker {full_stock_code}'),
                ('业绩预告与分红数据抓取', f'python analyze_performance_forecast.py --ticker {full_stock_code}'),
                ('股东数据抓取-前十大股东', f'python shareholders_collector.py --ticker {full_stock_code}'),
                ('股东数据抓取-股东户数', f'python shareholder_num_collector.py --ticker {full_stock_code}'),
                ('股东数据抓取-机构持股', f'python org_hold_collector.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-市场表现', f'python fetch_stock_market_performance.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-行业估值', f'python fetch_industry_valuation.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-同行业公司', f'python fetch_industry_peers.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-行业成长', f'python fetch_industry_growth.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-杜邦分析', f'python fetch_dupont_analysis.py --ticker {full_stock_code}'),
                ('申万行业数据抓取', f'python shenwan_industry_collector.py --ticker {full_stock_code}'),
                # 按照指定顺序执行分析程序
                ('低频数据分析', f'python batch_analyze_periodic.py --ticker {full_stock_code}'),
                ('业绩预告与分红数据分析', f'python analyze_performance_forecast.py --ticker {full_stock_code}'),
                ('股东数据分析', f'python analyze_shareholder_structure.py --ticker {full_stock_code}'),
                ('同行对比分析', f'python analyze_peer_comparison.py --ticker {full_stock_code}'),
                ('日更数据分析', f'python batch_analyze_daily.py --ticker {full_stock_code}'),
                ('综合分析', f'python stock_ai_comprehensive_analyzer.py --ticker {full_stock_code}')
            ]
        elif task_type == 'daily':
            # 每日更新流程
            steps = [
                # 详细模式中日更数据类型的抓取程序
                ('日更数据抓取', f'python check_data_updates.py --ticker {full_stock_code}'),
                # 按照指定顺序执行分析程序
                ('股东数据分析', f'python analyze_shareholder_structure.py --ticker {full_stock_code}'),
                ('资金流分析', f'python analyze_fund_flow.py --ticker {full_stock_code}'),
                ('融资融券分析', f'python analyze_margin_data.py --ticker {full_stock_code}'),
                ('估值数据分析', f'python analyze_valuation_data.py --ticker {full_stock_code}'),
                ('技术趋势分析', f'python analyze_technical_trend_ds.py --ticker {full_stock_code}'),
                ('综合分析', f'python stock_ai_comprehensive_analyzer.py --ticker {full_stock_code}')
            ]
        elif task_type == 'periodic':
            # 定期更新流程
            steps = [
                # 详细模式中除日更数据外的所有抓取程序
                ('低频数据抓取', f'python stock_company_info_collector.py --ticker {full_stock_code}'),
                ('北向资金数据抓取', f'python north_holdings.py --ticker {full_stock_code}'),
                ('财务指标数据抓取', f'python financial_indicators_collector.py --ticker {full_stock_code}'),
                ('东方财富财务数据抓取', f'python em_financial_collector.py --ticker {full_stock_code}'),
                ('计算财务指标', f'python calculate_financial_indicators.py --ticker {full_stock_code}'),
                ('业绩预告与分红数据抓取', f'python analyze_performance_forecast.py --ticker {full_stock_code}'),
                ('股东数据抓取-前十大股东', f'python shareholders_collector.py --ticker {full_stock_code}'),
                ('股东数据抓取-股东户数', f'python shareholder_num_collector.py --ticker {full_stock_code}'),
                ('股东数据抓取-机构持股', f'python org_hold_collector.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-市场表现', f'python fetch_stock_market_performance.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-行业估值', f'python fetch_industry_valuation.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-同行业公司', f'python fetch_industry_peers.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-行业成长', f'python fetch_industry_growth.py --ticker {full_stock_code}'),
                ('同行对比数据抓取-杜邦分析', f'python fetch_dupont_analysis.py --ticker {full_stock_code}'),
                ('申万行业数据抓取', f'python shenwan_industry_collector.py --ticker {full_stock_code}'),
                # 按照指定顺序执行分析程序
                ('低频数据分析', f'python batch_analyze_periodic.py --ticker {full_stock_code}'),
                ('业绩预告与分红数据分析', f'python analyze_performance_forecast.py --ticker {full_stock_code}'),
                ('同行对比分析', f'python analyze_peer_comparison.py --ticker {full_stock_code}')
            ]
        else:
            task_status[task_id] = {
                'status': 'failed',
                'progress': 100,
                'messages': ['无效的任务类型']
            }
            return
        
        total_steps = len(steps)
        for i, (step_name, command) in enumerate(steps):
            messages.append(f'开始：{step_name}')
            task_status[task_id] = {
                'status': 'running',
                'progress': int((i / total_steps) * 100),
                'messages': messages.copy()
            }
            
            # 执行命令（实时获取输出）
            try:
                process = subprocess.Popen(
                    command, 
                    shell=True, 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.STDOUT, 
                    text=True,
                    bufsize=1  # 行缓冲
                )
                
                # 实时读取输出
                for line in iter(process.stdout.readline, ''):
                    if line.strip():
                        messages.append(f'{step_name}: {line.strip()}')
                        # 每次获取到新输出都更新任务状态
                        task_status[task_id] = {
                            'status': 'running',
                            'progress': int((i / total_steps) * 100),
                            'messages': messages.copy()
                        }
                
                # 等待进程结束
                process.wait()
                
                if process.returncode == 0:
                    messages.append(f'完成：{step_name}')
                else:
                    error_msg = f'错误：{step_name} - 命令执行失败'
                    messages.append(error_msg)
            except Exception as e:
                error_msg = f'异常：{step_name} - {str(e)}'
                messages.append(error_msg)
        
        task_status[task_id] = {
            'status': 'completed',
            'progress': 100,
            'messages': messages,
            'stock_code': full_stock_code
        }
    except Exception as e:
        task_status[task_id] = {
            'status': 'failed',
            'progress': 100,
            'messages': [f'任务执行失败：{str(e)}']
        }

def worker():
    """任务工作线程"""
    while True:
        task = task_queue.get()
        if task is None:
            break
        task_id, stock_code, task_type = task
        run_task(task_id, stock_code, task_type)
        task_queue.task_done()

# 启动工作线程
worker_thread = threading.Thread(target=worker, daemon=True)
worker_thread.start()

@analysis_bp.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    stock_code = data.get('stock_code', '').strip()
    task_type = data.get('task_type', 'daily')
    
    if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({
            'success': False,
            'message': '请输入6位数字的股票代码'
        })
    
    # 生成任务ID
    task_id = f"{stock_code}_{int(time.time())}"
    
    # 将任务加入队列
    task_queue.put((task_id, stock_code, task_type))
    
    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'任务已开始，股票代码：{stock_code}{get_exchange_suffix(stock_code)}'
    })

@analysis_bp.route('/task_status/<task_id>')
def get_task_status(task_id):
    status = task_status.get(task_id, {
        'status': 'not_found',
        'progress': 0,
        'messages': ['任务不存在']
    })
    return jsonify(status)

@analysis_bp.route('/reports/<stock_code>')
def get_reports(stock_code):
    """获取股票的分析报告列表"""
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    data_dir = os.path.join('data', full_stock_code)
    
    if not os.path.exists(data_dir):
        return jsonify({
            'success': False,
            'message': '股票数据不存在'
        })
    
    # 按报告类型分组
    reports_by_type = {}
    for file in os.listdir(data_dir):
        if file.endswith('.md') and 'analysis' in file:
            # 提取报告类型（假设文件名格式为：{stock_code}_{report_type}_analysis_{date}.md）
            # 或者其他格式，根据实际情况调整
            parts = file.split('_')
            # 找到包含'analysis'的部分，其前面的部分即为报告类型
            report_type = ''
            for i, part in enumerate(parts):
                if part == 'analysis':
                    if i > 0:
                        report_type = '_'.join(parts[1:i])
                    break
            if not report_type:
                # 如果无法提取类型，使用默认类型
                report_type = 'unknown'
            
            report_info = {
                'name': file,
                'path': os.path.join(full_stock_code, file),
                'size': os.path.getsize(os.path.join(data_dir, file))
            }
            
            if report_type not in reports_by_type:
                reports_by_type[report_type] = []
            reports_by_type[report_type].append(report_info)
    
    # 对每种类型的报告按文件名排序，取最新的一个
    latest_reports = []
    for report_type, type_reports in reports_by_type.items():
        if type_reports:
            # 按文件名排序，最新的在前面
            type_reports.sort(key=lambda x: x['name'], reverse=True)
            # 添加最新的报告
            latest_reports.append(type_reports[0])
    
    # 最后按文件名排序，确保整体顺序合理
    latest_reports.sort(key=lambda x: x['name'], reverse=True)
    
    return jsonify({
        'success': True,
        'reports': latest_reports
    })

@analysis_bp.route('/report/<path:report_path>')
def get_report_content(report_path):
    """获取报告内容"""
    try:
        # 构建完整的文件路径
        file_path = os.path.join('data', report_path)
        
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'message': '报告文件不存在'
            })
        
        # 读取报告内容
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        return jsonify({
            'success': True,
            'content': content
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'读取报告失败：{str(e)}'
        })
