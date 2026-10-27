"""Google ID-token authentication for the API routes.

``get_current_user`` verifies the bearer token on every request (no server session, no
cached verification result) and returns the verified identity. ``user_id_from_email`` is the
one place the storage id under ``users/{user_id}/`` is derived from that identity, and
``user_log_id`` the one stand-in for it that may appear in a log line.
"""

import functools
import hashlib
import logging

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth import exceptions as google_exceptions
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import GOOGLE_CERTS_TIMEOUT_S, GOOGLE_CLIENT_ID

logger = logging.getLogger(__name__)

security = HTTPBearer()

_INVALID_TOKEN = "Invalid or expired token"


def user_id_from_email(email: str) -> str:
    """Storage id for a verified e-mail: ``@`` becomes ``_at_`` and ``.`` becomes ``_``."""
    return email.replace("@", "_at_").replace(".", "_")


def user_log_id(user_id: str) -> str:
    """Short, stable stand-in for ``user_id`` in log lines: the first 12 hex characters of its SHA-256.

    The agent's ``_log_id`` computes the same value, so edge and agent lines for one user correlate.
    """
    return hashlib.sha256(user_id.encode()).hexdigest()[:12]


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Verify the bearer Google ID token and return ``{"email", "name"}``.

    Raises 401 when the token is invalid, expired, issued for another client, or carries an
    e-mail Google has not verified; 503 when Google's signing certificates can't be fetched,
    so an outage on Google's side is not reported to the client as a bad session.
    """
    request = functools.partial(google_requests.Request(), timeout=GOOGLE_CERTS_TIMEOUT_S)
    try:
        payload = id_token.verify_oauth2_token(credentials.credentials, request, GOOGLE_CLIENT_ID)
    except google_exceptions.TransportError:
        logger.exception("Google certificate fetch failed")
        raise HTTPException(status_code=503, detail="Sign-in is temporarily unavailable.") from None
    except (ValueError, google_exceptions.GoogleAuthError):
        raise HTTPException(status_code=401, detail=_INVALID_TOKEN) from None

    email = payload.get("email")
    if not email or payload.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail=_INVALID_TOKEN)
    return {"email": email, "name": payload.get("given_name", "")}
