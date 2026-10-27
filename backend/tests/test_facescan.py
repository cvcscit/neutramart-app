"""``POST /api/facescan/analyze``: key scoping, the response whitelist and generic error details."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent_client import AgentError
from app.routes import facescan

from .conftest import USER_ID, RecordingAgent, upload_key

VIDEO_KEY = upload_key("0123456789abcdef0123456789abcdef.webm")

AGENT_RESULT = {
    "heart_rate": {
        "heart_rate_bpm": 72.5, "status": "ok", "windows_used": 3, "windows_total": 4,
        "gate": "trained", "reliability": 0.91, "spread_bpm": 2.0,
    },
    "bp": {"status": "ok", "experimental": True, "disclaimer": "Research estimate only.", "sbp": 118.0, "dbp": 76.0},
    "spo2": {"status": "unavailable", "reason": "SpO2 model is not deployed yet."},
}


def _post(client: TestClient, key: str = VIDEO_KEY):
    return client.post("/api/facescan/analyze", json={"key": key, "content_type": "video/webm"})


def _use_agent(monkeypatch: pytest.MonkeyPatch, reply: dict | Exception) -> RecordingAgent:
    agent = RecordingAgent(reply)
    monkeypatch.setattr(facescan, "invoke_agent", agent)
    return agent


def test_only_whitelisted_fields_reach_the_client(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _use_agent(monkeypatch, AGENT_RESULT)

    body = _post(client).json()

    assert body["heart_rate"] == {"status": "ok", "reason": None, "heart_rate_bpm": 72.5}
    assert body["bp"]["sbp"] == 118.0 and body["bp"]["experimental"] is True
    assert agent.calls[0]["payload"] == {"action": "face_scan", "user_id": USER_ID, "key": VIDEO_KEY}


def test_bp_and_spo2_are_always_flagged_experimental(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_agent(monkeypatch, AGENT_RESULT)

    spo2 = _post(client).json()["spo2"]

    assert spo2["status"] == "unavailable"
    assert spo2["experimental"] is True and spo2["disclaimer"]


def test_a_non_experimental_bp_from_the_agent_is_refused(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_agent(monkeypatch, {**AGENT_RESULT, "bp": {"status": "ok", "experimental": False, "sbp": 1, "dbp": 1}})

    assert _post(client).status_code == 502


def test_a_key_outside_the_users_uploads_is_rejected(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _use_agent(monkeypatch, AGENT_RESULT)

    response = _post(client, upload_key("0123456789abcdef0123456789abcdef.webm", user_id="bob_at_example_com"))

    assert response.status_code == 400
    assert agent.calls == []


def test_agent_failure_details_stay_on_the_server(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_agent(monkeypatch, AgentError("An error occurred (AccessDenied) when calling the GetObject operation"))

    response = _post(client)

    assert response.status_code == 502
    assert "AccessDenied" not in response.json()["detail"]
