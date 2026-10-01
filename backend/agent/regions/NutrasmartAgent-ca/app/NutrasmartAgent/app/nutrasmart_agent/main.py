"""
NutraSmart AgentCore Runtime — a Strands agent that owns all of NutraSmart's LLM logic.

One runtime, three actions routed by the ``action`` field of the invocation payload:

    {"action": "chat",    "user_id": ..., "message": ..., "history": [...]}  -> {"reply": str}
    {"action": "summary", "user_id": ...}                                    -> {"status": "ok"}
    {"action": "analyze", "user_id": ..., "images": [{"key", "content_type"}]} -> analysis JSON
    {"action": "face_scan", "user_id": ..., "key": "users/.../scans/<id>.mp4"} -> {"heart_rate": {...}}

Identity is never taken from the client: the FastAPI edge validates the Google ID token,
derives ``user_id`` and passes it here. This agent trusts ``user_id`` from the payload only.

Data model (S3 bucket ``sci-neutrasmart-project`` in ap-south-1):
    users/{user_id}/scans/{ts}.json      food-analysis records (the knowledge base)
    users/{user_id}/weekly_summary.txt   generated eating summary
    users/{user_id}/health_profile.json  optional health profile
"""

import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timedelta, timezone

import boto3
from PIL import Image

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

from app.dsv.extract import extract_video
from app.dsv.heart_rate import measure_hr, HRGate
from app.dsv.features import compute_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nutrasmart_agent")

# ─── Config (env-driven, matching the existing agentcore_experiments pattern) ────────
BEDROCK_MODEL_ID = os.environ.get(
    "BEDROCK_MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0"
)
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", os.environ.get("AWS_REGION", "us-east-1"))
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "sci-neutrasmart-project")
S3_REGION = os.environ.get("S3_REGION", "ap-south-1")  # bucket lives in Mumbai

