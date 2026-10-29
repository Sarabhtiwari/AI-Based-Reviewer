"""
Writes a professor, their papers and all co-authors into Neo4j.
Everything is MERGEd on S2 IDs / paper IDs, so re-indexing never duplicates.
"""

import re
from app.graph.client import get_driver

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


def ingest_professor(data: dict) -> dict:
    """
    data = output of get_full_professor_data (no 'error').
    Returns counts of what was written (merged), for the API response.
    """
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

    with get_driver().session() as session:
        session.execute_write(
            lambda tx: tx.run(
                _CYPHER, s2_id=s2_id, name=data["name"], ids=ids, papers=papers
            ).consume()
        )

    return {
        "authors": 1 + len(coauthor_ids),
        "papers": len(papers),
        "coauthors": len(coauthor_ids),
    }