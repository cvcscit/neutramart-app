#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# nutrasmart — Production Fargate Infrastructure Setup
# ══════════════════════════════════════════════════════════════
# This script creates ALL AWS resources from scratch:
#   VPC, Subnets, IGW, NAT GW, ALB, Security Groups,
#   IAM Roles, ECR, CloudWatch, ECS Cluster + Service + AutoScaling
#
# Prerequisites:
#   - AWS CLI v2 installed and configured
#   - Docker installed
#   - jq installed (brew install jq)
#
# Usage:
#   chmod +x setup.sh
#   ./setup.sh
# ══════════════════════════════════════════════════════════════

AWS_REGION="ap-south-1"
PROJECT="nutrasmart"

# Auto-detect AWS Account ID
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo "==> AWS Account: $AWS_ACCOUNT_ID"
echo "==> Region: $AWS_REGION"
echo ""

# ──────────────────────────────────────────────
# 1. VPC + NETWORKING
# ──────────────────────────────────────────────
echo "==> [1/12] Creating VPC..."
VPC_ID=$(aws ec2 create-vpc \
    --cidr-block 10.0.0.0/16 \
    --tag-specifications "ResourceType=vpc,Tags=[{Key=Name,Value=${PROJECT}-vpc}]" \
    --region $AWS_REGION \
    --query 'Vpc.VpcId' --output text)
echo "    VPC: $VPC_ID"

# Enable DNS hostnames (required for ALB)
aws ec2 modify-vpc-attribute --vpc-id $VPC_ID --enable-dns-hostnames '{"Value":true}' --region $AWS_REGION

# Get availability zones
AZ1=$(aws ec2 describe-availability-zones --region $AWS_REGION --query 'AvailabilityZones[0].ZoneName' --output text)
AZ2=$(aws ec2 describe-availability-zones --region $AWS_REGION --query 'AvailabilityZones[1].ZoneName' --output text)
echo "    AZs: $AZ1, $AZ2"

# Public subnets (for ALB)
echo "==> [2/12] Creating subnets..."
PUB_SUBNET_1=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID --cidr-block 10.0.1.0/24 --availability-zone $AZ1 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT}-public-1}]" \
    --region $AWS_REGION --query 'Subnet.SubnetId' --output text)

PUB_SUBNET_2=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID --cidr-block 10.0.2.0/24 --availability-zone $AZ2 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT}-public-2}]" \
    --region $AWS_REGION --query 'Subnet.SubnetId' --output text)

# Private subnets (for Fargate tasks)
PRIV_SUBNET_1=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID --cidr-block 10.0.3.0/24 --availability-zone $AZ1 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT}-private-1}]" \
    --region $AWS_REGION --query 'Subnet.SubnetId' --output text)

PRIV_SUBNET_2=$(aws ec2 create-subnet \
    --vpc-id $VPC_ID --cidr-block 10.0.4.0/24 --availability-zone $AZ2 \
    --tag-specifications "ResourceType=subnet,Tags=[{Key=Name,Value=${PROJECT}-private-2}]" \
    --region $AWS_REGION --query 'Subnet.SubnetId' --output text)

echo "    Public:  $PUB_SUBNET_1, $PUB_SUBNET_2"
echo "    Private: $PRIV_SUBNET_1, $PRIV_SUBNET_2"

# Internet Gateway
echo "==> [3/12] Creating Internet Gateway + NAT Gateway..."
IGW_ID=$(aws ec2 create-internet-gateway \
    --tag-specifications "ResourceType=internet-gateway,Tags=[{Key=Name,Value=${PROJECT}-igw}]" \
    --region $AWS_REGION --query 'InternetGateway.InternetGatewayId' --output text)
aws ec2 attach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID --region $AWS_REGION

# Public route table
PUB_RT=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT}-public-rt}]" \
    --region $AWS_REGION --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PUB_RT --destination-cidr-block 0.0.0.0/0 --gateway-id $IGW_ID --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $PUB_RT --subnet-id $PUB_SUBNET_1 --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $PUB_RT --subnet-id $PUB_SUBNET_2 --region $AWS_REGION > /dev/null

# Elastic IP for NAT Gateway
EIP_ALLOC=$(aws ec2 allocate-address --domain vpc --region $AWS_REGION --query 'AllocationId' --output text)

# NAT Gateway (in public subnet, used by private subnets for outbound)
NAT_GW_ID=$(aws ec2 create-nat-gateway \
    --subnet-id $PUB_SUBNET_1 --allocation-id $EIP_ALLOC \
    --tag-specifications "ResourceType=natgateway,Tags=[{Key=Name,Value=${PROJECT}-nat}]" \
    --region $AWS_REGION --query 'NatGateway.NatGatewayId' --output text)

