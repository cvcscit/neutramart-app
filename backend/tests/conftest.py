"""Shared fixtures for the edge tests: a TestClient with the identity and region dependencies faked.

``app.config`` loads ``backend/.env`` at import, but ``load_dotenv`` never overrides a variable
that is already set, so the variables that change request handling are pinned below before the
app is imported. No test talks to AWS or Google.
"""

from __future__ import annotations

import os

os.environ["CF_ORIGIN_SECRET"] = ""
os.environ["AGENT_LOCAL_URL"] = ""
os.environ["ORIGIN_VERIFY_EXEMPT_ORIGINS"] = ""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.auth import get_current_user
from app.limiter import limiter
from app.main import app
from app.regions import get_data_context

EMAIL = "ana@example.com"
USER_ID = "ana_at_example_com"
BUCKET = "test-bucket"
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:000000000000:runtime/test"


class FakeS3:
    """Records presign requests and answers the daily-quota listing with an empty prefix."""

    def __init__(self) -> None:
        self.presigned: list[dict] = []

    def generate_presigned_url(self, operation: str, Params: dict, ExpiresIn: int) -> str:
        self.presigned.append({"operation": operation, "params": Params, "expires_in": ExpiresIn})
        return f"https://{Params['Bucket']}.s3.us-east-1.amazonaws.com/{Params['Key']}?signed"

    def list_objects_v2(self, Bucket: str, Prefix: str) -> dict:
        return {"KeyCount": 0}


class RecordingAgent:
    """Stands in for ``invoke_agent``: records each call and replies or raises as scripted."""

    def __init__(self, reply: dict | Exception) -> None:
        self.reply = reply
        self.calls: list[dict] = []

    def __call__(self, payload: dict, agent_arn: str, session_id: str | None = None) -> dict:
        self.calls.append({"payload": payload, "agent_arn": agent_arn, "session_id": session_id})
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def upload_key(name: str = "0123456789abcdef0123456789abcdef.jpg", user_id: str = USER_ID) -> str:
    return f"users/{user_id}/uploads/{name}"


@pytest.fixture(autouse=True)
def _reset_rate_limits() -> None:
    limiter.reset()


@pytest.fixture
def fake_s3() -> FakeS3:
    return FakeS3()


@pytest.fixture
def client(fake_s3: FakeS3) -> Iterator[TestClient]:
    """A client whose requests come from ``EMAIL`` and resolve to a configured us-east-1."""
    app.dependency_overrides[get_current_user] = lambda: {"email": EMAIL, "name": "Ana"}
    app.dependency_overrides[get_data_context] = lambda: {
        "region": "us-east-1",
        "bucket": BUCKET,
        "s3": fake_s3,
        "agent_arn": AGENT_ARN,
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
