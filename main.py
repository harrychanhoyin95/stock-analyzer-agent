import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langfuse.langchain import CallbackHandler

load_dotenv()

langfuse_handler = CallbackHandler()

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
    print("Chatting with the LLM... (traced at http://localhost:3000)\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit", "q"]:
            break
        response = chain.invoke(
            {"input": user_input},
            config={"callbacks": [langfuse_handler]}
        )
        print(f"\nAssistant: {response}\n")
