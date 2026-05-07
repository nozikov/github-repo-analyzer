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
