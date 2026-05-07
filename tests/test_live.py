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
