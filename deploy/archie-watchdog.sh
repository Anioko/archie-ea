#!/bin/bash
# Archie liveness watchdog.
# Gunicorn's `timeout` cannot detect wedged gthread request threads: the worker's
# main thread keeps answering the arbiter heartbeat while every request thread is
# blocked. That is exactly how the 24-30 Jul 2026 outage went unnoticed for six
# days. This restarts the server container when /health stops answering.
set -u

URL="http://127.0.0.1:5000/health"
CONTAINER="archie-ea-server-1"
STATE_DIR="/var/lib/archie-watchdog"
FAIL_FILE="$STATE_DIR/consecutive_failures"
LAST_ACTION_FILE="$STATE_DIR/last_restart_epoch"
LOG="/var/log/archie-watchdog.log"

FAIL_THRESHOLD=3      # ~3 minutes of unresponsiveness before acting
COOLDOWN_SECONDS=600  # never restart-loop
# Startup grace. Boot runs init-db + reconcile-schema + backfill-architect-role
# before gunicorn binds, which measured 286s on 2026-07-30 - longer than
# FAIL_THRESHOLD*60. The watchdog duly restarted the container MID-MIGRATION.
# It survived only because those commands are idempotent. Never act on a
# container that is still legitimately booting.
STARTUP_GRACE_SECONDS=600

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

