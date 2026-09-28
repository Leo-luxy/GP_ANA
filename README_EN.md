# GP_ANA — AI-Powered A-Share Analysis System

**Current version: v1.5.0**

[中文](README.md) ｜ **English**

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9--3.12-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/Platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg" alt="Platform">
  <img src="https://img.shields.io/badge/AI-Ollama%20%7C%20Fully%20Local-orange.svg" alt="AI">
</p>

---

## 📖 What Is This

GP_ANA is an **A-share investment decision system that runs entirely on your own computer**.

It automatically collects the data scattered across dozens of sources — price action, financial statements,
capital flows, margin trading, shareholder structure, analyst research — feeds it to a **local large language model**
for multi-dimensional analysis, and produces a concrete, position-aware trading plan.

**In one sentence: it compresses the judgement you'd normally assemble by visiting a dozen websites and reading
dozens of financial reports into a single report you can read in a few minutes.**

> **First time here?** Jump straight to [🚀 Step-by-Step Deployment](#-step-by-step-deployment). It takes about
> 20 minutes end to end (excluding AI model download time).
>
> **Want to understand the internals?** See **[Introduction.md](Introduction.md)** — architecture, algorithms,
> data structures and design decisions.

---

## ✨ Features

### 1️⃣ Five-Dimensional Analysis — It's Not Just Candlesticks

Making decisions from OHLC data alone is fragile. GP_ANA evaluates five dimensions simultaneously, and each one
emits a **structured verdict** (bullish/bearish/neutral + confidence + anomalies) rather than a pile of raw numbers:

| Dimension | Weight | What it answers |
|:---|--:|:---|
| 📈 **Technical Trend** | **40%** | Is there a trend? Overbought or oversold? Where are the key levels? |
| 💰 **Financial Quality** | 25% | Is the profit real cash? Is growth sustainable? Is leverage dangerous? |
| 🌡️ **Sentiment & Valuation** | 15% | Are institutions buying or selling? Where does valuation sit? |
| 🏢 **Shareholder Structure** | 10% | Is ownership concentrated or dispersed? Are institutions accumulating or exiting? |
| 📰 **Analyst Research** | 10% | How are ratings distributed? How are target prices and forecasts moving? |

### 2️⃣ Two-Layer AI Decision — Argue First, Then Act

This is the single biggest difference between GP_ANA and an ordinary "report generator".

```
Layer 1: Conflict Detection
  Isolate only the conclusions that【contradict each other】across the five dimensions
  Role: hedge fund risk manager
  Output: what is the logic behind this contradiction? Which metric should we watch?

          ↓ only conclusions and your real cost basis are passed down

Layer 2: Trading Plan
  Role: trading coach
  Hard constraint: vague advice is forbidden
  Output: an actionable scenario plan — "if the price fails to hold 27.6 within 3 sessions, cut to half position"
```

**Why design it this way?** If you dump tens of thousands of words of reports into an LLM, it degrades into a
*summarizer* — and when it meets conflicting opinions it produces a fence-sitting conclusion.
Isolating the contradictions for the model to reason about, then grounding the advice in your **actual P&L**,
plays to what LLMs are genuinely good at.

### 3️⃣ Technical-Led, Others for Risk Avoidance

The other four dimensions **never generate buy signals on their own** — they hold a veto only.
The same data, three ways of using it:

| Mode | Timeframe | Technical | Financial | Shareholder | Sentiment |
|:---|:---|--:|--:|--:|--:|
| **Short-term** | < 1 month | **80%** | 0% | 0% | 20% |
| **Medium-term** | 1–6 months | **60%** | 30% | 10% | 0% |
| **Long-term** | > 6 months | 20% | **50%** | **30%** | 0% |

Risk thresholds adjust with the mode automatically. Debt-to-asset ratio, for example:
80% tolerated short-term, 70% medium-term, only 60% long-term.

### 4️⃣ Fully Local Inference — Your Data Never Leaves Your Machine

- AI inference runs on **your local Ollama** — **no cloud API key required**
- Market data comes straight from public financial endpoints
- Your cost basis, trade records and analysis results **stay on your disk only**

> This is a deliberate design choice: investment decisions involve personal financial information,
> and that should never be uploaded to a third-party AI service.

### 5️⃣ Multi-Source with Automatic Failover

A single data source going down shouldn't blind you. GP_ANA uses **redundant sources** for critical data:

- Quotes come from both Sina Finance and akshare; if the primary fails it fails over automatically
- Valuation data has a dual-path fallback
- Every collection step is exception-isolated — **one failure won't crash the whole run**
- All collectors are **incremental**: they fetch only new data, never re-download

### 6️⃣ Whole-Market Stock Screening Pipeline

Don't want to stare only at your watchlist? There's a complete pipeline built in:

```
Tushare whole-market daily  →  merge basic metrics  →  multi-condition filter  →  per-stock backtest  →  final holdings
        (5,500+ stocks)        (mkt cap/PE/PB)        (price/turnover/          (real historical
                                                       amplitude)                backtest)
```

### 7️⃣ Strategy Backtesting + Live Monitoring

- Full backtest of the trend-following strategy, with equity curve, Sharpe ratio and max drawdown
- Entry/exit use **symmetric dual signals**: entry on trend confirmation (bullish structure + volume + ADX + MACD),
  exit on trend termination (break of 10-day low, or MA death cross with MACD turning negative)
- **3-trading-day cooldown** after an exit, preventing the self-contradictory "just sold, now buy" prompts
- All protective stops retained: time stop / peak drawdown / ATR stop / trailing take-profit / partial take-profit

### 8️⃣ 20+ Professional Charts, Generated Automatically

Every stock gets price/volume charts, a technical indicator panel, Bollinger bands, a correlation heatmap,
signal-effectiveness analysis, support/resistance levels, trend channels, AI price predictions and feature
importance — viewable in the browser or exportable for reports.

### How It Compares

| Aspect | Traditional trading software | **GP_ANA** |
|:---|:---|:---|
| Data sources | Single platform | 20+ collectors, multi-source with failover |
| Analysis dimensions | Candlesticks only | **Five dimensions**: financial + sentiment/valuation + technical + shareholder + research |
| AI decision | ❌ | ✅ **Two-layer**: conflict detection → position-aware trading plan |
| Strategy validation | Manual review | Automated backtest + live monitoring |
| Stock screening | Manual browsing | Whole-market filter → backtest → final holdings |
| Data privacy | Uploaded to the cloud | ✅ **Fully local inference**, positions never leave your machine |
| Cost | Subscription fee | Free & open source + local model |

---

## 🖥️ Screenshots

### Full Analysis & Quick Analysis
<p align="center">
  <img src="assets/screenshots/完整分析.png" alt="Full Analysis" width="45%">
  &nbsp;
  <img src="assets/screenshots/快速分析.png" alt="Quick Analysis" width="45%">
</p>

### Detailed Mode & Single Function
<p align="center">
  <img src="assets/screenshots/详细模式.png" alt="Detailed Mode" width="45%">
  &nbsp;
  <img src="assets/screenshots/单功能执行.png" alt="Single Function" width="45%">
</p>

### Backtest & Stock Screening
<p align="center">
  <img src="assets/screenshots/策略回测.png" alt="Backtest" width="45%">
  &nbsp;
  <img src="assets/screenshots/市场选股.png" alt="Stock Screening" width="45%">
</p>

### Sector Analysis & Watchlist
<p align="center">
  <img src="assets/screenshots/板块分析.png" alt="Sector Analysis" width="45%">
  &nbsp;
  <img src="assets/screenshots/关注股票.png" alt="Watchlist" width="45%">
</p>

### Report Viewer & Trade Records
<p align="center">
  <img src="assets/screenshots/报告查看.png" alt="Report Viewer" width="45%">
  &nbsp;
  <img src="assets/screenshots/买卖记录管理.png" alt="Trade Records" width="45%">
</p>

---

## 🚀 Step-by-Step Deployment

> About 20 minutes end to end. Every step gives you the **exact commands** and **which file to edit, on which line**.

### Step 0: Check that your machine qualifies

| Item | Requirement | Notes |
|:---|:---|:---|
| **OS** | macOS / Linux / Windows | macOS is the least painful |
| **Python** | **3.9 – 3.12** (3.10 / 3.11 recommended) | ⚠️ **3.13 is not supported** — see below |
| **RAM** | ≥ 8 GB | ≥ 32 GB recommended if you run local LLMs |
| **Disk** | ≥ 5 GB | Excludes the AI model; the model itself can exceed 20 GB |
| **Network** | Access to Chinese financial sites | Sources are Eastmoney / akshare / Sina / Tushare |

Check your Python version first:

```bash
python3 --version
```

> ⚠️ **Why not Python 3.13?**
> The dependency list pins `numpy==1.26.3`, which only ships prebuilt wheels for Python 3.9 – 3.12.
> On 3.13 it falls back to compiling from source, which usually fails.
> If you must use 3.13, change `numpy==1.26.3` to `numpy>=2.1` in `requirements.txt` (not thoroughly tested).

If your version doesn't fit, create a dedicated conda environment:

```bash
conda create -n gpana python=3.10 -y
conda activate gpana
```

---

### Step 1: Get the code

```bash
git clone https://github.com/Leo-luxy/GP_ANA.git
cd GP_ANA
```

All subsequent commands are run from this directory.

---

### Step 2: Create a virtual environment

Keeps your system Python clean:

```bash
# Create
python3 -m venv venv

# Activate — macOS / Linux
source venv/bin/activate

# Activate — Windows
venv\Scripts\activate
```

Once activated, `(venv)` appears at the start of your prompt.

---

### Step 3: Install the TA-Lib system library (the usual sticking point)

GP_ANA uses `TA-Lib` to compute 40+ technical indicators. **It has a C library underneath, so you must install
the system library before the Python package** — doing it in the wrong order always fails.

**macOS:**

```bash
brew install ta-lib
```

**Ubuntu / Debian:** (no prebuilt package in the official repos — build from source)

```bash
sudo apt-get update
sudo apt-get install -y build-essential wget
wget https://github.com/ta-lib/ta-lib/releases/download/v0.6.4/ta-lib-0.6.4-src.tar.gz
tar -xzf ta-lib-0.6.4-src.tar.gz
cd ta-lib-0.6.4/
./configure --prefix=/usr
make
sudo make install
cd ..
```

**Windows:** the easiest route is a prebuilt wheel (pick the file matching your Python version and architecture):

```
https://github.com/cgohlke/talib-build/releases
```

```bash
pip install TA_Lib-0.6.8-cp310-cp310-win_amd64.whl
```

**Verify it worked** (printing a version number means success):

```bash
python3 -c "import talib; print(talib.__version__)"
```

> Don't proceed until this passes — otherwise every technical analysis feature will crash later.

---

### Step 4: Install Python dependencies

```bash
pip install -r requirements.txt
```

Takes roughly 3–10 minutes. **Nothing extra needs to be installed manually** (`flask` is already included).

If an individual package fails, retry it on its own:

```bash
pip install akshare==1.18.39
```

---

### Step 5: Install and start Ollama (required for AI features) ⭐

All AI analysis, the five-dimensional reasoning and the two-layer decision depend on a local LLM.

**1) Install Ollama** — visit <https://ollama.com/download>, or on macOS `brew install ollama`

