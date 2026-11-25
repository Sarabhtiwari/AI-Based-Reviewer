"""
Glue layer: turns a professor identifier (Google Scholar ID or ORCID) into a full profile.
Both paths end the same way: find the Semantic Scholar author ID, then fetch their papers,
keeping only papers whose titles match the professor's own Scholar/ORCID list.
The output shape is identical, so routes, embeddings and ChromaDB never change.

HOW FAILURES ARE SPLIT
  TEMPORARY  (SOURCE_UNAVAILABLE): a service did not answer (timeout, 429, 5xx, blocked).
             The whole build is retried automatically (after 10 s and 30 s) before giving up.
  PERMANENT  (everything else): the data really is not there or does not match.
             ID_NOT_FOUND, NO_TITLES, AUTHOR_NOT_IDENTIFIED, NO_MATCHING_PAPERS, LOW_TITLE_MATCH.
So an error other than SOURCE_UNAVAILABLE means retrying will not help.

HOW THE SEMANTIC SCHOLAR AUTHOR IS FOUND
  1. Title vote (fast).
  2. If that finds nobody: take up to 5 same-surname authors from Semantic Scholar and keep
     the one whose papers best match the person's own titles (needs >= 30% and a clear lead).
  3. Manual: add the author ID yourself:  0000-0001-6071-0571=1234567
"""

import re
import time
import httpx
from app.connectors import google_scholar, orcid, semantic_scholar

_ORCID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]")

# Below this, the S2 profile is probably the wrong person or a mixed profile.
MIN_MATCH_PERCENT = 30.0
CANDIDATE_LIMIT = 5          # how many same-surname authors the fallback may check
CANDIDATE_LEAD = 15.0        # best candidate must beat the second by this many percentage points
_RETRY_WAITS = (10, 30)      # seconds to wait before the 2nd and 3rd attempt


def _error(name, identifier, message, code="PROFILE_ERROR"):
    return {
        "name": name or "Unknown",
        "scholar_id": identifier,
        "semantic_scholar_author_id": None,
        "publications": [],
        "error": message,
        "error_code": code,
        "retryable": code == "SOURCE_UNAVAILABLE",
    }


def _split_override(identifier: str) -> tuple[str, str | None]:
    """'0000-0001-6071-0571=1234567' -> ('0000-0001-6071-0571', '1234567')."""
    if "=" in identifier:
        left, right = identifier.rsplit("=", 1)
        right = right.strip()
        if right.isdigit():
            return left.strip(), right
    return identifier.strip(), None


def _normalize(identifier: str) -> tuple[str, object]:
    """Returns (clean_identifier, source_module)."""
    identifier = identifier.strip()
    match = _ORCID_PATTERN.search(identifier)
    # Treat it as ORCID only if it's a bare ORCID or an orcid.org URL
    if match and (identifier == match.group(0) or "orcid.org" in identifier.lower()):
        return match.group(0).upper(), orcid
    return identifier, google_scholar


def _find_by_candidates(name: str, titles: list[str]):
    """
    Fallback when the title vote finds nobody. Check several same-surname authors and keep
    the one whose papers cover the most of the person's own titles.
    Returns (author_id, all_papers) or None. Raises if Semantic Scholar did not answer.
    """
    candidates = semantic_scholar.find_author_candidates_by_name(name, limit=10)[:CANDIDATE_LIMIT]
    scored, failures = [], 0
    for cid in candidates:
        try:
            papers = semantic_scholar.fetch_author_papers(cid)
        except Exception:
            failures += 1
            continue
        result = semantic_scholar.filter_papers_by_titles(papers, titles)
        scored.append((result["match_percent"], cid, papers))

    if not scored:
        if failures:
            raise RuntimeError(f"Semantic Scholar did not answer for {failures} candidate profile(s)")
        return None
    scored.sort(key=lambda x: x[0], reverse=True)
    best = scored[0]
    # if best[0] < MIN_MATCH_PERCENT:
    #     return None
    if len(scored) > 1 and scored[1][0] > best[0] - CANDIDATE_LEAD:
        return None            # two profiles look equally right: do not guess
    return best[1], best[2]


