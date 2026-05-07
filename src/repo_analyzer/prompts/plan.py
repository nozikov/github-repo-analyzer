PROMPT = """You are a senior code reviewer planning an analysis of a GitHub repo.

Repo: {owner}/{name}
Description: {description}
Language: {language}
Topics: {topics}
Stars: {stars}

README (first 3000 chars):
{readme}

File tree (first 500 paths):
{file_tree}

Plan an investigation that will produce:
1. A tech due-diligence verdict (should I use this?)
2. Concrete improvement advice for the maintainer
3. Ideas for products/applications on top of this technology

Output a JSON object with these fields:
- files_to_read: 5 to 15 file paths from the tree above (entry points, core modules, CI configs)
- similar_repos_query: a GitHub Search query string (no qualifiers, just keywords) to find similar projects
- web_queries: 2-3 web search queries to gather context (alternatives, known issues, trends)
"""
