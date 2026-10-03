"""Smoke test against a real checkpoint; skipped unless ``FOOD_CLASSIFIER_TEST_CHECKPOINT`` is set.

Example::

    FOOD_CLASSIFIER_TEST_CHECKPOINT=/path/to/nutrasmart_efficientnetv2s_best.pt pytest -k checkpoint
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from PIL import Image

CHECKPOINT = os.environ.get("FOOD_CLASSIFIER_TEST_CHECKPOINT")

pytestmark = pytest.mark.skipif(not CHECKPOINT, reason="FOOD_CLASSIFIER_TEST_CHECKPOINT not set")


def _classify(device: str):
    from app.nutrasmart_agent.food_scan.recognition.efficientnet import EfficientNetV2SClassifier

    classifier = EfficientNetV2SClassifier.from_checkpoint(
        Path(CHECKPOINT), top_k=5, num_threads=2, device=device
    )
    return classifier.classify(Image.new("RGB", (320, 240), (180, 90, 30)))


def test_checkpoint_loads_and_classifies():
    result = _classify("cpu")

    assert len(result.predictions) == 5
    confidences = [p.confidence for p in result.predictions]
    assert confidences == sorted(confidences, reverse=True)
    assert all(0.0 <= c <= 1.0 for c in confidences)


def test_cuda_matches_cpu():
    torch = pytest.importorskip("torch")
    if not torch.cuda.is_available():
        pytest.skip("CUDA not available")

    cpu, cuda = _classify("cpu"), _classify("cuda")

    assert [p.food_id for p in cuda.predictions] == [p.food_id for p in cpu.predictions]
    for a, b in zip(cpu.predictions, cuda.predictions):
        assert abs(a.confidence - b.confidence) < 1e-3
