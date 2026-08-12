import uuid

from fastapi.testclient import TestClient

POLICY_PAYLOAD = {
    "name": "Star Health Comprehensive",
    "provider": "Star Health",
    "policy_number": "SH-2026-001",
    "description": "Family floater health insurance policy",
}


def create_policy(client: TestClient) -> dict:
    response = client.post("/api/v1/policies", json=POLICY_PAYLOAD)
    assert response.status_code == 201
    return response.json()


def test_create_policy(client: TestClient) -> None:
    body = create_policy(client)

    assert body["name"] == POLICY_PAYLOAD["name"]
    assert body["provider"] == POLICY_PAYLOAD["provider"]
    assert body["policy_number"] == POLICY_PAYLOAD["policy_number"]
    assert uuid.UUID(body["id"])  # valid UUID
    assert body["created_at"] is not None


def test_create_policy_requires_name(client: TestClient) -> None:
    response = client.post("/api/v1/policies", json={"provider": "Acme"})
    assert response.status_code == 422


def test_create_policy_rejects_empty_name(client: TestClient) -> None:
    response = client.post("/api/v1/policies", json={"name": ""})
    assert response.status_code == 422


def test_get_policy(client: TestClient) -> None:
    created = create_policy(client)

    response = client.get(f"/api/v1/policies/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_policy_not_found(client: TestClient) -> None:
    response = client.get(f"/api/v1/policies/{uuid.uuid4()}")

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "policy_not_found"


def test_list_policies(client: TestClient) -> None:
    for i in range(3):
        client.post("/api/v1/policies", json={"name": f"Policy {i}"})

    response = client.get("/api/v1/policies")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    assert len(body["items"]) == 3


def test_list_policies_pagination(client: TestClient) -> None:
    for i in range(5):
        client.post("/api/v1/policies", json={"name": f"Policy {i}"})

    response = client.get("/api/v1/policies", params={"limit": 2, "offset": 4})

    body = response.json()
    assert body["total"] == 5
    assert len(body["items"]) == 1
    assert body["limit"] == 2
    assert body["offset"] == 4


def test_update_policy(client: TestClient) -> None:
    created = create_policy(client)

    response = client.patch(
        f"/api/v1/policies/{created['id']}",
        json={"description": "Updated description"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["description"] == "Updated description"
    assert body["name"] == POLICY_PAYLOAD["name"]  # untouched field preserved


def test_update_policy_not_found(client: TestClient) -> None:
    response = client.patch(f"/api/v1/policies/{uuid.uuid4()}", json={"name": "X"})
    assert response.status_code == 404


def test_delete_policy(client: TestClient) -> None:
    created = create_policy(client)

    response = client.delete(f"/api/v1/policies/{created['id']}")
    assert response.status_code == 204

    response = client.get(f"/api/v1/policies/{created['id']}")
    assert response.status_code == 404


def test_delete_policy_not_found(client: TestClient) -> None:
    response = client.delete(f"/api/v1/policies/{uuid.uuid4()}")
    assert response.status_code == 404
