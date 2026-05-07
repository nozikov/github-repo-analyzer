import os
from unittest.mock import MagicMock, patch

from repo_analyzer.tools import tavily


def test_search_returns_normalized_snippets():
    fake_client = MagicMock()
    fake_client.search.return_value = {
        "results": [
            {"url": "https://x", "title": "X", "content": "foo bar"},
            {"url": "https://y", "title": "Y", "content": "baz"},
        ]
    }
    with patch.object(tavily, "_make_client", return_value=fake_client), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}):
        results = tavily.search("how to use X", max_results=5)
    assert len(results) == 2
    assert results[0]["url"] == "https://x"
    assert results[0]["snippet"] == "foo bar"


def test_search_returns_empty_on_error():
    fake_client = MagicMock()
    fake_client.search.side_effect = RuntimeError("boom")
    with patch.object(tavily, "_make_client", return_value=fake_client), \
         patch.dict(os.environ, {"TAVILY_API_KEY": "tvly-test"}):
        results = tavily.search("x")
    assert results == []
