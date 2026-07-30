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
COOLDOWN_SECONDS=600  # app needs ~70s to boot; never restart-loop

log() { echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) $*" >> "$LOG"; }

mkdir -p "$STATE_DIR"
[ -f "$FAIL_FILE" ] || echo 0 > "$FAIL_FILE"
[ -f "$LAST_ACTION_FILE" ] || echo 0 > "$LAST_ACTION_FILE"

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
last=$(cat "$LAST_ACTION_FILE")
if [ $(( now - last )) -lt "$COOLDOWN_SECONDS" ]; then
    log "threshold reached but still in cooldown ($(( now - last ))s < ${COOLDOWN_SECONDS}s) - not restarting"
    exit 0
fi

log "ACTION: restarting $CONTAINER after $fails consecutive failures"
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
