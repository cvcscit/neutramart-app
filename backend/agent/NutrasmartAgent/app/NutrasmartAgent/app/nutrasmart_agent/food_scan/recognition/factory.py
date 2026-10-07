"""Build the configured food classifier ensemble.

``CLASSIFIER_BACKENDS`` maps a backend name (``FOOD_CLASSIFIER_BACKEND``) to a loader.
Every checkpoint in ``FOOD_CLASSIFIER_MODELS`` is loaded with that backend and wrapped in
a ``HighestConfidenceClassifier``. To add or swap a checkpoint of the same architecture,
edit ``FOOD_CLASSIFIER_MODELS``. To use a different architecture, add a class that
satisfies ``FoodClassifier`` and register its loader here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..settings import ClassifierSettings
from .base import ClassifierError, FoodClassifier
from .ensemble import HighestConfidenceClassifier
from .model_store import resolve_model_path

# Loader signature: (local model path, classifier settings) -> FoodClassifier
ClassifierLoader = Callable[[Path, ClassifierSettings], FoodClassifier]


def _load_efficientnet_v2_s(path: Path, settings: ClassifierSettings) -> FoodClassifier:
    # Imported lazily so torch is only loaded when the classifier is enabled.
    from .efficientnet import EfficientNetV2SClassifier

    return EfficientNetV2SClassifier.from_checkpoint(
        path, top_k=settings.top_k, num_threads=settings.num_threads, device=settings.device
    )


CLASSIFIER_BACKENDS: dict[str, ClassifierLoader] = {
    "efficientnet_v2_s": _load_efficientnet_v2_s,
}


def build_classifier(settings: ClassifierSettings, s3_client) -> FoodClassifier:
    """Resolve every model file and load each one with the configured backend."""
    loader = CLASSIFIER_BACKENDS.get(settings.backend)
    if loader is None:
        raise ClassifierError(
            f"Unknown classifier backend {settings.backend!r}; "
            f"expected one of {sorted(CLASSIFIER_BACKENDS)}."
        )
    if not settings.models:
        raise ClassifierError("No classifier models configured.")
    members = {
        model.name: loader(resolve_model_path(model.uri, settings.cache_dir, s3_client), settings)
        for model in settings.models
    }
    return HighestConfidenceClassifier(members)
