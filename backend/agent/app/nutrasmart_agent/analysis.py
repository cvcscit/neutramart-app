"""Food-image analysis with two recognizers: a local classifier and the Bedrock vision LLM.

``FOOD_RECOGNITION_ORDER`` picks which recognizer runs first; the other is the fallback
when the first one's answer is not good enough.

* **Classifier** (``source = "classifier"``): every image is classified and the score is
  the *lowest* top-1 confidence across images. It is good enough when that reaches
  ``FOOD_CLASSIFIER_THRESHOLD``. Its dish names then go to a cheap text-only LLM call
  that estimates nutrition.
* **Vision LLM** (``source = "llm"``): the images go to the LLM, which self-reports a
  ``confidence`` in [0, 1]. It is good enough when that reaches
  ``LLM_CONFIDENCE_THRESHOLD``. A reply with no JSON, "No food detected", or a missing
  confidence scores 0.

When the first recognizer is not good enough, the fallback runs. If the fallback also
misses its threshold, the higher score wins (ties go to the first recognizer). With no
classifier configured, or if it fails, the vision LLM result is used.

Both paths return the same JSON shape plus a ``recognition`` block that records the
order, which path won, both scores and the classifier's predictions, so accuracy and
fallback rate can be audited from the saved scans.
"""

from __future__ import annotations

import io
import json
import logging
import math
import re
import time
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageOps, UnidentifiedImageError

from .prompts import ANALYZE_PROMPT, nutrition_from_labels_prompt
from .recognition import ClassificationResult, ClassifierError, FoodClassifier
from .settings import AgentSettings, RecognitionOrder

logger = logging.getLogger(__name__)

MICRONUTRIENT_KEYS = (
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_b12", "iron",
    "calcium", "potassium", "sodium", "zinc", "magnesium",
)
_TOP_LEVEL_KEYS = (
    "description", "weight", "calories", "protein", "carbs", "fat",
    "fiber", "sugar", "summary", "recommendation",
)
_JPEG_QUALITY = 85
NO_FOOD_DESCRIPTION = "No food detected"


class RecognitionSource(str, Enum):
    """Which path identified the food."""

    CLASSIFIER = "classifier"
    LLM = "llm"


@dataclass(frozen=True)
class ImageRef:
    """An uploaded image in the user's S3 bucket."""

    key: str
    content_type: str


@dataclass(frozen=True)
class Attempt:
    """One recognizer's nutrition analysis and how good it is (score in [0, 1])."""

    source: RecognitionSource
    analysis: dict
    score: float


@dataclass(frozen=True)
class Outcome:
    """The attempt returned to the caller plus what was tried along the way."""

    chosen: Attempt
    results: list[ClassificationResult] | None  # classifier predictions, if it ran
    llm_score: float | None  # vision LLM score, if it ran
    fallback_used: bool  # the first recognizer fell short and the fallback's answer won


def extract_json(text: str) -> dict:
    """Robustly pull a JSON object out of a model response.

    Handles clean JSON, ```json fenced blocks, and JSON wrapped in prose
    (some models, e.g. Nova, add commentary around the object).
    """
    text = (text or "").strip()
    # 1) code-fenced block
    m = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if m:
        text = m.group(1).strip()
    # 2) straight parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 3) first '{' … last '}'
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    raise ValueError("Failed to parse nutrition analysis from model response")


def decode_image(raw_bytes: bytes) -> Image.Image:
    """Decode bytes into an EXIF-oriented RGB image (fixes format mismatches / rotation)."""
    try:
        with Image.open(io.BytesIO(raw_bytes)) as img:
            return ImageOps.exif_transpose(img).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("An uploaded file is not a readable image.") from exc


def to_jpeg_bytes(image: Image.Image) -> bytes:
    """Re-encode an RGB image as JPEG for the Bedrock Converse image block."""
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=_JPEG_QUALITY)
    return out.getvalue()


