from flask import Blueprint, request, jsonify
import os
import sys

watchlist_bp = Blueprint('watchlist', __name__)

# 关注列表存储文件路径
WATCHLIST_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'watchlist.py')

def normalize_stock_code(stock_code):
    """标准化股票代码，自动添加市场后缀"""
    stock_code = stock_code.strip()
    
    # 如果已经有后缀，直接返回
    if stock_code.endswith(('.SH', '.SZ', '.BJ')):
        return stock_code
    
    # 根据股票代码前缀判断市场
    if stock_code.startswith('60') or stock_code.startswith('68'):
        return stock_code + '.SH'
    elif stock_code.startswith('00') or stock_code.startswith('30'):
        return stock_code + '.SZ'
    elif stock_code.startswith('8'):
        return stock_code + '.BJ'
    else:
        # 默认返回原代码（可能是其他格式）
        return stock_code

def load_watchlist():
    """加载关注列表"""
    if os.path.exists(WATCHLIST_FILE):
        try:
            # 导入模块获取关注列表
            if 'watchlist' in sys.modules:
                del sys.modules['watchlist']
            import watchlist
            if hasattr(watchlist, 'WATCHLIST'):
                return watchlist.WATCHLIST
        except Exception as e:
            print(f"加载关注列表失败: {e}")
    return []

def save_watchlist(watchlist_items):
    """保存关注列表到文件，每行一只股票"""
    lines = [
        '# 关注股票列表',
        '# 格式: [(\'股票代码\', \'股票名称\'), ...]',
        '',
        'WATCHLIST = ['
    ]
    
    for i, item in enumerate(watchlist_items):
        code = item[0]
        name = item[1] if item[1] else ''
        line = f"    ('{code}', '{name}')"
        if i < len(watchlist_items) - 1:
            line += ','
        lines.append(line)
    
    lines.append(']')
    
    content = '\n'.join(lines)
    with open(WATCHLIST_FILE, 'w', encoding='utf-8') as f:
        f.write(content)
    return True

@watchlist_bp.route('/watchlist/get', methods=['GET'])
def get_watchlist():
    """获取关注列表"""
    watchlist = load_watchlist()
    return jsonify({'success': True, 'data': watchlist})

@watchlist_bp.route('/watchlist/add', methods=['POST'])
def add_to_watchlist():
    """添加股票到关注列表"""
    data = request.get_json()
    stock_code = data.get('stock_code', '').strip()
    stock_name = data.get('stock_name', '').strip()
    
    if not stock_code:
        return jsonify({'success': False, 'message': '股票代码不能为空'})
    
    # 标准化股票代码
    normalized_code = normalize_stock_code(stock_code)
    
    watchlist = load_watchlist()
    
    # 检查是否已存在（使用标准化后的代码）
    for item in watchlist:
        if item[0] == normalized_code:
            return jsonify({'success': False, 'message': '该股票已在关注列表中'})
    
    # 添加到列表（使用标准化后的代码）
    watchlist.append((normalized_code, stock_name))
    save_watchlist(watchlist)
    
    return jsonify({'success': True, 'message': '添加成功', 'data': watchlist})

@watchlist_bp.route('/watchlist/remove', methods=['POST'])
def remove_from_watchlist():
    """从关注列表中删除股票"""
    data = request.get_json()
    stock_code = data.get('stock_code', '').strip()
    
    if not stock_code:
        return jsonify({'success': False, 'message': '股票代码不能为空'})
    
    # 标准化股票代码
    normalized_code = normalize_stock_code(stock_code)
    
    watchlist = load_watchlist()
    new_watchlist = [item for item in watchlist if item[0] != normalized_code]
    
    if len(new_watchlist) == len(watchlist):
        return jsonify({'success': False, 'message': '该股票不在关注列表中'})
    
    save_watchlist(new_watchlist)
    
    return jsonify({'success': True, 'message': '删除成功', 'data': new_watchlist})
