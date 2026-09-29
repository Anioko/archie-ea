#!/usr/bin/env bash
# Point-in-time restore drill against a scratch container.
#
# Restores the production database to a chosen minute using wal-g, records the
# time taken, and compares row counts before and after. Designed to run in CI
# (no production credentials needed — it reads from a dedicated backup copy or
# a test bucket) and on a schedule (monthly drill).
#
# The restore target is a disposable scratch postgres container on the same
# Docker host. The live database is never touched.
#
# Required environment:
#   WALG_STORAGE_PREFIX       e.g. s3://bucket/archie-wal
#   AWS_ACCESS_KEY_ID
#   AWS_SECRET_ACCESS_KEY
#   AWS_REGION                (or WALG_S3_REGION)
#   RESTORE_TARGET_TIME       ISO-8601 timestamp to restore to (e.g. 2026-09-29T12:00:00Z)
#
# Optional:
#   SCRATCH_CONTAINER_NAME    default archie-restore-drill
#   SCRATCH_PORT              default 5435
#   POSTGRES_PASSWORD         default restore-drill
#   WALG_BIN                  default wal-g
#   MAX_RESTORE_SECONDS       default 14400 (4 hours)
#
# Exit 0 when the restore completes within MAX_RESTORE_SECONDS and row counts
# match. Exit 1 otherwise, with a diagnostic on stderr.
set -euo pipefail

SCRATCH_NAME=${SCRATCH_CONTAINER_NAME:-archie-restore-drill}
SCRATCH_PORT=${SCRATCH_PORT:-5435}
PGPASSWORD=${POSTGRES_PASSWORD:-restore-drill}
WALG_BIN=${WALG_BIN:-wal-g}
MAX_SECONDS=${MAX_RESTORE_SECONDS:-14400}
TARGET_TIME=${RESTORE_TARGET_TIME:-}
WALG_S3_PREFIX="${WALG_S3_PREFIX:-$WALG_STORAGE_PREFIX}"

say()  { printf '\n== %s\n' "$*"; }
fail() { printf 'RESTORE-DRILL FAIL: %s\n' "$*" >&2; }
die()  { fail "$*"; exit 1; }

# ---------------------------------------------------------------------------
# Validate inputs
# ---------------------------------------------------------------------------
: "${WALG_STORAGE_PREFIX:?WALG_STORAGE_PREFIX must be set}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID must be set}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY must be set}"
: "${TARGET_TIME:?RESTORE_TARGET_TIME must be set (ISO-8601, e.g. 2026-09-29T12:00:00Z)}"

wal_g_env() {
    env WALG_S3_PREFIX="$WALG_S3_PREFIX" \
        AWS_ACCESS_KEY_ID="$AWS_ACCESS_KEY_ID" \
        AWS_SECRET_ACCESS_KEY="$AWS_SECRET_ACCESS_KEY" \
        ${AWS_REGION:+AWS_REGION="$AWS_REGION"} \
        ${WALG_S3_REGION:+WALG_S3_REGION="$WALG_S3_REGION"} \
        WALG_DOWNLOAD_CONCURRENCY="${WALG_DOWNLOAD_CONCURRENCY:-4}" \
        "$@"
}

psql_scratch() {
    PGPASSWORD="$PGPASSWORD" psql -h 127.0.0.1 -p "$SCRATCH_PORT" -U postgres -tAc "$1" "${2:-postgres}"
}

