# sector_data_collector.py
# 板块数据采集器
# 功能：统一采集大盘指数、行业板块、概念板块的历史行情数据
# 数据来源：akshare (东方财富接口)
# 存储结构：data/sector/{broad_index,industry,concept}/{code}/

import os
import sys

# ===== 绕过不可用的系统代理 =====
# macOS 系统代理设置为 127.0.0.1:6789，但代理服务未运行时会阻断所有 outbound 请求。
# 必须在使用 requests/akshare 之前，强制禁用代理。
def _disable_system_proxy():
    """移除系统代理配置，避免因本地代理不可用导致请求失败"""
    # 清除代理相关环境变量
    for key in ('http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
                'all_proxy', 'ALL_PROXY'):
        os.environ.pop(key, None)
    # 通知 urllib 不使用系统代理
    try:
        import urllib.request
        urllib.request.getproxies = lambda: {}
    except Exception:
        pass

_disable_system_proxy()

import json
import time
import argparse
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    import akshare as ak
except ImportError:
    print("错误：请先安装 akshare: pip install akshare")
    sys.exit(1)

try:
    from config import DATA_DIR
except ImportError:
    DATA_DIR = "./data"

# 板块数据根目录
SECTOR_DATA_DIR = os.path.join(DATA_DIR, 'sector')

# 预定义的大盘指数列表
BROAD_INDEX_LIST = [
    {'code': 'sh000001', 'name': '上证指数', 'short_name': '上证'},
    {'code': 'sz399001', 'name': '深证成指', 'short_name': '深证'},
    {'code': 'sz399006', 'name': '创业板指', 'short_name': '创业板'},
    {'code': 'sh000688', 'name': '科创50', 'short_name': '科创50'},
    {'code': 'sh000300', 'name': '沪深300', 'short_name': '沪深300'},
    {'code': 'sh000016', 'name': '上证50', 'short_name': '上证50'},
]

# 预定义的港股核心指数列表
HK_INDEX_LIST = [
    {'code': 'HSI', 'name': '恒生指数', 'short_name': '恒指'},
    {'code': 'HSCEI', 'name': '国企指数', 'short_name': '国企'},
    {'code': 'HSTECH', 'name': '恒生科技指数', 'short_name': '恒科'},
    {'code': 'HSCCI', 'name': '红筹指数', 'short_name': '红筹'},
    {'code': 'HSC', 'name': '恒生工商业指数', 'short_name': '工商业'},
]

# 预定义的中证指数列表（存储到 broad_index 目录，统一为 A 股大盘指数）
CSI_INDEX_LIST = [
    {'code': 'sh000905', 'name': '中证500', 'short_name': '中证500'},
    {'code': 'sh000852', 'name': '中证1000', 'short_name': '中证1000'},
]