echo "    IGW: $IGW_ID"
echo "    NAT: $NAT_GW_ID (waiting for it to become available...)"
aws ec2 wait nat-gateway-available --nat-gateway-ids $NAT_GW_ID --region $AWS_REGION
echo "    NAT Gateway is ready."

# Private route table (routes outbound through NAT)
PRIV_RT=$(aws ec2 create-route-table \
    --vpc-id $VPC_ID \
    --tag-specifications "ResourceType=route-table,Tags=[{Key=Name,Value=${PROJECT}-private-rt}]" \
    --region $AWS_REGION --query 'RouteTable.RouteTableId' --output text)
aws ec2 create-route --route-table-id $PRIV_RT --destination-cidr-block 0.0.0.0/0 --nat-gateway-id $NAT_GW_ID --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $PRIV_RT --subnet-id $PRIV_SUBNET_1 --region $AWS_REGION > /dev/null
aws ec2 associate-route-table --route-table-id $PRIV_RT --subnet-id $PRIV_SUBNET_2 --region $AWS_REGION > /dev/null

# ──────────────────────────────────────────────
# 2. SECURITY GROUPS
# ──────────────────────────────────────────────
echo "==> [4/12] Creating Security Groups..."

# ALB Security Group — allows HTTP (80) from anywhere
ALB_SG=$(aws ec2 create-security-group \
    --group-name ${PROJECT}-alb-sg \
    --description "ALB - allow HTTP from internet" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress \
    --group-id $ALB_SG --protocol tcp --port 80 --cidr 0.0.0.0/0 --region $AWS_REGION > /dev/null
aws ec2 create-tags --resources $ALB_SG --tags Key=Name,Value=${PROJECT}-alb-sg --region $AWS_REGION

# Fargate Security Group — allows 8000 ONLY from ALB SG
FARGATE_SG=$(aws ec2 create-security-group \
    --group-name ${PROJECT}-fargate-sg \
    --description "Fargate - allow 8000 from ALB only" \
    --vpc-id $VPC_ID \
    --region $AWS_REGION --query 'GroupId' --output text)
aws ec2 authorize-security-group-ingress \
    --group-id $FARGATE_SG --protocol tcp --port 8000 --source-group $ALB_SG --region $AWS_REGION > /dev/null
aws ec2 create-tags --resources $FARGATE_SG --tags Key=Name,Value=${PROJECT}-fargate-sg --region $AWS_REGION

echo "    ALB SG:     $ALB_SG (inbound: 80 from 0.0.0.0/0)"
echo "    Fargate SG: $FARGATE_SG (inbound: 8000 from ALB SG only)"

# ──────────────────────────────────────────────
# 3. APPLICATION LOAD BALANCER
# ──────────────────────────────────────────────
echo "==> [5/12] Creating Application Load Balancer..."

ALB_ARN=$(aws elbv2 create-load-balancer \
    --name ${PROJECT}-alb \
    --subnets $PUB_SUBNET_1 $PUB_SUBNET_2 \
    --security-groups $ALB_SG \
    --scheme internet-facing \
    --type application \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].LoadBalancerArn' --output text)

ALB_DNS=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns $ALB_ARN \
    --region $AWS_REGION \
    --query 'LoadBalancers[0].DNSName' --output text)

echo "    ALB ARN: $ALB_ARN"
echo "    ALB DNS: $ALB_DNS"

# Target Group
TG_ARN=$(aws elbv2 create-target-group \
    --name ${PROJECT}-tg \
    --protocol HTTP \
    --port 8000 \
    --vpc-id $VPC_ID \
    --target-type ip \
    --health-check-path /health \
    --health-check-interval-seconds 30 \
    --health-check-timeout-seconds 5 \
    --healthy-threshold-count 2 \
    --unhealthy-threshold-count 3 \
    --region $AWS_REGION \
    --query 'TargetGroups[0].TargetGroupArn' --output text)

echo "    Target Group: $TG_ARN"

# HTTP Listener
aws elbv2 create-listener \
    --load-balancer-arn $ALB_ARN \
    --protocol HTTP \
    --port 80 \
    --default-actions Type=forward,TargetGroupArn=$TG_ARN \
    --region $AWS_REGION > /dev/null

echo "    Listener: HTTP:80 -> Target Group"

# ──────────────────────────────────────────────
# 4. IAM ROLES
# ──────────────────────────────────────────────
echo "==> [6/12] Creating IAM Roles..."

