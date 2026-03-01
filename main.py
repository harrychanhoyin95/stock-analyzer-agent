import argparse
import os
import sys
import time
from dataclasses import dataclass, field

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from openai import RateLimitError
from langfuse.langchain import CallbackHandler

from prompts.system import get_system_prompt
from tools import (
    get_stock_history,
    get_top_gainers,
    python_analyzer,
    send_email,
    get_stock_news,
    generate_chart,
)

load_dotenv()

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

def check_langfuse_health():
    """Check if LangFuse is running before starting the app."""
    try:
        response = httpx.get(f"{LANGFUSE_HOST}", timeout=5.0)
        if response.status_code == 200:
            return True
    except httpx.ConnectError:
        pass
    return False

if not check_langfuse_health():
    print(f"❌ LangFuse is not running at {LANGFUSE_HOST}")
    print("\nStart it with:")
    print("   docker compose up -d")
    print("\nThen try again.")
    sys.exit(1)

print(f"✓ LangFuse running at {LANGFUSE_HOST}\n")

langfuse_handler = CallbackHandler()

_MODELS = [
    # "anthropic/claude-sonnet-4.6",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "arcee-ai/trinity-large-preview:free",
    "arcee-ai/trinity-mini:free",
    "stepfun/step-3.5-flash:free",
]

_KEYS = [k for k in [
    os.getenv("OPENROUTER_API_KEY"),
    os.getenv("OPENROUTER_API_KEY_2"),
    os.getenv("OPENROUTER_API_KEY_3"),
] if k]

_CANDIDATES: list[tuple[str, str]] = [
    (model, key)
    for model in _MODELS
    for key in _KEYS
]

_current_idx = 0   # module-level sticky index — advances forward only

_REASONING_MODELS = {
    "nvidia/nemotron-3-nano-30b-a3b:free",
}


def _make_llm(model: str, key: str) -> ChatOpenAI:
    kwargs = {}
    if model in _REASONING_MODELS:
        kwargs["reasoning"] = {"max_tokens": 5000}
    return ChatOpenAI(
        model=model,
        openai_api_key=key,
        openai_api_base="https://openrouter.ai/api/v1",
        **kwargs,
    )


_VALID_PERIODS = {"1d", "5d", "1mo", "3mo", "6mo", "1y", "2y", "5y", "10y"}


@dataclass
class Config:
    period: str = "5d"
    recipients: list[str] = field(default_factory=lambda: ["harrychanhoyin95@gmail.com"])


def _parse_config() -> Config:
    parser = argparse.ArgumentParser(description="NASDAQ stock analyzer agent")
    parser.add_argument(
        "--period",
        type=str,
        default="5d",
        choices=sorted(_VALID_PERIODS),
        help="History period (default: 5d). One of: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y",
    )
    parser.add_argument("--email", type=str, default=None, help="Comma-separated recipient emails (default: harrychanhoyin95@gmail.com)")
    args = parser.parse_args()

    recipients = args.email.split(",") if args.email else ["harrychanhoyin95@gmail.com"]
    return Config(period=args.period, recipients=recipients)


def _make_agent(model: str, key: str, config: Config):
    return create_agent(
        model=_make_llm(model, key),
        tools=[
            get_stock_history,
            get_top_gainers,
            python_analyzer,
            send_email,
            get_stock_news,
            generate_chart,
        ],
        system_prompt=get_system_prompt(period=config.period, recipients=config.recipients),
    )


def run_agent(history, config: Config):
    global _current_idx

    while _current_idx < len(_CANDIDATES):
        model, key = _CANDIDATES[_current_idx]
        agent = _make_agent(model, key, config)

        try:
            final_state = None
            t = time.perf_counter()

            for chunk in agent.stream(
                {"messages": history},
                config={"callbacks": [langfuse_handler]},
                stream_mode="updates",
            ):
                elapsed = time.perf_counter() - t
                node_name = list(chunk.keys())[0]
                node_data = list(chunk.values())[0]

                if node_name == "tools":
                    for msg in node_data["messages"]:
                        print(f"[node: tools] → {msg.name} ({elapsed:.2f}s)")
                else:
                    print(f"[node: {node_name}] ({elapsed:.2f}s)")

                final_state = chunk
                t = time.perf_counter()

            return next(iter(final_state.values()))["messages"]

        except RateLimitError as e:
            print(f"Rate limited on {model} (key ...{key[-6:]}): {e}")
            _current_idx += 1
            if _current_idx >= len(_CANDIDATES):
                print("All models and keys exhausted.")
                raise
            next_model, next_key = _CANDIDATES[_current_idx]
            print(f"Switching to {next_model} (key ...{next_key[-6:]})\n")


if __name__ == "__main__":
    config = _parse_config()

    print(f"Running {config.period} NASDAQ analysis...\n")
    print(f"Recipients: {', '.join(config.recipients)}\n")

    history = run_agent([("human", f"Run the {config.period} analysis.")], config)
    print(f"\n{history[-1].content}\n")
