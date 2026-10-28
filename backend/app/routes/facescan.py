import json
import logging
import uuid
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)
from fastapi import APIRouter, Depends, HTTPException, Query, Request
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


@router.post("/facescan/save")
@limiter.limit("20/minute")
def save_vitals_scan(
    request: Request,
    body: dict,
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Save a client-computed vitals scan (e.g. the Shen.AI on-device scan, which never
    uploads a video -- unlike /facescan/analyze, which runs the in-house video pipeline
    server-side). `body` is heterogeneous per-metric (status/reason vs
    status/sbp/dbp/experimental/disclaimer -- see senai_scan/adapter.js's toVitals()), so
    it's stored as-is rather than forced into a strict schema.

    S3 key: users/{user_id}/vitals_scans/{timestamp}.json -- same prefix the in-house
    pipeline's _save_vitals_scan() already uses, so both sources read back uniformly.
    """
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    key = f"users/{user_id}/vitals_scans/{timestamp}.json"

    try:
        ctx["s3"].put_object(
            Bucket=ctx["bucket"],
            Key=key,
            Body=json.dumps({**body, "timestamp": timestamp}),
            ContentType="application/json",
        )
    except Exception as e:
        logger.error(f"Failed to save vitals scan for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to save vitals scan.")

    return {"status": "ok"}


def _vitals_scan_date(timestamp: str) -> Optional[date]:
    """Vitals timestamps are always "YYYYMMDDTHHMMSSZ" (see save_vitals_scan /
    _save_vitals_scan) -- no ISO fallback needed, unlike meals.py's logged_at parsing."""
    try:
        return datetime.strptime(timestamp, "%Y%m%dT%H%M%SZ").date()
    except (ValueError, TypeError):
        return None


@router.get("/vitals/summary")
@limiter.limit("30/minute")
def get_vitals_summary(
    request: Request,
    startDate: Optional[str] = Query(None),  # YYYY-MM-DD
    endDate: Optional[str] = Query(None),
    limit: int = Query(60),
    _user=Depends(get_current_user),
    ctx: dict = Depends(get_data_context),
):
    """
    Return the user's vitals scans as flat, chartable rows -- one row per scan, not
    bucketed/averaged like /nutrition/summary (vitals are point-in-time readings, not
    totals to sum). Normalizes the two source shapes that can land in vitals_scans/
    (Shen.AI's sbp/dbp vs. the in-house pipeline's systolic/diastolic) into one shape.
    Optional startDate/endDate filter the scan date, same param names/format as
    /nutrition/summary for a consistent frontend contract.
    """
    user_id = _user["email"].replace("@", "_at_").replace(".", "_")
    prefix = f"users/{user_id}/vitals_scans/"

    start = date.fromisoformat(startDate) if startDate else None
    end = date.fromisoformat(endDate) if endDate else None

    try:
        response = ctx["s3"].list_objects_v2(Bucket=ctx["bucket"], Prefix=prefix)
    except Exception as e:
        logger.error(f"Failed to list vitals scans for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load vitals summary.")

    scans = []
    for obj in response.get("Contents", []):
        try:
            data = json.loads(ctx["s3"].get_object(Bucket=ctx["bucket"], Key=obj["Key"])["Body"].read())
        except Exception as e:
            logger.warning(f"Skipping unreadable {obj['Key']}: {e}")
            continue

        timestamp = data.get("timestamp", "")
        if start or end:
            d = _vitals_scan_date(timestamp)
            if d is None or (start and d < start) or (end and d > end):
                continue

        hr = data.get("heart_rate") or {}
        bp = data.get("bp") or {}
        extras = data.get("extras") or {}

        scans.append({
            "date": timestamp,
            "heart_rate_bpm": hr.get("heart_rate_bpm") if hr.get("status") == "ok" else None,
            "systolic": (bp.get("sbp", bp.get("systolic")) if bp.get("status") == "ok" else None),
            "diastolic": (bp.get("dbp", bp.get("diastolic")) if bp.get("status") == "ok" else None),
            "hrv_sdnn_ms": extras.get("hrv_sdnn_ms"),
            "breathing_rate_bpm": extras.get("breathing_rate_bpm"),
            "stress_index": extras.get("stress_index"),
        })

    scans.sort(key=lambda s: s["date"])
    return {"data": scans[-limit:]}
