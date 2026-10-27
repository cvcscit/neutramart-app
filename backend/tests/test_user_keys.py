"""Upload key layout: keys are built from the verified user and only that user's keys are accepted."""

from __future__ import annotations

import pytest

from app.user_keys import is_upload_key, new_upload_key

from .conftest import USER_ID, upload_key


def test_new_key_is_under_the_users_uploads_prefix() -> None:
    key = new_upload_key(USER_ID, ".png")

    assert key.startswith(f"users/{USER_ID}/uploads/") and key.endswith(".png")
    assert is_upload_key(USER_ID, key)


def test_new_keys_are_unique() -> None:
    assert new_upload_key(USER_ID, ".jpg") != new_upload_key(USER_ID, ".jpg")


@pytest.mark.parametrize(
    "key",
    [
        upload_key(user_id="bob_at_example_com"),  # another user's upload
        upload_key(user_id="ana_at_example_com_evil"),  # a user id that extends this one
        f"users/{USER_ID}/scans/20261026T120000Z.json",  # a record, not an upload
        f"users/{USER_ID}/uploads/../../bob_at_example_com/uploads/0123456789abcdef0123456789abcdef.jpg",
        f"users/{USER_ID}/uploads/nested/0123456789abcdef0123456789abcdef.jpg",
        "ana@example.com/0123456789abcdef0123456789abcdef.jpg",  # the pre-2026-10-26 layout
        f"users/{USER_ID}/uploads/",
    ],
)
def test_keys_outside_the_users_uploads_are_rejected(key: str) -> None:
    assert not is_upload_key(USER_ID, key)
