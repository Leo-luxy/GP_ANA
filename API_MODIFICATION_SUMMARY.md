
# API 修改总结 - 多策略分析器集成

## 修改概览

已成功将 `/api/quick_analysis.py` 集成 `/Process/multi_strategy_analyzer.py`，支持三种策略选择。

## 主要修改内容

### 1. API 请求参数增强

**新增参数**：
- `strategy_mode`: 策略模式选择
  - `short`: 短期交易（默认）
  - `medium`: 中期持仓
  - `long`: 长期投资

**示例请求**：
```json
{
  "stock_code": "688981",
  "task_type": "daily",
  "strategy_mode": "short"
}
```

### 2. 任务执行流程更新

**初始化流程（init）**：
- 保持原有数据抓取和计算流程
- 最后一步：使用 `multi_strategy_analyzer.py` 替代 `quick_analysis_helpers.py --type twolayer`

**每日更新流程（daily）**：
- 保持原有数据更新和计算流程
- 最后一步：使用 `multi_strategy_analyzer.py` 进行 LLM 分析

### 3. 报告获取 API 更新

- 优先查找 `multi_strategy_analyzer.py` 生成的报告
- 报告文件名格式：`{ticker}_{mode}_strategy_analysis_{date}.md`
- 保持对旧格式 `final_decision` 报告的兼容

## 数据准备流程

在进行 LLM 分析前，系统确保以下数据完整：

| 数据文件 | 说明 |
|---------|------|
| `{ticker}_technical_trend_analysis.json` | 技术趋势分析（必需） |
| `{ticker}_financial_summary.json` | 财务分析（必需） |
| `{ticker}_sentiment_valuation.json` | 情绪估值（必需） |
| `{ticker}_shareholder_structure.json` | 股东结构（必需） |
| `{ticker}_research_report_analysis.json` | 研报分析（必需） |
| `{ticker}_company_basic.json` | 公司基本信息（必需） |

## 使用示例

### cURL 示例

```bash
# 短期交易策略
curl -X POST http://localhost:5000/quick_analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"688981","task_type":"daily","strategy_mode":"short"}'

# 中期持仓策略
curl -X POST http://localhost:5000/quick_analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"688981","task_type":"daily","strategy_mode":"medium"}'

# 长期投资策略
curl -X POST http://localhost:5000/quick_analyze \
  -H "Content-Type: application/json" \
  -d '{"stock_code":"688981","task_type":"daily","strategy_mode":"long"}'
```

### Python 示例

```python
import requests

# 发起分析请求
response = requests.post(
    'http://localhost:5000/quick_analyze',
    json={
        'stock_code': '688981',
        'task_type': 'daily',
        'strategy_mode': 'short'  # 可选: short/medium/long
    }
)
task_id = response.json()['task_id']

# 查询任务状态
status = requests.get(f'http://localhost:5000/quick_task_status/{task_id}').json()

# 获取报告
report = requests.get('http://localhost:5000/quick_report/688981').json()
```

## 策略模式说明

| 模式 | 权重配置 | 适用场景 |
|------|---------|---------|
| **短期交易** | 技术 80% + 情绪 20% | 波段操作，追求短期收益 |
| **中期持仓** | 技术 60% + 财务 30% + 股东 10% | 中线持有，平衡收益与风险 |
| **长期投资** | 财务 50% + 股东 30% + 技术 20% | 价值投资，关注长期价值 |

## 文件清单

### 修改的文件

- `api/quick_analysis.py` - 主要 API 文件
  - 增加策略模式参数
  - 修改任务流程
  - 更新报告获取逻辑

### 新增/使用的文件

- `Process/multi_strategy_analyzer.py` - 多策略分析器（已存在）

## 注意事项

1. 确保 Ollama 服务正常运行（默认 `http://localhost:11434`）
2. 配置文件 `config.py` 中的 `AI_CONFIG` 确保正确
3. 股票的基本数据和 JSON 文件必须完整
4. 首次使用建议使用 `task_type: init` 进行完整数据抓取
