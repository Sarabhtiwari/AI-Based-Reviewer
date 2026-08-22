"""
Looks up a paper's full details (especially its abstract) on Semantic
Scholar by searching for its title.

Why this file exists:
Google Scholar profile pages (see google_scholars.py) give us titles and
years but rarely full abstracts. Semantic Scholar's API often has richer
abstracts for the same papers. This connector bridges that gap: given a
paper title, it searches Semantic Scholar and returns the best-matching
paper's abstract (if found).

This only touches PUBLIC data, so there's no confidentiality concern.
"""

import time
import httpx
from app.config.settings import settings


def find_abstract_by_title(title: str, max_retries: int = 3) -> str:
    """
    Searches Semantic Scholar for a paper matching the given title and
    returns its abstract, or an empty string if not found.

    Retries on 429 (rate limit) with increasing backoff, since the
    unauthenticated/free tier is easy to hit when looping over many papers.
    """
    if not title or not title.strip():
        return ""

    url = f"{settings.semantic_scholar_base_url}/paper/search"
    params = {"query": title, "fields": "title,abstract", "limit": 1}

    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    for attempt in range(max_retries):
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        except httpx.HTTPError:
            return ""

        if response.status_code == 429:
            wait_seconds = 5 * (attempt + 1)  # 5s, 10s, 15s
            time.sleep(wait_seconds)
            continue

        if response.status_code != 200:
            return ""

        data = response.json()
        results = data.get("data", [])
        if not results:
            return ""

        return results[0].get("abstract") or ""

    return ""  # gave up after max_retries


def enrich_papers_with_abstracts(papers: list[dict]) -> list[dict]:
    """
    Takes a list of paper dicts (each with at least a 'title' key, as
    returned by the Google Scholar connector) and fills in an 'abstract'
    key for each one by searching Semantic Scholar, if not already present.

    Adds a small delay between calls to be polite to the free-tier rate
    limit when processing many papers in a loop.
    """
    for paper in papers:
        if not paper.get("abstract"):
            paper["abstract"] = find_abstract_by_title(paper.get("title", ""))
            time.sleep(1)  # space out requests to avoid hitting 429 repeatedly
    return papers