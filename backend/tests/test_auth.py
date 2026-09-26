"""Authentication flow tests."""

from fastapi.testclient import TestClient

from tests.conftest import auth_headers


def test_register_and_login_round_trip(client: TestClient):
    register = client.post("/api/auth/register", json={"email": "User@Example.com", "password": "secret1234"})
    assert register.status_code == 201, register.text
    assert register.json()["email"] == "user@example.com"

    login = client.post("/api/auth/login", json={"email": "user@example.com", "password": "secret1234"})
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {login.json()['access_token']}"})
    assert me.status_code == 200, me.text
    assert me.json()["email"] == "user@example.com"


def test_register_duplicate_email_conflicts(client: TestClient):
    client.post("/api/auth/register", json={"email": "dupe@example.com", "password": "secret1234"})
    again = client.post("/api/auth/register", json={"email": "dupe@example.com", "password": "secret1234"})
    assert again.status_code == 409


def test_login_wrong_password_is_unauthorized(client: TestClient):
    client.post("/api/auth/register", json={"email": "locked@example.com", "password": "secret1234"})
    response = client.post("/api/auth/login", json={"email": "locked@example.com", "password": "wrongpass"})
    assert response.status_code == 401


def test_protected_route_without_token_is_rejected(client: TestClient):
    assert client.get("/api/auth/me").status_code in {401, 403}
    assert client.get("/api/videos").status_code in {401, 403}


def test_invalid_token_is_rejected(client: TestClient):
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


def test_auth_headers_helper_logs_in(client: TestClient):
    headers = auth_headers(client)
    assert client.get("/api/auth/me", headers=headers).status_code == 200
