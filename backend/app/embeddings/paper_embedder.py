"""
Embeds a professor's PUBLIC papers using the shared SPECTER2 model.
"""

from app.embeddings.specter2_model import build_text, embed_texts


def embed_paper(title: str, abstract: str = "") -> list[float]:
    text = build_text(title, abstract)
    if not text:
        raise ValueError("Cannot embed empty text -- provide at least a title.")
    return embed_texts([text])[0]


def embed_papers_for_professor(papers: list[dict]) -> list[dict]:
    """
    Adds an 'embedding' key to each paper. Papers with no title and no
    abstract are dropped (nothing to embed), so the returned list can be
    shorter than the input. Batched, so much faster than one at a time.
    """
    usable = [p for p in papers if build_text(p.get("title"), p.get("abstract"))]
    vectors = embed_texts([build_text(p.get("title"), p.get("abstract")) for p in usable])
    for paper, vector in zip(usable, vectors):
        paper["embedding"] = vector
    return usable