#!/usr/bin/env bash
# Coordinate the checkout around deploy/deploy.sh and provide a one-time
# rollback to the source-mounted deployment that predates immutable releases.
set -euo pipefail

IMAGE_REF=${1:-}
EXPECTED_COMMIT=${2:-}
LEGACY_COMMIT=${3:-}
STATE_DIR=${ARCHIE_RELEASE_STATE:-/root/deploy-releases}
RELEASE_FILE="$STATE_DIR/release.env"
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:5000/health}
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-900}

die() { printf 'cutover: %s\n' "$*" >&2; exit 1; }

[[ "$IMAGE_REF" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || \
    die "image must be an immutable GHCR digest"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "expected commit must be a full SHA"
[[ "$LEGACY_COMMIT" =~ ^[0-9a-f]{40}$ ]] || die "legacy commit must be a full SHA"
git cat-file -e "$LEGACY_COMMIT^{commit}" || die "legacy commit is not available locally"
[ "$(git rev-parse HEAD)" = "$EXPECTED_COMMIT" ] || die "checkout does not match expected commit"

if ./deploy/deploy.sh "$IMAGE_REF" "$EXPECTED_COMMIT"; then
    exit 0
else
    deploy_status=$?
fi

# Once a digest release exists, deploy/deploy.sh has already attempted and
# verified digest-to-digest rollback. This fallback is exclusively for the
# first immutable cutover from the legacy source-mounted topology.
if test -f "$RELEASE_FILE"; then
    exit "$deploy_status"
fi

printf '\n== restoring pre-immutable deployment at %s\n' "$LEGACY_COMMIT" >&2
git checkout --detach "$LEGACY_COMMIT"
docker compose up -d --no-build --force-recreate server

deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    if [ "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$HEALTH_URL" || true)" = 200 ]; then
        printf 'cutover: verified legacy rollback to %s\n' "$LEGACY_COMMIT" >&2
        exit "$deploy_status"
    fi
    sleep 10
done

die "immutable cutover and legacy rollback both failed health verification"