**2) Start the service**

```bash
ollama serve
```

It listens on `http://localhost:11434`. **It's best to keep it running** (on macOS you can use
`brew services start ollama`).

**3) Pull a model**

> ⚠️ **Note**: the default model name in `config.example.py` is a custom model from the author's own machine and
> **does not exist in the public Ollama registry** — pulling it directly will fail. Pull a model you can actually
> get, then point the config at it (covered in the next step).
>
> 💡 You can also browse the Ollama website and pick any model you like.

```bash
# Pick one based on your available memory
ollama pull qwen3:8b          # ~5 GB, runs on 8GB RAM, fast
ollama pull qwen3:32b         # ~20 GB, better quality, 32GB+ RAM recommended
ollama pull deepseek-r1:32b   # alternative
```

**4) Confirm the model is ready**

```bash
ollama list
```

**Note down the model name you pulled** — you'll need it in the next step.

---

### Step 6: Create the config file `config.py` ⭐

The repository does **not** ship `config.py` (it holds your personal stock list and is excluded by `.gitignore`).
Only a template is provided. **This step is: copy the template, then change two things.**

**Copy the template:**

```bash
# macOS / Linux
cp config.example.py config.py

# Windows
copy config.example.py config.py
```

**Then edit `config.py` — at minimum these two places:**

