from unittest.mock import patch

import pytest

from repo_analyzer.nodes import fetch_meta as node


def _empty_meta(o, n):
    return {
        "owner": o, "name": n, "file_tree": [], "readme": "", "stars": 0,
        "description": "", "language": "", "topics": [], "manifest": {},
    }


def test_fetch_meta_parses_url_and_calls_github(monkeypatch):
    captured: dict = {}

    def fake_fetch(owner, name):
        captured["owner"] = owner
        captured["name"] = name
        return {"owner": owner, "name": name, "file_tree": [
            "package.json", "src/index.js"
        ], "readme": "", "stars": 0, "description": "",
        "language": "JavaScript", "topics": [], "manifest": {}}

    def fake_raw(owner, name, path):
        if path == "package.json":
            return '{"name":"x","dependencies":{"a":"1"}}'
        return ""

    monkeypatch.setattr(node.github, "fetch_repo_meta", fake_fetch)
    monkeypatch.setattr(node.github, "fetch_raw_file", fake_raw)

    state = {"repo_url": "https://github.com/foo/bar"}
    result = node.fetch_meta(state)
    assert captured == {"owner": "foo", "name": "bar"}
    assert result["meta"]["owner"] == "foo"
    assert result["meta"]["manifest"] == {"name": "x", "dependencies": {"a": "1"}}


def test_fetch_meta_handles_url_with_trailing_slash(monkeypatch):
    monkeypatch.setattr(node.github, "fetch_repo_meta", _empty_meta)
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: "")
    result = node.fetch_meta({"repo_url": "https://github.com/foo/bar/"})
    assert result["meta"]["name"] == "bar"


@pytest.mark.parametrize("url", [
    "https://github.com/foo/bar.git",
    "https://github.com/foo/bar/tree/main",
    "git@github.com:foo/bar.git",
    "https://github.com/foo/bar",
    "https://github.com/foo/bar/",
])
def test_fetch_meta_parses_various_url_forms(monkeypatch, url):
    monkeypatch.setattr(node.github, "fetch_repo_meta", _empty_meta)
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: "")
    result = node.fetch_meta({"repo_url": url})
    assert result["meta"]["owner"] == "foo"
    assert result["meta"]["name"] == "bar"


def test_fetch_meta_rejects_non_github_url(monkeypatch):
    monkeypatch.setattr(node.github, "fetch_repo_meta", _empty_meta)
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: "")
    with pytest.raises(ValueError):
        node.fetch_meta({"repo_url": "not-a-url"})
