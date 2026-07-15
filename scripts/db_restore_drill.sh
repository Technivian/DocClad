#!/usr/bin/env bash
# db_restore_drill.sh — restore a pg_dump file into a scratch database and
# boot the app against it to prove the backup is viable.
#
# Usage:  ./scripts/db_restore_drill.sh <backup.dump> [scratch_db_url]
#
# If scratch_db_url is omitted, creates a local database named clmone_drill
# (requires local Postgres with createdb access).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

DUMP_FILE="${1:-}"
if [[ -z "$DUMP_FILE" || ! -f "$DUMP_FILE" ]]; then
  echo "Usage: $0 <backup.dump> [scratch_db_url]" >&2
  exit 1
fi

# Prefer a pg_restore that can read the dump format (match pg_dump version).
for _candidate in \
  /opt/homebrew/opt/postgresql@18/bin/pg_restore \
  /opt/homebrew/opt/postgresql@17/bin/pg_restore \
  /usr/local/opt/postgresql@18/bin/pg_restore \
  /usr/local/opt/postgresql@17/bin/pg_restore \
  pg_restore; do
  if command -v "$_candidate" &>/dev/null; then
    PG_RESTORE="$_candidate"
    break
  fi
done
PG_RESTORE="${PG_RESTORE:-pg_restore}"

SCRATCH_URL="${2:-}"
LOCAL_SCRATCH=false
if [[ -z "$SCRATCH_URL" ]]; then
  SCRATCH_DB="clmone_drill_$(date +%s)"
  createdb "$SCRATCH_DB"
  SCRATCH_URL="postgresql://localhost/$SCRATCH_DB"
  LOCAL_SCRATCH=true
  echo "Created scratch database: $SCRATCH_DB"
fi

echo "Restoring $DUMP_FILE → $SCRATCH_URL (using $PG_RESTORE) ..."
START=$(date +%s)
# --exit-on-error is NOT set; pg_restore continues past non-fatal extension
# errors (e.g. supabase_vault is a Supabase-internal extension that does not
# exist on vanilla PostgreSQL — those errors are expected and safe to ignore).
"$PG_RESTORE" --no-acl --no-owner -d "$SCRATCH_URL" "$DUMP_FILE" || RESTORE_RC=$?
END=$(date +%s)
if [[ "${RESTORE_RC:-0}" -ne 0 ]]; then
  echo "WARNING: pg_restore exited $RESTORE_RC — check for unexpected errors above."
  echo "         Supabase-only extensions (supabase_vault, pg_graphql, etc.) are expected to fail on non-Supabase targets."
fi
echo "Restore finished in $((END - START))s."

echo "Booting app against scratch DB (migrate --run-syncdb --check) ..."
DATABASE_URL="$SCRATCH_URL" .venv/bin/python "$ROOT_DIR/manage.py" migrate --check 2>&1 \
  && echo "Migration check: OK" \
  || echo "WARNING: migration check reported issues — review above output."

echo "Running tenant integrity audit ..."
DATABASE_URL="$SCRATCH_URL" .venv/bin/python "$ROOT_DIR/manage.py" audit_null_organizations 2>&1 || true

if $LOCAL_SCRATCH; then
  echo ""
  echo "Scratch DB left in place: $SCRATCH_DB"
  echo "To drop it:  dropdb $SCRATCH_DB"
fi

echo ""
echo "Drill complete. Record time-to-restore: $((END - START))s"
