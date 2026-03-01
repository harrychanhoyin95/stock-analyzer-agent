# Stock Analyzer Agent

An LLM-powered CLI that analyzes NASDAQ stocks, scrapes top gainers, runs sandboxed Python analysis, and emails an HTML report with an optional chart.

## How It Works

```
CLI (main.py)
    │
    ▼
LangGraph Agent  ──────────────────────────────────────────┐
    │                                                       │
    ├── get_stock_history   (yfinance OHLCV data)          │
    ├── get_top_gainers     (Playwright scrape, Yahoo)      │
    ├── get_stock_news      (news headlines)                │
    ├── python_analyzer     (Docker sandbox, pandas/numpy)  │
    ├── generate_chart      (matplotlib / mplfinance PNG)   │
    └── send_email          (Gmail SMTP, HTML + chart)      │
                                                            │
    ◄───────────────────────────────────────────────────────┘
    │
    ▼
Langfuse  (trace observability at localhost:3000)
```

The agent is built with LangChain + LangGraph (`create_agent`). It uses OpenRouter as the LLM provider (default: free-tier models with automatic rate-limit fallback across multiple API keys). Every run is traced in Langfuse, which must be running before the app starts.

## Tools

| Tool | What it does | Tech |
|---|---|---|
| `get_stock_history` | Fetches OHLCV price history for a ticker | yfinance |
| `get_top_gainers` | Scrapes the top NASDAQ gainers from Yahoo Finance | Playwright |
| `get_stock_news` | Fetches recent news headlines for a ticker | yfinance |
| `python_analyzer` | Executes arbitrary Python to analyze data | Docker sandbox (pandas, numpy) |
| `generate_chart` | Generates a line or candlestick chart as a PNG | matplotlib, mplfinance |
| `send_email` | Sends an HTML email with optional chart attachment | Gmail SMTP |

## Prerequisites

- Python 3.13
- [uv](https://docs.astral.sh/uv/) (package manager)
- Docker (for the Python sandbox and Langfuse)
- An [OpenRouter](https://openrouter.ai) API key
- A Gmail account with an [App Password](https://support.google.com/accounts/answer/185833) enabled

## Setup

**1. Clone the repo**

```bash
git clone <repo-url>
cd stock-analyzer-agent
```

**2. Configure environment variables**

Create a `.env` file in the project root:

```env
# OpenRouter — add up to 3 keys for rate-limit fallback
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_API_KEY_2=sk-or-...   # optional
OPENROUTER_API_KEY_3=sk-or-...   # optional

# Langfuse (self-hosted defaults — change if you customized docker-compose.yml)
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=http://localhost:3000

# Gmail SMTP
GMAIL_SENDER=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

**3. Start Langfuse**

```bash
docker compose up -d
```

Langfuse will be available at [http://localhost:3000](http://localhost:3000). Create an account, then a project, and copy the public/secret keys into your `.env`.

**4. Build the Python sandbox image**

```bash
docker build -t stock-analyzer-sandbox docker/sandbox/
```

**5. Install dependencies**

```bash
uv sync
```

**6. Install Playwright browsers**

```bash
uv run playwright install chromium
```

## Running

```bash
uv run python main.py
```

**CLI flags:**

| Flag | Default | Description |
|---|---|---|
| `--period` | `5d` | History period. One of: `1d` `5d` `1mo` `3mo` `6mo` `1y` `2y` `5y` `10y` |
| `--email` | hardcoded default | Comma-separated recipient email addresses |

**Examples:**

```bash
# Run a 1-month analysis
uv run python main.py --period 1mo

# Send to a different email
uv run python main.py --email analyst@example.com

# Multiple recipients
uv run python main.py --email alice@example.com,bob@example.com
```

## Observability

All agent runs are traced in Langfuse. Open [http://localhost:3000](http://localhost:3000) to inspect traces, tool calls, token usage, and latency for every run.

The app performs a health check against Langfuse on startup and exits early if it is not reachable — run `docker compose up -d` first.

## Rate Limit Fallback

The agent rotates across all configured `OPENROUTER_API_KEY_*` keys and the models listed in `main.py` when it hits a rate limit. It advances forward through the list and never retries an exhausted combination.
