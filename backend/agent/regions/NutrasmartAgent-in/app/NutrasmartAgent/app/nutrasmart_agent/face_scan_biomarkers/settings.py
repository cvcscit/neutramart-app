"""Env-driven settings for the face-scan biomarker feature.

Separate bucket/region from user data: this is the biomarker model-training pipeline's
output (see biomarker-processing S3 bucket + Glue jobs).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BiomarkerSettings:
    bucket: str
    region: str
    hr_gate_key: str
    bp_model_key: str
    spo2_model_key: str
    max_video_size_bytes: int


def load_settings() -> BiomarkerSettings:
    return BiomarkerSettings(
        bucket=os.environ.get("BIOMARKER_BUCKET", "biomarker-processing"),
        region=os.environ.get("BIOMARKER_REGION", "us-east-1"),
        hr_gate_key=os.environ.get("HR_GATE_KEY", "models/hr/latest/gate.joblib"),
        bp_model_key=os.environ.get("BP_MODEL_KEY", "models/bp/latest/model.joblib"),
        spo2_model_key=os.environ.get("SPO2_MODEL_KEY", "models/spo2/latest/model.joblib"),
        # 400MB, matches BP_measurement/app/server.py default
        max_video_size_bytes=int(os.environ.get("MAX_VIDEO_SIZE_BYTES", 400 * 1024 * 1024)),
    )