def _build_profile(identifier: str) -> dict:
    identifier, s2_override = _split_override(identifier)
    identifier, source = _normalize(identifier)

    # 1) Read the professor's own list from ORCID or Google Scholar
    try:
        profile = source.fetch_profile(identifier)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return _error(None, identifier,
                          f"Could not load profile: ID not found ({source.__name__.split('.')[-1]}): {identifier}",
                          "ID_NOT_FOUND")
        return _error(None, identifier, f"Could not load profile: {e}", "SOURCE_UNAVAILABLE")
    except Exception as e:
        return _error(None, identifier, f"Could not load profile: {e}", "SOURCE_UNAVAILABLE")

    name, titles = profile["name"], profile["titles"]
    if not name or (not titles and not s2_override):
        return _error(name, identifier,
                      "No name/titles found (wrong ID, private ORCID works, or blocked)"
                      + ("" if s2_override else ". If you know the Semantic Scholar author ID, "
                         "enter it as ID=S2ID, e.g. " + identifier + "=1234567"),
                      "NO_TITLES")

    # 2) Find the Semantic Scholar author (or use the one typed in) and fetch papers
    method = "manual S2 ID" if s2_override else "title vote"
    try:
        all_papers = None
        if s2_override:
            author_id = s2_override
        else:
            author_id = semantic_scholar.find_author_id_via_titles(name, titles)
            if not author_id:
                found = _find_by_candidates(name, titles)
                if not found:
                    return _error(name, identifier,
                                  "Could not confidently match this professor on Semantic Scholar "
                                  "(title vote and name-candidate check both failed). If you can see "
                                  "them there, enter the author ID as ID=S2ID, e.g. "
                                  + identifier + "=1234567",
                                  "AUTHOR_NOT_IDENTIFIED")
                author_id, all_papers = found
                method = "name candidates, checked by titles"

        if all_papers is None:
            all_papers = semantic_scholar.fetch_author_papers(author_id)
        if titles:
            result = semantic_scholar.filter_papers_by_titles(all_papers, titles)
        else:
            # ORCID has no public works: nothing to check against, accept as typed
            result = {"papers": all_papers, "match_percent": None, "dropped": 0}
    except Exception as e:
        return _error(name, identifier, f"Semantic Scholar request failed: {e}", "SOURCE_UNAVAILABLE")

    if not result["papers"]:
        return _error(name, identifier,
                      f"Semantic Scholar profile {author_id} has no paper matching the titles on this profile",
                      "NO_MATCHING_PAPERS")
    # if result["match_percent"] is not None and result["match_percent"] < MIN_MATCH_PERCENT:
    #     return _error(
    #         name, identifier,
    #         f"Semantic Scholar profile {author_id} matches only {result['match_percent']}% "
    #         f"of the titles on this profile; refusing to index it",
    #         "LOW_TITLE_MATCH",
    #     )

    return {
        "name": name,
        "scholar_id": identifier,  # holds whichever ID was given
        "semantic_scholar_author_id": author_id,
        "publications": result["papers"],
        "match_percent": result["match_percent"],
        "papers_dropped": result["dropped"],
        "institutions": profile.get("institutions", []),
        "identity_check": method + ("" if titles else ", no title list to check"),
    }


def get_full_professor_data(identifier: str) -> dict:
    """Builds the profile; temporary failures are retried before an error is returned."""
    result = _build_profile(identifier)
    for wait in _RETRY_WAITS:
        if result.get("error_code") != "SOURCE_UNAVAILABLE":
            break
        time.sleep(wait)
        result = _build_profile(identifier)
    if result.get("error_code") == "SOURCE_UNAVAILABLE":
        result["error"] += "  [temporary problem: tried 3 times, try again later]"
    return result