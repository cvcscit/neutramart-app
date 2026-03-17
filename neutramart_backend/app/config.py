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

BEDROCK_MODEL_ID = "us.meta.llama3-2-90b-instruct-v1:0"
BEDROCK_REGION = "us-east-1"
