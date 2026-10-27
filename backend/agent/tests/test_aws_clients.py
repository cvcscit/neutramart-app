"""Every AWS client the agent builds carries explicit timeouts and retries from settings."""

from __future__ import annotations

import pytest

from app.nutrasmart_agent import main
from app.nutrasmart_agent.face_scan_biomarkers import services as biomarker_services
from app.nutrasmart_agent.face_scan_biomarkers.settings import (
    load_settings as load_biomarker_settings,
)
from app.nutrasmart_agent.food_scan.services import build_services
from app.nutrasmart_agent.food_scan.settings import load_settings


def test_chat_model_uses_the_settings_timeouts_and_token_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    services = build_services(load_settings({
        "BEDROCK_REGION": "us-east-1",
        "BEDROCK_CONNECT_TIMEOUT_S": "4",
        "BEDROCK_READ_TIMEOUT_S": "77",
        "AWS_MAX_RETRIES": "2",
        "CHAT_MAX_TOKENS": "1500",
    }))
    monkeypatch.setattr(main, "_food_scan_services", lambda: services)

    model = main._model()

    config = model.client.meta.config
    assert (config.connect_timeout, config.read_timeout) == (4.0, 77.0)
    # A built client normalizes Config's max_attempts (retries) to total attempts: 2 retries + 1.
    assert config.retries == {"total_max_attempts": 3, "mode": "standard"}
    assert model.get_config()["max_tokens"] == 1500


def test_biomarker_model_client_carries_timeouts(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict] = []
    monkeypatch.setattr(biomarker_services.boto3, "client", lambda service, **kwargs: built.append(kwargs))

    biomarker_services.build_services(
        load_biomarker_settings({"S3_CONNECT_TIMEOUT_S": "3", "S3_READ_TIMEOUT_S": "42", "AWS_MAX_RETRIES": "1"})
    )

    config = built[0]["config"]
    assert (config.connect_timeout, config.read_timeout) == (3.0, 42.0)
    assert config.retries == {"max_attempts": 1, "mode": "standard"}


def test_biomarker_settings_default_to_the_food_scan_s3_timeouts() -> None:
    biomarker, agent = load_biomarker_settings({}), load_settings({})

    assert (biomarker.s3_connect_timeout_s, biomarker.s3_read_timeout_s) == (
        agent.s3_connect_timeout_s, agent.s3_read_timeout_s,
    )
    assert biomarker.max_retries == agent.max_retries
