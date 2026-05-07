"""find_similar node: GitHub Search + LLM comparison."""

import logging

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.find_similar import PROMPT
from repo_analyzer.state import SimilarRepo
from repo_analyzer.tools import github

log = logging.getLogger(__name__)
MAX_KEEP = 5


def find_similar(state: dict) -> dict:
    query = state["plan"].get("similar_repos_query", "").strip()
    if not query:
        return {"similar_repos": []}

    target = state["meta"]
    candidates = github.search_repos(query, limit=10)

    llm = get_chat_model()
    structured = llm.with_structured_output(SimilarRepo)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    kept: list[SimilarRepo] = []
    for c in candidates:
        if c.get("full_name") == f"{target['owner']}/{target['name']}":
            continue
        try:
            messages = prompt.format_messages(
                target_full_name=f"{target['owner']}/{target['name']}",
                target_description=target.get("description", ""),
                target_language=target.get("language", ""),
                candidate_full_name=c.get("full_name", ""),
                candidate_description=c.get("description", "") or "",
                candidate_stars=c.get("stargazers_count", 0),
            )
            comp: SimilarRepo = structured.invoke(messages)
        except Exception as e:
            log.warning("comparison failed for %s: %s", c.get("full_name"), e)
            continue
        if comp.get("why_similar") == "NOT_SIMILAR":
            continue
        kept.append(comp)
        if len(kept) >= MAX_KEEP:
            break
    return {"similar_repos": kept}
