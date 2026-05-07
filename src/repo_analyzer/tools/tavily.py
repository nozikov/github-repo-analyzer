"""Tavily web search wrapper. Failures are swallowed (returns []).

Web search is non-critical: a missing source should not abort the run.
"""

import logging
import os
from typing import Any

from tavily import TavilyClient

log = logging.getLogger(__name__)


def _make_client() -> TavilyClient:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    try:
        client = _make_client()
        raw = client.search(query=query, max_results=max_results)
    except Exception as e:
        log.warning("tavily search failed for %r: %s", query, e)
        return []
    return [
        {"url": r.get("url", ""), "title": r.get("title", ""), "snippet": r.get("content", "")}
        for r in raw.get("results", [])
    ]
