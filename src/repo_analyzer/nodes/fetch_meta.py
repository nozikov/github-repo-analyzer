"""fetch_meta node: pulls repo metadata, README, file tree, manifest from GitHub."""

import json
import re
from typing import Any

from repo_analyzer.tools import github

MANIFEST_FILES = ["package.json", "pyproject.toml", "Cargo.toml", "go.mod", "pom.xml", "build.gradle"]
URL_RE = re.compile(r"github\.com/([^/]+)/([^/]+?)/?$")


def _parse_url(url: str) -> tuple[str, str]:
    m = URL_RE.search(url.strip())
    if not m:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    return m.group(1), m.group(2)


def _parse_manifest(name: str, content: str) -> dict[str, Any]:
    if not content:
        return {}
    if name == "package.json":
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
    # For pyproject/Cargo/etc we just stash raw text — LLM can read it.
    return {"_raw": content[:5000], "_filename": name}


def fetch_meta(state: dict) -> dict:
    owner, name = _parse_url(state["repo_url"])
    meta = github.fetch_repo_meta(owner, name)
    for mf in MANIFEST_FILES:
        if mf in meta["file_tree"]:
            content = github.fetch_raw_file(owner, name, mf)
            meta["manifest"] = _parse_manifest(mf, content)
            break
    return {"meta": meta}
