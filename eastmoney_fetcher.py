# eastmoney_fetcher.py
# 统一的东方财富数据中心数据获取器
# --type market_performance | industry_valuation | industry_peers | industry_growth | dupont
# 每种 type 的输出格式与 GP_ANA_V3 的独立 fetch 脚本完全一致
import requests
import json
import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR

# ============================================================
# 共享基础设施
# ============================================================
BASE_URL = "https://datacenter.eastmoney.com/securities/api/data/v1/get"

BASE_HEADERS = {
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-site",
    "Origin": "https://emweb.securities.eastmoney.com",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "Sec-Fetch-Dest": "empty",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Sec-Fetch-Mode": "cors",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.6 Safari/605.1.15",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

REPORT_TYPES = {
    'market_performance': {
        'label': '历史日度市场表现',
    },
    'industry_valuation': {
        'label': '行业估值排名',
    },
    'industry_peers': {
        'label': '同行业公司对比',
    },
    'industry_growth': {
        'label': '行业成长能力排名',
    },
    'dupont': {
        'label': '杜邦分析行业排名',
    },
}


# ============================================================
# 数据获取
# ============================================================
def _do_request(params, headers_extra=None):
    """通用 HTTP 请求"""
    headers = dict(BASE_HEADERS)
    if headers_extra:
        headers.update(headers_extra)
    try:
        resp = requests.get(BASE_URL, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        if data.get('success') and data.get('result') and data['result'].get('data'):
            return data['result']['data']
        print("  响应格式不正确或无数据")
        return []
    except Exception as e:
        print(f"  获取数据出错: {e}")
        return []


def save_json(ticker, filename, save_obj):
    """通用保存"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_obj, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {file_path}")
    return file_path


# ============================================================
# 1. market_performance —— 与 V3 fetch_stock_market_performance.py 完全一致
# ============================================================
def run_market_performance(ticker):
    print(f"\n=== 历史日度市场表现: {ticker} ===")
    params = {
        "reportName": "RPT_PCF10_MARKETPER",
        "columns": "ALL",
        "filter": f'(SECUCODE="{ticker}")(TIME_TYPE=1)',
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    raw = _do_request(params)
    if not raw:
        print("  未获取到数据")
        return False

    processed = sorted(
        [{'trade_date': d.get('TRADE_DATE', ''),
          'change_rate': d.get('CHANGERATE', 0),
          'hs300_change_rate': d.get('HS300_CHANGERATE', 0),
          'board_change_rate': d.get('BOARD_CHANGERATE', 0),
          'board_name': d.get('BOARD_NAME', ''),
          'board_code': d.get('BOARD_CODE', '')} for d in raw],
        key=lambda x: x['trade_date'], reverse=True)

    save_json(ticker, f'{ticker}_market_performance.json', {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'market_performance': processed,
    })
    return True


# ============================================================
# 2. industry_valuation —— 与 V3 fetch_industry_valuation.py 完全一致
# ============================================================
def run_industry_valuation(ticker):
    print(f"\n=== 行业估值排名: {ticker} ===")
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_CVALUE",
        "columns": "ALL",
        "filter": f'(SECUCODE="{ticker}")',
        "sortTypes": 1,
        "sortColumns": "PAIMING",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    raw = _do_request(params)
    if not raw:
        print("  未获取到数据")
        return False

    code = ticker.split('.')[0]
    result = {'industry_average': None, 'industry_median': None, 'company_data': None, 'top_companies': []}
    val_keys = ['PE', 'PE_TTM', 'PE_1Y', 'PE_2Y', 'PE_3Y', 'PS', 'PS_TTM', 'PB', 'PB_MRQ', 'PEG', 'REPORT_DATE']

    for item in raw:
        name = item.get('CORRE_SECURITY_NAME', '')
        vals = {k: item.get(k, 0) for k in val_keys}
        if name == '行业平均':
            result['industry_average'] = vals
        elif name == '行业中值':
            result['industry_median'] = vals
        elif item.get('CORRE_SECURITY_CODE') == code:
            vals['stock_code'] = code
            vals['stock_name'] = name
            vals['PAIMING'] = item.get('PAIMING', 0)
            result['company_data'] = vals
        elif item.get('PAIMING') and int(item.get('PAIMING', 99)) <= 5:
            result['top_companies'].append({
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': name,
                'PE': item.get('PE', 0), 'PE_TTM': item.get('PE_TTM', 0),
                'PB': item.get('PB', 0), 'PEG': item.get('PEG', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),  # V3 有此字段
            })

    save_json(ticker, f'{ticker}_industry_valuation.json', {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'industry_valuation': result,
    })
    return True


# ============================================================
# 3. industry_peers —— 与 V3 fetch_industry_peers.py 完全一致
# ============================================================
def run_industry_peers(ticker):
    print(f"\n=== 同行业公司对比: {ticker} ===")
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_MARKET",
        "columns": "SECUCODE,SECURITY_CODE,SECURITY_NAME_ABBR,ORG_CODE,CORRE_SECUCODE,CORRE_SECURITY_CODE,CORRE_SECURITY_NAME,CORRE_ORG_CODE,TOTAL_CAP,FREECAP,TOTAL_OPERATEINCOME,NETPROFIT,REPORT_TYPE,TOTAL_CAP_RANK,FREECAP_RANK,TOTAL_OPERATEINCOME_RANK,NETPROFIT_RANK",
        "filter": f'(SECUCODE="{ticker}")(CORRE_SECUCODE<>"{ticker}")(CORRE_SECUCODE<>"行业平均")(CORRE_SECUCODE<>"行业中值")',
        "pageNumber": 1,
        "pageSize": 5,
        "sortTypes": -1,
        "sortColumns": "NETPROFIT",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    # 与 V3 完全一致的请求头
    headers_extra = {"Priority": "u=3, I"}  # 注意大写 I
    raw = _do_request(params, headers_extra)
    if not raw:
        print("  未获取到数据")
        return False

    processed = []
    for item in raw:
        processed.append({
            'stock_code': item.get('CORRE_SECURITY_CODE', ''),
            'stock_name': item.get('CORRE_SECURITY_NAME', ''),
            'ticker': item.get('CORRE_SECUCODE', ''),
            'total_market_cap': item.get('TOTAL_CAP', 0) / 100000000,  # 转换为亿元（V3 行为）
            'free_market_cap': item.get('FREECAP', 0),
            'total_operating_income': item.get('TOTAL_OPERATEINCOME', 0) / 100000000,  # 转换为亿元
            'net_profit': item.get('NETPROFIT', 0) / 100000000,  # 转换为亿元
            'report_type': item.get('REPORT_TYPE', ''),
            'total_cap_rank': item.get('TOTAL_CAP_RANK', 0),
            'free_cap_rank': item.get('FREECAP_RANK', 0),
            'operating_income_rank': item.get('TOTAL_OPERATEINCOME_RANK', 0),
            'net_profit_rank': item.get('NETPROFIT_RANK', 0),
        })

    save_json(ticker, f'{ticker}_industry_peers.json', {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'report_type': processed[0].get('report_type', '') if processed else '',
        'industry_peers': processed,
    })
    return True


# ============================================================
# 4. industry_growth —— 与 V3 fetch_industry_growth.py 完全一致
# ============================================================
def run_industry_growth(ticker):
    print(f"\n=== 行业成长能力排名: {ticker} ===")
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_GROWTH",
        "columns": "ALL",
        "filter": f'(SECUCODE="{ticker}")',
        "sortTypes": 1,
        "sortColumns": "PAIMING",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    headers_extra = {"Priority": "u=3, I"}  # V3 大写 I
    raw = _do_request(params, headers_extra)
    if not raw:
        print("  未获取到数据")
        return False

    result = {'industry_average': None, 'industry_median': None, 'company_data': None, 'top_companies': []}
    code = ticker.split('.')[0]

    # V3 的完整字段列表（中文缩写，含 3 年预测值）
    growth_fields = [
        'YYSRTB', 'MGSYTB', 'JLRTB',  # 同比
        'JLR_3Y', 'YYSR_3Y', 'MGSY_3Y',  # 3年复合
        'YYSRTTM', 'MGSYTTM', 'JLRTTM',  # TTM
        'MGSY_1E', 'MGSY_2E', 'MGSY_3E',  # 每股收益预测
        'JLR_1E', 'JLR_2E', 'JLR_3E',  # 净利润预测
        'YYSR_1E', 'YYSR_2E', 'YYSR_3E',  # 营业收入预测
        'REPORT_DATE',
    ]

    for item in raw:
        if item.get('CORRE_SECURITY_NAME') == '行业平均':
            result['industry_average'] = {k: item.get(k, 0) for k in growth_fields}
        elif item.get('CORRE_SECURITY_NAME') == '行业中值':
            result['industry_median'] = {k: item.get(k, 0) for k in growth_fields}
        elif item.get('CORRE_SECURITY_CODE') == code:
            company = {k: item.get(k, 0) for k in growth_fields}
            company['stock_code'] = item.get('CORRE_SECURITY_CODE', '')
            company['stock_name'] = item.get('CORRE_SECURITY_NAME', '')
            company['PAIMING'] = item.get('PAIMING', 0)
            result['company_data'] = company
        elif item.get('PAIMING') and int(item.get('PAIMING', 99)) <= 5:
            result['top_companies'].append({
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': item.get('CORRE_SECURITY_NAME', ''),
                'YYSRTB': item.get('YYSRTB', 0),
                'MGSYTB': item.get('MGSYTB', 0),
                'JLRTB': item.get('JLRTB', 0),
                'JLR_3Y': item.get('JLR_3Y', 0),
                'YYSR_3Y': item.get('YYSR_3Y', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),
            })

    save_json(ticker, f'{ticker}_industry_growth.json', {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'industry_growth': result,
    })
    return True


# ============================================================
# 5. dupont —— 与 V3 fetch_dupont_analysis.py 完全一致
# ============================================================
def run_dupont(ticker):
    print(f"\n=== 杜邦分析行业排名: {ticker} ===")
    params = {
        "reportName": "RPT_PCF10_INDUSTRY_DBFX",
        "columns": "ALL",
        "filter": f'(SECUCODE="{ticker}")',
        "sortTypes": 1,
        "sortColumns": "PAIMING",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    headers_extra = {"Priority": "u=3, I"}  # V3 大写 I
    raw = _do_request(params, headers_extra)
    if not raw:
        print("  未获取到数据")
        return False

    result = {'industry_average': None, 'industry_median': None, 'company_data': None, 'top_companies': []}
    code = ticker.split('.')[0]

    for item in raw:
        if item.get('CORRE_SECURITY_NAME') == '行业平均':
            result['industry_average'] = {
                'ROE_AVG': item.get('ROE_AVG', 0),
                'XSJLL_AVG': item.get('XSJLL_AVG', 0),
                'TOAZZL_AVG': item.get('TOAZZL_AVG', 0),
                'QYCS_AVG': item.get('QYCS_AVG', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),
            }
        elif item.get('CORRE_SECURITY_NAME') == '行业中值':
            result['industry_median'] = {
                'ROE_AVG': item.get('ROE_AVG', 0),
                'XSJLL_AVG': item.get('XSJLL_AVG', 0),
                'TOAZZL_AVG': item.get('TOAZZL_AVG', 0),
                'QYCS_AVG': item.get('QYCS_AVG', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),
            }
        elif item.get('CORRE_SECURITY_CODE') == code:
            result['company_data'] = {
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': item.get('CORRE_SECURITY_NAME', ''),
                # V3 历史分层数据
                'ROEPJ_L3': item.get('ROEPJ_L3', 0),
                'ROEPJ_L2': item.get('ROEPJ_L2', 0),
                'ROEPJ_L1': item.get('ROEPJ_L1', 0),
                'ROE_AVG': item.get('ROE_AVG', 0),
                'XSJLL_L3': item.get('XSJLL_L3', 0),
                'XSJLL_L2': item.get('XSJLL_L2', 0),
                'XSJLL_L1': item.get('XSJLL_L1', 0),
                'XSJLL_AVG': item.get('XSJLL_AVG', 0),
                'TOAZZL_L3': item.get('TOAZZL_L3', 0),
                'TOAZZL_L2': item.get('TOAZZL_L2', 0),
                'TOAZZL_L1': item.get('TOAZZL_L1', 0),
                'TOAZZL_AVG': item.get('TOAZZL_AVG', 0),
                'QYCS_L3': item.get('QYCS_L3', 0),
                'QYCS_L2': item.get('QYCS_L2', 0),
                'QYCS_L1': item.get('QYCS_L1', 0),
                'QYCS_AVG': item.get('QYCS_AVG', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),
            }
        elif item.get('PAIMING') and int(item.get('PAIMING', 99)) <= 5:
            result['top_companies'].append({
                'stock_code': item.get('CORRE_SECURITY_CODE', ''),
                'stock_name': item.get('CORRE_SECURITY_NAME', ''),
                'ROE_AVG': item.get('ROE_AVG', 0),
                'XSJLL_AVG': item.get('XSJLL_AVG', 0),
                'TOAZZL_AVG': item.get('TOAZZL_AVG', 0),
                'QYCS_AVG': item.get('QYCS_AVG', 0),
                'PAIMING': item.get('PAIMING', 0),
                'REPORT_DATE': item.get('REPORT_DATE', ''),
            })

    # 注意：V3 的数据键是 "dupont_analysis"，不是 "dupont"
    save_json(ticker, f'{ticker}_dupont_analysis.json', {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'dupont_analysis': result,
    })
    return True


# ============================================================
# 调度与 CLI
# ============================================================
RUNNERS = {
    'market_performance': run_market_performance,
    'industry_valuation': run_industry_valuation,
    'industry_peers': run_industry_peers,
    'industry_growth': run_industry_growth,
    'dupont': run_dupont,
}


def main():
    import argparse
    parser = argparse.ArgumentParser(description="东方财富数据中心统一数据获取器")
    parser.add_argument('--ticker', required=True, help="股票代码，如 300433.SZ")
    parser.add_argument('--type', choices=list(RUNNERS.keys()), required=True,
                        help="数据类型")
    parser.add_argument('--all', action='store_true', help="获取全部类型")
    args = parser.parse_args()

    if args.all:
        for rt in RUNNERS:
            RUNNERS[rt](args.ticker)
    else:
        RUNNERS[args.type](args.ticker)


if __name__ == "__main__":
    main()
