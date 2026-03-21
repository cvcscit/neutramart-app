import json
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional
import boto3

from app.auth import get_current_user
from app.config import (
    AWS_REGION,
    S3_BUCKET_NAME,
    BEDROCK_MODEL_ID,
    BEDROCK_REGION,
)
from app.limiter import limiter

logger = logging.getLogger(__name__)

router = APIRouter()

s3 = boto3.client("s3", region_name=AWS_REGION)
bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)

CHAT_SYSTEM_PROMPT = (
    "You are NutraSmart AI, a friendly and knowledgeable nutrition assistant. "
    "You have access to the user's food analysis history and weekly eating summary. "
    "Use this data to answer questions about their diet, nutrition, eating habits, "
    "and provide personalized recommendations.\n\n"
    "Rules:\n"
    "- Be conversational, friendly, and concise.\n"
    "- Reference specific foods and numbers from their data when relevant.\n"
    "- If asked about something not in the data, say so honestly.\n"
    "- Keep responses short (2-4 sentences) unless the user asks for detail.\n"
    "- Do not provide medical diagnoses. Suggest consulting a doctor for health concerns.\n\n"
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessage]] = []


def _load_user_context(user_id: str) -> str:
    """Load weekly summary and recent scans as context for the chat."""
    context = ""

    # Load weekly summary
    try:
        response = s3.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"users/{user_id}/weekly_summary.txt",
        )
        summary = response["Body"].read().decode("utf-8")
        context += f"=== 7-DAY EATING SUMMARY ===\n{summary}\n\n"
    except Exception:
        pass

    # Load health profile if exists
    try:
        response = s3.get_object(
            Bucket=S3_BUCKET_NAME,
            Key=f"users/{user_id}/health_profile.json",
        )
        profile = json.loads(response["Body"].read())
        context += "=== HEALTH PROFILE ===\n"
        for key, value in profile.items():
            context += f"{key}: {value}\n"
        context += "\n"
    except Exception:
        pass

    # Load recent scans (last 7 days)
    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=f"users/{user_id}/scans/",
        )
        if "Contents" in response:
            scans = []
            for obj in sorted(response["Contents"], key=lambda x: x["Key"], reverse=True)[:20]:
                scan_data = s3.get_object(Bucket=S3_BUCKET_NAME, Key=obj["Key"])
                scans.append(json.loads(scan_data["Body"].read()))

            context += "=== RECENT FOOD SCANS ===\n"
            for scan in scans:
                context += (
                    f"- {scan.get('timestamp', '?')}: {scan.get('description', 'N/A')} "
                    f"({scan.get('calories', 'N/A')} cal, "
                    f"P:{scan.get('protein', 'N/A')}, "
                    f"C:{scan.get('carbs', 'N/A')}, "
                    f"F:{scan.get('fat', 'N/A')})\n"
                )
            context += "\n"
    except Exception:
        pass

    return context


@router.post("/chat")
@limiter.limit("20/minute")
def chat(request: Request, body: ChatRequest, _user=Depends(get_current_user)):
    user_email = _user["email"]
    user_id = user_email.replace("@", "_at_").replace(".", "_")

    # Load user context
    user_context = _load_user_context(user_id)

    system_prompt = CHAT_SYSTEM_PROMPT
    if user_context:
        system_prompt += f"Here is the user's data:\n\n{user_context}"
    else:
        system_prompt += (
            "The user has no food data yet. Encourage them to upload food images "
            "to get personalized nutrition insights."
        )

    # Build conversation messages
    messages = []
    for msg in (body.history or []):
        messages.append({"role": msg.role, "content": [{"text": msg.content}]})
    messages.append({"role": "user", "content": [{"text": body.message}]})

    try:
        response = bedrock.converse(
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            inferenceConfig={"maxTokens": 512},
        )
        reply = response["output"]["message"]["content"][0]["text"]
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Chat failed: {e}")
        raise HTTPException(status_code=502, detail="Chat failed. Please try again.")
