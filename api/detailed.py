# api/detailed.py
# 详细模式相关的API
import os
import sys
import subprocess
import json
from flask import Blueprint, request, jsonify

# 创建蓝图
detailed_bp = Blueprint('detailed', __name__)

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

@detailed_bp.route('/detailed_function', methods=['POST'])
def detailed_function():
    """执行详细功能"""
    data = request.json
    function_type = data.get('function_type', '')
    data_type = data.get('data_type', '')
    stock_code = data.get('stock_code', '').strip()
    
    if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({
            'success': False,
            'message': '请输入6位数字的股票代码'
        })
    
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    
    try:
        if function_type == 'fetch_data':
            # 抓取数据
            if data_type == 'periodic':
                # 抓取低频数据，依次执行五个程序
                commands = [
                    f'python stock_company_info_collector.py --ticker {full_stock_code}',
                    f'python north_holdings.py --ticker {full_stock_code}',
                    f'python financial_indicators_collector.py --ticker {full_stock_code}',
                    f'python em_financial_collector.py --ticker {full_stock_code}',
                    f'python calculate_financial_indicators.py --ticker {full_stock_code}'
                ]
                # 依次执行命令
                outputs = []
                for cmd in commands:
                    result = subprocess.run(
                        cmd, 
                        shell=True, 
                        capture_output=True, 
                        text=True
                    )
                    outputs.append(f"执行命令: {cmd}\n输出: {result.stdout}\n错误: {result.stderr}\n返回码: {result.returncode}")
                return jsonify({
                    'success': True,
                    'message': '低频数据抓取完成',
                    'output': '\n\n'.join(outputs)
                })
            else:
                # 其他数据类型的抓取
                if data_type == 'daily':
                    # 抓取日更数据
                    command = f'python check_data_updates.py --ticker {full_stock_code}'
                elif data_type == 'performance':
                    # 抓取业绩预告与分红数据
                    command = f'python analyze_performance_forecast.py --ticker {full_stock_code}'
                elif data_type == 'shareholder':
                    # 抓取股东数据，依次执行三个程序
                    commands = [
                        f'python shareholders_collector.py --ticker {full_stock_code}',
                        f'python shareholder_num_collector.py --ticker {full_stock_code}',
                        f'python org_hold_collector.py --ticker {full_stock_code}'
                    ]
                    # 依次执行命令
                    outputs = []
                    for cmd in commands:
                        result = subprocess.run(
                            cmd, 
                            shell=True, 
                            capture_output=True, 
                            text=True
                        )
                        outputs.append(f"执行命令: {cmd}\n输出: {result.stdout}\n错误: {result.stderr}\n返回码: {result.returncode}")
                    return jsonify({
                        'success': True,
                        'message': '股东数据抓取完成',
                        'output': '\n\n'.join(outputs)
                    })
                elif data_type == 'industry':
                    # 抓取同行对比数据，依次执行五个程序
                    commands = [
                        f'python fetch_stock_market_performance.py --ticker {full_stock_code}',
                        f'python fetch_industry_valuation.py --ticker {full_stock_code}',
                        f'python fetch_industry_peers.py --ticker {full_stock_code}',
                        f'python fetch_industry_growth.py --ticker {full_stock_code}',
                        f'python fetch_dupont_analysis.py --ticker {full_stock_code}',
                        f'python shenwan_industry_collector.py --ticker {full_stock_code}'
                    ]
                    # 依次执行命令
                    outputs = []
                    for cmd in commands:
                        result = subprocess.run(
                            cmd, 
                            shell=True, 
                            capture_output=True, 
                            text=True
                        )
                        outputs.append(f"执行命令: {cmd}\n输出: {result.stdout}\n错误: {result.stderr}\n返回码: {result.returncode}")
                    return jsonify({
                        'success': True,
                        'message': '同行对比数据抓取完成',
                        'output': '\n\n'.join(outputs)
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': '无效的数据类型'
                    })
                
                # 执行命令
                result = subprocess.run(
                    command, 
                    shell=True, 
                    capture_output=True, 
                    text=True
                )
                
                if result.returncode == 0:
                    return jsonify({
                        'success': True,
                        'message': '功能执行成功',
                        'output': result.stdout
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': '功能执行失败',
                        'error': result.stderr
                    })
        
        elif function_type == 'analyze_data':
            # 分析数据
            if data_type == 'periodic':
                # 分析低频数据
                command = f'python batch_analyze_periodic.py --ticker {full_stock_code}'
            elif data_type == 'daily':
                # 分析日更数据
                command = f'python batch_analyze_daily.py --ticker {full_stock_code}'
            elif data_type == 'performance':
                # 分析业绩预告与分红数据
                command = f'python analyze_performance_forecast.py --ticker {full_stock_code}'
            elif data_type == 'shareholder':
                # 分析股东数据
                command = f'python analyze_shareholder_structure.py --ticker {full_stock_code}'
            elif data_type == 'industry':
                # 分析同行对比数据
                command = f'python analyze_peer_comparison.py --ticker {full_stock_code}'
            else:
                return jsonify({
                    'success': False,
                    'message': '无效的数据类型'
                })
            
            # 执行命令
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True
            )
            
            if result.returncode == 0:
                return jsonify({
                    'success': True,
                    'message': '功能执行成功',
                    'output': result.stdout
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '功能执行失败',
                    'error': result.stderr
                })
        
        elif function_type == 'query_data':
            # 查询数据
            data_dir = os.path.join('data', full_stock_code)
            
            if not os.path.exists(data_dir):
                return jsonify({
                    'success': False,
                    'message': f'未找到股票 {full_stock_code} 的数据'
                })
            
            if data_type == 'periodic':
                # 查询低频数据文件信息
                files_info = []
                
                # 1. 公司基本信息（stock_company_info_collector.py）
                company_info_file = os.path.join(data_dir, f'{full_stock_code}_company_basic.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_company_basic.json',
                    'exists': os.path.exists(company_info_file),
                    'modified_time': os.path.getmtime(company_info_file) if os.path.exists(company_info_file) else None,
                    'content': '公司基本信息、经营范围、财务摘要等',
                    'update_frequency': '季度'
                })
                
                # 研究报告
                research_reports_file = os.path.join(data_dir, f'{full_stock_code}_research_reports.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_research_reports.csv',
                    'exists': os.path.exists(research_reports_file),
                    'modified_time': os.path.getmtime(research_reports_file) if os.path.exists(research_reports_file) else None,
                    'content': '研究报告数据',
                    'update_frequency': '季度'
                })
                
                # 财务报表-利润表
                financial_profit_file = os.path.join(data_dir, f'{full_stock_code}_financial_profit.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_financial_profit.csv',
                    'exists': os.path.exists(financial_profit_file),
                    'modified_time': os.path.getmtime(financial_profit_file) if os.path.exists(financial_profit_file) else None,
                    'content': '财务报表-利润表数据',
                    'update_frequency': '季度'
                })
                
                # 财务报表-资产负债表
                financial_balance_file = os.path.join(data_dir, f'{full_stock_code}_financial_balance.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_financial_balance.csv',
                    'exists': os.path.exists(financial_balance_file),
                    'modified_time': os.path.getmtime(financial_balance_file) if os.path.exists(financial_balance_file) else None,
                    'content': '财务报表-资产负债表数据',
                    'update_frequency': '季度'
                })
                
                # 北向资金（north_holdings.py）
                north_holdings_file = os.path.join(data_dir, f'{full_stock_code}_north_holdings.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_north_holdings.csv',
                    'exists': os.path.exists(north_holdings_file),
                    'modified_time': os.path.getmtime(north_holdings_file) if os.path.exists(north_holdings_file) else None,
                    'content': '北向资金持股数据',
                    'update_frequency': '季度'
                })
                
                # 财务指标（financial_indicators_collector.py）
                financial_indicators_file = os.path.join(data_dir, f'{full_stock_code}_financial_indicators.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_financial_indicators.json',
                    'exists': os.path.exists(financial_indicators_file),
                    'modified_time': os.path.getmtime(financial_indicators_file) if os.path.exists(financial_indicators_file) else None,
                    'content': '毛利率、净利率、资产负债率、流动比率等财务指标',
                    'update_frequency': '季度'
                })
                
                # 杜邦分析数据（em_financial_collector.py）
                dupont_file = os.path.join(data_dir, f'{full_stock_code}_dupont_data.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_dupont_data.csv',
                    'exists': os.path.exists(dupont_file),
                    'modified_time': os.path.getmtime(dupont_file) if os.path.exists(dupont_file) else None,
                    'content': '从东方财富获取的杜邦分析数据',
                    'update_frequency': '季度'
                })
                
                # 增长率数据（em_financial_collector.py）
                growth_ratio_file = os.path.join(data_dir, f'{full_stock_code}_growth_ratio_data.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_growth_ratio_data.csv',
                    'exists': os.path.exists(growth_ratio_file),
                    'modified_time': os.path.getmtime(growth_ratio_file) if os.path.exists(growth_ratio_file) else None,
                    'content': '从东方财富获取的增长率数据',
                    'update_frequency': '季度'
                })
                
                # 主要财务指标数据（em_financial_collector.py）
                main_financial_file = os.path.join(data_dir, f'{full_stock_code}_main_financial_data.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_main_financial_data.csv',
                    'exists': os.path.exists(main_financial_file),
                    'modified_time': os.path.getmtime(main_financial_file) if os.path.exists(main_financial_file) else None,
                    'content': '从东方财富获取的主要财务指标数据',
                    'update_frequency': '季度'
                })
                
                # 计算的财务指标数据（calculate_financial_indicators.py）
                calculated_indicators_file = os.path.join(data_dir, f'{full_stock_code}_financial_indicators_calculated.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_financial_indicators_calculated.json',
                    'exists': os.path.exists(calculated_indicators_file),
                    'modified_time': os.path.getmtime(calculated_indicators_file) if os.path.exists(calculated_indicators_file) else None,
                    'content': '计算的财务指标数据，包括盈利能力、偿债能力、运营能力、现金流和成长能力指标',
                    'update_frequency': '季度'
                })
                
                return jsonify({
                    'success': True,
                    'message': '查询成功',
                    'output': json.dumps(files_info, ensure_ascii=False, indent=2)
                })
            
            elif data_type == 'daily':
                # 查询日更数据文件信息
                files_info = []
                
                # 前复权数据
                qfq_file = os.path.join(data_dir, f'{full_stock_code}_qfq.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_qfq.csv',
                    'exists': os.path.exists(qfq_file),
                    'modified_time': os.path.getmtime(qfq_file) if os.path.exists(qfq_file) else None,
                    'content': '开盘价、收盘价、最高价、最低价、成交量、成交额等基础数据',
                    'update_frequency': '每日'
                })
                
                # 资金流数据
                fund_flow_file = os.path.join(data_dir, f'{full_stock_code}_fund_flow.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_fund_flow.csv',
                    'exists': os.path.exists(fund_flow_file),
                    'modified_time': os.path.getmtime(fund_flow_file) if os.path.exists(fund_flow_file) else None,
                    'content': '主力资金、超大单、大单、中单、小单的流入流出情况',
                    'update_frequency': '每日'
                })
                
                # 融资融券数据
                margin_data_file = os.path.join(data_dir, f'{full_stock_code}_margin_data.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_margin_data.csv',
                    'exists': os.path.exists(margin_data_file),
                    'modified_time': os.path.getmtime(margin_data_file) if os.path.exists(margin_data_file) else None,
                    'content': '融资余额、融券余额、融资买入额、融券卖出量等数据',
                    'update_frequency': '每日'
                })
                
                # 估值数据
                valuation_file = os.path.join(data_dir, f'{full_stock_code}_valuation.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_valuation.csv',
                    'exists': os.path.exists(valuation_file),
                    'modified_time': os.path.getmtime(valuation_file) if os.path.exists(valuation_file) else None,
                    'content': '市盈率、市净率、市销率等估值指标',
                    'update_frequency': '每日'
                })
                
                return jsonify({
                    'success': True,
                    'message': '查询成功',
                    'output': json.dumps(files_info, ensure_ascii=False, indent=2)
                })
            
            elif data_type == 'performance':
                # 查询业绩预告与分红数据文件信息
                files_info = []
                
                # 业绩预告数据
                performance_file = os.path.join(data_dir, f'{full_stock_code}_performance_forecast.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_performance_forecast.csv',
                    'exists': os.path.exists(performance_file),
                    'modified_time': os.path.getmtime(performance_file) if os.path.exists(performance_file) else None,
                    'content': '公司业绩预告数据',
                    'update_frequency': '按需'
                })
                
                # 分红数据
                ex_dividend_file = os.path.join(data_dir, f'{full_stock_code}_ex_dividend.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_ex_dividend.csv',
                    'exists': os.path.exists(ex_dividend_file),
                    'modified_time': os.path.getmtime(ex_dividend_file) if os.path.exists(ex_dividend_file) else None,
                    'content': '公司分红记录',
                    'update_frequency': '按需'
                })
                
                return jsonify({
                    'success': True,
                    'message': '查询成功',
                    'output': json.dumps(files_info, ensure_ascii=False, indent=2)
                })
            
            elif data_type == 'shareholder':
                # 查询股东数据文件信息
                files_info = []
                
                # 1. 前十大持股股东数据（shareholders_collector.py）
                historical_shareholders_file = os.path.join(data_dir, f'{full_stock_code}_historical_shareholders.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_historical_shareholders.csv',
                    'exists': os.path.exists(historical_shareholders_file),
                    'modified_time': os.path.getmtime(historical_shareholders_file) if os.path.exists(historical_shareholders_file) else None,
                    'content': '前十大持股股东数据',
                    'update_frequency': '季度'
                })
                
                # 2. 股东户数数据（shareholder_num_collector.py）
                shareholder_num_file = os.path.join(data_dir, f'{full_stock_code}_shareholder_num.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_shareholder_num.csv',
                    'exists': os.path.exists(shareholder_num_file),
                    'modified_time': os.path.getmtime(shareholder_num_file) if os.path.exists(shareholder_num_file) else None,
                    'content': '股东户数、户均持股等数据',
                    'update_frequency': '季度'
                })
                
                # 股东户数详细信息
                shareholder_num_info_file = os.path.join(data_dir, f'{full_stock_code}_shareholder_num_info.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_shareholder_num_info.csv',
                    'exists': os.path.exists(shareholder_num_info_file),
                    'modified_time': os.path.getmtime(shareholder_num_info_file) if os.path.exists(shareholder_num_info_file) else None,
                    'content': '股东户数详细信息数据',
                    'update_frequency': '季度'
                })
                
                # 3. 机构持股明细数据（org_hold_collector.py）
                institutional_holdings_file = os.path.join(data_dir, f'{full_stock_code}_institutional_holdings.csv')
                files_info.append({
                    'file_name': f'{full_stock_code}_institutional_holdings.csv',
                    'exists': os.path.exists(institutional_holdings_file),
                    'modified_time': os.path.getmtime(institutional_holdings_file) if os.path.exists(institutional_holdings_file) else None,
                    'content': '机构持股明细数据',
                    'update_frequency': '季度'
                })
                
                return jsonify({
                    'success': True,
                    'message': '查询成功',
                    'output': json.dumps(files_info, ensure_ascii=False, indent=2)
                })
            
            elif data_type == 'industry':
                # 查询同行对比数据文件信息
                files_info = []
                
                # 1. 股票历史日度市场表现数据（fetch_stock_market_performance.py）
                market_performance_file = os.path.join(data_dir, f'{full_stock_code}_market_performance.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_market_performance.json',
                    'exists': os.path.exists(market_performance_file),
                    'modified_time': os.path.getmtime(market_performance_file) if os.path.exists(market_performance_file) else None,
                    'content': '股票历史日度市场表现数据',
                    'update_frequency': '按需'
                })
                
                # 2. 股票行业估值排名数据（fetch_industry_valuation.py）
                industry_valuation_file = os.path.join(data_dir, f'{full_stock_code}_industry_valuation.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_industry_valuation.json',
                    'exists': os.path.exists(industry_valuation_file),
                    'modified_time': os.path.getmtime(industry_valuation_file) if os.path.exists(industry_valuation_file) else None,
                    'content': '股票行业估值排名数据',
                    'update_frequency': '按需'
                })
                
                # 3. 股票同行业公司数据（fetch_industry_peers.py）
                industry_peers_file = os.path.join(data_dir, f'{full_stock_code}_industry_peers.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_industry_peers.json',
                    'exists': os.path.exists(industry_peers_file),
                    'modified_time': os.path.getmtime(industry_peers_file) if os.path.exists(industry_peers_file) else None,
                    'content': '股票同行业公司数据',
                    'update_frequency': '按需'
                })
                
                # 4. 股票行业成长能力排名数据（fetch_industry_growth.py）
                industry_growth_file = os.path.join(data_dir, f'{full_stock_code}_industry_growth.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_industry_growth.json',
                    'exists': os.path.exists(industry_growth_file),
                    'modified_time': os.path.getmtime(industry_growth_file) if os.path.exists(industry_growth_file) else None,
                    'content': '股票行业成长能力排名数据',
                    'update_frequency': '按需'
                })
                
                # 5. 股票杜邦分析行业排名数据（fetch_dupont_analysis.py）
                dupont_analysis_file = os.path.join(data_dir, f'{full_stock_code}_dupont_analysis.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_dupont_analysis.json',
                    'exists': os.path.exists(dupont_analysis_file),
                    'modified_time': os.path.getmtime(dupont_analysis_file) if os.path.exists(dupont_analysis_file) else None,
                    'content': '股票杜邦分析行业排名数据',
                    'update_frequency': '按需'
                })
                
                # 6. 股票申万行业数据（shenwan_industry_collector.py）
                shenwan_industry_file = os.path.join(data_dir, f'{full_stock_code}_industry_info.json')
                files_info.append({
                    'file_name': f'{full_stock_code}_industry_info.json',
                    'exists': os.path.exists(shenwan_industry_file),
                    'modified_time': os.path.getmtime(shenwan_industry_file) if os.path.exists(shenwan_industry_file) else None,
                    'content': '股票申万行业数据',
                    'update_frequency': '按需'
                })
                
                return jsonify({
                    'success': True,
                    'message': '查询成功',
                    'output': json.dumps(files_info, ensure_ascii=False, indent=2)
                })
            
            else:
                return jsonify({
                    'success': False,
                    'message': '无效的数据类型'
                })
        
        else:
            return jsonify({
                'success': False,
                'message': '无效的功能类型'
            })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'执行功能失败：{str(e)}'
        })
