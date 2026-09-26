"""
Local vector store for professor paper embeddings, using ChromaDB.

Stores each PUBLIC paper's embedding (from paper_embedder.py) tagged
with which professor it belongs to. At query time, we embed the
confidential paper (locally, via specter2_local.py) and ask ChromaDB
for the most similar stored paper vectors -- which tells us which
professors have written the most topically similar work.

ChromaDB runs fully embedded/local (just a folder on disk) -- no
server process needed, matching the "no Docker" simplification.
"""

import os
os.environ["ANONYMIZED_TELEMETRY"] = "False"

import chromadb
from app.config.settings import settings

_client = chromadb.PersistentClient(path=str(settings.chroma_persist_dir))

_collection = _client.get_or_create_collection(
    name="professor_papers",
    metadata={"hnsw:space": "cosine"},  # cosine similarity, standard for text embeddings
)


def add_professor_papers(professor_name: str, scholar_id: str, papers: list[dict]) -> None:
    """
    Stores each of a professor's embedded papers in ChromaDB.

    Each paper dict must already have an 'embedding' key (from
    embed_papers_for_professor). Uses scholar_id + paper index as a
    stable unique ID so re-running this for the same professor
    overwrites rather than duplicates.
    """
    ids = []
    embeddings = []
    metadatas = []
    documents = []

    for i, paper in enumerate(papers):
        if "embedding" not in paper:
            continue  # skip papers that weren't embedded (e.g. empty text)
        coauthor_ids = ",".join(
            c["authorId"] for c in paper.get("coauthors", []) if c.get("authorId")
        )
        ids.append(f"{scholar_id}_{i}")
        embeddings.append(paper["embedding"])
        metadatas.append({
            "professor_name": professor_name,
            "scholar_id": scholar_id,
            "title": paper.get("title", ""),
            "year": str(paper.get("year", "")),
            "coauthor_ids": coauthor_ids,
        })
        documents.append(paper.get("title", ""))

    if not ids:
        return

    _collection.upsert(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents,
    )


def find_matching_professors(query_embedding: list[float], top_k: int = 10) -> list[dict]:
    """
    Given the confidential paper's embedding, finds the top_k most
    similar stored papers across all professors, and returns them
    ranked by similarity (best match first).

    Returns one entry per matching PAPER (not deduplicated by professor
    yet) -- e.g. if a professor has 2 highly relevant papers, they may
    appear twice. Aggregation into a per-professor ranking happens in
    the matching layer, not here.
    """
    results = _collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
    )

    matches = []
    for i in range(len(results["ids"][0])):
        distance = results["distances"][0][i]
        matches.append({
            "professor_name": results["metadatas"][0][i]["professor_name"],
            "scholar_id": results["metadatas"][0][i]["scholar_id"],
            "matched_paper_title": results["metadatas"][0][i]["title"],
            "similarity_score": 1 - distance,  # cosine distance -> similarity
            "coauthor_ids": results["metadatas"][0][i].get("coauthor_ids", ""),
        })

    return matches
def get_professor_coauthor_ids(scholar_id: str) -> set[str]:
    """
    Returns the union of co-author IDs across ALL of this professor's
    indexed papers -- used for conflict-of-interest checking, since a
    conflict should be based on the professor's whole publication
    history, not just the one paper that happened to match by topic.
    """
    results = _collection.get(
        where={"scholar_id": scholar_id},
        include=["metadatas"],
    )

    all_ids = set()
    for metadata in results.get("metadatas", []):
        ids_str = metadata.get("coauthor_ids", "")
        if ids_str:
            all_ids.update(cid.strip() for cid in ids_str.split(",") if cid.strip())

    return all_ids