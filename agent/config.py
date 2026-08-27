import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "没有找到 OPENAI_API_KEY。请把 .env.example 复制为 .env，"
        "然后填写 OPENAI_API_KEY。"
    )

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-5.6-luna")
SEARCH_MODEL_NAME = os.getenv("SEARCH_MODEL_NAME", "gpt-5.4-mini")
MAX_RESEARCH_ATTEMPTS = int(os.getenv("MAX_RESEARCH_ATTEMPTS", "3"))
MIN_DATA_COMPLETENESS = float(os.getenv("MIN_DATA_COMPLETENESS", "0.80"))
SEARCH_MAX_TOKENS = int(os.getenv("SEARCH_MAX_TOKENS", "1400"))

llm = ChatOpenAI(
    model=MODEL_NAME,
    max_retries=0,
)

search_llm = ChatOpenAI(
    model=SEARCH_MODEL_NAME,
    max_completion_tokens=SEARCH_MAX_TOKENS,
    max_retries=0,
)
