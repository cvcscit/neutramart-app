#!/bin/bash
set -euo pipefail

# ══════════════════════════════════════════════════════════════
# Neutramart — Deploy Frontend to S3 + CloudFront
# ══════════════════════════════════════════════════════════════
# What this script does:
#   1. Builds the Vite/React frontend
#   2. Creates an S3 bucket for static hosting
#   3. Requests ACM cert in us-east-1 (required by CloudFront)
#   4. Creates CloudFront distribution
#   5. Points nutrasmart.in to CloudFront
#   6. Uploads build files to S3
#
# Usage:
#   cd neutramart_ui
#   chmod +x deploy-frontend.sh
#   ./deploy-frontend.sh
# ══════════════════════════════════════════════════════════════

DOMAIN="nutrasmart.in"
S3_BUCKET="nutrasmart-frontend"
AWS_REGION="ap-south-1"
PROFILE="neutramart"
HOSTED_ZONE_ID="Z05944272T7ZXS3L3CYCR"

export AWS_PROFILE="$PROFILE"

echo "══════════════════════════════════════════════"
echo "  Deploying Neutramart Frontend"
echo "══════════════════════════════════════════════"
echo ""

# ──────────────────────────────────────────────
# 1. BUILD FRONTEND
# ──────────────────────────────────────────────
echo "==> [1/7] Building frontend..."
npm run build
echo "    Build complete: dist/"

# ──────────────────────────────────────────────
# 2. CREATE S3 BUCKET
# ──────────────────────────────────────────────
echo "==> [2/7] Creating S3 bucket..."
if aws s3api head-bucket --bucket "$S3_BUCKET" --region $AWS_REGION 2>/dev/null; then
    echo "    Bucket already exists: $S3_BUCKET"
else
    aws s3api create-bucket \
        --bucket "$S3_BUCKET" \
        --region $AWS_REGION \
        --create-bucket-configuration LocationConstraint=$AWS_REGION > /dev/null
    echo "    Created bucket: $S3_BUCKET"
fi

# Block public access (CloudFront will use OAC)
aws s3api put-public-access-block \
    --bucket "$S3_BUCKET" \
    --public-access-block-configuration \
    "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true" > /dev/null

echo "    Public access blocked (CloudFront OAC will be used)"

# ──────────────────────────────────────────────
# 3. ACM CERTIFICATE IN US-EAST-1
# ──────────────────────────────────────────────
echo "==> [3/7] Requesting ACM certificate in us-east-1 (required by CloudFront)..."

EXISTING_CERT=$(aws acm list-certificates \
    --region us-east-1 \
    --query "CertificateSummaryList[?DomainName=='${DOMAIN}'].CertificateArn" \
    --output text)

if [ -n "$EXISTING_CERT" ] && [ "$EXISTING_CERT" != "None" ]; then
    CF_CERT_ARN="$EXISTING_CERT"
    echo "    Certificate already exists: $CF_CERT_ARN"
else
    CF_CERT_ARN=$(aws acm request-certificate \
        --domain-name "$DOMAIN" \
        --subject-alternative-names "*.${DOMAIN}" \
        --validation-method DNS \
        --region us-east-1 \
        --query 'CertificateArn' --output text)
    echo "    Certificate requested: $CF_CERT_ARN"

    # Wait for validation details
    sleep 5

    VALIDATION_JSON=$(aws acm describe-certificate \
        --certificate-arn "$CF_CERT_ARN" \
        --region us-east-1 \
        --query 'Certificate.DomainValidationOptions[0].ResourceRecord')

    VALIDATION_NAME=$(echo "$VALIDATION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Name'])")
    VALIDATION_VALUE=$(echo "$VALIDATION_JSON" | python3 -c "import sys,json; print(json.load(sys.stdin)['Value'])")

    # Create DNS validation record (may already exist from ap-south-1 cert)
    aws route53 change-resource-record-sets \
        --hosted-zone-id "$HOSTED_ZONE_ID" \
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

    echo "    Waiting for certificate validation..."
    aws acm wait certificate-validated \
        --certificate-arn "$CF_CERT_ARN" \
        --region us-east-1
    echo "    Certificate validated!"