class SectorDataCollector:
    """板块数据采集器"""

    def __init__(self):
        self.data_root = SECTOR_DATA_DIR
        os.makedirs(self.data_root, exist_ok=True)

    # ==================== 工具方法 ====================

    def _save_csv(self, df, file_path, encoding='utf-8-sig'):
        """安全保存CSV文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.to_csv(file_path, index=False, encoding=encoding)
        print(f"  ✓ 已保存: {file_path} ({len(df)} 条)")

    def _save_json(self, data, file_path):
        """安全保存JSON文件"""
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _get_sector_dir(self, sector_type, code):
        """获取板块数据目录"""
        dir_path = os.path.join(self.data_root, sector_type, code)
        os.makedirs(dir_path, exist_ok=True)
        return dir_path

    # ==================== 大盘指数采集 ====================

    def collect_broad_index_list(self):
        """获取预定义的大盘指数列表"""
        print(f"\n{'='*60}")
        print(f"大盘指数列表 (共 {len(BROAD_INDEX_LIST)} 只)")
        print(f"{'='*60}")
        for idx in BROAD_INDEX_LIST:
            print(f"  {idx['code']} - {idx['name']} ({idx['short_name']})")
        return BROAD_INDEX_LIST

    def collect_broad_index_daily(self, symbol, name, short_name):
        """采集单只大盘指数的历史日线数据

        数据源优先级: 新浪财经 > 东方财富

        Args:
            symbol: 指数代码 (如 sh000001)
            name: 指数名称 (如 上证指数)
            short_name: 简称

        Returns:
            bool: 是否成功
        """
        print(f"\n--- 采集 {name} ({symbol}) ---")
        try:
            from datetime import datetime as dt
            end_date = dt.now().strftime('%Y%m%d')
            start_date = '19900101'
            source = 'unknown'
            df = None

            # ---- 数据源1：新浪财经 (主力) ----
            index_symbol = symbol  # sh000001 等格式，Sina 可直接使用
            print(f"  指数代码: {index_symbol}")
            df = self._try_sina_index(index_symbol, start_date, end_date)
            if df is not None:
                source = 'sina'

            # ---- 数据源2：东方财富 (兜底) ----
            if df is None:
                print(f"  新浪不可用，尝试东方财富...")
                for em_start in ['20050101', '20100101', '20150101']:
                    try:
                        df = ak.stock_zh_index_daily_em(symbol=symbol, start_date=em_start, end_date=end_date)
                        if df is not None and not df.empty:
                            # 标准化东方财富列名
                            col_map = {
                                'date': 'date', 'open': 'open', 'high': 'high',
                                'low': 'low', 'close': 'close', 'volume': 'volume',
                                'amount': 'amount',
                            }
                            df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                            source = 'eastmoney'
                            print(f"  ✓ 东方财富数据源获取成功 ({len(df)} 条)")
                            break
                    except Exception:
                        continue

            if df is None or df.empty:
                print(f"  ✗ 所有数据源均无法获取数据")
                return False

            # 确保日期格式
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])

            # 按日期排序
            df = df.sort_values('date').reset_index(drop=True)

            # 保存数据
            dir_path = self._get_sector_dir('broad_index', symbol)
            csv_path = os.path.join(dir_path, f'{symbol}_daily.csv')
            self._save_csv(df, csv_path)

            # 保存元数据
            meta = {
                'code': symbol,
                'name': name,
                'short_name': short_name,
                'type': 'broad_index',
                'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'data_start': df['date'].iloc[0].strftime('%Y-%m-%d') if 'date' in df.columns else '',
                'data_end': df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else '',
                'data_rows': len(df),
            }
            meta_path = os.path.join(dir_path, f'{symbol}_meta.json')
            self._save_json(meta, meta_path)

            latest = df.iloc[-1]
            print(f"  最新日期: {meta['data_end']}, "
                  f"收盘: {latest.get('close', 'N/A')}, "
                  f"总天数: {len(df)}")
            return True

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return False

    def collect_all_broad_indices(self):
        """采集所有大盘指数"""
        print(f"\n{'='*60}")
        print(f"开始采集所有大盘指数数据")
        print(f"{'='*60}")

        results = {'success': [], 'failed': []}
        for idx in BROAD_INDEX_LIST:
            success = self.collect_broad_index_daily(
                idx['code'], idx['name'], idx['short_name']
            )
            if success:
                results['success'].append(idx['code'])
            else:
                results['failed'].append(idx['code'])
            time.sleep(0.5)  # 避免请求过快

        print(f"\n大盘指数采集完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
        if results['failed']:
            print(f"  失败列表: {results['failed']}")
        return results

    def collect_all_csi_indices(self):
        """采集所有中证指数（存入 broad_index 目录）"""
        print(f"\n{'='*60}")
        print(f"开始采集中证指数数据")
        print(f"{'='*60}")

        results = {'success': [], 'failed': []}
        for idx in CSI_INDEX_LIST:
            success = self.collect_broad_index_daily(
                idx['code'], idx['name'], idx['short_name']
            )
            if success:
                results['success'].append(idx['code'])
            else:
                results['failed'].append(idx['code'])
            time.sleep(0.5)

        print(f"\n中证指数采集完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
        if results['failed']:
            print(f"  失败列表: {results['failed']}")
        return results

    def collect_all_broad_indices_including_csi(self):
        """采集所有大盘指数（含中证指数）"""
        r1 = self.collect_all_broad_indices()
        r2 = self.collect_all_csi_indices()
        return {
            'broad': r1,
            'csi': r2,
        }

    # ==================== 港股指数采集 ====================

    def collect_hk_index_list(self):
        """获取所有港股指数列表

        Returns:
            pd.DataFrame: 指数列表
        """
        print(f"\n{'='*60}")
        print(f"采集港股指数列表")
        print(f"{'='*60}")

        try:
            df = ak.stock_hk_index_spot_em()
            if df is None or df.empty:
                print("  ✗ 未获取到港股指数列表")
                return None

            print(f"  获取到 {len(df)} 个港股指数")

            dir_path = os.path.join(self.data_root, 'hk_index')
            os.makedirs(dir_path, exist_ok=True)
            list_path = os.path.join(dir_path, '_index_list.csv')
            self._save_csv(df, list_path)

            # 打印核心指数
            print(f"  核心指数:")
            for hk_idx in HK_INDEX_LIST:
                code = hk_idx['code']
                matched = df[df['代码'].str.strip() == code]
                if len(matched) > 0:
                    row = matched.iloc[0]
                    print(f"    {code} - {hk_idx['name']}: 最新价={row['最新价']}, "
                          f"涨跌幅={row['涨跌幅']}%")

            return df

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return None

    def collect_hk_index_daily(self, symbol, name, short_name):
        """采集单只港股指数的历史日线数据

        数据源优先级: 新浪财经 > 东方财富

        Args:
            symbol: 指数代码 (如 HSI)
            name: 指数名称
            short_name: 简称

        Returns:
            bool: 是否成功
        """
        print(f"\n--- 采集港股: {name} ({symbol}) ---")

        from datetime import datetime as dt
        end_date = dt.now().strftime('%Y%m%d')
        start_date = '19900101'

        # 解析为标准指数代码（hk_ 前缀走 Sina）
        index_symbol = self._HK_CODE_MAP.get(symbol, f'hk_{symbol}')
        print(f"  指数代码: {index_symbol}")

        # ---- 数据源1：新浪财经 (主力) ----
        df = self._try_sina_index(index_symbol, start_date, end_date)

        # ---- 数据源2：东方财富 (兜底) ----
        if df is None:
            print(f"  新浪不可用，尝试东方财富...")
            try:
                df = ak.stock_hk_index_daily_em(symbol=symbol)
                if df is not None and not df.empty:
                    # eastmoney 列名不同: latest→close
                    col_map = {'date': 'date', 'open': 'open', 'high': 'high',
                               'low': 'low', 'latest': 'close'}
                    df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})
                    print(f"  ✓ 东方财富数据源获取成功 ({len(df)} 条)")
            except Exception as e:
                print(f"  ⚠ 东方财富 API 不可用 ({e})")

        if df is None or df.empty:
            print(f"  ✗ 所有数据源均无法获取数据")
            return False

        # HK指数可能无成交量，添加占位列（技术指标计算需要）
        if 'volume' not in df.columns:
            df['volume'] = 1

        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        df = df.sort_values('date').reset_index(drop=True)

        # 保存数据
        dir_path = self._get_sector_dir('hk_index', symbol)
        csv_path = os.path.join(dir_path, f'{symbol}_daily.csv')
        self._save_csv(df, csv_path)

        # 保存元数据
        meta = {
            'code': symbol,
            'name': name,
            'short_name': short_name,
            'type': 'hk_index',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_start': df['date'].iloc[0].strftime('%Y-%m-%d') if 'date' in df.columns else '',
            'data_end': df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else '',
            'data_rows': len(df),
        }
        meta_path = os.path.join(dir_path, f'{symbol}_meta.json')
        self._save_json(meta, meta_path)

        latest = df.iloc[-1]
        print(f"  最新日期: {meta['data_end']}, "
              f"收盘: {latest.get('close', 'N/A')}, "
              f"总天数: {len(df)}")
        return True

    def collect_core_hk_indices(self):
        """采集核心港股指数"""
        print(f"\n{'='*60}")
        print(f"采集核心港股指数")
        print(f"{'='*60}")

        results = {'success': [], 'failed': []}
        for idx in HK_INDEX_LIST:
            success = self.collect_hk_index_daily(
                idx['code'], idx['name'], idx['short_name']
            )
            if success:
                results['success'].append(idx['code'])
            else:
                results['failed'].append(idx['code'])
            time.sleep(1.0)  # 港股接口限流

        print(f"\n港股指数采集完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
        return results

    def collect_top_hk_indices(self, top_n=30):
        """采集前N个港股指数（按涨跌幅活跃度排序）"""
        print(f"\n{'='*60}")
        print(f"批量采集前 {top_n} 个港股指数")
        print(f"{'='*60}")

        list_path = os.path.join(self.data_root, 'hk_index', '_index_list.csv')
        if os.path.exists(list_path):
            df = pd.read_csv(list_path)
        else:
            df = self.collect_hk_index_list()
            if df is None:
                return {'success': [], 'failed': []}

        # 过滤掉衍生品/杠杆指数（含"倍"、"短仓"、"期货"等关键词）
        exclude_kw = ['倍', '短仓', '期货', '波幅']
        mask = ~df['名称'].str.contains('|'.join(exclude_kw), na=False)
        df_filtered = df[mask]

        results = {'success': [], 'failed': []}
        total = min(top_n, len(df_filtered))

        for i, (_, row) in enumerate(df_filtered.head(total).iterrows()):
            code = row['代码'].strip()
            name = row['名称']
            print(f"\n[{i+1}/{total}] {name} ({code})")

            success = self.collect_hk_index_daily(code, name, code)
            if success:
                results['success'].append(code)
            else:
                results['failed'].append(code)
            time.sleep(1.0)

        print(f"\n港股指数批量采集完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
        return results

    # ==================== 行业板块采集 ====================

    def collect_industry_board_list(self):
        """采集所有行业板块列表

        Returns:
            pd.DataFrame: 板块列表
        """
        print(f"\n{'='*60}")
        print(f"采集行业板块列表")
        print(f"{'='*60}")

        try:
            df = ak.stock_board_industry_name_em()
            if df is None or df.empty:
                print("  ✗ 未获取到行业板块列表")
                return None

            print(f"  获取到 {len(df)} 个行业板块")

            # 保存板块列表
            dir_path = os.path.join(self.data_root, 'industry')
            os.makedirs(dir_path, exist_ok=True)
            list_path = os.path.join(dir_path, '_board_list.csv')
            self._save_csv(df, list_path)

            # 打印前10个作为示例
            print(f"  示例板块 (前10):")
            for i, row in df.head(10).iterrows():
                name_col = '板块名称' if '板块名称' in df.columns else df.columns[1]
                code_col = '板块代码' if '板块代码' in df.columns else df.columns[0]
                print(f"    {row.get(code_col, '')} - {row.get(name_col, '')}")

            return df

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return None

    def collect_industry_board_daily(self, board_code, board_name=None):
        """采集单个行业板块的历史日线数据

        数据源优先级: 新浪财经(指数) > 东方财富(BK) > 同花顺(THS)

        Args:
            board_code: 板块代码 (如 BK0477 / sh000819 / sz399991)
            board_name: 板块名称 (可选，用于智能匹配指数代码)

        Returns:
            bool: 是否成功
        """
        if board_name:
            print(f"\n--- 采集板块: {board_name} ({board_code}) ---")
        else:
            print(f"\n--- 采集板块: {board_code} ---")

        from datetime import datetime as dt
        end_date = dt.now().strftime('%Y%m%d')
        start_date = '19900101'

        # 解析为标准指数代码
        index_symbol, display_name = self._resolve_index_code(board_code, board_name)
        df = None
        source = 'unknown'

        # ---- 数据源1：新浪财经 (最可靠) ----
        if index_symbol:
            board_name = display_name or board_name or board_code
            print(f"  指数代码: {index_symbol}")
            df = self._try_sina_index(index_symbol, start_date, end_date)
            if df is not None:
                source = 'sina'

        # ---- 数据源2：东方财富 BK (兜底) ----
        if df is None and board_code.startswith('BK'):
            df = self._try_eastmoney_history(board_code, start_date, end_date)
            if df is not None:
                source = 'eastmoney'

        # ---- 数据源3：同花顺 THS (最终兜底) ----
        if df is None and board_name:
            print(f"  尝试同花顺 (THS) 数据源...")
            df = self._try_ths_history(board_name, start_date, end_date)
            if df is not None:
                source = 'ths'

        if df is None or df.empty:
            print(f"  ✗ 所有数据源均无法获取数据")
            return False

        # 标准化列名
        col_map = {
            '日期': 'date', '开盘': 'open', '开盘价': 'open',
            '最高': 'high', '最高价': 'high',
            '最低': 'low', '最低价': 'low',
            '收盘': 'close', '收盘价': 'close',
            '成交量': 'volume', '成交额': 'amount',
            '涨跌幅': 'pct_change', '换手率': 'turnover_rate',
        }
        df = df.rename(columns={k: v for k, v in col_map.items() if k in df.columns})

        # 确保日期格式
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])

        df = df.sort_values('date').reset_index(drop=True)

        # 保存数据
        dir_path = self._get_sector_dir('industry', board_code)
        csv_path = os.path.join(dir_path, f'{board_code}_daily.csv')
        self._save_csv(df, csv_path)

        # 保存元数据
        meta = {
            'code': board_code,
            'name': board_name or board_code,
            'type': 'industry',
            'last_updated': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data_start': df['date'].iloc[0].strftime('%Y-%m-%d') if 'date' in df.columns else '',
            'data_end': df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else '',
            'data_rows': len(df),
        }
        meta_path = os.path.join(dir_path, f'{board_code}_meta.json')
        self._save_json(meta, meta_path)

        latest = df.iloc[-1]
        print(f"  最新日期: {meta['data_end']}, 收盘: {latest.get('close', 'N/A')}, "
              f"总天数: {len(df)}")
        return True

    def _try_sina_index(self, index_symbol, start_date, end_date):
        """尝试从新浪财经 API 获取指数日线数据

        新浪财经是快速分析使用的数据源，稳定可靠。
        支持 A股指数 (sh/sz前缀) 和 港股指数 (HSI/HSCEI等)。
        """
        try:
            # 判断是港股指数还是 A 股指数
            if index_symbol.startswith('hk_'):
                # 港股指数: hk_HSI, hk_HSCEI 等
                hk_code = index_symbol[3:]  # 去掉 hk_ 前缀
                df = ak.stock_hk_index_daily_sina(symbol=hk_code)
            else:
                # A 股指数
                df = ak.stock_zh_index_daily(symbol=index_symbol)

            if df is not None and not df.empty:
                # 过滤日期范围
                if 'date' in df.columns:
                    df['date'] = pd.to_datetime(df['date'])
                    start_dt = pd.to_datetime(start_date)
                    end_dt = pd.to_datetime(end_date)
                    df = df[(df['date'] >= start_dt) & (df['date'] <= end_dt)]
                print(f"  ✓ 新浪财经数据源获取成功 ({len(df)} 条)")
                return df
        except Exception as e:
            print(f"  ⚠ 新浪财经 API 失败: {e}")
        return None

    def _try_eastmoney_history(self, board_code, start_date, end_date):
        """尝试从东方财富 API 获取行业板块历史日线（带重试）"""
        max_retries = 2
        for attempt in range(1, max_retries + 1):
            try:
                df = ak.stock_board_industry_hist_em(
                    symbol=board_code,
                    period="日k",
                    start_date=start_date,
                    end_date=end_date,
                )
                if df is not None and not df.empty:
                    print(f"  ✓ 东方财富数据源获取成功")
                    return df
            except Exception as e:
                if attempt < max_retries:
                    wait = 2 ** attempt
                    print(f"  ⚠ 东方财富第 {attempt} 次请求失败，{wait}s 后重试...")
                    time.sleep(wait)
                else:
                    print(f"  ⚠ 东方财富 API 不可用 ({e})")
        return None

    # ===== 标准指数代码映射 =====
    # 数据源：新浪财经 stock_zh_index_daily（稳定可靠，快速分析也在用）
    # 优先使用 sh000xxx（用户熟悉的格式），停更的用 sz399xxx 替代
    _SECTOR_INDEX_MAP = {
        # ---- 中证行业指数 sh000xxx (还在更新的) ----
        '有色金属':   'sh000819',
        '钢铁':       'sh000823',
        '机械设备':   'sh000827',
        '轻工制造':   'sh000847',
        '科创芯片':   'sh000685',
        # ---- 中证主题指数 sz399xxx (sh000xxx 已停更的替代) ----
        '煤炭':       'sz399990',
        '电力':       'sz399990',   # 中证煤炭/电力共用一个
        '银行':       'sz399986',
        '证券':       'sz399993',
        '保险':       'sz399994',
        '白酒':       'sz399997',
        '医疗':       'sz399989',
        '医药':       'sz399808',
        '电子':       'sz399809',
        '半导体':     'sz399809',
        '芯片':       'sz399809',
        '军工':       'sz399967',
        '计算机':     'sz399998',
        '家电':       'sz399996',
        '基建':       'sz399995',
        '食品饮料':   'sz399807',
        '传媒':       'sz399810',
        '物流':       'sz399813',
        '农业':       'sz399814',
        '养老':       'sz399812',
        # ---- 申万行业指数 ----
        '制造业':     'sz399415',
        '消费':       'sz399416',
        '医药生物':   'sz399417',
        '信息技术':   'sz399418',
        '金融':       'sz399419',
        '房地产':     'sz399420',
        # ---- 大盘指数 ----
        '上证指数':   'sh000001',
        '深证成指':   'sz399001',
        '创业板指':   'sz399006',
        '科创50':     'sh000688',
        '沪深300':    'sh000300',
        '上证50':     'sh000016',
        '中证500':    'sh000905',
        '中证1000':   'sh000852',
        # ---- 港股指数 (hk_ 前缀走 Sina stock_hk_index_daily_sina) ----
        '恒生指数':   'hk_HSI',
        '国企指数':   'hk_HSCEI',
        '恒生科技':   'hk_HSTECH',
        '红筹指数':   'hk_HSCCI',
    }

    # HK代码 → hk_ 前缀映射
    _HK_CODE_MAP = {
        'HSI':    'hk_HSI',
        'HSCEI':  'hk_HSCEI',
        'HSTECH': 'hk_HSTECH',
        'HSCCI':  'hk_HSCCI',
    }

    # BK代码 → 标准指数代码（向后兼容）
    _BK_TO_INDEX_MAP = {
        'BK0478': 'sh000819',   # 有色金属
        'BK0479': 'sz399990',   # 煤炭
        'BK0480': 'sh000823',   # 钢铁
        'BK0482': 'sz399986',   # 银行
        'BK0483': 'sz399993',   # 证券
        'BK0484': 'sz399994',   # 保险
        'BK0488': 'sz399997',   # 白酒
        'BK0481': 'sz399990',   # 电力
        'BK0489': 'sz399809',   # 半导体
        'BK0487': 'sz399808',   # 医药
    }

    def _resolve_index_code(self, sector_code, board_name=None):
        """将 BK代码/板块名称/HK代码 解析为标准指数代码

        Returns:
            (str, str): (index_symbol, display_name) 或 (None, None)
        """
        # 1. 如果已经是 sh/sz/hk_ 开头的标准代码，直接使用
        if sector_code and (sector_code.startswith('sh') or sector_code.startswith('sz') or sector_code.startswith('hk_')):
            return sector_code, board_name or sector_code

        # 2. HK代码映射 (HSI, HSCEI 等)
        if sector_code and sector_code in self._HK_CODE_MAP:
            idx_code = self._HK_CODE_MAP[sector_code]
            return idx_code, board_name or sector_code

        # 3. BK代码映射
        if sector_code and sector_code in self._BK_TO_INDEX_MAP:
            idx_code = self._BK_TO_INDEX_MAP[sector_code]
            return idx_code, board_name or sector_code

        # 4. 板块名称映射
        if board_name and board_name in self._SECTOR_INDEX_MAP:
            return self._SECTOR_INDEX_MAP[board_name], board_name

        # 5. 模糊匹配板块名称
        if board_name:
            for key, code in self._SECTOR_INDEX_MAP.items():
                if key in board_name or board_name in key:
                    return code, board_name

        return None, None

    # 东方财富 → 同花顺 板块名称映射（两者分类体系不同）
    _EM_TO_THS_NAME_MAP = {
        '有色金属': '工业金属',
        '黄金': '贵金属',
        '贵金属': '贵金属',
        '煤炭': '煤炭开采加工',
        '钢铁': '钢铁',
        '小金属': '小金属',
        '能源金属': '能源金属',
    }

    # 概念板块名称映射（东方财富 → 同花顺）
    _EM_TO_THS_CONCEPT_MAP = {
        '科创芯片': '芯片概念',
        '半导体芯片': '芯片概念',
        '人工智能': '人工智能',
        '新能源车': '新能源汽车',
        '光伏': '光伏概念',
        '锂电池': '锂电池',
        '5G': '5G概念',
        '区块链': '区块链',
        '国产软件': '国产软件',
        '大数据': '大数据',
        '云计算': '云计算',
        '物联网': '物联网',
        '机器人': '机器人概念',
        '军工': '军工',
        '创新药': '创新药',
    }

    def _resolve_ths_name(self, em_name, board_type='industry'):
        """将东方财富板块名称映射到同花顺板块名称

        Args:
            em_name: 东方财富板块名称
            board_type: 'industry' | 'concept'

        Returns:
            str | None: 同花顺板块名称，无匹配返回 None
        """
        # 1. 直接匹配映射表
        if board_type == 'industry' and em_name in self._EM_TO_THS_NAME_MAP:
            return self._EM_TO_THS_NAME_MAP[em_name]
        if board_type == 'concept' and em_name in self._EM_TO_THS_CONCEPT_MAP:
            return self._EM_TO_THS_CONCEPT_MAP[em_name]

        # 2. 如果名称本身就在 THS 体系中，直接使用
        try:
            if board_type == 'industry':
                ths_list = ak.stock_board_industry_name_ths()
            else:
                ths_list = ak.stock_board_concept_name_ths()
            ths_names = set(ths_list['name'].tolist())
            if em_name in ths_names:
                return em_name
            # 模糊匹配（包含关系）
            for ths_name in ths_names:
                if em_name in ths_name or ths_name in em_name:
                    return ths_name
        except Exception:
            pass

        return None

    def _try_ths_history(self, board_name, start_date, end_date, board_type='industry'):
        """尝试从同花顺 API 获取板块历史日线

        Args:
            board_name: 板块名称
            start_date: 开始日期
            end_date: 结束日期
            board_type: 'industry' | 'concept'
        """
        # 先解析 THS 名称
        ths_name = self._resolve_ths_name(board_name, board_type)
        if ths_name is None:
            print(f"  ⚠ 同花顺未收录板块 '{board_name}'，跳过 THS 数据源")
            return None

        if ths_name != board_name:
            print(f"  映射: '{board_name}' → 同花顺 '{ths_name}'")

        try:
            if board_type == 'industry':
                df = ak.stock_board_industry_index_ths(
                    symbol=ths_name,
                    start_date=start_date,
                    end_date=end_date,
                )
            else:
                df = ak.stock_board_concept_index_ths(
                    symbol=ths_name,
                    start_date=start_date,
                    end_date=end_date,
                )
            if df is not None and not df.empty:
                # 确保有 volume 列
                if '成交量' not in df.columns and 'volume' not in df.columns:
                    df['成交量'] = 1
                if '成交额' not in df.columns and 'amount' not in df.columns:
                    df['成交额'] = 0
                print(f"  ✓ 同花顺数据源获取成功 ({len(df)} 条)")
                return df
        except Exception as e:
            print(f"  ✗ 同花顺 API 也失败: {e}")
        return None

    def collect_industry_board_constituents(self, board_code):
        """采集行业板块的成分股列表

        Args:
            board_code: 板块代码 (如 BK0477)

        Returns:
            bool: 是否成功
        """
        print(f"\n--- 采集成分股: {board_code} ---")
        try:
            df = ak.stock_board_industry_cons_em(symbol=board_code)

            if df is None or df.empty:
                print(f"  ✗ 未获取到成分股数据")
                return False

            # 保存成分股
            dir_path = self._get_sector_dir('industry', board_code)
            csv_path = os.path.join(dir_path, f'{board_code}_constituents.csv')
            self._save_csv(df, csv_path)

            print(f"  成分股数量: {len(df)}")
            return True

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return False

    def collect_top_industry_boards(self, top_n=30):
        """采集前N个行业板块的日线数据（按市场热度/成交量排序）

        Args:
            top_n: 采集前N个板块

        Returns:
            dict: 采集结果
        """
        print(f"\n{'='*60}")
        print(f"采集前 {top_n} 个行业板块日线数据")
        print(f"{'='*60}")

        # 先获取板块列表
        list_path = os.path.join(self.data_root, 'industry', '_board_list.csv')
        if os.path.exists(list_path):
            board_df = pd.read_csv(list_path)
        else:
            board_df = self.collect_industry_board_list()
            if board_df is None:
                return {'success': [], 'failed': []}

        # 确定代码列和名称列
        code_col = '板块代码' if '板块代码' in board_df.columns else board_df.columns[0]
        name_col = '板块名称' if '板块名称' in board_df.columns else board_df.columns[1]

        results = {'success': [], 'failed': []}
        total = min(top_n, len(board_df))

        for i, (_, row) in enumerate(board_df.head(total).iterrows()):
            code = row[code_col]
            name = row[name_col]
            print(f"\n[{i+1}/{total}] {name} ({code})")

            success = self.collect_industry_board_daily(code, name)
            if success:
                results['success'].append(code)
                # 也采集成分股
                self.collect_industry_board_constituents(code)
            else:
                results['failed'].append(code)

            time.sleep(1.0)  # 行业板块接口限流更严格

        print(f"\n行业板块采集完成: 成功 {len(results['success'])}, 失败 {len(results['failed'])}")
        return results

    # ==================== 概念板块采集（预留） ====================

    def collect_concept_board_list(self):
        """采集所有概念板块列表（预留）"""
        print(f"\n{'='*60}")
        print(f"采集概念板块列表")
        print(f"{'='*60}")

        try:
            df = ak.stock_board_concept_name_em()
            if df is None or df.empty:
                print("  ✗ 未获取到概念板块列表")
                return None

            print(f"  获取到 {len(df)} 个概念板块")

            dir_path = os.path.join(self.data_root, 'concept')
            os.makedirs(dir_path, exist_ok=True)
            list_path = os.path.join(dir_path, '_board_list.csv')
            self._save_csv(df, list_path)

            return df

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return None

    # ==================== 板块异动与资金流向 ====================

    def collect_board_changes(self):
        """采集当日板块异动数据"""
        print(f"\n{'='*60}")
        print(f"采集当日板块异动数据")
        print(f"{'='*60}")

        try:
            df = ak.stock_board_change_em()
            if df is None or df.empty:
                print("  ✗ 未获取到板块异动数据")
                return None

            dir_path = os.path.join(self.data_root, '_daily')
            os.makedirs(dir_path, exist_ok=True)
            csv_path = os.path.join(dir_path, 'board_changes.csv')
            self._save_csv(df, csv_path)

            print(f"  板块异动数量: {len(df)}")
            return df

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return None

    def collect_sector_fund_flow(self):
        """采集板块资金流向排名"""
        print(f"\n{'='*60}")
        print(f"采集板块资金流向排名")
        print(f"{'='*60}")

        try:
            df = ak.stock_sector_fund_flow_rank()
            if df is None or df.empty:
                print("  ✗ 未获取到资金流向数据")
                return None

            dir_path = os.path.join(self.data_root, '_daily')
            os.makedirs(dir_path, exist_ok=True)
            csv_path = os.path.join(dir_path, 'fund_flow.csv')
            self._save_csv(df, csv_path)

            print(f"  资金流向条目: {len(df)}")
            return df

        except Exception as e:
            print(f"  ✗ 采集失败: {str(e)}")
            return None

    # ==================== 综合采集 ====================

    def update_all(self):
        """一键更新所有板块数据"""
        print(f"\n{'#'*60}")
        print(f"# 板块数据一键更新")
        print(f"# 开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")

        summary = {}

        # 1. 大盘指数
        summary['broad_index'] = self.collect_all_broad_indices()

        # 2. 中证指数
        summary['csi_index'] = self.collect_all_csi_indices()

        # 3. 港股指数
        summary['hk_index'] = self.collect_core_hk_indices()

        # 4. 行业板块列表 + 前30个板块日线
        self.collect_industry_board_list()
        summary['industry'] = self.collect_top_industry_boards(top_n=30)

        # 5. 板块异动
        summary['board_changes'] = self.collect_board_changes()

        # 6. 资金流向
        summary['fund_flow'] = self.collect_sector_fund_flow()

        print(f"\n{'#'*60}")
        print(f"# 更新完成")
        print(f"# 结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'#'*60}")

        return summary

    def get_available_sectors(self):
        """获取所有已采集的板块列表（含元数据）"""
        sectors = []
        type_map = {
            'broad_index': '大盘指数',
            'hk_index': '港股指数',
            'industry': '行业板块',
            'concept': '概念板块',
        }

        for stype, stype_cn in type_map.items():
            type_dir = os.path.join(self.data_root, stype)
            if not os.path.exists(type_dir):
                continue
            for code in sorted(os.listdir(type_dir)):
                code_path = os.path.join(type_dir, code)
                if not os.path.isdir(code_path):
                    continue
                meta_file = os.path.join(code_path, f'{code}_meta.json')
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
                })

        return sectors


# ==================== CLI 入口 ====================

def main():
    parser = argparse.ArgumentParser(description='板块数据采集器')
    parser.add_argument('--type', type=str,
                        choices=['broad_index', 'hk_index', 'industry', 'concept', 'changes', 'fund_flow', 'all'],
                        default='all',
                        help='采集类型 (默认: all)')
    parser.add_argument('--code', type=str, help='指定板块/指数代码')
    parser.add_argument('--name', type=str, help='板块/指数名称')
    parser.add_argument('--top', type=int, default=30, help='采集前N个行业板块 (默认: 30)')
    parser.add_argument('--list', action='store_true', help='仅列出已采集的板块')
    args = parser.parse_args()

    collector = SectorDataCollector()

    # 仅列出已采集板块
    if args.list:
        sectors = collector.get_available_sectors()
        print(f"\n已采集板块 (共 {len(sectors)} 个):")
        print(f"{'类型':<10} {'代码':<15} {'名称':<20} {'数据量':<10} {'更新时间'}")
        print("-" * 80)
        for s in sectors:
            print(f"{s['type_cn']:<10} {s['code']:<15} {s['name']:<20} "
                  f"{s['data_rows']:<10} {s['last_updated']}")
        return

    # 按类型执行采集
    if args.type == 'broad_index':
        if args.code:
            # 采集单只指数
            name = args.name or args.code
            collector.collect_broad_index_daily(args.code, name, name)
        else:
            collector.collect_all_broad_indices_including_csi()

    elif args.type == 'hk_index':
        if args.code:
            # 采集单只港股指数
            name = args.name or args.code
            collector.collect_hk_index_daily(args.code, name, name)
        else:
            collector.collect_hk_index_list()
            collector.collect_core_hk_indices()

    elif args.type == 'industry':
        if args.code:
            collector.collect_industry_board_daily(args.code, args.name)
            collector.collect_industry_board_constituents(args.code)
        else:
            collector.collect_industry_board_list()
            collector.collect_top_industry_boards(top_n=args.top)

    elif args.type == 'concept':
        collector.collect_concept_board_list()

    elif args.type == 'changes':
        collector.collect_board_changes()

    elif args.type == 'fund_flow':
        collector.collect_sector_fund_flow()

    elif args.type == 'all':
        collector.update_all()


if __name__ == '__main__':
    main()
