from unittest.mock import MagicMock

from repo_analyzer.nodes import reflect as node


def _state_with_data():
    return {
        "meta": {"owner": "o", "name": "r"},
        "code_findings": [{"path": "a.py", "summary": "x", "quality_notes": []}],
        "similar_repos": [],
        "web_snippets": [],
        "reflection_iteration": 0,
    }


def test_reflect_marks_sufficient(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {"sufficient": True, "gaps": [], "rerun": ""}
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    result = node.reflect(_state_with_data())
    assert result["gaps"] == []
    assert result["reflection_iteration"] == 1
    assert result["rerun_branch"] == ""


def test_reflect_marks_gaps(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {
        "sufficient": False, "gaps": ["no similar repos"], "rerun": "find_similar"
    }
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    result = node.reflect(_state_with_data())
    assert result["gaps"] == ["no similar repos"]
    assert result["rerun_branch"] == "find_similar"
