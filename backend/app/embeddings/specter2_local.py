"""
Embeds the CONFIDENTIAL unpublished paper, entirely offline.

Uses the same shared model as the public path, wrapped in the network guard.
This file must never import requests/httpx/openai or any networking library.
"""

from app.embeddings.specter2_model import build_text, embed_texts
from app.security.network_guard import no_network_calls


@no_network_calls
def embed_text(title: str, abstract: str = "") -> list[float]:
    if not title or not title.strip():
        raise ValueError("Cannot embed empty title.")
    return embed_texts([build_text(title, abstract)])[0]