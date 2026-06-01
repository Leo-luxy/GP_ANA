# Multi Strategy Analyzer - 多策略股票综合分析器

## 📖 概述

`multi_strategy_analyzer.py` 是一个采用 **"技术为主，其他避雷"** 权重架构的股票综合分析系统。它结合了程序化决策引擎与AI大模型分析，支持三种交易模式，为股票投资决策提供专业建议。

---

## 🎯 核心架构理念

### "技术为主，其他避雷"的分层决策逻辑

```
┌─────────────────────────────────────────────────────────────┐
│                    主要决策层（技术面）                         │
│              80%（短期）/ 60%（中期）/ 20%（长期）              │
│         - 趋势判断、超买超卖、支撑阻力、量价配合                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    风险过滤层（其他维度）                       │
│              - 财务估值风险 (PE、PB、PEG、ROE)                │
│              - 情绪/资金流风险 (主力流出、融资风险)             │
│              - 股东结构风险 (股权集中、机构参与)                │
└─────────────────────────────────────────────────────────────┘
```

### 三种交易模式配置

| 模式 | 名称 | 时间框架 | 技术面权重 | 财务权重 | 股东权重 | 情绪权重 |
|------|------|----------|-----------|---------|---------|---------|
| **short** | 短期交易 | <1个月 | 80% | 0% | 0% | 20% |
| **medium** | 中期持仓 | 1-6个月 | 60% | 30% | 10% | 0% |
| **long** | 长期投资 | >6个月 | 20% | 50% | 30% | 0% |

---

## 📁 文件结构

```
multi_strategy_analyzer.py
└── MultiStrategyAnalyzer (class)
    ├── 初始化与配置
    │   ├── __init__()
    │   └── get_trading_mode_config()
    ├── 数据加载
    │   ├── load_all_data()
    │   ├── load_stock_info()
    │   ├── load_trading_records()
    │   └── calculate_position()
    ├── 信号提取（五维度）
    │   ├── extract_technical_signal()        # 技术面
    │   ├── extract_financial_risk()          # 财务面（避雷）
    │   ├── extract_sentiment_signal()        # 情绪/资金流
    │   ├── extract_shareholder_risk()        # 股东结构
    │   ├── extract_research_signal()         # 研报（弱参考）
    │   └── extract_support_resistance()      # 关键价位
    ├── 决策引擎
    │   ├── calculate_programmatic_signal()   # 程序化决策
    │   └── check_risk_filters()              # 风险过滤检查
    ├── 报告生成
    │   ├── generate_analysis_prompt()        # 生成提示词
    │   ├── save_prompt()                     # 保存提示词
    │   ├── get_ai_analysis()                 # 调用AI
    │   └── save_analysis_report()            # 保存报告
    └── 主流程
        └── run_analysis()                    # 完整分析流程
```

---

## 📊 五维度分析详解

### 1. 技术面分析（主要决策依据）

**数据来源**：`{ticker}_technical_trend_analysis.json`

**提取内容**：
- 交易信号 (BUY/HOLD/SELL) + 信心度
- 多时间周期趋势（日/周）
- 指标一致性评分
- 超买/超卖判断
  - RSI > 75 或 CCI > 150 或 BB_pctB > 1.0 → 超买
  - RSI < 25 或 CCI < -150 或 BB_pctB < 0 → 超卖
- 关键技术指标 (MACD、ATR等)
- 关键价位（布林带支撑/阻力、MA20）

### 2. 财务估值分析（风险过滤器）

**数据来源**：`{ticker}_financial_summary.json`

**风险检查项**：
| 指标 | 短期阈值 | 中期阈值 | 长期阈值 |
|------|---------|---------|---------|
| PE(TTM) | >150 | >100 | >80 |
| PB | >10 | >10 | >10 |
| PEG | >2.0 | >2.5 | >2.0 |
| ROE | <8% | <8% | <8% |
| 净利率 | <5% | <5% | <5% |
| 资产负债率 | >80% | >70% | >60% |
| 经营现金流 | 可为负 | 必须为正 | 必须为正 |
| 净利润增长率 | < -20% | < -20% | < -20% |

**利好因素**：
- 营收增长 > 20%
- 净利润增长 > 20%
- ROE > 15%
- PEG < 1.5

### 3. 情绪/资金流分析（辅助验证）

**数据来源**：`{ticker}_sentiment_valuation.json`

**风险检查项**：
- 主力连续流出检测（连续流出天数=0且5日平均净占比< -0.5%）
- 融资余额快速上升（5日变化率>5%）
- 资金流异常（major_anomalies）

### 4. 股东结构分析（避雷机制）

**数据来源**：`{ticker}_shareholder_structure.json`

**风险检查项**：
- 股权高度集中
- 机构参与度低
- 股东人数异常

### 5. 机构研报分析（弱参考）

**数据来源**：`{ticker}_research_report_analysis.json`

- 买入评级占比判断
- 近三月研报数量

---

## 🤖 程序化决策引擎

### 决策逻辑（伪代码）

```python
IF 技术信号 = BUY AND 信心度 >= 0.7 AND 风险等级 = LOW:
    → BUY (信心度 min(tech_conf, 0.8))

ELIF 技术信号 in [BUY, HOLD] AND 短期超买:
    → HOLD (信心度 0.7)

ELIF 技术信号 = SELL OR 风险等级 = HIGH:
    → SELL (信心度 max(tech_conf, 0.6))

ELIF (技术看多 AND 风险 >= 2) OR (技术看空 AND 情绪看多):
    → HOLD (信心度 0.5)

ELSE:
    → 以技术面信号为主
```

