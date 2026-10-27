"""``OriginVerifyMiddleware``: only CloudFront's secret header, or an explicitly exempted origin, gets through."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import main

SECRET = "cloudfront-shared-secret"
DEMO_ORIGIN = "http://demo.example"


@pytest.fixture
def gated(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(main, "CF_ORIGIN_SECRET", SECRET)
    monkeypatch.setattr(main, "ORIGIN_VERIFY_EXEMPT_ORIGINS", frozenset())
    return TestClient(main.app)


def test_request_without_the_secret_is_forbidden(gated: TestClient) -> None:
    assert gated.get("/api/testimonials").status_code == 403


def test_request_with_a_wrong_secret_is_forbidden(gated: TestClient) -> None:
    assert gated.get("/api/testimonials", headers={"X-Origin-Verify": "guess"}).status_code == 403


def test_request_with_the_secret_passes(gated: TestClient) -> None:
    assert gated.get("/api/testimonials", headers={"X-Origin-Verify": SECRET}).status_code == 200


def test_health_needs_no_secret(gated: TestClient) -> None:
    assert gated.get("/health").status_code == 200


def test_origin_is_not_exempt_unless_configured(gated: TestClient) -> None:
    assert gated.get("/api/testimonials", headers={"Origin": DEMO_ORIGIN}).status_code == 403


def test_configured_exempt_origin_passes(gated: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(main, "ORIGIN_VERIFY_EXEMPT_ORIGINS", frozenset({DEMO_ORIGIN}))

    assert gated.get("/api/testimonials", headers={"Origin": DEMO_ORIGIN}).status_code == 200
