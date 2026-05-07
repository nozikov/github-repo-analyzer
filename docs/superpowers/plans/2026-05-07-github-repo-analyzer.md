# GitHub Repo Analyzer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a CLI agent in Python+LangGraph that takes a GitHub repo URL and produces a 3-section markdown report (tech due-diligence, advice to author, ideas on top) using Claude Sonnet 4.6, GitHub API, and Tavily web search.

**Architecture:** A LangGraph state machine with 7 nodes. After fetching repo metadata and producing a plan, three branches (`analyze_code`, `find_similar`, `web_context`) run in parallel via static fan-out edges. A `reflect` node decides whether to loop back to one branch (max 1 iteration) or proceed to `synthesize`, which writes the final markdown report.

**Tech Stack:** Python 3.11+, LangGraph, langchain-anthropic (Claude Sonnet 4.6), httpx, tavily-python, tenacity, pytest, respx, uv (package manager).

**Reference docs:**

- Spec: `docs/superpowers/specs/2026-05-07-github-repo-analyzer-design.md`
- LangGraph: prefer `mcp__plugin_context7_context7__query-docs` to verify current API when in doubt (especially `StateGraph`, conditional edges, `with_structured_output`).

---

## Phase 1 — Project setup

### Task 1: Initialize Python project with uv

**Files:**
- Create: `/Users/anton/IdeaProjects/lang-graph/pyproject.toml`
- Create: `/Users/anton/IdeaProjects/lang-graph/.env.example`
- Create: `/Users/anton/IdeaProjects/lang-graph/reports/.gitkeep`

- [ ] **Step 1: Verify `uv` is installed**

Run: `uv --version`
Expected: prints version like `uv 0.5.x`. If not installed, run `curl -LsSf https://astral.sh/uv/install.sh | sh` first.

- [ ] **Step 2: Write `pyproject.toml`**

```toml
[project]
name = "repo-analyzer"
version = "0.1.0"
description = "LangGraph-based GitHub repository analyzer"
requires-python = ">=3.11"
dependencies = [
    "langgraph>=0.2.50",
    "langchain-anthropic>=0.3",
    "langchain-core>=0.3",
    "httpx>=0.27",
    "tavily-python>=0.5",
    "python-dotenv>=1.0",
    "tenacity>=9.0",
]

[dependency-groups]
dev = [
    "pytest>=8.0",
    "pytest-asyncio>=0.24",
    "respx>=0.21",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/repo_analyzer"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
    "live: requires real API keys (run manually)",
]
```

- [ ] **Step 3: Write `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
GITHUB_TOKEN=ghp_...
TAVILY_API_KEY=tvly-...
```

- [ ] **Step 4: Create `reports/` directory with placeholder**

Run: `mkdir -p reports && touch reports/.gitkeep`

- [ ] **Step 5: Initialize venv and install deps**

Run: `uv sync`
Expected: creates `.venv/`, downloads deps, prints "Resolved N packages".

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml .env.example reports/.gitkeep
git commit -m "chore: bootstrap python project with uv"
```

---

### Task 2: Create source skeleton

**Files:**
- Create: `src/repo_analyzer/__init__.py`
- Create: `src/repo_analyzer/__main__.py`
- Create: `src/repo_analyzer/nodes/__init__.py`
- Create: `src/repo_analyzer/tools/__init__.py`
- Create: `src/repo_analyzer/prompts/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/test_nodes/__init__.py`

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p src/repo_analyzer/{nodes,tools,prompts}
mkdir -p tests/{test_nodes,fixtures}
touch src/repo_analyzer/__init__.py
touch src/repo_analyzer/nodes/__init__.py
touch src/repo_analyzer/tools/__init__.py
touch src/repo_analyzer/prompts/__init__.py
touch tests/__init__.py
touch tests/test_nodes/__init__.py
```

- [ ] **Step 2: Write minimal `__main__.py` stub**

`src/repo_analyzer/__main__.py`:

```python
"""Entry point for `python -m repo_analyzer <url>`."""

if __name__ == "__main__":
    from repo_analyzer.cli import main
    main()
```

- [ ] **Step 3: Verify package import works**

Run: `uv run python -c "import repo_analyzer; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add src tests
git commit -m "chore: add package skeleton"
```

---

## Phase 2 — Foundation (state, llm, tools)

### Task 3: Define state types

**Files:**
- Create: `src/repo_analyzer/state.py`

- [ ] **Step 1: Write all TypedDicts**

`src/repo_analyzer/state.py`:

```python
from typing import Annotated, TypedDict
from operator import add


class RepoMeta(TypedDict, total=False):
    owner: str
    name: str
    description: str
    stars: int
    language: str
    topics: list[str]
    readme: str
    manifest: dict
    file_tree: list[str]


class CodeFinding(TypedDict):
    path: str
    summary: str
    quality_notes: list[str]


class SimilarRepo(TypedDict):
    full_name: str
    description: str
    stars: int
    why_similar: str
    differentiator: str


class WebSnippet(TypedDict):
    url: str
    title: str
    relevant_quote: str


class Plan(TypedDict):
    files_to_read: list[str]
    similar_repos_query: str
    web_queries: list[str]


class State(TypedDict, total=False):
    repo_url: str

    meta: RepoMeta
    plan: Plan

    code_findings: Annotated[list[CodeFinding], add]
    similar_repos: Annotated[list[SimilarRepo], add]
    web_snippets: Annotated[list[WebSnippet], add]

    reflection_iteration: int
    gaps: list[str]
    rerun_branch: str

    report_markdown: str
    report_path: str
```

