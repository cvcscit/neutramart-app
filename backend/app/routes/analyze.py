import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.agent_client import invoke_agent, AgentError
from app.regions import get_data_context
from app.limiter import limiter

router = APIRouter()

MAX_IMAGES_PER_REQUEST = 5
MAX_DAILY_UPLOADS = int(os.environ.get("MAX_DAILY_UPLOADS", "1000"))


class ImageItem(BaseModel):
    key: str
    content_type: str


class AnalyzeRequest(BaseModel):
    images: list[ImageItem]


@router.post("/analyze")
@limiter.limit("10/minute")
def analyze_food(
    request: Request,
    body: AnalyzeRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    if not body.images:
        raise HTTPException(status_code=400, detail="At least one image is required.")
    if len(body.images) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES_PER_REQUEST} images per request.")

    user_id = _user["email"].replace("@", "_at_").replace(".", "_")

    # Daily upload limit (cheap regional S3 list before invoking the agent)
    today_prefix = f"users/{user_id}/scans/{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        today_count = ctx["s3"].list_objects_v2(Bucket=ctx["bucket"], Prefix=today_prefix).get("KeyCount", 0)
        if today_count >= MAX_DAILY_UPLOADS:
            raise HTTPException(
                status_code=429,
                detail=f"Daily upload limit reached ({MAX_DAILY_UPLOADS} images/day). Try again tomorrow.",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Don't block the user if the check fails

    # Delegate to the user's REGIONAL agent (image fetch + vision + scan save, all in-region).
    try:
        analysis = invoke_agent(
            {
                "action": "analyze",
                "user_id": user_id,
                "images": [{"key": i.key, "content_type": i.content_type} for i in body.images],
            },
            agent_arn=ctx["agent_arn"],
        )
    except AgentError as e:
        logger.error("Analyze failed (region=%s): %s", ctx["region"], e)
        raise HTTPException(status_code=502, detail=f"Food analysis failed: {e}")

    return analysis


@router.post("/weekly-summary/generate")
@limiter.limit("5/minute")
def generate_weekly_summary(
    request: Request,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")
    try:
        invoke_agent({"action": "summary", "user_id": user_id}, agent_arn=ctx["agent_arn"])
        return {"status": "ok"}
    except AgentError as e:
        logger.error("Weekly summary generation failed (region=%s) for %s: %s", ctx["region"], user_id, e)
        raise HTTPException(status_code=500, detail=f"Weekly summary generation failed: {e}")


@router.get("/weekly-summary")
@limiter.limit("10/minute")
def get_weekly_summary(
    request: Request,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")
    summary_key = f"users/{user_id}/weekly_summary.txt"

    try:
        ctx["s3"].head_object(Bucket=ctx["bucket"], Key=summary_key)
        response = ctx["s3"].get_object(Bucket=ctx["bucket"], Key=summary_key)
        summary = response["Body"].read().decode("utf-8")
        return {"summary": summary}
    except Exception as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404", "Not Found"):
            return {"summary": None, "message": "No weekly summary available yet. Upload food images to generate one."}
        logger.error("Weekly summary fetch failed: %s", e)
        return {"summary": None, "message": "Summary not available yet."}
