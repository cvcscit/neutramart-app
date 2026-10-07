"""Centralized, env-driven settings for the NutraSmart agent.

Every tunable (model IDs, regions, bucket, image limits, classifier config, recognition
order and confidence thresholds, network timeouts) lives here. ``load_settings()`` reads the process environment once; callers
receive an immutable ``AgentSettings`` and never read ``os.environ`` themselves.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

_TRUE_VALUES = {"1", "true", "yes", "on"}
CLASSIFIER_DEVICES = ("cpu", "cuda")  # AgentCore has no GPU; "cuda" is for local runs only


class RecognitionOrder(str, Enum):
    """Which recognizer runs first; the other is the fallback when the first is not good enough."""

    CLASSIFIER_FIRST = "classifier_first"
    LLM_FIRST = "llm_first"


@dataclass(frozen=True)
class ClassifierModel:
    """One named checkpoint (e.g. a cuisine) in the classifier ensemble."""

    name: str
    uri: str


@dataclass(frozen=True)
class ClassifierSettings:
    """Configuration for the local food-image classifier (first-pass recognition).

    ``models`` are all run on every image; the most confident top-1 prediction wins.
    """

    enabled: bool
    backend: str
    models: tuple[ClassifierModel, ...]
    model_region: str
    threshold: float
    top_k: int
    cache_dir: str
    num_threads: int
    device: str


@dataclass(frozen=True)
class AgentSettings:
    """All runtime configuration for the agent."""

    bedrock_model_id: str
    bedrock_region: str
    s3_bucket_name: str
    s3_region: str

    max_image_size_bytes: int
    bedrock_max_image_bytes: int
    max_images_per_request: int
    analyze_max_tokens: int
    summary_max_tokens: int

    bedrock_connect_timeout_s: float
    bedrock_read_timeout_s: float
    s3_connect_timeout_s: float
    s3_read_timeout_s: float
    max_retries: int

    recognition_order: RecognitionOrder
    llm_confidence_threshold: float
    classifier: ClassifierSettings


def _get_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
    raw = env.get(name)
    return default if raw is None else raw.strip().lower() in _TRUE_VALUES


def _get_int(env: Mapping[str, str], name: str, default: int, minimum: int = 0) -> int:
    value = int(env.get(name, default))
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")
    return value


def _get_float(env: Mapping[str, str], name: str, default: float) -> float:
    return float(env.get(name, default))


def _get_unit_float(env: Mapping[str, str], name: str, default: float) -> float:
    value = _get_float(env, name, default)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be within [0, 1], got {value}")
    return value


def _get_recognition_order(env: Mapping[str, str]) -> RecognitionOrder:
    raw = env.get("FOOD_RECOGNITION_ORDER", RecognitionOrder.CLASSIFIER_FIRST.value).strip().lower()
    try:
        return RecognitionOrder(raw)
    except ValueError:
        allowed = [order.value for order in RecognitionOrder]
        raise ValueError(f"FOOD_RECOGNITION_ORDER must be one of {allowed}, got {raw!r}") from None


def _parse_models(raw: str) -> tuple[ClassifierModel, ...]:
    """Parse ``FOOD_CLASSIFIER_MODELS`` (``name=uri,name=uri``), keeping the configured order."""
    models: list[ClassifierModel] = []
    for entry in filter(None, (part.strip() for part in raw.split(","))):
        name, sep, uri = (piece.strip() for piece in entry.partition("="))
        if not sep or not name or not uri:
            raise ValueError(f"FOOD_CLASSIFIER_MODELS entries must be name=uri, got {entry!r}")
        if any(model.name == name for model in models):
            raise ValueError(f"FOOD_CLASSIFIER_MODELS has a duplicate model name {name!r}")
        models.append(ClassifierModel(name=name, uri=uri))
    return tuple(models)


def _load_classifier_settings(env: Mapping[str, str]) -> ClassifierSettings:
    threshold = _get_unit_float(env, "FOOD_CLASSIFIER_THRESHOLD", 0.60)
    device = env.get("FOOD_CLASSIFIER_DEVICE", "cpu").strip().lower()
    if device not in CLASSIFIER_DEVICES:
        raise ValueError(f"FOOD_CLASSIFIER_DEVICE must be one of {CLASSIFIER_DEVICES}, got {device!r}")

    settings = ClassifierSettings(
        enabled=_get_bool(env, "FOOD_CLASSIFIER_ENABLED", False),
        backend=env.get("FOOD_CLASSIFIER_BACKEND", "efficientnet_v2_s"),
        models=_parse_models(env.get("FOOD_CLASSIFIER_MODELS", "")),
        # Region of the bucket holding the checkpoints, which may differ from S3_REGION.
        model_region=env.get("FOOD_CLASSIFIER_MODEL_REGION", "us-east-1"),
        threshold=threshold,
        top_k=_get_int(env, "FOOD_CLASSIFIER_TOP_K", 5, minimum=1),
        cache_dir=env.get("FOOD_CLASSIFIER_CACHE_DIR", "/tmp/food_models"),
        num_threads=_get_int(env, "FOOD_CLASSIFIER_NUM_THREADS", 2, minimum=1),
        device=device,
    )
    if settings.enabled and not settings.models:
        raise ValueError("FOOD_CLASSIFIER_MODELS is required when FOOD_CLASSIFIER_ENABLED is true")
    return settings


def load_settings(env: Mapping[str, str] | None = None) -> AgentSettings:
    """Build ``AgentSettings`` from ``env`` (defaults to ``os.environ``)."""
    env = os.environ if env is None else env
    return AgentSettings(
        bedrock_model_id=env.get(
            "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        ),
        bedrock_region=env.get("BEDROCK_REGION", env.get("AWS_REGION", "us-east-1")),
        s3_bucket_name=env.get("S3_BUCKET_NAME", "sci-neutrasmart-project"),
        s3_region=env.get("S3_REGION", "ap-south-1"),
        max_image_size_bytes=_get_int(env, "MAX_IMAGE_SIZE_BYTES", 10 * 1024 * 1024, minimum=1),
        # 3.75 MB: Bedrock Converse inline image limit.
        bedrock_max_image_bytes=_get_int(env, "BEDROCK_MAX_IMAGE_BYTES", 3_932_160, minimum=1),
        max_images_per_request=_get_int(env, "MAX_IMAGES_PER_REQUEST", 5, minimum=1),
        analyze_max_tokens=_get_int(env, "ANALYZE_MAX_TOKENS", 4096, minimum=1),
        summary_max_tokens=_get_int(env, "SUMMARY_MAX_TOKENS", 2048, minimum=1),
        bedrock_connect_timeout_s=_get_float(env, "BEDROCK_CONNECT_TIMEOUT_S", 10.0),
        bedrock_read_timeout_s=_get_float(env, "BEDROCK_READ_TIMEOUT_S", 120.0),
        s3_connect_timeout_s=_get_float(env, "S3_CONNECT_TIMEOUT_S", 5.0),
        s3_read_timeout_s=_get_float(env, "S3_READ_TIMEOUT_S", 60.0),
        max_retries=_get_int(env, "AWS_MAX_RETRIES", 3),
        recognition_order=_get_recognition_order(env),
        llm_confidence_threshold=_get_unit_float(env, "LLM_CONFIDENCE_THRESHOLD", 0.60),
        classifier=_load_classifier_settings(env),
    )
