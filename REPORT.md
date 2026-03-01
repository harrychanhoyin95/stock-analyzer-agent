# Stock Analyzer Agent — Technical Report

## 1. Agent Framework & Architecture

The agent is built on **LangChain** with **LangGraph** as the underlying execution engine. `create_agent` from `langchain.agents` constructs a LangGraph `StateGraph` with two nodes — an `agent` node (the LLM) and a `tools` node — connected by conditional edges. After each LLM response, the graph checks whether a tool call was requested: if yes, it routes to the tools node and feeds the result back to the LLM; if no, execution terminates. This is the **ReAct** (Reason + Act) loop.

```
┌─────────┐     tool call?     ┌───────┐
│  agent  │ ────── yes ──────► │ tools │
│  (LLM)  │ ◄──── result ───── └───────┘
└─────────┘
     │
    no tool call
     │
     ▼
   END
```

Six tools are registered at agent creation time: `get_top_gainers`, `get_stock_history`, `get_stock_news`, `python_analyzer`, `generate_chart`, and `send_email`. The LLM selects tools and constructs their arguments autonomously based on the system prompt and conversation state.

**LLM backend:** The agent uses OpenRouter via `ChatOpenAI` with an `openai_api_base` override, making the model layer swappable without code changes. Four free models are configured in a priority list. On a rate limit error (HTTP 428), the agent automatically advances to the next model in the list — without retrying the same one — preserving forward progress across a session.

**Observability:** Langfuse (self-hosted) was chosen over LangSmith for GUI trace visibility at no cost. The `CallbackHandler` is injected per `agent.stream()` call. Langfuse reachability is checked at startup — the app exits immediately if unavailable, preventing silent observability failure.

**System prompt:** Injected via the `system_prompt=` parameter at agent creation — not placed in the message history — so it does not pollute the tool context window or appear as a user turn.

## 2. Task Planning & Execution

The agent does not plan dynamically — it executes a **deterministic 7-step workflow** encoded in the system prompt. This is a deliberate design choice: free-tier LLMs are unreliable at open-ended planning, so the sequencing is fixed in natural language instructions while the LLM's role is constrained to argument construction and prose generation.

The information flow is strictly forward — each step's output becomes the input to the next:

```
get_top_gainers
      │ symbol
      ▼
get_stock_history (symbol + SPY)     get_stock_news (symbol)
      │ OHLCV data                         │ headlines
      └──────────────┬──────────────────────┘
                     ▼
              python_analyzer
              (metrics payload)
                     │ computed metrics
                     ▼
              generate_chart
              (chart PNG path)
                     │ chart_path
                     ▼
               send_email
```

**Tool selection:** The LLM constructs tool arguments from prior results in the message history. For `python_analyzer`, the system prompt defines the exact JSON payload schema — including key names, types, and nesting — and explicitly forbids keys that do not exist (`"exchange"`, `"news"`, `"change_pct"`). This prevents the LLM from hallucinating plausible-but-wrong fields that would silently break the sandbox code.

**Mandatory termination:** `send_email` is declared with a `CRITICAL RULE` in the system prompt. Without this constraint, weaker models tend to end the conversation with a text summary instead of executing the final tool call.

## 3. Dynamic Code Generation & Execution

The `python_analyzer` tool enables the agent to perform quantitative analysis without hard-coding metric calculations. The LLM **generates Python code at runtime** as a string argument, synthesized from the data shape described in the system prompt and the OHLCV payload from prior tool outputs.

**Why not `exec()`:** LLM-generated code running on the host can read environment variables, make outbound network calls, write to the filesystem, or consume unbounded resources. All generated code runs inside a **fresh Docker container** per invocation instead.

The execution flow is:

```
LLM generates code string
        │
        ▼
Pydantic validates input payload     ← rejects malformed data before container launch
        │
        ▼
Code written to temp file
        │
        ▼
docker run --rm
  --network none          ← no outbound calls
  --memory 128m           ← memory cap
  --cpus 0.5              ← CPU cap
  -v /tmp/...:/sandbox:ro ← read-only mount
  stock-analyzer-sandbox
  python /sandbox/run.py
        │
        ▼
stdout captured → truncated to 20,000 bytes → returned to agent
```

**Sandbox image:** `python:3.13-slim` with only `pandas` and `numpy` installed — minimal attack surface, pinned versions. The container runs as `USER nobody`. The tool docstring instructs the LLM to use `print()` for all output; the 20,000-byte stdout cap and 15-second timeout ensure a single bad generation cannot flood the context window or hang the host.

## 4. Challenges & Solutions

**Rate limiting on free models:** Free OpenRouter models impose aggressive rate limits (HTTP 428). The agent maintains a candidate matrix of `model × API key` pairs and a sticky forward index. On any 428 error, the index advances to the next candidate — exhausting a slot once rather than retrying it — allowing the session to continue across multiple keys and models without restarting.

**LLM tool-calling reliability:** Free-tier models occasionally skip required tools, hallucinate invalid payload fields, or terminate early with a text response. Three mitigations were applied: (1) the system prompt defines the exact JSON schema for the `python_analyzer` payload including forbidden keys; (2) `send_email` is declared as the mandatory final action via a `CRITICAL RULE`; (3) the workflow is encoded as an ordered numbered list rather than left to the model to derive. Residual failure on the weakest models is accepted as a known limitation — a paid model like Claude Sonnet would eliminate most of these issues.

**Data sourcing — NASDAQ top gainers:** No free API reliably returns NASDAQ-only top gainers. `yfinance` provides an `EquityQuery` screener but has a documented server-side leakage bug (issue #2218) where non-NASDAQ stocks slip through. The fix is a client-side re-filter on exchange codes (`NMS`, `NGM`, `NCM`) and quote type, with Playwright scraping of Futunn as fallback.

**Security — code execution:** LLM-generated code on the host is a direct attack surface. A Docker sandbox addresses this (see Section 3). `subprocess.run` was chosen over the Docker Python SDK for fewer dependencies, simpler error handling, and no daemon socket exposure.

**Domain knowledge — finance indicators:** Standard retail analysis approaches were researched to define a computable metric set: total return, annualized volatility (σ × √252), volume spike ratio, intraday range percentage, and relative performance versus the SPY benchmark — all derivable from OHLCV data alone.

## 5. Error Handling & Reliability

Reliability is built into each layer independently so that a failure in one component degrades gracefully rather than aborting the run.

**Tool-level fallback chain:** Both `get_top_gainers` and `get_stock_history` follow the same pattern — yfinance primary, Playwright scraper automatic fallback on any exception or empty result. Both paths return identical dict shapes so the agent layer never knows which path was taken. The fallback can also be forced via `USE_SCRAPER=1`.

**Workflow-level recovery:** The system prompt encodes explicit recovery instructions for each failure scenario:
- `get_stock_history` fails → retry once with `1mo`; if still failing, report data unavailable
- SPY history fails → proceed without benchmark, omit relative performance section
- `generate_chart` fails → omit `chart_path`; email is still sent

**Structured errors and validation:** Every tool returns `{"error": message}` on failure rather than raising an exception, surfacing cleanly in the agent's message history. Pydantic validates all tool inputs at the boundary — for `python_analyzer`, this happens before the container is even launched, catching malformed payloads early.

**Sandbox isolation:** Each `python_analyzer` invocation runs in a fresh container with no shared state. Resource caps (memory, CPU, 15s timeout) ensure a single bad code generation cannot destabilize the host.

**Terminal gate:** `send_email` is always the final action regardless of what failed upstream — partial output is always delivered rather than silently dropped.
