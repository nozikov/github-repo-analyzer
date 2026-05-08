"""CLI: `python -m repo_analyzer <github-url>`"""

import argparse
import logging
import os
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

    if os.environ.get("LANGSMITH_TRACING", "").lower() in ("true", "1"):
        project = os.environ.get("LANGSMITH_PROJECT", "default")
        print(f"LangSmith tracing enabled — project: {project}", flush=True)

    print(f"Analyzing {args.repo_url} ...", flush=True)
    graph = build_graph()
    final = graph.invoke({"repo_url": args.repo_url})

    print(f"\nReport written to: {final['report_path']}\n")
    print("=" * 60)
    print(final["report_markdown"])


if __name__ == "__main__":
    sys.exit(main())
