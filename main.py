import os
import sys
import time

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


def _make_llm(model: str, key: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=key,
        openai_api_base="https://openrouter.ai/api/v1",
    )


def _make_agent(model: str, key: str):
    return create_agent(
        model=_make_llm(model, key),
        tools=[
            get_stock_history,
            get_top_gainers,
            python_analyzer,
            send_email,
            get_stock_news,
        ],
        system_prompt=get_system_prompt(),
    )


def run_agent(history):
    global _current_idx

    while _current_idx < len(_CANDIDATES):
        model, key = _CANDIDATES[_current_idx]
        agent = _make_agent(model, key)

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
    print("Running daily NASDAQ analysis...\n")

    history = run_agent([("human", "Run the daily analysis.")])
    print(f"\n{history[-1].content}\n")

    try:
        email = input("Your email: ").strip()
    except KeyboardInterrupt:
        print("\nBye!")
        raise SystemExit(0)

    if email:
        history.append(("human", email))
        history = run_agent(history)
        print(f"\n{history[-1].content}\n")
