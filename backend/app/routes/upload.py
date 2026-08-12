import uuid
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.config import ALLOWED_CONTENT_TYPES, PRESIGN_EXPIRY_SECONDS
from app.regions import get_data_context
from app.limiter import limiter

router = APIRouter()


class PresignRequest(BaseModel):
    filename: str
    content_type: str
    email: str


@router.post("/upload/presign")
@limiter.limit("20/minute")
def create_presigned_url(
    request: Request,
    body: PresignRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    if body.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=400, detail="File type not allowed")

    ext = os.path.splitext(body.filename)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        raise HTTPException(status_code=400, detail="Invalid file extension")

    key = f"{body.email}/{uuid.uuid4().hex}{ext}"

    # Presign against the user's REGIONAL bucket so the browser uploads the image
    # directly into the correct region (bytes never transit the edge).
    url = ctx["s3"].generate_presigned_url(
        "put_object",
        Params={
            "Bucket": ctx["bucket"],
            "Key": key,
            "ContentType": body.content_type,
        },
        ExpiresIn=PRESIGN_EXPIRY_SECONDS,
    )

    return {"url": url, "key": key}
