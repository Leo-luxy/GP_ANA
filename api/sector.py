# api/sector.py
# 板块分析 API
# 遵循 api/backtest.py 的自包含 Blueprint 模式
# 提供：数据采集触发、分析触发、状态轮询、报告获取

import os
import sys
import subprocess
import json
import time
from datetime import datetime
from flask import Blueprint, request, jsonify
import threading
import queue

# 创建蓝图
sector_bp = Blueprint('sector', __name__)

# 任务队列和状态管理
sector_task_queue = queue.Queue()
sector_task_status = {}

# 项目路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = os.path.join(project_root, 'data')

SECTOR_DATA_DIR = os.path.join(DATA_DIR, 'sector')
SECTOR_REPORT_DIR = os.path.join(SECTOR_DATA_DIR, 'reports')

# 内存缓存：避免同一进程内反复请求 akshare
_board_list_cache = {}


def _fetch_board_list_on_demand(sector_type):
    """按需获取板块列表，优先读缓存/CSV，不存在则自动从 akshare 拉取

    Args:
        sector_type: 'industry' | 'concept'

    Returns:
        pd.DataFrame | None: 板块列表 DataFrame，失败返回 None
    """
    import pandas as pd

    # 1. 内存缓存
    if sector_type in _board_list_cache:
        return _board_list_cache[sector_type]

    # 2. 磁盘缓存
    type_dir = os.path.join(SECTOR_DATA_DIR, sector_type)
    board_list_path = os.path.join(type_dir, '_board_list.csv')
    if os.path.exists(board_list_path):
        try:
            df = pd.read_csv(board_list_path)
            _board_list_cache[sector_type] = df
            return df
        except Exception:
            pass

    # 3. 从 akshare 实时拉取
    try:
        # 禁用系统代理（避免本地代理不可用导致请求失败）
        for _key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
                     'all_proxy', 'ALL_PROXY'):
            os.environ.pop(_key, None)
        try:
            import urllib.request
            urllib.request.getproxies = lambda: {}
        except Exception:
            pass

        import akshare as ak

        os.makedirs(type_dir, exist_ok=True)

        if sector_type == 'industry':
            df = ak.stock_board_industry_name_em()
        elif sector_type == 'concept':
            df = ak.stock_board_concept_name_em()
        else:
            return None

        if df is not None and not df.empty:
            df.to_csv(board_list_path, index=False, encoding='utf-8-sig')
            _board_list_cache[sector_type] = df
            return df

    except Exception:
        pass  # 网络不可用时静默失败，后续逻辑会 fallback 到硬编码映射

    return None


# 常用板块代码 → (名称, 标准指数代码) 硬编码映射
_FALLBACK_BOARD_INFO = {
    'BK0477': ('黄金',       'sh000819'),
    'BK0478': ('有色金属',   'sh000819'),
    'BK0479': ('煤炭',       'sz399990'),
    'BK0480': ('钢铁',       'sh000823'),
    'BK0481': ('电力',       'sz399990'),
    'BK0482': ('银行',       'sz399986'),
    'BK0483': ('证券',       'sz399993'),
    'BK0484': ('保险',       'sz399994'),
    'BK0485': ('房地产',     'sz399420'),
    'BK0486': ('汽车',       'sh000827'),
    'BK0487': ('医药',       'sz399808'),
    'BK0488': ('白酒',       'sz399997'),
    'BK0489': ('半导体',     'sz399809'),
    'BK0490': ('新能源',     'sz399809'),
}

# 行业名称 → 标准指数代码
_SECTOR_NAME_TO_INDEX = {
    '有色金属': 'sh000819', '科创芯片': 'sh000685',
    '钢铁': 'sh000823', '机械设备': 'sh000827', '轻工制造': 'sh000847',
    '煤炭': 'sz399990', '银行': 'sz399986', '证券': 'sz399993',
    '保险': 'sz399994', '白酒': 'sz399997', '医疗': 'sz399989',
    '医药': 'sz399808', '电子': 'sz399809', '半导体': 'sz399809',
    '芯片': 'sz399809', '军工': 'sz399967', '计算机': 'sz399998',
    '家电': 'sz399996', '基建': 'sz399995', '食品饮料': 'sz399807',
    '传媒': 'sz399810', '物流': 'sz399813', '农业': 'sz399814',
    '房地产': 'sz399420', '金融': 'sz399419', '信息技术': 'sz399418',
    '消费': 'sz399416', '制造业': 'sz399415',
    '上证指数': 'sh000001', '深证成指': 'sz399001', '创业板指': 'sz399006',
    '科创50': 'sh000688', '沪深300': 'sh000300',
    '上证50': 'sh000016', '中证500': 'sh000905', '中证1000': 'sh000852',
}


