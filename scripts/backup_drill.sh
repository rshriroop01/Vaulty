#!/usr/bin/env bash
# scripts/backup_drill.sh — M10 hardening: backup & restore drill.
#
# pg_dumps the docker-compose Postgres, restores the dump into a throwaway
# scratch database on the SAME server, then diffs row counts on a handful of
# key tables between source and restored copies. Prints PASS/FAIL and exits
# non-zero on any mismatch or step failure, so it's CI/cron-friendly.
#
# Uses `docker compose exec`/`cp` against the `postgres` service rather than
# requiring pg_dump/psql on the host — the only local dependency is Docker.
#
# Usage: scripts/backup_drill.sh
set -euo pipefail

COMPOSE=(docker compose)
DB_SERVICE=postgres
DB_USER=vaultly
SOURCE_DB=vaultly
SCRATCH_DB=vaultly_restore_drill
REMOTE_DUMP=/tmp/vaultly_backup_drill.dump
LOCAL_DUMP="$(mktemp -t vaultly-backup-drill-XXXXXX.dump)"

# A representative slice, not every table: enough to catch a broken dump/
# restore (a table with zero rows copied, a FK-order failure, etc.) without
# hardcoding the full, evolving schema here.
TABLES=(users vaults vault_memberships documents reminders audit_log feature_flags)

cleanup() {
  rm -f "$LOCAL_DUMP"
}
trap cleanup EXIT

echo "==> Vaultly backup/restore drill — $(date -u +%FT%TZ)"

if ! "${COMPOSE[@]}" ps --status running --services 2>/dev/null | grep -qx "$DB_SERVICE"; then
  echo "FAIL: the '$DB_SERVICE' service is not running (docker compose up -d postgres)"
  exit 1
fi

echo "==> 1/5 pg_dump $SOURCE_DB (custom format)"
"${COMPOSE[@]}" exec -T "$DB_SERVICE" pg_dump -U "$DB_USER" -d "$SOURCE_DB" -F c -f "$REMOTE_DUMP"
"${COMPOSE[@]}" cp "$DB_SERVICE:$REMOTE_DUMP" "$LOCAL_DUMP"
DUMP_SIZE=$(wc -c <"$LOCAL_DUMP" | tr -d '[:space:]')
echo "    dump pulled to host: $LOCAL_DUMP ($DUMP_SIZE bytes)"

echo "==> 2/5 create scratch database $SCRATCH_DB"
"${COMPOSE[@]}" exec -T "$DB_SERVICE" psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS $SCRATCH_DB;" \
  -c "CREATE DATABASE $SCRATCH_DB OWNER $DB_USER;"

echo "==> 3/5 restore dump into scratch database"
"${COMPOSE[@]}" exec -T "$DB_SERVICE" pg_restore -U "$DB_USER" -d "$SCRATCH_DB" \
  --no-owner --no-privileges "$REMOTE_DUMP"

echo "==> 4/5 row-count sanity diff (source vs. restored)"
FAIL=0
for t in "${TABLES[@]}"; do
  src=$("${COMPOSE[@]}" exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$SOURCE_DB" -tAc \
    "SELECT COUNT(*) FROM $t;" | tr -d '[:space:]')
  dst=$("${COMPOSE[@]}" exec -T "$DB_SERVICE" psql -U "$DB_USER" -d "$SCRATCH_DB" -tAc \
    "SELECT COUNT(*) FROM $t;" | tr -d '[:space:]')
  if [ "$src" = "$dst" ]; then
    printf '    %-20s source=%-6s restored=%-6s OK\n' "$t" "$src" "$dst"
  else
    printf '    %-20s source=%-6s restored=%-6s MISMATCH\n' "$t" "$src" "$dst"
    FAIL=1
  fi
done

echo "==> 5/5 cleanup (drop scratch database + remote dump file)"
"${COMPOSE[@]}" exec -T "$DB_SERVICE" psql -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1 \
  -c "DROP DATABASE IF EXISTS $SCRATCH_DB;"
"${COMPOSE[@]}" exec -T "$DB_SERVICE" rm -f "$REMOTE_DUMP"

if [ "$FAIL" -eq 0 ]; then
  echo "==> PASS: dump/restore round-trip verified, all sampled row counts match"
  exit 0
else
  echo "==> FAIL: one or more tables mismatched after restore"
  exit 1
fi
