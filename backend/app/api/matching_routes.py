"""
FastAPI routes for confidential paper -> reviewer matching.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.embeddings.specter2_local import embed_text
from app.nlp.conflict_check import check_conflict
from app.connectors.semantic_scholar import resolve_authors
from app.vectorstore.chroma_client import find_matching_professors, get_professor_coauthor_ids

router = APIRouter(prefix="/match", tags=["matching"])


class MatchRequest(BaseModel):
    title: str = Field(..., description="Title of the confidential paper")
    abstract: str = Field("", description="Abstract (optional but recommended)")
    top_k: int = Field(5, ge=1, le=50, description="Number of reviewers to return")
    author_names: list[str] = Field(
        default_factory=list,
        description="Names of the confidential paper's authors, for conflict checking",
    )


class MatchResult(BaseModel):
    professor_name: str
    scholar_id: str
    similarity_score: float
    matched_papers: list[str]
    conflict_status: str            # "clear" | "conflict" | "unverified"
    conflict_reasons: list[str]


class AuthorResolution(BaseModel):
    name: str
    authorId: str | None


class MatchResponse(BaseModel):
    matches: list[MatchResult]
    author_resolution: list[AuthorResolution]


@router.post("/reviewers", response_model=MatchResponse)
def match_reviewers(request: MatchRequest):
    try:
        query_vector = embed_text(request.title, request.abstract)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Fetch extra papers, then group, so one professor cannot fill every slot
    raw = find_matching_professors(query_vector, top_k=min(request.top_k * 10, 200))
    if not raw:
        raise HTTPException(
            status_code=404,
            detail="No professors indexed yet. Index at least one professor's papers first.",
        )

    grouped: dict[str, dict] = {}
    for m in raw:  # raw is already ordered best-first
        g = grouped.setdefault(m["scholar_id"], {
            "professor_name": m["professor_name"],
            "scholar_id": m["scholar_id"],
            "similarity_score": m["similarity_score"],  # best paper's score
            "matched_papers": [],
            "semantic_scholar_author_id": m.get("semantic_scholar_author_id"),
        })
        if len(g["matched_papers"]) < 3:
            g["matched_papers"].append(m["matched_paper_title"])

    top = sorted(grouped.values(), key=lambda g: g["similarity_score"], reverse=True)[:request.top_k]

    paper_authors = resolve_authors(request.author_names)

    results = []
    for g in top:
        verdict = check_conflict(
            paper_authors,
            set(get_professor_coauthor_ids(g["scholar_id"])),
            reviewer_author_id=g["semantic_scholar_author_id"],
        )
        results.append(MatchResult(
            professor_name=g["professor_name"],
            scholar_id=g["scholar_id"],
            similarity_score=g["similarity_score"],
            matched_papers=g["matched_papers"],
            conflict_status=verdict["status"],
            conflict_reasons=verdict["reasons"],
        ))

    return MatchResponse(
        matches=results,
        author_resolution=[AuthorResolution(**a) for a in paper_authors],
    )