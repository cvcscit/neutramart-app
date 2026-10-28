# AWS ECR Public mirrors official Docker Hub images 1:1 -- using it instead of
# docker.io directly sidesteps Docker Hub's rate limits/flakiness, and this image is
# deployed to AWS anyway, so pulls from ECR Public are typically faster too.
FROM public.ecr.aws/docker/library/python:3.12-slim AS builder

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --target=/app/deps -r requirements.txt

FROM public.ecr.aws/docker/library/python:3.12-slim

RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

WORKDIR /app

COPY --from=builder /app/deps /usr/local/lib/python3.12/site-packages/
COPY . .

RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
