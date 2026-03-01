import os
from dotenv import load_dotenv

load_dotenv()

AWS_ACCESS_KEY_ID = os.environ["AWS_ACCESS_KEY_ID"]
AWS_SECRET_ACCESS_KEY = os.environ["AWS_SECRET_ACCESS_KEY"]
AWS_REGION = os.environ["AWS_REGION"]
S3_BUCKET_NAME = os.environ["S3_BUCKET_NAME"]

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
}

PRESIGN_EXPIRY_SECONDS = 300
