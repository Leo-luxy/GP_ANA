"""
基于申万行业数据的智能阈值系统
使用申万一级、三级行业的平均数据作为阈值基准
"""

import os
import pandas as pd
from typing import Dict, Optional


class ShenwanIndustryThresholds:
    """申万行业阈值管理器"""
    
    def __init__(self, data_dir: str = None):
        """
        初始化阈值管理器
        
        Args:
            data_dir: 申万行业数据目录，默认使用 data/shenwan_industry
        """
        if data_dir is None:
            # 默认使用项目目录下的申万行业数据
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            self.data_dir = os.path.join(project_root, 'data', 'shenwan_industry')
        else:
            self.data_dir = data_dir
        
        self.level1_data = None
        self.level3_stocks = {}
        self.industry_averages = {}
        
        # 尝试加载数据
        self._load_data()
    
    def _load_data(self):
        """加载申万行业数据"""
        # 加载一级行业数据
        level1_file = os.path.join(self.data_dir, 'shenwan_industry_level1.csv')
        if os.path.exists(level1_file):
            self.level1_data = pd.read_csv(level1_file)
            print(f"✅ 加载申万一级行业数据成功: {len(self.level1_data)} 个行业")
        
        # 扫描三级行业股票数据
        for filename in os.listdir(self.data_dir):
            if filename.startswith('shenwan_industry_level3_') and filename.endswith('_stocks.csv'):
                industry_code = filename.replace('shenwan_industry_level3_', '').replace('_stocks.csv', '')
                file_path = os.path.join(self.data_dir, filename)
                
                try:
                    stocks_df = pd.read_csv(file_path)
                    self.level3_stocks[industry_code] = stocks_df
                    
                    # 预计算行业平均
                    self._calculate_industry_average(industry_code, stocks_df)
                    
                except Exception as e:
                    print(f"⚠️  加载 {filename} 失败: {e}")
        
        print(f"✅ 加载申万三级行业股票数据成功: {len(self.level3_stocks)} 个行业")
    
    def _calculate_industry_average(self, industry_code: str, stocks_df: pd.DataFrame):
        """
        计算行业平均指标
        
        Args:
            industry_code: 行业代码
            stocks_df: 股票数据
        """
        # 只计算有值的数据
        valid_df = stocks_df.dropna(subset=['市盈率ttm', '市净率', '市值'])
        
        if len(valid_df) == 0:
            return
        
        # 计算平均指标
        avg_data = {
            '行业代码': industry_code,
            '市盈率TTM_平均': valid_df['市盈率ttm'].mean(),
            '市盈率TTM_中位数': valid_df['市盈率ttm'].median(),
            '市盈率TTM_25分位': valid_df['市盈率ttm'].quantile(0.25),
            '市盈率TTM_75分位': valid_df['市盈率ttm'].quantile(0.75),
            '市净率_平均': valid_df['市净率'].mean(),
            '市净率_中位数': valid_df['市净率'].median(),
            '市净率_25分位': valid_df['市净率'].quantile(0.25),
            '市净率_75分位': valid_df['市净率'].quantile(0.75),
            '市值_平均': valid_df['市值'].mean(),
            '市值_中位数': valid_df['市值'].median(),
            '股息率_平均': valid_df['股息率'].mean() if '股息率' in valid_df.columns else None,
            '成分股数量': len(valid_df),
        }
        
        # 计算增长率（如果有数据）
        if '归母净利润同比增长(09-30)' in valid_df.columns:
            avg_data['净利润增长率_平均'] = valid_df['归母净利润同比增长(09-30)'].mean()
            avg_data['净利润增长率_中位数'] = valid_df['归母净利润同比增长(09-30)'].median()
        
        if '营业收入同比增长(09-30)' in valid_df.columns:
            avg_data['营收增长率_平均'] = valid_df['营业收入同比增长(09-30)'].mean()
            avg_data['营收增长率_中位数'] = valid_df['营业收入同比增长(09-30)'].median()
        
        self.industry_averages[industry_code] = avg_data
    
    def get_level1_industry_info(self, industry_name: str) -> Optional[Dict]:
        """
        获取一级行业信息
        
        Args:
            industry_name: 行业名称（如"电子"、"食品饮料"）
        
        Returns:
            行业信息字典
        """
        if self.level1_data is None:
            return None
        
        # 查找匹配的行业
        matches = self.level1_data[self.level1_data['行业名称'].str.contains(industry_name, na=False)]
        
        if len(matches) > 0:
            return matches.iloc[0].to_dict()
        
        return None
    
    def get_industry_thresholds(self, industry_code: str = None, industry_name: str = None) -> Optional[Dict]:
        """
        获取行业差异化的阈值
        
        Args:
            industry_code: 行业代码（如"850813.SI"）
            industry_name: 行业名称（如"电子"）
        
        Returns:
            行业阈值字典
        """
        # 1. 优先使用三级行业数据
        if industry_code and industry_code in self.industry_averages:
            return self._build_thresholds_from_average(self.industry_averages[industry_code])
        
        # 2. 其次使用一级行业数据
        if industry_name and self.level1_data is not None:
            level1_info = self.get_level1_industry_info(industry_name)
            if level1_info:
                return self._build_thresholds_from_level1(level1_info)
        
        # 3. 如果都没有，返回默认阈值
        return self._get_default_thresholds()
    
    def _build_thresholds_from_average(self, avg_data: Dict) -> Dict:
        """
        从行业平均数据构建阈值
        
        Args:
            avg_data: 行业平均数据
        
        Returns:
            阈值字典
        """
        return {
            'threshold_source': f"申万三级行业({avg_data['行业代码']})",
            'base_data': avg_data,
            
            # 市盈率阈值（使用行业分位）
            'pe_low': avg_data.get('市盈率TTM_25分位', 20),
            'pe_medium': avg_data.get('市盈率TTM_中位数', 30),
            'pe_high': avg_data.get('市盈率TTM_75分位', 50),
            
            # 市净率阈值
            'pb_low': avg_data.get('市净率_25分位', 1.5),
            'pb_medium': avg_data.get('市净率_中位数', 2.5),
            'pb_high': avg_data.get('市净率_75分位', 4.0),
            
            # 股息率阈值
            'dividend_high': avg_data.get('股息率_平均', 2.0) * 1.2 if avg_data.get('股息率_平均') else 3.0,
            'dividend_medium': avg_data.get('股息率_平均', 2.0),
            'dividend_low': avg_data.get('股息率_平均', 2.0) * 0.8 if avg_data.get('股息率_平均') else 1.0,
            
            # 市值阈值（按行业调整）
            'cap_large': avg_data.get('市值_中位数', 100) * 2.0,
            'cap_medium': avg_data.get('市值_中位数', 100),
            'cap_small': avg_data.get('市值_中位数', 100) * 0.5,
            
            # 增长率阈值
            'growth_strong': avg_data.get('净利润增长率_平均', 20) * 1.5 if avg_data.get('净利润增长率_平均') else 30,
            'growth_medium': avg_data.get('净利润增长率_平均', 20) if avg_data.get('净利润增长率_平均') else 15,
            'growth_low': avg_data.get('净利润增长率_平均', 20) * 0.5 if avg_data.get('净利润增长率_平均') else 5,
        }
    
    def _build_thresholds_from_level1(self, level1_info: Dict) -> Dict:
        """
        从一级行业数据构建阈值
        
        Args:
            level1_info: 一级行业信息
        
        Returns:
            阈值字典
        """
        return {
            'threshold_source': f"申万一级行业({level1_info['行业名称']})",
            'base_data': level1_info,
            
            # 使用一级行业静态市盈率作为基准
            'pe_low': level1_info.get('静态市盈率', 30) * 0.6,
            'pe_medium': level1_info.get('静态市盈率', 30),
            'pe_high': level1_info.get('静态市盈率', 30) * 1.5,
            
            # 市净率
            'pb_low': level1_info.get('市净率', 2.5) * 0.7,
            'pb_medium': level1_info.get('市净率', 2.5),
            'pb_high': level1_info.get('市净率', 2.5) * 1.5,
            
            # 股息率
            'dividend_high': level1_info.get('静态股息率', 2.0) * 1.5,
            'dividend_medium': level1_info.get('静态股息率', 2.0),
            'dividend_low': level1_info.get('静态股息率', 2.0) * 0.7,
            
            # 市值（一级行业没有，用默认）
            'cap_large': 500,
            'cap_medium': 100,
            'cap_small': 30,
            
            # 增长率（默认）
            'growth_strong': 30,
            'growth_medium': 15,
            'growth_low': 5,
        }
    
    def _get_default_thresholds(self) -> Dict:
        """获取默认阈值（当没有行业数据时使用）"""
        return {
            'threshold_source': '默认通用阈值',
            'base_data': None,
            
            # 市盈率
            'pe_low': 20,
            'pe_medium': 30,
            'pe_high': 50,
            
            # 市净率
            'pb_low': 1.5,
            'pb_medium': 2.5,
            'pb_high': 4.0,
            
            # 股息率
            'dividend_high': 3.0,
            'dividend_medium': 2.0,
            'dividend_low': 1.0,
            
            # 市值
            'cap_large': 500,
            'cap_medium': 100,
            'cap_small': 30,
            
            # 增长率
            'growth_strong': 30,
            'growth_medium': 15,
            'growth_low': 5,
        }
    
    def compare_to_industry(self, stock_pe: float, stock_pb: float, 
                          stock_dividend: float, industry_code: str = None, 
                          industry_name: str = None) -> Dict:
        """
        将股票指标与行业平均对比
        
        Args:
            stock_pe: 股票市盈率TTM
            stock_pb: 股票市净率
            stock_dividend: 股票股息率
            industry_code: 行业代码
            industry_name: 行业名称
        
        Returns:
            对比结果字典
        """
        thresholds = self.get_industry_thresholds(industry_code, industry_name)
        
        result = {
            'threshold_source': thresholds['threshold_source'],
            
            # 市盈率对比
            'pe_status': self._get_status(stock_pe, thresholds['pe_low'], 
                                         thresholds['pe_medium'], thresholds['pe_high']),
            'pe_vs_industry': '低于行业' if stock_pe and thresholds['pe_medium'] and stock_pe < thresholds['pe_medium'] else '高于行业',
            
            # 市净率对比
            'pb_status': self._get_status(stock_pb, thresholds['pb_low'], 
                                         thresholds['pb_medium'], thresholds['pb_high']),
            'pb_vs_industry': '低于行业' if stock_pb and thresholds['pb_medium'] and stock_pb < thresholds['pb_medium'] else '高于行业',
            
            # 股息率对比
            'dividend_status': self._get_status_reverse(stock_dividend, thresholds['dividend_low'], 
                                                      thresholds['dividend_medium'], thresholds['dividend_high']),
            'dividend_vs_industry': '低于行业' if stock_dividend and thresholds['dividend_medium'] and stock_dividend < thresholds['dividend_medium'] else '高于行业',
        }
        
        return result
    
    def _get_status(self, value: float, low: float, medium: float, high: float) -> str:
        """获取指标状态（越低越好）"""
        if value is None:
            return '未知'
        if value < low:
            return '低估'
        elif value < medium:
            return '合理偏低'
        elif value < high:
            return '合理'
        else:
            return '高估'
    
    def _get_status_reverse(self, value: float, low: float, medium: float, high: float) -> str:
        """获取指标状态（越高越好）"""
        if value is None:
            return '未知'
        if value > high:
            return '优秀'
        elif value > medium:
            return '良好'
        elif value > low:
            return '一般'
        else:
            return '偏低'
    
    def list_available_industries(self) -> list:
        """列出所有可用的三级行业"""
        return list(self.industry_averages.keys())
    
    def print_industry_info(self, industry_code: str):
        """打印指定行业的信息"""
        if industry_code in self.industry_averages:
            avg_data = self.industry_averages[industry_code]
            print(f"\n{'='*60}")
            print(f"行业代码: {industry_code}")
            print(f"成分股数量: {avg_data['成分股数量']}")
            print(f"\n平均指标:")
            print(f"  市盈率TTM: {avg_data.get('市盈率TTM_平均', 'N/A'):.2f} (中位数: {avg_data.get('市盈率TTM_中位数', 'N/A'):.2f})")
            print(f"  市净率: {avg_data.get('市净率_平均', 'N/A'):.2f} (中位数: {avg_data.get('市净率_中位数', 'N/A'):.2f})")
            print(f"  市值: {avg_data.get('市值_平均', 'N/A'):.2f} 亿元 (中位数: {avg_data.get('市值_中位数', 'N/A'):.2f})")
            print(f"{'='*60}")
        else:
            print(f"未找到行业: {industry_code}")


