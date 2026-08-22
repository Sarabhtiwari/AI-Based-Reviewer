"""
Embeds a professor's PUBLIC papers into vectors using SPECTER2.

Unlike specter2_local.py (which is reserved for the confidential paper
and guarded against network calls), this file handles public paper data
-- no network restriction needed. Uses the same title+abstract format
as specter2_local.py so both sides of any similarity comparison are
consistent.
"""

from sentence_transformers import SentenceTransformer
from app.config.settings import settings

_model = SentenceTransformer(settings.embedding_model_name)


def _combine_title_abstract(title: str, abstract: str = "") -> str:
    title = (title or "").strip()
    abstract = (abstract or "").strip()

    if title and abstract:
        return f"{title}[SEP]{abstract}"
    return title or abstract


def embed_paper(title: str, abstract: str = "") -> list[float]:
    """
    Embeds a single public paper (title+abstract) into a 768-dim vector.
    """
    text = _combine_title_abstract(title, abstract)
    if not text:
        raise ValueError("Cannot embed empty text -- provide at least a title.")

    embedding = _model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def embed_papers_for_professor(papers: list[dict]) -> list[dict]:
    """
    Takes a list of paper dicts (with 'title' and optionally 'abstract')
    and adds an 'embedding' key (768-dim vector) to each one.
    """
    for paper in papers:
        paper["embedding"] = embed_paper(
            title=paper.get("title", ""),
            abstract=paper.get("abstract", ""),
        )
    return papers