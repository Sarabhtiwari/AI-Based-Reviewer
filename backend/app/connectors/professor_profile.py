"""
Glue layer: turns a professor identifier into a full profile.
Every identifier type (Google Scholar now, ORCID later) ends the same way:
find the Semantic Scholar author ID, then fetch their papers.
The output shape is identical, so routes, embeddings and ChromaDB never change.
"""

from app.connectors import google_scholar, semantic_scholar


def _error(name, scholar_id, message):
    return {
        "name": name or "Unknown",
        "scholar_id": scholar_id,
        "semantic_scholar_author_id": None,
        "publications": [],
        "error": message,
    }


def get_full_professor_data(scholar_id: str) -> dict:
    try:
        profile = google_scholar.fetch_profile(scholar_id)
    except Exception as e:
        return _error(None, scholar_id, f"Could not load Google Scholar profile: {e}")

    name, titles = profile["name"], profile["titles"]
    if not name or not titles:
        return _error(name, scholar_id, "Google Scholar returned no name/titles (wrong ID or blocked)")

    author_id = semantic_scholar.find_author_id_via_titles(name, titles)
    if not author_id:
        return _error(name, scholar_id, "Could not confidently match this professor on Semantic Scholar")

    return {
        "name": name,
        "scholar_id": scholar_id,
        "semantic_scholar_author_id": author_id,
        "publications": semantic_scholar.fetch_author_papers(author_id),
    }


# Later:
# def get_full_professor_data_by_orcid(orcid: str) -> dict:
#     fetch name + works from ORCID -> same Semantic Scholar steps -> same return shape