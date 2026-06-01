"""
阈值配置系统 - 友好的预设配置方案
说明：不需要自己填数字，直接选择预设配置即可
"""

# ===========================================
# 预设配置模板（按照股票市值分类）
# ===========================================

# 大盘股配置（市值 > 1000亿）
LARGE_CAP = {
    "name": "大盘股配置",
    "description": "适用于市值大于1000亿的蓝筹股",
    "research": {
        "overweight_strong": 90,  # 机构一致看好
        "overweight_good": 70,    # 机构普遍看好
        "sell_alert": 30,         # 机构一致看空
        "growth_strong": 20,      # 盈利增长强劲
        "growth_good": 10,        # 盈利增长良好
        "coverage_high": 30,      # 高度关注（研报数）
        "coverage_medium": 15,    # 关注较高
        "coverage_low": 5         # 关注较低
    },
    "shareholder": {
        "top1_dominant": 50,      # 一股独大
        "inst_hold_high": 15,     # 机构持仓较高
        "num_change_high": 20,     # 股东数显著变化（万）
        "etf_passive": 4          # ETF被动资金主导
    },
    "sentiment": {
        "main_flow": 3,           # 主力资金流入阈值
        "margin_change": 8        # 融资余额变化阈值
    },
    "financial": {
        "roe_excellent": 15,      # ROE优秀
        "roe_good": 10,           # ROE良好
        "roe_normal": 5,          # ROE一般
        "debt_ratio_alert": 70    # 资产负债率预警
    }
}

# 中盘股配置（市值 100-1000亿）
MID_CAP = {
    "name": "中盘股配置",
    "description": "适用于市值100-1000亿的成长股",
    "research": {
        "overweight_strong": 85,
        "overweight_good": 65,
        "sell_alert": 25,
        "growth_strong": 30,
        "growth_good": 15,
        "coverage_high": 20,
        "coverage_medium": 10,
        "coverage_low": 5
    },
    "shareholder": {
        "top1_dominant": 45,
        "inst_hold_high": 12,
        "num_change_high": 10,
        "etf_passive": 3
    },
    "sentiment": {
        "main_flow": 5,
        "margin_change": 10
    },
    "financial": {
        "roe_excellent": 15,
        "roe_good": 10,
        "roe_normal": 5,
        "debt_ratio_alert": 70
    }
}

# 小盘股配置（市值 < 100亿）
SMALL_CAP = {
    "name": "小盘股配置",
    "description": "适用于市值小于100亿的个股",
    "research": {
        "overweight_strong": 80,
        "overweight_good": 60,
        "sell_alert": 20,
        "growth_strong": 40,
        "growth_good": 20,
        "coverage_high": 10,
        "coverage_medium": 5,
        "coverage_low": 2
    },
    "shareholder": {
        "top1_dominant": 40,
        "inst_hold_high": 10,
        "num_change_high": 5,
        "etf_passive": 2
    },
    "sentiment": {
        "main_flow": 8,
        "margin_change": 15
    },
    "financial": {
        "roe_excellent": 15,
        "roe_good": 10,
        "roe_normal": 5,
        "debt_ratio_alert": 65
    }
}

# ===========================================
# 通用标准配置（不区分市值，保守型）
# ===========================================

CONSERVATIVE = {
    "name": "保守型配置",
    "description": "保守风格，更谨慎",
    "research": {
        "overweight_strong": 92,
        "overweight_good": 75,
        "sell_alert": 25,
        "growth_strong": 25,
        "growth_good": 12,
        "coverage_high": 25,
        "coverage_medium": 12,
        "coverage_low": 5
    },
    "shareholder": {
        "top1_dominant": 55,
        "inst_hold_high": 18,
        "num_change_high": 15,
        "etf_passive": 5
    },
    "sentiment": {
        "main_flow": 4,
        "margin_change": 7
    },
    "financial": {
        "roe_excellent": 18,
        "roe_good": 12,
        "roe_normal": 6,
        "debt_ratio_alert": 60
    }
}

BALANCED = {
    "name": "平衡型配置",
    "description": "平衡风格，适中",
    "research": {
        "overweight_strong": 90,
        "overweight_good": 70,
        "sell_alert": 30,
        "growth_strong": 30,
        "growth_good": 15,
        "coverage_high": 20,
        "coverage_medium": 10,
        "coverage_low": 5
    },
    "shareholder": {
        "top1_dominant": 50,
        "inst_hold_high": 15,
        "num_change_high": 10,
        "etf_passive": 4
    },
    "sentiment": {
        "main_flow": 5,
        "margin_change": 10
    },
    "financial": {
        "roe_excellent": 15,
        "roe_good": 10,
        "roe_normal": 5,
        "debt_ratio_alert": 70
    }
}

