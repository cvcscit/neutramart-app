#!/bin/bash
set -euo pipefail

# Build and deploy the UI to S3/CloudFront with cache headers tuned for slow/rural
# connections: hashed assets (filename changes on every rebuild) are cached by the
# browser for a year and never re-validated; the two HTML entry points always
# revalidate since they're what points at the current asset hashes.

PROFILE="${AWS_PROFILE:-nutrasmart-792207721590}"
BUCKET="w360-maitribot-ui"
DISTRIBUTION_ID="E1H343JO0UX83F"

echo "==> Building..."
npm run build

echo "==> Syncing hashed assets (immutable, 1yr cache)..."
AWS_PROFILE="$PROFILE" aws s3 sync dist/ "s3://$BUCKET/" \
  --delete \
  --exclude "index.html" --exclude "scan.html" \
  --cache-control "public, max-age=31536000, immutable"

echo "==> Syncing HTML entry points (always revalidate)..."
AWS_PROFILE="$PROFILE" aws s3 cp dist/index.html "s3://$BUCKET/index.html" \
  --cache-control "no-cache, must-revalidate"
AWS_PROFILE="$PROFILE" aws s3 cp dist/scan.html "s3://$BUCKET/scan.html" \
  --cache-control "no-cache, must-revalidate"

echo "==> Invalidating CloudFront..."
AWS_PROFILE="$PROFILE" aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" --paths "/*"

echo "==> Done."