**① `STOCK_TICKERS` — the stocks you want analysed**

```python
# config.py, around line 9
STOCK_TICKERS = {
    'byd':    '002594.SZ',   # key name is arbitrary; value must be "6-digit code + exchange suffix"
    'lanxi':  '300433.SZ',
    # add more
}
```

> **Exchange suffix rule**: codes starting with `6` → `.SH` (Shanghai); codes starting with `0` or `3` → `.SZ` (Shenzhen).

**② `AI_CONFIG.model` — the model name you actually pulled in Step 5**

```python
# config.py, around line 57
AI_CONFIG = {
    'base_url': 'http://localhost:11434',   # Ollama address — no change needed locally
    'model': 'qwen3:8b',                    # ← set this to your model name
    'temperature': 0.3,
    'max_tokens': 8192,
    'trading_strategy': 'neutral',          # see table below
    'fallback_models': ['qwen3:8b'],        # ← same here
}
```

`trading_strategy` accepts four values and determines the lens the AI analyses through:

| Value | Meaning |
|:---|:---|
| `neutral` | Objective and balanced (default) — weighs bullish and bearish signals together |
| `trend_following` | Trades only when a clear trend exists |
| `mean_reversion` | Fades extremes, buying weakness and selling strength |
| `swing` | Holds for days to weeks, capturing daily-level swings |

