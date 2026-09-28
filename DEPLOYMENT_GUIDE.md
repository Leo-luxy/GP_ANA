# GP_ANA 部署与运维参考

> ## 📌 部署安装请看 [README.md](README.md)
>
> README 中包含完整的**分平台 11 步部署流程**：Python 版本要求、TA-Lib 系统库安装、
> 依赖安装、Ollama 配置、Tushare token 申请、首次使用流程与 9 条常见问题排查。
>
> **本文档只保留 README 未覆盖的内容：API 接口参考 与 运维维护。**

---

## ⚠️ 本文档旧版本的内容更正

旧版 `DEPLOYMENT_GUIDE.md` 存在多处错误，现已更正。若你参考过旧版本，请注意：

| 旧文档内容 | 实际情况 |
|:---|:---|
| 目录名 `GP_ANA_3V1` | 实际为 `GP_ANA` |
| Web 端口 `5000` | 实际为 **8081** |
| `python web_ui.py --port 5001` | 该参数**不存在**，端口硬编码在 `web_ui.py` 最后一行 |
| `sudo apt-get install libta-lib-dev` | Ubuntu 官方源**无此包**，必须从源码编译 TA-Lib |
| 依赖中未提 `flask` | `flask` 此前**漏列于 `requirements.txt`**，现已补上 |
| `/api/detailed/<ticker>` | 实际为 `POST /api/detailed_function` |
| `/api/watchlist/list` | 实际为 `GET /api/watchlist/get` |
| `/api/stock_selection/status/<task_id>` | 实际为 `GET /api/stock_selection/task_status/<task_id>` |

---

## 一、环境要求速查

> 详细安装步骤见 [README.md](README.md)

| 项目 | 要求 |
|:---|:---|
| 操作系统 | macOS / Linux / Windows |
| Python | **3.9 ~ 3.11**（推荐 3.10 / 3.11；3.12+ 的兼容性问题已修复，见下方说明） |
| 系统依赖 | TA-Lib C 库（必须）、Ollama（AI 功能必需） |
| 端口 | **8081** |

> 💡 **关于 Python 3.12+**：此前 `requirements.txt` 中的 `demjson` 依赖已被移除的 `imp` 模块，
> 导致 3.12+ 无法安装。该依赖已确认零引用并移除，**现在 Python 3.12 / 3.13 也可正常安装**。

---

## 二、目录结构

```
GP_ANA/
├── api/                    # Flask API 蓝图
│   ├── analysis.py         # 完整分析
│   ├── quick_analysis.py   # 快速分析
│   ├── detailed.py         # 单步功能执行
│   ├── backtest.py         # 策略回测
│   ├── sector.py           # 板块分析
│   ├── stock_selection.py  # 市场选股
│   ├── watchlist.py        # 自选股管理
│   ├── trading.py          # 交易记录
│   ├── report_viewer.py    # 报告查看
│   └── common.py           # 共享模块（交易所映射/任务队列/步骤执行）
├── Process/                # 五维分析引擎 + 两层决策
├── daily/                  # 日线策略与指标计算
├── weekly/                 # 周线策略
├── stocks_filter/          # 全市场筛选流水线（需 Tushare token）
├── shenwan_config/         # 申万行业分类配置
├── templates/              # 前端页面（index.html 单页应用）
├── static/                 # 静态资源
├── data/                   # 运行时生成：各股票的分析结果与图表（已 gitignore）
├── log/                    # 运行时生成：日志（已 gitignore）
├── web_ui.py               # **Web 服务入口**
├── config.py               # 本地配置（由 config.example.py 复制，不入库）
├── trading_records.py      # 本地持仓记录（由 trading_records.example.py 复制，不入库）
├── watchlist.py            # 自选股列表
├── requirements.txt        # 依赖清单
└── README.md               # **部署与使用主文档**
```

> ⚠️ `data/` 与 `log/` 不会自动创建，首次运行前需手动 `mkdir -p data log`。

---

## 三、API 接口参考

以下为**实际注册的全部 33 个路由**（自动从源码提取）。Web 界面本身也通过这些接口工作，
如需二次开发或对接自有前端，可直接调用。

### 3.1 完整分析（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/analyze` | 启动完整分析任务（全量采集 + 五维 + 两层决策） |
| `GET` | `/api/task_status/<task_id>` | 查询分析任务进度 |
| `GET` | `/api/reports/<stock_code>` | 列出该股票的全部分析报告 |
| `GET` | `/api/report/<path:report_path>` | 读取指定报告内容 |
| `GET` | `/api/latest_report/<stock_code>` | 读取最新报告 |

### 3.2 快速分析（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/quick_analyze` | 启动快速分析（仅技术面，支持三种策略视角） |
| `GET` | `/api/quick_task_status/<task_id>` | 查询快速分析进度 |
| `GET` | `/api/quick_report/<stock_code>` | 读取快速分析报告 |

### 3.3 单步功能执行（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/detailed_function` | 执行单个数据抓取/分析步骤 |
| `POST` | `/api/execute_single_function` | 执行指定脚本并返回输出 |

