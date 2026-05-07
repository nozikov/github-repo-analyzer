"""web_context node: Tavily search + LLM relevance filter."""

import logging
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.web_context import PROMPT
from repo_analyzer.state import WebSnippet
from repo_analyzer.tools import tavily

log = logging.getLogger(__name__)


class _FilterResult(TypedDict):
    kept: list[WebSnippet]


def web_context(state: dict) -> dict:
    queries = state["plan"].get("web_queries", [])
    if not queries:
        return {"web_snippets": []}

    target = state["meta"]
    llm = get_chat_model()
    structured = llm.with_structured_output(_FilterResult)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    all_kept: list[WebSnippet] = []
    for q in queries:
        raw = tavily.search(q, max_results=5)
        if not raw:
            continue
        formatted = "\n\n".join(f"[{r['url']}] {r['title']}\n{r['snippet']}" for r in raw)
        try:
            messages = prompt.format_messages(
                query=q, owner=target.get("owner", ""), name=target.get("name", ""),
                results=formatted,
            )
            res: _FilterResult = structured.invoke(messages)
        except Exception as e:
            log.warning("filter failed for %r: %s", q, e)
            continue
        all_kept.extend(res.get("kept", []))
    return {"web_snippets": all_kept}
