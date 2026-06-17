# 股票分析系统 - 部署说明

## 一、环境要求

### 1.1 操作系统
- macOS (推荐) / Linux / Windows
- Python 3.9+

### 1.2 必要依赖
- Git
- Python 3.9+
- pip

### 1.3 可选依赖
- Ollama (用于AI分析功能)
- Node.js (用于前端界面，如需要)

---

## 二、部署流程

### 2.1 克隆代码仓库

```bash
# 克隆项目
git clone <仓库地址>
cd GP_ANA_3V1

# 查看当前目录结构
ls -la
```

### 2.2 创建虚拟环境（推荐）

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 2.3 安装依赖包

```bash
# 安装基础依赖
pip install -r requirements.txt

# 安装 TA-Lib（如安装失败，需手动安装）
# macOS: brew install ta-lib
# Ubuntu: sudo apt-get install libta-lib-dev
# 然后重新安装
pip install TA-Lib==0.6.8
```

### 2.4 创建必要目录

```bash
# 创建数据目录
mkdir -p data
mkdir -p log

# 创建临时目录（如需要）
mkdir -p temp
```

### 2.5 配置文件设置

#### 2.5.1 修改股票配置

编辑 `config.py` 文件，配置需要分析的股票：

```python
STOCK_TICKERS = {
    'zhenjianggufen': '603507.SH',  # 振江股份
    'lansikeji': '300433.SZ',       # 蓝思科技
    # 添加更多股票...
}
```

#### 2.5.2 配置关注列表（可选）

创建或编辑 `watchlist.py` 文件：

```python
WATCHLIST = [
    ('603507.SH', '振江股份'),
    ('300433.SZ', '蓝思科技'),
    # 添加更多关注股票...
]
```

#### 2.5.3 AI模型配置（可选）

如需使用AI分析功能，需要部署Ollama：

```bash
# 安装 Ollama (macOS)
brew install ollama

# 启动 Ollama 服务
ollama serve

# 下载需要的模型
ollama pull gemma4:31b-mlx
ollama pull qwen3.6:35b-a3b-coding-nvfp4
```

### 2.6 初始化数据

```bash
# 手动运行一次数据更新，初始化股票数据
python check_data_updates.py --ticker 603507.SH

# 或者批量更新关注列表中的股票
python check_data_updates.py
```

---

## 三、启动服务

### 3.1 启动 Web UI

```bash
# 启动主服务
python web_ui.py

# 服务启动后访问
# http://localhost:5000
```

### 3.2 单独运行分析脚本

```bash
# 财务报表分析
python analyze_financial_statements.py --ticker 603507.SH

# 资金流分析
python analyze_fund_flow.py --ticker 603507.SH

# 股东结构分析
python analyze_shareholder_structure.py --ticker 603507.SH

# 运行回测
python -c "from api.backtest import run_backtest; run_backtest()"
```

---

## 四、API 接口说明

### 4.1 分析接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/analyze` | POST | 完整分析 |
| `/api/quick_analyze` | POST | 快速分析 |
| `/api/detailed/<ticker>` | GET | 获取详细信息 |

### 4.2 回测接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/backtest/run_backtest` | POST | 启动回测任务 |
| `/api/backtest/task_status/<task_id>` | GET | 获取任务状态 |
| `/api/backtest/get_stock_list` | GET | 获取股票列表 |

### 4.3 关注列表接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/watchlist/add` | POST | 添加关注股票 |
| `/api/watchlist/remove` | POST | 移除关注股票 |
| `/api/watchlist/list` | GET | 获取关注列表 |

### 4.4 选股接口

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/stock_selection/run` | POST | 启动选股任务 |
| `/api/stock_selection/status/<task_id>` | GET | 获取选股状态 |

---

## 五、目录结构说明

```
GP_ANA_3V1/
├── api/              # API接口模块
│   ├── analysis.py   # 分析API
│   ├── backtest.py   # 回测API
│   ├── watchlist.py  # 关注列表API
│   ├── stock_selection.py  # 选股API
│   └── ...
├── daily/            # 日线分析模块
├── weekly/           # 周线分析模块
├── Process/          # 策略分析模块
├── data/             # 数据存储目录（运行时创建）
├── log/              # 日志目录（运行时创建）
├── config.py         # 配置文件
├── requirements.txt  # 依赖列表
├── web_ui.py         # Web界面入口
└── README.md         # 项目说明
```

---

## 六、常见问题

### 6.1 TA-Lib 安装失败

**问题**：`pip install TA-Lib` 失败

**解决方案**：
```bash
# macOS
brew install ta-lib
pip install TA-Lib

# Ubuntu
sudo apt-get install libta-lib-dev
pip install TA-Lib
```

### 6.2 数据抓取失败

**问题**：网络请求超时或数据接口变更

**解决方案**：
1. 检查网络连接
2. 确认 akshare 版本正确
3. 查看错误日志定位问题

### 6.3 AI分析功能不可用

**问题**：Ollama 服务未启动或模型未下载

**解决方案**：
```bash
# 启动 Ollama 服务
ollama serve

# 下载模型
ollama pull gemma4:31b-mlx
```

### 6.4 端口冲突

**问题**：端口 5000 被占用

**解决方案**：
```bash
# 修改 web_ui.py 中的端口配置
# 或在启动时指定端口
python web_ui.py --port 5001
```

---

## 七、维护说明

### 7.1 定期更新

```bash
# 拉取最新代码
git pull origin main

# 更新依赖
pip install -r requirements.txt --upgrade
```

### 7.2 数据清理

```bash
# 清理过期日志
rm -rf log/*.log

# 清理临时文件
rm -rf temp/*
```

### 7.3 备份数据

```bash
# 备份数据目录
tar -czf data_backup_$(date +%Y%m%d).tar.gz data/
```

---

## 八、安全注意事项

1. 不要在公共网络环境下暴露服务端口
2. 定期更新依赖包，修复安全漏洞
3. 敏感配置信息建议使用环境变量管理
4. 数据目录权限设置为仅当前用户可读写