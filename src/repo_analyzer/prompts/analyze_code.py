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
