# api/trading.py
# 买卖记录管理相关的API
import os
import sys
import json
from flask import Blueprint, request, jsonify

from .common import get_exchange_suffix

# 创建蓝图
trading_bp = Blueprint('trading', __name__)

@trading_bp.route('/trading_records/<stock_code>')
def get_trading_records(stock_code):
    """获取股票的交易记录"""
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    
    try:
        from trading_records import TRADING_RECORDS
        records = TRADING_RECORDS.get(full_stock_code, [])
        return jsonify({
            'success': True,
            'records': records,
            'stock_code': full_stock_code
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取交易记录失败：{str(e)}'
        })

@trading_bp.route('/add_trading_record', methods=['POST'])
def add_trading_record():
    """添加交易记录"""
    data = request.json
    stock_code = data.get('stock_code', '').strip()
    date = data.get('date', '')
    trade_type = data.get('type', '')
    price = data.get('price', 0)
    shares = data.get('shares', 0)
    
    if not stock_code or len(stock_code) != 6 or not stock_code.isdigit():
        return jsonify({
            'success': False,
            'message': '请输入6位数字的股票代码'
        })
    
    if not date or not trade_type or price <= 0 or shares <= 0:
        return jsonify({
            'success': False,
            'message': '请填写完整的交易信息'
        })
    
    full_stock_code = stock_code + get_exchange_suffix(stock_code)
    
    try:
        # 读取trading_records.py文件内容
        trading_records_path = os.path.join(os.path.dirname(__file__), '..', 'trading_records.py')
        
        # 先导入trading_records模块
        import trading_records
        
        # 更新TRADING_RECORDS
        if full_stock_code not in trading_records.TRADING_RECORDS:
            trading_records.TRADING_RECORDS[full_stock_code] = []
        
        # 添加新记录
        new_record = {
            'date': date,
            'type': trade_type,
            'price': price,
            'shares': shares
        }
        trading_records.TRADING_RECORDS[full_stock_code].append(new_record)
        
        # 写回trading_records.py文件
        with open(trading_records_path, 'w', encoding='utf-8') as f:
            f.write('# trading_records.py\n')
            f.write('# 交易记录配置\n\n')
            f.write('TRADING_RECORDS = {\n')
            for stock, records in trading_records.TRADING_RECORDS.items():
                f.write(f"    '{stock}': [\n")
                for i, record in enumerate(records):
                    if i < len(records) - 1:
                        f.write(f"        {{'date': '{record['date']}', 'type': '{record['type']}', 'price': {record['price']}, 'shares': {record['shares']}}},\n")
                    else:
                        f.write(f"        {{'date': '{record['date']}', 'type': '{record['type']}', 'price': {record['price']}, 'shares': {record['shares']}}}\n")
                f.write('    ],\n')
            f.write('}\n')
            
            return jsonify({
                'success': True,
                'message': '交易记录添加成功',
                'stock_code': full_stock_code
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'添加交易记录失败：{str(e)}'
        })
