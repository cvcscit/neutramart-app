"""S3 key layout for the files a user uploads to their regional bucket.

Uploads live at ``users/{user_id}/uploads/{32 hex chars}{ext}``, under the same per-user
prefix as the rest of the user's records, so tenant isolation and erasure are one prefix.
``user_id`` must come from the verified token (``app.auth.user_id_from_email``), never
from the request body.
"""

import re
import uuid

_UPLOAD_NAME = re.compile(r"[0-9a-f]{32}\.[a-z0-9]{1,5}")


def _uploads_prefix(user_id: str) -> str:
    return f"users/{user_id}/uploads/"


def new_upload_key(user_id: str, ext: str) -> str:
    """A fresh, unguessable key for one upload; ``ext`` is the lower-case extension incl. the dot."""
    return f"{_uploads_prefix(user_id)}{uuid.uuid4().hex}{ext}"


def is_upload_key(user_id: str, key: str) -> bool:
    """True if ``key`` has the shape ``new_upload_key`` produces for this user and no other."""
    prefix = _uploads_prefix(user_id)
    return key.startswith(prefix) and _UPLOAD_NAME.fullmatch(key[len(prefix):]) is not None