def load_images(refs: list[ImageRef], s3, settings: AgentSettings) -> list[Image.Image]:
    """Validate count/size and fetch + decode each image from the user's bucket."""
    if not refs:
        raise ValueError("At least one image is required.")
    if len(refs) > settings.max_images_per_request:
        raise ValueError(f"Maximum {settings.max_images_per_request} images per request.")

    images = []
    for ref in refs:
        head = s3.head_object(Bucket=settings.s3_bucket_name, Key=ref.key)
        if head["ContentLength"] > settings.max_image_size_bytes:
            max_mb = settings.max_image_size_bytes // (1024 * 1024)
            raise ValueError(f"Image {ref.key} is too large (max {max_mb}MB)")
        raw_bytes = s3.get_object(Bucket=settings.s3_bucket_name, Key=ref.key)["Body"].read()
        images.append(decode_image(raw_bytes))
    return images


def _classify_all(classifier: FoodClassifier, images: list[Image.Image]) -> list[ClassificationResult] | None:
    """Classify every image; ``None`` if the classifier fails (caller falls back to the LLM)."""
    try:
        return [classifier.classify(image) for image in images]
    except ClassifierError:
        logger.exception("Food classifier failed; using the vision LLM result")
        return None


def _classifier_score(results: list[ClassificationResult]) -> float:
    """The least confident image decides: every image must be recognized."""
    return min(result.top.confidence for result in results)


def _llm_score(analysis: dict) -> float:
    """The LLM's self-reported confidence, clamped to [0, 1]; 0 for no food or no score."""
    description = analysis.get("description")
    if isinstance(description, str) and description.strip().lower() == NO_FOOD_DESCRIPTION.lower():
        return 0.0
    try:
        confidence = float(analysis.get("confidence"))
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(confidence):
        return 0.0
    return min(max(confidence, 0.0), 1.0)


def _converse(bedrock, settings: AgentSettings, content: list[dict]) -> tuple[str, str | None]:
    resp = bedrock.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": settings.analyze_max_tokens},
    )
    return resp["output"]["message"]["content"][0]["text"], resp.get("stopReason")


def _parse_or_graceful(text: str, stop_reason: str | None) -> dict:
    try:
        return extract_json(text)
    except ValueError:
        # Model replied in prose with no JSON (blurry/ambiguous/non-food image, or a
        # refusal). Degrade gracefully to a valid 200 result instead of a 502 so the
        # UI shows a friendly "couldn't read this photo" card.
        logger.warning("No JSON from model (stopReason=%s); returning graceful result. head=%r",
                       stop_reason, (text or "")[:160])
        return {
            "description": NO_FOOD_DESCRIPTION,
            "recommendation": "I couldn't read this photo clearly — try a well-lit shot with the food filling the frame.",
        }


def _backfill(analysis: dict) -> dict:
    """Ensure every key the UI and summaries expect is present."""
    for key in _TOP_LEVEL_KEYS:
        analysis.setdefault(key, "N/A")
    if not isinstance(analysis.get("micronutrients"), dict):
        analysis["micronutrients"] = {}
    for key in MICRONUTRIENT_KEYS:
        analysis["micronutrients"].setdefault(key, "N/A")
    return analysis


def _analyze_with_labels(results: list[ClassificationResult], bedrock, settings: AgentSettings) -> dict:
    dish_names = list(dict.fromkeys(result.top.display_name for result in results))
    text, stop_reason = _converse(bedrock, settings, [{"text": nutrition_from_labels_prompt(dish_names)}])
    return _parse_or_graceful(text, stop_reason)


