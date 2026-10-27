"""Face-scan vitals route: an uploaded face video is analysed by the user's regional agent.

The agent's result is validated against ``FaceScanResponse`` before it reaches the client:
only the whitelisted fields pass, and blood pressure and SpO2 always carry
``experimental: true`` (see ``face_scan_biomarkers/__init__.py`` in the agent for why).
"""

import logging
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ValidationError

from app.agent_client import AgentError, invoke_agent
from app.auth import get_current_user, user_id_from_email
from app.limiter import limiter
from app.regions import get_data_context
from app.user_keys import is_upload_key

logger = logging.getLogger(__name__)

router = APIRouter()

_BIOMARKER_DISCLAIMER = (
    "Research estimate only. Not validated for medical or consumer health decisions "
    "-- do not rely on this value."
)


class FaceScanRequest(BaseModel):
    key: str
    content_type: str


class _Vital(BaseModel):
    """Fields every vital shares: whether a value was produced and, if not, why."""

    status: Literal["ok", "withheld", "unavailable"]
    reason: str | None = None


class HeartRate(_Vital):
    heart_rate_bpm: float | None = None


class _ExperimentalVital(_Vital):
    """A research-grade estimate: flagged as experimental whatever the agent sent."""

    experimental: Literal[True] = True
    disclaimer: str = _BIOMARKER_DISCLAIMER


class BloodPressure(_ExperimentalVital):
    sbp: float | None = None
    dbp: float | None = None


class SpO2(_ExperimentalVital):
    spo2: float | None = None


class FaceScanResponse(BaseModel):
    heart_rate: HeartRate
    bp: BloodPressure
    spo2: SpO2


@router.post("/facescan/analyze", response_model=FaceScanResponse)
@limiter.limit("5/minute")
def analyze_face_scan(
    request: Request,
    body: FaceScanRequest,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """Run the in-house face-scan pipeline on an uploaded video and return the vitals."""
    user_id = user_id_from_email(_user["email"])
    if not is_upload_key(user_id, body.key):
        raise HTTPException(status_code=400, detail="Unknown upload. Please record the scan again.")

    # Delegate to the user's REGIONAL agent (same pattern as /analyze).
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
        return FaceScanResponse.model_validate(result)
    except AgentError as e:
        logger.error("Face scan failed (region=%s): %s", ctx["region"], e)
        raise HTTPException(status_code=502, detail="Face scan failed. Please try again.")
    except ValidationError as e:
        # include_input=False: the rejected values are the user's vitals, which never go to the log.
        logger.error(
            "Face scan returned an unexpected shape (region=%s): %s",
            ctx["region"], e.errors(include_input=False, include_url=False),
        )
        raise HTTPException(status_code=502, detail="Face scan failed. Please try again.")