- [ ] **Step 2: Verify imports**

Run: `uv run python -c "from repo_analyzer.state import State, Plan; print(State.__annotations__.keys())"`
Expected: prints dict_keys with all field names.

- [ ] **Step 3: Commit**

```bash
git add src/repo_analyzer/state.py
git commit -m "feat: define state typed dicts"
```

---

### Task 4: LLM singleton factory

**Files:**
- Create: `src/repo_analyzer/llm.py`
- Test: `tests/test_llm.py`

- [ ] **Step 1: Write the failing test**

`tests/test_llm.py`:

```python
import os
from unittest.mock import patch

from repo_analyzer import llm as llm_module


def test_get_chat_model_returns_claude_sonnet():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        llm_module._cached = None  # reset singleton
        model = llm_module.get_chat_model()
    assert "claude-sonnet-4-6" in model.model


def test_get_chat_model_is_singleton():
    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-test"}):
        llm_module._cached = None
        a = llm_module.get_chat_model()
        b = llm_module.get_chat_model()
    assert a is b
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_llm.py -v`
Expected: ImportError or ModuleNotFoundError on `repo_analyzer.llm`.

- [ ] **Step 3: Implement `llm.py`**

`src/repo_analyzer/llm.py`:

```python
"""Singleton ChatAnthropic factory.

Tests can reset the cache by setting `llm.cached = None`.
"""

import os

from langchain_anthropic import ChatAnthropic

_cached: ChatAnthropic | None = None
MODEL_ID = "claude-sonnet-4-6"


def get_chat_model() -> ChatAnthropic:
    global _cached
    if _cached is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        _cached = ChatAnthropic(model=MODEL_ID, api_key=api_key, temperature=0)
    return _cached
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_llm.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/repo_analyzer/llm.py tests/test_llm.py
git commit -m "feat: add llm singleton factory"
```

---

### Task 5: GitHub API tool

**Files:**
- Create: `src/repo_analyzer/tools/github.py`
- Create: `tests/conftest.py`
- Test: `tests/test_tools_github.py`
- Create: `tests/fixtures/repo_response.json`

- [ ] **Step 1: Write test fixture**

`tests/fixtures/repo_response.json`:

```json
{
  "name": "typer",
  "full_name": "tiangolo/typer",
  "description": "Typer, build great CLIs.",
  "owner": {"login": "tiangolo"},
  "stargazers_count": 15000,
  "language": "Python",
  "topics": ["cli", "python"]
}
```

- [ ] **Step 2: Write `conftest.py` with shared fixtures**

`tests/conftest.py`:

```python
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def repo_response_json() -> dict:
    return json.loads((FIXTURES_DIR / "repo_response.json").read_text())


@pytest.fixture(autouse=True)
def reset_llm_singleton(monkeypatch):
    """Ensure each test starts with a fresh llm singleton."""
    from repo_analyzer import llm as llm_module
    llm_module._cached = None
    yield
```

- [ ] **Step 3: Write the failing tests**

`tests/test_tools_github.py`:

```python
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
```

- [ ] **Step 4: Run — expect failure**

Run: `uv run pytest tests/test_tools_github.py -v`
Expected: ModuleNotFoundError on `repo_analyzer.tools.github`.

- [ ] **Step 5: Implement `tools/github.py`**

`src/repo_analyzer/tools/github.py`:

```python
"""Thin wrapper over GitHub REST API.

Uses httpx + tenacity. All functions are sync.
"""

import base64
import os
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

API = "https://api.github.com"


class RepoNotFoundError(Exception):
    pass


class GitHubError(Exception):
    pass


def _client() -> httpx.Client:
    token = os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return httpx.Client(headers=headers, timeout=30.0)


def _is_5xx(exc: BaseException) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and 500 <= exc.response.status_code < 600


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(httpx.HTTPStatusError),
    reraise=True,
)
def _get(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
    with _client() as c:
        r = c.get(url, params=params)
        if r.status_code == 404:
            raise RepoNotFoundError(url)
        if r.status_code >= 500:
            r.raise_for_status()
        if r.status_code >= 400:
            raise GitHubError(f"{r.status_code} {r.text[:200]}")
    return r


def fetch_repo_meta(owner: str, name: str) -> dict[str, Any]:
    info = _get(f"{API}/repos/{owner}/{name}").json()
    readme_b64 = _get(f"{API}/repos/{owner}/{name}/readme").json().get("content", "")
    readme = base64.b64decode(readme_b64).decode("utf-8", errors="replace") if readme_b64 else ""
    tree = _get(f"{API}/repos/{owner}/{name}/git/trees/HEAD", params={"recursive": "1"}).json()
    paths = [item["path"] for item in tree.get("tree", []) if item.get("type") == "blob"]
    return {
        "owner": owner,
        "name": name,
        "description": info.get("description") or "",
        "stars": info.get("stargazers_count", 0),
        "language": info.get("language") or "",
        "topics": info.get("topics", []),
        "readme": readme,
        "file_tree": paths,
        "manifest": {},
    }


def fetch_raw_file(owner: str, name: str, path: str) -> str:
    """Return file content (UTF-8)."""
    data = _get(f"{API}/repos/{owner}/{name}/contents/{path}").json()
    if data.get("encoding") == "base64":
        return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
    return data.get("content", "")


def search_repos(query: str, limit: int = 10) -> list[dict[str, Any]]:
    data = _get(
        f"{API}/search/repositories",
        params={"q": query, "sort": "stars", "per_page": str(limit)},
    ).json()
    return data.get("items", [])
```

