#!/bin/bash
set -e

# ──────────────────────────────────────────────
# One-time ECS Fargate setup
# Replace <ACCOUNT_ID> with your AWS account ID
# Replace <SUBNET_1>, <SUBNET_2>, <SG_ID> with your VPC values
# ──────────────────────────────────────────────
AWS_ACCOUNT_ID="<ACCOUNT_ID>"
AWS_REGION="ap-south-1"
ECR_REPO="neutramart-backend"
ECS_CLUSTER="neutramart-cluster"
ECS_SERVICE="neutramart-backend-service"

# 1. Create ECR repository
echo "==> Creating ECR repository..."
aws ecr create-repository \
  --repository-name $ECR_REPO \
  --region $AWS_REGION 2>/dev/null || echo "ECR repo already exists"

# 2. Create CloudWatch log group
echo "==> Creating CloudWatch log group..."
aws logs create-log-group \
  --log-group-name /ecs/neutramart-backend \
  --region $AWS_REGION 2>/dev/null || echo "Log group already exists"

# 3. Store secrets in SSM Parameter Store
echo "==> Storing secrets in SSM (you'll be prompted)..."
read -p "Enter AWS_ACCESS_KEY_ID for S3: " S3_KEY_ID
aws ssm put-parameter \
  --name "/neutramart/aws-access-key-id" \
  --value "$S3_KEY_ID" \
  --type SecureString \
  --region $AWS_REGION --overwrite

read -sp "Enter AWS_SECRET_ACCESS_KEY for S3: " S3_SECRET
echo
aws ssm put-parameter \
  --name "/neutramart/aws-secret-access-key" \
  --value "$S3_SECRET" \
  --type SecureString \
  --region $AWS_REGION --overwrite

# 4. Create ECS cluster
echo "==> Creating ECS cluster..."
aws ecs create-cluster \
  --cluster-name $ECS_CLUSTER \
  --region $AWS_REGION 2>/dev/null || echo "Cluster already exists"

# 5. Register task definition
echo "==> Registering task definition..."
TASK_DEF=$(sed "s/<ACCOUNT_ID>/$AWS_ACCOUNT_ID/g" task-definition.json)
echo "$TASK_DEF" | aws ecs register-task-definition \
  --cli-input-json file:///dev/stdin \
  --region $AWS_REGION

# 6. Create the service
echo "==> Creating ECS service..."
echo "NOTE: Replace <SUBNET_1>, <SUBNET_2>, <SG_ID> below with your VPC values"
aws ecs create-service \
  --cluster $ECS_CLUSTER \
  --service-name $ECS_SERVICE \
  --task-definition neutramart-backend \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[<SUBNET_1>,<SUBNET_2>],securityGroups=[<SG_ID>],assignPublicIp=ENABLED}" \
  --region $AWS_REGION

echo ""
echo "==> Setup complete!"
echo "Next steps:"
echo "  1. Replace <SUBNET_1>, <SUBNET_2>, <SG_ID> in the create-service command above"
echo "  2. Run deploy.sh to build, push, and deploy"
echo "  3. (Optional) Add an ALB for HTTPS and load balancing"