---

### Step 7: Create `trading_records.py` (optional but strongly recommended)

**Why bother:** the second decision layer reads your **real cost basis and P&L**.
Without it the AI can only talk about fundamentals in the abstract; with it, you get advice like
"you're down 27% — here's whether to cut or add".

**Copy the template:**

```bash
# macOS / Linux
cp trading_records.example.py trading_records.py

# Windows
copy trading_records.example.py trading_records.py
```

**Then edit `trading_records.py` with your real trades:**

```python
# trading_records.py
TRADING_RECORDS = {
    '600519.SH': [
        {'date': '2026-01-15', 'type': 'buy',  'price': 1500.00, 'shares': 100},
        {'date': '2026-02-20', 'type': 'sell', 'price': 1580.00, 'shares': 50},
    ],
    '000858.SZ': [
        {'date': '2026-03-01', 'type': 'buy',  'price': 130.00, 'shares': 500},
    ],
}
```

| Field | Meaning |
|:---|:---|
| `date` | Trade date, `YYYY-MM-DD` |
| `type` | `buy` or `sell` |
| `price` | Execution price |
| `shares` | Number of shares |

> You can skip this file and define `TRADING_RECORDS = {...}` directly in `config.py` instead, commenting out the
> `from trading_records import TRADING_RECORDS` line.
>
> 💡 You can also add and remove records from the Web UI under **Trade Records** — no need to hand-edit the file.

---

### Step 8: Configure a Tushare token (**only needed for Stock Screening**) ⭐

