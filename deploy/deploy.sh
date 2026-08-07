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

# ── 1. resolve $TARGET against origin, not whatever is locally cached ───────
#
# Twice in production this printed "fast-forward confirmed" and rebuilt the
# OLD code: the fast-forward check below used to run against "$TARGET" with
# no `git fetch` ever having happened, so a branch name resolved to whatever
# local ref happened to exist - stale (a branch fetched days ago) or, once,
# absent entirely (a branch never fetched on this host, so `origin/<branch>`
# didn't even resolve). Either way the check compared HEAD to itself or to a
# ref that trivially satisfied "is an ancestor" and never touched origin.
# Fetch first, then fast-forward the local branch to origin's tip so every
# later step - including the check right below - sees what origin actually
# has.
say "fetching origin"
if ! timeout 60 git fetch --prune origin; then
    echo "ABORT: git fetch origin failed - refusing to deploy against a possibly stale ref." >&2
    exit 1
fi

if git show-ref --verify --quiet "refs/remotes/origin/$TARGET"; then
    REMOTE_SHA=$(git rev-parse "origin/$TARGET")
    if git show-ref --verify --quiet "refs/heads/$TARGET"; then
        LOCAL_SHA=$(git rev-parse "refs/heads/$TARGET")
        if [ "$LOCAL_SHA" != "$REMOTE_SHA" ]; then
            if ! git merge-base --is-ancestor "$LOCAL_SHA" "$REMOTE_SHA"; then
                echo "ABORT: local branch $TARGET has diverged from origin/$TARGET - refusing to guess which wins." >&2
                echo "Local-only commits:" >&2
                git log --oneline "$REMOTE_SHA..$LOCAL_SHA" | sed 's/^/  /' >&2
                echo "Resolve manually (e.g. git merge --ff-only origin/$TARGET on this host) and re-run." >&2
                exit 1
            fi
            if [ "$(git rev-parse --abbrev-ref HEAD)" = "$TARGET" ]; then
                git merge --ff-only "origin/$TARGET"
            else
                git branch -f "$TARGET" "$REMOTE_SHA"
            fi
            echo "  fast-forwarded local $TARGET to origin/$TARGET"
        fi
    else
        git branch "$TARGET" "$REMOTE_SHA"
        echo "  created local $TARGET tracking origin/$TARGET (never fetched on this host before)"
    fi
fi

TARGET_SHA=$(git rev-parse "$TARGET")
say "resolved $TARGET -> $TARGET_SHA"

# ── 2. never silently discard work that only exists here ────────────────────
if ! git merge-base --is-ancestor HEAD "$TARGET_SHA" 2>/dev/null; then
    if [ "$FORCE" != "--force" ]; then
        echo "ABORT: $TARGET is not a fast-forward from HEAD." >&2
        echo "Commits on this host that $TARGET does not contain:" >&2
        git log --oneline "$TARGET_SHA..HEAD" | sed 's/^/  /' >&2
        echo "Re-run with --force only if you intend to discard them." >&2
        exit 1
    fi
    echo "WARNING: forcing a non-fast-forward deploy."
fi
echo "  fast-forward confirmed"

# ── 3. backups, before anything changes ─────────────────────────────────────
say "backing up"
docker compose exec -T postgres pg_dumpall -U postgres | gzip > "$BACKUPS/db-$TS.sql.gz"
cp docker-compose.yml "$BACKUPS/docker-compose.yml.$TS" 2>/dev/null || true
printf '%s\n%s\n' "$PREVIOUS" "$PREVIOUS_REF" > "$BACKUPS/ROLLBACK.$TS"
echo "  db: $(du -h "$BACKUPS/db-$TS.sql.gz" | cut -f1)   rollback: $PREVIOUS ($PREVIOUS_REF)"

# ── 4. check out, then verify integrity BEFORE restarting ───────────────────
say "checking out $TARGET"
git checkout -q "$TARGET"
git log --oneline -1 | sed 's/^/  /'

if [ "$(git rev-parse HEAD)" != "$TARGET_SHA" ]; then
    echo "ABORT: checked out $(git rev-parse HEAD) but resolved target was $TARGET_SHA." >&2
    echo "This is not the ref the operator asked for - stopping before any rebuild." >&2
    git checkout -q "$PREVIOUS_REF"
    exit 1
fi

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

# ── 5. rebuild, then restart (NOT SIGHUP - see README) ──────────────────────
#
# The build step is not optional and its absence was a silent, serious bug.
# `up -d --force-recreate` recreates the CONTAINER from the EXISTING image; it
# never rebuilds. So for as long as this script omitted a build, no change to
# Dockerfile or requirements.txt could reach production, however many times it
# was deployed.
#
# Measured on 2026-08-04: the running image was built 2026-07-12. The Dockerfile
# gained WeasyPrint's native libraries on 2026-07-30 (after someone installed
# them into a live container on 07-14 and that fix was destroyed by the next
# --force-recreate), and PDF export had been failing on "cannot load library
# gobject-2.0-0" ever since. In the same image, Pillow was 10.4.0, pypdf 5.9.0
# and weasyprint 60.2 while requirements.txt pinned CVE-patched floors — 62
# advisories that had been "fixed" in git for weeks and were still running.
# Prune BEFORE building, not after. Building on every deploy grows the buildkit
# cache without bound — it reached 16.3 GB in two rebuilds and the third died with
# "no space left on device" at 85% disk with a ~16 GB image to write.
#
# The first attempt at this put the prune after the build, reasoning that the run
# should keep its own warm cache. That is useless: a build that fails for want of
# space never reaches a cleanup step placed after it, so the deploy deadlocks at
# exactly the moment the cleanup was meant to help. Verified — the cache was back
# to 16.31 GB and the disk to 85% immediately after the next successful deploy.
#
# Pruning first costs a cold build every time. That is the correct trade: a slower
# deploy beats a deploy that cannot run.
say "pruning the build cache to make room"
docker builder prune -af >/dev/null 2>&1 || true
df -h / | tail -1 | sed 's/^/  /'

say "rebuilding the image"
docker compose build server
say "restarting the application"
docker compose up -d --force-recreate server

# ── 6. wait for health, roll back if it never arrives ───────────────────────
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

# ── 7. prove the new code is the code that is running ───────────────────────
say "post-deploy checks"
docker compose logs server 2>/dev/null | grep -E "reconcile-schema:" | tail -1 | sed 's/^/  /' || true
for path in / /account/login /health; do
    code=$(curl -s -o /dev/null -m 15 -w '%{http_code}' "http://127.0.0.1:5000$path" || true)
    printf '  %-18s %s\n' "$path" "$code"
done

say "deployed $(git log --oneline -1)"
echo "rollback:  git checkout $PREVIOUS && docker compose up -d --force-recreate server"
echo "database:  $BACKUPS/db-$TS.sql.gz"
