#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# Neutramart — HTTPS Setup (ACM + Route 53 + ALB)
# ══════════════════════════════════════════════════════════════
# Prerequisites:
#   - setup.sh has been run (resources.env exists)
#   - Domain nutrasmart.in is registered and hosted in Route 53
#
# What this script does:
#   1. Requests an ACM certificate for nutrasmart.in + *.nutrasmart.in
#   2. Creates DNS validation records in Route 53
#   3. Waits for certificate validation
#   4. Adds HTTPS (443) listener to ALB
#   5. Redirects HTTP (80) → HTTPS (443)
#   6. Points domain to ALB via Route 53 alias record
#   7. Opens port 443 on ALB security group
#
# Usage:
#   cd neutramart_backend/ecs
#   chmod +x setup-https.sh
#   ./setup-https.sh
# ══════════════════════════════════════════════════════════════

DOMAIN="nutrasmart.in"
API_SUBDOMAIN="api.nutrasmart.in"
PROFILE="neutramart"

# Load resource IDs from setup
if [ ! -f resources.env ]; then
    echo "ERROR: resources.env not found. Run setup.sh first."
    exit 1
fi
source resources.env

echo "══════════════════════════════════════════════"
echo "  Setting up HTTPS for $DOMAIN"
echo "══════════════════════════════════════════════"
echo ""

# ──────────────────────────────────────────────
# 1. GET HOSTED ZONE ID
# ──────────────────────────────────────────────
echo "==> [1/7] Finding Route 53 Hosted Zone..."
HOSTED_ZONE_ID=$(aws route53 list-hosted-zones-by-name \
    --dns-name "$DOMAIN" \
    --query "HostedZones[?Name=='${DOMAIN}.'].Id" \
    --output text \
    --profile $PROFILE | sed 's|/hostedzone/||')

if [ -z "$HOSTED_ZONE_ID" ]; then
    echo "ERROR: Hosted zone for $DOMAIN not found in Route 53."
    exit 1
fi
echo "    Hosted Zone: $HOSTED_ZONE_ID"

# ──────────────────────────────────────────────
# 2. REQUEST ACM CERTIFICATE
# ──────────────────────────────────────────────
echo "==> [2/7] Requesting ACM Certificate..."

# Check if a certificate already exists
EXISTING_CERT=$(aws acm list-certificates \
    --region $AWS_REGION \
    --profile $PROFILE \
    --query "CertificateSummaryList[?DomainName=='${DOMAIN}'].CertificateArn" \
    --output text)

if [ -n "$EXISTING_CERT" ] && [ "$EXISTING_CERT" != "None" ]; then
    CERT_ARN="$EXISTING_CERT"
    echo "    Certificate already exists: $CERT_ARN"
else
    CERT_ARN=$(aws acm request-certificate \
        --domain-name "$DOMAIN" \
        --subject-alternative-names "*.${DOMAIN}" \
        --validation-method DNS \
        --region $AWS_REGION \
        --profile $PROFILE \
        --query 'CertificateArn' --output text)
    echo "    Certificate requested: $CERT_ARN"
fi

# ──────────────────────────────────────────────
# 3. CREATE DNS VALIDATION RECORDS
# ──────────────────────────────────────────────
echo "==> [3/7] Creating DNS validation records..."

# Wait a moment for ACM to generate validation details
sleep 5

VALIDATION_JSON=$(aws acm describe-certificate \
    --certificate-arn "$CERT_ARN" \
    --region $AWS_REGION \
    --profile $PROFILE \
    --query 'Certificate.DomainValidationOptions[0].ResourceRecord')

VALIDATION_NAME=$(echo "$VALIDATION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Name'])")
VALIDATION_VALUE=$(echo "$VALIDATION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Value'])")

echo "    Validation CNAME: $VALIDATION_NAME -> $VALIDATION_VALUE"

# Create the CNAME record for validation
aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --profile $PROFILE \
    --change-batch "{
        \"Changes\": [{
            \"Action\": \"UPSERT\",
            \"ResourceRecordSet\": {
                \"Name\": \"$VALIDATION_NAME\",
                \"Type\": \"CNAME\",
                \"TTL\": 300,
                \"ResourceRecords\": [{\"Value\": \"$VALIDATION_VALUE\"}]
            }
        }]
    }" > /dev/null

echo "    DNS validation record created."

# ──────────────────────────────────────────────
# 4. WAIT FOR CERTIFICATE VALIDATION
# ──────────────────────────────────────────────
echo "==> [4/7] Waiting for certificate validation (this may take 2-5 minutes)..."
aws acm wait certificate-validated \
    --certificate-arn "$CERT_ARN" \
    --region $AWS_REGION \
    --profile $PROFILE

echo "    Certificate validated!"