### 3.4 策略回测（`/api/backtest`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/backtest/run_backtest` | 启动回测任务 |
| `GET` | `/api/backtest/task_status/<task_id>` | 查询回测进度 |
| `GET` | `/api/backtest/get_stock_list` | 获取可选股票列表 |
| `GET` | `/api/backtest/get_report` | 获取回测报告 |
| `GET` | `/api/backtest/get_chart/<path:chart_path>` | 获取回测图表 |
| `GET` | `/api/backtest/get_backtest_results` | 获取回测结果汇总 |

### 3.5 板块分析（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/sector_collect` | 触发板块数据采集 |
| `POST` | `/api/sector_analyze` | 触发板块分析 |
| `GET` | `/api/sector_task_status/<task_id>` | 查询板块任务进度 |
| `GET` | `/api/sector_list` | 获取可分析板块列表 |
| `GET` | `/api/sector_report/<task_id>` | 获取指定板块报告 |
| `GET` | `/api/sector_reports` | 列出全部板块报告 |
| `GET` | `/api/sector_report_content/<path:report_name>` | 读取板块报告内容 |

### 3.6 市场选股（`/api`，需 Tushare token）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `POST` | `/api/stock_selection/run` | 启动全市场选股任务 |
| `GET` | `/api/stock_selection/task_status/<task_id>` | 查询选股进度 |
| `GET` | `/api/stock_selection/get_result` | 获取选股结果 |

### 3.7 自选股管理（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/watchlist/get` | 获取关注列表 |
| `POST` | `/api/watchlist/add` | 添加关注股票 |
| `POST` | `/api/watchlist/remove` | 移除关注股票 |

### 3.8 交易记录（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/trading_records/<stock_code>` | 查询指定股票的交易记录 |
| `POST` | `/api/add_trading_record` | 新增买卖记录 |

### 3.9 报告查看（`/api`）

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| `GET` | `/api/stocks` | 获取已有数据的股票列表 |
| `GET` | `/api/stock_reports/<stock_code>` | 获取该股票的报告列表 |

---

## 四、运维维护

### 4.1 后台常驻运行

Web 服务默认前台运行，关闭终端即停止。长期使用建议：

**macOS / Linux（nohup）**

```bash
nohup python web_ui.py > log/web_ui.log 2>&1 &
```

**macOS / Linux（tmux，便于随时查看输出）**

```bash
tmux new -s gpana
python web_ui.py
# 按 Ctrl+B 再按 D 脱离；tmux attach -t gpana 可重新进入
```

> ⚠️ **安全提醒**：`web_ui.py` 当前以 `debug=True` 监听 `0.0.0.0`。
> **正式长期运行前请先改为** `app.run(host='127.0.0.1', port=8081, debug=False)`，
> 详见 [README.md 的安全注意事项](README.md#-安全注意事项)。

### 4.2 Ollama 服务常驻

AI 功能依赖 Ollama，若它未运行，所有 AI 分析都会失败。

```bash
# 检查是否在运行
ollama list

# 未运行时启动
ollama serve

# macOS 也可用 brew services 常驻
brew services start ollama
```

### 4.3 更新代码

```bash
git pull origin main
pip install -r requirements.txt --upgrade
```

### 4.4 数据备份

核心资产是 `data/`（分析结果）、`config.py`（配置）、`trading_records.py`（持仓记录）：

```bash
tar -czf gpana_backup_$(date +%Y%m%d).tar.gz data/ config.py trading_records.py watchlist.py
```

### 4.5 日志与空间清理

```bash
# 清理日志
rm -rf log/*.log

# 查看数据目录占用
du -sh data/
```

> 💡 长期运行后 `data/` 会持续增长（每次分析都会生成带时间戳的新报告）。
> 建议定期清理旧报告，只保留最近若干次。

### 4.6 端口占用排查

```bash
# 查看 8081 端口占用
lsof -i :8081                    # macOS / Linux
netstat -ano | findstr :8081     # Windows
```

端口被占用时，编辑 `web_ui.py` 最后一行修改 `port` 值。

---

## 五、安全注意事项

完整说明见 **[README.md 的安全注意事项](README.md#-安全注意事项)**，核心三条：

1. **不要以 `debug=True` 暴露到公网** —— Werkzeug 调试器可执行任意代码
2. **Tushare token 不要提交到仓库** —— `stocks_filter/step1_daily.py` 和 `step2_daily_basic.py` 是被跟踪文件
3. **分发前清理个人数据** —— `data/`、`config.py`、`trading_records.py` 含真实持仓信息

---

## 六、相关文档

| 文档 | 说明 |
|:---|:---|
| [README.md](README.md) | **部署与使用主文档**（11 步流程 + FAQ） |
| [CHANGELOG.md](CHANGELOG.md) | 版本变更记录 |
| [程序功能说明.md](程序功能说明.md) | 各模块功能详解 |
| [操作流程.md](操作流程.md) | 操作流程说明 |
| [说明书.md](说明书.md) | 完整使用说明书 |
| [SECURITY.md](SECURITY.md) | 安全政策 |