def _resolve_board_name(sector_type, sector_code):
    """从板块列表中查找板块名称（优先查 board_list，失败则用硬编码兜底）

    Args:
        sector_type: 'industry' | 'concept'
        sector_code: 板块代码

    Returns:
        str | None: 板块名称，未找到返回 None
    """
    import pandas as pd

    # 1. 尝试从 board_list 查找
    board_df = _fetch_board_list_on_demand(sector_type)
    if board_df is not None:
        try:
            code_col = '板块代码' if '板块代码' in board_df.columns else board_df.columns[0]
            name_col = '板块名称' if '板块名称' in board_df.columns else board_df.columns[1]
            matched = board_df[board_df[code_col].astype(str).str.strip() == sector_code]
            if len(matched) > 0:
                return str(matched.iloc[0][name_col]).strip()
        except Exception:
            pass

    # 2. 硬编码映射兜底（API 不可用时）
    if sector_code in _FALLBACK_BOARD_INFO:
        return _FALLBACK_BOARD_INFO[sector_code][0]

    # 3. 如果是标准指数代码，尝试从映射表反查名称
    for name, idx_code in _SECTOR_NAME_TO_INDEX.items():
        if idx_code == sector_code:
            return name

    return None


def run_sector_task(task_id, task_type, params):
    """后台执行板块任务

    Args:
        task_id: 任务ID
        task_type: 'collect' | 'analyze_ranking' | 'analyze_single' | 'analyze_broad'
        params: 任务参数
    """
    try:
        messages = []
        sector_task_status[task_id] = {
            'status': 'running', 'progress': 0, 'messages': messages.copy()
        }

        # ---- 数据采集任务 ----
        if task_type == 'collect':
            collect_type = params.get('collect_type', 'all')
            messages.append(f'[1/2] 开始采集板块数据 (类型: {collect_type})...')
            sector_task_status[task_id] = {
                'status': 'running', 'progress': 10,
                'messages': messages.copy()
            }

            cmd = f'python sector_data_collector.py --type {collect_type}'
            if collect_type == 'industry':
                cmd += ' --top 30'

            process = subprocess.Popen(
                cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                cwd=project_root,
            )

            progress = 10
            for line in iter(process.stdout.readline, ''):
                if line.strip():
                    msg = line.strip()
                    messages.append(msg)
                    if progress < 90:
                        progress = min(90, progress + 3)
                    sector_task_status[task_id] = {
                        'status': 'running', 'progress': progress,
                        'messages': messages.copy()
                    }

            process.wait()
            if process.returncode == 0:
                messages.append('[2/2] 数据采集完成')
                sector_task_status[task_id] = {
                    'status': 'completed', 'progress': 100,
                    'messages': messages.copy(),
                    'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
                }
            else:
                sector_task_status[task_id] = {
                    'status': 'failed', 'progress': 100,
                    'messages': messages + [f'采集失败，返回码: {process.returncode}'],
                }
            return

        # ---- 分析任务 ----
        analysis_type_map = {
            'analyze_single': 'single',
            'analyze_broad': 'broad',
        }
        analysis_mode = analysis_type_map.get(task_type, 'single')

        sector_code = params.get('sector_code', '')
        sector_type = params.get('sector_type', 'industry')

        # 分析前始终重新采集最新数据，确保数据时效性
        data_dir = os.path.join(SECTOR_DATA_DIR, sector_type, sector_code)
        daily_file = os.path.join(data_dir, f'{sector_code}_daily.csv')

        messages.append(f'[数据准备] 正在获取板块 {sector_code} 最新数据...')
        sector_task_status[task_id] = {
            'status': 'running', 'progress': 5,
            'messages': messages.copy()
        }

        collect_cmd = f'python sector_data_collector.py --type {sector_type} --code {sector_code}'
        board_name = _resolve_board_name(sector_type, sector_code) or ''
        if board_name:
            collect_cmd += f' --name "{board_name}"'

        collect_process = subprocess.Popen(
            collect_cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            cwd=project_root,
        )

        collect_progress = 5
        for line in iter(collect_process.stdout.readline, ''):
            if line.strip():
                msg = line.strip()
                messages.append(msg)
                if collect_progress < 40:
                    collect_progress = min(40, collect_progress + 3)
                sector_task_status[task_id] = {
                    'status': 'running', 'progress': collect_progress,
                    'messages': messages.copy()
                }

        collect_process.wait()
        if collect_process.returncode != 0:
            sector_task_status[task_id] = {
                'status': 'failed', 'progress': 100,
                'messages': messages + [f'数据采集失败，返回码: {collect_process.returncode}'],
            }
            return

        if not os.path.exists(daily_file):
            sector_task_status[task_id] = {
                'status': 'failed', 'progress': 100,
                'messages': messages + [f'数据采集后仍未找到数据文件: {daily_file}，请确认板块代码是否正确'],
            }
            return
        messages.append('[数据准备] 最新数据获取成功，开始分析...')

        # ---- 大盘全景分析：先采集所有大盘指数最新数据 ----
        if task_type == 'analyze_broad':
            messages.append('[数据准备] 正在获取所有大盘指数最新数据...')
            sector_task_status[task_id] = {
                'status': 'running', 'progress': 42,
                'messages': messages.copy()
            }

            broad_collect_cmd = 'python sector_data_collector.py --type broad_index'
            broad_process = subprocess.Popen(
                broad_collect_cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1,
                cwd=project_root,
            )
            for line in iter(broad_process.stdout.readline, ''):
                if line.strip():
                    messages.append(line.strip())
                    sector_task_status[task_id] = {
                        'status': 'running', 'progress': 42,
                        'messages': messages.copy()
                    }
            broad_process.wait()
            if broad_process.returncode != 0:
                sector_task_status[task_id] = {
                    'status': 'failed', 'progress': 100,
                    'messages': messages + [f'大盘指数数据采集失败，返回码: {broad_process.returncode}'],
                }
                return
            messages.append('[数据准备] 大盘指数数据获取成功，开始分析...')

        messages.append(f'[分析] 开始板块 AI 分析 (代码: {sector_code})...')
        sector_task_status[task_id] = {
            'status': 'running', 'progress': 45,
            'messages': messages.copy()
        }

        cmd_parts = [f'python analyze_sector.py --mode {analysis_mode}']
        if sector_code:
            cmd_parts.append(f' --sector {sector_code}')
        cmd_parts.append(f' --type {sector_type}')
        cmd = ' '.join(cmd_parts)

        process = subprocess.Popen(
            cmd, shell=True,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
            cwd=project_root,
        )

        report_path = None
        progress = 45
        for line in iter(process.stdout.readline, ''):
            if line.strip():
                msg = line.strip()
                messages.append(msg)
                # 检测报告保存路径
                if '报告已保存' in msg:
                    report_path = msg.split(':')[-1].strip()
                if progress < 90:
                    progress = min(90, progress + 3)
                sector_task_status[task_id] = {
                    'status': 'running', 'progress': progress,
                    'messages': messages.copy()
                }

        process.wait()

        if process.returncode == 0:
            # 查找最新的报告文件
            if not report_path:
                # 从输出中查找或搜索 reports 目录（递归）
                os.makedirs(SECTOR_REPORT_DIR, exist_ok=True)
                all_md = []
                for root, dirs, files in os.walk(SECTOR_REPORT_DIR):
                    for f in files:
                        if f.endswith('.md'):
                            all_md.append(os.path.join(root, f))
                if all_md:
                    report_path = max(all_md, key=os.path.getmtime)

            sector_task_status[task_id] = {
                'status': 'completed', 'progress': 100,
                'messages': messages.copy(),
                'report_path': report_path,
                'timestamp': datetime.now().strftime('%Y%m%d_%H%M%S'),
            }
        else:
            sector_task_status[task_id] = {
                'status': 'failed', 'progress': 100,
                'messages': messages + [f'分析失败，返回码: {process.returncode}'],
            }

    except Exception as e:
        sector_task_status[task_id] = {
            'status': 'failed', 'progress': 100,
            'messages': [f'任务执行异常：{str(e)}'],
        }