fi

# ──────────────────────────────────────────────
# 4. CREATE CLOUDFRONT OAC
# ──────────────────────────────────────────────
echo "==> [4/7] Creating CloudFront Origin Access Control..."

OAC_ID=$(aws cloudfront list-origin-access-controls \
    --query "OriginAccessControlList.Items[?Name=='${S3_BUCKET}-oac'].Id" \
    --output text)

if [ -n "$OAC_ID" ] && [ "$OAC_ID" != "None" ]; then
    echo "    OAC already exists: $OAC_ID"
else
    OAC_ID=$(aws cloudfront create-origin-access-control \
        --origin-access-control-config "{
            \"Name\": \"${S3_BUCKET}-oac\",
            \"Description\": \"OAC for ${S3_BUCKET}\",
            \"SigningProtocol\": \"sigv4\",
            \"SigningBehavior\": \"always\",
            \"OriginAccessControlOriginType\": \"s3\"
        }" \
        --query 'OriginAccessControl.Id' --output text)
    echo "    Created OAC: $OAC_ID"
fi

# ──────────────────────────────────────────────
# 5. CREATE CLOUDFRONT DISTRIBUTION
# ──────────────────────────────────────────────
echo "==> [5/7] Creating CloudFront distribution..."

# Check if distribution already exists for this domain
EXISTING_DIST=$(aws cloudfront list-distributions \
    --query "DistributionList.Items[?Aliases.Items[0]=='${DOMAIN}'].Id" \
    --output text 2>/dev/null)

if [ -n "$EXISTING_DIST" ] && [ "$EXISTING_DIST" != "None" ]; then
    CF_DIST_ID="$EXISTING_DIST"
    CF_DOMAIN=$(aws cloudfront get-distribution \
        --id "$CF_DIST_ID" \
        --query 'Distribution.DomainName' --output text)
    echo "    Distribution already exists: $CF_DIST_ID ($CF_DOMAIN)"
else
    S3_ORIGIN="${S3_BUCKET}.s3.${AWS_REGION}.amazonaws.com"

    CF_RESULT=$(aws cloudfront create-distribution \
        --distribution-config "{
            \"CallerReference\": \"${S3_BUCKET}-$(date +%s)\",
            \"Aliases\": {
                \"Quantity\": 1,
                \"Items\": [\"${DOMAIN}\"]
            },
            \"DefaultRootObject\": \"index.html\",
            \"Origins\": {
                \"Quantity\": 1,
                \"Items\": [{
                    \"Id\": \"S3-${S3_BUCKET}\",
                    \"DomainName\": \"${S3_ORIGIN}\",
                    \"OriginAccessControlId\": \"${OAC_ID}\",
                    \"S3OriginConfig\": {
                        \"OriginAccessIdentity\": \"\"
                    }
                }]
            },
            \"DefaultCacheBehavior\": {
                \"TargetOriginId\": \"S3-${S3_BUCKET}\",
                \"ViewerProtocolPolicy\": \"redirect-to-https\",
                \"AllowedMethods\": {
                    \"Quantity\": 2,
                    \"Items\": [\"GET\", \"HEAD\"]
                },
                \"CachePolicyId\": \"658327ea-f89d-4fab-a63d-7e88639e58f6\",
                \"Compress\": true
            },
            \"CustomErrorResponses\": {
                \"Quantity\": 1,
                \"Items\": [{
                    \"ErrorCode\": 403,
                    \"ResponsePagePath\": \"/index.html\",
                    \"ResponseCode\": \"200\",
                    \"ErrorCachingMinTTL\": 10
                }]
            },
            \"ViewerCertificate\": {
                \"ACMCertificateArn\": \"${CF_CERT_ARN}\",
                \"SSLSupportMethod\": \"sni-only\",
                \"MinimumProtocolVersion\": \"TLSv1.2_2021\"
            },
            \"Comment\": \"Neutramart Frontend\",
            \"Enabled\": true,
            \"HttpVersion\": \"http2and3\",
            \"PriceClass\": \"PriceClass_200\"
        }" \
        --query 'Distribution.{Id:Id,DomainName:DomainName}' --output json)

    CF_DIST_ID=$(echo "$CF_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['Id'])")
    CF_DOMAIN=$(echo "$CF_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['DomainName'])")
    echo "    Created distribution: $CF_DIST_ID"
    echo "    CloudFront domain: $CF_DOMAIN"
