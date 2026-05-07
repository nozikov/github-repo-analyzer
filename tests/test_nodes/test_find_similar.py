from unittest.mock import MagicMock

from repo_analyzer.nodes import find_similar as node


def test_find_similar_calls_github_search_and_summarizes(monkeypatch):
    monkeypatch.setattr(node.github, "search_repos", lambda q, limit: [
        {"full_name": "click/click", "description": "Composable cli", "stargazers_count": 14000},
        {"full_name": "fire/fire", "description": "google fire", "stargazers_count": 26000},
    ])
    fake_structured = MagicMock()
    fake_structured.invoke.side_effect = [
        {"full_name": "click/click", "description": "Composable cli", "stars": 14000,
         "why_similar": "cli", "differentiator": "decorator-heavy"},
        {"full_name": "fire/fire", "description": "google fire", "stars": 26000,
         "why_similar": "cli", "differentiator": "auto-cli"},
    ]
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    state = {
        "meta": {"owner": "tiangolo", "name": "typer", "description": "CLIs", "language": "Python"},
        "plan": {"similar_repos_query": "cli python", "files_to_read": [], "web_queries": []},
    }
    result = node.find_similar(state)
    assert len(result["similar_repos"]) == 2
    assert result["similar_repos"][0]["full_name"] == "click/click"
