"""
Read-only graph view for the frontend: a professor, their papers and co-authors.
"""

from fastapi import APIRouter, HTTPException
from app.graph.client import get_driver
from neo4j.exceptions import ServiceUnavailable

router = APIRouter(prefix="/graph", tags=["graph"])

_QUERY = """
MATCH (r:Author)
WHERE r.s2_id = $id OR r.orcid = $id OR r.scholar_id = $id
MATCH (r)-[:AUTHORED]->(p:Paper)
OPTIONAL MATCH (a:Author)-[:AUTHORED]->(p) WHERE a.s2_id <> r.s2_id
RETURN r.s2_id AS rid, r.name AS rname,
       p.paper_id AS pid, p.title AS title, p.year AS year,
       a.s2_id AS aid, a.name AS aname
"""


@router.get("/professor/{identifier}")
def professor_graph(identifier: str):
    """
    identifier = Semantic Scholar author ID, ORCID or Google Scholar ID.
    Returns nodes + edges, plus a collaborators summary (shared paper counts).
    """
    try:
        with get_driver().session() as s:
            rows = s.run(_QUERY, id=identifier).data()
    except ServiceUnavailable:
        raise HTTPException(status_code=503, detail="Graph database is unreachable. Check that Neo4j Aura is running.")

    if not rows:
        raise HTTPException(status_code=404, detail="Professor not found in the graph. Index them first.")

    nodes, edges, shared = {}, set(), {}
    for row in rows:
        rid = row["rid"]
        nodes[rid] = {"id": rid, "label": row["rname"], "type": "reviewer"}
        nodes[row["pid"]] = {"id": row["pid"], "label": row["title"], "type": "paper", "year": row["year"]}
        edges.add((rid, row["pid"]))

        if row["aid"]:
            nodes.setdefault(row["aid"], {"id": row["aid"], "label": row["aname"], "type": "coauthor"})
            edges.add((row["aid"], row["pid"]))
            shared[row["aid"]] = shared.get(row["aid"], 0) + 1

    collaborators = sorted(
        ({"s2_id": k, "name": nodes[k]["label"], "shared_papers": v} for k, v in shared.items()),
        key=lambda c: c["shared_papers"], reverse=True,
    )

    return {
        "nodes": list(nodes.values()),
        "edges": [{"source": a, "target": b, "type": "AUTHORED"} for a, b in edges],
        "collaborators": collaborators,
    }