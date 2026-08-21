"""
Central configuration for the backend.

Every module (connectors, embeddings, vectorstore, and later graph/agents)
needs shared config. Defining it once here and importing `settings`
everywhere avoids hardcoded values scattered across files.

Neo4j settings are declared now, unused, so that when the knowledge-graph
phase starts, app/graph/neo4j_client.py can just import `settings` and
read them -- no changes needed to this file.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Public data source APIs ---
    semantic_scholar_base_url: str = "https://api.semanticscholar.org/graph/v1"
    openalex_base_url: str = "https://api.openalex.org"
    dblp_base_url: str = "https://dblp.org/search/publ/api"
    orcid_base_url: str = "https://pub.orcid.org/v3.0"
    semantic_scholar_api_key: str | None = None

    # --- Grok API (used for keyword extraction on PUBLIC papers only) ---
    groq_api_key: str | None = None
    groq_base_url: str = "https://api.groq.com/openai/v1"
    groq_model: str = "qwen/qwen3.6-27b"
    tavily_api_key: str | None = None

    # --- Local paths ---
    data_raw_dir: Path = BACKEND_ROOT / "data" / "raw"
    data_processed_dir: Path = BACKEND_ROOT / "data" / "processed"
    data_confidential_dir: Path = BACKEND_ROOT / "data" / "confidential"
    chroma_persist_dir: Path = BACKEND_ROOT / "data" / "chroma_db"

    # --- Embedding model (local, offline) ---
    embedding_model_name: str = "allenai/specter2_base"

    # --- Keyword extraction ---
    max_keywords_per_paper: int = 8

    # --- Networking safety ---
    allow_network_in_embedding_module: bool = False

    # --- Knowledge graph (Neo4j) -- NOT USED YET ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "changeme"


settings = Settings()


def ensure_directories() -> None:
    """Create local data directories if they don't exist yet. Safe to call repeatedly."""
    for path in [settings.data_raw_dir, settings.data_processed_dir,
                 settings.data_confidential_dir, settings.chroma_persist_dir]:
        path.mkdir(parents=True, exist_ok=True)