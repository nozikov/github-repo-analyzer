PROMPT = """Compare these two GitHub repos:

TARGET: {target_full_name}
Description: {target_description}
Language: {target_language}

CANDIDATE: {candidate_full_name}
Description: {candidate_description}
Stars: {candidate_stars}

Return JSON:
- full_name: candidate's full_name (echo back)
- description: candidate's description (echo back, may be empty)
- stars: candidate's star count (echo back)
- why_similar: 1-sentence reason these are in the same niche
- differentiator: 1-sentence on what makes the candidate distinct from the target

If they are NOT really similar, set why_similar to "NOT_SIMILAR" — caller will discard.
"""