def sector_worker():
    """板块分析后台工作线程"""
    while True:
        task = sector_task_queue.get()
        if task is None:
            break
        task_id, task_type, params = task
        run_sector_task(task_id, task_type, params)
        sector_task_queue.task_done()


# 启动工作线程
sector_worker_thread = threading.Thread(target=sector_worker, daemon=True)
sector_worker_thread.start()


# ==================== API 路由 ====================

@sector_bp.route('/sector_collect', methods=['POST'])
def sector_collect():
    """触发板块数据采集

    POST JSON:
        collect_type: 'broad_index' | 'industry' | 'all'
    """
    data = request.get_json() or {}
    collect_type = data.get('collect_type', 'all')

    task_id = f"sector_collect_{int(time.time())}"
    sector_task_status[task_id] = {
        'status': 'pending', 'progress': 0,
        'messages': [f'数据采集任务已加入队列 (类型: {collect_type})'],
    }
    sector_task_queue.put((task_id, 'collect', {'collect_type': collect_type}))

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'数据采集任务已启动 ({collect_type})',
    })


@sector_bp.route('/sector_analyze', methods=['POST'])
def sector_analyze():
    """触发板块分析（默认单板块深度分析，调用本地 AI）

    POST JSON:
        sector_code: str (板块代码，如 BK0477 / sh000001 / HSI)
        sector_type: 'broad_index' | 'industry' | 'hk_index'
    """
    data = request.get_json() or {}
    sector_code = data.get('sector_code', '')
    sector_type = data.get('sector_type', 'industry')

    # 验证
    if not sector_code:
        return jsonify({'success': False, 'message': '请提供板块代码 sector_code'})

    task_id = f"sector_analysis_{int(time.time())}"
    sector_task_status[task_id] = {
        'status': 'pending', 'progress': 0,
        'messages': [f'板块分析任务已加入队列 (代码: {sector_code})'],
    }
    sector_task_queue.put((task_id, 'analyze_single', {
        'sector_code': sector_code,
        'sector_type': sector_type,
    }))

    return jsonify({
        'success': True,
        'task_id': task_id,
        'message': f'板块分析任务已启动 ({sector_code})',
    })


