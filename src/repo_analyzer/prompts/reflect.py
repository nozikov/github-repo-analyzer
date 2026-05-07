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
