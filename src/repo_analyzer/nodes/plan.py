"""plan node: LLM produces an investigation plan."""

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.plan import PROMPT
from repo_analyzer.state import Plan


def plan(state: dict) -> dict:
    meta = state["meta"]
    file_tree = meta.get("file_tree", [])[:500]
    readme = (meta.get("readme") or "")[:3000]

    llm = get_chat_model()
    structured = llm.with_structured_output(Plan)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    messages = prompt.format_messages(
        owner=meta.get("owner", ""),
        name=meta.get("name", ""),
        description=meta.get("description", ""),
        language=meta.get("language", ""),
        topics=", ".join(meta.get("topics", [])),
        stars=meta.get("stars", 0),
        readme=readme,
        file_tree="\n".join(file_tree),
    )
    result: Plan = structured.invoke(messages)
    return {"plan": result}
