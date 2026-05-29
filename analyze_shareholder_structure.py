
# analyze_shareholder_structure.py
# 功能：综合分析股东结构数据，包括company_info.json、shareholder.csv、shareholder_num.csv
# 优化版本：提取全部有用信息，计算量化指标，提供全面的股东结构分析

import json
import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DATA_DIR, AI_CONFIG

def load_company_info(ticker):
    """加载公司信息文件"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    
    # 加载公司基本信息
    basic_info_file = os.path.join(stock_dir, f"{ticker}_company_basic.json")
    if not os.path.exists(basic_info_file):
        print(f"公司基本信息文件不存在: {basic_info_file}")
        return None
    
    try:
        with open(basic_info_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"成功加载 {ticker} 的公司基本信息文件: {basic_info_file}")
    except Exception as e:
        print(f"加载公司基本信息文件时出错: {str(e)}")
        return None
    
    # 加载主要股东数据
    import pandas as pd
    
    # 加载主要股东数据（使用新的历史股东数据文件）
    main_shareholders_file = os.path.join(stock_dir, f"{ticker}_historical_shareholders.csv")
    if os.path.exists(main_shareholders_file):
        try:
            main_shareholders_df = pd.read_csv(main_shareholders_file)
            # 转换字段名以保持兼容性
            if 'END_DATE' in main_shareholders_df.columns:
                main_shareholders_df = main_shareholders_df.rename(columns={
                    'END_DATE': '截至日期',
                    'HOLDER_NAME': '股东名称',
                    'HOLD_NUM': '持股数量',
                    'HOLD_NUM_RATIO': '持股比例',
                    'SHARES_TYPE': '股本性质'
                })
            data['main_shareholders'] = main_shareholders_df.to_dict('records')
            print(f"成功加载 {ticker} 的主要股东数据: {main_shareholders_file}")
        except Exception as e:
            print(f"加载主要股东数据时出错: {str(e)}")
    
    return data

def load_shareholder_data(ticker):
    """加载机构持股数据（institutional_holdings.csv）"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    shareholder_file = os.path.join(stock_dir, f"{ticker}_institutional_holdings.csv")
    
    if not os.path.exists(shareholder_file):
        print(f"机构持股文件不存在: {shareholder_file}")
        return None
    
    try:
        df = pd.read_csv(shareholder_file)
        print(f"成功加载机构持股数据: {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"加载机构持股数据时出错: {str(e)}")
        return None

def load_shareholder_num_data(ticker):
    """加载股东户数数据（shareholder_num.csv）"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    shareholder_num_file = os.path.join(stock_dir, f"{ticker}_shareholder_num.csv")
    
    if not os.path.exists(shareholder_num_file):
        print(f"股东户数文件不存在: {shareholder_num_file}")
        return None
    
    try:
        df = pd.read_csv(shareholder_num_file)
        # 按日期排序
        if 'END_DATE' in df.columns:
            df['END_DATE'] = pd.to_datetime(df['END_DATE'])
            df.sort_values('END_DATE', ascending=False, inplace=True)
        print(f"成功加载股东户数数据: {len(df)} 条记录")
        return df
    except Exception as e:
        print(f"加载股东户数数据时出错: {str(e)}")
        return None

def load_north_fund_data(ticker):
    """加载北向资金数据，同时返回north_holdings.csv和north_fund.csv的数据"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    data = {}
    
    # 加载 north_holdings.csv（季度汇总数据）
    north_holdings_file = os.path.join(stock_dir, f"{ticker}_north_holdings.csv")
    if os.path.exists(north_holdings_file):
        try:
            df_holdings = pd.read_csv(north_holdings_file)
            # 按日期排序
            if 'TRADE_DATE' in df_holdings.columns:
                df_holdings['TRADE_DATE'] = pd.to_datetime(df_holdings['TRADE_DATE'])
                df_holdings.sort_values('TRADE_DATE', ascending=False, inplace=True)
            print(f"成功加载北向资金季度汇总数据（north_holdings.csv）: {len(df_holdings)} 条记录")
            data['holdings'] = df_holdings
        except Exception as e:
            print(f"加载north_holdings.csv时出错: {str(e)}")
    
    # 加载 north_fund.csv（机构明细数据）
    north_fund_file = os.path.join(stock_dir, f"{ticker}_north_fund.csv")
    if os.path.exists(north_fund_file):
        try:
            df_fund = pd.read_csv(north_fund_file)
            # 按日期排序
            if 'TRADE_DATE' in df_fund.columns:
                df_fund['TRADE_DATE'] = pd.to_datetime(df_fund['TRADE_DATE'])
                df_fund.sort_values('TRADE_DATE', ascending=False, inplace=True)
            print(f"成功加载北向资金机构明细数据（north_fund.csv）: {len(df_fund)} 条记录")
            data['fund'] = df_fund
        except Exception as e:
            print(f"加载north_fund.csv时出错: {str(e)}")
    
    if not data:
        print("北向资金文件不存在")
        return None
    
    return data

def extract_comprehensive_data(company_info, shareholder_df, shareholder_num_df, north_fund_df):
    """提取全面的股东结构数据"""
    data = {}
    
    # 1. 提取公司基本信息
    if 'basic_info' in company_info:
        basic = company_info['basic_info']
        data['company_basic'] = {
            '公司全称': basic.get('公司全称', ''),
            '公司简称': basic.get('公司简称', ''),
            '主营业务': basic.get('主营业务', ''),
            '所属行业': basic.get('所属行业', ''),
            '实际控制人': basic.get('实际控制人', ''),
            '员工人数': basic.get('员工人数', ''),
            '成立日期': basic.get('成立日期', ''),
            '上市日期': basic.get('上市日期', '')
        }
    
    # 2. 提取规模比较信息
    if 'scale_comparison' in company_info and company_info['scale_comparison']:
        scale_data = company_info['scale_comparison'][0]  # 取第一条数据
        data['scale_comparison'] = {
            '总市值': scale_data.get('总市值', 0),
            '总市值排名': scale_data.get('总市值排名', 0),
            '流通市值': scale_data.get('流通市值', 0),
            '流通市值排名': scale_data.get('流通市值排名', 0),
            '营业收入': scale_data.get('营业收入', 0),
            '营业收入排名': scale_data.get('营业收入排名', 0),
            '净利润': scale_data.get('净利润', 0),
            '净利润排名': scale_data.get('净利润排名', 0)
        }
    
    # 2. 提取大股东数据（前十大股东）
    if 'main_shareholders' in company_info:
        main_holders = company_info['main_shareholders']
        if isinstance(main_holders, list) and len(main_holders) > 0:
            # 只保留最新一期的数据
            # 先按截至日期分组
            from collections import defaultdict
            date_groups = defaultdict(list)
            for holder in main_holders:
                end_date = holder.get('截至日期', '')
                if end_date:
                    date_groups[end_date].append(holder)
            
            # 找到最新日期
            if date_groups:
                latest_date = max(date_groups.keys())
                latest_holders = date_groups[latest_date]
                print(f"使用最新一期股东数据: {latest_date}, 共 {len(latest_holders)} 条记录")
            else:
                latest_holders = main_holders[:10]
                print("无法确定最新日期，使用前10条记录")
            
            # 按持股比例排序
            sorted_holders = sorted(latest_holders, 
                                  key=lambda x: float(x.get('持股比例', 0)) if pd.notna(x.get('持股比例', 0)) else 0, 
                                  reverse=True)
            
            data['main_shareholders'] = []
            total_ratio = 0
            for holder in sorted_holders[:10]:
                ratio = float(holder.get('持股比例', 0)) if pd.notna(holder.get('持股比例', 0)) else 0
                total_ratio += ratio
                data['main_shareholders'].append({
                    '股东名称': holder.get('股东名称', ''),
                    '持股数量': holder.get('持股数量', 0),
                    '持股比例': ratio,
                    '股本性质': holder.get('股本性质', ''),
                    '截至日期': holder.get('截至日期', '')
                })
            
            # 计算股权集中度指标
            first_ratio = float(sorted_holders[0].get('持股比例', 0)) if pd.notna(sorted_holders[0].get('持股比例', 0)) else 0
            top5_ratio = sum(float(h.get('持股比例', 0)) if pd.notna(h.get('持股比例', 0)) else 0 for h in sorted_holders[:5])
            
            # 确保持股比例总和合理（如果超过100%，按比例调整）
            if total_ratio > 100:
                print(f"警告：前十大股东持股比例总和 {total_ratio:.2f}% 超过100%，正在按比例调整")
                scale_factor = 100 / total_ratio
                for holder in data['main_shareholders']:
                    holder['持股比例'] = holder['持股比例'] * scale_factor
                total_ratio = 100
                top5_ratio = top5_ratio * scale_factor
                first_ratio = first_ratio * scale_factor
            
            data['concentration'] = {
                '第一大股东持股比例': round(first_ratio, 2),
                '前五大股东持股比例合计': round(top5_ratio, 2),
                '前十大股东持股比例合计': round(total_ratio, 2),
                '股权集中度': '高度集中' if total_ratio > 70 else '中度集中' if total_ratio > 50 else '分散',
                '统计日期': latest_date if date_groups else ''
            }
    
    # 3. 提取机构持仓数据
    if shareholder_df is not None and not shareholder_df.empty:
        # 机构数量统计
        org_types = shareholder_df['ORG_TYPE'].value_counts().to_dict() if 'ORG_TYPE' in shareholder_df.columns else {}
        
        # 按持仓市值排序取前20
        if 'HOLD_VALUE' in shareholder_df.columns:
            top_institutions = shareholder_df.nlargest(20, 'HOLD_VALUE')
            data['institutional_holders'] = []
            for _, row in top_institutions.iterrows():
                data['institutional_holders'].append({
                    '机构名称': row.get('HOLDER_NAME', ''),
                    '持股数量': row.get('TOTAL_SHARES', 0),
                    '持仓市值': row.get('HOLD_VALUE', 0),
                    '占总股本比例': row.get('TOTALSHARES_RATIO', 0),
                    '占流通股比例': row.get('FREESHARES_RATIO', 0),
                    '基金代码': row.get('FUND_CODE', ''),
                    '净值占比': row.get('NETVALUE_RATIO', '')
                })
        
        # 机构持仓统计
        data['institutional_stats'] = {
            '机构数量': len(shareholder_df),
            '机构持仓总市值': shareholder_df['HOLD_VALUE'].sum() if 'HOLD_VALUE' in shareholder_df.columns else 0,
            '机构平均持仓市值': shareholder_df['HOLD_VALUE'].mean() if 'HOLD_VALUE' in shareholder_df.columns else 0,
            '机构类型分布': org_types
        }
    
    # 4. 提取股东户数数据
    if shareholder_num_df is not None and not shareholder_num_df.empty:
        # 最新一期数据
        latest = shareholder_num_df.iloc[0]
        
        data['shareholder_num'] = {
            '最新股东户数': latest.get('HOLDER_TOTAL_NUM', 0),
            '最新户均持股': latest.get('AVG_FREE_SHARES', 0),
            '持股集中度': latest.get('HOLD_FOCUS', ''),
            '统计日期': latest.get('END_DATE', '').strftime('%Y-%m-%d') if pd.notna(latest.get('END_DATE', '')) else ''
        }
        
        # 计算趋势指标
        if len(shareholder_num_df) >= 2:
            # 股东户数变化趋势
            recent_4q = shareholder_num_df.head(4)
            data['shareholder_trends'] = {
                '近一季度股东户数变化': recent_4q.iloc[0].get('TOTAL_NUM_RATIO', 0) if len(recent_4q) > 0 else 0,
                '近二季度股东户数变化': recent_4q.head(2)['TOTAL_NUM_RATIO'].sum() if len(recent_4q) >= 2 else 0,
                '近四季度股东户数变化': recent_4q['TOTAL_NUM_RATIO'].sum() if len(recent_4q) >= 4 else shareholder_num_df['TOTAL_NUM_RATIO'].sum(),
                '股东户数趋势': '上升（筹码分散）' if recent_4q.iloc[0].get('TOTAL_NUM_RATIO', 0) > 0 else '下降（筹码集中）',
                '户均持股趋势': '上升' if recent_4q.iloc[0].get('AVG_FREESHARES_RATIO', 0) > 0 else '下降'
            }
        
        # 历史数据（最近8个季度）
        historical = []
        for _, row in shareholder_num_df.head(8).iterrows():
            historical.append({
                '统计日期': row.get('END_DATE', '').strftime('%Y-%m-%d') if pd.notna(row.get('END_DATE', '')) else '',
                '股东户数': row.get('HOLDER_TOTAL_NUM', 0),
                '户均持股': row.get('AVG_FREE_SHARES', 0),
                '户数变动比例': row.get('TOTAL_NUM_RATIO', 0),
                '持股集中度': row.get('HOLD_FOCUS', '')
            })
        data['historical_data'] = historical
    
    # 6. 提取北向资金数据
    if north_fund_df is not None:
        # 首先处理 north_holdings.csv 数据（季度汇总）
        if 'holdings' in north_fund_df:
            df_holdings = north_fund_df['holdings']
            if not df_holdings.empty:
                latest = df_holdings.iloc[0]
                data['north_fund'] = {
                    '最新北向持股数量': latest.get('HOLD_SHARES', 0),
                    '最新北向持股比例': latest.get('TOTAL_SHARES_RATIO', 0),
                    '最新北向持股市值': latest.get('HOLD_MARKET_CAP', 0),
                    '统计日期': latest.get('TRADE_DATE', '').strftime('%Y-%m-%d') if pd.notna(latest.get('TRADE_DATE', '')) else ''
                }
                
                # 北向资金趋势分析
                if len(df_holdings) >= 2:
                    change_quarter = (df_holdings.iloc[0]['HOLD_SHARES'] - df_holdings.iloc[1]['HOLD_SHARES']) / df_holdings.iloc[1]['HOLD_SHARES'] * 100
                    data['north_fund_trends'] = {
                        '近一季度持股变化': round(change_quarter, 2),
                        '北向资金趋势': '增持' if change_quarter > 0 else '减持' if change_quarter < 0 else '稳定'
                    }
                
                # 北向资金历史数据（所有可用数据）
                north_fund_history = []
                for _, row in df_holdings.iterrows():
                    north_fund_history.append({
                        '统计日期': row.get('TRADE_DATE', '').strftime('%Y-%m-%d') if pd.notna(row.get('TRADE_DATE', '')) else '',
                        '持股数量': row.get('HOLD_SHARES', 0),
                        '持股比例': row.get('TOTAL_SHARES_RATIO', 0),
                        '持股市值': row.get('HOLD_MARKET_CAP', 0)
                    })
                data['north_fund_history'] = north_fund_history
        
        # 处理 north_fund.csv 数据（机构明细）
        if 'fund' in north_fund_df:
            df_fund = north_fund_df['fund']
            if not df_fund.empty:
                # 计算机构持仓汇总
                total_hold_shares = df_fund['HOLD_SHARES'].sum()
                total_hold_market_cap = df_fund['HOLD_MARKET_CAP'].sum()
                
                # 提取前十大北向机构
                top_10_institutions = df_fund.nlargest(10, 'HOLD_SHARES')
                institution_details = []
                for _, row in top_10_institutions.iterrows():
                    institution_details.append({
                        '机构名称': row.get('HOLD_ORG_NAME', ''),
                        '持股数量': row.get('HOLD_SHARES', 0),
                        '持股市值': row.get('HOLD_MARKET_CAP', 0),
                        '持股比例': row.get('TOTAL_SHARES_RATIO', 0),
                        '增减幅度': row.get('ADD_SHARES_AMP', 0)
                    })
                
                data['north_fund_institutions'] = {
                    '总机构数': len(df_fund),
                    '总持股数量': total_hold_shares,
                    '总持股市值': total_hold_market_cap,
                    '前十大机构': institution_details
                }
    
    # 5. 计算量化指标
    data['quantitative_indicators'] = calculate_quantitative_indicators(data)
    
    return data

def calculate_quantitative_indicators(data):
    """计算量化分析指标"""
    indicators = {}
    
    # 1. 股权集中度指标 (HHI指数)
    if 'main_shareholders' in data and len(data['main_shareholders']) > 0:
        hhi = sum(float(h['持股比例']) ** 2 for h in data['main_shareholders'])
        indicators['HHI指数'] = round(hhi, 2)
        indicators['股权集中度评级'] = '高度集中' if hhi > 2500 else '中度集中' if hhi > 1500 else '分散'
    
    # 2. 机构持仓比例
    if 'institutional_stats' in data and 'concentration' in data:
        inst_total = data['institutional_stats'].get('机构持仓总市值', 0)
        # 估算机构占总股本比例（简化计算）
        indicators['机构参与度'] = '高' if len(data.get('institutional_holders', [])) > 50 else '中' if len(data.get('institutional_holders', [])) > 20 else '低'
    
    # 3. 筹码集中度指标
    if 'shareholder_num' in data:
        holder_num = data['shareholder_num'].get('最新股东户数', 0)
        avg_shares = data['shareholder_num'].get('最新户均持股', 0)
        
        if holder_num > 0:
            indicators['筹码集中度评分'] = '高' if holder_num < 50000 else '中' if holder_num < 150000 else '低'
            indicators['散户化程度'] = '高' if holder_num > 200000 else '中' if holder_num > 100000 else '低'
    
    # 4. 筹码结构稳定性（基于股东户数变化）
    if 'shareholder_trends' in data:
        change_ratio = abs(data['shareholder_trends'].get('近一季度股东户数变化', 0))
        indicators['筹码结构稳定性'] = '稳定' if change_ratio < 5 else '较稳定' if change_ratio < 15 else '不稳定'
    
    # 5. 综合评分
    score = 0
    if '股权集中度评级' in indicators:
        score += 30 if indicators['股权集中度评级'] == '中度集中' else 20 if indicators['股权集中度评级'] == '高度集中' else 25
    if '筹码集中度评分' in indicators:
        score += 30 if indicators['筹码集中度评分'] == '高' else 20 if indicators['筹码集中度评分'] == '中' else 10
    if '筹码结构稳定性' in indicators:
        score += 20 if indicators['筹码结构稳定性'] == '稳定' else 15 if indicators['筹码结构稳定性'] == '较稳定' else 10
    if '机构参与度' in indicators:
        score += 20 if indicators['机构参与度'] == '高' else 15 if indicators['机构参与度'] == '中' else 10
    
    indicators['股东结构综合评分'] = score
    indicators['投资吸引力评级'] = 'A' if score >= 80 else 'B' if score >= 60 else 'C' if score >= 40 else 'D'
    
    return indicators

def build_comprehensive_prompt(ticker, data):
    """构建全面的AI分析提示词"""
    prompt = f"""你是一位专业的量化投资分析师，擅长从股东结构角度进行深度分析。请基于以下全面的股东结构数据，进行专业的量化分析：

=== 股票基本信息 ===
股票代码: {ticker}
"""
    
    # 公司基本信息
    if 'company_basic' in data:
        prompt += "\n【公司基本信息】\n"
        for key, value in data['company_basic'].items():
            if value:
                prompt += f"{key}: {value}\n"
    
    # 规模比较信息
    if 'scale_comparison' in data:
        prompt += "\n【行业规模比较】\n"
        scale = data['scale_comparison']
        prompt += f"总市值: {scale['总市值']:,.2f} 元\n"
        prompt += f"总市值排名: {scale['总市值排名']}\n"
        prompt += f"流通市值: {scale['流通市值']:,.2f} 亿元\n"
        prompt += f"流通市值排名: {scale['流通市值排名']}\n"
        prompt += f"营业收入: {scale['营业收入']:,.2f} 元\n"
        prompt += f"营业收入排名: {scale['营业收入排名']}\n"
        prompt += f"净利润: {scale['净利润']:,.2f} 元\n"
        prompt += f"净利润排名: {scale['净利润排名']}\n"
    
    # 股权集中度分析
    if 'concentration' in data:
        prompt += "\n【股权集中度分析】\n"
        for key, value in data['concentration'].items():
            prompt += f"{key}: {value}\n"
    
    # 大股东结构
    if 'main_shareholders' in data:
        prompt += "\n【前十大股东明细】\n"
        for i, holder in enumerate(data['main_shareholders'], 1):
            prompt += f"\n第{i}大股东:\n"
            prompt += f"  股东名称: {holder['股东名称']}\n"
            prompt += f"  持股数量: {holder['持股数量']:,.0f}股\n"
            prompt += f"  持股比例: {holder['持股比例']:.2f}%\n"
            prompt += f"  股本性质: {holder['股本性质']}\n"
    
    # 机构持仓统计
    if 'institutional_stats' in data:
        prompt += "\n【机构持仓统计】\n"
        stats = data['institutional_stats']
        # 提取统计日期（使用北向资金的最新日期作为参考）
        stat_date = ''
        if 'north_fund' in data and '统计日期' in data['north_fund']:
            stat_date = data['north_fund']['统计日期']
        elif 'shareholder_num' in data and '统计日期' in data['shareholder_num']:
            stat_date = data['shareholder_num']['统计日期']
        if stat_date:
            prompt += f"统计日期: {stat_date}\n"
        prompt += f"机构数量: {stats['机构数量']}\n"
        prompt += f"机构持仓总市值: {stats['机构持仓总市值']:,.2f}元\n"
        prompt += f"机构平均持仓市值: {stats['机构平均持仓市值']:,.2f}元\n"
        if stats.get('机构类型分布'):
            prompt += "机构类型分布:\n"
            for org_type, count in stats['机构类型分布'].items():
                # 尝试获取机构类型名称，如类型名称缺失，根据数量推测
                if str(org_type).isdigit():
                    if count > 1000:
                        type_name = "基金"
                    elif count > 100:
                        type_name = "券商"
                    else:
                        type_name = "其他机构"
                    prompt += f"  类型{org_type}({type_name}): {count}家\n"
                else:
                    prompt += f"  {org_type}: {count}家\n"
    
    if 'institutional_holders' in data and data['institutional_holders']:
        prompt += "\n【前20大机构持仓明细】\n"
        for i, inst in enumerate(data['institutional_holders'][:10], 1):
            prompt += f"\n第{i}大机构:\n"
            prompt += f"  机构名称: {inst['机构名称']}\n"
            prompt += f"  持股数量: {inst['持股数量']:,.0f}股\n"
            prompt += f"  持仓市值: {inst['持仓市值']:,.2f}元\n"
            prompt += f"  占总股本: {inst['占总股本比例']:.4f}%\n"
            prompt += f"  占流通股: {inst['占流通股比例']:.4f}%\n"
            if inst.get('净值占比'):
                prompt += f"  基金净值占比: {inst['净值占比']}%\n"
    
    # 股东户数分析
    if 'shareholder_num' in data:
        prompt += "\n【股东户数分析（筹码集中度）】\n"
        num_data = data['shareholder_num']
        prompt += f"最新股东户数: {num_data['最新股东户数']:,.0f}户\n"
        prompt += f"最新户均持股: {num_data['最新户均持股']:,.0f}股\n"
        prompt += f"持股集中度: {num_data['持股集中度']}\n"
        prompt += f"统计日期: {num_data['统计日期']}\n"
    
    # 趋势分析
    if 'shareholder_trends' in data:
        prompt += "\n【股东户数趋势分析】\n"
        trends = data['shareholder_trends']
        # 修正表述，使其更准确
        prompt += f"最新股东户数变化: {trends['近一季度股东户数变化']:.2f}%（相对最近统计周期）\n"
        prompt += f"最近两期股东户数累计变化: {trends['近二季度股东户数变化']:.2f}%\n"
        prompt += f"最近四期股东户数累计变化: {trends['近四季度股东户数变化']:.2f}%\n"
        prompt += f"股东户数趋势: {trends['股东户数趋势']}\n"
        prompt += f"户均持股趋势: {trends['户均持股趋势']}\n"
    
    # 历史数据
    if 'historical_data' in data:
        prompt += "\n【历史股东户数数据（最近8个季度）】\n"
        for record in data['historical_data']:
            prompt += f"{record['统计日期']}: 户数{record['股东户数']:,.0f}, 户均{record['户均持股']:,.0f}股, 变动{record['户数变动比例']:.2f}%, {record['持股集中度']}\n"
    
    # 北向资金分析
    if 'north_fund' in data:
        prompt += "\n【北向资金分析】\n"
        north_fund = data['north_fund']
        prompt += f"最新北向持股数量: {north_fund['最新北向持股数量']:,.0f}股\n"
        prompt += f"最新北向持股比例: {north_fund['最新北向持股比例']:.4f}%\n"
        prompt += f"最新北向持股市值: {north_fund['最新北向持股市值']:,.2f}元\n"
        prompt += f"统计日期: {north_fund['统计日期']}\n"
    
    if 'north_fund_trends' in data:
        prompt += "\n【北向资金趋势】\n"
        trends = data['north_fund_trends']
        if '近一季度持股变化' in trends:
            prompt += f"近一季度持股变化: {trends['近一季度持股变化']:.2f}%\n"
        else:
            prompt += f"近30天持股变化: {trends['近30天持股变化']:.2f}%\n"
            prompt += f"近90天持股变化: {trends['近90天持股变化']:.2f}%\n"
            prompt += f"近180天持股变化: {trends['近180天持股变化']:.2f}%\n"
        prompt += f"北向资金趋势: {trends['北向资金趋势']}\n"
    
    if 'north_fund_history' in data:
        prompt += "\n【北向资金历史数据】\n"
        for record in data['north_fund_history'][:10]:  # 只显示最近10条
            prompt += f"{record['统计日期']}: 持股{record['持股数量']:,.0f}股, 比例{record['持股比例']:.4f}%, 市值{record['持股市值']:,.2f}元\n"

    if 'north_fund_institutions' in data:
        institutions = data['north_fund_institutions']
        prompt += "\n【北向资金机构明细】\n"
        # 提取统计日期
        stat_date = ''
        if 'north_fund' in data and '统计日期' in data['north_fund']:
            stat_date = data['north_fund']['统计日期']
        if stat_date:
            prompt += f"统计日期: {stat_date}\n"
        prompt += f"总机构数: {institutions['总机构数']}\n"
        prompt += f"总持股数量: {institutions['总持股数量']:,.0f}股\n"
        prompt += f"总持股市值: {institutions['总持股市值']:,.2f}元\n"
        prompt += "\n前十大北向机构:\n"
        for i, inst in enumerate(institutions['前十大机构'], 1):
            prompt += f"{i}. {inst['机构名称']}: 持股{inst['持股数量']:,.0f}股, 市值{inst['持股市值']:,.2f}元, 比例{inst['持股比例']:.4f}%, 增减{inst['增减幅度']:.2f}%\n"

    # 量化指标
    if 'quantitative_indicators' in data:
        prompt += "\n【量化分析指标】\n"
        indicators = data['quantitative_indicators']
        for key, value in indicators.items():
            prompt += f"{key}: {value}\n"
    
    # 分析要求
    prompt += """
=== 量化分析要求 ===
请基于以上全面的股东结构数据，从专业量化投资角度进行深度分析：

【1. 股权结构分析】
- 分析股权集中度（HHI指数）及控制权结构
- 评估大股东背景、稳定性及减持风险
- 分析实际控制人影响力

【2. 机构持仓分析】
- 评估机构参与度及持仓稳定性
- 分析头部机构持仓特征（如公募基金、社保基金等）
- 评估机构增减持趋势及信号意义

【3. 筹码集中度分析】
- 分析股东户数变化趋势及筹码集中/分散程度
- 评估户均持股变化及散户化程度
- 判断当前筹码分布状态（集中/分散/均衡）

【4. 量化指标评估】
- 基于HHI指数评估股权集中度风险
- 基于股东户数趋势判断主力动向
- 综合评分及投资吸引力评级解读

【5. 风险评估】
- 大股东减持风险
- 股权质押风险（如有数据）
- 筹码过度集中或分散的风险

【6. 北向资金分析】
- 分析北向资金持股变化趋势及对股价的影响
- 评估北向资金持股比例的合理性
- 分析北向资金流入流出与市场情绪的关系
- 判断北向资金对股票走势的指示意义

【7. 股东结构信号评估】
- 仅基于当前的股东筹码数据，判断该信号对股价是偏多、偏空还是中性
- 指出最关键的1个正面信号和1个风险信号

请提供数据驱动的专业分析，给出具体的量化结论和投资建议。"""
    
    return prompt

def get_ai_analysis(prompt):
    """获取本地Ollama AI分析结果"""
    try:
        import ollama
        
        model = AI_CONFIG['model']
        temperature = AI_CONFIG['temperature']
        max_tokens = AI_CONFIG['max_tokens']
        
        print(f"正在请求本地Ollama AI ({model})...")
        client = ollama.Client(host=AI_CONFIG['base_url'])
        
        response = client.chat(
            model=model,
            messages=[
                {"role": "system", "content": "你是一位专业的量化投资分析师，擅长从股东结构角度进行深度量化分析。"},
                {"role": "user", "content": prompt}
            ],
            options={
                "temperature": temperature,
                "max_tokens": max_tokens
            }
        )
        
        return response['message']['content']
    except Exception as e:
        print(f"调用本地Ollama AI时出错: {str(e)}")
        return "无法获取AI分析，请检查Ollama服务是否正常运行。"

def save_analysis_result(ticker, analysis_content, data):
    """保存分析结果"""
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d')
    filename = f"{ticker}_shareholder_structure_analysis_{timestamp}.md"
    file_path = os.path.join(stock_dir, filename)
    
    # 构建markdown内容
    md_content = f"""# {ticker} 股东结构深度分析报告

## 分析时间
{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## AI深度分析结果
{analysis_content}

---
*报告由 analyze_shareholder_structure.py 自动生成*
"""
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    print(f"分析报告已保存到: {file_path}")
    return file_path

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="全面分析股票股东结构数据")
    parser.add_argument('--ticker', required=True, help="股票代码，例如：300433.SZ")
    args = parser.parse_args()
    
    ticker = args.ticker
    print(f"=" * 60)
    print(f"开始全面分析股票: {ticker}")
    print(f"=" * 60)
    
    # 加载所有数据
    print("\n【1/4】加载公司信息数据...")
    company_info = load_company_info(ticker)
    
    print("\n【2/4】加载机构持股数据...")
    shareholder_df = load_shareholder_data(ticker)
    
    print("\n【3/4】加载股东户数数据...")
    shareholder_num_df = load_shareholder_num_data(ticker)
    
    print("\n【4/4】加载北向资金数据...")
    north_fund_df = load_north_fund_data(ticker)
    
    if not company_info:
        print("错误：无法加载公司信息数据")
        return
    
    # 提取全面数据
    print("\n【5/5】提取并计算量化指标...")
    comprehensive_data = extract_comprehensive_data(company_info, shareholder_df, shareholder_num_df, north_fund_df)
    
    if not comprehensive_data:
        print("错误：无法提取股东结构数据")
        return
    
    # 构建提示词
    print("\n构建AI分析提示词...")
    prompt = build_comprehensive_prompt(ticker, comprehensive_data)
    
    # 保存提示词到data/{ticker}/目录
    stock_dir = os.path.join(DATA_DIR, ticker)
    os.makedirs(stock_dir, exist_ok=True)
    
    # 保存为TXT格式，便于人工核对
    prompt_file = os.path.join(stock_dir, f"{ticker}_shareholder_structure_prompt.txt")
    
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"提示词已保存到: {prompt_file}")
    
    # 获取AI分析
    print("\n请求AI深度分析...")
    ai_analysis = get_ai_analysis(prompt)
    
    print("\n" + "=" * 60)
    print("AI分析结果")
    print("=" * 60)
    print(ai_analysis)
    
    # 保存结果
    save_analysis_result(ticker, ai_analysis, comprehensive_data)
    
    print("\n" + "=" * 60)
    print("分析完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
