"""All Semantic Scholar logic: rate-limited client, identity resolution, paper fetching."""

import re
import time
from collections import Counter

import httpx
from app.config.settings import settings

_BASE = settings.semantic_scholar_base_url


def _get(url: str, params: dict, max_retries: int = 3):
    """GET with the 1 request/second limit enforced."""
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    response = None
    for attempt in range(max_retries):
        response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        time.sleep(1.1)
        if response.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        return response
    return response


def _clean_name(name: str) -> str:
    return re.sub(r"^(Dr\.?|Prof\.?)\s+", "", name.strip(), flags=re.IGNORECASE)


def find_author_id_via_titles(
    name: str, known_titles: list[str], sample_size: int = 8, min_votes: int = 2
) -> str | None:
    """
    Search a sample of the professor's known paper titles. Whichever author ID
    (with a matching surname) shows up repeatedly is the professor.
    """
    surname = _clean_name(name).lower().split()[-1]
    votes: Counter = Counter()

    for title in known_titles[:sample_size]:
        response = _get(f"{_BASE}/paper/search",
                        {"query": title, "fields": "title,authors", "limit": 1})
        if response is None or response.status_code != 200:
            continue
        results = response.json().get("data", [])
        if not results:
            continue
        for author in results[0].get("authors", []):
            if surname in (author.get("name") or "").lower().split() and author.get("authorId"):
                votes[author["authorId"]] += 1

    if not votes:
        return None
    best_id, best_count = votes.most_common(1)[0]
    return best_id if best_count >= min_votes else None


def fetch_author_papers(author_id: str, max_papers: int = 300) -> list[dict]:
    """All papers of an author (paged), each with abstract + co-authors (with IDs)."""
    publications, offset = [], 0
    while offset < max_papers:
        response = _get(
            f"{_BASE}/author/{author_id}/papers",
            {"fields": "title,abstract,year,authors", "limit": 100, "offset": offset},
        )
        if response is None or response.status_code != 200:
            break
        body = response.json()
        for p in body.get("data", []):
            publications.append({
                "title": p.get("title"),
                "year": p.get("year"),
                "abstract": p.get("abstract") or "",
                "coauthors": [
                    {"name": a.get("name"), "authorId": a.get("authorId")}
                    for a in p.get("authors", [])
                    if a.get("authorId") and a.get("authorId") != author_id
                ],
            })
        if "next" not in body:
            break
        offset = body["next"]
    return publications


# --- Confidential paper authors (name only, best effort) ---

def find_author_id_by_name(name: str) -> str | None:
    if not name or not name.strip():
        return None
    response = _get(f"{_BASE}/author/search",
                    {"query": _clean_name(name), "fields": "name,authorId", "limit": 1})
    if response is None or response.status_code != 200:
        return None
    results = response.json().get("data", [])
    return results[0].get("authorId") if results else None


def resolve_author_ids_by_names(names: list[str]) -> list[str]:
    ids = (find_author_id_by_name(n) for n in names)
    return [i for i in ids if i]

def resolve_authors(names: list[str]) -> list[dict]:
    """
    Like resolve_author_ids_by_names, but reports every name, including the
    ones that could not be found, so "not checked" is never hidden.
    Returns [{"name": str, "authorId": str | None}, ...]
    """
    return [{"name": n, "authorId": find_author_id_by_name(n)} for n in names if n and n.strip()]