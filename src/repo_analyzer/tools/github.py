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
    """Return file content (UTF-8). Falls back to raw URL for files >1MB."""
    data = _get(f"{API}/repos/{owner}/{name}/contents/{path}").json()
    content = data.get("content")
    encoding = data.get("encoding")
    if content and encoding == "base64":
        return base64.b64decode(content).decode("utf-8", errors="replace")
    # File too large for contents API — use raw URL
    raw_url = f"https://raw.githubusercontent.com/{owner}/{name}/HEAD/{path}"
    with _client() as c:
        r = c.get(raw_url)
        if r.status_code == 200:
            return r.text
    return ""


def search_repos(query: str, limit: int = 10) -> list[dict[str, Any]]:
    data = _get(
        f"{API}/search/repositories",
        params={"q": query, "sort": "stars", "per_page": str(limit)},
    ).json()
    return data.get("items", [])
