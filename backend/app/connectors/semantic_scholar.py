"""All Semantic Scholar logic: rate-limited client, identity resolution, paper fetching."""

import re
import time
from collections import Counter
from difflib import SequenceMatcher

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


def _norm_title(title: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


def filter_papers_by_titles(
    papers: list[dict], known_titles: list[str], fuzzy_threshold: float = 0.92
) -> dict:
    """
    Keep only S2 papers whose title matches one of the titles on the professor's
    Scholar/ORCID list (exact after normalising, else fuzzy >= threshold).
    match_percent = share of the known titles found among the S2 papers,
    i.e. how well this S2 profile covers the professor's real list.
    """
    known = {n for n in (_norm_title(t) for t in known_titles) if n}
    matched_known: set[str] = set()
    kept, dropped = [], []

    for paper in papers:
        norm = _norm_title(paper.get("title"))
        hit = None
        if norm in known:
            hit = norm
        elif norm:
            for k in known:
                sm = SequenceMatcher(None, norm, k)
                if sm.real_quick_ratio() >= fuzzy_threshold \
                        and sm.quick_ratio() >= fuzzy_threshold \
                        and sm.ratio() >= fuzzy_threshold:
                    hit = k
                    break
        if hit:
            matched_known.add(hit)
            kept.append(paper)
        else:
            dropped.append(paper.get("title"))

    pct = round(100 * len(matched_known) / len(known), 1) if known else 0.0
    return {"papers": kept, "match_percent": pct,
            "kept": len(kept), "dropped": len(dropped), "dropped_titles": dropped}


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
            {"fields": "paperId,title,abstract,year,authors", "limit": 100, "offset": offset},
        )
        if response is None or response.status_code != 200:
            break
        body = response.json()
        for p in body.get("data", []):
            publications.append({
                "paper_id": p.get("paperId"),
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
    """[{"name": ..., "authorId": id-or-None}, ...], one entry per input name."""
    return [{"name": n, "authorId": find_author_id_by_name(n)} for n in names if n and n.strip()]