"""Run several food classifiers on one image and keep the most confident answer.

Each member is a model trained on one cuisine (e.g. Chinese, Indian, Thai). Every member
classifies the image and the result with the highest top-1 confidence wins; ties go to
the member listed first. The winning result is tagged with the member's name so the saved
scan records which model recognized the dish.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Mapping

from PIL import Image

from .base import ClassificationResult, ClassifierError, FoodClassifier


class HighestConfidenceClassifier:
    """``FoodClassifier`` that returns the most confident member's result."""

    def __init__(self, members: Mapping[str, FoodClassifier]) -> None:
        if not members:
            raise ClassifierError("A classifier ensemble needs at least one member.")
        self._members = dict(members)

    def classify(self, image: Image.Image) -> ClassificationResult:
        """Classify with every member; a member's ``ClassifierError`` propagates."""
        best: ClassificationResult | None = None
        for name, classifier in self._members.items():
            result = classifier.classify(image)
            if best is None or result.top.confidence > best.top.confidence:
                best = replace(result, model=name)
        return best
