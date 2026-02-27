import os
import sys

import httpx
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langfuse.langchain import CallbackHandler

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

langfuse_handler = CallbackHandler(
    public_key=os.getenv("LANGFUSE_PUBLIC_KEY"),
    secret_key=os.getenv("LANGFUSE_SECRET_KEY"),
    host=LANGFUSE_HOST,
)

llm = ChatOpenAI(
    model=os.getenv("LLM_MODEL", "openrouter/google/gemini-2.0-flash-001"),
    openai_api_key=os.getenv("OPENROUTER_API_KEY"),
    openai_api_base="https://openrouter.ai/api/v1",
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant. Be concise."),
    ("user", "{input}")
])

chain = prompt | llm | StrOutputParser()

if __name__ == "__main__":
    print("Chat ready. Type 'exit' to quit.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            break
        response = chain.invoke(
            {"input": user_input},
            config={"callbacks": [langfuse_handler]}
        )
        print(f"\nAssistant: {response}\n")