@sector_bp.route('/sector_task_status/<task_id>')
def sector_task_status_route(task_id):
    """获取任务状态（用于轮询）

    Returns JSON:
        status: 'pending' | 'running' | 'completed' | 'failed' | 'not_found'
        progress: 0-100
        messages: [str, ...]
        report_path: str (完成时)
    """
    status = sector_task_status.get(task_id, {
        'status': 'not_found',
        'progress': 0,
        'messages': ['任务不存在或已过期'],
    })
    return jsonify(status)


@sector_bp.route('/sector_list', methods=['GET'])
def list_sectors():
    """获取可分析的板块列表

    Query params:
        type: 'broad_index' | 'industry' | 'concept' | 'all' (默认: all)
    """
    sector_type = request.args.get('type', 'all')

    sectors = []
    type_dirs = []
    if sector_type in ('broad_index', 'all'):
        type_dirs.append(('broad_index', '大盘指数'))
    if sector_type in ('hk_index', 'all'):
        type_dirs.append(('hk_index', '港股指数'))
    if sector_type in ('industry', 'all'):
        type_dirs.append(('industry', '行业板块'))
    if sector_type in ('concept', 'all'):
        type_dirs.append(('concept', '概念板块'))

    for stype, stype_cn in type_dirs:
        type_dir = os.path.join(SECTOR_DATA_DIR, stype)
        if not os.path.exists(type_dir):
            continue

        # 收集已有日线数据的板块
        codes_with_data = set()
        for code in sorted(os.listdir(type_dir)):
            code_path = os.path.join(type_dir, code)
            if not os.path.isdir(code_path):
                continue
            meta_file = os.path.join(code_path, f'{code}_meta.json')
            daily_file = os.path.join(code_path, f'{code}_daily.csv')
            if not os.path.exists(daily_file):
                continue
            codes_with_data.add(code)
            meta = {}
            if os.path.exists(meta_file):
                try:
                    with open(meta_file, 'r', encoding='utf-8') as f:
                        meta = json.load(f)
                except Exception:
                    pass
            sectors.append({
                'code': code,
                'name': meta.get('name', code),
                'short_name': meta.get('short_name', ''),
                'type': stype,
                'type_cn': stype_cn,
                'last_updated': meta.get('last_updated', ''),
                'data_rows': meta.get('data_rows', 0),
                'data_end': meta.get('data_end', ''),
                'has_data': True,
            })

        # 对于 industry/concept 类型，按需拉取板块列表（首次自动从 akshare 获取）
        if stype in ('industry', 'concept'):
            board_df = _fetch_board_list_on_demand(stype)
            if board_df is not None:
                try:
                    import pandas as pd
                    code_col = '板块代码' if '板块代码' in board_df.columns else board_df.columns[0]
                    name_col = '板块名称' if '板块名称' in board_df.columns else board_df.columns[1]
                    for _, row in board_df.iterrows():
                        code = str(row[code_col]).strip()
                        if code in codes_with_data:
                            continue  # 已有日线数据的跳过
                        name = str(row[name_col]).strip() if pd.notna(row[name_col]) else code
                        sectors.append({
                            'code': code,
                            'name': name,
                            'short_name': name,
                            'type': stype,
                            'type_cn': stype_cn,
                            'last_updated': '',
                            'data_rows': 0,
                            'data_end': '',
                            'has_data': False,
                        })
                except Exception:
                    pass  # 读取板块列表失败时静默跳过

    # 按名称排序
    sectors.sort(key=lambda x: x['name'])
    return jsonify({'success': True, 'sectors': sectors})


