"""
FastAPI routes for professor expertise discovery and indexing.
"""

import time
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connectors.google_scholars import get_full_professor_data
from app.nlp.keyword_extraction import extract_keywords_for_papers
from app.nlp.expertise_profile import build_expertise_profile
from app.embeddings.paper_embedder import embed_papers_for_professor
from app.vectorstore.chroma_client import add_professor_papers

router = APIRouter(prefix="/professor", tags=["professor"])


@router.get("/{scholar_id}/expertise")
def get_professor_expertise(scholar_id: str):
    """
    Given a Google Scholar ID, fetches the professor's full profile
    (via Semantic Scholar, disambiguated by paper-title matching) and
    returns an aggregated expertise profile.
    """
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
    """
    Fetches a professor's public papers, embeds them, and stores the
    vectors in ChromaDB so they become searchable via /match/reviewers.
    """
    author_data = get_full_professor_data(scholar_id)

    if author_data.get("error"):
        raise HTTPException(status_code=404, detail=author_data["error"])

    papers = author_data.get("publications", [])
    if not papers:
        raise HTTPException(status_code=404, detail="No publications found for this scholar ID")

    papers = embed_papers_for_professor(papers)
    add_professor_papers(author_data["name"], scholar_id, papers)

    return {
        "professor_name": author_data["name"],
        "scholar_id": scholar_id,
        "semantic_scholar_author_id": author_data.get("semantic_scholar_author_id"),
        "papers_indexed": len(papers),
    }


class BatchIndexRequest(BaseModel):
    scholar_ids: list[str]


class BatchIndexResult(BaseModel):
    scholar_id: str
    status: str
    professor_name: str | None = None
    papers_indexed: int | None = None
    error: str | None = None


class BatchIndexResponse(BaseModel):
    results: list[BatchIndexResult]


@router.post("/index-batch", response_model=BatchIndexResponse)
def index_professors_batch(request: BatchIndexRequest):
    """
    Indexes multiple professors given a list of Google Scholar IDs.
    """
    results = []

    for scholar_id in request.scholar_ids:
        try:
            author_data = get_full_professor_data(scholar_id)

            if author_data.get("error"):
                results.append(BatchIndexResult(
                    scholar_id=scholar_id,
                    status="failed",
                    error=author_data["error"],
                ))
                continue

            papers = author_data.get("publications", [])
            if not papers:
                results.append(BatchIndexResult(
                    scholar_id=scholar_id,
                    status="failed",
                    error="No publications found",
                ))
                continue

            papers = embed_papers_for_professor(papers)
            add_professor_papers(author_data["name"], scholar_id, papers)

            results.append(BatchIndexResult(
                scholar_id=scholar_id,
                status="success",
                professor_name=author_data["name"],
                papers_indexed=len(papers),
            ))

        except Exception as e:
            results.append(BatchIndexResult(
                scholar_id=scholar_id,
                status="failed",
                error=str(e),
            ))

        time.sleep(1)  # pacing between professors -- Semantic Scholar rate limit

    return BatchIndexResponse(results=results)  