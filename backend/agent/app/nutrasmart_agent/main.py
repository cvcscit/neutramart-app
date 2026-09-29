"""
NutraSmart AgentCore Runtime — a Strands agent that owns all of NutraSmart's LLM logic.

One runtime, three actions routed by the ``action`` field of the invocation payload:

    {"action": "chat",    "user_id": ..., "message": ..., "history": [...]}  -> {"reply": str}
    {"action": "summary", "user_id": ...}                                    -> {"status": "ok"}
    {"action": "analyze", "user_id": ..., "images": [{"key", "content_type"}]} -> analysis JSON

Identity is never taken from the client: the FastAPI edge validates the Google ID token,
derives ``user_id`` and passes it here. This agent trusts ``user_id`` from the payload only.

Food recognition for ``analyze`` runs a local classifier first and falls back to the
vision LLM below a confidence threshold (see ``analysis.py``). Configuration lives in
``settings.py``; AWS clients and the classifier are built lazily in ``services.py``.

Data model (S3 bucket ``S3_BUCKET_NAME``):
    users/{user_id}/scans/{ts}.json      food-analysis records (the knowledge base)
    users/{user_id}/weekly_summary.txt   generated eating summary
    users/{user_id}/health_profile.json  optional health profile
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel

from .analysis import ImageRef, analyze_food_images
from .prompts import CHAT_SYSTEM_PROMPT, WEEKLY_SUMMARY_PROMPT
from .services import AgentServices, build_services
from .settings import load_settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nutrasmart_agent")

app = BedrockAgentCoreApp()


@lru_cache(maxsize=1)
def _services() -> AgentServices:
    """Build settings, AWS clients and the lazy classifier once per container."""
    return build_services(load_settings())


# ─── Tools ───────────────────────────────────────────────────────────────────────────
@tool
def get_recent_scans(user_id: str, days: int = 60) -> str:
    """Fetch the user's food-analysis scan records from the last N days (default 60).

    Returns a formatted text block of dated records with calories, macros and
    micronutrients — the knowledge base for summaries and chat.
    """
    services = _services()
    prefix = f"users/{user_id}/scans/"
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    response = services.s3.list_objects_v2(Bucket=services.settings.s3_bucket_name, Prefix=prefix)
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
            scan_data = services.s3.get_object(Bucket=services.settings.s3_bucket_name, Key=obj["Key"])
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
    services = _services()
    try:
        response = services.s3.get_object(
            Bucket=services.settings.s3_bucket_name, Key=f"users/{user_id}/health_profile.json"
        )
        profile = json.loads(response["Body"].read())
    except Exception:
        return "No health profile on file for this user."
    lines = "\n".join(f"  {k}: {v}" for k, v in profile.items())
    return f"The user has the following health profile:\n{lines}"


@tool
def get_eating_summary(user_id: str) -> str:
    """Fetch the user's most recently generated 2-month eating summary, if any."""
    services = _services()
    try:
        response = services.s3.get_object(
            Bucket=services.settings.s3_bucket_name, Key=f"users/{user_id}/weekly_summary.txt"
        )
        return response["Body"].read().decode("utf-8")
    except Exception:
        return "No eating summary has been generated yet."


def _save_summary(user_id: str, text: str) -> None:
    services = _services()
    services.s3.put_object(
        Bucket=services.settings.s3_bucket_name,
        Key=f"users/{user_id}/weekly_summary.txt",
        Body=text,
        ContentType="text/plain",
    )


def _save_scan(user_id: str, analysis: dict, image_keys: list) -> None:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_key = f"users/{user_id}/scans/{timestamp}.json"
    services = _services()
    services.s3.put_object(
        Bucket=services.settings.s3_bucket_name,
        Key=scan_key,
        Body=json.dumps({**analysis, "timestamp": timestamp, "image_keys": image_keys}),
        ContentType="application/json",
    )


# ─── Action handlers ─────────────────────────────────────────────────────────────────
def _model() -> BedrockModel:
    services = _services()
    return BedrockModel(
        model_id=services.settings.bedrock_model_id,
        region_name=services.settings.bedrock_region,
        boto_client_config=services.bedrock_config,
    )


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
    services = _services()
    resp = services.bedrock.converse(
        modelId=services.settings.bedrock_model_id,
        messages=[{"role": "user", "content": [{"text": full_prompt}]}],
        inferenceConfig={"maxTokens": services.settings.summary_max_tokens},
    )
    summary_text = resp["output"]["message"]["content"][0]["text"]
    _save_summary(user_id, summary_text)
    logger.info("Summary saved for %s", user_id)
    return {"status": "ok"}


def _handle_analyze(payload: dict) -> dict:
    user_id = payload["user_id"]
    refs = [
        ImageRef(key=img["key"], content_type=img.get("content_type", ""))
        for img in payload.get("images") or []
    ]
    services = _services()
    analysis = analyze_food_images(
        refs,
        s3=services.s3,
        bedrock=services.bedrock,
        classifier=services.classifier.get(),
        settings=services.settings,
    )
    try:
        _save_scan(user_id, analysis, [ref.key for ref in refs])
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
