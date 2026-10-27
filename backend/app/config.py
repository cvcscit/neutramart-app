"""Environment-driven settings for the FastAPI edge.

Every tunable the edge uses is read here, once, at import. Region buckets and agent runtime
ARNs have no defaults: a data region whose bucket (or ARN) is missing is refused with 503
by ``app.regions.get_data_context`` instead of being routed elsewhere.
"""

import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "1002409619791-66n3jv66p121t7g0qmasukau0r6tc6i1.apps.googleusercontent.com",
)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:5174,https://nutrasmart.in,"
        "http://maitribot-demo-ui.s3-website.ap-south-1.amazonaws.com,"
        "https://maitribot-demo-ui.s3.ap-south-1.amazonaws.com,"
        "https://maitribot-demo-ui.s3.amazonaws.com",
    ).split(",")
    if o.strip()
]

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

# Face-scan video uploads (separate allowlist so image endpoints can't be fed video).
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",  # .mov
    "video/webm",  # browser MediaRecorder default
}

PRESIGN_EXPIRY_SECONDS = 300

# ─── Timeouts and retries for calls made on the request path ────────────────────────
# S3 calls go through the regional clients built in app.regions. AWS_MAX_RETRIES counts
# retries after the first attempt (botocore's ``max_attempts`` inside a Config).
S3_CONNECT_TIMEOUT_S = float(os.environ.get("S3_CONNECT_TIMEOUT_S", "5"))
S3_READ_TIMEOUT_S = float(os.environ.get("S3_READ_TIMEOUT_S", "30"))
AWS_MAX_RETRIES = int(os.environ.get("AWS_MAX_RETRIES", "3"))
# Fetch of Google's ID-token signing certificates (google-auth's own default is 120 s).
GOOGLE_CERTS_TIMEOUT_S = float(os.environ.get("GOOGLE_CERTS_TIMEOUT_S", "5"))
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE_BYTES = 400 * 1024 * 1024  # 400MB, matches BP_measurement/app/server.py

# ─── AgentCore Runtime (agentic backend) ────────────────────────────────────────────
# The FastAPI edge proxies analyze/chat/summary/face_scan to a Strands agent deployed on
# Amazon Bedrock AgentCore Runtime, one per data region (REGION_AGENT_ARNS below, from SSM).
# AGENTCORE_REGION is the region assumed when a runtime ARN can't be parsed.
AGENTCORE_REGION = os.environ.get("AGENTCORE_REGION", "us-east-1")

# Default botocore read timeout (~60s) is too short for slower actions (face_scan: video
# download + MediaPipe extraction; analyze: first-request torch/classifier import).
AGENT_INVOKE_READ_TIMEOUT_S = float(os.environ.get("AGENT_INVOKE_READ_TIMEOUT_S", "300"))

# Local development: when set (e.g. http://localhost:8080), every agent call goes to the
# locally running agent's /invocations endpoint instead of the deployed AgentCore runtime.
AGENT_LOCAL_URL = os.environ.get("AGENT_LOCAL_URL", "").rstrip("/")
AGENT_LOCAL_TIMEOUT_S = float(os.environ.get("AGENT_LOCAL_TIMEOUT_S", "180"))

# ─── Data residency (per-geography storage + processing) ─────────────────────────────
# A user's location (from the CloudFront-Viewer-Country header) is mapped to a data
# region; ALL of that user's data is stored in the region's bucket and processed by the
# region's AgentCore runtime + in-region Bedrock. This keeps data resident by geography.
#
# The default region is used when the country cannot be determined or is unmapped.
DEFAULT_DATA_REGION = os.environ.get("DEFAULT_DATA_REGION", "us-east-1")

# region -> S3 bucket (bucket physically lives in that region). No defaults: an unset
# bucket makes its region unavailable (503) rather than sending data to another bucket.
REGION_BUCKETS = {
    "us-east-1": os.environ.get("BUCKET_US", ""),
    "ap-south-1": os.environ.get("BUCKET_IN", ""),
    "ca-central-1": os.environ.get("BUCKET_CA", ""),
    "eu-west-1": os.environ.get("BUCKET_EU", ""),
}

# region -> AgentCore runtime ARN (each runtime is pinned to its region's bucket +
# in-region Bedrock). Injected via env/SSM at deploy.
REGION_AGENT_ARNS = {
    "us-east-1": os.environ.get("AGENT_ARN_US", ""),
    "ap-south-1": os.environ.get("AGENT_ARN_IN", ""),
    "ca-central-1": os.environ.get("AGENT_ARN_CA", ""),
    "eu-west-1": os.environ.get("AGENT_ARN_EU", ""),
}

# ISO-3166 alpha-2 country code -> data region. Anything unmapped falls back to
# DEFAULT_DATA_REGION. EU/EEA/UK/CH are grouped into eu-west-1.
_EU_COUNTRIES = [
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU",
    "IE", "IT", "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES",
    "SE", "IS", "LI", "NO", "GB", "CH",
]
COUNTRY_REGION = {"CA": "ca-central-1", "US": "us-east-1", "IN": "ap-south-1"}
COUNTRY_REGION.update({c: "eu-west-1" for c in _EU_COUNTRIES})

CF_ORIGIN_SECRET = os.environ.get("CF_ORIGIN_SECRET", "")

# Origins OriginVerifyMiddleware lets through without X-Origin-Verify. Empty by default.
# Set only for the temporary S3 demo build while CloudFront is blocked
# (documents/MIGRATION_OUTSTANDING_TASKS.md), and unset once CloudFront is restored: the
# Origin header is client-controlled, so every entry here bypasses the CloudFront gate.
ORIGIN_VERIFY_EXEMPT_ORIGINS = frozenset(
    o.strip() for o in os.environ.get("ORIGIN_VERIFY_EXEMPT_ORIGINS", "").split(",") if o.strip()
)
