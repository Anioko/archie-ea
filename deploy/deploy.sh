#!/usr/bin/env bash
# Deploy one CI-produced Archie image by immutable registry digest.
# Usage: ./deploy/deploy.sh ghcr.io/anioko/archie@sha256:<64 hex> <40-char commit>
set -euo pipefail

REPO=${ARCHIE_REPO:-/root/archie-ea}
BACKUPS=${ARCHIE_BACKUPS:-/root/deploy-backups}
STATE_DIR=${ARCHIE_RELEASE_STATE:-/root/deploy-releases}
RELEASE_FILE="$STATE_DIR/release.env"
HEALTH_URL=${HEALTH_URL:-http://127.0.0.1:5000/health}
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-900}
PUBLIC_BASE_URL=${PUBLIC_BASE_URL:-https://165-22-125-156.sslip.io}
PUBLIC_HEALTH_TIMEOUT=${PUBLIC_HEALTH_TIMEOUT:-300}
IMAGE_REF=${1:-}
EXPECTED_COMMIT=${2:-}
COMPOSE=(docker compose -f docker-compose.yml -f deploy/docker-compose.production.yml)

say() { printf '\n== %s\n' "$*"; }
die() { printf 'ABORT: %s\n' "$*" >&2; exit 1; }

[[ "$IMAGE_REF" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[0-9a-f]{64}$ ]] || \
    die "image must be a lowercase GHCR reference pinned by sha256:[0-9a-f]{64}"
[[ "$EXPECTED_COMMIT" =~ ^[0-9a-f]{40}$ ]] || \
    die "commit must be the full [0-9a-f]{40} Git SHA"

cd "$REPO"
mkdir -p "$BACKUPS" "$STATE_DIR"
exec 9>"$STATE_DIR/deploy.lock"
flock -n 9 || die "another deployment is already running"

PREVIOUS_IMAGE=""
PREVIOUS_COMMIT=""
if [ -f "$RELEASE_FILE" ]; then
    PREVIOUS_IMAGE=$(sed -n 's/^ARCHIE_IMAGE=//p' "$RELEASE_FILE")
    PREVIOUS_COMMIT=$(sed -n 's/^ARCHIE_COMMIT=//p' "$RELEASE_FILE")
fi

image_revision() {
    docker image inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$1"
}

verify_image() {
    local ref=$1 expected=$2 revision
    revision=$(image_revision "$ref")
    [ "$revision" = "$expected" ] || \
        die "image revision $revision does not equal requested commit $expected"
}

compose_with() {
    ARCHIE_IMAGE="$1" "${COMPOSE[@]}" "${@:2}"
}

verify_running_identity() {
    local ref=$1 expected=$2 cid running_id local_id running_revision
    cid=$(compose_with "$ref" ps -q server)
    [ -n "$cid" ] || return 1
    running_id=$(docker inspect --format '{{.Image}}' "$cid")
    local_id=$(docker image inspect --format '{{.Id}}' "$ref")
    running_revision=$(docker inspect --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}' "$cid")
    [ "$running_id" = "$local_id" ] && [ "$running_revision" = "$expected" ]
}

wait_for_health() {
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT )) payload
    while [ "$(date +%s)" -lt "$deadline" ]; do
        payload=$(curl -fsS -m 10 "$HEALTH_URL" 2>/dev/null || true)
        if printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if data.get("status") == "healthy" and data.get("environment") == "production" else 1)
'; then
            return 0
        fi
        sleep 10
    done
    return 1
}

# The external load balancer deliberately needs successful probes after the
# server is replaced.  During schema deployment it can mark the backend down,
# so a one-shot public request immediately after local health is a race.  Wait
# for the public route to serve this exact production-mode application before
# running the broader page checks.
wait_for_public_health() {
    local base=$1 deadline=$(( $(date +%s) + PUBLIC_HEALTH_TIMEOUT )) payload
    while [ "$(date +%s)" -lt "$deadline" ]; do
        payload=$(curl -kfsS -m 10 "${base%/}/health" 2>/dev/null || true)
        if printf '%s' "$payload" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except (json.JSONDecodeError, UnicodeDecodeError):
    raise SystemExit(1)
raise SystemExit(0 if data.get("status") == "healthy" and data.get("environment") == "production" else 1)
'; then
            return 0
        fi
        sleep 10
    done
    return 1
}

activate() {
    local ref=$1 expected=$2
    compose_with "$ref" up -d --no-build --force-recreate server
    verify_running_identity "$ref" "$expected" && wait_for_health
}

rollback() {
    [ -n "$PREVIOUS_IMAGE" ] && [ -n "$PREVIOUS_COMMIT" ] || \
        die "deployment failed and no previous digest is recorded for rollback"
    say "rolling back to $PREVIOUS_IMAGE"
    docker pull "$PREVIOUS_IMAGE"
    verify_image "$PREVIOUS_IMAGE" "$PREVIOUS_COMMIT"
    activate "$PREVIOUS_IMAGE" "$PREVIOUS_COMMIT" || \
        die "rollback image failed identity or health verification"
    die "deployment failed; verified rollback to $PREVIOUS_COMMIT is serving"
}

say "pre-pulling immutable release"
docker pull "$IMAGE_REF"
verify_image "$IMAGE_REF" "$EXPECTED_COMMIT"

# Parse the overlay before touching data or the running container. This proves
# the host Compose supports !reset and ARCHIE_IMAGE is set.
compose_with "$IMAGE_REF" config --quiet

say "backing up the live database"
TS=$(date +%Y%m%d-%H%M%S)
docker compose exec -T postgres pg_dumpall -U postgres | gzip > "$BACKUPS/db-$TS.sql.gz"
[ -s "$BACKUPS/db-$TS.sql.gz" ] || die "database backup is empty"

say "activating exact image digest"
if ! activate "$IMAGE_REF" "$EXPECTED_COMMIT"; then
    rollback
fi

say "running post-deploy product checks"
if ! wait_for_public_health "$PUBLIC_BASE_URL"; then
    printf 'public load balancer did not route a healthy production response within %ss\n' \
        "$PUBLIC_HEALTH_TIMEOUT" >&2
    rollback
fi
if ! python3 scripts/post_deploy_verify.py --base "$PUBLIC_BASE_URL"; then
    rollback
fi
log_errors=$(compose_with "$IMAGE_REF" logs --since 15m server 2>/dev/null \
    | grep -cE 'ERROR|CRITICAL|Traceback|safe-query failed|Failed to enrich' || true)
if [ "$log_errors" -ne 0 ]; then
    printf '%s production error signal(s) found in the last 15 minutes\n' "$log_errors" >&2
    rollback
fi

tmp="$STATE_DIR/release.env.tmp.$$"
{
    printf 'ARCHIE_IMAGE=%s\n' "$IMAGE_REF"
    printf 'ARCHIE_COMMIT=%s\n' "$EXPECTED_COMMIT"
    printf 'DEPLOYED_AT=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'BACKUP=%s\n' "$BACKUPS/db-$TS.sql.gz"
} > "$tmp"
chmod 600 "$tmp"
mv "$tmp" "$RELEASE_FILE"

say "deployed and identity-verified $EXPECTED_COMMIT"
printf 'image: %s\nbackup: %s\n' "$IMAGE_REF" "$BACKUPS/db-$TS.sql.gz"
