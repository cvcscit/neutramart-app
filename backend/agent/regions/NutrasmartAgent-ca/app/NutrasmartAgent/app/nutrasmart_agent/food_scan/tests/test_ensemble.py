"""Highest-confidence selection across cuisine models in ``recognition.ensemble``."""

from __future__ import annotations

import pytest
from PIL import Image

from app.nutrasmart_agent.food_scan.recognition import ClassifierError, HighestConfidenceClassifier

from .conftest import ScriptedClassifier

IMAGE = Image.new("RGB", (32, 32))


def test_most_confident_member_wins_and_is_tagged():
    ensemble = HighestConfidenceClassifier({
        "chinese": ScriptedClassifier([("dongpo_pork", 0.41)]),
        "indian": ScriptedClassifier([("aloo_gobi", 0.87)]),
        "thai": ScriptedClassifier([("thai_chicken_green_curry", 0.55)]),
    })
    result = ensemble.classify(IMAGE)
    assert result.model == "indian"
    assert result.top.food_id == "aloo_gobi"
    assert result.top.confidence == 0.87


def test_tie_keeps_first_member():
    ensemble = HighestConfidenceClassifier({
        "chinese": ScriptedClassifier([("dongpo_pork", 0.7)]),
        "thai": ScriptedClassifier([("pad_thai", 0.7)]),
    })
    assert ensemble.classify(IMAGE).model == "chinese"


def test_every_member_runs():
    members = {name: ScriptedClassifier([("dish", 0.5)]) for name in ("a", "b", "c")}
    HighestConfidenceClassifier(members).classify(IMAGE)
    assert [member.calls for member in members.values()] == [1, 1, 1]


def test_member_error_propagates():
    ensemble = HighestConfidenceClassifier({
        "chinese": ScriptedClassifier([("dongpo_pork", 0.9)]),
        "indian": ScriptedClassifier(error=True),
    })
    with pytest.raises(ClassifierError):
        ensemble.classify(IMAGE)


def test_empty_ensemble_rejected():
    with pytest.raises(ClassifierError):
        HighestConfidenceClassifier({})
