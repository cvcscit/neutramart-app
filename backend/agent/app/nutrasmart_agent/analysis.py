"""Food-image analysis: local classifier first, Bedrock vision LLM as fallback.

Flow for one ``analyze`` request:

1. Fetch the images from S3 and decode them once (EXIF-oriented RGB).
2. If a classifier is configured, classify every image. When *every* image's top
   prediction reaches the confidence threshold, the dish names are trusted and a cheap
   text-only LLM call estimates nutrition (``source = "classifier"``).
3. Otherwise, or if the classifier fails, send the images to the vision LLM exactly as
   before (``source = "llm"``).

Both paths return the same JSON shape plus a ``recognition`` block that records which
path ran and the classifier's predictions, so accuracy and fallback rate can be audited
from the saved scans.
"""

from __future__ import annotations

import io
import json
import logging
import re
import time
from dataclasses import dataclass
from enum import Enum

from PIL import Image, ImageOps, UnidentifiedImageError

from .prompts import ANALYZE_PROMPT, nutrition_from_labels_prompt
from .recognition import ClassificationResult, ClassifierError, FoodClassifier
from .settings import AgentSettings

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


class RecognitionSource(str, Enum):
    """Which path identified the food."""

    CLASSIFIER = "classifier"
    LLM = "llm"


@dataclass(frozen=True)
class ImageRef:
    """An uploaded image in the user's S3 bucket."""

    key: str
    content_type: str


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
        logger.exception("Food classifier failed; falling back to vision LLM")
        return None


def _all_confident(results: list[ClassificationResult], threshold: float) -> bool:
    return all(result.top.confidence >= threshold for result in results)


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
            "description": "No food detected",
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


def _recognition_block(
    source: RecognitionSource, threshold: float, results: list[ClassificationResult] | None
) -> dict:
    return {
        "source": source.value,
        "threshold": threshold,
        "predictions": [
            [prediction.to_dict() for prediction in result.predictions] for result in results or []
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
    threshold = settings.classifier.threshold

    results = _classify_all(classifier, images) if classifier is not None else None
    if results is not None and _all_confident(results, threshold):
        source = RecognitionSource.CLASSIFIER
        analysis = _analyze_with_labels(results, bedrock, settings)
    else:
        source = RecognitionSource.LLM
        analysis = _analyze_with_vision(images, bedrock, settings)

    analysis = _backfill(analysis)
    analysis["recognition"] = _recognition_block(source, threshold, results)

    logger.info("food_analysis %s", json.dumps({
        "source": source.value,
        "images": len(images),
        "top": [
            {"food_id": r.top.food_id, "confidence": round(r.top.confidence, 4)}
            for r in results or []
        ],
        "threshold": threshold,
        "latency_ms": round((time.perf_counter() - started) * 1000),
    }))
    return analysis
