#!/usr/bin/env bash
# deploy_verified.sh — deploy + PROVE the deploy landed, for the bind-mount
# source-checkout topology that production actually runs today.
#
# WHY THIS EXISTS (incident, 8 Sep 2026):
#   `docker compose restart` was run 6+ times against production. `restart`
#   only restarts a container with its EXISTING config — it never re-reads
#   docker-compose.yml — so it silently kept the same stale, already-running
#   container alive while `git log` on the host and `curl /health` both kept
#   reporting success. `docker inspect archie-ea-server-1` eventually showed
#   the running container had ZERO bind mounts, despite docker-compose.yml
#   declaring `volumes: - './:/app'`. Every verification used in that session
#   (curl 200, host git log) proved nothing about what the CONTAINER was
#   running. Fixing it required `docker compose up -d --force-recreate
#   server`, which also surfaced a second bug: a 600-root-owned `.env` file
#   unreadable by the container's non-root `appuser`, killing the one-shot
#   schema-deploy container with a permission error that read like an app bug.
#
#   This script makes that failure mode structurally impossible to repeat
#   SILENTLY: it never trusts `docker compose ps`/health alone, always forces
#   a real container recreation, and independently proves — from OUTSIDE the
#   container's own self-report — that the bind mount is real and the code
#   running inside it is the commit that was asked for.
#
# RELATIONSHIP TO deploy/deploy.sh (read before adding a third script):
#   deploy/deploy.sh + scripts/deploy.sh are a SEPARATE, more advanced
#   pipeline for a different topology: an immutable image built by CI and
#   pulled by exact `ghcr.io/...@sha256:` digest, with the production Compose
#   overlay (deploy/docker-compose.production.yml) stripping ALL bind mounts
#   (`volumes: !reset []`). That pipeline is real and committed, but as of
#   8 Sep 2026 it is NOT what is actually running: `docker inspect
#   archie-ea-server-1` on the droplet still shows `/root/archie-ea -> /app`,
#   the running image is the locally-built `archie-ea-server` (not a
#   `ghcr.io` digest), and `/root/deploy-releases/release.env` is stale
#   (points at a commit several deploys behind current HEAD). Production is
#   still deployed by checking out a ref on the host and recreating the
#   bind-mounted container — the exact topology this incident happened in.
#   THIS script is the deploy+verify tool for THAT live topology. It does not
#   duplicate deploy/deploy.sh's job (immutable-digest activation/rollback);
#   it replaces the ad-hoc `git pull && docker compose restart` that caused
#   the incident. If/when the ghcr pipeline becomes the live path, this
#   script's verification half (steps 2-5) should be folded into that one and
#   this file retired — do not let both remain the "current" answer at once.
#
# USAGE:
#   scripts/deploy_verified.sh <ref> [--skip-deploy]
#
#   <ref>           branch or commit to deploy (e.g. main, or a full SHA).
#                   Resolved to a full SHA via `git rev-parse` on the droplet
#                   AFTER `git fetch`, so a branch name always means its
#                   current tip, never a stale local ref.
#   --skip-deploy   run verification only, against whatever is already
#                   running (used for testing this script itself, and for
#                   re-checking a deploy without repeating it).
#
# ENVIRONMENT:
#   DROPLET                 ssh target (default root@134.122.105.56)
#   APP_DIR                 checkout path on droplet (default /root/archie-ea)
#   SERVER_CONTAINER        container name (default archie-ea-server-1)
#   EXPECTED_MOUNT_SOURCE   host path expected as the bind-mount source
#                           (default: same as APP_DIR)
#   EXPECTED_MOUNT_DEST     container path expected as the bind-mount target
#                           (default /app)
#   HEALTH_TIMEOUT_SECONDS  how long to wait for the container to report
#                           healthy before giving up (default 900 = 15 min;
#                           this project's boot chain is documented as
#                           taking 8-12 minutes)
#   DEPLOY_VERIFY_EMAIL / DEPLOY_VERIFY_PASSWORD
#                           if BOTH are set, an authenticated Playwright
#                           smoke check is run at the end. If either is
#                           unset, step 5 is SKIPPED with a printed warning —
#                           never silently treated as a pass.
#
# EXIT CODE is the AND of every check. Any failure prints a clear diagnostic
# to stderr and the script exits non-zero — a deploy that cannot prove itself
# is not allowed to report success.
set -euo pipefail

DROPLET=${DROPLET:-root@134.122.105.56}
APP_DIR=${APP_DIR:-/root/archie-ea}
SERVER_CONTAINER=${SERVER_CONTAINER:-archie-ea-server-1}
EXPECTED_MOUNT_SOURCE=${EXPECTED_MOUNT_SOURCE:-$APP_DIR}
EXPECTED_MOUNT_DEST=${EXPECTED_MOUNT_DEST:-/app}
HEALTH_TIMEOUT_SECONDS=${HEALTH_TIMEOUT_SECONDS:-900}
SSH_OPTS=(-o ConnectTimeout=20 -o BatchMode=yes)

