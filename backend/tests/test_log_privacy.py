"""Edge log lines name a user by ``user_log_id`` only: no user id, object key, meal name or reply body."""

from __future__ import annotations

import io
import logging
import re

import pytest
from fastapi.testclient import TestClient

from app import agent_client
from app.agent_client import AgentError
from app.auth import user_log_id
from app.routes import meals

from .conftest import BUCKET, EMAIL, USER_ID

MEAL_ID = "20261026T120000Z_Ana_s_diabetic_lunch"
MEAL = {
    "mealName": "Ana's diabetic lunch",
    "mealType": "lunch",
    "totalNutrition": {"calories": 450, "protein": 20, "carbs": 60, "fat": 12, "fiber": 8},
    "dishes": [{"name": "dal", "servingSize": "1 bowl"}],
}


class BrokenS3:
    """Fails every write and listing the way an unreachable S3 does; ``head_object`` finds the meal."""

    def put_object(self, **kwargs) -> None:
        raise RuntimeError("S3 unavailable")

    def list_objects_v2(self, **kwargs) -> dict:
        raise RuntimeError("S3 unavailable")

    def head_object(self, **kwargs) -> dict:
        return {}

    def delete_object(self, **kwargs) -> None:
        raise RuntimeError("S3 unavailable")


class UnreadableS3:
    """Lists one meal record whose body is not JSON."""

    def list_objects_v2(self, Bucket: str, Prefix: str) -> dict:
        return {"Contents": [{"Key": f"{Prefix}{MEAL_ID}.json"}]}

    def get_object(self, Bucket: str, Key: str) -> dict:
        return {"Body": io.BytesIO(b"not json")}


@pytest.fixture
def fake_s3() -> BrokenS3:
    """Overrides conftest's ``fake_s3``, so ``client`` routes every S3 call to a failing double."""
    return BrokenS3()


@pytest.fixture(autouse=True)
def _capture(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)


def _assert_private(caplog: pytest.LogCaptureFixture) -> None:
    assert caplog.records, "expected a log line"
    for leaked in (USER_ID, EMAIL, "users/", "Ana_s_diabetic", "diabetic lunch"):
        assert leaked not in caplog.text
    assert user_log_id(USER_ID) in caplog.text


def test_failed_meal_save_logs_only_the_hashed_user(client: TestClient, caplog: pytest.LogCaptureFixture) -> None:
    assert client.post("/api/meals", json=MEAL).status_code == 500
    _assert_private(caplog)


def test_failed_meal_delete_logs_neither_key_nor_meal_name(
    client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    assert client.delete(f"/api/meals/{MEAL_ID}").status_code == 500
    _assert_private(caplog)


def test_failed_listing_logs_only_the_hashed_user(caplog: pytest.LogCaptureFixture) -> None:
    assert meals._load_s3_jsons(USER_ID, "meals", BrokenS3(), BUCKET) == []
    _assert_private(caplog)


def test_unreadable_record_logs_neither_key_nor_meal_name(caplog: pytest.LogCaptureFixture) -> None:
    assert meals._load_s3_jsons(USER_ID, "meals", UnreadableS3(), BUCKET) == []
    _assert_private(caplog)


def test_malformed_agent_reply_is_logged_by_size_only(caplog: pytest.LogCaptureFixture) -> None:
    body = "<html>ana@example.com logged dal and an insulin dose</html>"

    with pytest.raises(AgentError):
        agent_client._parse_result(body)

    assert "insulin" not in caplog.text and EMAIL not in caplog.text
    assert f"{len(body)} characters" in caplog.text


def test_user_log_id_is_a_short_stable_hash() -> None:
    assert user_log_id(USER_ID) == user_log_id(USER_ID)
    assert re.fullmatch(r"[0-9a-f]{12}", user_log_id(USER_ID))
