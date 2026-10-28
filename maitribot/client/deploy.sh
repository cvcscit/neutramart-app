#!/bin/bash
set -euo pipefail

# Build and deploy the UI to S3/CloudFront with cache headers tuned for slow/rural
# connections: hashed assets (filename changes on every rebuild) are cached by the
# browser for a year and never re-validated; the two HTML entry points always
# revalidate since they're what points at the current asset hashes.
#
# Needs VITE_GOOGLE_CLIENT_ID / VITE_ORIGIN_VERIFY_SECRET / VITE_SHENAI_API_KEY in the
# environment before `npm run build` runs (from .env.production locally, or from SSM via
# the "Fetch build-time config from SSM" step in deploy-frontend.yml in CI) -- without
# them the build still succeeds but ships a bundle with Google Sign-In broken.

# Locally: defaults to the nutrasmart profile. In CI (CI=true, set by GitHub Actions):
# leave AWS_PROFILE unset so the OIDC-assumed role credentials already in the
# environment are used as-is, instead of pointing at a local profile that doesn't exist.
PROFILE="${AWS_PROFILE:-}"
if [ -z "$PROFILE" ] && [ "${CI:-}" != "true" ]; then
  PROFILE="nutrasmart-792207721590"
fi
BUCKET="w360-maitribot-ui"
DISTRIBUTION_ID="E1H343JO0UX83F"

# aws_cmd wraps the CLI: only sets AWS_PROFILE when one is actually chosen above, since
# an empty AWS_PROFILE="" env var makes the CLI look for a profile named "" and fail.
aws_cmd() {
  if [ -n "$PROFILE" ]; then
    AWS_PROFILE="$PROFILE" aws "$@"
  else
    aws "$@"
  fi
}

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
aws_cmd s3 sync dist/ "s3://$BUCKET/" \
  --delete \
  "${EXCLUDES[@]}" \
  --cache-control "public, max-age=31536000, immutable"

echo "==> Syncing unhashed files (always revalidate)..."
for f in $UNHASHED; do
  aws_cmd s3 cp "dist/$f" "s3://$BUCKET/$f" \
    --cache-control "no-cache, must-revalidate"
done

echo "==> Invalidating CloudFront..."
aws_cmd cloudfront create-invalidation \
  --distribution-id "$DISTRIBUTION_ID" --paths "/*"

echo "==> Done."
