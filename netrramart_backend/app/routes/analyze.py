import json
import re
import base64
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import boto3

from app.auth import get_current_user
from app.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
)

router = APIRouter()

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
)

bedrock = boto3.client(
    "bedrock-runtime",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=BEDROCK_REGION,
)

PROMPT = (
    "You are a nutrition analysis assistant. Analyze the food in this image and "
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


class AnalyzeRequest(BaseModel):
    key: str
    content_type: str


@router.post("/analyze")
def analyze_food(body: AnalyzeRequest, _user=Depends(get_current_user)):
    # 1. Fetch image from S3
    try:
        s3_response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=body.key)
        image_bytes = s3_response["Body"].read()
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Image not found in S3: {e}")

    # 2. Build Bedrock request with base64-encoded image
    image_base64 = base64.b64encode(image_bytes).decode("utf-8")

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": body.content_type,
                            "data": image_base64,
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    })

    # 3. Call Bedrock
    try:
        bedrock_response = bedrock.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=request_body,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Bedrock API error: {e}")

    # 4. Parse response
    response_body = json.loads(bedrock_response["body"].read())
    assistant_text = response_body["content"][0]["text"]

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

    return analysis