### 风险等级判定

| 风险分数 | 等级 |
|---------|------|
| 0 - 1 | LOW |
| 2 - 4 | MEDIUM |
| ≥5 | HIGH |

---

## 💾 数据文件要求

运行分析前需要以下数据文件（存放在 `data/{ticker}/` 目录下）：

### 必需文件

| 文件 | 说明 |
|------|------|
| `{ticker}_technical_trend_analysis.json` | 技术趋势分析数据 |
| `{ticker}_financial_summary.json` | 财务分析数据 |
| `{ticker}_sentiment_valuation.json` | 情绪估值数据 |
| `{ticker}_shareholder_structure.json` | 股东结构数据 |
| `{ticker}_research_report_analysis.json` | 研报分析数据 |
| `{ticker}_company_basic.json` | 公司基本信息 |

### 可选文件

| 文件 | 说明 |
|------|------|
| `{ticker}_valuation.csv` | 估值数据（CSV格式） |

---

## 🚀 使用方法

### 命令行使用

```bash
# 短期交易模式（默认）
python Process/multi_strategy_analyzer.py --ticker 688981.SH --mode short

# 中期持仓模式
python Process/multi_strategy_analyzer.py --ticker 688981.SH --mode medium

# 长期投资模式
python Process/multi_strategy_analyzer.py --ticker 688981.SH --mode long
```

### Python 代码调用

```python
from Process.multi_strategy_analyzer import MultiStrategyAnalyzer

# 创建分析器
analyzer = MultiStrategyAnalyzer(ticker='688981.SH', trading_mode='short')

# 运行分析
result = analyzer.run_analysis(
    ai_config={
        'model': 'qwen3.5:35b',
        'temperature': 0.3,
        'max_tokens': 16000,
        'base_url': 'http://localhost:11434'
    },
    trading_records={
        '688981.SH': [
            {'type': 'buy', 'date': '2024-01-15', 'price': 100.0, 'shares': 100}
        ]
    }
)

print(result)
```

### 配置文件

需要 `config.py` 包含 AI 配置：
```python
# config.py
AI_CONFIG = {
    'model': 'qwen3.5:35b',
    'temperature': 0.3,
    'max_tokens': 16000,
    'base_url': 'http://localhost:11434'
}
```

需要 `trading_records.py` 包含交易记录：
```python
# trading_records.py
TRADING_RECORDS = {
    '688981.SH': [
        {'type': 'buy', 'date': '2024-01-15', 'price': 100.0, 'shares': 100}
    ]
}
```

---

## 📋 输出结果

### 生成文件

| 文件 | 格式 | 说明 |
|------|------|------|
| `{ticker}_{mode}_strategy_prompt_{date}.txt` | TXT | 发送给AI的完整提示词 |
| `{ticker}_{mode}_strategy_analysis_{date}.md` | MD | 最终分析报告（Markdown格式） |

### 报告内容结构

```markdown
# 股票代码综合策略分析报告
## 基本信息
## 权重架构
## 决策原则
## AI分析结果
    ## 主信号
    ## 避雷触发项
    ## 核心逻辑
    ## 具体操作建议
    ## 监控要点
## 数据来源
## 风险提示
```

---

## ⚙️ 关键配置说明

### 模式配置

三种交易模式的风险阈值在 `get_trading_mode_config()` 方法中定义，可根据需求调整：

```python
'medium': {
    'risk_filters': {
        'peg_threshold': 2.5,    # PEG阈值
        'pe_threshold': 100,     # PE阈值
        'debt_ratio': 0.7,       # 资产负债率（小数形式）
        'net_cash_flow': True    # 是否要求正现金流
    }
}
```

### AI配置

在 `config.py` 中设置：
- **model**: 使用的Ollama模型
- **temperature**: 创造性（0.0-1.0），建议0.2-0.4
- **max_tokens**: 最大输出token数
- **base_url**: Ollama服务地址

---

## 📈 决策流程示例（短期交易）

```
1. 输入：688981.SH，mode=short
2. 加载5维度数据
3. 程序化决策
   ├─ 技术信号：BUY，信心度0.65，短期超买
   ├─ 财务风险：PE=195触发，PEG=5.15触发
   ├─ 情绪风险：主力连续流出
   └─ 风险等级：HIGH
4. 决策结果：HOLD，观望
5. AI分析：根据提示词生成详细建议
6. 输出：Markdown报告
```

---

## 🔧 扩展建议

### 添加新模式

在 `get_trading_mode_config()` 中新增配置：

```python
'ultra_short': {
    'name': '超短线',
    'timeframe': '<1周',
    'weights': {
        'technical': 90,
        'sentiment': 10,
        'financial': 0,
        'shareholder': 0,
        'research': 0
    },
    # ...其他配置
}
```

### 自定义风险过滤器

在相关 `extract_*` 方法中添加新的风险检查项。

### 支持更多AI提供商

修改 `get_ai_analysis()` 方法以支持OpenAI、Claude等。

---

## 📝 版本历史

| 版本 | 修改日期 | 说明 |
|------|---------|------|
| 2.0 | 2026-05-11 | 完善五维度分析，增加程序化决策引擎 |
| 1.0 | 2026-05-08 | 基础版本，三种交易模式 |

---

## ⚠️ 风险提示

> **重要声明**：
> 1. 本系统仅供学习和研究使用，不构成任何投资建议
> 2. 股市有风险，投资需谨慎
> 3. 使用前请确保数据的准确性和完整性
> 4. AI分析结果存在不确定性，请结合自身判断决策
