"""synthesize node: produce final markdown report and save to file."""

import json
import logging
from datetime import datetime
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.synthesize import PROMPT

REPORTS_DIR = Path("reports")

log = logging.getLogger(__name__)

REQUIRED_SECTIONS = (
    "## 1. Tech due-diligence",
    "## 2. Рекомендации автору",
    "## 3. Идеи поверх",
)


def _fmt_list(items: list, key_order: list[str]) -> str:
    if not items:
        return "(none)"
    return "\n".join(json.dumps({k: it.get(k) for k in key_order}, ensure_ascii=False) for it in items)


def synthesize(state: dict) -> dict:
    meta = state["meta"]
    llm = get_chat_model()
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    messages = prompt.format_messages(
        owner=meta.get("owner", ""),
        name=meta.get("name", ""),
        description=meta.get("description", ""),
        language=meta.get("language", ""),
        stars=meta.get("stars", 0),
        readme=(meta.get("readme") or "")[:2000],
        code_findings=_fmt_list(state.get("code_findings", []), ["path", "summary", "quality_notes"]),
        similar_repos=_fmt_list(state.get("similar_repos", []), ["full_name", "stars", "differentiator"]),
        web_snippets=_fmt_list(state.get("web_snippets", []), ["url", "title", "relevant_quote"]),
        gaps="\n".join(state.get("gaps", [])) or "(none)",
    )
    msg = llm.invoke(messages)
    markdown = msg.content if hasattr(msg, "content") else str(msg)

    missing = [s for s in REQUIRED_SECTIONS if s not in markdown]
    if missing:
        log.warning("synthesize output missing sections: %s", missing)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.utcnow().strftime("%Y-%m-%d")
    out = REPORTS_DIR / f"{meta['owner']}-{meta['name']}-{date}.md"
    out.write_text(markdown, encoding="utf-8")
    return {"report_markdown": markdown, "report_path": str(out)}
