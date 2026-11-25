"""All Semantic Scholar logic: rate-limited client, identity resolution, paper fetching."""

import re
import time
from collections import Counter
from difflib import SequenceMatcher

import httpx
from app.config.settings import settings

_BASE = settings.semantic_scholar_base_url


def _get(url: str, params: dict, max_retries: int = 4):
    """
    GET with the 1 request/second limit enforced.
    Retries on: network errors/timeouts, HTTP 429 (too many requests) and HTTP 5xx.
    Returns the last response (possibly an error one) or None if nothing ever answered.
    """
    headers = {}
    if settings.semantic_scholar_api_key:
        headers["x-api-key"] = settings.semantic_scholar_api_key

    response = None
    for attempt in range(max_retries):
        try:
            response = httpx.get(url, params=params, headers=headers, timeout=30.0)
        except (httpx.TransportError, OSError):
            response = None                      # timeout / connection failed: wait, try again
            time.sleep(2 * (attempt + 1))
            continue
        time.sleep(1.1)
        if response.status_code == 429 or response.status_code >= 500:
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


def _name_tokens(name: str | None) -> list[str]:
    return re.findall(r"[a-z0-9]+", (name or "").lower())


def _tally(hits: list[list[dict]], token: str, other: str) -> tuple[Counter, Counter]:
    """votes[id] = papers where an author whose name contains `token` has that id.
    bonus[id] = tie-breaker: +2 per paper if the author's name also contains the full
    `other` name part (e.g. the first name), +1 if only its first letter matches."""
    votes, bonus = Counter(), Counter()
    for authors in hits:
        for a in authors:
            aid = a.get("authorId")
            toks = _name_tokens(a.get("name"))
            if aid and token in toks:
                votes[aid] += 1
                rest = [t for t in toks if t != token]
                if other in rest:
                    bonus[aid] += 2
                elif any(t[:1] == other[:1] for t in rest):
                    bonus[aid] += 1
    return votes, bonus


def _pick(votes: Counter, bonus: Counter, min_votes: int) -> str | None:
    if not votes:
        return None
    ranked = sorted(votes, key=lambda k: (votes[k], bonus[k]), reverse=True)
    best = ranked[0]
    if votes[best] < min_votes:
        return None
    # two different authors equally good (e.g. two "Gupta" co-authors): refuse to guess
    if len(ranked) > 1 and (votes[ranked[1]], bonus[ranked[1]]) == (votes[best], bonus[best]):
        return None
    return best


