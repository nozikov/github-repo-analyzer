from unittest.mock import patch

from repo_analyzer.nodes import fetch_meta as node


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
    monkeypatch.setattr(node.github, "fetch_repo_meta", lambda o, n: {
        "owner": o, "name": n, "file_tree": [], "readme": "", "stars": 0,
        "description": "", "language": "", "topics": [], "manifest": {}
    })
    monkeypatch.setattr(node.github, "fetch_raw_file", lambda o, n, p: "")
    result = node.fetch_meta({"repo_url": "https://github.com/foo/bar/"})
    assert result["meta"]["name"] == "bar"
