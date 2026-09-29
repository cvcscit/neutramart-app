"""Shared test doubles for the agent: in-memory S3, recording Bedrock, scripted classifier."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from app.nutrasmart_agent.recognition import ClassificationResult, ClassifierError, FoodPrediction
from app.nutrasmart_agent.settings import load_settings

BUCKET = "test-bucket"


def jpeg_bytes(color=(200, 120, 40), size=(64, 48)) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", size, color).save(out, format="JPEG")
    return out.getvalue()


class FakeS3:
    """Minimal S3 double: head_object/get_object over a dict of key -> bytes."""

    def __init__(self, objects: dict[str, bytes]):
        self.objects = objects

    def head_object(self, Bucket, Key):
        return {"ContentLength": len(self.objects[Key]), "ETag": '"etag-1"'}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Key])}


class FakeBedrock:
    """Records converse() calls and replies with a fixed analysis JSON."""

    def __init__(self, reply: dict | str | None = None):
        self.calls: list[dict] = []
        self.reply = reply if reply is not None else {"description": "Stub meal", "calories": "300 kcal"}

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        text = self.reply if isinstance(self.reply, str) else json.dumps(self.reply)
        return {"output": {"message": {"content": [{"text": text}]}}, "stopReason": "end_turn"}

    @property
    def last_content(self) -> list[dict]:
        return self.calls[-1]["messages"][0]["content"]


class ScriptedClassifier:
    """Returns one predetermined (food_id, confidence) per call, in order."""

    def __init__(self, outputs: list[tuple[str, float]] | None = None, error: bool = False):
        self.outputs = list(outputs or [])
        self.error = error
        self.calls = 0

    def classify(self, image):
        self.calls += 1
        if self.error:
            raise ClassifierError("boom")
        food_id, confidence = self.outputs.pop(0)
        return ClassificationResult(
            predictions=(
                FoodPrediction(food_id, food_id.replace("_", " ").title(), confidence),
                FoodPrediction("other_dish", "Other Dish", 1.0 - confidence),
            )
        )


@pytest.fixture
def settings():
    return load_settings({"S3_BUCKET_NAME": BUCKET, "FOOD_CLASSIFIER_THRESHOLD": "0.6"})