@sector_bp.route('/sector_report/<task_id>')
def get_sector_report(task_id):
    """获取已完成任务的报告内容

    Args:
        task_id: 任务ID
    """
    task_info = sector_task_status.get(task_id, {})
    if task_info.get('status') != 'completed':
        return jsonify({
            'success': False,
            'message': '任务尚未完成或不存在',
        })

    report_path = task_info.get('report_path', '')
    if report_path and os.path.exists(report_path):
        with open(report_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return jsonify({
            'success': True,
            'content': content,
            'filename': os.path.basename(report_path),
        })

    # 备用：从 reports 目录递归查找最新报告
    if os.path.exists(SECTOR_REPORT_DIR):
        all_md = []
        for root, dirs, files in os.walk(SECTOR_REPORT_DIR):
            for f in files:
                if f.endswith('.md'):
                    all_md.append(os.path.join(root, f))
        if all_md:
            latest = max(all_md, key=os.path.getmtime)
            with open(latest, 'r', encoding='utf-8') as f:
                content = f.read()
            return jsonify({
                'success': True,
                'content': content,
                'filename': os.path.basename(latest),
            })

    return jsonify({
        'success': False,
        'message': '未找到报告文件',
    })


@sector_bp.route('/sector_reports', methods=['GET'])
def list_sector_reports():
    """列出所有历史板块分析报告（递归扫描，按类别→板块→报告组织）"""
    os.makedirs(SECTOR_REPORT_DIR, exist_ok=True)
    reports = []
    for root, dirs, files in os.walk(SECTOR_REPORT_DIR):
        for f in files:
            if f.endswith('.md'):
                fpath = os.path.join(root, f)
                rel_path = os.path.relpath(fpath, SECTOR_REPORT_DIR)
                # 解析路径: e.g. "broad_index/sh000001/sector_single_xxx.md"
                parts = rel_path.replace('\\', '/').split('/')
                category = parts[0] if len(parts) > 1 else ''
                sector = parts[1] if len(parts) > 2 else ''
                reports.append({
                    'name': rel_path,
                    'category': category,
                    'sector': sector,
                    'filename': os.path.basename(f),
                    'size': os.path.getsize(fpath),
                    'mtime': datetime.fromtimestamp(
                        os.path.getmtime(fpath)
                    ).strftime('%Y-%m-%d %H:%M'),
                })
    # 按时间降序
    reports.sort(key=lambda x: x['mtime'], reverse=True)
    return jsonify({'success': True, 'reports': reports})


@sector_bp.route('/sector_report_content/<path:report_name>')
def get_sector_report_content(report_name):
    """按相对路径获取报告内容（路径格式: category/sector/filename.md）"""
    # 安全检查：防止路径遍历，只允许在 SECTOR_REPORT_DIR 内
    report_path = os.path.normpath(os.path.join(SECTOR_REPORT_DIR, report_name))
    # 确保解析后的路径仍在 SECTOR_REPORT_DIR 下
    if not report_path.startswith(os.path.normpath(SECTOR_REPORT_DIR)):
        return jsonify({
            'success': False,
            'message': '非法路径',
        })

    if not os.path.exists(report_path):
        return jsonify({
            'success': False,
            'message': '报告文件不存在',
        })

    with open(report_path, 'r', encoding='utf-8') as f:
        content = f.read()

    return jsonify({
        'success': True,
        'content': content,
        'filename': os.path.basename(report_name),
    })
