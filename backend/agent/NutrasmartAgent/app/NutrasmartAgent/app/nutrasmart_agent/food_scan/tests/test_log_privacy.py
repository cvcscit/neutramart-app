"""Errors and log lines from the food pipeline carry no object key and no model text."""

from __future__ import annotations

import logging
from dataclasses import replace

import pytest

from app.nutrasmart_agent.food_scan.analysis import (
    ImageRef,
    _parse_or_graceful,
    load_images,
)

from .conftest import FakeS3, jpeg_bytes

KEY = "users/ana_at_example_com/uploads/0123456789abcdef0123456789abcdef.jpg"


def test_oversize_image_error_names_its_position_not_its_key(settings):
    refs = [ImageRef(key=KEY, content_type="image/jpeg")]
    small = replace(settings, max_image_size_bytes=16)

    with pytest.raises(ValueError) as caught:
        load_images(refs, FakeS3({KEY: jpeg_bytes()}), small)

    assert "ana_at_example_com" not in str(caught.value)
    assert "Image 1 of 1" in str(caught.value)


def test_prose_reply_is_logged_by_length_not_text(caplog):
    caplog.set_level(logging.WARNING)
    reply = "I see a plate of dal next to an insulin pen."

    result = _parse_or_graceful(reply, "end_turn")

    assert result["description"]
    assert "insulin" not in caplog.text
    assert f"{len(reply)} characters" in caplog.text
