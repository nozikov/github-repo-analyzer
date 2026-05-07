"""LangGraph assembly.

Topology:
    fetch_meta -> plan -> {analyze_code, find_similar, web_context} (parallel)
                       -> synthesize -> END

Note on parallelism: we use 3 static add_edge calls from `plan`. LangGraph
runs them concurrently and merges their state updates (Annotated[..., add]).
For dynamic fan-out you would use `Send` instead.

V1 ships without the reflection loop. The loop is in the spec for V2 — it
requires a 'replace' reducer for branch lists and gap-aware re-prompts to be
useful, neither of which V1 has.
"""

from langgraph.graph import END, START, StateGraph

from repo_analyzer.nodes.analyze_code import analyze_code
from repo_analyzer.nodes.fetch_meta import fetch_meta
from repo_analyzer.nodes.find_similar import find_similar
from repo_analyzer.nodes.plan import plan
from repo_analyzer.nodes.synthesize import synthesize
from repo_analyzer.nodes.web_context import web_context
from repo_analyzer.state import State


def build_graph():
    g = StateGraph(State)

    g.add_node("fetch_meta", fetch_meta)
    g.add_node("plan", plan)
    g.add_node("analyze_code", analyze_code)
    g.add_node("find_similar", find_similar)
    g.add_node("web_context", web_context)
    g.add_node("synthesize", synthesize)

    g.add_edge(START, "fetch_meta")
    g.add_edge("fetch_meta", "plan")

    # parallel fan-out
    g.add_edge("plan", "analyze_code")
    g.add_edge("plan", "find_similar")
    g.add_edge("plan", "web_context")

    # converge directly at synthesize
    g.add_edge("analyze_code", "synthesize")
    g.add_edge("find_similar", "synthesize")
    g.add_edge("web_context", "synthesize")

    g.add_edge("synthesize", END)

    return g.compile()
