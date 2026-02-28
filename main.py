import os
import sys
import time

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
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

FALLBACK_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "arcee-ai/trinity-large-preview:free",
    "arcee-ai/trinity-mini:free",
    "stepfun/step-3.5-flash:free",
]

def make_llm(model: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=model,
        openai_api_key=os.getenv("OPENROUTER_API_KEY"),
        openai_api_base="https://openrouter.ai/api/v1",
    )
    
primary, *fallbacks = [make_llm(m) for m in FALLBACK_MODELS]
llm = primary.with_fallbacks(fallbacks)

agent = create_agent(
    model=llm,
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