# Task Execution Role (ECR pull + CloudWatch logs + SSM read)
cat > /tmp/ecs-trust-policy.json << 'POLICY'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "ecs-tasks.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
POLICY

EXEC_ROLE_ARN=$(aws iam create-role \
    --role-name ${PROJECT}-ecs-execution-role \
    --assume-role-policy-document file:///tmp/ecs-trust-policy.json \
    --query 'Role.Arn' --output text 2>/dev/null || \
    aws iam get-role --role-name ${PROJECT}-ecs-execution-role --query 'Role.Arn' --output text)

aws iam attach-role-policy \
    --role-name ${PROJECT}-ecs-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true

# SSM read permission for execution role (to inject GOOGLE_CLIENT_ID)
cat > /tmp/ssm-read-policy.json << POLICY
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["ssm:GetParameters", "ssm:GetParameter"],
    "Resource": "arn:aws:ssm:${AWS_REGION}:${AWS_ACCOUNT_ID}:parameter/${PROJECT}/*"
  }]
}
POLICY

aws iam put-role-policy \
    --role-name ${PROJECT}-ecs-execution-role \
    --policy-name ${PROJECT}-ssm-read \
    --policy-document file:///tmp/ssm-read-policy.json

echo "    Execution Role: $EXEC_ROLE_ARN"

# Task Role (S3 + Bedrock — this is what the running container uses)
TASK_ROLE_ARN=$(aws iam create-role \
    --role-name ${PROJECT}-ecs-task-role \
    --assume-role-policy-document file:///tmp/ecs-trust-policy.json \
    --query 'Role.Arn' --output text 2>/dev/null || \
    aws iam get-role --role-name ${PROJECT}-ecs-task-role --query 'Role.Arn' --output text)

