# GP_ANA — A 股 AI 综合分析系统

**当前版本：v1.4.0**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9--3.12-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/AI-Ollama-orange.svg" alt="AI">
</p>

---

## 📖 项目摘要

**GP_ANA** 是一款面向 A 股市场的全流程量化投资与 AI 辅助决策系统。它打通了"数据采集 → 技术分析 → 策略回测 → AI 多维研判 → 交易决策"的完整链路，并通过 Flask Web 界面提供一站式的可视化操作体验。

**核心流程：** 从东方财富、akshare、Tushare、新浪财经等多源采集 20+ 类数据 → 覆盖财务、情绪估值、技术趋势、股东结构、研报观点五大维度的结构化分析 → 本地 LLM（Ollama）进行两层 AI 决策 → 自动生成交易计划与 20+ 种专业分析图表。

**适用人群：** 希望用数据驱动决策的个人投资者、量化策略研究者、以及需要批量跟踪多只股票的活跃交易者。

> **📌 第一次使用？** 直接跳到 [🚀 快速开始](#-快速开始从零到跑起来)，按 11 个步骤操作即可。整个部署约需 20 分钟（不含 AI 模型下载时间）。
>
> **📌 想深入了解内部实现？** 见 **[Introduction.md](Introduction.md)** —— 架构、算法、数据结构与设计决策的技术详解。

---

## 📑 目录

- [🚀 快速开始（从零到跑起来）](#-快速开始从零到跑起来)
- [🔑 Token 与账号需求](#-token-与账号需求)
- [⚙️ 配置详解](#-配置详解)
- [📦 依赖说明](#-依赖说明)
- [🖥️ 界面预览](#-界面预览)
- [🎯 核心能力](#-核心能力)
- [📊 可视化能力](#-可视化能力)
- [📂 程序分类](#-程序分类)
- [💻 命令行使用](#-命令行使用)
- [🔧 常见问题排查](#-常见问题排查)
- [⚠️ 安全注意事项](#-安全注意事项)
- [📄 版本历史](#-版本历史)

---

## 🚀 快速开始（从零到跑起来）

### 第 0 步：确认环境要求

| 项目 | 要求 | 说明 |
|:---|:---|:---|
| **操作系统** | macOS / Linux / Windows | macOS 与 Linux 最省事 |
| **Python** | **3.9 ~ 3.12**（推荐 3.10 / 3.11） | ⚠️ **3.13 暂不支持**，见下方说明 |
| **内存** | ≥ 8 GB | 若跑本地大模型建议 ≥ 32 GB |
| **磁盘** | ≥ 5 GB | 含数据目录与 AI 模型（模型本身可能 20 GB+） |
| **网络** | 可访问国内财经站点 | 数据源为东方财富/akshare/新浪/Tushare |

> ⚠️ **为什么推荐 Python 3.9 ~ 3.12？**
> 依赖中锁定了 `numpy==1.26.3`，该版本仅提供 Python 3.9 ~ 3.12 的预编译包。
> 在 **Python 3.13** 上会因找不到 wheel 而尝试源码编译，通常以失败告终。
> 若必须用 3.13，可把 `requirements.txt` 中的 `numpy==1.26.3` 改成 `numpy>=2.1` 再安装（未做完整验证）。
>
> 📌 早期版本曾因 `demjson` 依赖已被移除的 `imp` 模块而无法在 3.12 安装；
> **该依赖已作为冗余项清理，Python 3.12 现已可正常安装。**

检查你的 Python 版本：

```bash
python3 --version
```

若版本不符，建议用 conda 单独建一个 3.10 环境：

```bash
conda create -n gpana python=3.10 -y
conda activate gpana
```

---

### 第 1 步：获取代码

```bash
git clone https://github.com/Leo-luxy/GP_ANA.git
cd GP_ANA
```

---

### 第 2 步：创建虚拟环境（强烈推荐）

避免污染系统 Python 环境：

```bash
# 创建虚拟环境
python3 -m venv venv

# 激活 —— macOS / Linux
source venv/bin/activate

# 激活 —— Windows
venv\Scripts\activate
```

激活成功后，命令行提示符前会出现 `(venv)`。

---

### 第 3 步：安装 TA-Lib 系统库 ⚠️（最容易卡住的一步）

本项目用 `TA-Lib` 计算 40+ 种技术指标。**`TA-Lib` 的 Python 包依赖一个 C 语言底层库，必须先装系统库，再装 Python 包**，顺序反了必定失败。

**macOS：**

```bash
brew install ta-lib
```

**Ubuntu / Debian：**

```bash
sudo apt-get update
sudo apt-get install -y build-essential wget
# Ubuntu 官方源没有 ta-lib 包，需从源码编译：
wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
tar -xzf ta-lib-0.6.4-src.tar.gz
cd ta-lib-0.6.4/
./configure --prefix=/usr
make
sudo make install
cd ..
```

**Windows：**

Windows 下编译困难，**推荐直接下载预编译 wheel**（选择与你 Python 版本和系统位数匹配的文件）：

```
https://github.com/cgohlke/talib-build/releases
```

下载后本地安装：

```bash
pip install TA_Lib-0.6.8-cp310-cp310-win_amd64.whl
```

> 💡 **验证是否装好**：`python3 -c "import talib; print(talib.__version__)"`，能打印版本号即成功。
> 该命令报错时，请先解决 TA-Lib 再继续，不要跳过——否则后续所有技术分析功能都会崩。

---

### 第 4 步：安装 Python 依赖

```bash
pip install -r requirements.txt
```

> 💡 `requirements.txt` **现已包含** Web 框架 `flask`，正常安装即可。
> 若你使用的是旧版本（依赖清单中缺少该条目）并遇到启动报错，单独补装即可：

```bash
pip install flask
```

依赖较多，安装约需 3~10 分钟。若中途某个包失败，可单独重试该包，例如：

```bash
pip install akshare==1.18.39
```

---

### 第 5 步：安装并启动 Ollama（AI 分析功能必需）⭐

项目的所有 AI 分析、五维研判、两层决策都依赖本地大模型服务。

**1）安装 Ollama**

- macOS / Linux：访问 <https://ollama.com/download> 下载安装，或 `brew install ollama`
- Windows：下载安装包安装

**2）启动服务**

```bash
ollama serve
```

服务默认监听 `http://localhost:11434`。**建议让它在后台常驻**，或在另一个终端窗口保持运行。

**3）下载一个模型**

> ⚠️ **重要提醒**：配置文件 `config.example.py` 里默认写的是作者本机的模型名
> （`qwen3.6:35b-a3b-coding-nvfp4`）。**这些是自定义/本地模型，在 Ollama 公共仓库里并不存在**，
> 直接 `ollama pull` 会失败。请自行拉取一个可用模型，并把配置改成对应的名字。

```bash
# 示例：拉取公开可用的模型（按你的显存/内存选择）
ollama pull qwen3:8b        # 约 5 GB，8GB 内存可跑，速度较快
ollama pull qwen3:32b       # 约 20 GB，效果更好，建议 32GB+ 内存
ollama pull deepseek-r1:32b # 备选
```

**4）确认模型已就绪**

```bash
ollama list
```

记下你拉取的模型名，第 6 步要填进配置里。

---

### 第 6 步：创建配置文件

仓库里**没有** `config.py` 和 `trading_records.py`（它们含个人持仓信息，已被 `.gitignore` 排除），只提供了模板。请复制模板：

**macOS / Linux：**

```bash
cp config.example.py config.py
cp trading_records.example.py trading_records.py
```

**Windows：**

```bash
copy config.example.py config.py
copy trading_records.example.py trading_records.py
```

然后编辑 `config.py`，**至少修改以下两处**：

```python
# ① 填入你要分析的股票（键名任意，值为 6 位代码 + 交易所后缀）
STOCK_TICKERS = {
    'byd':    '002594.SZ',   # 6/9 开头 → .SH，0/3 开头 → .SZ
    'lanxi':  '300433.SZ',
}

# ② 填入你第 5 步实际拉取的模型名
AI_CONFIG = {
    'base_url': 'http://localhost:11434',
    'model': 'qwen3:8b',                       # ← 改成你自己的模型名
    'temperature': 0.3,
    'max_tokens': 8192,
    'trading_strategy': 'neutral',             # trend_following / mean_reversion / swing / neutral
    'fallback_models': ['qwen3:8b'],           # ← 同上
}
```

> **交易所后缀规则**：`6` 开头 → `.SH`（上交所），`0` / `3` 开头 → `.SZ`（深交所）。

**持仓记录（可选）**：编辑 `trading_records.py` 填入你的真实买卖记录，AI 才能结合持仓给出"继续持有/减仓/清仓"的建议。不填也能用，只是决策层拿不到持仓上下文。

---

### 第 7 步：配置 Tushare Token（仅"市场选股"功能需要）⭐

**这是本项目唯一需要申请的 token。**其余数据源（akshare、东方财富、新浪财经）都是免费公开接口，**无需任何密钥**。

**只在你要使用「市场选股」全市场筛选功能时才需要**，其余功能可跳过本步。

1. 注册并登录 <https://tushare.pro/>
2. 进入「个人主页 → 接口 TOKEN」，复制你的 token
3. 打开以下**两个**文件，把占位符替换成你的真实 token：

```python
# stocks_filter/step1_daily.py  第 15 行
# stocks_filter/step2_daily_basic.py  第 14 行
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"    # ← 替换为你的真实 token
```

> ⚠️ **安全提示**：这两个文件**在 git 仓库中是被跟踪的**。如果你打算把改动提交回公开仓库，
> 请务必先把自己的 token 改回 `YOUR_TUSHARE_TOKEN`，或改用环境变量注入，避免泄露。
> 详见 [⚠️ 安全注意事项](#-安全注意事项)。

> 💡 新注册的 Tushare 账号积分较低，**全市场日线接口（`pro.daily()`）需要 120 积分以上**才能调用。
> 若提示权限不足，请先在 Tushare 官网完成积分任务或升级权限。

---

### 第 8 步：初始化数据目录

程序不会自动创建数据目录，请手动建立：

```bash
mkdir -p data log
```

> 程序运行后，每只股票的分析结果和图表都会存到 `data/{股票代码}/` 下。

---

### 第 9 步：启动 Web 界面

```bash
python web_ui.py
```

看到类似下面的输出即为启动成功：

```
 * Running on http://0.0.0.0:8081
```

**打开浏览器访问：<http://localhost:8081>**

> ⚠️ 端口是 **8081**（不是 5000），且**当前版本硬编码在 `web_ui.py` 中，不支持命令行改端口**。
> 若 8081 被占用，请直接编辑 `web_ui.py` 最后一行的 `port=8081`。

---

### 第 10 步：首次使用流程

界面打开后，按以下顺序操作（**这个顺序很重要，跳过会导致功能空白**）：

| 顺序 | 操作 | 说明 |
|:---:|:---|:---|
| 1️⃣ | **先采集板块数据** | 点击「板块分析 → 更新板块数据」。**首次必须做**，否则板块列表是空的，无法分析 |
| 2️⃣ | **添加关注股票** | 点击「关注股票」，添加你想跟踪的股票。后续回测/分析会优先使用该列表 |
| 3️⃣ | **完整分析** | 点击「完整分析」，输入股票代码。首次全面评估，耗时 3~5 分钟 |
| 4️⃣ | **后续日常使用** | 「快速分析」30 秒出结果；需要筛选新股时用「市场选股」 |

各功能耗时与适用场景：

| 模式 | 耗时 | 适用场景 |
|:---|:---|:---|
| 🔍 **完整分析** | 3-5 分钟 | 新股票，首次全面评估（五维度 + 两层决策） |
| ⚡ **快速分析** | 30 秒 | 每日盘后快速复盘（仅技术面） |
| 📊 **策略回测** | 1-2 分钟 | 验证交易策略有效性 |
| 🏢 **板块分析** | 2-3 分钟 | 大盘/行业/概念/港股 AI 深度分析 |
| 🎯 **市场选股** | 3-5 分钟 | 全市场筛选 → 趋势回测 → 最终持仓（需 Tushare token） |
| ⭐ **自选股管理** | 即时 | 管理关注列表 |

---

### 第 11 步：命令行初始化数据（可选）

如果想在开界面之前先把数据准备好，可以运行：

```bash
# 为指定股票抓取并更新全部数据
python check_data_updates.py --mode daily --ticker 300433.SZ

# 板块数据采集
python sector_data_collector.py --type broad_index
python sector_data_collector.py --type industry --top 30
```

---

## 🔑 Token 与账号需求

**一句话总结：只有「市场选股」需要 Tushare token，其余全部功能开箱即用，无需任何密钥。**

| 功能 | 需要的凭据 | 获取方式 | 是否必需 |
|:---|:---|:---|:---|
| 完整分析 / 快速分析 / 回测 / 板块分析 | **无** | akshare、东方财富、新浪财经均为免费公开接口 | — |
| AI 分析（全部） | **无密钥** | 只需本地运行 Ollama 服务 | AI 功能必需 |
| **市场选股（全市场筛选）** | **Tushare Token** | 注册 <https://tushare.pro/> → 个人主页复制 token | 仅此功能需要 |
| Web 界面 | **无** | 本地访问 | — |

> ✅ 本项目**不需要** OpenAI / DeepSeek / 通义千问等云端 API key。所有 AI 推理均在本地 Ollama 完成，数据不出本机。

---

## ⚙️ 配置详解

`config.py` 是唯一的核心配置文件，主要区块：

| 配置项 | 作用 | 是否必改 |
|:---|:---|:---:|
| `STOCK_TICKERS` | 要分析的股票列表 | ✅ 必改 |
| `AI_CONFIG.model` | Ollama 模型名 | ✅ 必改（默认值是作者本机模型） |
| `AI_CONFIG.base_url` | Ollama 服务地址 | 默认 `http://localhost:11434` |
| `AI_CONFIG.trading_strategy` | 交易策略视角 | 可选，默认 `neutral` |
| `STRATEGY_PROMPTS` | 各策略的提示词模板 | 可选，可自行调优 |
| `HISTORY_DATE_RANGE` | 指定股票的历史数据区间 | 可选 |
| `TECHNICAL_INDICATORS` | 技术指标周期参数（MA/RSI/MACD/KDJ…） | 可选 |
| `STRATEGY_CONFIG` | 回测参数（初始资金、买卖阈值） | 可选 |
| `DATA_DIR` | 数据保存目录 | 自动推导为项目根目录 `data/`，无需改 |

**四种交易策略视角说明：**

| 策略 | 含义 |
|:---|:---|
| `trend_following` | 趋势跟踪 —— 只做有明显趋势的行情，不预测顶底 |
| `mean_reversion` | 均值回归 —— 在极端位置反向交易，需严格止损 |
| `swing` | 波段交易 —— 持仓数天至数周，捕捉日线级波段 |
| `neutral` | 中性客观 —— 不预设偏好，综合多空信号给出判断 |

---

## 📦 依赖说明

### 系统级依赖

| 依赖 | 用途 | 安装方式 |
|:---|:---|:---|
| **TA-Lib C 库** | 技术指标计算底层库 | 见 [第 3 步](#第-3-步安装-ta-lib-系统库-最容易卡住的一步) |
| **Ollama** | 本地大模型推理服务 | <https://ollama.com/download> |

### Python 依赖（`requirements.txt`）

| 包 | 用途 |
|:---|:---|
| `pandas` / `numpy` | 数据处理基础 |
| `akshare` | 主要财经数据源 |
| `tushare` | 全市场日线数据（市场选股功能） |
| `TA-Lib` | 40+ 技术指标计算 |
| `matplotlib` / `seaborn` | 图表生成 |
| `scikit-learn` | AI 预测模型 |
| `ollama` | 调用本地 LLM |
| `requests` | HTTP 请求 |
| `py_mini_racer` | 部分数据接口的 JS 加密参数计算 |
| `demjson` | 部分数据接口的宽松 JSON 解析 |

### ✅ 依赖完整性说明

当前 `requirements.txt` 已修正，**可直接一次安装成功**，无需额外补装。历史上的两个问题均已解决：

| 历史问题 | 状态 |
|:---|:---|
| `flask` 漏列，导致装完依赖后 Web 界面无法启动 | ✅ 已补入依赖清单 |
| `demjson` 依赖已移除的 `imp` 模块，导致 Python 3.12+ 无法安装 | ✅ 已作为冗余项移除 |

同时清理了两个从未被代码引用的历史遗留依赖：`yfinance`、`pandas-datareader`。

> ⚠️ **唯一剩余的版本约束**：`numpy==1.26.3` 仅支持 Python 3.9 ~ 3.12，**不支持 3.13**。

---

## 🖥️ 界面预览

### 完整分析 & 快速分析
<p align="center">
  <img src="assets/screenshots/完整分析.png" alt="完整分析" width="45%">
  &nbsp;
  <img src="assets/screenshots/快速分析.png" alt="快速分析" width="45%">
</p>

### 详细模式 & 单功能执行
<p align="center">
  <img src="assets/screenshots/详细模式.png" alt="详细模式" width="45%">
  &nbsp;
  <img src="assets/screenshots/单功能执行.png" alt="单功能执行" width="45%">
</p>

### 策略回测 & 市场选股
<p align="center">
  <img src="assets/screenshots/策略回测.png" alt="策略回测" width="45%">
  &nbsp;
  <img src="assets/screenshots/市场选股.png" alt="市场选股" width="45%">
</p>

### 板块分析 & 关注股票
<p align="center">
  <img src="assets/screenshots/板块分析.png" alt="板块分析" width="45%">
  &nbsp;
  <img src="assets/screenshots/关注股票.png" alt="关注股票" width="45%">
</p>

### 报告查看 & 买卖记录管理
<p align="center">
  <img src="assets/screenshots/报告查看.png" alt="报告查看" width="45%">
  &nbsp;
  <img src="assets/screenshots/买卖记录管理.png" alt="买卖记录管理" width="45%">
</p>

---

## 🎯 核心能力

```
┌──────────────────────────────────────────────────────────────┐
│                     📡 数据采集层                              │
│   20+ 采集器：行情 / 财务 / 资金流 / 融资融券 / 股东 / 行业 / 研报   │
│   + 板块数据：大盘指数 / 行业板块 / 概念板块 / 港股指数             │
│   + 全市场数据：Tushare 日线行情 / 基础指标                        │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     🔬 五维度分析引擎 + 板块分析                  │
│   个股：财务(25%) + 情绪估值(15%) + 技术趋势(40%)                │
│   + 股东结构(10%) + 研报观点(10%)                               │
│   板块：技术指标 + LLM 深度分析（single/broad 双模式）            │
│   每个维度 → 结构化 JSON → LLM 深度分析                         │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│                     🧠 两层 AI 决策                            │
│   第一层：五维度冲突检测 → 识别多空矛盾信号                       │
│   第二层：结合持仓信息 → 生成具体交易计划（买入/卖出/持有）          │
└──────────────────────────┬───────────────────────────────────┘
                           ▼
┌──────────────────────────────────────────────────────────────┐
│              📊 可视化 & 📈 策略回测 & 🎯 市场选股 & 🌐 Web 界面    │
│   20+ 图表 / 3 种策略模式 / 全市场筛选+回测 / Flask Web UI          │
└──────────────────────────────────────────────────────────────┘
```

### 为什么选择 GP_ANA？

| 特性 | 传统炒股软件 | **GP_ANA** |
|:---|:---|:---|
| 数据来源 | 单一平台 | **20+ 采集器**，东方财富/akshare/Tushare/新浪财经多源融合 |
| 分析维度 | 仅 K 线 | **五大维度**：财务 + 情绪估值 + 技术趋势 + 股东结构 + 研报观点 |
| AI 决策 | ❌ | ✅ **两层 AI 决策**：冲突检测 + 交易计划，本地 Ollama 驱动 |
| 策略验证 | 手动复盘 | **自动回测**，趋势跟踪/均值回归/波段三种策略 |
| 可视化 | 固定模板 | **20+ 种专业图表**，价格/成交量/布林带/相关性/信号分析/趋势通道... |
| 板块分析 | 手动翻看 | **四大板块类型**（大盘/行业/概念/港股）AI 深度分析 |
| 市场选股 | 逐个翻找 | **全市场筛选**：Tushare 全市场日线 → 多条件筛选 → 趋势回测 → 最终持仓 |
| 自选股管理 | 脑记笔记 | **Web 界面增删查**，回测/分析优先从关注列表取股票 |
| 数据隐私 | 上传云端 | ✅ **全部本地推理**，行情与持仓不出本机 |

---

## 📊 可视化能力

GP_ANA 为每只股票自动生成 **20+ 种专业级分析图表**，无需任何配置：

### 市场数据可视化

| 图表类型 | 文件名示例 | 说明 |
|:---|:---|:---|
| 🕯️ **价格成交量** | `price_volume.png` | K 线 + 成交量柱状图 + 均线系统 |
| 📈 **技术指标面板** | `technical_indicators.png` | 多面板展示 MA/RSI/MACD/KDJ/CCI/ROC/WR 等 16 项指标 |
| 🎚️ **布林带** | `bollinger_bands.png` | 布林带 + 价格走势，识别超买超卖 |
| 🔗 **相关性热力图** | `correlation.png` | 全部技术指标相关性矩阵 |

### 策略与信号

| 图表类型 | 文件名示例 | 说明 |
|:---|:---|:---|
| 📡 **信号分析** | `signal_analysis.png` | 各技术指标的买卖信号分布与有效性评估 |
| 📊 **策略回测结果** | `strategy_results.png` | 资金曲线 + 买卖点标注 + 收益率/夏普比率/最大回撤 |
| 🏔️ **支撑阻力位** | `support_resistance.png` | AI 识别的关键支撑/阻力位，含成交密集区 |
| 📐 **趋势通道** | `trend_channel_results.png` | 自动检测趋势通道，标记突破/回归信号 |

### AI 预测

| 图表类型 | 文件名示例 | 说明 |
|:---|:---|:---|
| 🔮 **AI 价格预测** | `ai_predictions.png` | 机器学习模型对未来 N 日价格预测 |
| ⭐ **特征重要性** | `feature_importance.png` | 各技术指标对预测的贡献度排序 |
| 🧠 **AI 综合预测** | `prediction.png` | LLM 增强的综合趋势预判 |

### 回测系统

| 图表类型 | 文件名示例 | 说明 |
|:---|:---|:---|
| 📈 **回测收益曲线** | `backtest_YYYYMMDD.png` | 每次回测的完整收益曲线 + 交易标记 |

> 所有图表自动保存至 `./data/{ticker}/` 目录，既可在 Web 界面在线查看，也可导出用于报告。

---

## 📂 程序分类

> 以下是完整的模块清单，供查阅参考。

### 1. 数据抓取类

| 程序名称 | 功能 | 数据源 | 输出物 |
|---------|------|--------|--------|
| `data_collector.py` | 历史行情数据（前复权） | akshare | `{ticker}_qfq.csv` |
| `stock_market_data_collector.py` | 资金流、融资融券、估值数据 | akshare | `{ticker}_fund_flow.csv` / `_margin_data.csv` / `_valuation.csv` |
| `stock_company_info_collector.py` | 公司基本信息、研报、股东、财务报表 | akshare | `{ticker}_company_basic.json` / `_research_reports.csv` 等 |
| `eastmoney_fetcher.py` ⭐ | **统一东方财富数据抓取入口** (`--type market_performance\|industry_valuation\|industry_peers\|industry_growth\|dupont`) | 东方财富 API | 各类行业/市场数据 |
| `financial_indicators_collector.py` | 财务指标、成长指标、现金流指标 | akshare | `{ticker}_financial_indicators.json` |
| `shareholders_collector.py` | 前十大股东历史数据 | 东方财富 API | `{ticker}_historical_shareholders.csv` |
| `shareholder_num_collector.py` | 股东户数、户均持股 | 东方财富 API | `{ticker}_shareholder_num.csv` |
| `north_holdings.py` | 北向资金持股 | 东方财富 API | `{ticker}_north_holdings.csv` |
| `org_hold_collector.py` | 机构持仓明细 | 东方财富 API | `{ticker}_institutional_holdings.csv` |
| `em_financial_collector.py` | 东方财富财务数据 | 东方财富 API | `{ticker}_dupont_data.csv` / `_growth_ratio_data.csv` |
| `important_missing_data_collector.py` | 业绩预告与分红数据 | 多数据源 | `{ticker}_performance_forecast.csv` / `_ex_dividend.csv` |
| `shenwan_industry_collector.py` | 申万行业分类 | 东方财富 API | `{ticker}_industry_info.json` |
| `batch_margin_collector.py` ⭐ | 批量融资融券数据采集 | akshare | 多股票 `_margin_data.csv` |
| `sector_data_collector.py` ⭐ | **板块数据采集** — 大盘指数/行业/概念/港股，新浪财经+东方财富 | akshare / 新浪 | `data/sector/{type}/{code}/` |
| `stocks_filter/step1_daily.py` ⭐ | **全市场日线行情** — Tushare pro.daily() 获取全 A 股日线 | Tushare（**需 token**） | `stocks_daily_temp.csv` |
| `stocks_filter/step2_daily_basic.py` ⭐ | **全市场基础指标** — 换手率/市值/PE/PB 等合并 | Tushare（**需 token**） | `stocks_daily_full.csv` |
| `stocks_filter/step3_filter.py` ⭐ | **多条件筛选** — 价格/成交额/换手率/市值/振幅/涨幅过滤 | 本地计算 | `stocks_daily_filtered.csv` |
| `stocks_filter/batch_backtest_filter.py` ⭐ | **批量回测筛选** — 对筛选结果逐只趋势回测，输出最终持仓 | 本地计算 | `final_holdings.csv` |

### 2. 数据分析类

| 程序名称 | 功能 | 输出物 |
|---------|------|--------|
| `analyze_financial_statements.py` | 财务报表 AI 分析 | `{ticker}_financial_analysis_{timestamp}.md` |
| `analyze_fund_flow.py` | 资金流 AI 分析 | `{ticker}_fund_flow_analysis_{timestamp}.md` |
| `analyze_margin_data.py` | 融资融券 AI 分析 | `{ticker}_margin_data_analysis_{timestamp}.md` |
| `analyze_research_reports.py` | 研究报告 AI 分析 | `{ticker}_research_reports_analysis_{timestamp}.md` |
| `analyze_shareholder_structure.py` | 股东结构 AI 分析 | `{ticker}_shareholder_structure_analysis_{timestamp}.md` |
| `analyze_valuation_data.py` | 估值 AI 分析 | `{ticker}_valuation_analysis_{timestamp}.md` |
| `analyze_technical_trend.py` | 技术趋势 AI 分析（支持 `--strategy` 切换策略视角） | `{ticker}_technical_trend_analysis.json` |
| `analyze_em_financial.py` | 东方财富财务 AI 分析 | 财务分析报告 |
| `analyze_performance_forecast.py` | 业绩预测 AI 分析 | 业绩预测分析报告 |
| `analyze_peer_comparison.py` | 同行对比 AI 分析 | 同行对比分析报告 |
| `analyze_sector.py` ⭐ | **板块 AI 分析** — 单板块深度/大盘全景双模式 | 板块分析报告 |
| `calculate_financial_indicators.py` | 综合财务指标计算（盈利能力/偿债能力/运营能力/现金流/成长能力） | `{ticker}_financial_indicators_calculated.json` |
| `calculate_technical_trend_ds.py` ⭐ | 技术趋势分析计算 | 技术趋势分析数据 |
| `daily/data_analysis.py` | 数据质量检查 + 可视化（16 项指标含 OBV/ATR/ADX/MFI） | 价格/成交量/布林带/相关性图表 |
| `daily/technical_analysis.py` | 技术指标信号分析与有效性评估 | 信号分析图表 |
| `daily/quantitative_strategy.py` | 量化策略回测 | 策略回测图表 + 交易信号 CSV |
| `daily/strategy_optimization.py` | 策略参数优化 | 优化结果图表 |
| `daily/trend_channel_analyzer.py` | 趋势通道分析 | 趋势通道图表 + 信号 CSV |
| `daily/stock_quantitative_analyzer.py` | 股票量化综合分析 | 分析 CSV + 图表 |
| `daily/ai_model.py` | AI 预测模型训练与推理 | AI 模型文件 |
| `daily/stock_prediction.py` | 股票价格预测 | 预测结果图表 |
| `daily/stock_daily_indicator_calculator.py` | 日线综合指标计算 | `{ticker}_daily_indicators.csv` |
| `daily/daily_strategy_optimization_multistock.py` | 多股票策略参数优化 | 优化结果 CSV + 图表 |
| `daily/daily_trend_strategy.py` | 日线趋势跟踪策略 | 策略信号 CSV |
| `weekly/` | 周线分析（数据检查/策略回测/优化/综合分析/AI预测） | 周线分析报告 |

### 3. Process/ 分析引擎 ⭐（v1.2 新增）

五维度 JSON 摘要 + 两层决策系统：

| 模块 | 功能 |
|------|------|
| `Process/financial_structured_analyzer.py` | 财务数据 → 结构化 JSON（盈利能力/成长性/风险） |
| `Process/sentiment_valuation_analyzer.py` | 情绪 + 估值 → JSON（市场情绪/估值分位/技术情绪） |
| `Process/shareholder_structure_analyzer.py` | 股东结构 → JSON（集中度/机构动向/北向资金） |
| `Process/research_report_analyzer.py` | 研报观点 → JSON（评级分布/目标价/关键观点） |
| `Process/two_layer_decision_analyzer.py` | **两层决策** — 冲突检测 + 持仓交易计划 |
| `Process/multi_strategy_analyzer.py` | 多策略 LLM 分析（趋势跟踪/均值回归/波段） |
| `Process/financial_analysis_enhancer.py` | 财务分析增强 — 深度解读财务指标关联与异常 |

### 4. AI / LLM 分析类

| 程序名称 | 功能 |
|---------|------|
| `stock_ai_comprehensive_analyzer.py` | 综合各维度分析报告 → AI 大模型综合分析 |
| `daily/stock_ai_local_analyzer.py` | K 线数据 → AI 日线分析 + 支撑阻力位图表 |
| `weekly/weekly_stock_ai_local_analyzer.py` | 周线数据 → AI 周线分析 |

### 5. 回测系统 ⭐

| 程序名称 | 功能 |
|---------|------|
| `trend_following_backtest.py` | 趋势跟踪策略回测引擎 |
| `backtest_all_stocks.py` | 全股票批量回测（`--mode full\|simple`） |
| `trend_following_backtest_simplified.py` ⭐ | 简化版趋势跟踪回测（仅 MA5>MA20） |
| `backtest_all_stocks_simplified.py` ⭐ | 简化版全股票批量回测 |

### 6. Web 界面 & API

| 程序名称 | 功能 |
|---------|------|
| `web_ui.py` | Flask Web 主界面（`http://localhost:8081`） |
| `api/analysis.py` | 完整分析 API（全量数据 + 五维度 + 两层决策） |
| `api/quick_analysis.py` ⭐ | 快速分析 API（仅 K 线 + 技术趋势，三种策略视角） |
| `api/backtest.py` ⭐ | 回测 API |
| `api/detailed.py` | 详细模式 API（单步数据抓取/分析/查询） |
| `api/trading.py` | 交易记录管理 API |
| `api/report_viewer.py` | 报告查看 API |
| `api/common.py` ⭐ | 共享模块（交易所映射、任务队列、步骤执行引擎） |
| `api/sector.py` ⭐ | **板块分析 API** — 数据采集/分析触发/状态轮询/报告获取 |
| `api/stock_selection.py` ⭐ | **市场选股 API** — 异步选股任务/进度追踪/结果读取 |
| `api/watchlist.py` ⭐ | **自选股管理 API** — 关注列表增删查 |

### 7. 工具 & 配置

| 文件名 | 功能 |
|-------|------|
| `config.example.py` | 配置模板（复制为 `config.py` 后使用） |
| `trading_records.example.py` | 持仓记录模板（复制为 `trading_records.py` 后使用） |
| `watchlist.py` | 自选股配置（Web 界面可增删，回测/分析优先使用） |
| `requirements.txt` | Python 依赖包列表 |
| `utils.py` | 通用工具函数（技术指标计算、日期处理、文件操作等） |
| `check_data_updates.py` | 统一数据更新检查（`--mode daily\|periodic`） |
| `batch_analyze.py` | 统一批量分析入口（`--mode all\|daily\|periodic`） |

---

## 💻 命令行使用

```bash
# 统一批量分析
python batch_analyze.py --mode periodic --ticker 300433.SZ
python batch_analyze.py --mode daily --ticker 300433.SZ

# 统一数据抓取
python eastmoney_fetcher.py --type market_performance --ticker 300433.SZ
python eastmoney_fetcher.py --type dupont --ticker 300433.SZ

# 数据更新检查
python check_data_updates.py --mode daily --ticker 300433.SZ
python check_data_updates.py --mode periodic --ticker 300433.SZ

# 技术趋势分析（切换策略视角）
python analyze_technical_trend.py --strategy trend_following --ticker 300433.SZ
python analyze_technical_trend.py --strategy swing --ticker 300433.SZ

# 板块分析
python sector_data_collector.py --type broad_index                # 采集大盘指数数据
python sector_data_collector.py --type industry --top 30           # 采集行业板块数据
python analyze_sector.py --mode single --sector BK0477             # 单板块深度分析
python analyze_sector.py --mode broad                              # 大盘全景分析

# 市场选股（三步流水线，需先在 step1/step2 中填入 Tushare token）
cd stocks_filter
python step1_daily.py                     # Step1: 获取全市场日线行情
python step2_daily_basic.py               # Step2: 获取基础指标并合并（需等 step1 完成 1 小时后）
python step3_filter.py                    # Step3: 多条件筛选
python batch_backtest_filter.py            # Step4: 批量趋势回测 → final_holdings.csv
```

---

## 🔧 常见问题排查

### Q1: 安装依赖时 `TA-Lib` 报错

**现象**：`pip install TA-Lib` 失败，提示找不到 `ta_lib.h` 或 `ta-lib` 库。

**原因**：只装了 Python 包，没装底层 C 库。

**解决**：先按 [第 3 步](#第-3-步安装-ta-lib-系统库-最容易卡住的一步) 装系统库，再 `pip install TA-Lib==0.6.8`。

---

### Q2: 启动后报 `ModuleNotFoundError: No module named 'flask'`

**原因**：旧版本的 `requirements.txt` 漏列了 `flask`（该问题已修复）。

**解决**：

```bash
pip install flask
```

---

### Q3: 在 Python 3.13 上安装失败（numpy 编译报错）

**原因**：`requirements.txt` 锁定 `numpy==1.26.3`，该版本不支持 Python 3.13。

**解决**：改用 Python 3.9 ~ 3.12；或把依赖改为 `numpy>=2.1` 后重装（未做完整验证）。

> 另：旧版本曾在 Python 3.12 报 `ModuleNotFoundError: No module named 'imp'`，
> 原因是 `demjson` 依赖已被移除的 `imp` 模块。该依赖已清理，此问题不复存在。

---

### Q4: 启动后浏览器打不开 / 端口不通

**检查清单**：

1. 端口是 **8081**，不是 5000 —— 访问 <http://localhost:8081>
2. 确认 8081 未被占用：`lsof -i :8081`（macOS/Linux）
3. 需要改端口时，编辑 `web_ui.py` 最后一行的 `port=8081`（**当前版本不支持命令行 `--port` 参数**）

---

### Q5: AI 分析一直失败或超时

**检查清单**：

1. Ollama 服务是否在运行：`ollama list`，若报连接错误则先执行 `ollama serve`
2. `config.py` 中 `AI_CONFIG.model` 是否与你实际拉取的模型名**完全一致**
3. 模型是否太大导致推理过慢：可换用更小的模型如 `qwen3:8b`
4. 首次加载模型需要时间，请耐心等待

> ⚠️ 默认配置里的模型名（如 `qwen3.6:35b-a3b-coding-nvfp4`）是作者本机的自定义模型，
> **公共 Ollama 仓库中不存在**，必须改成你自己拉取的模型名。

---

### Q6: 板块分析页面的板块列表是空的

**原因**：板块数据尚未采集，首次使用必须初始化。

**解决**：在 Web 界面点击「板块分析 → 更新板块数据」，或命令行执行：

```bash
python sector_data_collector.py --type broad_index
python sector_data_collector.py --type industry --top 30
```

---

### Q7: 市场选股提示 Tushare 权限不足

**原因**：Tushare 的 `pro.daily()` 接口需要 **120 积分以上**，新账号默认积分不足。

**解决**：登录 <https://tushare.pro/> 完成积分任务或升级权限；同时确认 token 已正确填入 `stocks_filter/step1_daily.py` 和 `step2_daily_basic.py`。

---

### Q8: 抓取数据时报网络错误 / 超时

**原因**：财经数据接口偶发限流、代理干扰或接口变更。

**解决**：

1. 检查网络能否正常访问东方财富、新浪财经
2. **关闭系统代理或 VPN**（项目代码已主动清理代理环境变量，但全局代理仍可能干扰）
3. 升级 akshare：`pip install --upgrade akshare`
4. 稍后重试，数据接口有频率限制

---

### Q9: 找不到 `config.py`

**原因**：出于安全考虑，`config.py` 和 `trading_records.py` 未包含在仓库中。

**解决**：

```bash
cp config.example.py config.py
cp trading_records.example.py trading_records.py
```

---

## ⚠️ 安全注意事项

### 🔴 部署前必读

**1）`web_ui.py` 以 Flask debug 模式监听 `0.0.0.0`**

当前版本 `web_ui.py` 使用 `app.run(host='0.0.0.0', port=8081, debug=True)`。这意味着：

- `debug=True` 会启用 Werkzeug 调试器，**在出错页面提供可执行任意代码的交互式控制台**
- `host='0.0.0.0'` 表示监听**所有网卡**，同一局域网内其他设备可访问

**⚠️ 请勿在公网或不可信网络中运行。** 若需长期运行，建议修改为：

```python
app.run(host='127.0.0.1', port=8081, debug=False)   # 仅本机可访问，关闭调试器
```

**2）Tushare token 不要提交到公开仓库**

`stocks_filter/step1_daily.py` 和 `stocks_filter/step2_daily_basic.py` **是被 git 跟踪的文件**。
如果你填入了真实 token 并执行 `git commit`，token 将进入公开的 commit 历史。

- 提交前务必把 token 改回 `"YOUR_TUSHARE_TOKEN"`
- 更稳妥的做法：改用环境变量读取，例如
  ```python
  import os
  TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
  ```
- 若已误提交，需立即到 Tushare 官网**重置 token**，并清理 git 历史

**3）`config.py` 与 `trading_records.py` 含个人持仓隐私**

这两个文件已被 `.gitignore` 排除，**请勿手动取消忽略或提交**。它们记录了你的真实持仓成本与数量。

**4）`data/` 目录含全部分析结果与持仓决策**

`data/` 同样被 `.gitignore` 排除。分享或打包本项目前，建议清空该目录：

```bash
rm -rf data/*        # 注意：会删除所有已生成的分析报告与图表
```

### 🟢 良好的隐私设计

值得肯定的是，本项目**所有 AI 推理均在本地 Ollama 完成**，行情数据直接取自公开财经接口，**不会将你的持仓或分析数据上传到任何第三方 AI 服务**。

### 其他建议

1. 不要在公共网络环境下暴露服务端口
2. 定期更新依赖包以修复安全漏洞：`pip install -r requirements.txt --upgrade`
3. 数据目录权限设为仅当前用户可读写：`chmod 700 data`

---

## 📄 版本历史

| 版本 | 日期 | 主要变更 |
|------|------|---------|
| **v1.4.0** | 2026-06 | 市场选股+自选股管理、KDJ/板块时效性修复、回测增强（关注列表+公司名）、超时控制 |
| **v1.3.0** | 2026-06 | 板块分析：四大类型 AI 分析、新浪财经数据源、sector API |
| **v1.2.0** | 2026-05 | 架构重构：统一入口、Process/引擎、两层决策、快速分析、回测系统 |
| v1.1.0 | 2026-03 | 41 模块：Web 界面、12 个新采集器、5 个新分析引擎 |
| v1.0.1 | 2026-02 | 18 模块：数据采集 + 基础分析 |

详见 [CHANGELOG.md](CHANGELOG.md)

---

## 📚 相关文档

| 文档 | 说明 |
|:---|:---|
| [**Introduction.md**](Introduction.md) | **技术详解** —— 系统架构、五维决策算法、模块技术档案、数据字典、API 参考、设计决策 |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 |
| [SECURITY.md](SECURITY.md) | 安全政策 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 行为准则 |

---

## 📜 许可证

本项目采用 [MIT License](LICENSE)。

---

## ⚖️ 免责声明

本项目为**技术学习与研究工具**，所有 AI 分析结果、交易建议、回测数据**均不构成任何投资建议**。
股市有风险，投资需谨慎。使用本项目产生的任何投资决策及其后果，由使用者自行承担。

---

<p align="center">
  <sub>Made with ❤️ for quantitative investors</sub>
</p>