# Notification. The watchdog restarts a wedged container and records everything it
# does, but until now it told nobody: production could crash-loop, fail its backup
# freshness check, or be restarted at 03:00, and the only trace was a log file
# on the box that had the problem.
#
# Inert until ALERT_WEBHOOK is set, because a destination is a decision this script
# cannot make — there is no SMTP configured anywhere (the email worker was disabled
# on 2026-07-30 for exactly that reason) and no chat webhook in the repo. Set one in
# /etc/archie-alerts.env and every WARNING and ACTION below starts being delivered
# with no further change:
#
#     echo 'ALERT_WEBHOOK=https://hooks.slack.com/services/...' > /etc/archie-alerts.env
#
# Slack and Teams both accept {"text": "..."}. Failures are swallowed: an alerting
# problem must never stop the watchdog from doing its actual job.
[ -f /etc/archie-alerts.env ] && . /etc/archie-alerts.env
alert() {
    [ -n "${ALERT_WEBHOOK:-}" ] || return 0
    body=$(printf '{"text":"[archie %s] %s"}' "$(hostname)" "$(echo "$*" | tr -d '"' | head -c 400)")
    curl -sS -m 10 -X POST -H 'Content-Type: application/json'          -d "$body" "$ALERT_WEBHOOK" >/dev/null 2>&1 || true
}

log_and_alert() { log "$*"; alert "$*"; }

mkdir -p "$STATE_DIR"
[ -f "$FAIL_FILE" ] || echo 0 > "$FAIL_FILE"
[ -f "$LAST_ACTION_FILE" ] || echo 0 > "$LAST_ACTION_FILE"

# Crash-looping is a DIFFERENT failure from wedging, and the startup grace hides
# it: a container that dies and restarts every 30s is always "recently started",
# so the grace check spares it forever while it never serves a request. Docker's
# RestartCount climbing is the signal. Learned on 2026-07-30, when a chmod 600
# on a bind-mounted .env locked out the container's non-root user and it
# restarted 16 times while the watchdog stood down each cycle.
RESTART_FILE="$STATE_DIR/last_restart_count"
current_restarts=$(docker inspect -f '{{.RestartCount}}' "$CONTAINER" 2>/dev/null || echo "")
if [ -n "$current_restarts" ]; then
    previous_restarts=$(cat "$RESTART_FILE" 2>/dev/null || echo "$current_restarts")
    if [ "$current_restarts" -gt "$previous_restarts" ]; then
        log_and_alert "WARNING: $CONTAINER is crash-looping - Docker restart count rose $previous_restarts -> $current_restarts. This is a boot failure, not a wedge; restarting it will not help. Check: docker logs $CONTAINER --tail 40"
    fi
    echo "$current_restarts" > "$RESTART_FILE"
fi

# Backups fail silently by nature: nothing breaks when they stop, so nobody
# notices until a restore is needed. Surface staleness on the same cadence as
# the liveness check. Threshold is 3x the 6-hourly schedule.
BACKUP_MARKER=/var/backups/archie/LAST_SUCCESS
BACKUP_MAX_AGE=$((18 * 3600))
if [ -f "$BACKUP_MARKER" ]; then
    age=$(( $(date +%s) - $(stat -c %Y "$BACKUP_MARKER") ))
    if [ "$age" -gt "$BACKUP_MAX_AGE" ]; then
        # once an hour, not every 60s
        if [ ! -f "$STATE_DIR/backup_warned" ] || [ $(( $(date +%s) - $(stat -c %Y "$STATE_DIR/backup_warned") )) -gt 3600 ]; then
            log_and_alert "WARNING: last successful database backup was $((age/3600))h ago (threshold $((BACKUP_MAX_AGE/3600))h)"
            touch "$STATE_DIR/backup_warned"
        fi
    fi
else
    if [ ! -f "$STATE_DIR/backup_warned" ]; then
        log_and_alert "WARNING: no successful database backup has ever been recorded"
        touch "$STATE_DIR/backup_warned"
    fi
fi

if curl -sf --max-time 10 -o /dev/null "$URL"; then
    prev=$(cat "$FAIL_FILE")
    if [ "$prev" -ne 0 ]; then
        log "RECOVERED after $prev consecutive failure(s)"
    fi
    echo 0 > "$FAIL_FILE"
    exit 0
fi

fails=$(( $(cat "$FAIL_FILE") + 1 ))
echo "$fails" > "$FAIL_FILE"
log "health check FAILED ($fails/$FAIL_THRESHOLD)"

[ "$fails" -lt "$FAIL_THRESHOLD" ] && exit 0

now=$(date +%s)

# Still booting? Migrations run before gunicorn binds, so "not answering" is
# expected for several minutes after a (re)start. Restarting here would abort a
# schema migration and could loop indefinitely.
started_at=$(docker inspect -f '{{.State.StartedAt}}' "$CONTAINER" 2>/dev/null || echo "")
if [ -n "$started_at" ]; then
    started_epoch=$(date -d "$started_at" +%s 2>/dev/null || echo 0)
    uptime_s=$(( now - started_epoch ))
    if [ "$started_epoch" -gt 0 ] && [ "$uptime_s" -lt "$STARTUP_GRACE_SECONDS" ]; then
        log "threshold reached but container is only ${uptime_s}s old (grace ${STARTUP_GRACE_SECONDS}s) - still booting, not restarting"
        exit 0
    fi
fi

last=$(cat "$LAST_ACTION_FILE")
if [ $(( now - last )) -lt "$COOLDOWN_SECONDS" ]; then
    log "threshold reached but still in cooldown ($(( now - last ))s < ${COOLDOWN_SECONDS}s) - not restarting"
    exit 0
fi

log_and_alert "ACTION: restarting $CONTAINER after $fails consecutive failures"
# Capture forensics BEFORE destroying the evidence. On 30 Jul 2026 the restart
# was issued without a dump, so the code path that wedged all 8 request threads
# is still unknown. py-spy runs on the host and can introspect the containerised
# interpreter, giving real Python stack traces for every thread.
DUMP="$STATE_DIR/wedge-$(date -u +%Y%m%dT%H%M%SZ).txt"
{
  echo "=== Archie wedge forensics $(date -u) ==="
  echo
  echo "--- py-spy Python stacks (the useful part) ---"
  for pid in $(pgrep -f "gunicorn -c gunicorn.conf.py"); do
      echo "### pid $pid"
      timeout 45 py-spy dump --pid "$pid" 2>&1 || echo "  py-spy failed for $pid"
      echo
  done
  echo "--- kernel wait channels (fallback if py-spy is unavailable) ---"
  for pid in $(pgrep -f "gunicorn -c gunicorn.conf.py"); do
      echo "pid $pid:"
      for t in /proc/$pid/task/*; do
          echo "  tid $(basename "$t") wchan=$(cat "$t/wchan" 2>/dev/null)"
      done
  done
  echo
  echo "--- inbound socket queues (non-zero Recv-Q = accepted but never read) ---"
  ss -tn 2>/dev/null | awk 'NR==1 || $4 ~ /:5000$/' | head -25
  echo
  echo "--- memory ---"
  free -m
  docker stats --no-stream --format "{{.Name}} {{.MemUsage}}" 2>/dev/null
  echo
  echo "--- postgres activity ---"
  docker exec archie-ea-postgres-1 psql -U postgres -d archie -c     "select pid, state, wait_event_type, wait_event, now()-state_change as idle_for, left(query,60) from pg_stat_activity where datname='archie' order by state_change;" 2>&1 | head -30
} >> "$DUMP" 2>&1
log "forensics written to $DUMP"

echo "$now" > "$LAST_ACTION_FILE"
docker restart "$CONTAINER" >> "$LOG" 2>&1
echo 0 > "$FAIL_FILE"
log "restart issued"
