#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# nutrasmart — build, push and deploy the edge to Fargate
# ══════════════════════════════════════════════════════════════
# Builds backend/ as an amd64 image tagged with the commit, registers a task-definition revision that
# runs exactly that image (task-definition.json filled from config.env), points the service at the
# new revision and waits for it to stabilize. If it does not, the service goes back to the revision it
# ran before. Every revision stays registered, so any earlier one can be redeployed by hand.
#
# Usage, from any directory:
#   AWS_PROFILE=<profile for EXPECTED_ACCOUNT_ID> backend/ecs/deploy.sh --plan   # read-only diff
#   AWS_PROFILE=<profile for EXPECTED_ACCOUNT_ID> backend/ecs/deploy.sh          # build and deploy
#
# The image is built from the working tree. Uncommitted changes to the build inputs below stop the
# deploy unless ALLOW_DIRTY=1, which tags the image <commit>-dirty-<UTC time> so it never passes for
# the commit.
# ══════════════════════════════════════════════════════════════

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

PLAN=false
case "${1:-}" in
    "") ;;
    --plan) PLAN=true ;;
    *) die "Usage: deploy.sh [--plan]" ;;
esac

# Needs only config.env and the account check, not resources.env: any machine with the profile can deploy.
require_aws_identity

ECS_CLUSTER="${PROJECT}-cluster"
ECS_SERVICE="${PROJECT}-backend-service"
BUILD_INPUTS=(backend/app backend/requirements.txt backend/Dockerfile backend/.dockerignore
    backend/ecs/task-definition.json backend/ecs/config.env)

IMAGE_TAG=$(git -C "$REPO_ROOT" rev-parse --short HEAD)
if [ -n "$(git -C "$REPO_ROOT" status --porcelain -- "${BUILD_INPUTS[@]}")" ]; then
    if [ "$PLAN" = false ] && [ "${ALLOW_DIRTY:-}" != 1 ]; then
        git -C "$REPO_ROOT" status --short -- "${BUILD_INPUTS[@]}" >&2
        die "Uncommitted changes to the build inputs above. Commit them, or set ALLOW_DIRTY=1."
    fi
    IMAGE_TAG="${IMAGE_TAG}-dirty-$(date -u +%Y%m%dT%H%M%SZ)"
fi
export IMAGE_TAG

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

render task-definition.json > "$WORK/new.json"
IMAGE_URI=$(python3 -c 'import json, sys; print(json.load(sys.stdin)["containerDefinitions"][0]["image"])' \
    < "$WORK/new.json")

CURRENT_TASK_DEF=$(aws ecs describe-services \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE" \
    --region "$AWS_REGION" \
    --query 'services[0].taskDefinition' --output text)
[ "$CURRENT_TASK_DEF" != "None" ] || die "Service $ECS_SERVICE not found in $ECS_CLUSTER."

aws ecs describe-task-definition \
    --task-definition "$CURRENT_TASK_DEF" \
    --region "$AWS_REGION" \
    --query taskDefinition --output json > "$WORK/live.json"

echo "══════════════════════════════════════════════"
echo "  Running: $CURRENT_TASK_DEF"
echo "  New:     $IMAGE_URI"
echo "══════════════════════════════════════════════"
python3 "$HELPERS" diff "$WORK/live.json" "$WORK/new.json"
echo ""

if [ "$PLAN" = true ]; then
    echo "Plan only: nothing was built, pushed or registered."
    exit 0
fi

echo "==> [1/5] Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | \
    docker login --username AWS --password-stdin "${IMAGE_URI%%/*}"

echo "==> [2/5] Building $IMAGE_URI (linux/amd64)..."
docker build --platform linux/amd64 -t "$IMAGE_URI" "$REPO_ROOT/backend"

# ECR scans every pushed image (scanOnPush); results:
#   aws ecr describe-image-scan-findings --repository-name ${PROJECT}-backend --image-id imageTag=<tag>
echo "==> [3/5] Pushing..."
docker push "$IMAGE_URI"

echo "==> [4/5] Registering the task definition..."
NEW_TASK_DEF=$(aws ecs register-task-definition \
    --cli-input-json "file://$WORK/new.json" \
    --region "$AWS_REGION" \
    --query 'taskDefinition.taskDefinitionArn' --output text)
echo "    $NEW_TASK_DEF"

echo "==> [5/5] Deploying and waiting for the service to stabilize (up to 10 minutes)..."
aws ecs update-service \
    --cluster "$ECS_CLUSTER" \
    --service "$ECS_SERVICE" \
    --task-definition "$NEW_TASK_DEF" \
    --region "$AWS_REGION" > /dev/null

if aws ecs wait services-stable \
    --cluster "$ECS_CLUSTER" \
    --services "$ECS_SERVICE" \
    --region "$AWS_REGION"; then
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  DEPLOYMENT SUCCESSFUL"
    echo "══════════════════════════════════════════════"
    echo ""
    echo "  Revision: $NEW_TASK_DEF"
    echo "  Image:    $IMAGE_URI"
    echo "  Previous: $CURRENT_TASK_DEF (redeploy it with update-service --task-definition to roll back)"
    echo "  Logs:     aws logs tail /ecs/${PROJECT}-backend --since 15m --region $AWS_REGION"
    echo ""
else
    echo ""
    echo "══════════════════════════════════════════════"
    echo "  DEPLOYMENT FAILED — ROLLING BACK"
    echo "══════════════════════════════════════════════"
    echo ""

    aws ecs update-service \
        --cluster "$ECS_CLUSTER" \
        --service "$ECS_SERVICE" \
        --task-definition "$CURRENT_TASK_DEF" \
        --region "$AWS_REGION" > /dev/null

    echo "  Service is going back to: $CURRENT_TASK_DEF"
    echo "  Failed revision (still registered): $NEW_TASK_DEF"
    echo "  Watch: aws ecs wait services-stable --cluster $ECS_CLUSTER --services $ECS_SERVICE --region $AWS_REGION"
    echo "  Logs:  aws logs tail /ecs/${PROJECT}-backend --since 15m --region $AWS_REGION"
    exit 1
fi
