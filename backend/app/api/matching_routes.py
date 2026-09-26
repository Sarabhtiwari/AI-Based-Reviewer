"""
FastAPI routes for confidential paper -> reviewer matching.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.embeddings.specter2_local import embed_text
from app.nlp.conflict_check import parse_coauthor_ids, has_conflict
from app.connectors.google_scholars import resolve_author_ids_by_names
from app.vectorstore.chroma_client import find_matching_professors, get_professor_coauthor_ids
router = APIRouter(prefix="/match", tags=["matching"])


class MatchRequest(BaseModel):
    title: str = Field(..., description="Title of the confidential paper")
    abstract: str = Field("", description="Abstract of the confidential paper (optional but recommended)")
    top_k: int = Field(5, ge=1, le=50, description="Number of top reviewer matches to return")
    author_names: list[str] = Field(
        default_factory=list,
        description="Names of the confidential paper's own authors, used for conflict-of-interest checking"
    )


class MatchResult(BaseModel):
    professor_name: str
    scholar_id: str
    matched_paper_title: str
    similarity_score: float
    conflict_flag: bool


class MatchResponse(BaseModel):
    matches: list[MatchResult]


@router.post("/reviewers", response_model=MatchResponse)
def match_reviewers(request: MatchRequest):
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

    paper_author_ids = set(resolve_author_ids_by_names(request.author_names))

    results = []
    for m in raw_matches:
        m.pop("coauthor_ids", None)  # no longer used per-match
        reviewer_coauthor_ids = get_professor_coauthor_ids(m["scholar_id"])
        conflict = has_conflict(paper_author_ids, reviewer_coauthor_ids)
        results.append(MatchResult(**m, conflict_flag=conflict))
    return MatchResponse(matches=results)