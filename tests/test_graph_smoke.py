"""End-to-end test of the assembled graph with all I/O mocked.

This test verifies the graph topology: parallel branches converge directly at
synthesize (V1 ships without the reflection loop).
"""

from unittest.mock import MagicMock

from repo_analyzer import graph as graph_module


def _llm_with_responses(responses_by_target):
    """Build a fake LLM whose with_structured_output returns staged answers per target type."""
    queue = list(responses_by_target)

    def factory(_target):
        s = MagicMock()
        # Pop in order; raise if exhausted
        s.invoke.side_effect = lambda *_args, **_kwargs: queue.pop(0)
        return s

    fake_llm = MagicMock()
    fake_llm.with_structured_output.side_effect = factory
    fake_llm.invoke.return_value = MagicMock(
        content="# Анализ репо o/r\n## 1. Tech due-diligence\nx\n## 2. Рекомендации автору\nx\n## 3. Идеи поверх\nx"
    )
    return fake_llm


def test_graph_runs_end_to_end(monkeypatch, tmp_path):
    # Mock GitHub
    monkeypatch.setattr("repo_analyzer.tools.github.fetch_repo_meta", lambda o, n: {
        "owner": o, "name": n, "description": "test", "stars": 10, "language": "Python",
        "topics": [], "readme": "# test", "file_tree": ["main.py"], "manifest": {},
    })
    monkeypatch.setattr("repo_analyzer.tools.github.fetch_raw_file", lambda o, n, p: "print('hi')")
    monkeypatch.setattr("repo_analyzer.tools.github.search_repos", lambda q, limit: [
        {"full_name": "a/b", "description": "x", "stargazers_count": 100},
    ])

    # Mock Tavily
    monkeypatch.setattr("repo_analyzer.tools.tavily.search", lambda q, max_results: [])

    # Reports dir
    monkeypatch.setattr("repo_analyzer.nodes.synthesize.REPORTS_DIR", tmp_path)

    # Mock LLM with staged responses (order: plan -> analyze_code -> find_similar)
    fake_llm = _llm_with_responses([
        {"files_to_read": ["main.py"], "similar_repos_query": "test", "web_queries": []},  # plan
        {"path": "main.py", "summary": "entry", "quality_notes": []},                       # analyze_code
        {"full_name": "a/b", "description": "x", "stars": 100,                              # find_similar
         "why_similar": "test", "differentiator": "diff"},
    ])

    # Each node imports `get_chat_model` via `from repo_analyzer.llm import get_chat_model`,
    # which binds the symbol into the node's namespace at import time. Patching
    # `repo_analyzer.llm.get_chat_model` therefore does NOT intercept the calls — we have
    # to patch each node's local reference.
    for mod in (
        "repo_analyzer.nodes.plan",
        "repo_analyzer.nodes.analyze_code",
        "repo_analyzer.nodes.find_similar",
        "repo_analyzer.nodes.web_context",
        "repo_analyzer.nodes.synthesize",
    ):
        monkeypatch.setattr(f"{mod}.get_chat_model", lambda: fake_llm)
    # Belt-and-suspenders: also patch the source, in case anything else looks it up there.
    monkeypatch.setattr("repo_analyzer.llm.get_chat_model", lambda: fake_llm)

    g = graph_module.build_graph()
    final = g.invoke({"repo_url": "https://github.com/o/r"})

    assert "1. Tech due-diligence" in final["report_markdown"]
    assert "2. Рекомендации автору" in final["report_markdown"]
    assert "3. Идеи поверх" in final["report_markdown"]
    assert final["meta"]["owner"] == "o"
