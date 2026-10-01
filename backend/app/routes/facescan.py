import logging
import uuid

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.auth import get_current_user
from app.agent_client import invoke_agent, AgentError
from app.regions import get_data_context
from app.limiter import limiter

router = APIRouter()


class FaceScanRequest(BaseModel):
    key: str
    content_type: str


@router.post("/facescan/analyze")
@limiter.limit("5/minute")
def analyze_face_scan(
    request: Request,
    body: FaceScanRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")

    # Delegate to the user's REGIONAL agent (same pattern as /analyze). Only heart rate
    # is returned to the client -- BP/SpO2 are intentionally not exposed (unvalidated).
    # Fresh random session per request: face_scan is a one-shot action with no need for
    # conversational continuity, so always route to a newly-provisioned container rather
    # than potentially reusing a stale warm instance pinned to an older deployed image.
    try:
        result = invoke_agent(
            {
                "action": "face_scan",
                "user_id": user_id,
                "key": body.key,
            },
            agent_arn=ctx["agent_arn"],
            session_id=f"facescan-{uuid.uuid4().hex}",  # 41 chars, well over AgentCore's 33-char minimum
        )
    except AgentError as e:
        logger.error("Face scan failed (region=%s): %s", ctx["region"], e)
        raise HTTPException(status_code=502, detail=f"Face scan failed: {e}")

    return result
