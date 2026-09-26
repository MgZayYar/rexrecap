"""Project CRUD and ownership-isolation tests."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_project_crud_round_trip(client: TestClient):
    headers = auth_headers(client)

    created = client.post("/api/projects", json={"name": "My Channel", "description": "Recaps"}, headers=headers)
    assert created.status_code == 201, created.text
    project_id = created.json()["id"]
    assert created.json()["status"] == "active"

    listed = client.get("/api/projects", headers=headers)
    assert listed.status_code == 200
    assert [p["id"] for p in listed.json()] == [project_id]

    updated = client.patch(
        f"/api/projects/{project_id}", json={"name": "Renamed", "status": "archived"}, headers=headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"] == "Renamed"
    assert updated.json()["status"] == "archived"

    deleted = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}", headers=headers).status_code == 404


def test_projects_are_isolated_between_users(client: TestClient):
    owner = auth_headers(client, email="owner@example.com")
    stranger = auth_headers(client, email="stranger@example.com")

    created = client.post("/api/projects", json={"name": "Secret"}, headers=owner)
    project_id = created.json()["id"]

    assert client.get("/api/projects", headers=stranger).json() == []
    assert client.get(f"/api/projects/{project_id}", headers=stranger).status_code == 404
    assert client.patch(f"/api/projects/{project_id}", json={"name": "Hijacked"}, headers=stranger).status_code == 404
    assert client.delete(f"/api/projects/{project_id}", headers=stranger).status_code == 404


def test_project_requires_authentication(client: TestClient):
    assert client.post("/api/projects", json={"name": "Nope"}).status_code in {401, 403}
    assert client.get("/api/projects").status_code in {401, 403}


def test_project_name_is_validated(client: TestClient):
    headers = auth_headers(client)
    assert client.post("/api/projects", json={"name": ""}, headers=headers).status_code == 422
    assert client.post("/api/projects", json={}, headers=headers).status_code == 422
    # A name of only whitespace must be rejected, not stored as an empty name.
    assert client.post("/api/projects", json={"name": "   "}, headers=headers).status_code == 422


def test_project_name_is_trimmed(client: TestClient):
    headers = auth_headers(client)
    response = client.post("/api/projects", json={"name": "  My project  "}, headers=headers)
    assert response.status_code == 201
    assert response.json()["name"] == "My project"
