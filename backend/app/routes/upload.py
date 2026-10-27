"""Presigned uploads: the browser PUTs a meal photo or face-scan video straight to the user's regional bucket."""

import os

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_current_user, user_id_from_email
from app.config import (
    ALLOWED_CONTENT_TYPES,
    ALLOWED_VIDEO_CONTENT_TYPES,
    PRESIGN_EXPIRY_SECONDS,
)
from app.limiter import limiter
from app.regions import get_data_context
from app.user_keys import new_upload_key

router = APIRouter()


class PresignRequest(BaseModel):
    filename: str
    content_type: str


@router.post("/upload/presign")
@limiter.limit("20/minute")
def create_presigned_url(
    request: Request,
    body: PresignRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """Validate the file type and return a presigned PUT URL and the key it uploads to.

    The key sits under the verified user's ``users/{user_id}/uploads/`` prefix. An
    ``email`` field still sent by older clients is ignored.
    """
    is_video = body.content_type in ALLOWED_VIDEO_CONTENT_TYPES
    if body.content_type not in ALLOWED_CONTENT_TYPES and not is_video:
        raise HTTPException(status_code=400, detail="File type not allowed")

    ext = os.path.splitext(body.filename)[1].lower()
    allowed_ext = {".mp4", ".mov", ".webm"} if is_video else {".jpg", ".jpeg", ".png", ".gif", ".webp"}
    if ext not in allowed_ext:
        raise HTTPException(status_code=400, detail="Invalid file extension")

    key = new_upload_key(user_id_from_email(_user["email"]), ext)

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
