"""Action handlers in ``main``: object keys in a payload must sit under the caller's ``users/{user_id}/``."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app.nutrasmart_agent import main

USER_ID = "ana_at_example_com"
BUCKET = "test-bucket"
OWN_IMAGE = f"users/{USER_ID}/uploads/0123456789abcdef0123456789abcdef.jpg"
OWN_VIDEO = f"users/{USER_ID}/uploads/0123456789abcdef0123456789abcdef.webm"
OUTSIDE_KEY_ERROR = {"error": "Object key is outside the user's data."}


class RecordingS3:
    """Records put_object calls; the handlers under test write scan records and nothing else."""

    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, **kwargs) -> None:
        self.puts.append(kwargs)


@pytest.fixture
def s3(monkeypatch: pytest.MonkeyPatch) -> RecordingS3:
    fake = RecordingS3()
    services = SimpleNamespace(
        s3=fake,
        bedrock=None,
        classifier=SimpleNamespace(get=lambda: None),
        settings=SimpleNamespace(s3_bucket_name=BUCKET),
    )
    monkeypatch.setattr(main, "_food_scan_services", lambda: services)
    return fake


@pytest.fixture
def analysed(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Replaces the food pipeline; each entry is the list of keys one call was asked to read."""
    calls: list[list[str]] = []

    def fake_analyze(refs, **kwargs) -> dict:
        calls.append([ref.key for ref in refs])
        return {"description": "Dal and rice", "calories": "450 kcal"}

    monkeypatch.setattr(main, "analyze_food_images", fake_analyze)
    return calls


def _analyze(*keys: str) -> dict:
    images = [{"key": key, "content_type": "image/jpeg"} for key in keys]
    return main.invoke({"action": "analyze", "user_id": USER_ID, "images": images})


def test_own_upload_is_analysed_and_recorded(s3: RecordingS3, analysed: list[list[str]]) -> None:
    result = _analyze(OWN_IMAGE)

    assert result["description"] == "Dal and rice"
    assert analysed == [[OWN_IMAGE]]
    record = s3.puts[0]
    assert record["Bucket"] == BUCKET and record["Key"].startswith(f"users/{USER_ID}/scans/")
    assert json.loads(record["Body"])["image_keys"] == [OWN_IMAGE]


@pytest.mark.parametrize(
    "key",
    [
        "users/bob_at_example_com/uploads/0123456789abcdef0123456789abcdef.jpg",
        f"users/{USER_ID}_x/uploads/0123456789abcdef0123456789abcdef.jpg",
        f"users/{USER_ID}/../bob_at_example_com/uploads/0123456789abcdef0123456789abcdef.jpg",
        "ana@example.com/0123456789abcdef0123456789abcdef.jpg",
    ],
)
def test_a_key_outside_the_users_data_refuses_the_request(
    s3: RecordingS3, analysed: list[list[str]], key: str
) -> None:
    assert _analyze(OWN_IMAGE, key) == OUTSIDE_KEY_ERROR
    assert analysed == [] and s3.puts == []


def test_face_scan_reads_the_own_video_from_the_user_bucket(
    s3: RecordingS3, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: dict = {}

    def fake_face_scan(key: str, *, user_s3, user_bucket: str, services) -> dict:
        seen.update(key=key, s3=user_s3, bucket=user_bucket)
        return {"heart_rate": {"status": "ok", "heart_rate_bpm": 70.0}}

    monkeypatch.setattr(main, "analyze_face_scan", fake_face_scan)
    monkeypatch.setattr(main, "_biomarker_services", lambda: None)

    main.invoke({"action": "face_scan", "user_id": USER_ID, "key": OWN_VIDEO})

    assert seen == {"key": OWN_VIDEO, "s3": s3, "bucket": BUCKET}
    assert s3.puts[0]["Key"].startswith(f"users/{USER_ID}/vitals_scans/")


def test_face_scan_refuses_another_users_video(s3: RecordingS3, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main, "analyze_face_scan", lambda key, **kwargs: calls.append(key))

    result = main.invoke(
        {"action": "face_scan", "user_id": USER_ID, "key": "users/bob_at_example_com/uploads/v.webm"}
    )

    assert result == OUTSIDE_KEY_ERROR
    assert calls == [] and s3.puts == []


def test_log_id_is_short_stable_and_not_the_user_id() -> None:
    assert main._log_id(USER_ID) == main._log_id(USER_ID)
    assert len(main._log_id(USER_ID)) == 12 and "ana" not in main._log_id(USER_ID)
