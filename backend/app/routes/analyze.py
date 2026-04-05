import io
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from PIL import Image

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
import boto3

from app.auth import get_current_user
from app.config import (
    AWS_REGION,
    S3_BUCKET_NAME,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
    MAX_IMAGE_SIZE_BYTES,
)
from app.limiter import limiter

router = APIRouter()

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

BEDROCK_MAX_IMAGE_BYTES = 3_932_160  # 3.75 MB – Bedrock Converse inline bytes limit
SUPPORTED_BEDROCK_FORMATS = {"jpeg", "png", "gif", "webp"}
MAX_IMAGES_PER_REQUEST = 5


def normalize_image(raw_bytes: bytes) -> bytes:
    """Open with Pillow and re-encode as JPEG to fix format mismatches / HEIC / corruption."""
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img = img.convert("RGB")
        out = io.BytesIO()
        img.save(out, format="JPEG", quality=85)
        return out.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or unreadable image file.")

PROMPT = (
    "You are a nutrition analysis assistant. Analyze the food in the provided image(s) and "
    "return ONLY a JSON object with these exact keys, no other text:\n"
    "{\n"
    '  "description": "Brief description of the food item(s) visible",\n'
    '  "weight": "Estimated weight/portion size (e.g. 250g)",\n'
    '  "calories": "Estimated calories (e.g. 350 kcal)",\n'
    '  "protein": "Estimated protein (e.g. 25g)",\n'
    '  "carbs": "Estimated carbohydrates (e.g. 40g)",\n'
    '  "fat": "Estimated fat (e.g. 15g)",\n'
    '  "fiber": "Estimated fiber (e.g. 5g)",\n'
    '  "sugar": "Estimated sugar (e.g. 10g)",\n'
    '  "summary": "One-sentence nutritional summary",\n'
    '  "recommendation": "Brief dietary recommendation"\n'
    "}\n"
    "If the image does not contain food, set description to 'No food detected' "
    "and set all nutritional values to 'N/A'."
)


class ImageItem(BaseModel):
    key: str
    content_type: str


class AnalyzeRequest(BaseModel):
    images: list[ImageItem]


MAX_DAILY_UPLOADS = 15


@router.post("/analyze")
@limiter.limit("10/minute")
def analyze_food(request: Request, body: AnalyzeRequest, _user=Depends(get_current_user)):
    if not body.images:
        raise HTTPException(status_code=400, detail="At least one image is required.")
    if len(body.images) > MAX_IMAGES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_IMAGES_PER_REQUEST} images per request.")

    # 0. Check daily upload limit
    user_email = _user["email"]
    uid = user_email.replace("@", "_at_").replace(".", "_")
    today_prefix = f"users/{uid}/scans/{datetime.now(timezone.utc).strftime('%Y%m%d')}"
    try:
        today_scans = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=today_prefix)
        today_count = today_scans.get("KeyCount", 0)
        if today_count >= MAX_DAILY_UPLOADS:
            raise HTTPException(
                status_code=429,
                detail=f"Daily upload limit reached ({MAX_DAILY_UPLOADS} images/day). Try again tomorrow.",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Don't block user if check fails

    # 1. Fetch all images from S3, normalize with Pillow
    image_content_blocks = []
    for item in body.images:
        try:
            head = s3.head_object(Bucket=S3_BUCKET_NAME, Key=item.key)
            if head["ContentLength"] > MAX_IMAGE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail=f"Image {item.key} is too large (max 10MB)")
            s3_response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=item.key)
            raw_bytes = s3_response["Body"].read()
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=404, detail=f"Image not found: {item.key}")

        # Normalize: re-encode as JPEG via Pillow (fixes HEIC, format mismatches, corruption)
        jpeg_bytes = normalize_image(raw_bytes)

        if len(jpeg_bytes) > BEDROCK_MAX_IMAGE_BYTES:
            raise HTTPException(
                status_code=413,
                detail="An image is too large for analysis after processing (max 3.75 MB). Please use a smaller image.",
            )

        image_content_blocks.append({
            "image": {"format": "jpeg", "source": {"bytes": jpeg_bytes}}
        })

    # 2. Call Bedrock via Converse API
    content = image_content_blocks + [{"text": PROMPT}]
    try:
        bedrock_response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            messages=[{"role": "user", "content": content}],
            inferenceConfig={"maxTokens": 1024},
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bedrock API error: {e}")

    # 4. Parse response
    assistant_text = bedrock_response["output"]["message"]["content"][0]["text"]

    try:
        analysis = json.loads(assistant_text)
    except json.JSONDecodeError:
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", assistant_text)
        if json_match:
            analysis = json.loads(json_match.group(1).strip())
        else:
            raise HTTPException(
                status_code=502,
                detail="Failed to parse nutrition analysis from model response",
            )

    # 5. Ensure all expected keys exist
    for k in ("description", "weight", "calories", "protein", "carbs", "fat", "fiber", "sugar", "summary", "recommendation"):
        if k not in analysis:
            analysis[k] = "N/A"

    # 6. Save scan result to S3 and trigger weekly summary in background
    user_email = _user["email"]
    user_id = user_email.replace("@", "_at_").replace(".", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    scan_key = f"users/{user_id}/scans/{timestamp}.json"

    try:
        image_keys = [img.key for img in body.images]
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=scan_key,
            Body=json.dumps({**analysis, "timestamp": timestamp, "image_keys": image_keys}),
            ContentType="application/json",
        )
    except Exception:
        pass  # Don't fail the request if scan save fails

    return analysis


