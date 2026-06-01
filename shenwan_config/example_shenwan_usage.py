"""
申万行业阈值系统使用示例
展示如何将申万行业数据集成到股票分析中
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_shenwan_thresholds


def example_basic_usage():
    """示例1: 基本用法"""
    print("\n" + "="*70)
    print("示例1: 获取不同行业的差异化阈值")
    print("="*70)
    
    manager = get_shenwan_thresholds()
    
    # 列出所有可用行业
    print(f"\n📊 已加载 {len(manager.list_available_industries())} 个行业")
    
    # 获取某个行业的阈值
    test_industry = manager.list_available_industries()[0] if manager.list_available_industries() else None
    
    if test_industry:
        thresholds = manager.get_industry_thresholds(industry_code=test_industry)
        print(f"\n🎯 行业代码: {test_industry}")
        print(f"阈值来源: {thresholds['threshold_source']}")
        print(f"\n市盈率阈值:")
        print(f"  低估线: {thresholds['pe_low']:.1f}")
        print(f"  合理线: {thresholds['pe_medium']:.1f}")
        print(f"  高估线: {thresholds['pe_high']:.1f}")
        print(f"\n市值阈值:")
        print(f"  小盘: <{thresholds['cap_small']:.0f} 亿")
        print(f"  中盘: {thresholds['cap_small']:.0f}-{thresholds['cap_large']:.0f} 亿")
        print(f"  大盘: >{thresholds['cap_large']:.0f} 亿")


def example_compare_to_industry():
    """示例2: 将股票指标与行业对比"""
    print("\n" + "="*70)
    print("示例2: 股票与行业对比")
    print("="*70)
    
    manager = get_shenwan_thresholds()
    
    # 假设我们要分析的股票
    stock_info = {
        '代码': '002409.SZ',
        '名称': '雅克科技',
        '市盈率TTM': 46.15,
        '市净率': 5.43,
        '股息率': 0.65,
        '市值': 424.05,
    }
    
    print(f"\n📈 分析股票: {stock_info['名称']}({stock_info['代码']})")
    print(f"   市盈率TTM: {stock_info['市盈率TTM']}")
    print(f"   市净率: {stock_info['市净率']}")
    print(f"   股息率: {stock_info['股息率']}%")
    print(f"   市值: {stock_info['市值']} 亿")
    
    # 假设有行业信息
    test_industry = manager.list_available_industries()[0] if manager.list_available_industries() else None
    
    if test_industry:
        comparison = manager.compare_to_industry(
            stock_pe=stock_info['市盈率TTM'],
            stock_pb=stock_info['市净率'],
            stock_dividend=stock_info['股息率'],
            industry_code=test_industry
        )
        
        print(f"\n🔍 行业对比 ({comparison['threshold_source']}):")
        print(f"   市盈率: {comparison['pe_status']} ({comparison['pe_vs_industry']})")
        print(f"   市净率: {comparison['pb_status']} ({comparison['pb_vs_industry']})")
        print(f"   股息率: {comparison['dividend_status']} ({comparison['dividend_vs_industry']})")


def example_level1_industry():
    """示例3: 使用一级行业数据"""
    print("\n" + "="*70)
    print("示例3: 使用一级行业数据")
    print("="*70)
    
    manager = get_shenwan_thresholds()
    
    # 测试几个一级行业
    test_industries = ['电子', '食品饮料', '汽车']
    
    for industry_name in test_industries:
        level1_info = manager.get_level1_industry_info(industry_name)
        
        if level1_info:
            thresholds = manager.get_industry_thresholds(industry_name=industry_name)
            
            print(f"\n📊 {industry_name}:")
            print(f"   成分股: {level1_info['成份个数']} 只")
            print(f"   行业平均市盈率: {level1_info['静态市盈率']}")
            print(f"   行业平均市净率: {level1_info['市净率']}")
            print(f"   阈值来源: {thresholds['threshold_source']}")


def example_integration():
    """示例4: 如何集成到实际分析中"""
    print("\n" + "="*70)
    print("示例4: 集成到股票分析流程")
    print("="*70)
    
    manager = get_shenwan_thresholds()
    
    # 模拟分析流程
    def analyze_stock(stock_data, industry_code=None, industry_name=None):
        """模拟股票分析函数"""
        print(f"\n{'─'*50}")
        print(f"分析: {stock_data['名称']}")
        print(f"{'─'*50}")
        
        # 1. 获取行业阈值
        thresholds = manager.get_industry_thresholds(industry_code, industry_name)
        print(f"使用阈值: {thresholds['threshold_source']}")
        
        # 2. 行业对比
        comparison = manager.compare_to_industry(
            stock_pe=stock_data['市盈率TTM'],
            stock_pb=stock_data['市净率'],
            stock_dividend=stock_data['股息率'],
            industry_code=industry_code,
            industry_name=industry_name
        )
        
        # 3. 评分逻辑（使用行业相对值）
        score = 50  # 基准分
        
        if comparison['pe_status'] == '低估':
            score += 15
        elif comparison['pe_status'] == '合理偏低':
            score += 10
        elif comparison['pe_status'] == '高估':
            score -= 10
        
        if comparison['dividend_status'] == '优秀':
            score += 10
        elif comparison['dividend_status'] == '良好':
            score += 5
        
        print(f"\n📈 估值评分: {score}")
        print(f"   市盈率: {comparison['pe_status']}")
        print(f"   市净率: {comparison['pb_status']}")
        print(f"   股息率: {comparison['dividend_status']}")
        
        return score
    
    # 测试几只股票
    test_industry = manager.list_available_industries()[0] if manager.list_available_industries() else None
    
    stocks = [
        {
            '名称': '模拟股票A',
            '市盈率TTM': 30,
            '市净率': 2.0,
            '股息率': 4.0,
        },
        {
            '名称': '模拟股票B',
            '市盈率TTM': 100,
            '市净率': 8.0,
            '股息率': 0.5,
        },
    ]
    
    for stock in stocks:
        analyze_stock(stock, industry_code=test_industry)


if __name__ == "__main__":
    print("="*70)
    print("申万行业阈值系统 - 使用示例")
    print("="*70)
    
    # 运行所有示例
    example_basic_usage()
    example_compare_to_industry()
    example_level1_industry()
    example_integration()
    
    print("\n" + "="*70)
    print("✅ 所有示例运行完成")
    print("="*70)
    print("\n📝 提示:")
    print("1. 使用 get_shenwan_thresholds() 获取管理器实例")
    print("2. 使用 get_industry_thresholds() 获取行业阈值")
    print("3. 使用 compare_to_industry() 进行行业对比")
    print("4. 根据股票所属行业调整阈值，而不是用通用值")
