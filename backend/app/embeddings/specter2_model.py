"""
The ONE shared SPECTER2 model (base encoder + proximity adapter).

Both the public-paper path (paper_embedder.py) and the confidential path
(specter2_local.py) call this module, so every vector in the project is
produced by exactly the same method and lives in the same vector space.
"""

import torch
from transformers import AutoTokenizer
from adapters import AutoAdapterModel

_BASE_MODEL = "allenai/specter2_base"
_ADAPTER = "allenai/specter2"  # proximity adapter: paper-to-paper similarity

_tokenizer = AutoTokenizer.from_pretrained(_BASE_MODEL)
_model = AutoAdapterModel.from_pretrained(_BASE_MODEL)
_model.load_adapter(_ADAPTER, source="hf", load_as="specter2", set_active=True)
_model.eval()


def build_text(title: str, abstract: str = "") -> str:
    """SPECTER2 input format: title [SEP] abstract (title alone if no abstract)."""
    title = (title or "").strip()
    abstract = (abstract or "").strip()
    if title and abstract:
        return title + _tokenizer.sep_token + abstract
    return title or abstract


def embed_texts(texts: list[str], batch_size: int = 16) -> list[list[float]]:
    """Embeds many texts in batches. CLS-token vector, 768 dims each."""
    vectors: list[list[float]] = []
    with torch.no_grad():  # inference only, saves memory and time
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            inputs = _tokenizer(
                batch, padding=True, truncation=True,
                return_tensors="pt", max_length=512,
            )
            output = _model(**inputs)
            vectors.extend(output.last_hidden_state[:, 0, :].tolist())
    return vectors