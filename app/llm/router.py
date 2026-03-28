"""
LLM boundary router.

Rule:
  sensitive == True  →  local Ollama (Mistral / Llama3)  — never leaves the VPS
  sensitive == False →  OpenAI GPT-4o                     — cloud reasoning
"""

from functools import lru_cache
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from app.config import settings


@lru_cache(maxsize=1)
def _cloud_llm() -> ChatOpenAI:
    return ChatOpenAI(
        model=settings.CLOUD_LLM_MODEL,
        temperature=0.2,
        api_key=settings.OPENAI_API_KEY,
    )


@lru_cache(maxsize=1)
def _local_llm() -> ChatOllama:
    return ChatOllama(
        model=settings.LOCAL_LLM_MODEL,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0.1,
    )


def get_llm(sensitive: bool = False):
    """Return the appropriate LLM based on sensitivity classification."""
    if sensitive:
        return _local_llm()
    return _cloud_llm()
