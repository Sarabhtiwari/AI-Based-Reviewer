"""
FastAPI routes for confidential paper -> reviewer matching.

Similarity comes from ChromaDB; conflicts come from the Neo4j graph.
The confidential title/abstract is embedded locally and never leaves the machine.
Only author IDs, names, ORCIDs and institution names are looked up externally.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.embeddings.specter2_local import embed_text
from app.connectors import orcid as orcid_api
from app.connectors.semantic_scholar import resolve_authors
from app.vectorstore.chroma_client import find_matching_professors
from app.graph.coi import check_conflicts
from app.graph.institutions import recent

router = APIRouter(prefix="/match", tags=["matching"])


class MatchRequest(BaseModel):
    title: str = Field(..., description="Title of the confidential paper")
    abstract: str = Field("", description="Abstract (optional but recommended)")
    top_k: int = Field(5, ge=1, le=50, description="Number of reviewers to return")
    author_ids: list[str] = Field(default_factory=list,
        description="Semantic Scholar author IDs of the paper's authors (preferred, exact)")
    author_names: list[str] = Field(default_factory=list,
        description="Author names, fallback only; searched on Semantic Scholar")
    author_institutions: list[str] = Field(default_factory=list,
        description="Institutions of the paper's authors, e.g. 'IIT Bombay'")
    author_orcids: list[str] = Field(default_factory=list,
        description="ORCIDs of paper authors; their current employers are fetched automatically")


class MatchResult(BaseModel):
    professor_name: str
    scholar_id: str
    similarity_score: float
    matched_papers: list[str]
    conflict_status: str            # "clear" | "conflict" | "unverified"
    conflict_reasons: list[str]
    conflict_evidence: list[dict] = []


class AuthorResolution(BaseModel):
    name: str
    authorId: str | None


class MatchResponse(BaseModel):
    matches: list[MatchResult]
    author_resolution: list[AuthorResolution]
    author_institutions_used: list[dict] = []
    warnings: list[str] = []


@router.post("/reviewers", response_model=MatchResponse)
def match_reviewers(request: MatchRequest):
    try:
        query_vector = embed_text(request.title, request.abstract)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    raw = find_matching_professors(query_vector, top_k=min(request.top_k * 10, 200))
    if not raw:
        raise HTTPException(
            status_code=404,
            detail="No professors indexed yet. Index at least one professor's papers first.",
        )

    grouped: dict[str, dict] = {}
    for m in raw:  # already ordered best-first
        g = grouped.setdefault(m["scholar_id"], {
            "professor_name": m["professor_name"],
            "scholar_id": m["scholar_id"],
            "similarity_score": m["similarity_score"],
            "matched_papers": [],
            "semantic_scholar_author_id": m.get("semantic_scholar_author_id"),
        })
        if len(g["matched_papers"]) < 3:
            g["matched_papers"].append(m["matched_paper_title"])

    top = sorted(grouped.values(), key=lambda g: g["similarity_score"], reverse=True)[:request.top_k]

    # Authors: IDs given directly are exact; names are a fallback search
    paper_authors = [{"name": i, "authorId": i} for i in request.author_ids]
    paper_authors += resolve_authors(request.author_names)

    # Institutions: typed names count as current; ORCIDs are looked up
    warnings: list[str] = []
    paper_institutions = [{"name": n.strip(), "ror": None, "end_year": None}
                          for n in request.author_institutions if n and n.strip()]
    for o in request.author_orcids:
        o = o.strip()
        if not o:
            continue
        try:
            found = recent(orcid_api.fetch_institutions(o))
            if not found:
                warnings.append(f"ORCID {o}: no current institution is public")
            paper_institutions += found
        except Exception as e:
            warnings.append(f"ORCID {o}: could not load institutions ({e})")

    results = []
    for g in top:
        try:
            verdict = check_conflicts(g["semantic_scholar_author_id"], paper_authors, paper_institutions)
        except Exception as e:  # e.g. Neo4j down: report it, never claim "clear"
            verdict = {"status": "unverified", "reasons": [f"Conflict check failed: {e}"], "evidence": []}
        results.append(MatchResult(
            professor_name=g["professor_name"],
            scholar_id=g["scholar_id"],
            similarity_score=g["similarity_score"],
            matched_papers=g["matched_papers"],
            conflict_status=verdict["status"],
            conflict_reasons=verdict["reasons"],
            conflict_evidence=verdict["evidence"],
        ))

    return MatchResponse(
        matches=results,
        author_resolution=[AuthorResolution(**a) for a in paper_authors],
        author_institutions_used=paper_institutions,
        warnings=warnings,
    )