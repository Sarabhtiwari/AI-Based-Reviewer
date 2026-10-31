"""
Conflict-of-interest check against the Neo4j graph. Matches on IDs, never on author names.
Rules: reviewer is an author | co-authored with an author | same institution.
Statuses: conflict | unverified | clear
"""

from app.graph.client import get_driver
from app.graph.institutions import compare, recent

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

_REVIEWER_INSTITUTIONS = """
MATCH (r:Author {s2_id: $reviewer})-[a:AFFILIATED_WITH]->(i:Institution)
RETURN i.name AS name, i.ror AS ror, a.end_year AS end_year
"""


def check_conflicts(reviewer_s2_id: str, paper_authors: list[dict],
                    paper_institutions: list[dict] | None = None) -> dict:
    """
    paper_authors      = [{"name": str, "authorId": str | None}, ...]
    paper_institutions = [{"name": str, "ror": str | None, "end_year": None}, ...]
    Returns {"status", "reasons", "evidence"}.
    """
    paper_institutions = paper_institutions or []
    resolved = [a["authorId"] for a in paper_authors if a.get("authorId")]
    unresolved = [a["name"] for a in paper_authors if not a.get("authorId")]

    if not reviewer_s2_id:
        return {"status": "unverified",
                "reasons": ["Reviewer has no Semantic Scholar ID stored; re-index them"],
                "evidence": []}

    conflict_reasons, evidence = [], []

    with get_driver().session() as s:
        if resolved:
            if s.run(_SELF, reviewer=reviewer_s2_id, authors=resolved).data():
                return {"status": "conflict",
                        "reasons": ["Reviewer is listed as an author of this paper"],
                        "evidence": []}
            hits = s.run(_COAUTHOR, reviewer=reviewer_s2_id, authors=resolved).data()
            if hits:
                names = sorted({h["author"] for h in hits})
                conflict_reasons.append(f"Has co-authored with paper author(s): {', '.join(names)}")
                evidence = [{"author": h["author"], "paper": h["title"], "year": h["year"]} for h in hits]

        in_graph = s.run(_EXISTS, reviewer=reviewer_s2_id).single()["n"]
        reviewer_insts = recent(s.run(_REVIEWER_INSTITUTIONS, reviewer=reviewer_s2_id).data())

    possible = []
    for pi in paper_institutions:
        for ri in reviewer_insts:
            verdict = compare(pi, ri)
            if verdict == "same":
                conflict_reasons.append(f"Same institution: {pi['name']} (reviewer: {ri['name']})")
            elif verdict == "possible":
                possible.append(f"Possible same institution, check manually: {pi['name']} / {ri['name']}")

    if conflict_reasons:
        return {"status": "conflict", "reasons": list(dict.fromkeys(conflict_reasons)), "evidence": evidence}

    reasons = list(dict.fromkeys(possible))
    if not paper_authors:
        reasons.append("No paper authors were provided")
    if unresolved:
        reasons.append("Could not find on Semantic Scholar: " + ", ".join(unresolved))
    if not in_graph:
        reasons.append("Reviewer is not in the graph; re-index them")
    if not paper_institutions:
        reasons.append("No author institutions provided; same-institution check not done")
    if not reviewer_insts:
        reasons.append("No current institution stored for this reviewer; same-institution check not done")

    if reasons:
        return {"status": "unverified", "reasons": reasons, "evidence": []}
    return {"status": "clear", "reasons": [], "evidence": []}