"""
Conflict-of-interest (COI) detection.

Checks whether a candidate reviewer shares a co-author with the
confidential paper's declared authors -- a standard COI signal used
by real conference review systems (e.g. OpenReview).

This only compares author ID strings, never paper content, so it's
safe to run using the confidential paper's author list without
exposing anything else about the paper.
"""


def parse_coauthor_ids(coauthor_id_string: str) -> set[str]:
    """
    Parses the comma-separated co-author ID string stored in ChromaDB
    metadata back into a set, for comparison.
    """
    if not coauthor_id_string:
        return set()
    return {cid.strip() for cid in coauthor_id_string.split(",") if cid.strip()}


def has_conflict(paper_author_ids: set[str], reviewer_coauthor_ids: set[str]) -> bool:
    """
    Returns True if there's any overlap between the confidential paper's
    author IDs and a candidate reviewer's known co-author IDs.

    Example:
        >>> has_conflict({"123", "456"}, {"456", "789"})
        True
    """
    if not paper_author_ids or not reviewer_coauthor_ids:
        return False
    return bool(paper_author_ids & reviewer_coauthor_ids)