# S3 client targets the bucket's region; Bedrock uses the runtime region.
s3 = boto3.client("s3", region_name=S3_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

app = BedrockAgentCoreApp()

# ─── Face scan (heart rate, blood pressure, SpO2) ──────────────────────────────────────
# Separate bucket/region from user data: this is the biomarker model-training pipeline's
# output (see biomarker-processing S3 bucket + Glue jobs).
#
# IMPORTANT STATUS NOTE: only the heart-rate gate has been validated against a held-out
# test set with meaningful accuracy (see BP_measurement/README.md, "Results"). The BP and
# SpO2 models trained by this pipeline so far are either unvalidated (SpO2 -- never run
# against real ground truth) or shown in the source repo's own benchmarks to not beat a
# naive age/sex baseline (BP, on the MCD-rPPG dataset). They are wired up and returned
# here because the product decision was to surface all three, but every bp/spo2 response
# below carries an explicit "experimental" flag the UI must not hide from the user.
BIOMARKER_BUCKET = os.environ.get("BIOMARKER_BUCKET", "biomarker-processing")
BIOMARKER_REGION = os.environ.get("BIOMARKER_REGION", "us-east-1")
HR_GATE_KEY = os.environ.get("HR_GATE_KEY", "models/hr/latest/gate.joblib")
BP_MODEL_KEY = os.environ.get("BP_MODEL_KEY", "models/bp/latest/model.joblib")
SPO2_MODEL_KEY = os.environ.get("SPO2_MODEL_KEY", "models/spo2/latest/model.joblib")
MAX_VIDEO_SIZE_BYTES = 400 * 1024 * 1024  # 400MB, matches BP_measurement/app/server.py default

biomarker_s3 = boto3.client("s3", region_name=BIOMARKER_REGION)
_model_cache = {}
_model_load_failed = set()


def _load_hr_gate():
    """Lazily load and cache the trained HR reliability gate from S3.

    Returns None (and logs) if no model has been promoted to models/hr/latest/ yet --
    callers must treat that as "feature not yet available", never fall back to an
    untrained/ungated heart rate reading.
    """
    if "hr" in _model_cache or "hr" in _model_load_failed:
        return _model_cache.get("hr")
    try:
        import joblib
        with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
            biomarker_s3.download_file(BIOMARKER_BUCKET, HR_GATE_KEY, tmp.name)
            d = joblib.load(tmp.name)
        _model_cache["hr"] = HRGate(d["model"], d["threshold"], d["features"], d.get("info"))
        logger.info("Loaded HR gate from s3://%s/%s", BIOMARKER_BUCKET, HR_GATE_KEY)
    except Exception as e:
        logger.warning("HR gate not available (s3://%s/%s): %s", BIOMARKER_BUCKET, HR_GATE_KEY, e)
        _model_load_failed.add("hr")
    return _model_cache.get("hr")


def _load_regression_bundle(name, key):
    """Lazily load and cache a BP/SpO2 model bundle (dict with 'models', 'features', ...)
    as saved by scripts/glue/{bp,spo2}/train_glue.py. Returns None if not yet promoted."""
    if name in _model_cache or name in _model_load_failed:
        return _model_cache.get(name)
    try:
        import joblib
        with tempfile.NamedTemporaryFile(suffix=".joblib") as tmp:
            biomarker_s3.download_file(BIOMARKER_BUCKET, key, tmp.name)
            _model_cache[name] = joblib.load(tmp.name)
        logger.info("Loaded %s model from s3://%s/%s", name, BIOMARKER_BUCKET, key)
    except Exception as e:
        logger.warning("%s model not available (s3://%s/%s): %s", name, BIOMARKER_BUCKET, key, e)
        _model_load_failed.add(name)
    return _model_cache.get(name)


def _predict_bundle(bundle, feats):
    """Apply a trained BP/SpO2 bundle's per-target sklearn models to one feature dict."""
    import pandas as pd
    X = pd.DataFrame([{c: feats.get(c, float("nan")) for c in bundle["features"]}])
    return {t: round(float(m.predict(X)[0]), 1) for t, m in bundle["models"].items()}

# Image limits (moved here from the FastAPI edge)
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB raw
BEDROCK_MAX_IMAGE_BYTES = 3_932_160  # 3.75 MB Bedrock Converse inline limit
MAX_IMAGES_PER_REQUEST = 5

MICRONUTRIENT_KEYS = (
    "vitamin_a", "vitamin_c", "vitamin_d", "vitamin_b12", "iron",
    "calcium", "potassium", "sodium", "zinc", "magnesium",
)

# ─── Prompts (ported verbatim from analyze.py / chat.py) ─────────────────────────────
ANALYZE_PROMPT = (
    "You are a nutrition analysis assistant. Analyze the food in the provided image(s) and "
    "return ONLY a JSON object with these exact keys, no other text:\n"
    "{\n"
    '  "description": "Brief description of the food item(s) visible",\n'
    '  "weight": "Estimated total weight/portion size (e.g. 250g)",\n'
    '  "calories": "Estimated total calories (e.g. 350 kcal)",\n'
    '  "protein": "Estimated total protein (e.g. 25g)",\n'
    '  "carbs": "Estimated total carbohydrates (e.g. 40g)",\n'
    '  "fat": "Estimated total fat (e.g. 15g)",\n'
    '  "fiber": "Estimated total fiber (e.g. 5g)",\n'
    '  "sugar": "Estimated total sugar (e.g. 10g)",\n'
    '  "dishes": [\n'
    '    {\n'
    '      "name": "Dish name (e.g. Masala Chai)",\n'
    '      "servingSize": "Serving description (e.g. 1 cup)",\n'
    '      "servingWeightGrams": 250,\n'
    '      "calories": 98,\n'
    '      "protein": 3,\n'
    '      "carbs": 12,\n'
    '      "fat": 4,\n'
    '      "fiber": 0,\n'
    '      "sugar": 8\n'
    '    }\n'
    '  ],\n'
    '  "objects": ["List of all ingredients and objects visible in the image, e.g. black tea, milk, cardamom, cinnamon, porcelain cup, spoon"],\n'
    '  "micronutrients": {\n'
    '    "vitamin_a": "Estimated Vitamin A (e.g. 120 mcg)",\n'
    '    "vitamin_c": "Estimated Vitamin C (e.g. 15 mg)",\n'
    '    "vitamin_d": "Estimated Vitamin D (e.g. 2 mcg)",\n'
    '    "vitamin_b12": "Estimated Vitamin B12 (e.g. 0.5 mcg)",\n'
    '    "iron": "Estimated Iron (e.g. 3 mg)",\n'
    '    "calcium": "Estimated Calcium (e.g. 80 mg)",\n'
    '    "potassium": "Estimated Potassium (e.g. 200 mg)",\n'
    '    "sodium": "Estimated Sodium (e.g. 400 mg)",\n'
    '    "zinc": "Estimated Zinc (e.g. 2 mg)",\n'
    '    "magnesium": "Estimated Magnesium (e.g. 30 mg)"\n'
    '  },\n'
    '  "summary": "One-sentence nutritional summary",\n'
    '  "recommendation": "Brief dietary recommendation"\n'
    "}\n"
    "IMPORTANT: Identify EACH separate dish/food item in the image and list them individually in the dishes array "
    "with per-dish nutrition. The top-level calories/protein/carbs/fat/fiber/sugar should be the TOTAL across all dishes.\n"
    "If the image does not contain food, set description to 'No food detected' "
    "and set all nutritional values to 'N/A'."
)

WEEKLY_SUMMARY_PROMPT = (
    "You are a nutrition and dietary advisor. Below are the food analysis records "
    "from the last 2 months for a user. Each record includes the food description, "
    "calories, protein, carbs, fat, fiber, sugar, and micronutrients (vitamins and "
    "minerals).\n\n"
    "{health_profile_section}"
    "Analyze the eating patterns and provide a comprehensive 2-month summary in "
    "plain text format with these sections:\n\n"
    "1. EATING HABITS OVERVIEW - Summarize what the user has been eating, meal "
    "patterns, and dietary tendencies.\n\n"
    "2. NUTRITIONAL ANALYSIS - Average daily calorie intake, macronutrient "
    "balance (protein/carbs/fat ratio), fiber and sugar trends.\n\n"
    "3. POSITIVE HABITS - What the user is doing well nutritionally.\n\n"
    "4. AREAS OF CONCERN - Any nutritional gaps, excess intake, or unhealthy "
    "patterns.\n\n"
    "5. MINERAL & VITAMIN DEFICIENCIES - Carefully analyze the micronutrient data "
    "across all records and identify any minerals or vitamins the user appears to "
    "be deficient in (e.g., iron, calcium, magnesium, zinc, potassium, vitamin D, "
    "vitamin B12, vitamin C). Explain which foods in their diet are (or are not) "
    "providing these nutrients.\n\n"
    "6. SUPPLEMENT RECOMMENDATIONS - Based on the identified deficiencies, recommend "
    "specific supplements the user could consider (name the nutrient, a typical "
    "form/dosage range, and the reason). Also suggest natural food sources to "
    "correct each deficiency. Add a note to consult a doctor before starting any "
    "new supplement.\n\n"
    "7. RECOMMENDATIONS - Specific, actionable dietary suggestions to improve "
    "nutrition.\n\n"
    "8. RESTRICTIONS & WARNINGS - Any foods or patterns to avoid based on the "
    "observed diet (e.g., too much sugar, sodium, processed food).\n\n"
    "Keep the tone friendly but professional. Be specific with numbers where "
    "possible.\n\n"
    "Here are the food records:\n\n"
)

CHAT_SYSTEM_PROMPT = (
    "You are NutraSmart AI, a friendly and knowledgeable nutrition assistant. "
    "You have access to the user's food analysis history and eating summary through "
    "your tools. Call the tools to look up the user's data before answering questions "
    "about their diet, nutrition, eating habits, deficiencies, and recommendations.\n\n"
    "Rules:\n"
    "- Be conversational, friendly, and concise.\n"
    "- Reference specific foods and numbers from their data when relevant.\n"
    "- When relevant, analyze the user's micronutrient intake for any mineral or "
    "vitamin deficiencies (e.g., iron, calcium, magnesium, zinc, potassium, "
    "vitamin D, B12, C) and recommend supplements and natural food sources to "
    "correct them.\n"
    "- If asked about something not in the data, say so honestly.\n"
    "- Keep responses short (2-4 sentences) unless the user asks for detail.\n"
    "- Do not provide medical diagnoses. Suggest consulting a doctor before "
    "starting any new supplement or for health concerns.\n\n"
)


# ─── Helpers ─────────────────────────────────────────────────────────────────────────
def _extract_json(text: str) -> dict:
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


def _normalize_image(raw_bytes: bytes) -> bytes:
    """Open with Pillow and re-encode as JPEG (fixes HEIC / format mismatches / corruption)."""
    img = Image.open(io.BytesIO(raw_bytes))
    img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85)
    return out.getvalue()


