"""Data-region resolution: unmapped countries go to the default, unconfigured regions are refused."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app import regions
from app.auth import get_current_user
from app.main import app

BUCKETS = {"us-east-1": "bucket-us", "ap-south-1": "bucket-in", "ca-central-1": "", "eu-west-1": "bucket-eu"}
ARNS = {"us-east-1": "arn-us", "ap-south-1": "arn-in", "ca-central-1": "arn-ca", "eu-west-1": ""}
REAL_S3_CLIENT_FOR_REGION = regions.s3_client_for_region  # the autouse fixture replaces it


def _request(country: str | None) -> Request:
    headers = [(b"cloudfront-viewer-country", country.encode())] if country else []
    return Request({"type": "http", "headers": headers})


@pytest.fixture(autouse=True)
def _configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(regions, "REGION_BUCKETS", BUCKETS)
    monkeypatch.setattr(regions, "REGION_AGENT_ARNS", ARNS)
    monkeypatch.setattr(regions, "AGENT_LOCAL_URL", "")
    monkeypatch.setattr(regions, "s3_client_for_region", lambda region: f"s3-{region}")


def test_configured_region_returns_its_own_bucket_and_runtime() -> None:
    ctx = regions.get_data_context(_request("IN"))

    assert ctx == {"region": "ap-south-1", "bucket": "bucket-in", "s3": "s3-ap-south-1", "agent_arn": "arn-in"}


def test_unmapped_country_uses_the_default_region() -> None:
    assert regions.get_data_context(_request("BR"))["region"] == regions.DEFAULT_DATA_REGION


def test_region_without_bucket_is_refused_not_rerouted() -> None:
    with pytest.raises(regions.RegionNotConfigured) as caught:
        regions.get_data_context(_request("CA"))
    assert caught.value.region == "ca-central-1"


def test_region_without_runtime_is_refused() -> None:
    with pytest.raises(regions.RegionNotConfigured):
        regions.get_data_context(_request("FR"))


def test_local_agent_needs_no_runtime_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(regions, "AGENT_LOCAL_URL", "http://localhost:8080")

    assert regions.get_data_context(_request("FR"))["bucket"] == "bucket-eu"


def test_unconfigured_region_answers_503() -> None:
    app.dependency_overrides[get_current_user] = lambda: {"email": "ana@example.com", "name": "Ana"}
    try:
        response = TestClient(app).post(
            "/api/upload/presign",
            json={"filename": "meal.jpg", "content_type": "image/jpeg"},
            headers={"CloudFront-Viewer-Country": "CA"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "bucket" not in response.json()["detail"]


def test_s3_client_carries_timeouts_and_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    built: list[dict] = []
    monkeypatch.setattr(regions.boto3, "client", lambda service, **kwargs: built.append(kwargs))
    REAL_S3_CLIENT_FOR_REGION.cache_clear()

    REAL_S3_CLIENT_FOR_REGION("eu-west-1")
    REAL_S3_CLIENT_FOR_REGION.cache_clear()

    config = built[0]["config"]
    assert built[0]["region_name"] == "eu-west-1"
    assert (config.connect_timeout, config.read_timeout) == (regions.S3_CONNECT_TIMEOUT_S, regions.S3_READ_TIMEOUT_S)
    assert config.retries == {"max_attempts": regions.AWS_MAX_RETRIES, "mode": "standard"}
