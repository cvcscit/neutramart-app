#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# nutrasmart — Build, Push, and Deploy to Fargate
# ══════════════════════════════════════════════════════════════
# Usage:
#   cd netrramart_backend/ecs
#   ./deploy.sh
# ══════════════════════════════════════════════════════════════

# Load resource IDs from setup
if [ ! -f resources.env ]; then
    echo "ERROR: resources.env not found. Run setup.sh first."
    exit 1
fi
source resources.env

PROFILE="nutrasmart"
export AWS_PROFILE="$PROFILE"

ECR_REPO="${PROJECT}-backend"
ECS_CLUSTER="${PROJECT}-cluster"
ECS_SERVICE="${PROJECT}-backend-service"
ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"

# Use git commit SHA as image tag (immutable, traceable)
cd ..
IMAGE_TAG=$(git rev-parse --short HEAD 2>/dev/null || echo "latest")
IMAGE_URI="${ECR_URI}:${IMAGE_TAG}"

echo "══════════════════════════════════════════════"
echo "  Deploying nutrasmart Backend"
echo "  Image tag: $IMAGE_TAG"
echo "══════════════════════════════════════════════"
echo ""

# 1. Authenticate with ECR
echo "==> [1/5] Logging into ECR..."
aws ecr get-login-password --region $AWS_REGION | \
    docker login --username AWS --password-stdin \
    "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

# 2. Build
echo "==> [2/5] Building Docker image..."
docker build --platform linux/amd64 -t $ECR_REPO:$IMAGE_TAG .

# 3. Tag and push
echo "==> [3/5] Pushing to ECR..."
docker tag $ECR_REPO:$IMAGE_TAG $IMAGE_URI
docker push $IMAGE_URI

# Also tag as latest for the task definition
docker tag $ECR_REPO:$IMAGE_TAG ${ECR_URI}:latest
docker push ${ECR_URI}:latest

# 4. Check ECR scan results
echo "==> [4/5] Checking image scan..."
echo "    (Scan runs asynchronously — check ECR console for results)"

# 5. Update task definition with new image and force deployment
echo "==> [5/5] Deploying to ECS..."

# Get current task definition
CURRENT_TASK_DEF=$(aws ecs describe-services \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION \
    --query 'services[0].taskDefinition' --output text)

echo "    Current task def: $CURRENT_TASK_DEF"

# Force new deployment
aws ecs update-service \
    --cluster $ECS_CLUSTER \
    --service $ECS_SERVICE \
    --force-new-deployment \
    --region $AWS_REGION > /dev/null

echo "    Deployment initiated. Waiting for stability..."

# Wait for service to stabilize (timeout: 10 minutes)
if aws ecs wait services-stable \
    --cluster $ECS_CLUSTER \
    --services $ECS_SERVICE \
    --region $AWS_REGION 2>/dev/null; then
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  DEPLOYMENT SUCCESSFUL"
    echo "══════════════════════════════════════════════"
    echo ""
    echo "  Image:  $IMAGE_URI"
    echo "  URL:    http://$ALB_DNS"
    echo "  Health: http://$ALB_DNS/health"
    echo ""
else
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  DEPLOYMENT FAILED — ROLLING BACK"
    echo "══════════════════════════════════════════════"
    echo ""

    # Rollback to previous task definition
    aws ecs update-service \
        --cluster $ECS_CLUSTER \
        --service $ECS_SERVICE \
        --task-definition $CURRENT_TASK_DEF \
        --force-new-deployment \
        --region $AWS_REGION > /dev/null

    echo "  Rolled back to: $CURRENT_TASK_DEF"
    echo "  Check logs: aws logs tail /ecs/${PROJECT}-backend --region $AWS_REGION"
    exit 1
fi
