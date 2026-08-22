"""
Aggregates per-paper keywords into a single professor-level expertise
profile: a ranked list of the topics this professor works on most,
based on how often each keyword appears across their papers.

This is the actual "reviewer expertise discovery" deliverable -- turning
a list of papers into a clean, explainable summary of what this person
is an expert in.
"""

from collections import Counter


def build_expertise_profile(
    professor_name: str,
    papers_with_keywords: list[dict],
    top_n: int = 15,
) -> dict:
    """
    Takes a list of paper dicts (each with a 'keywords' list, as produced
    by extract_keywords_for_papers) and returns an aggregated profile.

    Keywords are counted case-insensitively so "Machine Learning" and
    "machine learning" are treated as the same topic, but the profile
    keeps the most common casing/version for display.

    Example return shape:
        {
            "professor_name": "Deepak Gupta",
            "num_papers_analyzed": 20,
            "top_keywords": [
                {"keyword": "machine learning", "count": 8},
                {"keyword": "support vector machines", "count": 5},
                ...
            ]
        }
    """
    # Track occurrences case-insensitively, but remember one "display"
    # version of each keyword's original casing.
    counts: Counter = Counter()
    display_form: dict[str, str] = {}

    for paper in papers_with_keywords:
        for kw in paper.get("keywords", []):
            key = kw.lower().strip()
            if not key:
                continue
            counts[key] += 1
            display_form.setdefault(key, kw.strip())

    top_keywords = [
        {"keyword": display_form[key], "count": count}
        for key, count in counts.most_common(top_n)
    ]

    return {
        "professor_name": professor_name,
        "num_papers_analyzed": len(papers_with_keywords),
        "top_keywords": top_keywords,
    }