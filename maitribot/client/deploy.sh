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

# Everything that is NOT content-hashed by Vite -- the two HTML entry points, the PWA
# manifest, and the home-screen/favicon icons -- must revalidate on every visit, since
# their filenames never change when their content does. Only the hashed /assets/* and
# the vendored /shenai-sdk/* are safe to cache for a year.
UNHASHED="index.html scan.html manifest.webmanifest apple-touch-icon.png icon-192.png icon-512.png favicon-32.png"
EXCLUDES=()
for f in $UNHASHED; do EXCLUDES+=(--exclude "$f"); done

echo "==> Syncing hashed assets (immutable, 1yr cache)..."
AWS_PROFILE="$PROFILE" aws s3 sync dist/ "s3://$BUCKET/" \
  --delete \
  "${EXCLUDES[@]}" \
  --cache-control "public, max-age=31536000, immutable"

echo "==> Syncing unhashed files (always revalidate)..."
for f in $UNHASHED; do
  AWS_PROFILE="$PROFILE" aws s3 cp "dist/$f" "s3://$BUCKET/$f" \
    --cache-control "no-cache, must-revalidate"
done

echo "==> Invalidating CloudFront..."
AWS_PROFILE="$PROFILE" aws cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" --paths "/*"

echo "==> Done."