# ─── Tools ───────────────────────────────────────────────────────────────────────────
@tool
def get_recent_scans(user_id: str, days: int = 60) -> str:
    """Fetch the user's food-analysis scan records from the last N days (default 60).

    Returns a formatted text block of dated records with calories, macros and
    micronutrients — the knowledge base for summaries and chat.
    """
    prefix = f"users/{user_id}/scans/"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)
    if "Contents" not in response:
        return "No food scans found for this user."

    scans = []
    for obj in response["Contents"]:
        filename = obj["Key"].split("/")[-1].replace(".json", "")
        try:
            scan_time = datetime.strptime(filename, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        if scan_time >= cutoff:
            scan_data = s3.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])
            scans.append(json.loads(scan_data["Body"].read()))

    if not scans:
        return f"No food scans in the last {days} days for this user."

    records_text = ""
    for scan in sorted(scans, key=lambda x: x.get("timestamp", "")):
        micro = scan.get("micronutrients") or {}
        micro_text = ", ".join(f"{k}: {v}" for k, v in micro.items() if v and v != "N/A")
        records_text += (
            f"- Date: {scan.get('timestamp', 'unknown')}\n"
            f"  Food: {scan.get('description', 'N/A')}\n"
            f"  Calories: {scan.get('calories', 'N/A')}, "
            f"Protein: {scan.get('protein', 'N/A')}, "
            f"Carbs: {scan.get('carbs', 'N/A')}, "
            f"Fat: {scan.get('fat', 'N/A')}, "
            f"Fiber: {scan.get('fiber', 'N/A')}, "
            f"Sugar: {scan.get('sugar', 'N/A')}\n"
            f"  Micronutrients: {micro_text or 'N/A'}\n\n"
        )
    return records_text


