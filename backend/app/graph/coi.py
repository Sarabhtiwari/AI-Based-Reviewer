"""
Conflict-of-interest check against the Neo4j graph.
Everything matches on Semantic Scholar IDs, never on names.
Statuses: conflict | unverified | clear
"""

from app.graph.client import get_driver

_SELF = """
MATCH (r:Author {s2_id: $reviewer})
WHERE r.s2_id IN $authors
RETURN r.name AS name
"""

_COAUTHOR = """
MATCH (r:Author {s2_id: $reviewer})-[:AUTHORED]->(p:Paper)<-[:AUTHORED]-(a:Author)
WHERE a.s2_id IN $authors AND a.s2_id <> $reviewer
RETURN a.name AS author, p.title AS title, p.year AS year
ORDER BY p.year DESC
"""

_EXISTS = "MATCH (r:Author {s2_id: $reviewer}) RETURN count(r) AS n"


def check_conflicts(reviewer_s2_id: str, paper_authors: list[dict]) -> dict:
    """
    paper_authors = [{"name": str, "authorId": str | None}, ...]
    Returns {"status", "reasons", "evidence"}.
    """
    resolved = [a["authorId"] for a in paper_authors if a.get("authorId")]
    unresolved = [a["name"] for a in paper_authors if not a.get("authorId")]

    if not reviewer_s2_id:
        return {"status": "unverified",
                "reasons": ["Reviewer has no Semantic Scholar ID stored; re-index them"],
                "evidence": []}

    with get_driver().session() as s:
        if resolved:
            me = s.run(_SELF, reviewer=reviewer_s2_id, authors=resolved).data()
            if me:
                return {"status": "conflict",
                        "reasons": ["Reviewer is listed as an author of this paper"],
                        "evidence": []}

            hits = s.run(_COAUTHOR, reviewer=reviewer_s2_id, authors=resolved).data()
            if hits:
                names = sorted({h["author"] for h in hits})
                return {"status": "conflict",
                        "reasons": [f"Has co-authored with paper author(s): {', '.join(names)}"],
                        "evidence": [{"author": h["author"], "paper": h["title"], "year": h["year"]}
                                     for h in hits]}

        in_graph = s.run(_EXISTS, reviewer=reviewer_s2_id).single()["n"]

    reasons = []
    if not paper_authors:
        reasons.append("No paper authors were provided")
    if unresolved:
        reasons.append("Could not find on Semantic Scholar: " + ", ".join(unresolved))
    if not in_graph:
        reasons.append("Reviewer is not in the graph; re-index them")

    if reasons:
        return {"status": "unverified", "reasons": reasons, "evidence": []}
    return {"status": "clear", "reasons": [], "evidence": []}