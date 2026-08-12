import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.exceptions import PolicyNotFoundError
from app.services.retrieval_service import RetrievedChunk

CHUNKS = [
    RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=18,
        section="Pre-existing Diseases",
        content="Diabetes is covered after a waiting period of 24 months.",
        similarity=0.91,
    ),
    RetrievedChunk(
        chunk_id=uuid.uuid4(),
        document_id=uuid.uuid4(),
        page_number=19,
        section=None,
        content="Waiting periods apply to all pre-existing conditions.",
        similarity=0.85,
    ),
]


@pytest.fixture
def canned_search(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Replace vector search with canned results (SQLite can't run pgvector).

    Real similarity search is exercised against Postgres in the live stack.
    """
    calls: dict = {}

    def fake_semantic_search(db, policy_id, query, top_k=None):
        calls["policy_id"] = policy_id
        calls["query"] = query
        calls["top_k"] = top_k
        return CHUNKS

    monkeypatch.setattr(
        "app.services.retrieval_service.semantic_search", fake_semantic_search
    )
    return calls


class TestSearchEndpoint:
    def test_search_returns_ranked_chunks(
        self, client: TestClient, canned_search: dict
    ) -> None:
        policy_id = uuid.uuid4()
        response = client.post(
            f"/api/v1/policies/{policy_id}/search",
            json={"query": "Is diabetes covered?", "top_k": 2},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "Is diabetes covered?"
        assert len(body["results"]) == 2
        first = body["results"][0]
        assert first["page_number"] == 18
        assert first["section"] == "Pre-existing Diseases"
        assert first["similarity_score"] == 0.91
        assert "Diabetes is covered" in first["content"]
        assert canned_search["policy_id"] == policy_id
        assert canned_search["top_k"] == 2

    def test_search_requires_query(self, client: TestClient, canned_search: dict) -> None:
        response = client.post(f"/api/v1/policies/{uuid.uuid4()}/search", json={})
        assert response.status_code == 422

    def test_search_rejects_bad_top_k(self, client: TestClient, canned_search: dict) -> None:
        response = client.post(
            f"/api/v1/policies/{uuid.uuid4()}/search",
            json={"query": "x", "top_k": 0},
        )
        assert response.status_code == 422

    def test_search_unknown_policy(
        self, client: TestClient, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def raise_not_found(db, policy_id, query, top_k=None):
            raise PolicyNotFoundError(policy_id)

        monkeypatch.setattr(
            "app.services.retrieval_service.semantic_search", raise_not_found
        )
        response = client.post(
            f"/api/v1/policies/{uuid.uuid4()}/search", json={"query": "x"}
        )
        assert response.status_code == 404

    def test_search_policy_without_documents_conflicts(
        self, client: TestClient, fake_embeddings
    ) -> None:
        """Real code path (no canned search): a policy with no uploaded
        documents must return a helpful 409, not an empty result list."""
        policy = client.post("/api/v1/policies", json={"name": "Empty"}).json()

        response = client.post(
            f"/api/v1/policies/{policy['id']}/search", json={"query": "anything"}
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "no_processed_documents"


class TestDebugSearchEndpoint:
    def test_debug_search_returns_ranked_list(
        self, client: TestClient, canned_search: dict
    ) -> None:
        policy_id = uuid.uuid4()
        response = client.post(
            "/api/v1/debug/search",
            json={"policy_id": str(policy_id), "query": "Is maternity covered?"},
        )

        assert response.status_code == 200
        body = response.json()
        assert [r["rank"] for r in body["results"]] == [1, 2]
        assert body["results"][0]["page"] == 18
        assert body["results"][0]["similarity"] == 0.91
        assert canned_search["query"] == "Is maternity covered?"
