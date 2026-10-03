"""Face-scan video -> heart rate, blood pressure, SpO2.

heart_rate is a validated wellness estimate (trained + tested gate, see README). bp and
spo2 are RESEARCH/EXPERIMENTAL -- always returned with "experimental": true and a
disclaimer, since neither has cleared real-data validation yet (see __init__.py). Callers
must display that disclaimer, not hide it, whenever these fields are shown.
"""

from __future__ import annotations

import logging
import os
import tempfile

from .dsv.extract import extract_video
from .dsv.features import compute_features
from .dsv.heart_rate import measure_hr
from .services import BiomarkerServices

logger = logging.getLogger(__name__)


def _predict_bundle(bundle: dict, feats: dict) -> dict:
    """Apply a trained BP/SpO2 bundle's per-target sklearn models to one feature dict."""
    import pandas as pd
    X = pd.DataFrame([{c: feats.get(c, float("nan")) for c in bundle["features"]}])
    return {t: round(float(m.predict(X)[0]), 1) for t, m in bundle["models"].items()}


def analyze_face_scan(key: str, *, user_s3, user_bucket: str, services: BiomarkerServices) -> dict:
    """Download the user's video from ``user_s3``/``user_bucket`` and run it through the
    HR gate and (if deployed) the BP/SpO2 models from ``services``."""
    settings = services.settings

    head = user_s3.head_object(Bucket=user_bucket, Key=key)
    if head["ContentLength"] > settings.max_video_size_bytes:
        raise ValueError(f"Video is too large (max {settings.max_video_size_bytes // (1024 * 1024)}MB).")

    suffix = os.path.splitext(key)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        user_s3.download_file(user_bucket, key, tmp.name)
        raw = extract_video(tmp.name)

    out: dict = {}

    gate = services.models.load_hr_gate()
    if gate is None:
        out["heart_rate"] = {
            "status": "unavailable",
            "reason": "Heart-rate model is not deployed yet. Please check back later.",
        }
    else:
        out["heart_rate"] = measure_hr(raw, gate=gate)

    # BP/SpO2 need the fuller feature set (rPPG+rBCG+quality), not just the HR window
    # features measure_hr() computes -- only run this if at least one model is present.
    bp_bundle = services.models.load_regression_bundle("bp", settings.bp_model_key)
    spo2_bundle = services.models.load_regression_bundle("spo2", settings.spo2_model_key)
    if bp_bundle or spo2_bundle:
        try:
            feats = compute_features(raw)
        except Exception as e:
            logger.warning("Feature computation failed for face scan: %s", e)
            feats = None

        for name, bundle, key_out in (("bp", bp_bundle, "bp"), ("spo2", spo2_bundle, "spo2")):
            if bundle is None:
                out[key_out] = {"status": "unavailable", "reason": f"{name.upper()} model is not deployed yet."}
                continue
            if feats is None:
                out[key_out] = {"status": "withheld", "reason": "signal quality too low for this scan."}
                continue
            pred = _predict_bundle(bundle, feats)
            result = {"status": "ok", "experimental": True,
                      "disclaimer": ("Research estimate only. Not validated for medical or "
                                     "consumer health decisions -- do not rely on this value.")}
            result.update(pred)
            out[key_out] = result
    else:
        out["bp"] = {"status": "unavailable", "reason": "BP model is not deployed yet."}
        out["spo2"] = {"status": "unavailable", "reason": "SpO2 model is not deployed yet."}

    return out
