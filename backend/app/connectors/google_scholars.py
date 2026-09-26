"""
Fetches a professor's full academic profile, given only a Google Scholar ID.

Flow:
1. Fetch name + paper titles directly from the Google Scholar HTML page
   (deterministic regex parsing, no AI/scraping-tool needed)
2. Search Semantic Scholar by name -- since names can collide, disambiguate
   by checking which candidate's papers overlap with the titles from step 1
3. Once confirmed, fetch the FULL data (papers + abstracts + co-authors)
   from Semantic Scholar using the disambiguated author ID

This replaces the earlier Tavily+Groq scraping approach: Semantic Scholar
gives abstracts and co-authors directly, so no separate enrichment step
or AI parsing is needed anymore.
"""

import re
import time
import httpx
from app.config.settings import settings

_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}


def _get_semantic_scholar(url: str, params: dict, max_retries: int = 3):
    """Rate-limit-safe GET for Semantic Scholar (1 req/sec limit)."""
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    for attempt in range(max_retries):
        response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        time.sleep(1.1)  # always pace, even after success

        if response.status_code == 200:
            return response
        if response.status_code == 429:
            time.sleep(3 * (attempt + 1))
            continue
        return response

    return response


def _fetch_scholar_name(scholar_id: str) -> str:
    """Deterministically extracts the profile owner's name from Google Scholar's HTML."""
    profile_url = f"https://scholar.google.com/citations?user={scholar_id}&hl=en"
    response = httpx.get(profile_url, headers=_BROWSER_HEADERS, timeout=30.0)
    response.raise_for_status()

    match = re.search(r'<div id="gsc_prf_in">(.*?)</div>', response.text)
    if not match:
        return "Unknown"

    return re.sub(r"<[^>]+>", "", match.group(1)).strip() or "Unknown"


def _fetch_scholar_paper_titles(scholar_id: str, max_papers: int = 100) -> list[str]:
    """
    Deterministically extracts paper titles from Google Scholar's HTML.
    Titles sit inside <a class="gsc_a_at">Title Here</a> elements on the
    profile page -- a fixed, predictable structure, no AI parsing needed.
    """
    profile_url = (
        f"https://scholar.google.com/citations?user={scholar_id}"
        f"&hl=en&cstart=0&pagesize={max_papers}"
    )
    response = httpx.get(profile_url, headers=_BROWSER_HEADERS, timeout=30.0)
    response.raise_for_status()

    titles = re.findall(r'<a[^>]*class="gsc_a_at"[^>]*>(.*?)</a>', response.text)
    return [re.sub(r"<[^>]+>", "", t).strip() for t in titles if t.strip()]


def find_author_id_by_name_and_papers(
    name: str, known_paper_titles: list[str], min_overlap: int = 3
) -> str | None:
    if not name or not name.strip():
        return None

    clean_name = re.sub(r"^(Dr\.?|Prof\.?)\s+", "", name.strip(), flags=re.IGNORECASE)

    url = f"{settings.semantic_scholar_base_url}/author/search"
    params = {"query": clean_name, "fields": "name,authorId,papers.title", "limit": 100}

    response = _get_semantic_scholar(url, params)
    if response.status_code != 200:
        return None

    candidates = response.json().get("data", [])
    if not candidates:
        return None

    known_titles_lower = {t.lower().strip() for t in known_paper_titles}

    best_match_id = None
    best_match_score = 0

    for candidate in candidates:
        candidate_titles = {
            p.get("title", "").lower().strip() for p in candidate.get("papers", [])
        }
        overlap = len(known_titles_lower & candidate_titles)

        if overlap > best_match_score:
            best_match_score = overlap
            best_match_id = candidate.get("authorId")

    if best_match_score < min_overlap:
        return None

    return best_match_id

