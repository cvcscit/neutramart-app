"""Local food-image recognition: classifier protocol, implementations and factory."""

from .base import ClassificationResult, ClassifierError, FoodClassifier, FoodPrediction
from .ensemble import HighestConfidenceClassifier
from .factory import CLASSIFIER_BACKENDS, build_classifier

__all__ = [
    "CLASSIFIER_BACKENDS",
    "ClassificationResult",
    "ClassifierError",
    "FoodClassifier",
    "FoodPrediction",
    "HighestConfidenceClassifier",
    "build_classifier",
]
