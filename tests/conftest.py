"""Test fixtures.

Tests run against an in-memory SQLite database by overriding the `get_db`
dependency — no Docker required. This works for Phase 1 because no table
uses Postgres-specific column types yet; once the DocumentChunk table adds
a pgvector column (Phase 3/4), chunk-related tests will need a real
Postgres instance.
"""

import hashlib
import random
import uuid
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.dependencies import get_db
from app.core.config import settings
from app.main import app
from app.models import Base

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,  # share the single in-memory DB across connections
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture(autouse=True)
def _fresh_database() -> Iterator[None]:
    """Give every test an empty database."""
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(autouse=True)
def _tmp_upload_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Store uploaded files in a per-test temp directory."""
    monkeypatch.setattr(settings, "upload_dir", str(tmp_path / "uploads"))


@pytest.fixture(autouse=True)
def queued_documents(monkeypatch: pytest.MonkeyPatch) -> list[uuid.UUID]:
    """Record queued document ids instead of enqueueing to a real broker.

    Tests get no Redis; the Celery pipeline itself is tested by calling
    `process_document_pipeline` directly.
    """
    queued: list[uuid.UUID] = []
    monkeypatch.setattr(
        "app.api.routes.documents.queue_document_processing", queued.append
    )
    return queued


class FakeEmbeddingService:
    """Deterministic stand-in for the real model.

    Same text always gets the same vector, so tests are stable and fast —
    no model download, no PyTorch. Semantic *quality* of retrieval is
    verified against the real model in the live stack, not in unit tests.
    """

    dimension = 384

    def embed_text(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            seed = int.from_bytes(hashlib.sha256(text.encode()).digest()[:8], "big")
            rng = random.Random(seed)
            vectors.append([rng.uniform(-1.0, 1.0) for _ in range(self.dimension)])
        return vectors


@pytest.fixture
def fake_embeddings(monkeypatch: pytest.MonkeyPatch) -> FakeEmbeddingService:
    fake = FakeEmbeddingService()
    monkeypatch.setattr(
        "app.services.embedding_service.get_embedding_service", lambda: fake
    )
    return fake


@pytest.fixture
def client() -> Iterator[TestClient]:
    def override_get_db() -> Iterator[Session]:
        session = TestingSessionLocal()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db
    # raise_server_exceptions=False lets us assert on the JSON body of 500s
    # produced by the generic exception handler.
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
    app.dependency_overrides.clear()
