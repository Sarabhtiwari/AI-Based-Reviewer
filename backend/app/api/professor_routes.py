"""
FastAPI routes for professor expertise discovery.

Exposes the pipeline we've built (Google Scholar fetch -> abstract
enrichment -> keyword extraction -> aggregation) as a real HTTP endpoint,
so it can be called from a frontend or tested via Swagger docs instead
of one-off scripts.
"""
import time
from fastapi import APIRouter, HTTPException

from app.connectors.google_scholars import get_author_by_scholar_id
from app.connectors.semantic_scholars import enrich_papers_with_abstracts
from app.nlp.keyword_extraction import extract_keywords_for_papers
from app.nlp.expertise_profile import build_expertise_profile
from app.embeddings.paper_embedder import embed_papers_for_professor
from app.vectorstore.chroma_client import add_professor_papers
from pydantic import BaseModel  

router = APIRouter(prefix="/professor", tags=["professor"])

class BatchIndexRequest(BaseModel):
    scholar_ids: list[str]


class BatchIndexResult(BaseModel):
    scholar_id: str
    status: str  # "success" or "failed"
    professor_name: str | None = None
    papers_indexed: int | None = None
    error: str | None = None


class BatchIndexResponse(BaseModel):
    results: list[BatchIndexResult]



@router.get("/{scholar_id}/expertise")
def get_professor_expertise(scholar_id: str):
    """
    Given a Google Scholar ID, runs the full public-data pipeline and
    returns an aggregated expertise profile for that professor.

    Example: GET /professor/RwCZSW4AAAAJ/expertise
    """
    try:
        author_data = get_author_by_scholar_id(scholar_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Google Scholar profile: {e}")

    papers = author_data.get("publications", [])
    if not papers:
        raise HTTPException(status_code=404, detail="No publications found for this scholar ID")

    papers = enrich_papers_with_abstracts(papers)
    papers = extract_keywords_for_papers(papers)

    profile = build_expertise_profile(author_data.get("name", "Unknown"), papers)

    # Return the profile plus the raw per-paper breakdown, useful for
    # debugging/demo -- the frontend can choose to show only the summary.
    return {
        "profile": profile,
        "papers": papers,
    }

@router.post("/{scholar_id}/index")
def index_professor(scholar_id: str):
    """
    Fetches a professor's public papers, embeds them, and stores the
    vectors in ChromaDB so they become searchable via /match/reviewers.
    """
    try:
        author_data = get_author_by_scholar_id(scholar_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to fetch Google Scholar profile: {e}")

    papers = author_data.get("publications", [])
    if not papers:
        raise HTTPException(status_code=404, detail="No publications found for this scholar ID")

    papers = embed_papers_for_professor(papers)
    add_professor_papers(author_data["name"], scholar_id, papers)

    return {
        "professor_name": author_data["name"],
        "scholar_id": scholar_id,
        "papers_indexed": len(papers),
    }

@router.post("/index-batch", response_model=BatchIndexResponse)
def index_professors_batch(request: BatchIndexRequest):
    """
    Indexes multiple professors given a list of Google Scholar IDs --
    e.g. the reviewer list your teacher provides. Processes one at a
    time (not parallel) to stay within Tavily/Groq rate limits, and
    continues even if individual professors fail (bad ID, no papers,
    API hiccup), reporting per-professor status rather than aborting
    the whole batch on one failure.
    """
    results = []

    for scholar_id in request.scholar_ids:
        try:
            author_data = get_author_by_scholar_id(scholar_id)
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

        time.sleep(2)  # pacing between professors -- avoid hammering Tavily/Groq

    return BatchIndexResponse(results=results)