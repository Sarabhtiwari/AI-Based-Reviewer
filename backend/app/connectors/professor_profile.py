"""
Glue layer: turns a professor identifier (Google Scholar ID or ORCID) into a full profile.
Both paths end the same way: find the Semantic Scholar author ID, then fetch their papers.
The output shape is identical, so routes, embeddings and ChromaDB never change.
"""

import re
from app.connectors import google_scholar, orcid, semantic_scholar

_ORCID_PATTERN = re.compile(r"\d{4}-\d{4}-\d{4}-\d{3}[\dXx]")


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

    return {
        "name": name,
        "scholar_id": identifier,  # holds whichever ID was given
        "semantic_scholar_author_id": author_id,
        "publications": semantic_scholar.fetch_author_papers(author_id),
    }