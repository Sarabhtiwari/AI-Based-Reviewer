"""
Embeds the confidential unpublished paper into a vector, entirely
offline, using SPECTER2 (a scientific-paper embedding model).

CRITICAL CONSTRAINT: this file must NEVER import requests/httpx/openai
or any networking library. The @no_network_calls decorator enforces
this at runtime as a safety net -- but the real guarantee comes from
this file's imports being limited to local model-loading libraries only.
"""

from sentence_transformers import SentenceTransformer
from app.config.settings import settings
from app.security.network_guard import no_network_calls

# Loaded once at import time -- the model itself is downloaded to local
# disk cache the first time this runs (one-time internet use to fetch
# model weights), then used fully offline for every call after that.
_model = SentenceTransformer(settings.embedding_model_name)


@no_network_calls
def embed_text(text: str) -> list[float]:
    """
    Converts a paper's title/abstract text into a vector (list of floats)
    using SPECTER2, running entirely on the local machine's CPU.

    This is the ONLY function that should ever touch the confidential
    paper's content.
    """
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")

    embedding = _model.encode(text, convert_to_numpy=True)
    return embedding.tolist()