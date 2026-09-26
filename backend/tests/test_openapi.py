"""The OpenAPI schema must build cleanly and cover every registered route.

docs/api.md is written by hand; this test guards the machine-readable
contract it describes: the schema builds, every route has a unique
operation id, and the documented resource prefixes all appear.
"""

from fastapi.testclient import TestClient

DOCUMENTED_PREFIXES = [
    "/api/auth",
    "/api/assistant",
    "/api/batch",
    "/api/dubbings",
    "/api/faces",
    "/api/jobs",
    "/api/notifications",
    "/api/projects",
    "/api/shorts",
    "/api/subtitles",
    "/api/thumbnails",
    "/api/transcripts",
    "/api/translations",
    "/api/videos",
]


def test_openapi_schema_builds_and_covers_all_routes(client: TestClient) -> None:
    response = client.get("/openapi.json")
    assert response.status_code == 200
    schema = response.json()

    operation_ids: list[str] = []
    for path, methods in schema["paths"].items():
        for method, operation in methods.items():
            if method in {"get", "post", "patch", "put", "delete"}:
                operation_ids.append(operation["operationId"])
    assert len(operation_ids) == len(set(operation_ids)), "duplicate operation ids"

    paths = set(schema["paths"])
    for prefix in DOCUMENTED_PREFIXES:
        assert any(path.startswith(prefix + "/") or path == prefix for path in paths), prefix

    # Both the versioned and the legacy prefix serve the same routes.
    v1_paths = {path for path in paths if path.startswith("/api/v1/")}
    legacy_paths = {path for path in paths if path.startswith("/api/") and not path.startswith("/api/v1/")}
    assert v1_paths, "no /api/v1 routes registered"
    assert legacy_paths, "no legacy /api routes registered"
    assert {path.replace("/api/v1/", "/api/", 1) for path in v1_paths} == legacy_paths

    # The unauthenticated health probe is deliberately outside /api.
    assert "/health" in paths
