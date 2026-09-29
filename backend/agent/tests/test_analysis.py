"""Routing between the classifier path and the vision-LLM fallback in ``analyze_food_images``."""

from __future__ import annotations

import pytest

from app.nutrasmart_agent.analysis import ImageRef, analyze_food_images
from app.nutrasmart_agent.prompts import ANALYZE_PROMPT

from .conftest import FakeBedrock, FakeS3, ScriptedClassifier, jpeg_bytes


def _refs(n: int) -> list[ImageRef]:
    return [ImageRef(key=f"img{i}.jpg", content_type="image/jpeg") for i in range(n)]


def _s3(n: int) -> FakeS3:
    return FakeS3({f"img{i}.jpg": jpeg_bytes() for i in range(n)})


def _run(n, classifier, settings, bedrock=None):
    bedrock = bedrock or FakeBedrock()
    result = analyze_food_images(
        _refs(n), s3=_s3(n), bedrock=bedrock, classifier=classifier, settings=settings
    )
    return result, bedrock


def _has_image_block(content: list[dict]) -> bool:
    return any("image" in block for block in content)


def test_all_confident_uses_text_only_llm(settings):
    classifier = ScriptedClassifier([("butter_chicken", 0.91), ("garlic_naan", 0.75)])
    result, bedrock = _run(2, classifier, settings)

    assert result["recognition"]["source"] == "classifier"
    assert len(bedrock.calls) == 1
    content = bedrock.last_content
    assert not _has_image_block(content)
    assert "Butter Chicken" in content[0]["text"] and "Garlic Naan" in content[0]["text"]


def test_duplicate_labels_are_listed_once(settings):
    classifier = ScriptedClassifier([("idli", 0.9), ("idli", 0.8)])
    _, bedrock = _run(2, classifier, settings)
    assert bedrock.last_content[0]["text"].count("- Idli") == 1


def test_one_uncertain_image_falls_back_to_vision(settings):
    classifier = ScriptedClassifier([("butter_chicken", 0.91), ("garlic_naan", 0.59)])
    result, bedrock = _run(2, classifier, settings)

    assert result["recognition"]["source"] == "llm"
    assert len(result["recognition"]["predictions"]) == 2  # still recorded for auditing
    content = bedrock.last_content
    assert sum("image" in block for block in content) == 2
    assert content[-1]["text"] == ANALYZE_PROMPT


def test_threshold_is_inclusive(settings):
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.6)]), settings)
    assert result["recognition"]["source"] == "classifier"


def test_classifier_error_falls_back_to_vision(settings):
    result, bedrock = _run(1, ScriptedClassifier(error=True), settings)
    assert result["recognition"] == {"source": "llm", "threshold": 0.6, "predictions": []}
    assert _has_image_block(bedrock.last_content)


def test_no_classifier_uses_vision(settings):
    result, bedrock = _run(1, None, settings)
    assert result["recognition"]["source"] == "llm"
    assert _has_image_block(bedrock.last_content)


def test_result_is_backfilled(settings):
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.99)]), settings)
    assert result["protein"] == "N/A"
    assert result["micronutrients"]["iron"] == "N/A"


def test_prose_reply_degrades_gracefully(settings):
    result, _ = _run(1, None, settings, bedrock=FakeBedrock(reply="Sorry, I can't tell."))
    assert result["description"] == "No food detected"


def test_too_many_images_rejected(settings):
    with pytest.raises(ValueError, match="Maximum"):
        _run(settings.max_images_per_request + 1, None, settings)


def test_non_image_upload_rejected(settings):
    s3 = FakeS3({"img0.jpg": b"not an image"})
    with pytest.raises(ValueError, match="not a readable image"):
        analyze_food_images(_refs(1), s3=s3, bedrock=FakeBedrock(), classifier=None, settings=settings)
