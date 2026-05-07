import os
from pathlib import Path
from unittest.mock import MagicMock

from repo_analyzer.nodes import synthesize as node


def test_synthesize_writes_markdown_to_reports_dir(tmp_path, monkeypatch):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(
        content="# Анализ репо o/r\n\n## 1. Tech due-diligence\nfoo\n## 2. Рекомендации автору\nbar\n## 3. Идеи поверх\nbaz"
    )
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)
    monkeypatch.setattr(node, "REPORTS_DIR", tmp_path)

    state = {
        "meta": {"owner": "o", "name": "r"},
        "code_findings": [], "similar_repos": [], "web_snippets": [],
        "gaps": [],
    }
    result = node.synthesize(state)
    assert "report_markdown" in result
    assert "1. Tech due-diligence" in result["report_markdown"]
    assert Path(result["report_path"]).exists()
    assert "o-r-" in Path(result["report_path"]).name