- [ ] **Step 6: Run — expect pass**

Run: `uv run pytest tests/test_tools_github.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add src/repo_analyzer/tools/github.py tests/conftest.py tests/test_tools_github.py tests/fixtures/repo_response.json
git commit -m "feat: add github api tool with retry"
```

---

### Task 6: Tavily search tool

**Files:**
- Create: `src/repo_analyzer/tools/tavily.py`
- Test: `tests/test_tools_tavily.py`

- [ ] **Step 1: Write the failing test**

`tests/test_tools_tavily.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_tools_tavily.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `tools/tavily.py`**

`src/repo_analyzer/tools/tavily.py`:

```python
"""Tavily web search wrapper. Failures are swallowed (returns []).

Web search is non-critical: a missing source should not abort the run.
"""

import logging
import os
from typing import Any

from tavily import TavilyClient

log = logging.getLogger(__name__)


def _make_client() -> TavilyClient:
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise RuntimeError("TAVILY_API_KEY is not set")
    return TavilyClient(api_key=key)


def search(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    try:
        client = _make_client()
        raw = client.search(query=query, max_results=max_results)
    except Exception as e:
        log.warning("tavily search failed for %r: %s", query, e)
        return []
    return [
        {"url": r.get("url", ""), "title": r.get("title", ""), "snippet": r.get("content", "")}
        for r in raw.get("results", [])
    ]
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_tools_tavily.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/repo_analyzer/tools/tavily.py tests/test_tools_tavily.py
git commit -m "feat: add tavily search wrapper"
```

---

## Phase 3 — Nodes

### Task 7: `fetch_meta` node

**Files:**
- Create: `src/repo_analyzer/nodes/fetch_meta.py`
- Test: `tests/test_nodes/test_fetch_meta.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_fetch_meta.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_fetch_meta.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement node**

`src/repo_analyzer/nodes/fetch_meta.py`:

```python
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
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_fetch_meta.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/repo_analyzer/nodes/fetch_meta.py tests/test_nodes/test_fetch_meta.py
git commit -m "feat: add fetch_meta node"
```

---

### Task 8: `plan` node

**Files:**
- Create: `src/repo_analyzer/prompts/plan.py`
- Create: `src/repo_analyzer/nodes/plan.py`
- Test: `tests/test_nodes/test_plan.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_plan.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_plan.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/plan.py`:

```python
PROMPT = """You are a senior code reviewer planning an analysis of a GitHub repo.

Repo: {owner}/{name}
Description: {description}
Language: {language}
Topics: {topics}
Stars: {stars}

README (first 3000 chars):
{readme}

File tree (first 500 paths):
{file_tree}

Plan an investigation that will produce:
1. A tech due-diligence verdict (should I use this?)
2. Concrete improvement advice for the maintainer
3. Ideas for products/applications on top of this technology

Output a JSON object with these fields:
- files_to_read: 5 to 15 file paths from the tree above (entry points, core modules, CI configs)
- similar_repos_query: a GitHub Search query string (no qualifiers, just keywords) to find similar projects
- web_queries: 2-3 web search queries to gather context (alternatives, known issues, trends)
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/plan.py`:

```python
"""plan node: LLM produces an investigation plan."""

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.plan import PROMPT
from repo_analyzer.state import Plan


def plan(state: dict) -> dict:
    meta = state["meta"]
    file_tree = meta.get("file_tree", [])[:500]
    readme = (meta.get("readme") or "")[:3000]

    llm = get_chat_model()
    structured = llm.with_structured_output(Plan)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | structured

    result: Plan = chain.invoke({
        "owner": meta.get("owner", ""),
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "language": meta.get("language", ""),
        "topics": ", ".join(meta.get("topics", [])),
        "stars": meta.get("stars", 0),
        "readme": readme,
        "file_tree": "\n".join(file_tree),
    })
    return {"plan": result}
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_plan.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/plan.py src/repo_analyzer/nodes/plan.py tests/test_nodes/test_plan.py
git commit -m "feat: add plan node with structured output"
```

---

### Task 9: `analyze_code` node

**Files:**
- Create: `src/repo_analyzer/prompts/analyze_code.py`
- Create: `src/repo_analyzer/nodes/analyze_code.py`
- Test: `tests/test_nodes/test_analyze_code.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_analyze_code.py`:

```python
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
        captured.update(arg)
        return {"path": "x.py", "summary": "", "quality_notes": []}
    fake_structured.invoke.side_effect = capture

    state = {"meta": {"owner": "o", "name": "r"},
             "plan": {"files_to_read": ["x.py"], "similar_repos_query": "", "web_queries": []}}
    node.analyze_code(state)
    assert len(captured["content"]) <= 50_000
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_analyze_code.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/analyze_code.py`:

```python
PROMPT = """You are reviewing a single file from a GitHub repo: {owner}/{name}

Path: {path}
Content:
```
{content}
```

Return JSON with:
- path: the file path (echo back)
- summary: 1-2 sentence description of what this file does
- quality_notes: list of strings (0-5 items) — concrete code quality observations (e.g. "no error handling", "tight coupling to X", "good test coverage"). Empty list if nothing notable.
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/analyze_code.py`:

```python
"""analyze_code node: reads each planned file and produces findings."""

import logging

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.analyze_code import PROMPT
from repo_analyzer.state import CodeFinding
from repo_analyzer.tools import github

log = logging.getLogger(__name__)
MAX_FILE_BYTES = 50_000


def analyze_code(state: dict) -> dict:
    owner = state["meta"]["owner"]
    name = state["meta"]["name"]
    files = state["plan"].get("files_to_read", [])

    llm = get_chat_model()
    structured = llm.with_structured_output(CodeFinding)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | structured

    findings: list[CodeFinding] = []
    for path in files:
        try:
            content = github.fetch_raw_file(owner, name, path)
        except Exception as e:
            log.warning("failed to fetch %s: %s", path, e)
            continue
        if not content or "\x00" in content[:1000]:  # skip binary
            continue
        if len(content) > MAX_FILE_BYTES:
            content = content[:MAX_FILE_BYTES]
        try:
            finding: CodeFinding = chain.invoke({
                "owner": owner, "name": name, "path": path, "content": content,
            })
            findings.append(finding)
        except Exception as e:
            log.warning("LLM failed on %s: %s", path, e)
    return {"code_findings": findings}
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_analyze_code.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/analyze_code.py src/repo_analyzer/nodes/analyze_code.py tests/test_nodes/test_analyze_code.py
git commit -m "feat: add analyze_code node"
```

---

### Task 10: `find_similar` node

**Files:**
- Create: `src/repo_analyzer/prompts/find_similar.py`
- Create: `src/repo_analyzer/nodes/find_similar.py`
- Test: `tests/test_nodes/test_find_similar.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_find_similar.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_find_similar.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/find_similar.py`:

```python
PROMPT = """Compare these two GitHub repos:

TARGET: {target_full_name}
Description: {target_description}
Language: {target_language}

CANDIDATE: {candidate_full_name}
Description: {candidate_description}
Stars: {candidate_stars}

Return JSON:
- full_name: candidate's full_name (echo back)
- description: candidate's description (echo back, may be empty)
- stars: candidate's star count (echo back)
- why_similar: 1-sentence reason these are in the same niche
- differentiator: 1-sentence on what makes the candidate distinct from the target

If they are NOT really similar, set why_similar to "NOT_SIMILAR" — caller will discard.
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/find_similar.py`:

```python
"""find_similar node: GitHub Search + LLM comparison."""

import logging

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.find_similar import PROMPT
from repo_analyzer.state import SimilarRepo
from repo_analyzer.tools import github

log = logging.getLogger(__name__)
MAX_KEEP = 5


def find_similar(state: dict) -> dict:
    query = state["plan"].get("similar_repos_query", "").strip()
    if not query:
        return {"similar_repos": []}

    target = state["meta"]
    candidates = github.search_repos(query, limit=10)

    llm = get_chat_model()
    structured = llm.with_structured_output(SimilarRepo)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | structured

    kept: list[SimilarRepo] = []
    for c in candidates:
        if c.get("full_name") == f"{target['owner']}/{target['name']}":
            continue
        try:
            comp: SimilarRepo = chain.invoke({
                "target_full_name": f"{target['owner']}/{target['name']}",
                "target_description": target.get("description", ""),
                "target_language": target.get("language", ""),
                "candidate_full_name": c.get("full_name", ""),
                "candidate_description": c.get("description", "") or "",
                "candidate_stars": c.get("stargazers_count", 0),
            })
        except Exception as e:
            log.warning("comparison failed for %s: %s", c.get("full_name"), e)
            continue
        if comp.get("why_similar") == "NOT_SIMILAR":
            continue
        kept.append(comp)
        if len(kept) >= MAX_KEEP:
            break
    return {"similar_repos": kept}
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_find_similar.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/find_similar.py src/repo_analyzer/nodes/find_similar.py tests/test_nodes/test_find_similar.py
git commit -m "feat: add find_similar node"
```

---

### Task 11: `web_context` node

**Files:**
- Create: `src/repo_analyzer/prompts/web_context.py`
- Create: `src/repo_analyzer/nodes/web_context.py`
- Test: `tests/test_nodes/test_web_context.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_web_context.py`:

```python
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
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_web_context.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/web_context.py`:

```python
PROMPT = """We searched the web for: "{query}"
While analyzing the repo {owner}/{name}.

Raw search results:
{results}

Return JSON with field `kept`: a list of objects (0 to 5) with:
- url: source URL
- title: source title
- relevant_quote: the most useful 1-2 sentence quote/insight from the snippet

Discard results that are off-topic, unrelated marketing, or duplicate. If nothing useful, return {{"kept": []}}.
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/web_context.py`:

```python
"""web_context node: Tavily search + LLM relevance filter."""

import logging
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.web_context import PROMPT
from repo_analyzer.state import WebSnippet
from repo_analyzer.tools import tavily

log = logging.getLogger(__name__)


class _FilterResult(TypedDict):
    kept: list[WebSnippet]


def web_context(state: dict) -> dict:
    queries = state["plan"].get("web_queries", [])
    if not queries:
        return {"web_snippets": []}

    target = state["meta"]
    llm = get_chat_model()
    structured = llm.with_structured_output(_FilterResult)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | structured

    all_kept: list[WebSnippet] = []
    for q in queries:
        raw = tavily.search(q, max_results=5)
        if not raw:
            continue
        formatted = "\n\n".join(f"[{r['url']}] {r['title']}\n{r['snippet']}" for r in raw)
        try:
            res: _FilterResult = chain.invoke({
                "query": q, "owner": target.get("owner", ""), "name": target.get("name", ""),
                "results": formatted,
            })
        except Exception as e:
            log.warning("filter failed for %r: %s", q, e)
            continue
        all_kept.extend(res.get("kept", []))
    return {"web_snippets": all_kept}
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_web_context.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/web_context.py src/repo_analyzer/nodes/web_context.py tests/test_nodes/test_web_context.py
git commit -m "feat: add web_context node"
```

---

### Task 12: `reflect` node

**Files:**
- Create: `src/repo_analyzer/prompts/reflect.py`
- Create: `src/repo_analyzer/nodes/reflect.py`
- Test: `tests/test_nodes/test_reflect.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_reflect.py`:

```python
from unittest.mock import MagicMock

from repo_analyzer.nodes import reflect as node


def _state_with_data():
    return {
        "meta": {"owner": "o", "name": "r"},
        "code_findings": [{"path": "a.py", "summary": "x", "quality_notes": []}],
        "similar_repos": [],
        "web_snippets": [],
        "reflection_iteration": 0,
    }


def test_reflect_marks_sufficient(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {"sufficient": True, "gaps": [], "rerun": ""}
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    result = node.reflect(_state_with_data())
    assert result["gaps"] == []
    assert result["reflection_iteration"] == 1
    assert result["rerun_branch"] == ""


def test_reflect_marks_gaps(monkeypatch):
    fake_structured = MagicMock()
    fake_structured.invoke.return_value = {
        "sufficient": False, "gaps": ["no similar repos"], "rerun": "find_similar"
    }
    fake_llm = MagicMock()
    fake_llm.with_structured_output.return_value = fake_structured
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)

    result = node.reflect(_state_with_data())
    assert result["gaps"] == ["no similar repos"]
    assert result["rerun_branch"] == "find_similar"
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_reflect.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/reflect.py`:

```python
PROMPT = """We have collected the following data about repo {owner}/{name}:

CODE FINDINGS ({n_code}):
{code_findings}

SIMILAR REPOS ({n_similar}):
{similar_repos}

WEB SNIPPETS ({n_web}):
{web_snippets}

Goal: produce a 3-section report:
  1. Tech due-diligence (should I use this?)
  2. Concrete improvement advice for the maintainer
  3. Ideas for products on top of this technology

Is the collected data ENOUGH to write all three sections with concrete substance?

Return JSON:
- sufficient: true if YES, false if NO
- gaps: list of strings — what specifically is missing (empty if sufficient)
- rerun: one of "analyze_code", "find_similar", "web_context", or "" — which single branch to re-run to address the biggest gap (empty if sufficient)
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/reflect.py`:

```python
"""reflect node: decides whether to loop back or proceed to synthesis."""

import json
from typing import TypedDict

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.reflect import PROMPT


class _ReflectResult(TypedDict):
    sufficient: bool
    gaps: list[str]
    rerun: str


def _fmt(items: list, key_order: list[str], limit: int = 10) -> str:
    if not items:
        return "(none)"
    rows = []
    for it in items[:limit]:
        rows.append(json.dumps({k: it.get(k) for k in key_order}, ensure_ascii=False))
    return "\n".join(rows)


def reflect(state: dict) -> dict:
    code = state.get("code_findings", [])
    similar = state.get("similar_repos", [])
    web = state.get("web_snippets", [])

    llm = get_chat_model()
    structured = llm.with_structured_output(_ReflectResult)
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | structured

    res: _ReflectResult = chain.invoke({
        "owner": state["meta"].get("owner", ""),
        "name": state["meta"].get("name", ""),
        "n_code": len(code),
        "n_similar": len(similar),
        "n_web": len(web),
        "code_findings": _fmt(code, ["path", "summary"]),
        "similar_repos": _fmt(similar, ["full_name", "differentiator"]),
        "web_snippets": _fmt(web, ["url", "relevant_quote"]),
    })
    return {
        "gaps": res.get("gaps", []),
        "rerun_branch": res.get("rerun", "") if not res.get("sufficient") else "",
        "reflection_iteration": state.get("reflection_iteration", 0) + 1,
    }
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_reflect.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/reflect.py src/repo_analyzer/nodes/reflect.py tests/test_nodes/test_reflect.py
git commit -m "feat: add reflect node"
```

---

### Task 13: `synthesize` node

**Files:**
- Create: `src/repo_analyzer/prompts/synthesize.py`
- Create: `src/repo_analyzer/nodes/synthesize.py`
- Test: `tests/test_nodes/test_synthesize.py`

- [ ] **Step 1: Write the failing test**

`tests/test_nodes/test_synthesize.py`:

```python
import os
from pathlib import Path
from unittest.mock import MagicMock

from repo_analyzer.nodes import synthesize as node


def test_synthesize_writes_markdown_to_reports_dir(tmp_path, monkeypatch):
    fake_llm = MagicMock()
    fake_llm.invoke.return_value = MagicMock(
        content="# Анализ репо o/r\n\n## 1. Tech due-diligence\nfoo\n## 2. Рекомендации автору\nbar\n## 3. Идеи поверх\nbaz"
    )
    monkeypatch.setattr(node, "get_chat_model", lambda: fake_llm)
    monkeypatch.setattr(node, "REPORTS_DIR", tmp_path)

    state = {
        "meta": {"owner": "o", "name": "r"},
        "code_findings": [], "similar_repos": [], "web_snippets": [],
        "gaps": [],
    }
    result = node.synthesize(state)
    assert "report_markdown" in result
    assert "1. Tech due-diligence" in result["report_markdown"]
    assert Path(result["report_path"]).exists()
    assert "o-r-" in Path(result["report_path"]).name
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_nodes/test_synthesize.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Write prompt**

`src/repo_analyzer/prompts/synthesize.py`:

```python
PROMPT = """You are writing a final analysis report for repo {owner}/{name}.

DATA COLLECTED:

Description: {description}
Language: {language}
Stars: {stars}
README excerpt:
{readme}

Code findings:
{code_findings}

Similar repos:
{similar_repos}

Web context:
{web_snippets}

Known data gaps (be honest about these):
{gaps}

Write a markdown report in Russian with EXACTLY this structure:

# Анализ репо {owner}/{name}

## 1. Tech due-diligence
- Краткое резюме что это
- Качество кода
- Активность и экосистема
- Стоит ли использовать: вердикт + альтернативы

## 2. Рекомендации автору
- Конкретные улучшения кода
- Чего не хватает по сравнению с похожими проектами
- Документация / DX-проблемы

## 3. Идеи поверх технологии
- Применения, которых ещё не видно в нише
- Возможные продуктовые надстройки

## Источники и ограничения
- Все упомянутые URL
- Что не удалось собрать (data gaps)

Be concrete and specific. Cite paths and URLs. No hedging fluff. If gaps exist, list them in the last section.
"""
```

- [ ] **Step 4: Implement node**

`src/repo_analyzer/nodes/synthesize.py`:

```python
"""synthesize node: produce final markdown report and save to file."""

import json
from datetime import datetime
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

from repo_analyzer.llm import get_chat_model
from repo_analyzer.prompts.synthesize import PROMPT

REPORTS_DIR = Path("reports")


def _fmt_list(items: list, key_order: list[str]) -> str:
    if not items:
        return "(none)"
    return "\n".join(json.dumps({k: it.get(k) for k in key_order}, ensure_ascii=False) for it in items)


def synthesize(state: dict) -> dict:
    meta = state["meta"]
    llm = get_chat_model()
    prompt = ChatPromptTemplate.from_messages([("user", PROMPT)])
    chain = prompt | llm

    msg = chain.invoke({
        "owner": meta.get("owner", ""),
        "name": meta.get("name", ""),
        "description": meta.get("description", ""),
        "language": meta.get("language", ""),
        "stars": meta.get("stars", 0),
        "readme": (meta.get("readme") or "")[:2000],
        "code_findings": _fmt_list(state.get("code_findings", []), ["path", "summary", "quality_notes"]),
        "similar_repos": _fmt_list(state.get("similar_repos", []), ["full_name", "stars", "differentiator"]),
        "web_snippets": _fmt_list(state.get("web_snippets", []), ["url", "title", "relevant_quote"]),
        "gaps": "\n".join(state.get("gaps", [])) or "(none)",
    })
    markdown = msg.content if hasattr(msg, "content") else str(msg)

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    date = datetime.utcnow().strftime("%Y-%m-%d")
    out = REPORTS_DIR / f"{meta['owner']}-{meta['name']}-{date}.md"
    out.write_text(markdown, encoding="utf-8")
    return {"report_markdown": markdown, "report_path": str(out)}
```

- [ ] **Step 5: Run — expect pass**

Run: `uv run pytest tests/test_nodes/test_synthesize.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/prompts/synthesize.py src/repo_analyzer/nodes/synthesize.py tests/test_nodes/test_synthesize.py
git commit -m "feat: add synthesize node"
```

---

## Phase 4 — Wiring

### Task 14: Build the graph and add smoke test

**Files:**
- Create: `src/repo_analyzer/graph.py`
- Test: `tests/test_graph_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

`tests/test_graph_smoke.py`:

```python
"""End-to-end test of the assembled graph with all I/O mocked.

This test verifies the graph topology: parallel branches converge at reflect,
reflect routes to synthesize on first iteration sufficient=True.
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

    # Mock LLM with staged responses (order: plan -> analyze_code -> find_similar -> reflect)
    fake_llm = _llm_with_responses([
        {"files_to_read": ["main.py"], "similar_repos_query": "test", "web_queries": []},  # plan
        {"path": "main.py", "summary": "entry", "quality_notes": []},                       # analyze_code
        {"full_name": "a/b", "description": "x", "stars": 100,                              # find_similar
         "why_similar": "test", "differentiator": "diff"},
        {"sufficient": True, "gaps": [], "rerun": ""},                                      # reflect
    ])
    monkeypatch.setattr("repo_analyzer.llm.get_chat_model", lambda: fake_llm)

    g = graph_module.build_graph()
    final = g.invoke({"repo_url": "https://github.com/o/r"})

    assert "1. Tech due-diligence" in final["report_markdown"]
    assert "2. Рекомендации автору" in final["report_markdown"]
    assert "3. Идеи поверх" in final["report_markdown"]
    assert final["meta"]["owner"] == "o"
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_graph_smoke.py -v`
Expected: ModuleNotFoundError on `repo_analyzer.graph`.

- [ ] **Step 3: Implement `graph.py`**

`src/repo_analyzer/graph.py`:

```python
"""LangGraph assembly.

Topology:
    fetch_meta -> plan -> {analyze_code, find_similar, web_context} (parallel)
                       -> reflect
                       -> [synthesize OR back to one branch (max 1 retry)]

Note on parallelism: we use 3 static add_edge calls from `plan`. LangGraph
runs them concurrently and merges their state updates (Annotated[..., add]).
For dynamic fan-out you would use `Send` instead.
"""

from langgraph.graph import END, START, StateGraph

from repo_analyzer.nodes.analyze_code import analyze_code
from repo_analyzer.nodes.fetch_meta import fetch_meta
from repo_analyzer.nodes.find_similar import find_similar
from repo_analyzer.nodes.plan import plan
from repo_analyzer.nodes.reflect import reflect
from repo_analyzer.nodes.synthesize import synthesize
from repo_analyzer.nodes.web_context import web_context
from repo_analyzer.state import State

MAX_REFLECTION_ITERATIONS = 1


def _route_after_reflect(state: dict) -> str:
    if state.get("reflection_iteration", 0) > MAX_REFLECTION_ITERATIONS:
        return "synthesize"
    rerun = state.get("rerun_branch", "")
    if rerun in ("analyze_code", "find_similar", "web_context"):
        return rerun
    return "synthesize"


def build_graph():
    g = StateGraph(State)

    g.add_node("fetch_meta", fetch_meta)
    g.add_node("plan", plan)
    g.add_node("analyze_code", analyze_code)
    g.add_node("find_similar", find_similar)
    g.add_node("web_context", web_context)
    g.add_node("reflect", reflect)
    g.add_node("synthesize", synthesize)

    g.add_edge(START, "fetch_meta")
    g.add_edge("fetch_meta", "plan")

    # parallel fan-out
    g.add_edge("plan", "analyze_code")
    g.add_edge("plan", "find_similar")
    g.add_edge("plan", "web_context")

    # converge at reflect
    g.add_edge("analyze_code", "reflect")
    g.add_edge("find_similar", "reflect")
    g.add_edge("web_context", "reflect")

    g.add_conditional_edges("reflect", _route_after_reflect, {
        "analyze_code": "analyze_code",
        "find_similar": "find_similar",
        "web_context": "web_context",
        "synthesize": "synthesize",
    })

    g.add_edge("synthesize", END)

    return g.compile()
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_graph_smoke.py -v`
Expected: 1 passed.

- [ ] **Step 5: Run all tests together**

Run: `uv run pytest -v`
Expected: all green (every test from Tasks 4-13 + smoke).

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/graph.py tests/test_graph_smoke.py
git commit -m "feat: assemble langgraph and add smoke test"
```

---

### Task 15: CLI entry point

**Files:**
- Create: `src/repo_analyzer/cli.py`
- Test: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:

```python
import sys
from unittest.mock import MagicMock

from repo_analyzer import cli


def test_cli_invokes_graph_with_url(monkeypatch, capsys):
    fake_graph = MagicMock()
    fake_graph.invoke.return_value = {
        "meta": {"owner": "o", "name": "r"},
        "report_markdown": "# Анализ\n",
        "report_path": "reports/o-r.md",
    }
    monkeypatch.setattr(cli, "build_graph", lambda: fake_graph)
    monkeypatch.setattr(sys, "argv", ["repo-analyzer", "https://github.com/o/r"])

    cli.main()

    fake_graph.invoke.assert_called_once_with({"repo_url": "https://github.com/o/r"})
    captured = capsys.readouterr()
    assert "reports/o-r.md" in captured.out


def test_cli_exits_on_missing_url(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["repo-analyzer"])
    try:
        cli.main()
    except SystemExit as e:
        assert e.code != 0
    else:
        raise AssertionError("expected SystemExit")
```

- [ ] **Step 2: Run — expect failure**

Run: `uv run pytest tests/test_cli.py -v`
Expected: ModuleNotFoundError on `repo_analyzer.cli`.

- [ ] **Step 3: Implement CLI**

`src/repo_analyzer/cli.py`:

```python
"""CLI: `python -m repo_analyzer <github-url>`"""

import argparse
import logging
import sys

from dotenv import load_dotenv

from repo_analyzer.graph import build_graph

log = logging.getLogger(__name__)


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(prog="repo-analyzer")
    parser.add_argument("repo_url", help="GitHub repo URL, e.g. https://github.com/owner/repo")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    print(f"Analyzing {args.repo_url} ...", flush=True)
    graph = build_graph()
    final = graph.invoke({"repo_url": args.repo_url})

    print(f"\nReport written to: {final['report_path']}\n")
    print("=" * 60)
    print(final["report_markdown"])


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run — expect pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 5: Smoke-run the CLI with --help (no API calls)**

Run: `uv run python -m repo_analyzer --help`
Expected: prints argparse help.

- [ ] **Step 6: Commit**

```bash
git add src/repo_analyzer/cli.py tests/test_cli.py
git commit -m "feat: add cli entry point"
```

---

## Phase 5 — Live test, README, polish

### Task 16: Live end-to-end test

**Files:**
- Test: `tests/test_live.py`

- [ ] **Step 1: Write the live test**

`tests/test_live.py`:

```python
"""Live test against real APIs. Run manually:
    uv run pytest -m live -s
Requires .env with ANTHROPIC_API_KEY, GITHUB_TOKEN, TAVILY_API_KEY.
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

from repo_analyzer.graph import build_graph

LIVE_REPO = "https://github.com/tiangolo/typer"


@pytest.mark.live
def test_live_run_on_typer():
    load_dotenv()
    for var in ("ANTHROPIC_API_KEY", "GITHUB_TOKEN", "TAVILY_API_KEY"):
        assert os.environ.get(var), f"{var} must be set in .env"

    graph = build_graph()
    final = graph.invoke({"repo_url": LIVE_REPO})

    assert "1. Tech due-diligence" in final["report_markdown"]
    assert "2. Рекомендации автору" in final["report_markdown"]
    assert "3. Идеи поверх" in final["report_markdown"]
    assert Path(final["report_path"]).exists()
```

- [ ] **Step 2: Verify normal `pytest` skips it**

Run: `uv run pytest -v`
Expected: all previous tests pass, `test_live_run_on_typer` is **not** collected (because of `-m live` marker).

- [ ] **Step 3: Commit (without running live)**

```bash
git add tests/test_live.py
git commit -m "test: add live integration test (manual)"
```

- [ ] **Step 4: Run live test manually**

Make sure `.env` exists with all three keys. Then:

Run: `uv run pytest -m live -s`
Expected: passes within ~5 minutes, prints log lines, writes a real report into `reports/tiangolo-typer-<date>.md`.

- [ ] **Step 5: Inspect the report by hand**

```bash
cat reports/tiangolo-typer-*.md
```

Read it as a human. Check:
- All three sections present and non-empty.
- File paths cited in section 1/2 actually exist in typer's repo.
- Recommendations are specific (not generic LLM hedging).

If quality is poor — note issues and iterate on prompts (in `src/repo_analyzer/prompts/*.py`). Prompts are the main lever.

---

### Task 17: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write README**

`README.md`:

````markdown
# Repo Analyzer

Учебный LangGraph-агент: принимает URL публичного GitHub-репозитория и выдаёт markdown-отчёт из трёх секций — tech due-diligence, советы автору, идеи продуктов поверх технологии.

## Установка

```bash
uv sync
cp .env.example .env
# открой .env и впиши три ключа
```

## Запуск

```bash
uv run python -m repo_analyzer https://github.com/tiangolo/typer
```

Отчёт пишется в `reports/<owner>-<repo>-<date>.md` и одновременно печатается в stdout.

## Архитектура

См. `docs/superpowers/specs/2026-05-07-github-repo-analyzer-design.md`.

Граф из 7 узлов: `fetch_meta` → `plan` → 3 параллельные ветки (`analyze_code`, `find_similar`, `web_context`) → `reflect` → (loop or) `synthesize`.

## Тесты

```bash
uv run pytest -v          # все юнит и smoke тесты с моками
uv run pytest -m live -s  # реальные API (нужны ключи)
```

## Стоимость прогона

На среднем репо (10-15 файлов): ~10-30 центов на Claude Sonnet 4.6 + бесплатные tier-ы GitHub и Tavily.
````

- [ ] **Step 2: Verify it renders sensibly**

Run: `head -30 README.md`
Expected: clean markdown, no broken backticks.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: add README"
```

---

## Self-Review Notes

**Spec coverage check:** every requirement traced —

- 3-section report → Task 13 (`synthesize`) prompt enforces structure.
- Smart-выборка файлов (5-15) → Task 8 (`plan`) prompt enforces count.
- Параллельные ветки → Task 14 (`graph.py`) static fan-out edges.
- Reflection loop с лимитом 1 → Task 14 (`_route_after_reflect`) checks `reflection_iteration > MAX`.
- Tavily failure tolerated → Task 6 (`tools/tavily.py`) returns `[]` on exception.
- GitHub 404/5xx handled → Task 5 (`tools/github.py`) raises `RepoNotFoundError` / retries 3x.
- Файлы > 50KB обрезаются → Task 9 (`analyze_code.py`) `MAX_FILE_BYTES`.
- Markdown пишется в `reports/{owner}-{name}-{date}.md` → Task 13.
- CLI `python -m repo_analyzer <url>` → Task 15.
- Один узел = один файл → enforced by file structure throughout Phase 3.
- Промпты отдельно от логики → `prompts/` directory used in every node task.
- Tests at Levels 1 (unit per node), 2 (smoke), 3 (live) → Tasks 4-13, 14, 16.

**Type consistency:** `Plan`, `RepoMeta`, `CodeFinding`, `SimilarRepo`, `WebSnippet`, `State` defined in Task 3 are referenced consistently across Tasks 7-13.

**No placeholders:** every task has full code, exact commands, expected outcomes.

---

## Execution Handoff

Plan complete. Two ways to run it:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent for each task, review output between tasks, fast iteration with strong isolation.

**2. Inline Execution** — execute tasks here in this session, with checkpoints for your review.
