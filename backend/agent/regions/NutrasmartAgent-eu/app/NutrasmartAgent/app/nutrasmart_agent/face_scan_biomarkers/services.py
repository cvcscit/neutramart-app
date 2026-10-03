"""AWS client + lazy model cache for the face-scan biomarker feature.

Nothing here runs at import time: ``build_services`` is called on first use and the
result reused for the life of the container. Models are loaded lazily on first request
so chat/summary/analyze never pay for joblib/sklearn imports.
"""

from __future__ import annotations

import logging
import tempfile
from dataclasses import dataclass, field

import boto3

from .dsv.heart_rate import HRGate
from .settings import BiomarkerSettings

logger = logging.getLogger(__name__)


class ModelCache:
    """Lazily loads and caches the HR gate and BP/SpO2 regression bundles from S3.

    A load failure is logged and remembered so the agent doesn't retry a failing
    download on every request; callers treat a ``None`` result as "not deployed yet".
    """

    def __init__(self, settings: BiomarkerSettings, s3_client) -> None:
        self._settings = settings
        self._s3 = s3_client
        self._cache: dict = {}
        self._failed: set[str] = set()

    def load_hr_gate(self) -> HRGate | None:
        if "hr" in self._cache or "hr" in self._failed:
            return self._cache.get("hr")
        try:
            import joblib
            with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
                self._s3.download_file(self._settings.bucket, self._settings.hr_gate_key, tmp.name)
                d = joblib.load(tmp.name)
            self._cache["hr"] = HRGate(d["model"], d["threshold"], d["features"], d.get("info"))
            logger.info("Loaded HR gate from s3://%s/%s", self._settings.bucket, self._settings.hr_gate_key)
        except Exception as e:
            logger.warning("HR gate not available (s3://%s/%s): %s",
                            self._settings.bucket, self._settings.hr_gate_key, e)
            self._failed.add("hr")
        return self._cache.get("hr")

    def load_regression_bundle(self, name: str, key: str) -> dict | None:
        """Load a BP/SpO2 model bundle (dict with 'models', 'features', ...) as saved by
        scripts/glue/{bp,spo2}/train_glue.py."""
        if name in self._cache or name in self._failed:
            return self._cache.get(name)
        try:
            import joblib
            with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
                self._s3.download_file(self._settings.bucket, key, tmp.name)
                self._cache[name] = joblib.load(tmp.name)
            logger.info("Loaded %s model from s3://%s/%s", name, self._settings.bucket, key)
        except Exception as e:
            logger.warning("%s model not available (s3://%s/%s): %s", name, self._settings.bucket, key, e)
            self._failed.add(name)
        return self._cache.get(name)


@dataclass(frozen=True)
class BiomarkerServices:
    settings: BiomarkerSettings
    models: ModelCache = field(repr=False)


def build_services(settings: BiomarkerSettings) -> BiomarkerServices:
    s3 = boto3.client("s3", region_name=settings.region)
    return BiomarkerServices(settings=settings, models=ModelCache(settings, s3))
