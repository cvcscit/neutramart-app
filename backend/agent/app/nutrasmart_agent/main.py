"""
NutraSmart AgentCore Runtime — a Strands agent that owns all of NutraSmart's LLM logic.

One runtime, three actions routed by the ``action`` field of the invocation payload:

    {"action": "chat",    "user_id": ..., "message": ..., "history": [...]}  -> {"reply": str}
    {"action": "summary", "user_id": ...}                                    -> {"status": "ok"}
    {"action": "analyze", "user_id": ..., "images": [{"key", "content_type"}]} -> analysis JSON

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
from datetime import datetime, timedelta, timezone

import boto3
from PIL import Image

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

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


_HANDLERS = {
    "chat": _handle_chat,
    "summary": _handle_summary,
    "analyze": _handle_analyze,
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