@tool
def get_health_profile(user_id: str) -> str:
    """Fetch the user's health profile (age, conditions, allergies, goals) if it exists."""
    try:
        response = s3.get_object(
            Bucket=S3_BUCKET_NAME, Key=f"users/{user_id}/health_profile.json"
        )
        profile = json.loads(response["Body"].read())
    except Exception:
        return "No health profile on file for this user."
    lines = "\n".join(f"  {k}: {v}" for k, v in profile.items())
    return f"The user has the following health profile:\n{lines}"


@tool
def get_eating_summary(user_id: str) -> str:
    """Fetch the user's most recently generated 2-month eating summary, if any."""
    try:
        response = s3.get_object(
            Bucket=S3_BUCKET_NAME, Key=f"users/{user_id}/weekly_summary.txt"
        )
        return response["Body"].read().decode("utf-8")
    except Exception:
        return "No eating summary has been generated yet."


def _save_summary(user_id: str, text: str) -> None:
    s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=f"users/{user_id}/weekly_summary.txt",
        Body=text,
        ContentType="text/plain",
    )


def _save_scan(user_id: str, analysis: dict, image_keys: list) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_key = f"users/{user_id}/scans/{timestamp}.json"
    s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=scan_key,
        Body=json.dumps({**analysis, "timestamp": timestamp, "image_keys": image_keys}),
        ContentType="application/json",
    )


def _analyze_food_images(images: list) -> dict:
    """Fetch images from S3, normalize, run the vision model, return the analysis JSON.

    ``images`` is a list of {"key", "content_type"} dicts.
    """
    if not images:
        raise ValueError("At least one image is required.")
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise ValueError(f"Maximum {MAX_IMAGES_PER_REQUEST} images per request.")

    image_content_blocks = []
    for item in images:
        key = item["key"]
        head = s3.head_object(Bucket=S3_BUCKET_NAME, Key=key)
        if head["ContentLength"] > MAX_IMAGE_SIZE_BYTES:
            raise ValueError(f"Image {key} is too large (max 10MB)")
        raw_bytes = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)["Body"].read()
        jpeg_bytes = _normalize_image(raw_bytes)
        if len(jpeg_bytes) > BEDROCK_MAX_IMAGE_BYTES:
            raise ValueError("An image is too large for analysis after processing (max 3.75 MB).")
        image_content_blocks.append(
            {"image": {"format": "jpeg", "source": {"bytes": jpeg_bytes}}}
        )

    content = image_content_blocks + [{"text": ANALYZE_PROMPT}]
    resp = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"maxTokens": 4096},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    try:
        analysis = _extract_json(text)
    except ValueError:
        # Model replied in prose with no JSON (blurry/ambiguous/non-food image, or a
        # refusal). Degrade gracefully to a valid 200 result instead of a 502 so the
        # UI shows a friendly "couldn't read this photo" card.
        logger.warning("No JSON from model (stopReason=%s); returning graceful result. head=%r",
                       resp.get("stopReason"), (text or "")[:160])
        analysis = {
            "description": "No food detected",
            "recommendation": "I couldn't read this photo clearly — try a well-lit shot with the food filling the frame.",
        }

    # Backfill expected keys (mirrors the previous FastAPI behavior)
    for k in ("description", "weight", "calories", "protein", "carbs", "fat",
              "fiber", "sugar", "summary", "recommendation"):
        analysis.setdefault(k, "N/A")
    if not isinstance(analysis.get("micronutrients"), dict):
        analysis["micronutrients"] = {}
    for mk in MICRONUTRIENT_KEYS:
        analysis["micronutrients"].setdefault(mk, "N/A")
    return analysis