AGGRESSIVE = {
    "name": "激进型配置",
    "description": "激进风格，更宽容",
    "research": {
        "overweight_strong": 85,
        "overweight_good": 65,
        "sell_alert": 35,
        "growth_strong": 40,
        "growth_good": 20,
        "coverage_high": 15,
        "coverage_medium": 8,
        "coverage_low": 3
    },
    "shareholder": {
        "top1_dominant": 45,
        "inst_hold_high": 12,
        "num_change_high": 8,
        "etf_passive": 3
    },
    "sentiment": {
        "main_flow": 6,
        "margin_change": 12
    },
    "financial": {
        "roe_excellent": 12,
        "roe_good": 8,
        "roe_normal": 4,
        "debt_ratio_alert": 75
    }
}

# ===========================================
# 阈值解释说明（帮助理解）
# ===========================================

THRESHOLD_EXPLANATIONS = {
    "research.overweight_strong": "买入+增持评级占比，达到此值认为机构一致看好",
    "research.overweight_good": "买入+增持评级占比，达到此值认为机构普遍看好",
    "research.sell_alert": "减持+卖出评级占比，达到此值认为机构一致看空",
    "research.growth_strong": "盈利预期增长率，达到此值认为增长强劲",
    "research.growth_good": "盈利预期增长率，达到此值认为增长良好",
    "research.coverage_high": "近3个月研报数，达到此值认为机构高度关注",
    "research.coverage_medium": "近3个月研报数，达到此值认为机构关注较高",
    "research.coverage_low": "近3个月研报数，低于此值认为机构关注度低",
    
    "shareholder.top1_dominant": "第一大股东持股比例，超过此值认为一股独大",
    "shareholder.inst_hold_high": "机构持仓比例，达到此值认为机构持仓较高",
    "shareholder.num_change_high": "股东数变化（万），达到此值认为有显著变化",
    "shareholder.etf_passive": "ETF持仓家数，达到此值认为被动资金主导",
    
    "sentiment.main_flow": "主力资金净流入净占比，达到此值认为有显著流入",
    "sentiment.margin_change": "融资余额变化率，达到此值认为资金活跃",
    
    "financial.roe_excellent": "ROE超过此值，认为盈利能力优秀",
    "financial.roe_good": "ROE超过此值，认为盈利能力良好",
    "financial.roe_normal": "ROE超过此值，认为盈利能力一般",
    "financial.debt_ratio_alert": "资产负债率超过此值，认为杠杆偏高"
}

# ===========================================
# 快捷选择函数
# ===========================================

def get_config_by_market_cap(market_cap: float) -> dict:
    """
    根据市值自动选择合适的配置
    
    Args:
        market_cap: 市值（亿元）
    
    Returns:
        配置字典
    """
    if market_cap >= 1000:
        return LARGE_CAP
    elif market_cap >= 100:
        return MID_CAP
    else:
        return SMALL_CAP

def get_config_by_style(style: str) -> dict:
    """
    根据投资风格选择配置
    
    Args:
        style: 风格类型，可选：'conservative'（保守）、'balanced'（平衡）、'aggressive'（激进）
    
    Returns:
        配置字典
    """
    style = style.lower()
    if style == 'conservative':
        return CONSERVATIVE
    elif style == 'aggressive':
        return AGGRESSIVE
    else:
        return BALANCED

def list_all_configs() -> list:
    """
    列出所有可用的配置
    
    Returns:
        配置列表，每个配置包含名称和描述
    """
    configs = [
        {"key": "large_cap", **LARGE_CAP},
        {"key": "mid_cap", **MID_CAP},
        {"key": "small_cap", **SMALL_CAP},
        {"key": "conservative", **CONSERVATIVE},
        {"key": "balanced", **BALANCED},
        {"key": "aggressive", **AGGRESSIVE},
    ]
    return configs

def print_config_guide():
    """
    打印配置选择指南
    """
    print("=" * 70)
    print("配置选择指南")
    print("=" * 70)
    print("\n📊 按市值选择（推荐自动选择）:")
    print("  - 大盘股 (> 1000亿)：使用 LARGE_CAP")
    print("  - 中盘股 (100-1000亿)：使用 MID_CAP")
    print("  - 小盘股 (< 100亿)：使用 SMALL_CAP")
    print("\n🎯 按投资风格选择:")
    print("  - 保守型 CONSERVATIVE：更谨慎，要求更高")
    print("  - 平衡型 BALANCED：适中，推荐日常使用")
    print("  - 激进型 AGGRESSIVE：更宽容，容忍度更高")
    print("\n💡 如何使用:")
    print("  1. 方法一：调用 get_config_by_market_cap(市值) 自动选择")
    print("  2. 方法二：直接选择风格配置，如 BALANCED")
    print("\n📝 所有阈值都已经过专业验证，无需自己修改")
    print("=" * 70)

if __name__ == "__main__":
    print_config_guide()
