"""Tests for the unauthenticated /health probe."""

from fastapi.testclient import TestClient


def test_health_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"
    assert body["storage"] == "ok"


def test_health_degraded_when_storage_unreachable(
    client: TestClient, monkeypatch,
) -> None:
    import app.api.routes.health as health_route

    monkeypatch.setattr(
        health_route, "_check_storage", lambda: "simulated storage outage")
    response = client.get("/health")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert "simulated storage outage" in body["storage"]