cat > /tmp/task-policy.json << POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "S3Access",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::sci-neutrasmart-project/*"
    },
    {
      "Sid": "S3Presign",
      "Effect": "Allow",
      "Action": [
        "s3:GetBucketLocation"
      ],
      "Resource": "arn:aws:s3:::sci-neutrasmart-project"
    },
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel"
      ],
      "Resource": "*"
    }
  ]
}
POLICY

aws iam put-role-policy \
    --role-name ${PROJECT}-ecs-task-role \
    --policy-name ${PROJECT}-s3-bedrock \
    --policy-document file:///tmp/task-policy.json

echo "    Task Role: $TASK_ROLE_ARN"

# ──────────────────────────────────────────────
# 5. ECR REPOSITORY
# ──────────────────────────────────────────────
echo "==> [7/12] Creating ECR Repository..."
aws ecr create-repository \
    --repository-name ${PROJECT}-backend \
    --image-scanning-configuration scanOnPush=true \
    --region $AWS_REGION 2>/dev/null || echo "    ECR repo already exists"

ECR_URI="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/${PROJECT}-backend"
echo "    ECR: $ECR_URI"

# ──────────────────────────────────────────────
# 6. CLOUDWATCH LOG GROUP
# ──────────────────────────────────────────────
echo "==> [8/12] Creating CloudWatch Log Group..."
aws logs create-log-group \
    --log-group-name /ecs/${PROJECT}-backend \
    --region $AWS_REGION 2>/dev/null || echo "    Log group already exists"

aws logs put-retention-policy \
    --log-group-name /ecs/${PROJECT}-backend \
    --retention-in-days 30 \
    --region $AWS_REGION

echo "    Log group: /ecs/${PROJECT}-backend (30-day retention)"

# ──────────────────────────────────────────────
# 7. SSM — STORE GOOGLE CLIENT ID
# ──────────────────────────────────────────────
echo "==> [9/12] Storing Google Client ID in SSM..."
read -p "Enter your Google OAuth Client ID: " GOOGLE_CID
aws ssm put-parameter \
    --name "/${PROJECT}/google-client-id" \
    --value "$GOOGLE_CID" \
    --type SecureString \
    --region $AWS_REGION --overwrite > /dev/null
echo "    Stored as /${PROJECT}/google-client-id"

# ──────────────────────────────────────────────
# 8. ECS CLUSTER
# ──────────────────────────────────────────────
echo "==> [10/12] Creating ECS Cluster..."
aws ecs create-cluster \
    --cluster-name ${PROJECT}-cluster \
    --region $AWS_REGION > /dev/null 2>/dev/null || echo "    Cluster already exists"
echo "    Cluster: ${PROJECT}-cluster"

# ──────────────────────────────────────────────
# 9. REGISTER TASK DEFINITION
# ──────────────────────────────────────────────
echo "==> [11/12] Registering Task Definition..."

# Generate task definition with real values
TASK_DEF=$(cat task-definition.json | \
    sed "s|<ACCOUNT_ID>|${AWS_ACCOUNT_ID}|g" | \
    sed "s|<AWS_REGION>|${AWS_REGION}|g" | \
    sed "s|<ALB_DNS>|${ALB_DNS}|g")

echo "$TASK_DEF" | aws ecs register-task-definition \
    --cli-input-json file:///dev/stdin \
    --region $AWS_REGION > /dev/null

echo "    Task definition registered"

# ──────────────────────────────────────────────
# 10. ECS SERVICE + AUTO SCALING
# ──────────────────────────────────────────────
echo "==> [12/12] Creating ECS Service + Auto Scaling..."

aws ecs create-service \
    --cluster ${PROJECT}-cluster \
    --service-name ${PROJECT}-backend-service \
    --task-definition ${PROJECT}-backend \
    --desired-count 1 \
    --launch-type FARGATE \
    --network-configuration "awsvpcConfiguration={subnets=[$PRIV_SUBNET_1,$PRIV_SUBNET_2],securityGroups=[$FARGATE_SG],assignPublicIp=DISABLED}" \
    --load-balancers "targetGroupArn=$TG_ARN,containerName=${PROJECT}-backend,containerPort=8000" \
    --health-check-grace-period-seconds 60 \
    --region $AWS_REGION > /dev/null

echo "    Service created (desired: 1 task)"

# Auto Scaling — scale 1 to 4 based on CPU
RESOURCE_ID="service/${PROJECT}-cluster/${PROJECT}-backend-service"

aws application-autoscaling register-scalable-target \
    --service-namespace ecs \
    --resource-id "$RESOURCE_ID" \
    --scalable-dimension ecs:service:DesiredCount \
    --min-capacity 1 \
    --max-capacity 4 \
    --region $AWS_REGION > /dev/null

aws application-autoscaling put-scaling-policy \
    --service-namespace ecs \
    --resource-id "$RESOURCE_ID" \
    --scalable-dimension ecs:service:DesiredCount \
    --policy-name ${PROJECT}-cpu-scaling \
    --policy-type TargetTrackingScaling \
    --target-tracking-scaling-policy-configuration '{
        "TargetValue": 70.0,
        "PredefinedMetricSpecification": {
            "PredefinedMetricType": "ECSServiceAverageCPUUtilization"
        },
        "ScaleOutCooldown": 60,
        "ScaleInCooldown": 120
    }' \
    --region $AWS_REGION > /dev/null

echo "    Auto Scaling: 1-4 tasks, target 70% CPU"

# ──────────────────────────────────────────────
# SAVE RESOURCE IDS FOR TEARDOWN
# ──────────────────────────────────────────────
cat > resources.env << EOF
# Auto-generated by setup.sh — used by teardown.sh
VPC_ID=$VPC_ID
PUB_SUBNET_1=$PUB_SUBNET_1
PUB_SUBNET_2=$PUB_SUBNET_2
PRIV_SUBNET_1=$PRIV_SUBNET_1
PRIV_SUBNET_2=$PRIV_SUBNET_2
IGW_ID=$IGW_ID
NAT_GW_ID=$NAT_GW_ID
EIP_ALLOC=$EIP_ALLOC
PUB_RT=$PUB_RT
PRIV_RT=$PRIV_RT
ALB_SG=$ALB_SG
FARGATE_SG=$FARGATE_SG
ALB_ARN=$ALB_ARN
ALB_DNS=$ALB_DNS
TG_ARN=$TG_ARN
EXEC_ROLE_ARN=$EXEC_ROLE_ARN
TASK_ROLE_ARN=$TASK_ROLE_ARN
ECR_URI=$ECR_URI
AWS_ACCOUNT_ID=$AWS_ACCOUNT_ID
AWS_REGION=$AWS_REGION
PROJECT=$PROJECT
EOF

echo ""
echo "══════════════════════════════════════════════"
echo "  SETUP COMPLETE"
echo "══════════════════════════════════════════════"
echo ""
echo "  ALB URL:  http://$ALB_DNS"
echo "  Health:   http://$ALB_DNS/health"
echo ""
echo "  Next steps:"
echo "    1. Run ./deploy.sh to build and deploy"
echo "    2. Update your frontend API_URL to: http://$ALB_DNS"
echo ""
echo "  Resource IDs saved to: ecs/resources.env"
echo "══════════════════════════════════════════════"
