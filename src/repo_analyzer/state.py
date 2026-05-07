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

    gaps: list[str]

    report_markdown: str
    report_path: str
