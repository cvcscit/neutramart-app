# AgentCore Runtime runs on ARM64 (AWS Graviton) — build for linux/arm64.
FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# System deps for Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
        libjpeg62-turbo zlib1g \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-base.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# Food-classifier weights are not baked in: they are downloaded from
# FOOD_CLASSIFIER_MODEL_URI (S3) on the first analyze request and cached here.
ENV FOOD_CLASSIFIER_CACHE_DIR=/tmp/food_models

# AgentCore Runtime invokes the HTTP server on port 8080 (POST /invocations, GET /ping).
EXPOSE 8080

CMD ["python", "-m", "app.nutrasmart_agent.main"]
