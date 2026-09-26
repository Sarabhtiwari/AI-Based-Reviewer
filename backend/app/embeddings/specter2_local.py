"""
Embeds the confidential unpublished paper into a vector, entirely
offline, using SPECTER2 (base encoder + proximity adapter).

CRITICAL CONSTRAINT: this file must NEVER import requests/httpx/openai
or any networking library. The @no_network_calls decorator enforces
this at runtime as a safety net.
"""

from transformers import AutoTokenizer
from adapters import AutoAdapterModel
from app.security.network_guard import no_network_calls

_BASE_MODEL_NAME = "allenai/specter2_base"
_ADAPTER_NAME = "allenai/specter2"  # proximity adapter (paper-to-paper similarity)

_tokenizer = AutoTokenizer.from_pretrained(_BASE_MODEL_NAME)
_model = AutoAdapterModel.from_pretrained(_BASE_MODEL_NAME)
_model.load_adapter(_ADAPTER_NAME, source="hf", load_as="specter2", set_active=True)


@no_network_calls
def embed_text(title: str, abstract: str = "") -> list[float]:
    """
    Converts a paper's title + abstract into a vector using SPECTER2,
    running entirely on the local machine's CPU.

    SPECTER2 is trained on title + abstract concatenated with a [SEP]
    token, so combining them (rather than using just one) gives the
    intended embedding quality.
    """
    if not title or not title.strip():
        raise ValueError("Cannot embed empty title.")

    text = title.strip() + _tokenizer.sep_token + (abstract or "").strip()

    inputs = _tokenizer(
        text, padding=True, truncation=True, return_tensors="pt", max_length=512
    )
    output = _model(**inputs)
    embedding = output.last_hidden_state[:, 0, :]
    return embedding[0].tolist()