# 全局实例
_instance = None

def get_shenwan_thresholds() -> ShenwanIndustryThresholds:
    """获取申万阈值管理器单例"""
    global _instance
    if _instance is None:
        _instance = ShenwanIndustryThresholds()
    return _instance


if __name__ == "__main__":
    print("=" * 60)
    print("申万行业阈值系统 - 测试")
    print("=" * 60)
    
    manager = get_shenwan_thresholds()
    
    # 测试获取行业阈值
    print(f"\n📊 可用三级行业数量: {len(manager.list_available_industries())}")
    
    # 测试某个行业
    if manager.list_available_industries():
        test_industry = manager.list_available_industries()[0]
        print(f"\n🎯 测试行业: {test_industry}")
        
        thresholds = manager.get_industry_thresholds(industry_code=test_industry)
        print(f"阈值来源: {thresholds['threshold_source']}")
        print(f"市盈率阈值: 低={thresholds['pe_low']:.1f}, 中={thresholds['pe_medium']:.1f}, 高={thresholds['pe_high']:.1f}")
        
        # 测试对比
        test_pe = 40
        test_pb = 3.0
        test_dividend = 2.5
        print(f"\n🔍 假设股票指标: PE={test_pe}, PB={test_pb}, 股息率={test_dividend}%")
        
        comparison = manager.compare_to_industry(test_pe, test_pb, test_dividend, industry_code=test_industry)
        print(f"对比结果: {comparison}")