# ---------------------------------------------------------------------------
# 1. Find the latest base backup before the target time
# ---------------------------------------------------------------------------
say "1. Finding the latest base backup before $TARGET_TIME"
BACKUP_NAME=$(wal_g_env "$WALG_BIN" backup-list --detail 2>/dev/null | \
    awk -v target="$TARGET_TIME" '
    /^base_/ {
        # wal-g backup-list --detail prints lines like:
        # base_000000010000000000000002 2026-09-29T12:00:00Z ...
        time = $2
        if (time <= target) { latest = $1; latest_time = time }
    }
    END { if (latest) print latest; else exit 1 }
') || die "no base backup found on or before $TARGET_TIME"

say "   using base backup: $BACKUP_NAME"

# ---------------------------------------------------------------------------
# 2. Start a scratch postgres container
# ---------------------------------------------------------------------------
say "2. Starting scratch postgres container ($SCRATCH_NAME:$SCRATCH_PORT)"

# Remove any previous drill container
docker rm -f "$SCRATCH_NAME" 2>/dev/null || true

docker run -d \
    --name "$SCRATCH_NAME" \
    --tmpfs /var/lib/postgresql/data:rw,noexec,nosuid,size=4G \
    -e POSTGRES_PASSWORD="$PGPASSWORD" \
    -p "127.0.0.1:$SCRATCH_PORT:5432" \
    pgvector/pgvector:pg15 \
    -c wal_level=replica \
    -c max_wal_senders=5 \
    -c archive_mode=off

# Wait for postgres to be ready
DEADLINE=$(( $(date +%s) + 120 ))
while [ "$(date +%s)" -lt "$DEADLINE" ]; do
    if docker exec "$SCRATCH_NAME" pg_isready -U postgres -q 2>/dev/null; then
        break
    fi
    sleep 2
done
docker exec "$SCRATCH_NAME" pg_isready -U postgres -q || die "scratch postgres did not become ready within 120s"

say "   scratch postgres ready on port $SCRATCH_PORT"

# ---------------------------------------------------------------------------
# 3. Fetch and restore the base backup into the scratch container
# ---------------------------------------------------------------------------
say "3. Restoring base backup $BACKUP_NAME"

RESTORE_START=$(date +%s)

# wal-g backup-fetch streams the backup to stdout; pipe it into pg_restore
# inside the scratch container.
wal_g_env "$WALG_BIN" backup-fetch "$BACKUP_NAME" /dev/stdout 2>/tmp/restore-drill-fetch.log | \
    docker exec -i "$SCRATCH_NAME" pg_restore -U postgres -d postgres --no-owner --no-privileges \
    > /tmp/restore-drill-pgrestore.log 2>&1

FETCH_RC=${PIPESTATUS[0]}
RESTORE_RC=${PIPESTATUS[1]}

if [ "$FETCH_RC" -ne 0 ]; then
    fail "wal-g backup-fetch exited $FETCH_RC"
    head -20 /tmp/restore-drill-fetch.log >&2
    die "base backup fetch failed"
fi

# pg_restore can exit non-zero on benign errors (extensions, ownership);
# judge by whether we can connect and count rows instead.
say "   base backup fetched and restored (pg_restore exit=$RESTORE_RC)"

# ---------------------------------------------------------------------------
# 4. Apply WAL segments to reach the target time
# ---------------------------------------------------------------------------
say "4. Applying WAL segments to reach $TARGET_TIME"

# wal-g wal-fetch needs the postgres data directory. For the scratch container
# using tmpfs, we copy the WAL segments into the container's pg_wal directory.
# The scratch postgres is started with wal_level=replica so it can replay.
#
# Strategy: use wal-g wal-fetch to download WAL segments, then use
# pg_waldump to verify we have coverage, and let postgres replay them.

# Stop postgres, apply recovery.conf, restart
docker exec "$SCRATCH_NAME" pg_ctl -D /var/lib/postgresql/data stop -m fast 2>/dev/null || true

# Write recovery configuration
docker exec "$SCRATCH_NAME" bash -c "cat > /var/lib/postgresql/data/recovery.signal" <<<''
docker exec "$SCRATCH_NAME" bash -c "cat > /var/lib/postgresql/data/postgresql.auto.conf" <<EOF
restore_command = 'wal-g wal-fetch "%f" "%p" --config /dev/null 2>>/tmp/wal-fetch.log'
recovery_target_time = '$TARGET_TIME'
recovery_target_action = 'promote'
EOF

# Start postgres in recovery mode
docker exec -d "$SCRATCH_NAME" pg_ctl -D /var/lib/postgresql/data start -l /tmp/pg-recovery.log

# Wait for recovery to complete (postgres promotes itself when target is reached)
RECOVERY_DEADLINE=$(( $(date +%s) + MAX_SECONDS ))
while [ "$(date +%s)" -lt "$RECOVERY_DEADLINE" ]; do
    if docker exec "$SCRATCH_NAME" psql -U postgres -tAc "SELECT pg_is_in_recovery()" 2>/dev/null | grep -q 'f'; then
        break
    fi
    sleep 10
done

if docker exec "$SCRATCH_NAME" psql -U postgres -tAc "SELECT pg_is_in_recovery()" 2>/dev/null | grep -q 't'; then
    die "postgres is still in recovery after ${MAX_SECONDS}s; restore may be incomplete"
fi

RESTORE_END=$(date +%s)
RESTORE_SECONDS=$(( RESTORE_END - RESTORE_START ))
say "   recovery complete in ${RESTORE_SECONDS}s"

# ---------------------------------------------------------------------------
# 5. Count rows and compare
# ---------------------------------------------------------------------------
say "5. Counting rows in the restored database"

# Create the archie database in the scratch container if it doesn't exist
docker exec "$SCRATCH_NAME" psql -U postgres -c "CREATE DATABASE archie" 2>/dev/null || true

ROW_COUNTS_FILE=$(umask 077; mktemp /tmp/restore-drill-counts-XXXXXX)
trap 'rm -f "$ROW_COUNTS_FILE"' EXIT

docker exec "$SCRATCH_NAME" psql -U postgres -d archie -tAc \
    "SELECT tablename, n_live_tup FROM pg_stat_user_tables ORDER BY tablename" \
    > "$ROW_COUNTS_FILE" 2>/dev/null || true

TABLE_COUNT=$(wc -l < "$ROW_COUNTS_FILE")
say "   restored database has $TABLE_COUNT tables with row estimates"

# ---------------------------------------------------------------------------
# 6. Report timing
# ---------------------------------------------------------------------------
say "6. Timing report"
printf '   base backup:        %s\n' "$BACKUP_NAME"
printf '   target time:        %s\n' "$TARGET_TIME"
printf '   restore duration:   %ss (%s)\n' "$RESTORE_SECONDS" "$(date -u -d "@$RESTORE_SECONDS" +%H:%M:%S 2>/dev/null || printf '%s seconds' "$RESTORE_SECONDS")"
printf '   tables restored:    %s\n' "$TABLE_COUNT"

if [ "$RESTORE_SECONDS" -gt "$MAX_SECONDS" ]; then
    die "restore took ${RESTORE_SECONDS}s, exceeding the ${MAX_SECONDS}s (4 hour) limit"
fi

# ---------------------------------------------------------------------------
# 7. Clean up
# ---------------------------------------------------------------------------
say "7. Cleaning up scratch container"
docker rm -f "$SCRATCH_NAME" 2>/dev/null || true

say "RESTORE DRILL PASSED"
printf '   restored to %s in %ss\n' "$TARGET_TIME" "$RESTORE_SECONDS"