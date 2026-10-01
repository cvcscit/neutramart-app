# AgentCore Runtime runs on ARM64 (AWS Graviton) — build for linux/arm64.
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# System deps for Pillow + opencv/mediapipe (face-scan heart-rate pipeline, see app/dsv/)
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g \
        libglib2.0-0 libsm6 libxext6 libxrender1 libgomp1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# NOTE: mediapipe==0.10.14 must be confirmed to ship a manylinux_aarch64 wheel for
# this image's Python 3.12 before this build is trusted in production -- if pip
# falls back to building from source here it will likely fail or balloon build time.
# Verify with: docker buildx build --platform linux/arm64 . (see documents/DEPLOYMENT.md)

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# AgentCore Runtime invokes the HTTP server on port 8080 (POST /invocations, GET /ping).
EXPOSE 8080

CMD ["python", "-m", "app.nutrasmart_agent.main"]
