import os
import sys

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langfuse.langchain import CallbackHandler

from tools import get_stock_history, get_top_gainers, python_analyzer

load_dotenv()

LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "http://localhost:3000")

SYSTEM_PROMPT = "You are a helpful stock analysis assistant."

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

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "openrouter/google/gemini-2.0-flash-001"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
)

agent = create_agent(
    model=llm,
    tools=[get_stock_history, get_top_gainers, python_analyzer],
    system_prompt=SYSTEM_PROMPT,
)

if __name__ == "__main__":
    print("Chat ready. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            break
        response = agent.invoke(
            {"messages": [("human", user_input)]},
            config={"callbacks": [langfuse_handler]},
        )
        print(f"\nAssistant: {response['messages'][-1].content}\n")
