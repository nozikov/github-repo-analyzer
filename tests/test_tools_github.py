import os
from unittest.mock import patch

import httpx
import pytest
import respx

from repo_analyzer.tools import github as gh


@pytest.fixture(autouse=True)
def github_token():
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_test"}):
        yield


@respx.mock
def test_fetch_repo_meta_returns_normalized_dict(repo_response_json):
    respx.get("https://api.github.com/repos/tiangolo/typer").mock(
        return_value=httpx.Response(200, json=repo_response_json)
    )
    respx.get("https://api.github.com/repos/tiangolo/typer/readme").mock(
        return_value=httpx.Response(200, json={"content": "IyBoZWxsbw==", "encoding": "base64"})
    )
    respx.get("https://api.github.com/repos/tiangolo/typer/git/trees/HEAD").mock(
        return_value=httpx.Response(200, json={"tree": [{"path": "README.md", "type": "blob"}]})
    )
    meta = gh.fetch_repo_meta("tiangolo", "typer")
    assert meta["owner"] == "tiangolo"
    assert meta["name"] == "typer"
    assert meta["stars"] == 15000
    assert meta["readme"].startswith("# hello")
    assert meta["file_tree"] == ["README.md"]


@respx.mock
def test_fetch_raw_file_decodes_base64():
    respx.get("https://api.github.com/repos/o/r/contents/foo.py").mock(
        return_value=httpx.Response(200, json={"content": "cHJpbnQoImhpIik=", "encoding": "base64"})
    )
    content = gh.fetch_raw_file("o", "r", "foo.py")
    assert content == 'print("hi")'


@respx.mock
def test_fetch_raw_file_falls_back_to_raw_url_for_large_files():
    respx.get("https://api.github.com/repos/o/r/contents/big.py").mock(
        return_value=httpx.Response(200, json={"content": None, "encoding": None})
    )
    respx.get("https://raw.githubusercontent.com/o/r/HEAD/big.py").mock(
        return_value=httpx.Response(200, text="big content here")
    )
    content = gh.fetch_raw_file("o", "r", "big.py")
    assert content == "big content here"


@respx.mock
def test_search_repos_returns_top_n():
    respx.get("https://api.github.com/search/repositories").mock(
        return_value=httpx.Response(200, json={"items": [
            {"full_name": "a/b", "description": "x", "stargazers_count": 100},
            {"full_name": "c/d", "description": "y", "stargazers_count": 50},
        ]})
    )
    results = gh.search_repos("query", limit=2)
    assert len(results) == 2
    assert results[0]["full_name"] == "a/b"


@respx.mock
def test_404_raises():
    respx.get("https://api.github.com/repos/x/y").mock(return_value=httpx.Response(404))
    with pytest.raises(gh.RepoNotFoundError):
        gh.fetch_repo_meta("x", "y")
