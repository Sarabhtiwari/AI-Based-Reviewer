"""
Writes a professor, their papers, co-authors and institutions into Neo4j.
Everything is MERGEd on S2 IDs / paper IDs / institution keys, so re-indexing never duplicates.
"""

import re
from app.graph.client import get_driver
from app.graph.institutions import key as institution_key

_ORCID = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")

_CYPHER = """
MERGE (r:Author {s2_id: $s2_id})
SET r.name = $name, r.is_reviewer = true
SET r += $ids
WITH r
UNWIND $papers AS paper
MERGE (p:Paper {paper_id: paper.paper_id})
SET p.title = paper.title, p.year = paper.year
MERGE (r)-[:AUTHORED]->(p)
WITH p, paper
UNWIND paper.coauthors AS co
MERGE (a:Author {s2_id: co.s2_id})
ON CREATE SET a.name = co.name, a.is_reviewer = false
MERGE (a)-[:AUTHORED]->(p)
"""

# Old affiliations are replaced, so a re-index always reflects the latest ORCID data.
_INSTITUTIONS = """
MATCH (r:Author {s2_id: $s2_id})
OPTIONAL MATCH (r)-[old:AFFILIATED_WITH]->(:Institution)
DELETE old
WITH DISTINCT r
UNWIND $institutions AS inst
MERGE (i:Institution {key: inst.key})
SET i.name = inst.name, i.ror = inst.ror
MERGE (r)-[a:AFFILIATED_WITH]->(i)
SET a.end_year = inst.end_year
"""


def _write(tx, s2_id, name, ids, papers, institutions):
    tx.run(_CYPHER, s2_id=s2_id, name=name, ids=ids, papers=papers).consume()
    tx.run(_INSTITUTIONS, s2_id=s2_id, institutions=institutions).consume()


def _clean_institutions(raw: list[dict]) -> list[dict]:
    """One entry per institution; if listed twice, keep the most recent stint."""
    best: dict[str, dict] = {}
    for inst in raw or []:
        k = institution_key(inst.get("name"))
        if not k:
            continue
        rank = 9999 if inst.get("end_year") is None else inst["end_year"]
        if k not in best or rank > best[k]["_rank"]:
            best[k] = {"key": k, "name": inst["name"], "ror": inst.get("ror"),
                       "end_year": inst.get("end_year"), "_rank": rank}
    for v in best.values():
        v.pop("_rank")
    return list(best.values())


def ingest_professor(data: dict) -> dict:
    """data = output of get_full_professor_data (no 'error'). Returns counts written."""
    s2_id = data["semantic_scholar_author_id"]
    identifier = data["scholar_id"]
    ids = {"orcid": identifier} if _ORCID.match(identifier) else {"scholar_id": identifier}

    papers, coauthor_ids = [], set()
    for p in data["publications"]:
        if not p.get("paper_id"):
            continue
        coauthors = [
            {"s2_id": c["authorId"], "name": c.get("name")}
            for c in p.get("coauthors", [])
            if c.get("authorId") and c["authorId"] != s2_id
        ]
        coauthor_ids.update(c["s2_id"] for c in coauthors)
        papers.append({
            "paper_id": p["paper_id"],
            "title": p.get("title"),
            "year": p.get("year"),
            "coauthors": coauthors,
        })

    institutions = _clean_institutions(data.get("institutions", []))

    with get_driver().session() as session:
        session.execute_write(_write, s2_id, data["name"], ids, papers, institutions)

    return {
        "authors": 1 + len(coauthor_ids),
        "papers": len(papers),
        "coauthors": len(coauthor_ids),
        "institutions": len(institutions),
    }