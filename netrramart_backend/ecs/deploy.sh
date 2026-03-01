#!/bin/bash
set -e

# ──────────────────────────────────────────────
# Configuration — replace these with your values
# ──────────────────────────────────────────────
AWS_ACCOUNT_ID="<ACCOUNT_ID>"
AWS_REGION="ap-south-1"
ECR_REPO="neutramart-backend"
ECS_CLUSTER="neutramart-cluster"
ECS_SERVICE="neutramart-backend-service"

IMAGE_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}:latest"

echo "==> Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin \
  "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "==> Building Docker image..."
docker build -t $ECR_REPO .

echo "==> Tagging image..."
docker tag $ECR_REPO:latest $IMAGE_URI

echo "==> Pushing to ECR..."
docker push $IMAGE_URI

echo "==> Updating ECS service (forces new deployment)..."
aws ecs update-service \
  --cluster $ECS_CLUSTER \
  --service $ECS_SERVICE \
  --force-new-deployment \
  --region $AWS_REGION

echo "==> Done! ECS will roll out the new image."
