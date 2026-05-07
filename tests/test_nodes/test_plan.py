from unittest.mock import MagicMock

from repo_analyzer.nodes import plan as node


def test_plan_invokes_llm_with_structured_output(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {
        "files_to_read": ["src/main.py", "README.md"],
        "similar_repos_query": "cli framework python",
        "web_queries": ["best python cli libs", "typer alternatives"],
    }
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured

    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    state = {"meta": {
        "owner": "tiangolo", "name": "typer", "description": "CLIs",
        "language": "Python", "topics": ["cli"], "stars": 15000,
        "readme": "# Typer", "file_tree": ["src/main.py", "README.md"],
        "manifest": {},
    }}
    result = node.plan(state)
    assert result["plan"]["files_to_read"] == ["src/main.py", "README.md"]
    assert result["plan"]["similar_repos_query"] == "cli framework python"
    fake_llm.with_structured_output.assert_called_once()
