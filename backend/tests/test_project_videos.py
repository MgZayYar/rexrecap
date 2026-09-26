"""Tests for Phase 13: linking videos to projects."""

from fastapi.testclient import TestClient

from tests.conftest import FAKE_MP4, auth_headers


def _upload(client: TestClient, headers: dict[str, str], project_id: int | None = None):
    data = {"project_id": str(project_id)} if project_id is not None else {}
    return client.post(
        "/api/videos/upload",
        headers=headers,
        files={"file": ("clip.mp4", FAKE_MP4, "video/mp4")},
        data=data,
    )


def _project(client: TestClient, headers: dict[str, str], name: str = "Recap") -> int:
    response = client.post("/api/projects", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_upload_with_project_assigns_video(client: TestClient) -> None:
    headers = auth_headers(client)
    project_id = _project(client, headers)
    response = _upload(client, headers, project_id)
    assert response.status_code == 201, response.text
    assert response.json()["project_id"] == project_id


def test_upload_with_foreign_project_rejected(client: TestClient) -> None:
    owner = auth_headers(client, email="owner@example.com")
    intruder = auth_headers(client, email="intruder@example.com")
    project_id = _project(client, owner)
    response = _upload(client, intruder, project_id)
    assert response.status_code == 404


def test_patch_assign_move_unassign_video(client: TestClient) -> None:
    headers = auth_headers(client)
    project_a = _project(client, headers, "A")
    project_b = _project(client, headers, "B")
    video_id = _upload(client, headers).json()["id"]

    response = client.patch(f"/api/videos/{video_id}", headers=headers,
                            json={"project_id": project_a})
    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == project_a

    response = client.patch(f"/api/videos/{video_id}", headers=headers,
                            json={"project_id": project_b})
    assert response.json()["project_id"] == project_b

    response = client.patch(f"/api/videos/{video_id}", headers=headers,
                            json={"project_id": None})
    assert response.status_code == 200, response.text
    assert response.json()["project_id"] is None


def test_patch_omitted_project_id_leaves_video_untouched(client: TestClient) -> None:
    headers = auth_headers(client)
    project_id = _project(client, headers)
    video_id = _upload(client, headers, project_id).json()["id"]
    response = client.patch(f"/api/videos/{video_id}", headers=headers, json={})
    assert response.status_code == 200, response.text
    assert response.json()["project_id"] == project_id


def test_patch_with_foreign_project_rejected(client: TestClient) -> None:
    owner = auth_headers(client, email="owner2@example.com")
    intruder = auth_headers(client, email="intruder2@example.com")
    project_id = _project(client, owner)
    video_id = _upload(client, intruder).json()["id"]
    response = client.patch(f"/api/videos/{video_id}", headers=intruder,
                            json={"project_id": project_id})
    assert response.status_code == 404


def test_list_project_videos(client: TestClient) -> None:
    headers = auth_headers(client)
    project_id = _project(client, headers)
    _upload(client, headers, project_id)
    _upload(client, headers)  # unassigned video stays out
    response = client.get(f"/api/projects/{project_id}/videos", headers=headers)
    assert response.status_code == 200, response.text
    videos = response.json()
    assert len(videos) == 1
    assert videos[0]["project_id"] == project_id


def test_delete_project_unlinks_but_keeps_videos(client: TestClient) -> None:
    headers = auth_headers(client)
    project_id = _project(client, headers)
    video_id = _upload(client, headers, project_id).json()["id"]
    response = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert response.status_code == 204, response.text
    response = client.get("/api/videos", headers=headers)
    assert response.status_code == 200, response.text
    videos = response.json()
    assert len(videos) == 1 and videos[0]["project_id"] is None
    assert videos[0]["id"] == video_id
