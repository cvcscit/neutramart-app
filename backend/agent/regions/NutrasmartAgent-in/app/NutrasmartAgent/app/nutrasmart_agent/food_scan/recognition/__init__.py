"""Local food-image recognition: classifier protocol, implementations and factory."""

from .base import ClassificationResult, ClassifierError, FoodClassifier, FoodPrediction
from .factory import CLASSIFIER_BACKENDS, build_classifier

__all__ = [
    "CLASSIFIER_BACKENDS",
    "ClassificationResult",
    "ClassifierError",
    "FoodClassifier",
    "FoodPrediction",
    "build_classifier",
]
