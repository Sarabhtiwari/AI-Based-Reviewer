"""
Embeds the confidential unpublished paper into a vector, entirely
offline, using SPECTER2 (a scientific-paper embedding model).

CRITICAL CONSTRAINT: this file must NEVER import requests/httpx/openai
or any networking library. The @no_network_calls decorator enforces
this at runtime as a safety net -- but the real guarantee comes from
this file's imports being limited to local model-loading libraries only.

Uses title + abstract concatenated (SPECTER2's standard input format,
and the same format used for public papers in paper_embedder.py) so
similarity scores are comparing like with like.
"""

from sentence_transformers import SentenceTransformer
from app.config.settings import settings
from app.security.network_guard import no_network_calls

_model = SentenceTransformer(settings.embedding_model_name)


def _combine_title_abstract(title: str, abstract: str = "") -> str:
    """
    SPECTER2 was trained on title+abstract pairs, typically joined with
    the tokenizer's [SEP] token. sentence-transformers handles this
    internally when given a single string -- we just concatenate with
    a separator here.
    """
    title = (title or "").strip()
    abstract = (abstract or "").strip()

    if title and abstract:
        return f"{title}[SEP]{abstract}"
    return title or abstract


@no_network_calls
def embed_text(title: str, abstract: str = "") -> list[float]:
    """
    Converts a paper's title+abstract into a vector (list of floats)
    using SPECTER2, running entirely on the local machine's CPU.

    This is the ONLY function that should ever touch the confidential
    paper's content.
    """
    text = _combine_title_abstract(title, abstract)
    if not text:
        raise ValueError("Cannot embed empty text -- provide at least a title.")

    # SPECTER2 truncates beyond ~512 tokens -- fine here since we're only
    # feeding title+abstract, not the full paper body.
    embedding = _model.encode(text, convert_to_numpy=True)
    return embedding.tolist()