**This is the only credential the system ever asks for.** Every other data source (akshare, Eastmoney, Sina) is a
free public endpoint requiring **no key at all**; AI runs on local Ollama and needs **no cloud API key either**.

**If you don't plan to use Stock Screening, skip this step entirely.**

**1) Apply**: register and sign in at <https://tushare.pro/> → "Profile → API TOKEN" → copy your token

**2) Put it in two files** (note: **two**):

```python
# stocks_filter/step1_daily.py, line 15
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"     # ← replace with your real token
```

```python
# stocks_filter/step2_daily_basic.py, line 14
TUSHARE_TOKEN = "YOUR_TUSHARE_TOKEN"     # ← same token here
```

**3) Mind the Tushare points system**: the whole-market daily endpoint (`pro.daily()`) requires **120+ points**.
New accounts don't have enough by default and will see a permission error — complete the points tasks on the
Tushare website first.

> ⚠️ **Security note**: these two files **are tracked by git**. If you ever commit your changes back to a public
> repository, change the token back to `YOUR_TUSHARE_TOKEN` first, or switch to reading it from an environment
> variable. See [Security Notes](#-security-notes).

---

### Step 9: Create the data directories

The program does not create these automatically — **you must create them manually**:

```bash
mkdir -p data log
```

- `data/` — all market data, analysis reports and charts live here
- `log/` — runtime logs

---

### Step 10: Start the web interface

```bash
python web_ui.py
```

You'll know it worked when you see:

```
 * Running on http://0.0.0.0:8081
```

**Open your browser at <http://localhost:8081>**

> ⚠️ The port is **8081**, and it is **hard-coded on the last line of `web_ui.py` — there is no command-line
> flag to change it**. If 8081 is taken, edit the `port=8081` value on that line directly.

---

### Step 11: Start using it

> 💡 **The features in the interface are independent of one another — there is no required order.**
> Apart from the one marked "⚠️ first-time setup required", everything works as soon as you open it.
> They're grouped below by purpose.

#### 🔍 Analysing a single stock

Two entry points with different purposes:

| Feature | Purpose | Time | Notes |
|:---|:---|:---|:---|
| **Full Analysis** | First evaluation of a new stock | 3–5 min | Collects everything → five dimensions → two-layer decision → full trading plan |
| **Quick Analysis** | Daily post-close review | ~30 sec | Updates candles automatically, then **technical only**; pick a short/medium/long lens |

**How**: click **Full Analysis** or **Quick Analysis** → enter the 6-digit code (e.g. `300433`) → start.
Results show up under **Report Viewer**.

> 💡 **For a new stock, run Full Analysis once first** — it builds the complete dataset for that stock.
> After that, Quick Analysis is enough for daily monitoring.

#### 🏢 Sector Analysis ⚠️ first-time setup required

**You must do this once before the feature is usable**, otherwise the sector dropdown will be empty:

Click **Sector Analysis** → find **Update Sector Data** → click it → wait for it to finish (~1–2 min).

After that you can pick a sector type (broad index / industry / concept / Hong Kong) for AI deep analysis,
which takes ~2–3 min.

#### 🎯 Stock Screening — a completely independent feature

**It has nothing to do with the per-stock analysis above.** It's a standalone whole-market pipeline:

```
Whole-market daily (5,500+ stocks) → merge basic metrics → multi-condition filter → per-stock backtest → final holdings
```

**Prerequisite**: you've completed Step 8 (Tushare token).

**How**: click **Stock Screening** → tick your filter criteria → run. Takes ~3–5 min.

#### ⭐ Watchlist (optional enhancement)

Maintains a list of stocks you follow. **It's an optional convenience, not a prerequisite for anything else**:
once populated, backtests and analyses **prefer stocks from this list**, saving you from retyping codes.

Click **Watchlist** to add or remove — effective immediately.

#### 💰 Trade Records (worth filling in)

Record your actual trades. **This directly improves the quality of the AI's advice**: the second decision layer
reads your cost basis and gives advice grounded in your **real P&L** ("you're down 27% — cut or add?"),
rather than abstract fundamentals.

Click **Trade Records** → pick date / type / price / shares → add (the date defaults to today).

#### 📊 Strategy Backtest

**How**: click **Strategy Backtest** → choose a mode (full flow / quick backtest) → decide whether to use the
simplified strategy → start. Takes ~1–2 min.

When it finishes you'll see the **monitoring report** and per-stock backtest charts (click a card to view).

#### 🗂 Report Viewer

Browse every analysis report generated so far, organised by stock. You need at least one report for it to show
anything.

#### 🛠 Detailed Mode / Single Function

| Feature | Purpose |
|:---|:---|
| **Detailed Mode** | Inspect raw data and intermediate results for a single stock |
| **Single Function** | Run one specific script on its own — useful for troubleshooting |

---

**Time estimates at a glance:**

| Feature | Time |
|:---|:---|
| Full Analysis | 3–5 min |
| Quick Analysis | ~30 sec |
| Sector Analysis | 2–3 min (plus 1–2 min first-time data collection) |
| Stock Screening | 3–5 min |
| Strategy Backtest | 1–2 min |
| Watchlist / Trade Records / Report Viewer | Instant |

---

### Step 12: Command-line data initialisation (optional)

If you'd rather prepare data from the CLI before opening the UI:

```bash
# Fetch and update daily data (quotes / capital flow / margin / valuation / indicators)
python check_data_updates.py --mode daily --ticker 300433.SZ

# Fetch low-frequency data (company info / financials / shareholders / northbound)
python check_data_updates.py --mode periodic --ticker 300433.SZ

# Sector data
python sector_data_collector.py --type broad_index
python sector_data_collector.py --type industry --top 30
```

Omitting `--ticker` processes every stock in `STOCK_TICKERS` from `config.py`.

---

## 📁 Which File Holds What (Quick Reference)

After deployment you only need to care about these files:

| File | Where it comes from | What you change | Required? |
|:---|:---|:---|:---:|
| **`config.py`** | Copy from `config.example.py` | ① `STOCK_TICKERS` — your stock codes<br>② `AI_CONFIG.model` — your model name | ✅ **Yes** |
| **`trading_records.py`** | Copy from `trading_records.example.py` | Your real trades, in the documented format | Recommended |
| **`stocks_filter/step1_daily.py`** | Ships with the repo | Line 15, `TUSHARE_TOKEN` | Stock screening only |
| **`stocks_filter/step2_daily_basic.py`** | Ships with the repo | Line 14, `TUSHARE_TOKEN` | Stock screening only |
| **`watchlist.py`** | Ships with the repo | Your watchlist (easier via the Web UI) | No |
| `data/`, `log/` | Create manually | — | ✅ **Yes** |

**Other tunable parameters** (all in `config.py`; defaults work fine):

| Config block | Purpose |
|:---|:---|
| `HISTORY_DATE_RANGE` | Restrict the date range of historical data for a given stock (full history by default) |
| `TECHNICAL_INDICATORS` | Indicator periods (MA / RSI / MACD / KDJ, etc.) |
| `STRATEGY_CONFIG` | Backtest parameters (initial capital, buy/sell thresholds) |
| `STRATEGY_PROMPTS` | The prompt templates for the four strategy lenses — tune to taste |

> 📌 **`config.py` and `trading_records.py` contain your personal holdings. Both are listed in `.gitignore`
> and will not be committed.**

---

## 🔧 Troubleshooting

### Q1: `pip install TA-Lib` fails, complaining it can't find `ta_lib.h`

**Cause**: you installed the Python package without the underlying C library.

**Fix**: go back to [Step 3](#step-3-install-the-ta-lib-system-library-the-usual-sticking-point), install the
system library first, then `pip install TA-Lib==0.6.8`.

---

### Q2: Startup fails with `ModuleNotFoundError: No module named 'flask'`

**Cause**: older versions of `requirements.txt` omitted `flask` (**fixed in the current version**).

**Fix**:

```bash
pip install flask
```

---

### Q3: Installation fails on Python 3.13 (numpy compilation errors)

**Cause**: `numpy==1.26.3` does not support Python 3.13.

**Fix**: switch to Python 3.9 – 3.12, or change the pin to `numpy>=2.1` and reinstall (not thoroughly tested).

---

### Q4: The browser can't open the page / the port isn't reachable

1. The port is **8081** — go to <http://localhost:8081>
2. Check what's using it: `lsof -i :8081` (Windows: `netstat -ano | findstr :8081`)
3. To change the port, edit the last line of `web_ui.py`

---

### Q5: AI analysis keeps failing or timing out

1. Is Ollama running? `ollama list` — if it errors, run `ollama serve` first
2. Does `AI_CONFIG.model` in `config.py` **exactly** match the model you pulled? (most common cause)
3. Model too large and too slow? Try a smaller one, e.g. `qwen3:8b`
4. The first load of a model takes time — give it a moment

---

### Q6: The sector list on the Sector Analysis page is empty

**Cause**: sector data hasn't been collected yet; first-time initialisation is required.

**Fix**: click **Sector Analysis → Update Sector Data** in the UI, or run:

```bash
python sector_data_collector.py --type broad_index
python sector_data_collector.py --type industry --top 30
```

---

### Q7: Stock screening reports insufficient Tushare permissions

**Cause**: `pro.daily()` requires **120+ points**; new accounts don't have enough by default.

**Fix**: complete the points tasks or upgrade at <https://tushare.pro/>; also confirm the token is set in
**both** files.

---

### Q8: Network errors / timeouts when fetching data

1. Check you can reach Eastmoney and Sina Finance
2. **Turn off any system proxy or VPN** (the code actively clears proxy environment variables, but a global
   proxy can still interfere)
3. Upgrade akshare: `pip install --upgrade akshare`
4. Retry later — these endpoints are rate-limited

---

### Q9: `config.py` is missing

**Cause**: for privacy reasons, `config.py` and `trading_records.py` are not shipped in the repository.

**Fix**: see [Step 6](#step-6-create-the-config-file-configpy-) and
[Step 7](#step-7-create-trading_recordspy-optional-but-strongly-recommended) to copy the templates.

---

## ⚠️ Security Notes

### 🔴 Read before deploying

**1) `web_ui.py` runs Flask in debug mode bound to `0.0.0.0`**

The current version uses `app.run(host='0.0.0.0', port=8081, debug=True)`, which means:

- `debug=True` enables the Werkzeug debugger, exposing an **interactive console that can execute arbitrary code**
  on error pages
- `host='0.0.0.0'` binds to **all network interfaces** — other devices on your LAN can reach it

**⚠️ Do not run this on the public internet or on an untrusted network.** For long-running use, change it to:

```python
# last line of web_ui.py
app.run(host='127.0.0.1', port=8081, debug=False)   # localhost only, debugger off
```

**2) Never commit your Tushare token**

`stocks_filter/step1_daily.py` and `stocks_filter/step2_daily_basic.py` **are tracked by git**.
Once you put a real token in them and `git commit`, the token is permanently in the commit history.

- Always change it back to `"YOUR_TUSHARE_TOKEN"` before committing
- Better still, read it from an environment variable:

```python
import os
TUSHARE_TOKEN = os.environ.get("TUSHARE_TOKEN", "")
```

- If you have already committed it, **reset the token** on the Tushare website immediately

**3) `config.py` and `trading_records.py` hold personal portfolio data**

Both are in `.gitignore` — **do not remove them from it, and do not commit them manually**.

**4) The `data/` directory holds all analysis results and position decisions**

