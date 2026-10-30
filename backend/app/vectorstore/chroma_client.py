"""
Local vector store for professor paper embeddings, using ChromaDB.

Stores each PUBLIC paper's embedding tagged with its professor. Vector IDs
are built from the Semantic Scholar author ID + paper ID, so re-indexing
replaces old vectors instead of leaving stale ones behind.

Relationship data (co-authors, conflicts) lives in Neo4j, not here.
"""

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from app.config.settings import settings

_client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))

_collection = _client.get_or_create_collection(
    name="professor_papers",
    metadata={"hnsw:space": "cosine"},
)


def delete_professor_papers(scholar_id: str, s2_author_id: str | None = None) -> None:
    """Removes every stored vector for this professor (by either identifier)."""
    _collection.delete(where={"scholar_id": scholar_id})
    if s2_author_id:
        _collection.delete(where={"s2_author_id": s2_author_id})


def add_professor_papers(
    professor_name: str,
    scholar_id: str,
    papers: list[dict],
    s2_author_id: str | None = None,
) -> int:
    """
    Replaces this professor's vectors with the given papers.
    Each paper must already have an 'embedding' key. Returns how many were stored.
    """
    delete_professor_papers(scholar_id, s2_author_id)

    ids, embeddings, metadatas, documents = [], [], [], []
    key = s2_author_id or scholar_id

    for i, paper in enumerate(papers):
        if "embedding" not in paper:
            continue
        ids.append(f"{key}_{paper.get('paper_id') or i}")
        embeddings.append(paper["embedding"])
        metadatas.append({
            "professor_name": professor_name,
            "scholar_id": scholar_id,
            "s2_author_id": s2_author_id or "",
            "title": paper.get("title") or "",
            "year": str(paper.get("year") or ""),
        })
        documents.append(paper.get("title") or "")

    if not ids:
        return 0

    _collection.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
    return len(ids)


def find_matching_professors(query_embedding: list[float], top_k: int = 10) -> list[dict]:
    """Top_k most similar stored papers across all professors, best first (one entry per paper)."""
    results = _collection.query(query_embeddings=[query_embedding], n_results=top_k)

    matches = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        matches.append({
            "professor_name": meta["professor_name"],
            "scholar_id": meta["scholar_id"],
            "semantic_scholar_author_id": meta.get("s2_author_id") or None,
            "matched_paper_title": meta["title"],
            "similarity_score": 1 - results["distances"][0][i],
        })
    return matches