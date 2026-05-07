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