def find_author_id_via_titles(
    name: str, known_titles: list[str], sample_size: int = 15, min_votes: int = 2
) -> str | None:
    """
    Search the professor's known paper titles on Semantic Scholar. Whichever author ID
    (with a matching surname) shows up repeatedly is the professor.

    More robust than before:
      - a search only counts if the returned paper's title really matches the searched title
      - failed searches (429/timeouts) are skipped and the next title is tried
      - stops early once one author clearly leads (fewer requests, fewer rate-limit hits)
      - the first name breaks ties between authors that share a surname
      - if NO author has the surname (name stored in swapped order), the first name is tried
      - on a real tie it returns None instead of guessing
    """
    parts = [p for p in _name_tokens(_clean_name(name)) if len(p) >= 2]
    if not parts:
        return None
    surname, first = parts[-1], parts[0]

    hits: list[list[dict]] = []
    attempted = failed = 0
    for title in known_titles[:sample_size]:
        response = _get(f"{_BASE}/paper/search",
                        {"query": title, "fields": "title,authors", "limit": 1})
        attempted += 1
        if response is None or response.status_code != 200:
            failed += 1
            continue
        results = response.json().get("data", [])
        if not results:
            continue
        top = results[0]
        if SequenceMatcher(None, _norm_title(top.get("title")), _norm_title(title)).ratio() < 0.85:
            continue  # search returned some other paper; do not let it vote
        hits.append(top.get("authors") or [])

        votes, _ = _tally(hits, surname, first)
        ranked = votes.most_common(2)
        if ranked and ranked[0][1] >= 3 and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]):
            break

    votes, bonus = _tally(hits, surname, first)
    best = _pick(votes, bonus, min_votes) if votes else None
    if best:
        return best
    # No winner. If Semantic Scholar mostly did not ANSWER, that is a temporary problem,
    # not proof that the person is unknown: say so instead of returning "not found".
    if attempted and failed >= max(2, attempted // 2):
        raise RuntimeError(f"Semantic Scholar did not answer {failed} of {attempted} title searches")
    if votes:
        return None
    # Fallback for a name stored in swapped order ("Yadav Rama"): the matching author must
    # also agree on the other name part (at least its first letter) on every paper, so a
    # co-author who only shares a first name cannot be picked.
    votes, bonus = _tally(hits, first, surname)
    votes = Counter({k: v for k, v in votes.items() if bonus[k] >= v})
    return _pick(votes, bonus, min_votes)


def find_author_candidates_by_name(name: str, limit: int = 10) -> list[str]:
    """
    Several Semantic Scholar author IDs whose name contains the person's surname.
    Used only as a fallback; the caller must verify each candidate by title overlap.
    Raises if Semantic Scholar did not answer (so the caller can call it temporary).
    """
    parts = [p for p in _name_tokens(_clean_name(name)) if len(p) >= 2]
    if not parts:
        return []
    query = re.sub(r"^[\W_]+", "", _clean_name(name))
    response = _get(f"{_BASE}/author/search",
                    {"query": query, "fields": "name,authorId", "limit": limit})
    if response is None or response.status_code != 200:
        status = None if response is None else response.status_code
        raise RuntimeError(f"Semantic Scholar author search failed (status {status})")
    surname = parts[-1]
    out = []
    for a in response.json().get("data", []):
        if a.get("authorId") and surname in _name_tokens(a.get("name")):
            out.append(a["authorId"])
    return out


def fetch_author_papers(author_id: str) -> list[dict]:
    """
    Retrieve every page of papers currently available for this Semantic Scholar author.
    No application-level maximum-paper count is imposed.

    Raise on an incomplete/failed page rather than silently treating partial data
    as a complete publication list.
    """
    publications = []
    seen_paper_ids = set()
    offset = 0
    visited_offsets = set()
    page_size = 100

    while True:
        if offset in visited_offsets:
            raise RuntimeError(f"Repeated Semantic Scholar page offset {offset}; pagination stopped")
        visited_offsets.add(offset)

        response = _get(
            f"{_BASE}/author/{author_id}/papers",
            {
                "fields": "paperId,title,abstract,year,authors",
                "limit": page_size,
                "offset": offset,
            },
            max_retries=5,
        )
        if response is None:
            raise RuntimeError(f"No response from Semantic Scholar at offset {offset}")
        response.raise_for_status()

        body = response.json()
        batch = body.get("data")
        if not isinstance(batch, list):
            raise RuntimeError(f"Malformed Semantic Scholar page at offset {offset}")

        for p in batch:
            pid = p.get("paperId")
            if pid and pid in seen_paper_ids:
                continue
            if pid:
                seen_paper_ids.add(pid)
            publications.append({
                "paper_id": pid,
                "title": p.get("title"),
                "year": p.get("year"),
                "abstract": p.get("abstract") or "",
                "coauthors": [
                    {"name": a.get("name"), "authorId": a.get("authorId")}
                    for a in (p.get("authors") or [])
                    if a.get("authorId") and str(a.get("authorId")) != str(author_id)
                ],
            })

        next_offset = body.get("next")
        if next_offset is None:
            break
        next_offset = int(next_offset)
        if next_offset <= offset:
            raise RuntimeError(f"Invalid Semantic Scholar next offset: {next_offset}")
        offset = next_offset

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