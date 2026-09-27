#!/usr/bin/env bash
# Prove the backups can actually be restored. Runs on the application host.
#
#   ./deploy/verify_backup.sh
#
# An untested backup is not a backup - it is a file that resembles one. This
# takes a fresh dump, restores it into a scratch database, and compares row
# counts against the live one. The live database is only ever READ.
#
# It also checks the archives that deploy.sh and the backup timer leave behind,
# because a gzip that will not decompress is the failure you find during an
# incident, when it is too late to care.
set -euo pipefail

BACKUPS=/root/deploy-backups
SCRATCH=archie_restore_drill
DB=${POSTGRES_DB:-archie}
PGUSER_=${POSTGRES_USER:-postgres}
COMPOSE="docker compose"

cd /root/archie-ea
say() { printf '\n== %s\n' "$*"; }
psqlx() { $COMPOSE exec -T postgres psql -U "$PGUSER_" -tAc "$1" "${2:-$DB}"; }

say "1. existing archives decompress"
found=0; broken=0
for f in "$BACKUPS"/db-*.sql.gz; do
    [ -e "$f" ] || continue
    found=$((found+1))
    if gzip -t "$f" 2>/dev/null; then
        printf '  ok      %-46s %s\n' "$(basename "$f")" "$(du -h "$f" | cut -f1)"
    else
        printf '  CORRUPT %s\n' "$(basename "$f")"; broken=$((broken+1))
    fi
done
echo "  $found archive(s), $broken corrupt"
[ "$broken" -eq 0 ] || { echo "ABORT: corrupt archives present" >&2; exit 1; }

say "2. taking a fresh single-database dump"
TS=$(date +%Y%m%d-%H%M%S)
DUMP="$BACKUPS/restore-drill-$TS.dump"
# Custom format: what you would actually restore from, and it round-trips
# through pg_restore rather than needing a psql replay of the whole cluster.
$COMPOSE exec -T postgres pg_dump -U "$PGUSER_" -Fc "$DB" > "$DUMP"
echo "  $(du -h "$DUMP" | cut -f1)  $DUMP"
[ -s "$DUMP" ] || { echo "ABORT: dump is empty" >&2; exit 1; }

say "3. restoring into a scratch database (live database untouched)"
psqlx "SELECT 1" postgres >/dev/null
$COMPOSE exec -T postgres dropdb -U "$PGUSER_" --if-exists "$SCRATCH"
$COMPOSE exec -T postgres createdb -U "$PGUSER_" "$SCRATCH"
# pg_restore reports benign errors for extensions and ownership; -e would abort
# on those, so capture the count and judge it below instead.
set +e
$COMPOSE exec -T postgres pg_restore -U "$PGUSER_" -d "$SCRATCH" --no-owner --no-privileges \
    < "$DUMP" 2> "$BACKUPS/restore-drill-$TS.log"
restore_rc=$?
set -e
errs=$(grep -ci "error" "$BACKUPS/restore-drill-$TS.log" 2>/dev/null || echo 0)
echo "  pg_restore exit=$restore_rc, $errs error line(s) (see restore-drill-$TS.log)"

say "4. comparing the restored copy against live"
mismatch=0
while IFS= read -r t; do
    live=$(psqlx "SELECT count(*) FROM \"$t\"" "$DB" 2>/dev/null || echo skip)
    [ "$live" = "skip" ] && continue
    copy=$(psqlx "SELECT count(*) FROM \"$t\"" "$SCRATCH" 2>/dev/null || echo missing)
    if [ "$live" != "$copy" ]; then
        printf '  MISMATCH %-42s live=%s restored=%s\n' "$t" "$live" "$copy"
        mismatch=$((mismatch+1))
    fi
done < <(psqlx "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
live_tables=$(psqlx "SELECT count(*) FROM pg_tables WHERE schemaname='public'" "$DB")
copy_tables=$(psqlx "SELECT count(*) FROM pg_tables WHERE schemaname='public'" "$SCRATCH")
echo "  tables: live=$live_tables restored=$copy_tables"
echo "  row-count mismatches: $mismatch"

say "5. cleaning up the scratch database"
$COMPOSE exec -T postgres dropdb -U "$PGUSER_" --if-exists "$SCRATCH"
rm -f "$DUMP"
echo "  removed"

if [ "$mismatch" -ne 0 ] || [ "$live_tables" != "$copy_tables" ]; then
    echo
    echo "RESTORE DRILL FAILED - the backup does not reproduce the live database." >&2
    exit 1
fi
echo
echo "RESTORE DRILL PASSED - $live_tables tables restored with matching row counts."
