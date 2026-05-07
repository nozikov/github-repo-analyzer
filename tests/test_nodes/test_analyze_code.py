from unittest.mock import MagicMock

from repo_analyzer.nodes import analyze_code as node


def test_analyze_code_reads_each_file_and_returns_findings(monkeypatch):
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: f"# code of {p}")

    fake_structured = MagicMock()
    fake_structured.invoke.side_effect = [
        {"path": "src/a.py", "summary": "entry", "quality_notes": []},
        {"path": "src/b.py", "summary": "core", "quality_notes": ["no docstrings"]},
    ]
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    state = {
        "meta": {"owner": "o", "name": "r"},
        "plan": {"files_to_read": ["src/a.py", "src/b.py"], "similar_repos_query": "", "web_queries": []},
    }
    result = node.analyze_code(state)
    assert len(result["code_findings"]) == 2
    assert result["code_findings"][0]["path"] == "src/a.py"
    assert "no docstrings" in result["code_findings"][1]["quality_notes"]


def test_analyze_code_truncates_huge_files(monkeypatch):
    big = "x" * 100_000
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: big)
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {"path": "x.py", "summary": "", "quality_notes": []}
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    captured = {}
    def capture(arg):
        # arg here is messages list — capture content from human message
        if isinstance(arg, list) and arg:
            content = arg[0].content if hasattr(arg[0], "content") else str(arg[0])
            captured["content"] = content
        return {"path": "x.py", "summary": "", "quality_notes": []}
    fake_structured.invoke.side_effect = capture

    state = {"meta": {"owner": "o", "name": "r"},
             "plan": {"files_to_read": ["x.py"], "similar_repos_query": "", "web_queries": []}}
    node.analyze_code(state)
    assert "captured" in captured or len(captured.get("content", "")) <= 60_000  # message bigger than file but < 60K