fi

# ──────────────────────────────────────────────
# 5b. S3 BUCKET POLICY FOR CLOUDFRONT
# ──────────────────────────────────────────────
echo "    Setting S3 bucket policy for CloudFront..."
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

aws s3api put-bucket-policy \
    --bucket "$S3_BUCKET" \
    --policy "{
        \"Version\": \"2012-10-17\",
        \"Statement\": [{
            \"Sid\": \"AllowCloudFrontServicePrincipal\",
            \"Effect\": \"Allow\",
            \"Principal\": {
                \"Service\": \"cloudfront.amazonaws.com\"
            },
            \"Action\": \"s3:GetObject\",
            \"Resource\": \"arn:aws:s3:::${S3_BUCKET}/*\",
            \"Condition\": {
                \"StringEquals\": {
                    \"AWS:SourceArn\": \"arn:aws:cloudfront::${AWS_ACCOUNT_ID}:distribution/${CF_DIST_ID}\"
                }
            }
        }]
    }"

echo "    Bucket policy set."

# ──────────────────────────────────────────────
# 6. UPDATE DNS — POINT DOMAIN TO CLOUDFRONT
# ──────────────────────────────────────────────
echo "==> [6/7] Updating DNS records..."

aws route53 change-resource-record-sets \
    --hosted-zone-id "$HOSTED_ZONE_ID" \
    --change-batch "{
        \"Changes\": [{
            \"Action\": \"UPSERT\",
            \"ResourceRecordSet\": {
                \"Name\": \"${DOMAIN}\",
                \"Type\": \"A\",
                \"AliasTarget\": {
                    \"HostedZoneId\": \"Z2FDTNDATAQYW2\",
                    \"DNSName\": \"${CF_DOMAIN}\",
                    \"EvaluateTargetHealth\": false
                }
            }
        }]
    }" > /dev/null

echo "    $DOMAIN -> CloudFront ($CF_DOMAIN)"

# ──────────────────────────────────────────────
# 7. UPLOAD BUILD FILES TO S3
# ──────────────────────────────────────────────
echo "==> [7/7] Uploading build files to S3..."
aws s3 sync dist/ "s3://${S3_BUCKET}/" \
    --delete \
    --cache-control "public, max-age=31536000, immutable" \
    --region $AWS_REGION

# Set shorter cache for index.html (so updates are picked up)
aws s3 cp dist/index.html "s3://${S3_BUCKET}/index.html" \
    --cache-control "public, max-age=0, must-revalidate" \
    --content-type "text/html" \
    --region $AWS_REGION > /dev/null

echo "    Files uploaded."

# Invalidate CloudFront cache
echo "    Invalidating CloudFront cache..."
aws cloudfront create-invalidation \
    --distribution-id "$CF_DIST_ID" \
    --paths "/*" > /dev/null

echo ""
echo "══════════════════════════════════════════════"
echo "  FRONTEND DEPLOYMENT COMPLETE"
echo "══════════════════════════════════════════════"
echo ""
echo "  Website:      https://$DOMAIN"
echo "  CloudFront:   https://$CF_DOMAIN"
echo "  Distribution: $CF_DIST_ID"
echo "  S3 Bucket:    $S3_BUCKET"
echo ""
echo "  Note: CloudFront may take 5-10 minutes"
echo "  to fully propagate on first deploy."
echo ""
echo "══════════════════════════════════════════════"
