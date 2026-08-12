import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
S3_BUCKET_NAME = os.environ.get("S3_BUCKET_NAME", "sci-neutrasmart-project")

GOOGLE_CLIENT_ID = os.environ.get(
    "GOOGLE_CLIENT_ID",
    "1002409619791-66n3jv66p121t7g0qmasukau0r6tc6i1.apps.googleusercontent.com",
)

ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:5174,https://nutrasmart.in"
    ).split(",")
    if o.strip()
]

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

PRESIGN_EXPIRY_SECONDS = 300
MAX_IMAGE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB

# Bedrock is now called from the AgentCore runtime, not the edge. These remain only
# as a fallback for local/legacy direct-call paths and can be removed once the agent
# proxy is fully verified in production.
BEDROCK_MODEL_ID = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_REGION = "ap-south-1"

# ─── AgentCore Runtime (agentic backend) ────────────────────────────────────────────
# The FastAPI edge proxies analyze/chat/summary to a Strands agent deployed on
# Amazon Bedrock AgentCore Runtime. ARN is injected via env/SSM at deploy.
AGENT_RUNTIME_ARN = os.environ.get("AGENT_RUNTIME_ARN", "")
AGENTCORE_REGION = os.environ.get("AGENTCORE_REGION", "us-east-1")

# ─── Data residency (per-geography storage + processing) ─────────────────────────────
# A user's location (from the CloudFront-Viewer-Country header) is mapped to a data
# region; ALL of that user's data is stored in the region's bucket and processed by the
# region's AgentCore runtime + in-region Bedrock. This keeps data resident by geography.
#
# The default region is used when the country cannot be determined or is unmapped.
DEFAULT_DATA_REGION = os.environ.get("DEFAULT_DATA_REGION", "us-east-1")

# region -> S3 bucket (bucket physically lives in that region). India reuses the
# original bucket so existing data stays put.
REGION_BUCKETS = {
    "us-east-1": os.environ.get("BUCKET_US", "sci-neutrasmart-project-us"),
    "ap-south-1": os.environ.get("BUCKET_IN", "sci-neutrasmart-project"),
    "ca-central-1": os.environ.get("BUCKET_CA", "sci-neutrasmart-project-ca"),
    "eu-west-1": os.environ.get("BUCKET_EU", "sci-neutrasmart-project-eu"),
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
