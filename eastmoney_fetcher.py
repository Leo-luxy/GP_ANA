# eastmoney_fetcher.py
# 统一的东方财富数据中心数据获取器
# --type market_performance | industry_valuation | industry_peers | industry_growth | dupont
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
HEADERS = {
    "Accept": "*/*",
    "Sec-Fetch-Site": "same-site",
    "Origin": "https://emweb.securities.eastmoney.com",
    "Referer": "https://emweb.securities.eastmoney.com/",
    "Sec-Fetch-Dest": "empty",
    "Accept-Language": "zh-CN,zh-Hans;q=0.9",
    "Sec-Fetch-Mode": "cors",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Priority": "u=3, i",
}

REPORT_TYPES = {
    'market_performance': {
        'reportName': 'RPT_PCF10_MARKETPER',
        'extra_params': {'filter': '(SECUCODE="{ticker}")(TIME_TYPE=1)'},
        'filename': '{ticker}_market_performance.json',
        'label': '历史日度市场表现',
    },
    'industry_valuation': {
        'reportName': 'RPT_PCF10_INDUSTRY_CVALUE',
        'extra_params': {
            'filter': '(SECUCODE="{ticker}")',
            'sortTypes': 1,
            'sortColumns': 'PAIMING',
        },
        'filename': '{ticker}_industry_valuation.json',
        'label': '行业估值排名',
    },
    'industry_peers': {
        'reportName': 'RPT_PCF10_INDUSTRY_MARKET',
        'extra_params': {'filter': '(SECUCODE="{ticker}")'},
        'filename': '{ticker}_industry_peers.json',
        'label': '同行业公司对比',
    },
    'industry_growth': {
        'reportName': 'RPT_PCF10_INDUSTRY_GROWTH',
        'extra_params': {'filter': '(SECUCODE="{ticker}")'},
        'filename': '{ticker}_industry_growth.json',
        'label': '行业成长能力排名',
    },
    'dupont': {
        'reportName': 'RPT_PCF10_INDUSTRY_DBFX',
        'extra_params': {'filter': '(SECUCODE="{ticker}")'},
        'filename': '{ticker}_dupont_analysis.json',
        'label': '杜邦分析行业排名',
    },
}


def fetch_data(ticker, report_type):
    """通用数据获取"""
    cfg = REPORT_TYPES[report_type]
    url = BASE_URL
    params = {
        "reportName": cfg['reportName'],
        "columns": "ALL",
        "source": "HSF10",
        "client": "PC",
        "v": str(int(datetime.now().timestamp() * 1000)),
    }
    # 注入 ticker 到 filter
    extra = {}
    for k, v in cfg['extra_params'].items():
        if isinstance(v, str):
            extra[k] = v.format(ticker=ticker)
        else:
            extra[k] = v
    params.update(extra)

    print(f"获取 {ticker} 的 {cfg['label']} 数据...")
    try:
        resp = requests.get(url, params=params, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        if data.get('success') and data.get('result') and data['result'].get('data'):
            result = data['result']['data']
            print(f"  获取到 {len(result)} 条数据")
            return result
        print("  响应格式不正确或无数据")
        return []
    except Exception as e:
        print(f"  获取数据出错: {e}")
        return []


def save_data(ticker, report_type, processed):
    """通用数据保存"""
    cfg = REPORT_TYPES[report_type]
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    file_path = os.path.join(stock_dir, cfg['filename'].format(ticker=ticker))
    save_obj = {
        'ticker': ticker,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'data_source': '东方财富数据中心',
        'report_type': report_type,
    }
    # 用 report_type 作为 key
    save_obj[report_type] = processed
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(save_obj, f, ensure_ascii=False, indent=2)
    print(f"  已保存: {file_path}")
    return file_path


# ============================================================
# 各类型数据处理
# ============================================================
def process_market_performance(raw, ticker):
    return sorted(
        [{'trade_date': d.get('TRADE_DATE', ''),
          'change_rate': d.get('CHANGERATE', 0),
          'hs300_change_rate': d.get('HS300_CHANGERATE', 0),
          'board_change_rate': d.get('BOARD_CHANGERATE', 0),
          'board_name': d.get('BOARD_NAME', ''),
          'board_code': d.get('BOARD_CODE', '')} for d in raw],
        key=lambda x: x['trade_date'], reverse=True)


def process_industry_valuation(raw, ticker):
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
            })
    return result


