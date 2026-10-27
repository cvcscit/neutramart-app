"""Env-driven settings for the face-scan biomarker feature.

Separate bucket/region from user data: this is the biomarker model-training pipeline's
output (see biomarker-processing S3 bucket + Glue jobs). The S3 timeouts and retries read
the same variables as ``food_scan/settings.py``, so one setting governs every S3 client.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class BiomarkerSettings:
    """Where the face-scan models live, the video size cap, and the model-bucket S3 timeouts."""

    bucket: str
    region: str
    hr_gate_key: str
    bp_model_key: str
    spo2_model_key: str
    max_video_size_bytes: int
    s3_connect_timeout_s: float
    s3_read_timeout_s: float
    max_retries: int


def load_settings(env: Mapping[str, str] | None = None) -> BiomarkerSettings:
    """Build ``BiomarkerSettings`` from ``env`` (defaults to ``os.environ``)."""
    env = os.environ if env is None else env
    return BiomarkerSettings(
        bucket=env.get("BIOMARKER_BUCKET", "biomarker-processing"),
        region=env.get("BIOMARKER_REGION", "us-east-1"),
        hr_gate_key=env.get("HR_GATE_KEY", "models/hr/latest/gate.joblib"),
        bp_model_key=env.get("BP_MODEL_KEY", "models/bp/latest/model.joblib"),
        spo2_model_key=env.get("SPO2_MODEL_KEY", "models/spo2/latest/model.joblib"),
        # 400MB, matches BP_measurement/app/server.py default
        max_video_size_bytes=int(env.get("MAX_VIDEO_SIZE_BYTES", 400 * 1024 * 1024)),
        s3_connect_timeout_s=float(env.get("S3_CONNECT_TIMEOUT_S", 5.0)),
        s3_read_timeout_s=float(env.get("S3_READ_TIMEOUT_S", 60.0)),
        max_retries=int(env.get("AWS_MAX_RETRIES", 3)),
    )
