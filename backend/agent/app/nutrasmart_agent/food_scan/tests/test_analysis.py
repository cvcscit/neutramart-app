"""Routing between the classifier and the vision LLM in ``analyze_food_images``, in both orders."""

from __future__ import annotations

from dataclasses import replace

import pytest

from app.nutrasmart_agent.food_scan.analysis import ImageRef, analyze_food_images
from app.nutrasmart_agent.food_scan.prompts import ANALYZE_PROMPT
from app.nutrasmart_agent.food_scan.settings import RecognitionOrder

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


def _llm_reply(confidence) -> dict:
    return {"description": "Vision meal", "calories": "400 kcal", "confidence": confidence}


LABELS_REPLY = {"description": "Labelled meal", "calories": "250 kcal"}


@pytest.fixture
def llm_first(settings):
    return replace(settings, recognition_order=RecognitionOrder.LLM_FIRST)


def test_all_confident_uses_text_only_llm(settings):
    classifier = ScriptedClassifier([("butter_chicken", 0.91), ("garlic_naan", 0.75)])
    result, bedrock = _run(2, classifier, settings)

    assert result["recognition"]["source"] == "classifier"
    assert result["recognition"]["models"] == [None, None]
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
    assert result["recognition"] == {
        "source": "llm",
        "order": "classifier_first",
        "threshold": 0.6,
        "llm_threshold": 0.6,
        "llm_confidence": 0.9,
        "fallback_used": True,
        "models": [],
        "predictions": [],
    }
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


def test_confident_classifier_reports_its_score_as_confidence(settings):
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.8)]), settings)
    assert result["confidence"] == 0.8
    assert result["recognition"]["llm_confidence"] is None
    assert result["recognition"]["fallback_used"] is False


# --- classifier first, both below threshold: higher score wins ---


def test_classifier_first_weak_llm_loses_to_higher_classifier(settings):
    bedrock = FakeBedrock([_llm_reply(0.3), LABELS_REPLY])
    result, bedrock = _run(1, ScriptedClassifier([("dhokla", 0.5)]), settings, bedrock)

    assert result["recognition"]["source"] == "classifier"
    assert result["description"] == "Labelled meal"
    assert result["recognition"]["fallback_used"] is False
    assert len(bedrock.calls) == 2
    assert _has_image_block(bedrock.calls[0]["messages"][0]["content"])
    assert not _has_image_block(bedrock.last_content)


def test_classifier_first_weak_llm_beats_lower_classifier(settings):
    bedrock = FakeBedrock(_llm_reply(0.55))
    result, bedrock = _run(1, ScriptedClassifier([("dhokla", 0.5)]), settings, bedrock)

    assert result["recognition"]["source"] == "llm"
    assert result["recognition"]["fallback_used"] is True
    assert len(bedrock.calls) == 1


def test_classifier_first_tie_keeps_classifier(settings):
    bedrock = FakeBedrock([_llm_reply(0.5), LABELS_REPLY])
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.5)]), settings, bedrock)
    assert result["recognition"]["source"] == "classifier"


# --- LLM first ---


def test_llm_first_confident_llm_skips_classifier(llm_first):
    classifier = ScriptedClassifier([("dhokla", 0.99)])
    result, bedrock = _run(1, classifier, llm_first, FakeBedrock(_llm_reply(0.8)))

    assert result["recognition"]["source"] == "llm"
    assert result["recognition"]["order"] == "llm_first"
    assert result["recognition"]["fallback_used"] is False
    assert result["confidence"] == 0.8
    assert classifier.calls == 0
    assert len(bedrock.calls) == 1


def test_llm_first_threshold_is_inclusive(llm_first):
    classifier = ScriptedClassifier([("dhokla", 0.99)])
    result, _ = _run(1, classifier, llm_first, FakeBedrock(_llm_reply(0.6)))
    assert result["recognition"]["source"] == "llm"
    assert classifier.calls == 0


def test_llm_first_weak_llm_falls_back_to_confident_classifier(llm_first):
    bedrock = FakeBedrock([_llm_reply(0.4), LABELS_REPLY])
    result, bedrock = _run(1, ScriptedClassifier([("dhokla", 0.9)]), llm_first, bedrock)

    assert result["recognition"]["source"] == "classifier"
    assert result["recognition"]["fallback_used"] is True
    assert result["recognition"]["llm_confidence"] == 0.4
    assert result["description"] == "Labelled meal"
    assert result["confidence"] == 0.9
    assert "Dhokla" in bedrock.last_content[0]["text"]
    assert not _has_image_block(bedrock.last_content)


@pytest.mark.parametrize("vision_reply", [
    "Sorry, I can't tell.",
    {"description": "No food detected", "confidence": 0.95},
])
def test_llm_first_no_food_or_prose_falls_back_to_classifier(llm_first, vision_reply):
    bedrock = FakeBedrock([vision_reply, LABELS_REPLY])
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.3)]), llm_first, bedrock)
    assert result["recognition"]["source"] == "classifier"
    assert result["recognition"]["llm_confidence"] == 0.0


@pytest.mark.parametrize("confidence", [None, "high", "nan"])
def test_missing_or_invalid_llm_confidence_scores_zero(llm_first, confidence):
    reply = {"description": "Vision meal"}
    if confidence is not None:
        reply["confidence"] = confidence
    bedrock = FakeBedrock([reply, LABELS_REPLY])
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.1)]), llm_first, bedrock)
    assert result["recognition"]["llm_confidence"] == 0.0
    assert result["recognition"]["source"] == "classifier"


def test_llm_confidence_is_clamped(llm_first):
    result, _ = _run(1, None, llm_first, FakeBedrock(_llm_reply(7)))
    assert result["confidence"] == 1.0


def test_llm_first_both_weak_higher_llm_wins(llm_first):
    bedrock = FakeBedrock(_llm_reply(0.5))
    classifier = ScriptedClassifier([("dhokla", 0.4)])
    result, bedrock = _run(1, classifier, llm_first, bedrock)

    assert result["recognition"]["source"] == "llm"
    assert result["recognition"]["fallback_used"] is False
    assert classifier.calls == 1
    assert len(result["recognition"]["predictions"]) == 1
    assert len(bedrock.calls) == 1


def test_llm_first_tie_keeps_llm(llm_first):
    result, _ = _run(1, ScriptedClassifier([("dhokla", 0.5)]), llm_first, FakeBedrock(_llm_reply(0.5)))
    assert result["recognition"]["source"] == "llm"


def test_llm_first_one_uncertain_image_uses_lowest_score(llm_first):
    classifier = ScriptedClassifier([("butter_chicken", 0.95), ("garlic_naan", 0.3)])
    result, _ = _run(2, classifier, llm_first, FakeBedrock(_llm_reply(0.4)))
    assert result["recognition"]["source"] == "llm"


def test_llm_first_without_classifier_returns_weak_llm(llm_first):
    result, bedrock = _run(1, None, llm_first, FakeBedrock(_llm_reply(0.2)))
    assert result["recognition"]["source"] == "llm"
    assert result["recognition"]["fallback_used"] is False
    assert len(bedrock.calls) == 1


def test_llm_first_classifier_error_returns_weak_llm(llm_first):
    result, bedrock = _run(1, ScriptedClassifier(error=True), llm_first, FakeBedrock(_llm_reply(0.2)))
    assert result["recognition"]["source"] == "llm"
    assert result["recognition"]["predictions"] == []
    assert len(bedrock.calls) == 1