def process_industry_peers(raw, ticker):
    code = ticker.split('.')[0]
    return [{
        'security_code': d.get('SECURITY_CODE', ''),
        'security_name': d.get('SECURITY_NAME_ABBR', ''),
        'net_profit': d.get('NET_PROFIT', 0),
        'net_profit_yoy': d.get('NET_PROFIT_YOY', 0),
        'revenue': d.get('TOTAL_OPERATE_INCOME', 0),
        'gross_margin': d.get('GROSS_PROFIT_RATIO', 0),
        'roe': d.get('ROE', 0),
        'pe': d.get('PE', 0), 'pb': d.get('PB', 0),
        'market_cap': d.get('TOTAL_MARKET_CAP', 0),
        'is_self': d.get('SECURITY_CODE', '') == code,
    } for d in raw]


def process_industry_growth(raw, ticker):
    code = ticker.split('.')[0]
    return {
        'industry_average': _extract_growth(raw, '行业平均'),
        'industry_median': _extract_growth(raw, '行业中值'),
        'company_data': _extract_growth(raw, None, code),
    }


def _extract_growth(items, label=None, code=None):
    keys = ['NET_PROFIT_GROWTH', 'NET_PROFIT_GROWTH_RANK', 'TOTAL_REVENUE_GROWTH',
            'TOTAL_REVENUE_GROWTH_RANK', 'EPS_GROWTH', 'EPS_GROWTH_RANK', 'REPORT_DATE']
    for d in items:
        if label and d.get('CORRE_SECURITY_NAME') == label:
            return {k: d.get(k, 0) for k in keys}
        if code and d.get('CORRE_SECURITY_CODE') == code:
            r = {k: d.get(k, 0) for k in keys}
            r['stock_name'] = d.get('CORRE_SECURITY_NAME', '')
            r['PAIMING'] = d.get('PAIMING', 0)
            return r
    return None


def process_dupont(raw, ticker):
    code = ticker.split('.')[0]
    return {
        'industry_average': _extract_dupont(raw, '行业平均'),
        'industry_median': _extract_dupont(raw, '行业中值'),
        'company_data': _extract_dupont(raw, None, code),
    }


def _extract_dupont(items, label=None, code=None):
    keys = ['ROE', 'ROE_RANK', 'NET_PROFIT_RATIO', 'NET_PROFIT_RATIO_RANK',
            'ASSET_TURNOVER', 'ASSET_TURNOVER_RANK', 'EQUITY_MULTIPLIER',
            'EQUITY_MULTIPLIER_RANK', 'REPORT_DATE']
    for d in items:
        if label and d.get('CORRE_SECURITY_NAME') == label:
            return {k: d.get(k, 0) for k in keys}
        if code and d.get('CORRE_SECURITY_CODE') == code:
            r = {k: d.get(k, 0) for k in keys}
            r['stock_name'] = d.get('CORRE_SECURITY_NAME', '')
            r['PAIMING'] = d.get('PAIMING', 0)
            return r
    return None


# ============================================================
# CLI
# ============================================================
PROCESSORS = {
    'market_performance': process_market_performance,
    'industry_valuation': process_industry_valuation,
    'industry_peers': process_industry_peers,
    'industry_growth': process_industry_growth,
    'dupont': process_dupont,
}


def run(ticker, report_type):
    print(f"\n=== {REPORT_TYPES[report_type]['label']}: {ticker} ===")
    raw = fetch_data(ticker, report_type)
    if not raw:
        print("  未获取到数据")
        return False
    processed = PROCESSORS[report_type](raw, ticker)
    save_data(ticker, report_type, processed)
    return True


def main():
    import argparse
    parser = argparse.ArgumentParser(description="东方财富数据中心统一数据获取器")
    parser.add_argument('--ticker', required=True, help="股票代码，如 300433.SZ")
    parser.add_argument('--type', choices=list(REPORT_TYPES.keys()), required=True,
                        help="数据类型")
    parser.add_argument('--all', action='store_true', help="获取全部类型")
    args = parser.parse_args()

    if args.all:
        for rt in REPORT_TYPES:
            run(args.ticker, rt)
    else:
        run(args.ticker, args.type)


if __name__ == "__main__":
    main()