WEEKLY_SUMMARY_PROMPT = (
    "You are a nutrition and dietary advisor. Below are the food analysis records "
    "from the last 7 days for a user. Each record includes the food description, "
    "calories, protein, carbs, fat, fiber, and sugar.\n\n"
    "{health_profile_section}"
    "Analyze the eating patterns and provide a comprehensive 7-day summary in "
    "plain text format with these sections:\n\n"
    "1. EATING HABITS OVERVIEW - Summarize what the user has been eating, meal "
    "patterns, and dietary tendencies.\n\n"
    "2. NUTRITIONAL ANALYSIS - Average daily calorie intake, macronutrient "
    "balance (protein/carbs/fat ratio), fiber and sugar trends.\n\n"
    "3. POSITIVE HABITS - What the user is doing well nutritionally.\n\n"
    "4. AREAS OF CONCERN - Any nutritional gaps, excess intake, or unhealthy "
    "patterns.\n\n"
    "5. RECOMMENDATIONS - Specific, actionable dietary suggestions to improve "
    "nutrition.\n\n"
    "6. RESTRICTIONS & WARNINGS - Any foods or patterns to avoid based on the "
    "observed diet (e.g., too much sugar, sodium, processed food).\n\n"
    "Keep the tone friendly but professional. Be specific with numbers where "
    "possible.\n\n"
    "Here are the food records:\n\n"
)


def _get_health_profile(user_id: str) -> str:
    """Fetch user health profile from S3. Returns formatted section or empty string."""
    # TODO: Future — load from users/{user_id}/health_profile.json
    # Expected fields: age, gender, weight, height, BMI, medical conditions,
    # allergies, medications, fitness goals, dietary preferences (veg/vegan/etc),
    # blood sugar levels, cholesterol, blood pressure, etc.
    #
    # When available, the prompt will include:
    # "The user has the following health profile:\n{profile_data}\n\n"
    # "Factor in the user's health conditions, allergies, and goals when making "
    # "recommendations and restrictions.\n\n"
    try:
        profile_key = f"users/{user_id}/health_profile.json"
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=profile_key)
        profile = json.loads(response["Body"].read())
        profile_text = "The user has the following health profile:\n"
        for key, value in profile.items():
            profile_text += f"  {key}: {value}\n"
        profile_text += (
            "\nFactor in the user's health conditions, allergies, and goals "
            "when making recommendations and restrictions.\n\n"
        )
        return profile_text
    except Exception:
        return ""


def _generate_weekly_summary(user_id: str):
    """Fetch last 7 days of scans and generate a weekly eating summary."""
    prefix = f"users/{user_id}/scans/"
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    # List all scan files for this user
    response = s3.list_objects_v2(Bucket=S3_BUCKET_NAME, Prefix=prefix)
    if "Contents" not in response:
        raise ValueError(f"No scans found for {user_id}")

    # Filter to last 7 days and fetch each scan
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
        raise ValueError(f"No scans in last 7 days for {user_id}")

    # Build the prompt with all scan data
    health_section = _get_health_profile(user_id)
    records_text = ""
    for scan in sorted(scans, key=lambda x: x.get("timestamp", "")):
        records_text += (
            f"- Date: {scan.get('timestamp', 'unknown')}\n"
            f"  Food: {scan.get('description', 'N/A')}\n"
            f"  Calories: {scan.get('calories', 'N/A')}, "
            f"Protein: {scan.get('protein', 'N/A')}, "
            f"Carbs: {scan.get('carbs', 'N/A')}, "
            f"Fat: {scan.get('fat', 'N/A')}, "
            f"Fiber: {scan.get('fiber', 'N/A')}, "
            f"Sugar: {scan.get('sugar', 'N/A')}\n\n"
        )

    full_prompt = WEEKLY_SUMMARY_PROMPT.format(health_profile_section=health_section) + records_text

    logger.info(f"Generating weekly summary for {user_id} with {len(scans)} scans")

    # Call Bedrock for summary
    summary_response = bedrock.converse(
        modelId=BEDROCK_MODEL_ID,
        messages=[{"role": "user", "content": [{"text": full_prompt}]}],
        inferenceConfig={"maxTokens": 2048},
    )

    summary_text = summary_response["output"]["message"]["content"][0]["text"]

    # Save to S3
    summary_key = f"users/{user_id}/weekly_summary.txt"
    s3.put_object(
        Bucket=S3_BUCKET_NAME,
        Key=summary_key,
        Body=summary_text,
        ContentType="text/plain",
    )
    logger.info(f"Weekly summary saved for {user_id}")


@router.post("/weekly-summary/generate")
@limiter.limit("5/minute")
def generate_weekly_summary(request: Request, _user=Depends(get_current_user)):
    user_email = _user["email"]
    user_id = user_email.replace("@", "_at_").replace(".", "_")
    try:
        _generate_weekly_summary(user_id)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Weekly summary generation failed for {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Weekly summary generation failed: {e}")


@router.get("/weekly-summary")
@limiter.limit("10/minute")
def get_weekly_summary(request: Request, _user=Depends(get_current_user)):
    user_email = _user["email"]
    user_id = user_email.replace("@", "_at_").replace(".", "_")
    summary_key = f"users/{user_id}/weekly_summary.txt"

    try:
        # Check if file exists first
        s3.head_object(Bucket=S3_BUCKET_NAME, Key=summary_key)
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=summary_key)
        summary = response["Body"].read().decode("utf-8")
        return {"summary": summary}
    except Exception as e:
        error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
        if error_code in ("NoSuchKey", "404", "Not Found"):
            return {"summary": None, "message": "No weekly summary available yet. Upload food images to generate one."}
        logger.error(f"Weekly summary fetch failed: {e}")
        return {"summary": None, "message": "Summary not available yet."}