REF=${1:-}
MODE=${2:-}

say()  { printf '\n== %s\n' "$*"; }
fail() { printf 'DEPLOY-VERIFY FAIL: %s\n' "$*" >&2; }
die()  { fail "$*"; exit 1; }

[ -n "$REF" ] || die "usage: scripts/deploy_verified.sh <ref> [--skip-deploy]"
[ "$MODE" = "" ] || [ "$MODE" = "--skip-deploy" ] || die "unknown argument: $MODE"

remote() {
    # Runs a command on the droplet over ssh, positional args passed through
    # to the remote script safely (no local interpolation into remote quoting).
    ssh "${SSH_OPTS[@]}" "$DROPLET" bash -s -- "$@"
}

OVERALL_STATUS=0
record() {
    # $1 = 0/nonzero result of the step just run, $2 = step name.
    if [ "$1" -ne 0 ]; then
        OVERALL_STATUS=1
        fail "step failed: $2"
    else
        printf 'OK: %s\n' "$2"
    fi
}

RESOLVED_COMMIT=""

# ---------------------------------------------------------------------------
# Step 1: deploy — fetch, checkout the resolved ref, and force-recreate the
# server container. `up -d` alone is NOT sufficient (see incident above): if
# nothing in the compose *config* changed, `up -d` will not recreate a
# container either, only `restart`'s cousin. `--force-recreate` is what
# actually guarantees a fresh container is created from current config on
# every run, deploy after deploy, regardless of whether the compose file
# itself changed.
# ---------------------------------------------------------------------------
do_deploy() {
    say "deploying $REF to $DROPLET:$APP_DIR"
    remote "$APP_DIR" "$REF" <<'REMOTE'
set -euo pipefail
APP_DIR=$1
REF=$2
cd "$APP_DIR"
git fetch --prune origin
# Resolve to a full SHA now, after fetch, so a branch name means its current
# tip and the caller gets back exactly what was deployed.
if git rev-parse --verify --quiet "origin/$REF" >/dev/null; then
    TARGET=$(git rev-parse "origin/$REF")
else
    TARGET=$(git rev-parse --verify "$REF")
fi
CURRENT=$(git rev-parse HEAD)
if [ "$CURRENT" != "$TARGET" ]; then
    git checkout --detach "$TARGET"
    git reset --hard "$TARGET"
else
    echo "already at $TARGET; checkout skipped (verification still runs)"
fi
echo "RESOLVED_COMMIT=$TARGET"
docker compose up -d --force-recreate server
REMOTE
}

if [ "$MODE" != "--skip-deploy" ]; then
    DEPLOY_OUTPUT=$(do_deploy) || { fail "deploy step (checkout/compose up) failed"; exit 1; }
    printf '%s\n' "$DEPLOY_OUTPUT"
    RESOLVED_COMMIT=$(printf '%s\n' "$DEPLOY_OUTPUT" | sed -n 's/^RESOLVED_COMMIT=//p' | tail -1)
    [ -n "$RESOLVED_COMMIT" ] || die "could not determine the commit that was actually checked out on the droplet"
else
    say "--skip-deploy: verifying the currently-running deployment only"
    RESOLVED_COMMIT=$(remote "$APP_DIR" <<'REMOTE'
cd "$1"
git rev-parse HEAD
REMOTE
    ) || die "could not read the current commit on the droplet"
fi

EXPECTED_SHORT=${RESOLVED_COMMIT:0:8}
say "target commit: $RESOLVED_COMMIT (short: $EXPECTED_SHORT)"

# ---------------------------------------------------------------------------
# Step 2: wait for the container to report healthy. Necessary, not
# sufficient — a container can be "healthy" while running yesterday's code
# (that is exactly what happened in the incident).
# ---------------------------------------------------------------------------
wait_for_health() {
    say "waiting up to ${HEALTH_TIMEOUT_SECONDS}s for $SERVER_CONTAINER to report healthy"
    local deadline=$(( $(date +%s) + HEALTH_TIMEOUT_SECONDS )) status
    while [ "$(date +%s)" -lt "$deadline" ]; do
        status=$(remote "$SERVER_CONTAINER" <<'REMOTE'
docker inspect --format '{{.State.Health.Status}}' "$1" 2>/dev/null || echo missing
REMOTE
        ) || status="unreachable"
        status=$(printf '%s' "$status" | tail -1 | tr -d '\r')
        if [ "$status" = "healthy" ]; then
            return 0
        fi
        if [ "$status" = "missing" ]; then
            fail "container $SERVER_CONTAINER does not exist"
            return 1
        fi
        sleep 10
    done
    fail "container did not report healthy within ${HEALTH_TIMEOUT_SECONDS}s (last status: ${status:-unknown})"
    return 1
}
wait_for_health; record $? "container reports healthy"

