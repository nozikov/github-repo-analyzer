from unittest.mock import MagicMock

from repo_analyzer.nodes import web_context as node


def test_web_context_filters_relevant_snippets(monkeypatch):
    monkeypatch.setattr(node.tavily, "search", lambda q, max_results: [
        {"url": "https://x", "title": "X", "snippet": "useful"},
        {"url": "https://y", "title": "Y", "snippet": "spam"},
    ])
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {
        "kept": [{"url": "https://x", "title": "X", "relevant_quote": "useful"}]
    }
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    state = {
        "meta": {"owner": "o", "name": "r"},
        "plan": {"web_queries": ["q1"], "files_to_read": [], "similar_repos_query": ""},
    }
    result = node.web_context(state)
    assert len(result["web_snippets"]) == 1
    assert result["web_snippets"][0]["url"] == "https://x"


def test_web_context_handles_empty_queries():
    state = {"meta": {"owner": "o", "name": "r"},
             "plan": {"web_queries": [], "files_to_read": [], "similar_repos_query": ""}}
    result = node.web_context(state)
    assert result["web_snippets"] == []
