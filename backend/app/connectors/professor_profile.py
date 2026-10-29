"""
Glue layer: turns a professor identifier (Google Scholar ID or ORCID) into a full profile.
Both paths end the same way: find the Semantic Scholar author ID, then fetch their papers,
keeping only papers whose titles match the professor's own Scholar/ORCID list.
The output shape is identical, so routes, embeddings and ChromaDB never change.
"""

import re
from app.connectors import google_scholar, orcid, semantic_scholar

_ORCID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]")

# Below this, the S2 profile is probably the wrong person or a mixed profile.
MIN_MATCH_PERCENT = 30.0


def _error(name, identifier, message):
    return {
        "name": name or "Unknown",
        "scholar_id": identifier,
        "semantic_scholar_author_id": None,
        "publications": [],
        "error": message,
    }


def _normalize(identifier: str) -> tuple[str, object]:
    """Returns (clean_identifier, source_module)."""
    identifier = identifier.strip()
    match = _ORCID_PATTERN.search(identifier)
    # Treat it as ORCID only if it's a bare ORCID or an orcid.org URL
    if match and (identifier == match.group(0) or "orcid.org" in identifier.lower()):
        return match.group(0).upper(), orcid
    return identifier, google_scholar


def get_full_professor_data(identifier: str) -> dict:
    identifier, source = _normalize(identifier)

    try:
        profile = source.fetch_profile(identifier)
    except Exception as e:
        return _error(None, identifier, f"Could not load profile: {e}")

    name, titles = profile["name"], profile["titles"]
    if not name or not titles:
        return _error(name, identifier, "No name/titles found (wrong ID, private ORCID works, or blocked)")

    author_id = semantic_scholar.find_author_id_via_titles(name, titles)
    if not author_id:
        return _error(name, identifier, "Could not confidently match this professor on Semantic Scholar")

    result = semantic_scholar.filter_papers_by_titles(
        semantic_scholar.fetch_author_papers(author_id), titles
    )
    if not result["papers"] or result["match_percent"] < MIN_MATCH_PERCENT:
        return _error(
            name, identifier,
            f"Semantic Scholar profile {author_id} matches only {result['match_percent']}% "
            f"of the titles on this profile; refusing to index it",
        )

    return {
        "name": name,
        "scholar_id": identifier,  # holds whichever ID was given
        "semantic_scholar_author_id": author_id,
        "publications": result["papers"],
        "match_percent": result["match_percent"],
        "papers_dropped": result["dropped"],
    }