"""Application configuration.

All configuration is environment-driven (12-factor style). Values are read
from the process environment first, then from a local `.env` file if present.

Import `settings` (a cached singleton) rather than instantiating `Settings`
in multiple places, so the environment is only parsed once.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "PolicyGPT"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"

    # --- Database ---
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/policygpt"

    # --- Redis / Celery (used from Phase 2 onwards) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Embeddings (used from Phase 4 onwards) ---
    # The dimension is defined ONCE here. Everything that needs it (the
    # pgvector column, the embedding service, migrations) must read it from
    # settings instead of hard-coding 384.
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # --- Chunking (used from Phase 3 onwards) ---
    chunk_size: int = 500
    chunk_overlap: int = 100

    # --- Retrieval / RAG ---
    top_k: int = 5
    llm_api_key: str = ""
    llm_model: str = ""
    # Any OpenAI-compatible endpoint works (OpenAI, Groq, local Ollama, ...).
    llm_base_url: str = "https://api.openai.com/v1"
    llm_timeout_seconds: float = 60.0

    # --- File uploads (used from Phase 2 onwards) ---
    upload_dir: str = "uploads"
    max_upload_size_mb: int = 25

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
