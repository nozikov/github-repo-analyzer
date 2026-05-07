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