# ─── Action handlers ─────────────────────────────────────────────────────────────────
def _model() -> BedrockModel:
    return BedrockModel(model_id=BEDROCK_MODEL_ID, region_name=BEDROCK_REGION)


def _handle_chat(payload: dict) -> dict:
    user_id = payload["user_id"]
    message = payload.get("message", "")
    history = payload.get("history") or []

    # Bind user_id into the tools the agent can call, so it can only read this user's data.
    prior = [
        {"role": m["role"], "content": [{"text": m["content"]}]}
        for m in history
        if m.get("role") in ("user", "assistant") and m.get("content")
    ]
    agent = Agent(
        model=_model(),
        system_prompt=CHAT_SYSTEM_PROMPT + f"\n(The current user_id is: {user_id})\n",
        tools=[get_recent_scans, get_health_profile, get_eating_summary],
        messages=prior,
    )
    result = agent(message)
    return {"reply": str(result)}


def _handle_summary(payload: dict) -> dict:
    user_id = payload["user_id"]
    records = get_recent_scans(user_id=user_id, days=60)
    if records.startswith("No food scans"):
        raise ValueError(records)
    profile = get_health_profile(user_id=user_id)
    health_section = "" if profile.startswith("No health profile") else profile + "\n\n"

    full_prompt = WEEKLY_SUMMARY_PROMPT.format(health_profile_section=health_section) + records
    resp = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": full_prompt}]}],
        inferenceConfig={"maxTokens": 2048},
    )
    summary_text = resp["output"]["message"]["content"][0]["text"]
    _save_summary(user_id, summary_text)
    logger.info("Summary saved for %s", user_id)
    return {"status": "ok"}


def _handle_analyze(payload: dict) -> dict:
    user_id = payload["user_id"]
    images = payload.get("images") or []
    analysis = _analyze_food_images(images)
    try:
        _save_scan(user_id, analysis, [img["key"] for img in images])
    except Exception as e:  # don't fail the request if the scan save fails
        logger.warning("Scan save failed for %s: %s", user_id, e)
    return analysis


def _handle_face_scan(payload: dict) -> dict:
    """Face-scan video -> heart rate, blood pressure, SpO2.

    heart_rate is a validated wellness estimate (trained + tested gate, see README).
    bp and spo2 are RESEARCH/EXPERIMENTAL -- always returned with "experimental": true
    and a disclaimer, since neither has cleared real-data validation yet (see the
    BIOMARKER_BUCKET comment above). The frontend must display that disclaimer, not
    hide it, whenever these fields are shown.
    """
    key = payload.get("key")
    if not key:
        raise ValueError("Missing video key in payload.")

    head = s3.head_object(Bucket=S3_BUCKET_NAME, Key=key)
    if head["ContentLength"] > MAX_VIDEO_SIZE_BYTES:
        raise ValueError("Video is too large (max 400MB).")

    suffix = os.path.splitext(key)[1] or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        s3.download_file(S3_BUCKET_NAME, key, tmp.name)
        raw = extract_video(tmp.name)

    out = {}

    gate = _load_hr_gate()
    if gate is None:
        out["heart_rate"] = {
            "status": "unavailable",
            "reason": "Heart-rate model is not deployed yet. Please check back later.",
        }
    else:
        out["heart_rate"] = measure_hr(raw, gate=gate)

    # BP/SpO2 need the fuller feature set (rPPG+rBCG+quality), not just the HR window
    # features measure_hr() computes -- only run this if at least one model is present.
    bp_bundle = _load_regression_bundle("bp", BP_MODEL_KEY)
    spo2_bundle = _load_regression_bundle("spo2", SPO2_MODEL_KEY)
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


_HANDLERS = {
    "chat": _handle_chat,
    "summary": _handle_summary,
    "analyze": _handle_analyze,
    "face_scan": _handle_face_scan,
}


@app.entrypoint
def invoke(payload: dict) -> dict:
    """AgentCore Runtime entrypoint. Routes on payload['action']."""
    action = (payload or {}).get("action")
    if action not in _HANDLERS:
        return {"error": f"Unknown action: {action!r}. Expected one of {list(_HANDLERS)}."}
    if not payload.get("user_id"):
        return {"error": "Missing user_id in payload."}
    try:
        return _HANDLERS[action](payload)
    except Exception as e:
        logger.exception("Action %s failed", action)
        return {"error": str(e)}


if __name__ == "__main__":
    app.run()