# ──────────────────────────────────────────────
# 5. OPEN PORT 443 ON ALB SECURITY GROUP
# ──────────────────────────────────────────────
echo "==> [5/7] Opening port 443 on ALB Security Group..."
aws ec2 authorize-security-group-ingress \
    --group-id "$ALB_SG" \
    --protocol tcp \
    --port 443 \
    --cidr 0.0.0.0/0 \
    --region $AWS_REGION \
    --profile $PROFILE > /dev/null 2>&1 || echo "    Port 443 already open."

echo "    ALB SG updated: inbound 443 from 0.0.0.0/0"

# ──────────────────────────────────────────────
# 6. ADD HTTPS LISTENER + REDIRECT HTTP
# ──────────────────────────────────────────────
echo "==> [6/7] Configuring ALB listeners..."

# Create HTTPS listener (443 -> target group)
HTTPS_LISTENER_ARN=$(aws elbv2 create-listener \
    --load-balancer-arn "$ALB_ARN" \
    --protocol HTTPS \
    --port 443 \
    --certificates CertificateArn="$CERT_ARN" \
    --ssl-policy ELBSecurityPolicy-TLS13-1-2-2021-06 \
    --default-actions Type=forward,TargetGroupArn="$TG_ARN" \
    --region $AWS_REGION \
    --profile $PROFILE \
    --query 'Listeners[0].ListenerArn' --output text)

echo "    HTTPS listener created: $HTTPS_LISTENER_ARN"

# Modify existing HTTP listener to redirect to HTTPS
HTTP_LISTENER_ARN=$(aws elbv2 describe-listeners \
    --load-balancer-arn "$ALB_ARN" \
    --region $AWS_REGION \
    --profile $PROFILE \
    --query "Listeners[?Port==\`80\`].ListenerArn" --output text)

aws elbv2 modify-listener \
    --listener-arn "$HTTP_LISTENER_ARN" \
    --default-actions 'Type=redirect,RedirectConfig={Protocol=HTTPS,Port=443,StatusCode=HTTP_301}' \
    --region $AWS_REGION \
    --profile $PROFILE > /dev/null

echo "    HTTP (80) now redirects to HTTPS (443)"

# ──────────────────────────────────────────────
# 7. POINT DOMAIN TO ALB
# ──────────────────────────────────────────────
echo "==> [7/7] Creating DNS records pointing to ALB..."

# Get ALB hosted zone ID (needed for alias records)
ALB_HOSTED_ZONE=$(aws elbv2 describe-load-balancers \
    --load-balancer-arns "$ALB_ARN" \
    --region $AWS_REGION \
    --profile $PROFILE \
    --query 'LoadBalancers[0].CanonicalHostedZoneId' --output text)

# Create alias records for both root domain and api subdomain
aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --profile $PROFILE \
    --change-batch "{
        \"Changes\": [
            {
                \"Action\": \"UPSERT\",
                \"ResourceRecordSet\": {
                    \"Name\": \"$DOMAIN\",
                    \"Type\": \"A\",
                    \"AliasTarget\": {
                        \"HostedZoneId\": \"$ALB_HOSTED_ZONE\",
                        \"DNSName\": \"$ALB_DNS\",
                        \"EvaluateTargetHealth\": true
                    }
                }
            },
            {
                \"Action\": \"UPSERT\",
                \"ResourceRecordSet\": {
                    \"Name\": \"$API_SUBDOMAIN\",
                    \"Type\": \"A\",
                    \"AliasTarget\": {
                        \"HostedZoneId\": \"$ALB_HOSTED_ZONE\",
                        \"DNSName\": \"$ALB_DNS\",
                        \"EvaluateTargetHealth\": true
                    }
                }
            }
        ]
    }" > /dev/null

echo "    $DOMAIN -> ALB"
echo "    $API_SUBDOMAIN -> ALB"

# ──────────────────────────────────────────────
# SAVE HTTPS RESOURCE IDS
# ──────────────────────────────────────────────
cat >> resources.env << EOF

# HTTPS resources (added by setup-https.sh)
CERT_ARN=$CERT_ARN
HTTPS_LISTENER_ARN=$HTTPS_LISTENER_ARN
HOSTED_ZONE_ID=$HOSTED_ZONE_ID
DOMAIN=$DOMAIN
API_SUBDOMAIN=$API_SUBDOMAIN
EOF

echo ""
echo "══════════════════════════════════════════════"
echo "  HTTPS SETUP COMPLETE"
echo "══════════════════════════════════════════════"
echo ""
echo "  Root:    https://$DOMAIN"
echo "  API:     https://$API_SUBDOMAIN"
echo "  Health:  https://$API_SUBDOMAIN/health"
echo ""
echo "  Certificate: $CERT_ARN"
echo "  SSL Policy:  ELBSecurityPolicy-TLS13-1-2-2021-06"
echo ""
echo "  Next steps:"
echo "    1. Update ALLOWED_ORIGINS in your backend to use https://"
echo "    2. Update your frontend API_URL to: https://$API_SUBDOMAIN"
echo "    3. DNS propagation may take a few minutes"
echo ""
echo "══════════════════════════════════════════════"