# ---------------------------------------------------------------------------
# Step 3: verify the bind mount is REAL. This is the exact check that would
# have caught the incident immediately: the running container must actually
# have the source mount, not just the compose file declaring one.
# ---------------------------------------------------------------------------
verify_mount() {
    say "verifying bind mount on $SERVER_CONTAINER"
    local mounts
    mounts=$(remote "$SERVER_CONTAINER" <<'REMOTE'
docker inspect "$1" --format '{{range .Mounts}}{{.Source}} -> {{.Destination}}{{println}}{{end}}'
REMOTE
    ) || { fail "could not inspect container mounts"; return 1; }
    printf '%s' "$mounts"
    if ! printf '%s' "$mounts" | grep -qF "${EXPECTED_MOUNT_SOURCE} -> ${EXPECTED_MOUNT_DEST}"; then
        fail "expected mount '${EXPECTED_MOUNT_SOURCE} -> ${EXPECTED_MOUNT_DEST}' not found; container has zero or wrong bind mounts (this is precisely the 8 Sep 2026 incident)"
        return 1
    fi
    return 0
}
verify_mount; record $? "bind mount is present and correct"

# ---------------------------------------------------------------------------
# Step 4: verify the container is running the TARGET COMMIT's code, not just
# that files exist at the mount point. Use the app's own /version endpoint
# (app/_bootstrap/routes.py, build_id from app/_bootstrap/build_info.py,
# git short-8 SHA) rather than `git rev-parse` inside the container — the
# container's git identity check is documented (build_info.py's own
# docstring) to fail with "detected dubious ownership" for the appuser/root
# ownership mismatch, so a content/build-id check is the reliable path, not
# the fallback.
# ---------------------------------------------------------------------------
verify_running_code() {
    say "verifying running build_id via /version"
    local payload build_id
    payload=$(remote <<'REMOTE'
curl -fsS -m 10 http://127.0.0.1:5000/version
REMOTE
    ) || { fail "/version did not respond on the droplet"; return 1; }
    printf 'version endpoint: %s\n' "$payload"
    build_id=$(printf '%s' "$payload" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("build_id",""))' 2>/dev/null) || {
        fail "/version returned unparseable JSON: $payload"
        return 1
    }
    [ -n "$build_id" ] || { fail "/version returned no build_id"; return 1; }
    if [ "$build_id" != "$EXPECTED_SHORT" ]; then
        fail "/version reports build_id=$build_id, expected $EXPECTED_SHORT (git HEAD is not what the running process sees — a stale gunicorn master under preload_app is exactly this symptom, see deploy/README.md)"
        return 1
    fi
    return 0
}
verify_running_code; record $? "running build_id matches target commit"

# ---------------------------------------------------------------------------
# Step 5 (optional): authenticated Playwright reachability check. Skipped,
# with a loud warning (not a silent pass), if credentials are not supplied.
# Never hardcode credentials — read only from environment.
# ---------------------------------------------------------------------------
run_smoke_check() {
    if [ -z "${DEPLOY_VERIFY_EMAIL:-}" ] || [ -z "${DEPLOY_VERIFY_PASSWORD:-}" ]; then
        printf 'WARNING: DEPLOY_VERIFY_EMAIL/DEPLOY_VERIFY_PASSWORD not set; skipping authenticated smoke check (this step proves end-to-end reachability, not just container health — skipping it is a real gap, not a pass)\n' >&2
        return 0
    fi
    say "running authenticated Playwright smoke check"
    DEPLOY_VERIFY_EMAIL="$DEPLOY_VERIFY_EMAIL" \
    DEPLOY_VERIFY_PASSWORD="$DEPLOY_VERIFY_PASSWORD" \
    DEPLOY_VERIFY_BASE_URL="${DEPLOY_VERIFY_BASE_URL:-https://165-22-125-156.sslip.io}" \
    python3 "$(dirname "$0")/deploy_verify_smoke.py"
}
if [ -n "${DEPLOY_VERIFY_EMAIL:-}" ] && [ -n "${DEPLOY_VERIFY_PASSWORD:-}" ]; then
    run_smoke_check; record $? "authenticated smoke check reached a real page"
else
    run_smoke_check
fi

say "summary"
if [ "$OVERALL_STATUS" -eq 0 ]; then
    printf 'DEPLOY VERIFIED: commit %s is running, mounted and reachable.\n' "$RESOLVED_COMMIT"
else
    printf 'DEPLOY NOT VERIFIED — see FAIL lines above. Do not report this deploy as done.\n' >&2
fi
exit "$OVERALL_STATUS"
