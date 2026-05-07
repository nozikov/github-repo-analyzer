"""reflect node: decides whether to loop back or proceed to synthesis."""

import json
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.reflect import PROMPT


class _ReflectResult(TypedDict):
    sufficient: bool
    gaps: list[str]
    rerun: str


def _fmt(items: list, key_order: list[str], limit: int = 10) -> str:
    if not items:
        return "(none)"
    rows = []
    for it in items[:limit]:
        rows.append(json.dumps({k: it.get(k) for k in key_order}, ensure_ascii=False))
    return "\n".join(rows)


def reflect(state: dict) -> dict:
    code = state.get("code_findings", [])
    similar = state.get("similar_repos", [])
    web = state.get("web_snippets", [])

    llm = get_chat_model()
    structured = llm.with_structured_output(_ReflectResult)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    messages = prompt.format_messages(
        owner=state["meta"].get("owner", ""),
        name=state["meta"].get("name", ""),
        n_code=len(code),
        n_similar=len(similar),
        n_web=len(web),
        code_findings=_fmt(code, ["path", "summary"]),
        similar_repos=_fmt(similar, ["full_name", "differentiator"]),
        web_snippets=_fmt(web, ["url", "relevant_quote"]),
    )
    res: _ReflectResult = structured.invoke(messages)
    return {
        "gaps": res.get("gaps", []),
        "rerun_branch": res.get("rerun", "") if not res.get("sufficient") else "",
        "reflection_iteration": state.get("reflection_iteration", 0) + 1,
    }