def _analyze_with_vision(images: list[Image.Image], bedrock, settings: AgentSettings) -> dict:
    blocks = []
    for image in images:
        jpeg_bytes = to_jpeg_bytes(image)
        if len(jpeg_bytes) > settings.bedrock_max_image_bytes:
            max_mb = settings.bedrock_max_image_bytes / (1024 * 1024)
            raise ValueError(f"An image is too large for analysis after processing (max {max_mb:.2f} MB).")
        blocks.append({"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes}}})
    text, stop_reason = _converse(bedrock, settings, blocks + [{"text": ANALYZE_PROMPT}])
    return _parse_or_graceful(text, stop_reason)


def _vision_attempt(images: list[Image.Image], bedrock, settings: AgentSettings) -> Attempt:
    analysis = _analyze_with_vision(images, bedrock, settings)
    score = _llm_score(analysis)
    analysis["confidence"] = score
    return Attempt(RecognitionSource.LLM, analysis, score)


def _labels_attempt(
    results: list[ClassificationResult], score: float, bedrock, settings: AgentSettings
) -> Attempt:
    analysis = _analyze_with_labels(results, bedrock, settings)
    analysis["confidence"] = score
    return Attempt(RecognitionSource.CLASSIFIER, analysis, score)


def _run_classifier_first(
    images: list[Image.Image], bedrock, classifier: FoodClassifier | None, settings: AgentSettings
) -> Outcome:
    results = _classify_all(classifier, images) if classifier is not None else None
    if results is None:
        vision = _vision_attempt(images, bedrock, settings)
        return Outcome(vision, None, vision.score, fallback_used=classifier is not None)

    classifier_score = _classifier_score(results)
    if classifier_score >= settings.classifier.threshold:
        return Outcome(_labels_attempt(results, classifier_score, bedrock, settings), results, None, False)

    vision = _vision_attempt(images, bedrock, settings)
    if vision.score >= settings.llm_confidence_threshold or vision.score > classifier_score:
        return Outcome(vision, results, vision.score, fallback_used=True)
    labels = _labels_attempt(results, classifier_score, bedrock, settings)
    return Outcome(labels, results, vision.score, fallback_used=False)


def _run_llm_first(
    images: list[Image.Image], bedrock, classifier: FoodClassifier | None, settings: AgentSettings
) -> Outcome:
    vision = _vision_attempt(images, bedrock, settings)
    if vision.score >= settings.llm_confidence_threshold or classifier is None:
        return Outcome(vision, None, vision.score, fallback_used=False)

    results = _classify_all(classifier, images)
    if results is None:
        return Outcome(vision, None, vision.score, fallback_used=False)

    classifier_score = _classifier_score(results)
    if classifier_score >= settings.classifier.threshold or classifier_score > vision.score:
        labels = _labels_attempt(results, classifier_score, bedrock, settings)
        return Outcome(labels, results, vision.score, fallback_used=True)
    return Outcome(vision, results, vision.score, fallback_used=False)


_RUNNERS = {
    RecognitionOrder.CLASSIFIER_FIRST: _run_classifier_first,
    RecognitionOrder.LLM_FIRST: _run_llm_first,
}


def _recognition_block(outcome: Outcome, settings: AgentSettings) -> dict:
    return {
        "source": outcome.chosen.source.value,
        "order": settings.recognition_order.value,
        "threshold": settings.classifier.threshold,
        "llm_threshold": settings.llm_confidence_threshold,
        "llm_confidence": outcome.llm_score,
        "fallback_used": outcome.fallback_used,
        "predictions": [
            [prediction.to_dict() for prediction in result.predictions]
            for result in outcome.results or []
        ],
    }


def analyze_food_images(
    refs: list[ImageRef],
    *,
    s3,
    bedrock,
    classifier: FoodClassifier | None,
    settings: AgentSettings,
) -> dict:
    """Identify the food in ``refs`` and return the nutrition analysis JSON."""
    started = time.perf_counter()
    images = load_images(refs, s3, settings)

    outcome = _RUNNERS[settings.recognition_order](images, bedrock, classifier, settings)
    analysis = _backfill(outcome.chosen.analysis)
    analysis["recognition"] = _recognition_block(outcome, settings)

    logger.info("food_analysis %s", json.dumps({
        "source": outcome.chosen.source.value,
        "order": settings.recognition_order.value,
        "fallback_used": outcome.fallback_used,
        "images": len(images),
        "top": [
            {"food_id": r.top.food_id, "confidence": round(r.top.confidence, 4)}
            for r in outcome.results or []
        ],
        "llm_confidence": outcome.llm_score,
        "threshold": settings.classifier.threshold,
        "llm_threshold": settings.llm_confidence_threshold,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }))
    return analysis
