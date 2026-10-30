"""
FastAPI routes for professor expertise discovery and indexing.
"""

import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors.professor_profile import get_full_professor_data
from app.nlp.keyword_extraction import extract_keywords_for_papers
from app.nlp.expertise_profile import build_expertise_profile
from app.embeddings.paper_embedder import embed_papers_for_professor
from app.vectorstore.chroma_client import add_professor_papers, _collection
from app.graph.ingest import ingest_professor

router = APIRouter(prefix="/professor", tags=["professor"])


def _index_one(author_data: dict) -> dict:
    """Stores one professor in Chroma (vectors) and Neo4j (relationships)."""
    papers = embed_papers_for_professor(author_data["publications"])
    stored = add_professor_papers(
        author_data["name"],
        author_data["scholar_id"],
        papers,
        s2_author_id=author_data["semantic_scholar_author_id"],
    )

    # The graph is separate: if Neo4j is down, vector indexing still counts.
    try:
        graph = ingest_professor(author_data)
        graph_error = None
    except Exception as e:
        graph, graph_error = None, str(e)

    return {
        "professor_name": author_data["name"],
        "scholar_id": author_data["scholar_id"],
        "semantic_scholar_author_id": author_data["semantic_scholar_author_id"],
        "match_percent": author_data.get("match_percent"),
        "papers_indexed": stored,
        "graph": graph,
        "graph_error": graph_error,
    }


@router.get("/{scholar_id}/expertise")
def get_professor_expertise(scholar_id: str):
    author_data = get_full_professor_data(scholar_id)

    if author_data.get("error"):
        raise HTTPException(status_code=404, detail=author_data["error"])

    papers = author_data.get("publications", [])
    if not papers:
        raise HTTPException(status_code=404, detail="No publications found for this scholar ID")

    papers = extract_keywords_for_papers(papers)
    profile = build_expertise_profile(author_data.get("name", "Unknown"), papers)

    return {
        "profile": profile,
        "semantic_scholar_author_id": author_data.get("semantic_scholar_author_id"),
        "papers": papers,
    }


@router.post("/{scholar_id}/index")
def index_professor(scholar_id: str):
    """Indexes one professor (Google Scholar ID or ORCID) into Chroma and Neo4j."""
    author_data = get_full_professor_data(scholar_id)

    if author_data.get("error"):
        raise HTTPException(status_code=404, detail=author_data["error"])
    if not author_data.get("publications"):
        raise HTTPException(status_code=404, detail="No publications found for this ID")

    return _index_one(author_data)


class BatchIndexRequest(BaseModel):
    scholar_ids: list[str]


class BatchIndexResult(BaseModel):
    scholar_id: str
    status: str
    professor_name: str | None = None
    papers_indexed: int | None = None
    graph_papers: int | None = None
    graph_coauthors: int | None = None
    graph_error: str | None = None
    error: str | None = None


class BatchIndexResponse(BaseModel):
    results: list[BatchIndexResult]


@router.post("/index-batch", response_model=BatchIndexResponse)
def index_professors_batch(request: BatchIndexRequest):
    """Indexes several professors. One failure doesn't stop the rest."""
    results = []

    for identifier in request.scholar_ids:
        try:
            author_data = get_full_professor_data(identifier)

            if author_data.get("error"):
                results.append(BatchIndexResult(scholar_id=identifier, status="failed",
                                                error=author_data["error"]))
                continue
            if not author_data.get("publications"):
                results.append(BatchIndexResult(scholar_id=identifier, status="failed",
                                                error="No publications found"))
                continue

            out = _index_one(author_data)
            graph = out["graph"] or {}
            results.append(BatchIndexResult(
                scholar_id=identifier,
                status="success",
                professor_name=out["professor_name"],
                papers_indexed=out["papers_indexed"],
                graph_papers=graph.get("papers"),
                graph_coauthors=graph.get("coauthors"),
                graph_error=out["graph_error"],
            ))
        except Exception as e:
            results.append(BatchIndexResult(scholar_id=identifier, status="failed", error=str(e)))

        time.sleep(1)

    return BatchIndexResponse(results=results)


@router.get("/indexed")
def list_indexed_professors():
    """Professors currently stored in Chroma, for a quick sanity check."""
    all_data = _collection.get(include=["metadatas"])

    professors: dict[str, dict] = {}
    for meta in all_data["metadatas"]:
        sid = meta.get("scholar_id", "unknown")
        entry = professors.setdefault(sid, {
            "scholar_id": sid,
            "professor_name": meta.get("professor_name", "Unknown"),
            "semantic_scholar_author_id": meta.get("s2_author_id") or None,
            "paper_count": 0,
        })
        entry["paper_count"] += 1

    return {
        "total_professors": len(professors),
        "total_papers_indexed": len(all_data["metadatas"]),
        "professors": list(professors.values()),
    }