# api/report_viewer.py
# 报告查看器相关的API
import os
import sys
import json
from flask import Blueprint, request, jsonify

# 创建蓝图
report_viewer_bp = Blueprint('report_viewer', __name__)

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

@report_viewer_bp.route('/stocks')
def get_stocks():
    """获取股票列表"""
    data_dir = 'data'
    stocks = []
    
    if os.path.exists(data_dir):
        for stock_dir in os.listdir(data_dir):
            # 检查是否是股票目录（包含.SH或.SZ后缀）
            if '.SH' in stock_dir or '.SZ' in stock_dir:
                # 提取股票代码和名称
                stock_code = stock_dir
                stock_name = stock_code  # 暂时使用股票代码作为名称
                
                # 尝试从公司信息文件中获取股票名称
                company_info_file = os.path.join(data_dir, stock_dir, f'{stock_dir}_company_basic.json')
                if os.path.exists(company_info_file):
                    try:
                        with open(company_info_file, 'r', encoding='utf-8') as f:
                            company_info = json.load(f)
                            # 尝试从 basic_info 中获取公司简称或股票简称
                            if 'basic_info' in company_info:
                                if '公司简称' in company_info['basic_info']:
                                    stock_name = company_info['basic_info']['公司简称']
                                elif '股票简称' in company_info['basic_info']:
                                    stock_name = company_info['basic_info']['股票简称']
                    except:
                        pass
                
                stocks.append({
                    'code': stock_code,
                    'name': stock_name
                })
    
    return jsonify({
        'success': True,
        'stocks': stocks
    })

@report_viewer_bp.route('/stock_reports/<stock_code>')
def get_stock_reports(stock_code):
    """获取股票的报告列表，只显示每种类型的最新报告"""
    data_dir = os.path.join('data', stock_code)
    
    if not os.path.exists(data_dir):
        return jsonify({
            'success': False,
            'message': '股票数据不存在'
        })
    
    # 按报告类型分组，只保留最新的报告
    report_groups = {}
    for file in os.listdir(data_dir):
        if file.endswith('.md') and 'analysis' in file:
            # 提取报告类型（如 valuation_analysis, shareholder_structure_analysis）
            # 文件名格式可能是：{股票代码}_{报告类型}_{日期}.md 或 {股票代码}_{报告类型}_{日期}_{时间}.md
            parts = file.split('_')
            if len(parts) >= 3:
                # 找到包含 'analysis' 的部分，作为报告类型的结束
                analysis_index = -1
                for i, part in enumerate(parts):
                    if 'analysis' in part:
                        analysis_index = i
                        break
                
                if analysis_index != -1:
                    # 提取报告类型（从第一个下划线后到包含 'analysis' 的部分）
                    report_type = '_'.join(parts[1:analysis_index+1])
                    
                    report_info = {
                        'name': file,
                        'path': os.path.join(stock_code, file),
                        'size': os.path.getsize(os.path.join(data_dir, file))
                    }
                    
                    # 如果该类型还没有报告，或者当前报告比已存储的更新
                    if report_type not in report_groups or file > report_groups[report_type]['name']:
                        report_groups[report_type] = report_info
    
    # 将分组后的报告转换为列表
    reports = list(report_groups.values())
    
    # 按文件名排序，最新的在前面
    reports.sort(key=lambda x: x['name'], reverse=True)
    
    return jsonify({
        'success': True,
        'reports': reports
    })
