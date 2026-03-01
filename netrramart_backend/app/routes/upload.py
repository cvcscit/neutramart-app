import uuid
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import boto3

from app.config import (
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    AWS_REGION,
    S3_BUCKET_NAME,
    ALLOWED_CONTENT_TYPES,
    PRESIGN_EXPIRY_SECONDS,
)

router = APIRouter()

s3 = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_REGION,
    endpoint_url=f"https://s3.{AWS_REGION}.amazonaws.com",
)


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    email: str


@router.post("/upload/presign")
def create_presigned_url(body: PresignRequest):
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed")

    ext = os.path.splitext(body.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=400, detail="Invalid file extension")

    key = f"{body.email}/{uuid.uuid4().hex}{ext}"

    url = s3.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": S3_BUCKET_NAME,
            "Key": key,
            "ContentType": body.content_type,
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )

    return {"url": url, "key": key}
