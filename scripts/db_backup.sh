#!/usr/bin/env bash
# db_backup.sh — dump the CLM One PostgreSQL database to a timestamped file,
# VERIFY it is non-empty and restorable, and optionally upload it offsite.
#
# Usage:  ./scripts/db_backup.sh [output_dir]
# Reads DATABASE_URL from the environment (or .env if present).
#
# Roadmap B7: the previous version could leave a silent 0-byte "backup" on
# failure. This version fails loudly, deletes partial dumps, asserts a minimum
# size, verifies the archive with `pg_restore --list`, and (when BACKUP_S3_URL
# is set) pushes the dump to object storage so backups survive host loss.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Minimum plausible size for a real custom-format dump (bytes). A healthy DB
# with the current schema dumps to tens of KB+; anything under this is a failed
# or empty dump and must be treated as an error.
MIN_BACKUP_BYTES="${MIN_BACKUP_BYTES:-10240}"

# Load .env if present and DATABASE_URL not already set
if [[ -z "${DATABASE_URL:-}" && -f "$ROOT_DIR/.env" ]]; then
  export $(grep -v '^#' "$ROOT_DIR/.env" | grep DATABASE_URL | xargs)
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL is not set." >&2
  exit 1
fi

# Prefer a pg_dump that matches the server version (17/18) over the system default (14).
for _candidate in \
  /opt/homebrew/opt/postgresql@18/bin/pg_dump \
  /opt/homebrew/opt/postgresql@17/bin/pg_dump \
  /usr/local/opt/postgresql@18/bin/pg_dump \
  /usr/local/opt/postgresql@17/bin/pg_dump \
  pg_dump; do
  if command -v "$_candidate" &>/dev/null; then
    PG_DUMP="$_candidate"
    break
  fi
done
PG_DUMP="${PG_DUMP:-pg_dump}"
PG_RESTORE="${PG_DUMP%pg_dump}pg_restore"
command -v "$PG_RESTORE" &>/dev/null || PG_RESTORE="pg_restore"

OUTPUT_DIR="${1:-$ROOT_DIR/backups}"
mkdir -p "$OUTPUT_DIR"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
OUTFILE="$OUTPUT_DIR/clmone_${TIMESTAMP}.dump"

# Delete a partial/failed dump on any error so we never leave a misleading file.
cleanup_on_error() {
  if [[ -f "$OUTFILE" ]]; then
    echo "ERROR: backup failed — removing partial file $OUTFILE" >&2
    rm -f "$OUTFILE"
  fi
}
trap cleanup_on_error ERR

echo "Backing up to $OUTFILE (using $PG_DUMP) ..."
"$PG_DUMP" --format=custom --no-acl --no-owner "$DATABASE_URL" -f "$OUTFILE"

# --- Verify: file exists and is above the minimum plausible size ---
if [[ ! -f "$OUTFILE" ]]; then
  echo "ERROR: pg_dump reported success but no file was produced." >&2
  exit 1
fi
BYTES=$(wc -c < "$OUTFILE" | tr -d ' ')
if (( BYTES < MIN_BACKUP_BYTES )); then
  echo "ERROR: backup is only ${BYTES} bytes (< ${MIN_BACKUP_BYTES}). Treating as failure." >&2
  rm -f "$OUTFILE"
  exit 1
fi

# --- Verify: archive is structurally readable/restorable ---
if ! "$PG_RESTORE" --list "$OUTFILE" >/dev/null 2>&1; then
  echo "ERROR: pg_restore could not read the archive — backup is corrupt." >&2
  rm -f "$OUTFILE"
  exit 1
fi

trap - ERR

SIZE=$(du -sh "$OUTFILE" | cut -f1)
echo "OK. Verified backup $OUTFILE ($SIZE, ${BYTES} bytes), archive is restorable."

# --- Optional: push offsite to object storage ---
# Set BACKUP_S3_URL (e.g. s3://my-bucket/db-backups/) to enable. Uses the AWS
# CLI; for Supabase/other S3-compatible storage set AWS_S3_ENDPOINT_URL too.
if [[ -n "${BACKUP_S3_URL:-}" ]]; then
  if command -v aws &>/dev/null; then
    EXTRA_ARGS=()
    [[ -n "${AWS_S3_ENDPOINT_URL:-}" ]] && EXTRA_ARGS+=(--endpoint-url "$AWS_S3_ENDPOINT_URL")
    echo "Uploading to ${BACKUP_S3_URL%/}/$(basename "$OUTFILE") ..."
    aws "${EXTRA_ARGS[@]}" s3 cp "$OUTFILE" "${BACKUP_S3_URL%/}/$(basename "$OUTFILE")"
    echo "Offsite upload complete."
  else
    echo "WARNING: BACKUP_S3_URL set but 'aws' CLI not found — skipping offsite upload." >&2
    exit 1
  fi
fi
