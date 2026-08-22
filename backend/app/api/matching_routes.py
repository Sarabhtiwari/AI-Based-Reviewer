"""
FastAPI routes for confidential paper -> reviewer matching.

Ties together: local confidential-paper embedding (SPECTER2, no network)
and ChromaDB similarity search against stored professor paper vectors.

NOTE: this endpoint does NOT store or index the confidential paper's
title/abstract anywhere except in local memory during the request --
only its vector is used to query ChromaDB, and nothing about the
confidential paper is persisted to disk or sent externally.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.embeddings.specter2_local import embed_text
from app.vectorstore.chroma_client import find_matching_professors

router = APIRouter(prefix="/match", tags=["matching"])


class MatchRequest(BaseModel):
    title: str = Field(..., description="Title of the confidential paper")
    abstract: str = Field("", description="Abstract of the confidential paper (optional but recommended)")
    top_k: int = Field(5, ge=1, le=50, description="Number of top reviewer matches to return")


class MatchResult(BaseModel):
    professor_name: str
    scholar_id: str
    matched_paper_title: str
    similarity_score: float


class MatchResponse(BaseModel):
    matches: list[MatchResult]


@router.post("/reviewers", response_model=MatchResponse)
def match_reviewers(request: MatchRequest):
    """
    Given a confidential paper's title (and optionally abstract), embeds
    it locally (never leaves the machine) and returns the top_k most
    similar professors based on their public paper vectors already
    stored in ChromaDB.

    Professors must already be indexed via the professor expertise
    endpoint (or the indexing step) before they can appear as matches here.
    """
    try:
        query_vector = embed_text(request.title, request.abstract)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw_matches = find_matching_professors(query_vector, top_k=request.top_k)

    if not raw_matches:
        raise HTTPException(
            status_code=404,
            detail="No professors indexed yet. Index at least one professor's papers first."
        )

    return MatchResponse(matches=[MatchResult(**m) for m in raw_matches])