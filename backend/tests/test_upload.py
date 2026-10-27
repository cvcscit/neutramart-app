"""``POST /api/upload/presign``: the key comes from the verified identity, never from the body."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import BUCKET, USER_ID, FakeS3


def test_presign_key_is_built_from_the_verified_user(client: TestClient, fake_s3: FakeS3) -> None:
    response = client.post(
        "/api/upload/presign",
        json={"filename": "Meal.JPG", "content_type": "image/jpeg", "email": "bob@example.com"},
    )

    assert response.status_code == 200
    key = response.json()["key"]
    assert key.startswith(f"users/{USER_ID}/uploads/") and key.endswith(".jpg")
    assert "bob" not in key
    params = fake_s3.presigned[0]["params"]
    assert params == {"Bucket": BUCKET, "Key": key, "ContentType": "image/jpeg"}


def test_presign_rejects_a_disallowed_content_type(client: TestClient, fake_s3: FakeS3) -> None:
    response = client.post("/api/upload/presign", json={"filename": "x.html", "content_type": "text/html"})

    assert response.status_code == 400
    assert fake_s3.presigned == []


def test_presign_rejects_an_extension_that_does_not_match_the_type(client: TestClient) -> None:
    response = client.post("/api/upload/presign", json={"filename": "clip.mp4", "content_type": "image/png"})

    assert response.status_code == 400