Also in `.gitignore`. Before sharing or packaging the project, consider clearing it:

```bash
rm -rf data/*      # ⚠️ deletes every generated report and chart
```

### 🟢 Privacy by design

Worth calling out: **all AI inference happens locally in Ollama**, market data comes from public financial
endpoints, and **your positions and analysis results are never uploaded to any third-party AI service**.

### Other recommendations

1. Don't expose the service port on a public network
2. Update dependencies periodically: `pip install -r requirements.txt --upgrade`
3. Restrict the data directory to your own user: `chmod 700 data`

---

## 💻 Command-Line Cheatsheet

```bash
# Start the web interface
python web_ui.py

# Data updates
python check_data_updates.py --mode daily    --ticker 300433.SZ   # daily data
python check_data_updates.py --mode periodic --ticker 300433.SZ   # low-frequency data

# Batch analysis
python batch_analyze.py --mode daily    --ticker 300433.SZ   # daily dimensions (6 steps)
python batch_analyze.py --mode periodic --ticker 300433.SZ   # low-frequency dimensions (3 steps)
python batch_analyze.py --mode all      --ticker 300433.SZ   # full pipeline (14 steps)

# Technical trend analysis (switchable strategy lens)
python analyze_technical_trend.py --strategy trend_following --ticker 300433.SZ
python analyze_technical_trend.py --strategy swing           --ticker 300433.SZ

# Sector analysis
python sector_data_collector.py --type broad_index            # collect broad index data
python sector_data_collector.py --type industry --top 30      # collect industry sectors
python analyze_sector.py --mode single --sector BK0477        # single-sector deep dive
python analyze_sector.py --mode broad                         # whole-market overview

# Stock screening (4-step pipeline; fill in the Tushare token first)
python stocks_filter/step1_daily.py           # 1. whole-market daily data
python stocks_filter/step2_daily_basic.py     # 2. merge basic metrics (wait ~1h after step 1)
python stocks_filter/step3_filter.py          # 3. multi-condition filter
python stocks_filter/batch_backtest_filter.py # 4. batch backtest → final_holdings.csv
```

