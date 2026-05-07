"""analyze_code node: reads each planned file and produces findings."""

import logging

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.analyze_code import PROMPT
from repo_analyzer.state import CodeFinding
from repo_analyzer.tools import github

log = logging.getLogger(__name__)
MAX_FILE_BYTES = 50_000


def analyze_code(state: dict) -> dict:
    owner = state["meta"]["owner"]
    name = state["meta"]["name"]
    files = state["plan"].get("files_to_read", [])

    llm = get_chat_model()
    structured = llm.with_structured_output(CodeFinding)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])

    findings: list[CodeFinding] = []
    for path in files:
        try:
            content = github.fetch_raw_file(owner, name, path)
        except Exception as e:
            log.warning("failed to fetch %s: %s", path, e)
            continue
        if not content or "\x00" in content[:1000]:  # skip binary
            continue
        if len(content) > MAX_FILE_BYTES:
            content = content[:MAX_FILE_BYTES]
        try:
            messages = prompt.format_messages(
                owner=owner, name=name, path=path, content=content,
            )
            finding: CodeFinding = structured.invoke(messages)
            findings.append(finding)
        except Exception as e:
            log.warning("LLM failed on %s: %s", path, e)
    return {"code_findings": findings}
