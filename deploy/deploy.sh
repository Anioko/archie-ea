#!/usr/bin/env bash
# Deploy a ref to this host, safely, and roll back if it does not come up.
#
# Runs ON the application server (10.106.0.6), from /root/archie-ea.
#
#   ./deploy/deploy.sh <ref>            deploy a branch or commit already on this host
#   ./deploy/deploy.sh <ref> --force    allow a non-fast-forward (destroys local commits)
#
# The sequence exists because each step has already caught a real failure:
#
#   fast-forward check   production carried its own commits on a snapshot branch;
#                        deploying over them would have lost work
#   database dump        reconcile-schema adds columns on boot
#   SRI verification     a Windows checkout rewrote vendored JS to CRLF, changing
#                        every hash. Deploying that blocks Alpine, DOMPurify and
#                        every icon - the entire front end - while the templates
#                        stay perfectly valid. Checked BEFORE the restart, because
#                        afterwards is an outage
#   restart, not SIGHUP  gunicorn preloads the app; SIGHUP re-forks workers from a
#                        master still holding the old modules, so the deploy looks
#                        successful and changes nothing
#   auto-rollback        an unhealthy deploy reverts itself rather than waiting to
#                        be noticed
set -euo pipefail

REPO=/root/archie-ea
BACKUPS=/root/deploy-backups
HEALTH_URL=http://127.0.0.1:5000/health
HEALTH_TIMEOUT=${HEALTH_TIMEOUT:-300}

TARGET=${1:-}
FORCE=${2:-}
[ -n "$TARGET" ] || { echo "usage: $0 <ref> [--force]" >&2; exit 2; }

cd "$REPO"
mkdir -p "$BACKUPS"
TS=$(date +%Y%m%d-%H%M%S)
say() { printf '\n== %s\n' "$*"; }

PREVIOUS=$(git rev-parse HEAD)
PREVIOUS_REF=$(git rev-parse --abbrev-ref HEAD)
say "deploying $TARGET  (currently $(git log --oneline -1))"

# ── 1. never silently discard work that only exists here ────────────────────
if ! git merge-base --is-ancestor HEAD "$TARGET" 2>/dev/null; then
    if [ "$FORCE" != "--force" ]; then
        echo "ABORT: $TARGET is not a fast-forward from HEAD." >&2
        echo "Commits on this host that $TARGET does not contain:" >&2
        git log --oneline "$TARGET..HEAD" | sed 's/^/  /' >&2
        echo "Re-run with --force only if you intend to discard them." >&2
        exit 1
    fi
    echo "WARNING: forcing a non-fast-forward deploy."
fi
echo "  fast-forward confirmed"

# ── 2. backups, before anything changes ─────────────────────────────────────
say "backing up"
docker compose exec -T postgres pg_dumpall -U postgres | gzip > "$BACKUPS/db-$TS.sql.gz"
cp docker-compose.yml "$BACKUPS/docker-compose.yml.$TS" 2>/dev/null || true
printf '%s\n%s\n' "$PREVIOUS" "$PREVIOUS_REF" > "$BACKUPS/ROLLBACK.$TS"
echo "  db: $(du -h "$BACKUPS/db-$TS.sql.gz" | cut -f1)   rollback: $PREVIOUS ($PREVIOUS_REF)"

# ── 3. check out, then verify integrity BEFORE restarting ───────────────────
say "checking out $TARGET"
git checkout -q "$TARGET"
git log --oneline -1 | sed 's/^/  /'

say "verifying subresource integrity on the checked-out tree"
python3 - <<'PY' || { echo "ABORT: SRI mismatch - deploying this would kill the front end." >&2; git checkout -q "$PREVIOUS_REF"; exit 1; }
import base64, hashlib, glob, io, os, re, sys
bad = 0
for path in glob.glob("app/templates/**/*.html", recursive=True):
    src = io.open(path, encoding="utf-8", errors="ignore").read()
    for _url, rel, want in re.findall(
            r'src="([^"]*?/static/([\w./\-]+))"[^>]{0,300}?integrity="sha384-([A-Za-z0-9+/=]+)"',
            src, re.S):
        f = os.path.join("app/static", rel)
        if not os.path.exists(f):
            continue
        got = base64.b64encode(hashlib.sha384(open(f, "rb").read()).digest()).decode()
        if got != want:
            bad += 1
            print("  MISMATCH %s in %s" % (rel, path))
print("  integrity mismatches: %d" % bad)
sys.exit(1 if bad else 0)
PY

# ── 4. restart (NOT SIGHUP - see README) ────────────────────────────────────
say "restarting the application"
docker compose up -d --force-recreate server

# ── 5. wait for health, roll back if it never arrives ───────────────────────
say "waiting for health (up to ${HEALTH_TIMEOUT}s)"
deadline=$(( $(date +%s) + HEALTH_TIMEOUT ))
healthy=0
while [ "$(date +%s)" -lt "$deadline" ]; do
    if [ "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$HEALTH_URL" || true)" = "200" ]; then
        healthy=1; break
    fi
    sleep 10
done

if [ "$healthy" != "1" ]; then
    say "UNHEALTHY - rolling back to $PREVIOUS"
    git checkout -q "$PREVIOUS"
    docker compose up -d --force-recreate server
    echo "  rolled back. database dump: $BACKUPS/db-$TS.sql.gz"
    exit 1
fi
echo "  healthy"

# ── 6. prove the new code is the code that is running ───────────────────────
say "post-deploy checks"
docker compose logs server 2>/dev/null | grep -E "reconcile-schema:" | tail -1 | sed 's/^/  /' || true
for path in / /account/login /health; do
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "http://127.0.0.1:5000$path" || true)
    printf '  %-18s %s\n' "$path" "$code"
done

say "deployed $(git log --oneline -1)"
echo "rollback:  git checkout $PREVIOUS && docker compose up -d --force-recreate server"
echo "database:  $BACKUPS/db-$TS.sql.gz"
