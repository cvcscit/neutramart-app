"""Value objects and the protocol every food-image classifier implements.

A classifier takes one decoded RGB image and returns its top-k dish predictions with
calibrated-ish confidences in [0, 1]. The analysis flow only depends on this contract,
so swapping the model (checkpoint or architecture) never touches the analysis code.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol

from PIL import Image


class ClassifierError(Exception):
    """Raised when a classifier cannot be loaded or fails during inference."""


@dataclass(frozen=True)
class FoodPrediction:
    """One candidate dish for an image."""

    food_id: str
    display_name: str
    confidence: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class ClassificationResult:
    """Top-k predictions for one image, most confident first."""

    predictions: tuple[FoodPrediction, ...]

    @property
    def top(self) -> FoodPrediction:
        return self.predictions[0]


class FoodClassifier(Protocol):
    """A model that recognizes a dish in a single image."""

    def classify(self, image: Image.Image) -> ClassificationResult:
        """Classify an RGB image. Raises ``ClassifierError`` on failure."""
        ...
