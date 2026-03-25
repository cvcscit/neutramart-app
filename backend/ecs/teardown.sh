#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# nutrasmart — Teardown ALL Infrastructure
# ══════════════════════════════════════════════════════════════
# WARNING: This deletes everything created by setup.sh.
#          All data will be lost. This cannot be undone.
#
# Usage:
#   cd netrramart_backend/ecs
#   ./teardown.sh
# ══════════════════════════════════════════════════════════════

if [ ! -f resources.env ]; then
    echo "ERROR: resources.env not found. Nothing to tear down."
    exit 1
fi
source resources.env

echo "══════════════════════════════════════════════"
echo "  WARNING: This will DELETE all nutrasmart"
echo "  infrastructure in AWS. This cannot be undone."
echo "══════════════════════════════════════════════"
echo ""
read -p "Type 'DELETE' to confirm: " CONFIRM
if [ "$CONFIRM" != "DELETE" ]; then
    echo "Aborted."
    exit 0
fi

echo ""

# 1. Delete Auto Scaling
echo "==> Removing auto scaling..."
RESOURCE_ID="service/${PROJECT}-cluster/${PROJECT}-backend-service"
aws application-autoscaling deregister-scalable-target \
    --service-namespace ecs \
    --resource-id "$RESOURCE_ID" \
    --scalable-dimension ecs:service:DesiredCount \
    --region $AWS_REGION 2>/dev/null || true

# 2. Delete ECS Service (scale to 0 first)
echo "==> Deleting ECS service..."
aws ecs update-service \
    --cluster ${PROJECT}-cluster \
    --service ${PROJECT}-backend-service \
    --desired-count 0 \
    --region $AWS_REGION > /dev/null 2>/dev/null || true

aws ecs delete-service \
    --cluster ${PROJECT}-cluster \
    --service ${PROJECT}-backend-service \
    --force \
    --region $AWS_REGION > /dev/null 2>/dev/null || true

# 3. Delete ECS Cluster
echo "==> Deleting ECS cluster..."
aws ecs delete-cluster \
    --cluster ${PROJECT}-cluster \
    --region $AWS_REGION > /dev/null 2>/dev/null || true

# 4. Delete ALB, listener, target group
echo "==> Deleting ALB..."
# Delete listeners first
LISTENER_ARNS=$(aws elbv2 describe-listeners \
    --load-balancer-arn $ALB_ARN \
    --region $AWS_REGION \
    --query 'Listeners[*].ListenerArn' --output text 2>/dev/null || true)
for LISTENER in $LISTENER_ARNS; do
    aws elbv2 delete-listener --listener-arn $LISTENER --region $AWS_REGION 2>/dev/null || true
done

aws elbv2 delete-load-balancer --load-balancer-arn $ALB_ARN --region $AWS_REGION 2>/dev/null || true
echo "    Waiting for ALB to be deleted..."
sleep 30

aws elbv2 delete-target-group --target-group-arn $TG_ARN --region $AWS_REGION 2>/dev/null || true

# 5. Delete NAT Gateway
echo "==> Deleting NAT Gateway..."
aws ec2 delete-nat-gateway --nat-gateway-id $NAT_GW_ID --region $AWS_REGION > /dev/null 2>/dev/null || true
echo "    Waiting for NAT Gateway to be deleted..."
aws ec2 wait nat-gateway-deleted --nat-gateway-ids $NAT_GW_ID --region $AWS_REGION 2>/dev/null || sleep 60

# Release Elastic IP
aws ec2 release-address --allocation-id $EIP_ALLOC --region $AWS_REGION 2>/dev/null || true

# 6. Delete subnets and route tables
echo "==> Deleting subnets and route tables..."

# Disassociate and delete route tables
for RT in $PUB_RT $PRIV_RT; do
    ASSOC_IDS=$(aws ec2 describe-route-tables \
        --route-table-ids $RT \
        --region $AWS_REGION \
        --query 'RouteTables[0].Associations[?!Main].RouteTableAssociationId' --output text 2>/dev/null || true)
    for ASSOC in $ASSOC_IDS; do
        aws ec2 disassociate-route-table --association-id $ASSOC --region $AWS_REGION 2>/dev/null || true
    done
    aws ec2 delete-route-table --route-table-id $RT --region $AWS_REGION 2>/dev/null || true
done

# Delete subnets
for SUBNET in $PUB_SUBNET_1 $PUB_SUBNET_2 $PRIV_SUBNET_1 $PRIV_SUBNET_2; do
    aws ec2 delete-subnet --subnet-id $SUBNET --region $AWS_REGION 2>/dev/null || true
done

# 7. Detach and delete Internet Gateway
echo "==> Deleting Internet Gateway..."
aws ec2 detach-internet-gateway --internet-gateway-id $IGW_ID --vpc-id $VPC_ID --region $AWS_REGION 2>/dev/null || true
aws ec2 delete-internet-gateway --internet-gateway-id $IGW_ID --region $AWS_REGION 2>/dev/null || true

# 8. Delete security groups
echo "==> Deleting security groups..."
aws ec2 delete-security-group --group-id $FARGATE_SG --region $AWS_REGION 2>/dev/null || true
aws ec2 delete-security-group --group-id $ALB_SG --region $AWS_REGION 2>/dev/null || true

# 9. Delete VPC
echo "==> Deleting VPC..."
aws ec2 delete-vpc --vpc-id $VPC_ID --region $AWS_REGION 2>/dev/null || true

# 10. Delete IAM roles
echo "==> Deleting IAM roles..."
aws iam delete-role-policy --role-name ${PROJECT}-ecs-task-role --policy-name ${PROJECT}-s3-bedrock 2>/dev/null || true
aws iam delete-role --role-name ${PROJECT}-ecs-task-role 2>/dev/null || true

aws iam delete-role-policy --role-name ${PROJECT}-ecs-execution-role --policy-name ${PROJECT}-ssm-read 2>/dev/null || true
aws iam detach-role-policy --role-name ${PROJECT}-ecs-execution-role \
    --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy 2>/dev/null || true
aws iam delete-role --role-name ${PROJECT}-ecs-execution-role 2>/dev/null || true

# 11. Delete ECR repository
echo "==> Deleting ECR repository..."
aws ecr delete-repository \
    --repository-name ${PROJECT}-backend \
    --force \
    --region $AWS_REGION > /dev/null 2>/dev/null || true

# 12. Delete CloudWatch log group
echo "==> Deleting CloudWatch log group..."
aws logs delete-log-group --log-group-name /ecs/${PROJECT}-backend --region $AWS_REGION 2>/dev/null || true

# 13. Delete SSM parameters
echo "==> Deleting SSM parameters..."
aws ssm delete-parameter --name "/${PROJECT}/google-client-id" --region $AWS_REGION 2>/dev/null || true

# Cleanup
rm -f resources.env

echo ""
echo "══════════════════════════════════════════════"
echo "  TEARDOWN COMPLETE"
echo "  All nutrasmart infrastructure has been deleted."
echo "══════════════════════════════════════════════"