def find_author_id_via_paper_titles(name: str, known_paper_titles: list[str], sample_size: int = 8) -> str | None:
    """
    More reliable alternative to name-search disambiguation: searches
    Semantic Scholar for a SAMPLE of the professor's known papers by
    exact title, and checks which Author ID appears consistently among
    the paper's listed authors (matching the professor's name). This
    works because paper-level author lists are already correctly
    disambiguated by Semantic Scholar -- no separate guessing needed.
    """
    from collections import Counter

    name_parts = set(re.sub(r"^(Dr\.?|Prof\.?)\s+", "", name, flags=re.IGNORECASE).lower().split())

    id_votes = Counter()

    sample_titles = known_paper_titles[:sample_size]

    for title in sample_titles:
        url = f"{settings.semantic_scholar_base_url}/paper/search"
        params = {"query": title, "fields": "title,authors", "limit": 1}

        response = _get_semantic_scholar(url, params)
        if response.status_code != 200:
            continue

        results = response.json().get("data", [])
        if not results:
            continue

        paper = results[0]
        for author in paper.get("authors", []):
            author_name_parts = set(author.get("name", "").lower().split())
            # Check if this author's name shares meaningful overlap with our target name
            if name_parts & author_name_parts:
                aid = author.get("authorId")
                if aid:
                    id_votes[aid] += 1

    if not id_votes:
        return None

    # Return the Author ID that showed up most consistently across the sample
    best_id, best_count = id_votes.most_common(1)[0]

    # Require it to have matched on at least 2 different papers to be confident
    if best_count < 2:
        return None

    return best_id

def get_full_professor_data(scholar_id: str) -> dict:
    """
    The main entry point: given a Google Scholar ID, returns the
    professor's name, Semantic Scholar Author ID, and full paper list
    (with abstracts and co-authors, each with their own Author IDs).
    """
    name = _fetch_scholar_name(scholar_id)
    known_titles = _fetch_scholar_paper_titles(scholar_id)

    author_id = find_author_id_via_paper_titles(name, known_titles)
    if not author_id:
        return {
            "name": name,
            "scholar_id": scholar_id,
            "semantic_scholar_author_id": None,
            "publications": [],
            "error": "Could not confidently disambiguate this professor on Semantic Scholar",
        }

    url = f"{settings.semantic_scholar_base_url}/author/{author_id}/papers"
    params = {"fields": "title,abstract,year,authors", "limit": 100}

    response = _get_semantic_scholar(url, params)
    papers_raw = response.json().get("data", []) if response.status_code == 200 else []

    publications = []
    for p in papers_raw:
        coauthors = [
            {"name": a.get("name"), "authorId": a.get("authorId")}
            for a in p.get("authors", [])
            if a.get("authorId") != author_id
        ]
        publications.append({
            "title": p.get("title"),
            "year": p.get("year"),
            "abstract": p.get("abstract") or "",
            "coauthors": coauthors,
        })

    return {
        "name": name,
        "scholar_id": scholar_id,
        "semantic_scholar_author_id": author_id,
        "publications": publications,
    }

def find_author_id_by_name_simple(name: str) -> str | None:
    """
    Simple fallback resolver: given just a name (no known papers to
    cross-check against -- e.g. a confidential paper's author), searches
    Semantic Scholar and returns the FIRST matching author's ID.

    Less precise than find_author_id_via_paper_titles() -- use this only
    for the confidential paper's authors, where we don't have (and don't
    want to expose) a list of their papers to disambiguate against.
    """
    if not name or not name.strip():
        return None

    clean_name = re.sub(r"^(Dr\.?|Prof\.?)\s+", "", name.strip(), flags=re.IGNORECASE)

    url = f"{settings.semantic_scholar_base_url}/author/search"
    params = {"query": clean_name, "fields": "name,authorId", "limit": 1}

    response = _get_semantic_scholar(url, params)
    if response.status_code != 200:
        return None

    results = response.json().get("data", [])
    if not results:
        return None

    return results[0].get("authorId")


def resolve_author_ids_by_names(names: list[str]) -> list[str]:
    """
    Resolves a list of confidential-paper author names to Semantic
    Scholar author IDs, skipping any that couldn't be resolved.
    """
    ids = []
    for name in names:
        aid = find_author_id_by_name_simple(name)
        if aid:
            ids.append(aid)
    return ids