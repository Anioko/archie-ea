#!/usr/bin/env bash
#
# One-command deploy for A.R.C.H.I.E. -> the DigitalOcean droplet.
#
# Encodes the manual push -> checkout -> (restart | up -d) -> health-poll ->
# auto-rollback workflow so shipping is one reliable command regardless of which
# editor made the change.
#
# USAGE
#   scripts/deploy.sh [<git-ref>] [--recreate] [--yes]
#
#   <git-ref>    What to deploy. Default: HEAD. A branch/tag/sha in this repo.
#   --recreate   Force `docker compose up -d` (recreate) instead of `restart`.
#                Auto-selected anyway when docker-compose.yml differs from what's
#                live (a compose change needs a recreate to take effect).
#   --yes        Skip the confirmation prompt (for CI / non-interactive use).
#
# WHAT IT DOES
#   1. Refuses if the working tree is dirty (deploy only committed code).
#   2. Confirms the droplet isn't ahead of you (no silent clobber).
#   3. Pushes a dated deploy branch to `prod`.
#   4. On the droplet: fetch + checkout that branch.
#   5. restart (code-only) or `up -d` (compose changed / --recreate).
#   6. Polls /health for up to 15 min (boot is 8-12 min: init-db ->
#      reconcile-schema -> backfills -> gunicorn).
#   7. On failure/timeout: auto-rolls back to the previously-deployed branch
#      and reports.
#
# HARD RULES baked in (do not remove):
#   * NEVER `docker compose exec server flask ...` — it boots a 2nd Flask app in
#     the memory cgroup and has OOM-killed production. This script never execs
#     into the running container.
#   * Serial only — one deploy at a time.
#
set -euo pipefail

# ── config ──────────────────────────────────────────────────────────────────
PROD_REMOTE="${PROD_REMOTE:-prod}"                       # git remote name
DROPLET="${DROPLET:-root@134.122.105.56}"                # ssh target
APP_DIR="${APP_DIR:-/root/archie-ea}"                    # app dir on droplet
HEALTH_URL="${HEALTH_URL:-http://127.0.0.1:5000/health}" # health endpoint (on box)
PUBLIC_HEALTH="${PUBLIC_HEALTH:-https://165-22-125-156.sslip.io/health}"
POLL_SECONDS="${POLL_SECONDS:-900}"                      # 15 min bound
POLL_INTERVAL="${POLL_INTERVAL:-20}"
SSH_OPTS="-o ConnectTimeout=20 -o BatchMode=yes"

# ── args ────────────────────────────────────────────────────────────────────
REF="HEAD"; RECREATE=0; ASSUME_YES=0
for a in "$@"; do
  case "$a" in
    --recreate) RECREATE=1 ;;
    --yes|-y)   ASSUME_YES=1 ;;
    -*)         echo "unknown flag: $a" >&2; exit 2 ;;
    *)          REF="$a" ;;
  esac
done

log() { printf '\033[1;36m[deploy]\033[0m %s\n' "$*"; }
err() { printf '\033[1;31m[deploy:ERROR]\033[0m %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

command -v git >/dev/null || die "git not found"
command -v ssh >/dev/null || die "ssh not found"

# ── 1. clean tree ─────────────────────────────────────────────────────────────
if [ -n "$(git status --porcelain | grep -vE 'verify_static_out|HANDOFF-aider' || true)" ]; then
  die "working tree is dirty — commit or stash before deploying (deploy ships committed code only).
$(git status --short)"
fi

SHA="$(git rev-parse --short "$REF")" || die "cannot resolve ref: $REF"
DEPLOY_BRANCH="deploy-$(git show -s --format=%cd --date=format:%Y%m%d "$SHA")-$SHA"
log "deploying $REF ($SHA) as branch $DEPLOY_BRANCH"

# ── 2. don't clobber a droplet that moved ─────────────────────────────────────
log "checking droplet's current state…"
REMOTE_STATE="$(ssh $SSH_OPTS "$DROPLET" "cd '$APP_DIR' && git rev-parse --abbrev-ref HEAD && git rev-parse --short HEAD" 2>/dev/null)" \
  || die "cannot reach droplet $DROPLET or read $APP_DIR"
PREV_BRANCH="$(printf '%s\n' "$REMOTE_STATE" | sed -n 1p)"
PREV_SHA="$(printf '%s\n' "$REMOTE_STATE" | sed -n 2p)"
log "droplet is currently on: $PREV_BRANCH ($PREV_SHA)"

# The commit currently live must be an ancestor of what we're deploying, OR the
# same — otherwise the droplet has commits we don't, and pushing would diverge.
if ! git merge-base --is-ancestor "$PREV_SHA" "$SHA" 2>/dev/null; then
  if [ "$PREV_SHA" != "$SHA" ]; then
    err "droplet ($PREV_SHA) is NOT an ancestor of $SHA — it may have changes you don't have."
    err "Investigate before deploying; refusing to avoid a silent clobber."
    exit 1
  fi
fi

# ── confirm ───────────────────────────────────────────────────────────────────
if [ "$ASSUME_YES" -ne 1 ]; then
  printf '\nDeploy \033[1m%s\033[0m to \033[1m%s:%s\033[0m (currently %s)? [y/N] ' "$SHA" "$DROPLET" "$APP_DIR" "$PREV_SHA"
  read -r ans; case "$ans" in y|Y|yes|YES) ;; *) die "aborted." ;; esac
