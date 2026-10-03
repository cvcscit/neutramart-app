"""Build the configured food classifier.

``CLASSIFIER_BACKENDS`` maps a backend name (``FOOD_CLASSIFIER_BACKEND``) to a loader.
To use a different checkpoint of the same architecture, change
``FOOD_CLASSIFIER_MODEL_URI``. To use a different architecture, add a class that
satisfies ``FoodClassifier`` and register its loader here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..settings import ClassifierSettings
from .base import ClassifierError, FoodClassifier
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
    """Resolve the model file and instantiate the configured backend."""
    loader = CLASSIFIER_BACKENDS.get(settings.backend)
    if loader is None:
        raise ClassifierError(
            f"Unknown classifier backend {settings.backend!r}; "
            f"expected one of {sorted(CLASSIFIER_BACKENDS)}."
        )
    path = resolve_model_path(settings.model_uri, settings.cache_dir, s3_client)
    return loader(path, settings)
