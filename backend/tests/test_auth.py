"""Google ID-token verification in ``get_current_user``: what is accepted and what each failure maps to."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from google.auth import exceptions as google_exceptions

from app import auth

CREDENTIALS = HTTPAuthorizationCredentials(scheme="Bearer", credentials="id-token")


def _verify_returning(claims: dict | Exception, seen: list | None = None):
    def fake_verify(token: str, request, audience: str) -> dict:
        if seen is not None:
            seen.append(request)
        if isinstance(claims, Exception):
            raise claims
        return claims

    return fake_verify


def _status_for(monkeypatch: pytest.MonkeyPatch, claims: dict | Exception) -> int:
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", _verify_returning(claims))
    with pytest.raises(HTTPException) as caught:
        auth.get_current_user(CREDENTIALS)
    return caught.value.status_code


def test_verified_token_returns_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    claims = {"email": "ana@example.com", "email_verified": True, "given_name": "Ana"}
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", _verify_returning(claims))

    assert auth.get_current_user(CREDENTIALS) == {"email": "ana@example.com", "name": "Ana"}


def test_cert_fetch_is_bounded_by_the_configured_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list = []
    claims = {"email": "ana@example.com", "email_verified": True}
    monkeypatch.setattr(auth.id_token, "verify_oauth2_token", _verify_returning(claims, seen))

    auth.get_current_user(CREDENTIALS)

    assert seen[0].keywords == {"timeout": auth.GOOGLE_CERTS_TIMEOUT_S}


@pytest.mark.parametrize("verified", [False, None, "true"])
def test_unverified_email_is_rejected(monkeypatch: pytest.MonkeyPatch, verified: object) -> None:
    claims = {"email": "ana@example.com", "email_verified": verified}
    assert _status_for(monkeypatch, claims) == 401


def test_token_without_email_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _status_for(monkeypatch, {"email_verified": True}) == 401


def test_invalid_token_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _status_for(monkeypatch, ValueError("Token expired")) == 401


def test_wrong_issuer_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _status_for(monkeypatch, google_exceptions.GoogleAuthError("Wrong issuer")) == 401


def test_google_outage_is_unavailable_not_unauthorized(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _status_for(monkeypatch, google_exceptions.TransportError("timed out")) == 503


def test_user_id_from_email() -> None:
    assert auth.user_id_from_email("ana.b@example.com") == "ana_b_at_example_com"
