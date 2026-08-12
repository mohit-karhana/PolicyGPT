import io
import uuid
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Document, Policy, ProcessingStatus
from tests.pdf_factory import make_pdf


def upload_pdf(
    client: TestClient,
    policy_id: str,
    content: bytes,
    filename: str = "policy.pdf",
):
    return client.post(
        f"/api/v1/policies/{policy_id}/documents",
        files={"file": (filename, io.BytesIO(content), "application/pdf")},
    )


class TestUploadDocument:
    def test_upload_valid_pdf(
        self, client: TestClient, queued_documents: list[uuid.UUID]
    ) -> None:
        policy = client.post("/api/v1/policies", json={"name": "P"}).json()

        response = upload_pdf(client, policy["id"], make_pdf(["Some policy text"]))

        assert response.status_code == 202
        body = response.json()
        assert body["processing_status"] == "pending"
        assert body["filename"] == "policy.pdf"
        assert body["policy_id"] == policy["id"]
        # Processing was queued for exactly this document...
        assert queued_documents == [uuid.UUID(body["id"])]
        # ...and the file landed in storage under a server-generated name.
        stored = Path(settings.upload_dir) / policy["id"] / f"{body['id']}.pdf"
        assert stored.exists()

    def test_upload_rejects_wrong_extension(self, client: TestClient) -> None:
        policy = client.post("/api/v1/policies", json={"name": "P"}).json()

        response = upload_pdf(client, policy["id"], make_pdf(["x"]), filename="notes.txt")

        assert response.status_code == 415
        assert response.json()["error"]["code"] == "invalid_file_type"

    def test_upload_rejects_non_pdf_content(self, client: TestClient) -> None:
        policy = client.post("/api/v1/policies", json={"name": "P"}).json()

        response = upload_pdf(client, policy["id"], b"plain text pretending to be pdf")

        assert response.status_code == 415
        assert response.json()["error"]["code"] == "invalid_file_type"

    def test_upload_accepts_pdf_with_leading_junk(self, client: TestClient) -> None:
        """The PDF header may legally appear within the first 1024 bytes."""
        policy = client.post("/api/v1/policies", json={"name": "P"}).json()
        content = b"\xef\xbb\xbf junk prefix \n" + make_pdf(["text"])

        response = upload_pdf(client, policy["id"], content)

        assert response.status_code == 202

    def test_upload_rejects_oversized_file(
        self, client: TestClient, monkeypatch
    ) -> None:
        monkeypatch.setattr(settings, "max_upload_size_mb", 1)
        policy = client.post("/api/v1/policies", json={"name": "P"}).json()
        big = make_pdf(["x"]) + b"\n%" + b"0" * (2 * 1024 * 1024)

        response = upload_pdf(client, policy["id"], big)

        assert response.status_code == 413
        assert response.json()["error"]["code"] == "file_too_large"

    def test_upload_unknown_policy(self, client: TestClient) -> None:
        response = upload_pdf(client, str(uuid.uuid4()), make_pdf(["x"]))

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "policy_not_found"


def seed_policy_with_document(db_session: Session) -> tuple[Policy, Document]:
    """Insert rows directly; the upload endpoint only arrives in Phase 2."""
    policy = Policy(name="Test Policy")
    document = Document(
        policy=policy,
        filename="policy.pdf",
        file_path="uploads/policy.pdf",
        processing_status=ProcessingStatus.PENDING.value,
    )
    db_session.add(policy)
    db_session.commit()
    db_session.refresh(policy)
    db_session.refresh(document)
    return policy, document


def test_list_documents_empty(client: TestClient) -> None:
    created = client.post("/api/v1/policies", json={"name": "Empty Policy"}).json()

    response = client.get(f"/api/v1/policies/{created['id']}/documents")

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


def test_list_documents_unknown_policy(client: TestClient) -> None:
    response = client.get(f"/api/v1/policies/{uuid.uuid4()}/documents")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "policy_not_found"


def test_list_documents(client: TestClient, db_session: Session) -> None:
    policy, document = seed_policy_with_document(db_session)

    response = client.get(f"/api/v1/policies/{policy.id}/documents")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(document.id)
    assert body["items"][0]["processing_status"] == "pending"


def test_get_document_status(client: TestClient, db_session: Session) -> None:
    _, document = seed_policy_with_document(db_session)

    response = client.get(f"/api/v1/documents/{document.id}")

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "policy.pdf"
    assert body["processing_status"] == "pending"
    assert body["page_count"] is None


def test_get_document_not_found(client: TestClient) -> None:
    response = client.get(f"/api/v1/documents/{uuid.uuid4()}")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "document_not_found"
