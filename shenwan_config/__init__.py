"""
阈值配置系统 - 友好的预设配置方案
"""

# 导入根目录的config.py的内容以保持兼容性
import importlib.util
import sys
import os

# 导入根目录的config.py
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
config_path = os.path.join(project_root, 'config.py')
spec = importlib.util.spec_from_file_location('project_config', config_path)
project_config = importlib.util.module_from_spec(spec)
sys.modules['project_config'] = project_config
spec.loader.exec_module(project_config)

# 导出根目录config.py中的所有内容
for key in dir(project_config):
    if not key.startswith('_'):
        globals()[key] = getattr(project_config, key)

from .thresholds_config import (
    LARGE_CAP,
    MID_CAP,
    SMALL_CAP,
    CONSERVATIVE,
    BALANCED,
    AGGRESSIVE,
    get_config_by_market_cap,
    get_config_by_style,
    list_all_configs,
    print_config_guide,
    THRESHOLD_EXPLANATIONS
)

from .shenwan_industry_thresholds import (
    ShenwanIndustryThresholds,
    get_shenwan_thresholds
)

__all__ = [
    # 根目录config.py中的配置
    'STOCK_TICKERS',
    'TRADING_RECORDS',
    'HISTORY_DATE_RANGE',
    'AI_CONFIG',
    'STRATEGY_PROMPTS',
    'PROJECT_ROOT',
    'DATA_DIR',
    'TECHNICAL_INDICATORS',
    'STRATEGY_CONFIG',
    'OPTIMIZATION_CONFIG',
    'WEEKLY_STRATEGY_CONFIG',
    'WEEKLY_OPTIMIZATION_CONFIG',
    # 阈值配置
    'LARGE_CAP',
    'MID_CAP',
    'SMALL_CAP',
    'CONSERVATIVE',
    'BALANCED',
    'AGGRESSIVE',
    'get_config_by_market_cap',
    'get_config_by_style',
    'list_all_configs',
    'print_config_guide',
    'THRESHOLD_EXPLANATIONS',
    'ShenwanIndustryThresholds',
    'get_shenwan_thresholds'
]
