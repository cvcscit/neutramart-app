"""``POST /api/analyze`` and ``/api/weekly-summary/generate``: key scoping and generic error details."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent_client import AgentError
from app.routes import analyze

from .conftest import AGENT_ARN, USER_ID, RecordingAgent, upload_key

ANALYSIS = {"description": "Dal and rice", "calories": "450 kcal"}


def _use_agent(monkeypatch: pytest.MonkeyPatch, reply: dict | Exception) -> RecordingAgent:
    agent = RecordingAgent(reply)
    monkeypatch.setattr(analyze, "invoke_agent", agent)
    return agent


def _analyze(client: TestClient, *keys: str):
    return client.post("/api/analyze", json={"images": [{"key": k, "content_type": "image/jpeg"} for k in keys]})


def test_own_upload_is_sent_to_the_regional_agent(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _use_agent(monkeypatch, ANALYSIS)

    response = _analyze(client, upload_key())

    assert response.status_code == 200 and response.json() == ANALYSIS
    assert agent.calls[0]["agent_arn"] == AGENT_ARN
    assert agent.calls[0]["payload"]["user_id"] == USER_ID


def test_any_foreign_key_rejects_the_whole_request(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    agent = _use_agent(monkeypatch, ANALYSIS)

    response = _analyze(client, upload_key(), f"users/{USER_ID}/health_profile.json")

    assert response.status_code == 400
    assert agent.calls == []


def test_analysis_failure_details_stay_on_the_server(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_agent(monkeypatch, AgentError("torch.OutOfMemoryError: CUDA out of memory"))

    response = _analyze(client, upload_key())

    assert response.status_code == 502
    assert "torch" not in response.json()["detail"]


def test_summary_failure_is_a_generic_502(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    _use_agent(monkeypatch, AgentError("No food scans found for this user."))

    response = client.post("/api/weekly-summary/generate")

    assert response.status_code == 502
    assert "No food scans" not in response.json()["detail"]
