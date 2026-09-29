"""Env parsing and validation in ``settings.load_settings``."""

from __future__ import annotations

import pytest

from app.nutrasmart_agent.settings import load_settings


def test_defaults_keep_classifier_disabled():
    settings = load_settings({})
    assert settings.classifier.enabled is False
    assert settings.classifier.threshold == 0.60
    assert settings.classifier.backend == "efficientnet_v2_s"


def test_classifier_env_overrides():
    settings = load_settings({
        "FOOD_CLASSIFIER_ENABLED": "true",
        "FOOD_CLASSIFIER_MODEL_URI": "s3://b/models/food.pt",
        "FOOD_CLASSIFIER_THRESHOLD": "0.75",
        "FOOD_CLASSIFIER_TOP_K": "3",
    })
    assert settings.classifier.enabled is True
    assert settings.classifier.model_uri == "s3://b/models/food.pt"
    assert settings.classifier.threshold == 0.75
    assert settings.classifier.top_k == 3


@pytest.mark.parametrize("value", ["-0.1", "1.5"])
def test_threshold_out_of_range_rejected(value):
    with pytest.raises(ValueError, match="FOOD_CLASSIFIER_THRESHOLD"):
        load_settings({"FOOD_CLASSIFIER_THRESHOLD": value})


def test_enabled_without_model_uri_rejected():
    with pytest.raises(ValueError, match="FOOD_CLASSIFIER_MODEL_URI"):
        load_settings({"FOOD_CLASSIFIER_ENABLED": "1"})


def test_device_defaults_to_cpu_and_accepts_cuda():
    assert load_settings({}).classifier.device == "cpu"
    assert load_settings({"FOOD_CLASSIFIER_DEVICE": "CUDA"}).classifier.device == "cuda"


def test_unknown_device_rejected():
    with pytest.raises(ValueError, match="FOOD_CLASSIFIER_DEVICE"):
        load_settings({"FOOD_CLASSIFIER_DEVICE": "tpu"})
