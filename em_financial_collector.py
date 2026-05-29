
# em_financial_collector.py
"""
em_financial_collector.py
功能：从东方财富网抓取三类财务数据（杜邦分析、增长率、主要财务指标）
特点：
1. 支持增量更新，只抓取新数据
2. 按股票代码保存到对应文件夹
3. 自动合并新旧数据，避免重复
4. 支持命令行参数指定股票代码
"""

import requests
import pandas as pd
import os
import sys
import time
from datetime import datetime
from typing import Optional, Dict, Any

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATA_DIR


class EastmoneyFinancialCollector:
    """从东方财富网抓取股票财务数据"""

    def __init__(self, ticker: str):
        """
        初始化抓取器
        :param ticker: 股票代码，例如：300433.SZ
        """
        self.ticker = ticker
        self.code = ticker.split('.')[0]
        self.stock_dir = os.path.join(DATA_DIR, ticker)
        
        # 确保股票目录存在
        os.makedirs(self.stock_dir, exist_ok=True)
        
        # API基础配置
        self.base_url = "https://datacenter.eastmoney.com/securities/api/data"
        self.headers = {
            "Accept": "*/*",
            "Origin": "https://emweb.securities.eastmoney.com",
            "Referer": "https://emweb.securities.eastmoney.com/",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }

    def _make_request(self, url: str, params: Dict[str, Any], max_retries: int = 3) -> list:
        """发送HTTP请求，带重试机制"""
        for attempt in range(max_retries):
            try:
                response = requests.get(url, params=params, headers=self.headers, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                if "result" in data and "data" in data["result"]:
                    return data["result"]["data"]
                elif "data" in data:
                    return data["data"]
                else:
                    print(f"警告：返回的JSON结构不包含预期字段")
                    return []
                    
            except requests.exceptions.RequestException as e:
                print(f"请求出错 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    print(f"请求失败，已达到最大重试次数")
                    return []
            except Exception as e:
                print(f"处理响应时出错: {e}")
                return []
        
        return []

    def _load_existing_data(self, filename: str) -> Optional[pd.DataFrame]:
        """加载已存在的数据文件"""
        file_path = os.path.join(self.stock_dir, filename)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path)
                print(f"  加载已有数据: {len(df)} 条记录")
                return df
            except Exception as e:
                print(f"  加载已有数据时出错: {e}")
                return None
        return None

    def _save_data(self, df: pd.DataFrame, filename: str) -> bool:
        """保存数据到CSV文件"""
        file_path = os.path.join(self.stock_dir, filename)
        try:
            df.to_csv(file_path, index=False, encoding='utf-8-sig')
            print(f"  数据已保存: {file_path} ({len(df)} 条记录)")
            return True
        except Exception as e:
            print(f"  保存数据时出错: {e}")
            return False

    def _merge_data(self, new_df: pd.DataFrame, existing_df: Optional[pd.DataFrame], 
                    date_column: str = 'REPORT_DATE') -> pd.DataFrame:
        """合并新旧数据，避免重复"""
        if existing_df is None or existing_df.empty:
            return new_df
        
        if new_df is None or new_df.empty:
            return existing_df
        
        # 确保日期列格式一致
        if date_column in new_df.columns:
            new_df[date_column] = pd.to_datetime(new_df[date_column])
        if date_column in existing_df.columns:
            existing_df[date_column] = pd.to_datetime(existing_df[date_column])
        
        # 合并数据
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        
        # 根据日期列和可能的类型列去重，保留最新数据
        if date_column in combined.columns:
            # 对于增长率数据，需要同时考虑 REPORT_DATE 和 INTERFACE_TYPE
            if 'INTERFACE_TYPE' in combined.columns:
                combined = combined.drop_duplicates(subset=[date_column, 'INTERFACE_TYPE'], keep='last')
            else:
                combined = combined.drop_duplicates(subset=[date_column], keep='last')
            combined = combined.sort_values(by=date_column, ascending=True)
        
        return combined
    
    def _get_quarter_difference(self, date1: datetime, date2: datetime) -> int:
        """计算两个日期之间的季度差"""
        # 计算两个日期的季度数
        quarter1 = (date1.month - 1) // 3 + 1
        quarter2 = (date2.month - 1) // 3 + 1
        
        # 计算总季度差
        total_quarters = (date2.year - date1.year) * 4 + (quarter2 - quarter1)
        return max(0, total_quarters)
    
    def _get_latest_report_date(self, filename: str) -> Optional[datetime]:
        """获取本地数据文件中的最新报告日期"""
        existing_df = self._load_existing_data(filename)
        if existing_df is not None and not existing_df.empty:
            if 'REPORT_DATE' in existing_df.columns:
                # 转换为日期类型
                existing_df['REPORT_DATE'] = pd.to_datetime(existing_df['REPORT_DATE'])
                # 获取最新日期
                latest_date = existing_df['REPORT_DATE'].max()
                return latest_date
        return None

    def fetch_dupont_data(self) -> Optional[pd.DataFrame]:
        """抓取杜邦分析数据"""
        print(f"\n[{self.ticker}] 抓取杜邦分析数据...")
        
        filename = f"{self.ticker}_dupont_data.csv"
        
        # 检查本地数据文件
        latest_report_date = self._get_latest_report_date(filename)
        current_date = datetime.now()
        
        if latest_report_date:
            # 计算时间差
            quarter_diff = self._get_quarter_difference(latest_report_date, current_date)
            if quarter_diff < 1:
                print(f"  数据为最新，最新报告日期: {latest_report_date.strftime('%Y-%m-%d')}")
                return self._load_existing_data(filename)
            else:
                # 根据时间差决定 ps 值
                ps = min(200, quarter_diff * 4)  # 每个季度最多 4 条记录
                print(f"  数据需要更新，时间差: {quarter_diff} 个季度，设置 ps={ps}")
        else:
            # 文件不存在，设置 ps 为 200
            ps = 200
            print("  本地数据文件不存在，设置 ps=200")
        
        url = f"{self.base_url}/get"
        params = {
            "type": "RPT_F10_FINANCE_DUPONT",
            "sty": "APP_F10_FINANCE_DUPONT",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{self.ticker}")',
            "p": 1,
            "ps": ps,
            "sr": -1,
            "st": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
            "v": str(int(time.time() * 1000))
        }
        
        records = self._make_request(url, params)
        
        if not records:
            print("  未获取到杜邦分析数据")
            return None
        
        df = pd.DataFrame(records)
        
        # 转换日期列
        date_columns = ['REPORT_DATE', 'NOTICE_DATE', 'UPDATE_DATE']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # 加载已有数据并合并
        existing_df = self._load_existing_data(filename)
        merged_df = self._merge_data(df, existing_df, 'REPORT_DATE')
        
        # 保存数据
        self._save_data(merged_df, filename)
        
        return merged_df

    def fetch_growth_ratio_data(self) -> Optional[pd.DataFrame]:
        """抓取增长率数据"""
        print(f"\n[{self.ticker}] 抓取增长率数据...")
        
        filename = f"{self.ticker}_growth_ratio_data.csv"
        
        # 检查本地数据文件
        latest_report_date = self._get_latest_report_date(filename)
        current_date = datetime.now()
        
        if latest_report_date:
            # 计算时间差
            quarter_diff = self._get_quarter_difference(latest_report_date, current_date)
            if quarter_diff < 1:
                print(f"  数据为最新，最新报告日期: {latest_report_date.strftime('%Y-%m-%d')}")
                return self._load_existing_data(filename)
            else:
                # 根据时间差决定 pageSize 值
                pageSize = min(200, quarter_diff * 8)  # 每个季度最多 8 条记录（同比和环比）
                print(f"  数据需要更新，时间差: {quarter_diff} 个季度，设置 pageSize={pageSize}")
        else:
            # 文件不存在，设置 pageSize 为 200
            pageSize = 200
            print("  本地数据文件不存在，设置 pageSize=200")
        
        url = f"{self.base_url}/v1/get"
        params = {
            "reportName": "RPT_F10_FINANCE_GRATIO",
            "columns": "ALL",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{self.ticker}")',
            "sortTypes": "-1,1",
            "sortColumns": "REPORT_DATE,INTERFACE_TYPE",
            "pageNumber": 1,
            "pageSize": pageSize,
            "source": "HSF10",
            "client": "PC",
            "v": str(int(time.time() * 1000))
        }
        
        records = self._make_request(url, params)
        
        if not records:
            print("  未获取到增长率数据")
            return None
        
        df = pd.DataFrame(records)
        
        # 转换日期列
        date_columns = ['REPORT_DATE', 'NOTICE_DATE', 'UPDATE_DATE']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # 加载已有数据并合并
        existing_df = self._load_existing_data(filename)
        merged_df = self._merge_data(df, existing_df, 'REPORT_DATE')
        
        # 保存数据
        self._save_data(merged_df, filename)
        
        return merged_df

    def fetch_main_financial_data(self) -> Optional[pd.DataFrame]:
        """抓取主要财务指标数据"""
        print(f"\n[{self.ticker}] 抓取主要财务指标数据...")
        
        filename = f"{self.ticker}_main_financial_data.csv"
        
        # 检查本地数据文件
        latest_report_date = self._get_latest_report_date(filename)
        current_date = datetime.now()
        
        if latest_report_date:
            # 计算时间差
            quarter_diff = self._get_quarter_difference(latest_report_date, current_date)
            if quarter_diff < 1:
                print(f"  数据为最新，最新报告日期: {latest_report_date.strftime('%Y-%m-%d')}")
                return self._load_existing_data(filename)
            else:
                # 根据时间差决定 ps 值
                ps = min(200, quarter_diff * 4)  # 每个季度最多 4 条记录
                print(f"  数据需要更新，时间差: {quarter_diff} 个季度，设置 ps={ps}")
        else:
            # 文件不存在，设置 ps 为 200
            ps = 200
            print("  本地数据文件不存在，设置 ps=200")
        
        url = f"{self.base_url}/get"
        params = {
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "APP_F10_MAINFINADATA",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{self.ticker}")',
            "p": 1,
            "ps": ps,
            "sr": -1,
            "st": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
            "v": str(int(time.time() * 1000))
        }
        
        records = self._make_request(url, params)
        
        if not records:
            print("  未获取到主要财务指标数据")
            return None
        
        df = pd.DataFrame(records)
        
        # 转换日期列
        date_columns = ['REPORT_DATE', 'NOTICE_DATE', 'UPDATE_DATE']
        for col in date_columns:
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
        
        # 加载已有数据并合并
        existing_df = self._load_existing_data(filename)
        merged_df = self._merge_data(df, existing_df, 'REPORT_DATE')
        
        # 保存数据
        self._save_data(merged_df, filename)
        
        return merged_df

    def fetch_all_data(self) -> Dict[str, Optional[pd.DataFrame]]:
        """抓取所有三类财务数据"""
        print(f"\n{'='*60}")
        print(f"开始从东方财富网抓取 {self.ticker} 的股票财务数据")
        print(f"{'='*60}")
        
        results = {}
        
        # 1. 抓取杜邦分析数据
        try:
            results['dupont'] = self.fetch_dupont_data()
            time.sleep(1)
        except Exception as e:
            print(f"抓取杜邦分析数据时出错: {e}")
            results['dupont'] = None
        
        # 2. 抓取增长率数据
        try:
            results['growth_ratio'] = self.fetch_growth_ratio_data()
            time.sleep(1)
        except Exception as e:
            print(f"抓取增长率数据时出错: {e}")
            results['growth_ratio'] = None
        
        # 3. 抓取主要财务指标数据
        try:
            results['main_financial'] = self.fetch_main_financial_data()
            time.sleep(1)
        except Exception as e:
            print(f"抓取主要财务指标数据时出错: {e}")
            results['main_financial'] = None
        
        # 打印汇总信息
        print(f"\n{'='*60}")
        print(f"{self.ticker} 数据抓取完成汇总：")
        print(f"{'='*60}")
        for data_type, df in results.items():
            if df is not None and not df.empty:
                print(f"  {data_type}: {len(df)} 条记录")
            else:
                print(f"  {data_type}: 抓取失败")
        print(f"{'='*60}")
        
        return results


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='从东方财富网抓取股票财务数据')
    parser.add_argument('--ticker', type=str, required=True, 
                       help='股票代码，例如：300433.SZ')
    parser.add_argument('--type', type=str, choices=['dupont', 'growth', 'main', 'all'],
                       default='all', help='抓取数据类型（默认all）')
    args = parser.parse_args()
    
    collector = EastmoneyFinancialCollector(args.ticker)
    
    if args.type == 'dupont':
        collector.fetch_dupont_data()
    elif args.type == 'growth':
        collector.fetch_growth_ratio_data()
    elif args.type == 'main':
        collector.fetch_main_financial_data()
    else:
        collector.fetch_all_data()
    
    print("\n数据抓取完成！")


if __name__ == "__main__":
    main()
