
# -*- coding: utf-8 -*-
"""
股票分析报告查看器
用于查看本地股票的分析报告
"""

import os
import json
from flask import Flask, render_template_string, request, jsonify

app = Flask(__name__)

# 数据目录
DATA_DIR = 'data'

# 生成HTML模板
index_html = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票分析报告查看器</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        .container {
            max-width: 1000px;
            margin-top: 50px;
        }
        .stock-item {
            margin-bottom: 10px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .stock-item:hover {
            background-color: #f8f9fa;
        }
        .report-item {
            margin-bottom: 10px;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        .report-item:hover {
            background-color: #f8f9fa;
        }
        .report-content {
            margin-top: 20px;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            background-color: #f8f9fa;
            min-height: 400px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1 class="text-center">股票分析报告查看器</h1>
        
        <!-- 股票列表 -->
        <div class="mt-4" id="stock-list">
            <h3>股票列表</h3>
            <div id="stocks-container" class="border rounded p-3" style="max-height: 1000px; overflow-y: auto;">
                <!-- 股票列表将通过JavaScript动态生成 -->
            </div>
        </div>
        
        <!-- 报告列表 -->
        <div class="mt-4" id="report-list" style="display: none;">
            <h3>分析报告</h3>
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 id="current-stock-name"></h4>
                <button class="btn btn-secondary" onclick="showStockList()">返回股票列表</button>
            </div>
            <div id="reports-container" class="border rounded p-3" style="max-height: 400px; overflow-y: auto;">
                <!-- 报告列表将通过JavaScript动态生成 -->
            </div>
        </div>
        
        <!-- 报告内容 -->
        <div class="mt-4" id="report-content" style="display: none;">
            <h3>报告内容</h3>
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 id="current-report-name"></h4>
                <button class="btn btn-secondary" onclick="showReportList()">返回报告列表</button>
            </div>
            <div id="content-container" class="report-content">
                <!-- 报告内容将通过JavaScript动态生成 -->
            </div>
        </div>
    </div>
    
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        // 加载股票列表
        function loadStocks() {
            fetch('/api/stocks')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        let stocksHtml = '';
                        if (data.stocks.length === 0) {
                            stocksHtml = '<div class="text-muted text-center">暂无股票数据</div>';
                        } else {
                            data.stocks.forEach(stock => {
                                stocksHtml += `
                                    <div class="stock-item" onclick="loadReports('${stock.code}', '${stock.name}')">
                                        <div class="font-weight-bold">${stock.code}</div>
                                        <div class="text-sm text-muted">${stock.name}</div>
                                    </div>
                                `;
                            });
                        }
                        
                        document.getElementById('stocks-container').innerHTML = stocksHtml;
                    } else {
                        document.getElementById('stocks-container').innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                    }
                })
                .catch(error => {
                    document.getElementById('stocks-container').innerHTML = `<div class="alert alert-danger">加载失败：${error.message}</div>`;
                });
        }
        
        // 加载股票的报告列表
        function loadReports(stockCode, stockName) {
            document.getElementById('current-stock-name').textContent = `${stockCode} - ${stockName}`;
            document.getElementById('stock-list').style.display = 'none';
            document.getElementById('report-list').style.display = 'block';
            document.getElementById('report-content').style.display = 'none';
            
            document.getElementById('reports-container').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="sr-only">加载中...</span></div></div>';
            
            fetch(`/api/reports/${stockCode}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        let reportsHtml = '';
                        if (data.reports.length === 0) {
                            reportsHtml = '<div class="text-muted text-center">暂无分析报告</div>';
                        } else {
                            data.reports.forEach(report => {
                                reportsHtml += `
                                    <div class="report-item" onclick="viewReport('${report.path}')">
                                        <div class="font-weight-bold">${report.name}</div>
                                        <div class="text-sm text-muted">${(report.size / 1024).toFixed(2)} KB</div>
                                    </div>
                                `;
                            });
                        }
                        document.getElementById('reports-container').innerHTML = reportsHtml;
                    } else {
                        document.getElementById('reports-container').innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                    }
                })
                .catch(error => {
                    document.getElementById('reports-container').innerHTML = `<div class="alert alert-danger">加载失败：${error.message}</div>`;
                });
        }
        
        // 查看报告内容
        function viewReport(reportPath) {
            document.getElementById('current-report-name').textContent = reportPath.split('/').pop();
            document.getElementById('report-list').style.display = 'none';
            document.getElementById('report-content').style.display = 'block';
            
            document.getElementById('content-container').innerHTML = '<div class="text-center"><div class="spinner-border" role="status"><span class="sr-only">加载中...</span></div></div>';
            
            fetch(`/api/report/${reportPath}`)
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // 使用marked.js渲染Markdown内容
                        const markdownContent = data.content;
                        const htmlContent = marked.parse(markdownContent);
                        document.getElementById('content-container').innerHTML = htmlContent;
                    } else {
                        document.getElementById('content-container').innerHTML = `<div class="alert alert-danger">${data.message}</div>`;
                    }
                })
                .catch(error => {
                    document.getElementById('content-container').innerHTML = `<div class="alert alert-danger">加载失败：${error.message}</div>`;
                });
        }
        
        // 返回股票列表
        function showStockList() {
            document.getElementById('stock-list').style.display = 'block';
            document.getElementById('report-list').style.display = 'none';
            document.getElementById('report-content').style.display = 'none';
        }
        
        // 返回报告列表
        function showReportList() {
            document.getElementById('report-list').style.display = 'block';
            document.getElementById('report-content').style.display = 'none';
        }
        
        // 页面加载时加载股票列表
        window.onload = loadStocks;
    </script>
</body>
</html>
'''

# 辅助函数：获取交易所后缀
def get_exchange_suffix(stock_code):
    """根据股票代码获取交易所后缀"""
    # 6开头的是上海证券交易所
    if stock_code.startswith('6'):
        return '.SH'
    # 0或3开头的是深圳证券交易所
    elif stock_code.startswith('0') or stock_code.startswith('3'):
        return '.SZ'
    else:
        return ''

# API路由：获取所有股票
@app.route('/api/stocks')
def get_stocks():
    """获取所有已存在的股票"""
    try:
        stocks = []
        
        if os.path.exists(DATA_DIR):
            for stock_dir in os.listdir(DATA_DIR):
                stock_path = os.path.join(DATA_DIR, stock_dir)
                if os.path.isdir(stock_path):
                    # 提取股票代码和名称
                    stock_code = stock_dir
                    company_info_file = os.path.join(stock_path, f'{stock_dir}_company_basic.json')
                    company_name = stock_dir
                    
                    # 尝试从company_basic.json中读取公司名称
                    if os.path.exists(company_info_file):
                        try:
                            with open(company_info_file, 'r', encoding='utf-8') as f:
                                company_info = json.load(f)
                                if 'basic_info' in company_info:
                                    if '公司简称' in company_info['basic_info']:
                                        company_name = company_info['basic_info']['公司简称']
                                    elif '公司全称' in company_info['basic_info']:
                                        company_name = company_info['basic_info']['公司全称']
                        except Exception:
                            pass
                    
                    stocks.append({
                        'code': stock_code,
                        'name': company_name
                    })
        
        return jsonify({
            'success': True,
            'stocks': stocks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取股票列表失败：{str(e)}'
        })

# API路由：获取股票的报告列表
@app.route('/api/reports/<stock_code>')
def get_reports(stock_code):
    """获取特定股票的分析报告（每种报告只显示最新的一份）"""
    # 检查stock_code是否已经包含交易所后缀
    if '.' in stock_code:
        full_stock_code = stock_code
    else:
        full_stock_code = stock_code + get_exchange_suffix(stock_code)
    
    data_dir = os.path.join(DATA_DIR, full_stock_code)
    
    if not os.path.exists(data_dir):
        return jsonify({
            'success': False,
            'message': '股票数据不存在'
        })
    
    try:
        # 收集所有分析报告
        reports = []
        # 递归查找所有子目录中的MD文件
        for root, dirs, files in os.walk(data_dir):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    relative_path = os.path.relpath(file_path, DATA_DIR)
                    file_size = os.path.getsize(file_path)
                    
                    # 提取报告类型和日期
                    parts = file.split('_')
                    if len(parts) > 2:
                        # 假设报告名称格式为：{stock_code}_{report_type}_{date}.md
                        report_type = '_'.join(parts[1:-1]) if len(parts) > 3 else parts[1]
                        date_str = parts[-1].split('.')[0]
                    else:
                        report_type = file.split('.')[0]
                        date_str = ''
                    
                    reports.append({
                        'name': file,
                        'path': relative_path.replace('\\', '/'),
                        'size': file_size,
                        'type': report_type,
                        'date': date_str
                    })
        
        # 按报告类型分组，只保留最新的一份
        report_groups = {}
        for report in reports:
            report_type = report['type']
            if report_type not in report_groups or report['date'] > report_groups[report_type]['date']:
                report_groups[report_type] = report
        
        # 转换为列表并按文件名排序
        latest_reports = sorted([{
            'name': report['name'],
            'path': report['path'],
            'size': report['size']
        } for report in report_groups.values()], key=lambda x: x['name'])
        
        return jsonify({
            'success': True,
            'reports': latest_reports
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取报告列表失败：{str(e)}'
        })

# API路由：获取报告内容
@app.route('/api/report/<path:report_path>')
def get_report(report_path):
    """获取报告内容"""
    try:
        # 构建完整的文件路径
        file_path = os.path.join(DATA_DIR, report_path)
        
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

# 主页路由
@app.route('/')
def index():
    return render_template_string(index_html)

if __name__ == '__main__':
    # 启动Flask应用
    app.run(host='0.0.0.0', port=8081, debug=True)
