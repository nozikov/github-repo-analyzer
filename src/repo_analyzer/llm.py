"""Singleton ChatAnthropic factory.

Tests can reset the cache by setting `llm._cached = None`.
"""

import os

from langchain_anthropic import ChatAnthropic

_cached: ChatAnthropic | None = None
MODEL_ID = "claude-sonnet-4-6"


def get_chat_model() -> ChatAnthropic:
    global _cached
    if _cached is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _cached = ChatAnthropic(model=MODEL_ID, api_key=api_key, temperature=0)
    return _cached