Omitting `--ticker` makes batch commands process every stock in `STOCK_TICKERS` from `config.py`.

> For the full module and API reference, see [Introduction.md](Introduction.md).

---

## 📄 Version History

| Version | Date | Highlights |
|------|------|---------|
| **v1.5.0** | 2026-09 | Documentation restructured into README + Introduction; backtest page now shows the latest report; task status persistence; dependency list corrected; redundant scripts removed |
| **v1.4.0** | 2026-06 | Whole-market screening + watchlist management; KDJ and sector data-freshness fixes; backtest enhancements (watchlist + company names); timeout control |
| **v1.3.0** | 2026-06 | Sector analysis: four sector types with AI analysis; Sina Finance data source; sector API |
| **v1.2.0** | 2026-05 | Architecture refactor: unified entry point, Process/ engine, two-layer decision, quick analysis, backtest system |
| v1.1.0 | 2026-03 | 41 modules: web interface, 12 new collectors, 5 new analysis engines |
| v1.0.1 | 2026-02 | 18 modules: data collection + basic analysis |

See [CHANGELOG.md](CHANGELOG.md) for details.

---

## 📚 Related Documents

| Document | Description |
|:---|:---|
| [**Introduction.md**](Introduction.md) | **Technical deep dive** — architecture, five-dimensional decision algorithms, module reference, data dictionary, API reference, design decisions |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [README.md](README.md) | Chinese documentation (主文档) |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guide |
| [SECURITY.md](SECURITY.md) | Security policy |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Code of conduct |

---

## 📜 License

Released under the [MIT License](LICENSE).

---

## ⚖️ Disclaimer

This project is a **technical learning and research tool**. None of its AI analysis, trading suggestions or
backtest results **constitute investment advice**. Markets carry risk; invest carefully. Any investment decisions
and their consequences remain solely your own responsibility.

---

<p align="center">
  <sub>Made with ❤️ for quantitative investors</sub>
</p>
