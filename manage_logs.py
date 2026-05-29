
# manage_logs.py
# 功能：交互式变更日志管理工具
# 提供添加、查看、搜索变更日志的功能

import os
import sys
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'log')

def get_today_date():
    """获取今天的日期，格式YYYY-MM-DD"""
    return datetime.now().strftime('%Y-%m-%d')

def get_log_file_path(date=None):
    """获取日志文件路径"""
    if date is None:
        date = get_today_date()
    return os.path.join(LOG_DIR, f'{date}_changes.log')

def create_log_directory():
    """创建log目录（如果不存在）"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
        print(f'已创建log目录: {LOG_DIR}')

def list_all_logs():
    """列出所有日志文件"""
    if not os.path.exists(LOG_DIR):
        print('log目录不存在')
        return
    
    files = [f for f in os.listdir(LOG_DIR) if f.endswith('_changes.log')]
    if not files:
        print('没有找到变更日志文件')
        return
    
    print(f'\n找到 {len(files)} 个变更日志文件：\n')
    for i, f in enumerate(sorted(files), 1):
        file_path = os.path.join(LOG_DIR, f)
        file_size = os.path.getsize(file_path)
        print(f'{i}. {f} ({file_size} 字节)')

def view_log(date=None):
    """查看指定日期的日志"""
    if date is None:
        date = get_today_date()
    
    log_file = get_log_file_path(date)
    if not os.path.exists(log_file):
        print(f'日志文件不存在: {log_file}')
        return
    
    print(f'\n{"="*60}')
    print(f'{date} 变更日志')
    print(f'{"="*60}\n')
    
    with open(log_file, 'r', encoding='utf-8') as f:
        print(f.read())

def add_log_interactive():
    """交互式添加日志"""
    create_log_directory()
    
    print('\n请输入变更内容（输入空行结束）：')
    lines = []
    while True:
        line = input('> ')
        if not line:
            break
        lines.append(line)
    
    if not lines:
        print('未输入任何内容，取消添加')
        return
    
    change_content = '\n'.join(lines)
    add_change_log(change_content)

def add_change_log(change_content):
    """添加变更日志"""
    create_log_directory()
    
    today = get_today_date()
    log_file = get_log_file_path(today)
    
    current_time = datetime.now().strftime('%H:%M:%S')
    
    # 检查文件是否存在
    file_exists = os.path.exists(log_file)
    
    with open(log_file, 'a', encoding='utf-8') as f:
        if not file_exists:
            # 新文件，写入标题
            f.write(f'# {today} 变更日志\n\n')
        else:
            # 已有文件，添加空行
            f.write('\n')
        
        # 写入变更内容
        f.write(f'## {current_time} 变更\n\n')
        f.write(f'{change_content}\n')
    
    print(f'\n变更日志已添加到: {log_file}')
    return log_file

def search_logs(keyword):
    """在所有日志中搜索关键词"""
    if not os.path.exists(LOG_DIR):
        print('log目录不存在')
        return
    
    files = [f for f in os.listdir(LOG_DIR) if f.endswith('_changes.log')]
    if not files:
        print('没有找到变更日志文件')
        return
    
    print(f'\n在 {len(files)} 个日志文件中搜索 "{keyword}"：\n')
    
    found_count = 0
    for f in sorted(files):
        file_path = os.path.join(LOG_DIR, f)
        with open(file_path, 'r', encoding='utf-8') as log_file:
            content = log_file.read()
            if keyword.lower() in content.lower():
                found_count += 1
                print(f'✓ 在 {f} 中找到匹配')
    
    if found_count == 0:
        print(f'未找到包含 "{keyword}" 的日志')
    else:
        print(f'\n共找到 {found_count} 个包含 "{keyword}" 的日志文件')

def show_menu():
    """显示主菜单"""
    print('\n' + '='*60)
    print('变更日志管理工具')
    print('='*60)
    print('1. 查看今天的日志')
    print('2. 查看指定日期的日志')
    print('3. 列出所有日志文件')
    print('4. 添加变更日志（单行）')
    print('5. 添加变更日志（多行）')
    print('6. 搜索日志')
    print('0. 退出')
    print('='*60)

def main():
    while True:
        show_menu()
        choice = input('\n请选择操作 (0-6): ').strip()
        
        if choice == '0':
            print('再见！')
            break
        elif choice == '1':
            view_log(get_today_date())
        elif choice == '2':
            date = input('请输入日期 (YYYY-MM-DD): ').strip()
            if date:
                view_log(date)
        elif choice == '3':
            list_all_logs()
        elif choice == '4':
            content = input('请输入变更内容: ').strip()
            if content:
                add_change_log(content)
        elif choice == '5':
            add_log_interactive()
        elif choice == '6':
            keyword = input('请输入搜索关键词: ').strip()
            if keyword:
                search_logs(keyword)
        else:
            print('无效的选择，请重新输入')
        
        input('\n按回车键继续...')

if __name__ == '__main__':
    main()