fi

# ── 3. push ───────────────────────────────────────────────────────────────────
log "pushing $DEPLOY_BRANCH to $PROD_REMOTE…"
git branch -f "$DEPLOY_BRANCH" "$SHA"
git push "$PROD_REMOTE" "$DEPLOY_BRANCH"

# ── decide restart vs recreate ────────────────────────────────────────────────
# A docker-compose.yml change (e.g. mem_limit, boot command) only takes effect on
# `up -d` (recreate); `restart` reuses the old container config. Auto-detect.
if [ "$RECREATE" -ne 1 ]; then
  if ! git diff --quiet "$PREV_SHA" "$SHA" -- docker-compose.yml 2>/dev/null; then
    log "docker-compose.yml changed since $PREV_SHA -> using 'up -d' (recreate)."
    RECREATE=1
  fi
fi
ACTION=$([ "$RECREATE" -eq 1 ] && echo "up -d server" || echo "restart server")

# ── 4-5. checkout + (restart|up -d) ───────────────────────────────────────────
log "on droplet: checkout $DEPLOY_BRANCH + docker compose $ACTION…"
ssh $SSH_OPTS "$DROPLET" "cd '$APP_DIR' && git fetch -q && git checkout '$DEPLOY_BRANCH' && docker compose $ACTION" \
  || die "remote checkout/compose failed"

# ── 6. health poll ────────────────────────────────────────────────────────────
log "polling health (boot is 8-12 min; bound ${POLL_SECONDS}s)…"
deadline=$(( $(date +%s) + POLL_SECONDS ))
served=0
while [ "$(date +%s)" -lt "$deadline" ]; do
  code="$(ssh $SSH_OPTS "$DROPLET" "curl -s -o /dev/null -w '%{http_code}' --max-time 10 '$HEALTH_URL'" 2>/dev/null || echo 000)"
  printf '  %s health=%s\n' "$(date -u +%H:%M:%S)" "$code"
  if [ "$code" = "200" ]; then served=1; break; fi
  sleep "$POLL_INTERVAL"
done

if [ "$served" -eq 1 ]; then
  pub="$(ssh $SSH_OPTS "$DROPLET" "curl -s -o /dev/null -w '%{http_code}' --max-time 20 '$PUBLIC_HEALTH'" 2>/dev/null || echo '???')"
  log "✅ SERVING. local=200 public=$pub  deployed $SHA ($DEPLOY_BRANCH)."
  log "rollback if needed: ssh $DROPLET \"cd $APP_DIR && git checkout $PREV_BRANCH && docker compose up -d server\""
  exit 0
fi

# ── 7. rollback ───────────────────────────────────────────────────────────────
err "did NOT serve within ${POLL_SECONDS}s — rolling back to $PREV_BRANCH ($PREV_SHA)…"
ssh $SSH_OPTS "$DROPLET" "cd '$APP_DIR' && git checkout '$PREV_BRANCH' && docker compose up -d server" \
  || die "ROLLBACK FAILED — manual intervention needed on $DROPLET:$APP_DIR"
# confirm rollback serves
for _ in 1 2 3 4 5 6 7 8 9 10 11 12; do
  code="$(ssh $SSH_OPTS "$DROPLET" "curl -s -o /dev/null -w '%{http_code}' --max-time 10 '$HEALTH_URL'" 2>/dev/null || echo 000)"
  [ "$code" = "200" ] && { err "rolled back to $PREV_BRANCH and it is serving (200). Deploy of $SHA FAILED."; exit 1; }
  sleep 20
done
die "rolled back to $PREV_BRANCH but it is NOT serving — manual intervention needed."
