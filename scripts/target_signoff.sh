#!/usr/bin/env bash
# target_signoff.sh — single-command target-environment Sprint 3 signoff
#
# Usage:
#   ./scripts/target_signoff.sh
#
# Required env (set these before running):
#   DATABASE_URL           postgresql://<user>:<pass>@<host>:5432/<db>?sslmode=require
#   DJANGO_SECRET_KEY      long random secret
#   ALLOWED_HOSTS          your-staging-hostname.example.com
#   CSRF_TRUSTED_ORIGINS   https://your-staging-hostname.example.com
#
# Optional env (defaults shown):
#   ORG_SLUG               demo-firm
#   ORG_NAME               Demo Firm
#   DEFAULT_FROM_EMAIL     ops@example.com
#   SIGNOFF_OUTPUT         evidence/target-signoff-report.json
#   CUTOVER_MODE           require

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT_DIR/evidence}"
SIGNOFF_OUTPUT="${SIGNOFF_OUTPUT:-$EVIDENCE_DIR/target-signoff-report.json}"
ORG_SLUG="${ORG_SLUG:-demo-firm}"
ORG_NAME="${ORG_NAME:-Demo Firm}"

# ── preflight ──────────────────────────────────────────────────────────────────

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python not found: $PYTHON_BIN" >&2; exit 1
fi

: "${DATABASE_URL:?DATABASE_URL must be set to a PostgreSQL connection string}"
: "${DJANGO_SECRET_KEY:?DJANGO_SECRET_KEY must be set}"
: "${ALLOWED_HOSTS:?ALLOWED_HOSTS must be set}"
: "${CSRF_TRUSTED_ORIGINS:?CSRF_TRUSTED_ORIGINS must be set}"

export DJANGO_ENV=production
export DEFAULT_FROM_EMAIL="${DEFAULT_FROM_EMAIL:-ops@example.com}"
export DB_SSL_REQUIRE="${DB_SSL_REQUIRE:-true}"
export SECURE_SSL_REDIRECT="${SECURE_SSL_REDIRECT:-true}"
export SECURE_HSTS_PRELOAD="${SECURE_HSTS_PRELOAD:-true}"
export CUTOVER_MODE="${CUTOVER_MODE:-require}"
export ORG_SLUG ORG_NAME EVIDENCE_DIR PYTHON_BIN

SIGNOFF_TS="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
COMMIT_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
COMMIT_SHORT="${COMMIT_SHA:0:7}"
# Allow operator to set an explicit pg_dump/pg_restore binary directory.
# On Apple Silicon with Homebrew PG16: /opt/homebrew/opt/postgresql@16/bin
# On Render (Ubuntu, PG16): /usr/lib/postgresql/16/bin  (or just PATH)
PG_BIN_DIR="${PG_BIN_DIR:-}"
if [[ -z "$PG_BIN_DIR" ]]; then
  for _candidate in \
      /opt/homebrew/opt/postgresql@16/bin \
      /usr/lib/postgresql/16/bin \
      /usr/pgsql-16/bin; do
    if [[ -x "$_candidate/pg_dump" ]]; then
      PG_BIN_DIR="$_candidate"; break
    fi
  done
fi
PG_DUMP="${PG_BIN_DIR:+$PG_BIN_DIR/}pg_dump"
PG_RESTORE="${PG_BIN_DIR:+$PG_BIN_DIR/}pg_restore"
PSQL_BIN="${PG_BIN_DIR:+$PG_BIN_DIR/}psql"
# Set SKIP_DRILL=true to skip the backup/restore drill if already run this session.
SKIP_DRILL="${SKIP_DRILL:-false}"

mkdir -p "$EVIDENCE_DIR"

echo "================================================================"
echo " CLM One Target Signoff"
echo " Timestamp : $SIGNOFF_TS"
echo " Commit    : $COMMIT_SHORT"
echo " Org       : $ORG_SLUG ($ORG_NAME)"
echo " Host      : ${ALLOWED_HOSTS}"
echo "================================================================"

# ── step 1: django preflight ───────────────────────────────────────────────────

echo ""
echo "── Step 1/4: Django preflight"
# Only run the deploy security check when the environment is actually
# production-shaped (SSL redirect enabled). Local rehearsals with SSL
# disabled intentionally skip it.
if [[ "${SECURE_SSL_REDIRECT:-true}" == "true" ]]; then
  "$PYTHON_BIN" manage.py check --deploy --fail-level WARNING
else
  echo "SKIPPING deploy check: SECURE_SSL_REDIRECT=false (local/rehearsal mode)"
  "$PYTHON_BIN" manage.py check --fail-level ERROR
fi
"$PYTHON_BIN" manage.py migrate --noinput
"$PYTHON_BIN" manage.py audit_null_organizations

# ── step 2: evidence pack ──────────────────────────────────────────────────────

echo ""
echo "── Step 2/4: Sprint 3 evidence pack"
"$ROOT_DIR/scripts/run_live_evidence_pack.sh"

# ── step 3: backup/restore drill ──────────────────────────────────────────────

echo ""
echo "── Step 3/4: Backup/restore rehearsal"
DRILL_START="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DRILL_START_EPOCH="$(date +%s)"
BACKUP_FILE="$EVIDENCE_DIR/target-backup-$(date +%Y%m%dT%H%M%S).dump"
RESTORE_DB="${ORG_SLUG//-/_}_signoff_restore_$(date +%Y%m%d)"

# extract db name from DATABASE_URL for pg_dump (strips query string)
DB_URL_NOQUERY="${DATABASE_URL%%\?*}"
PG_RESTORE_DB_URL="${DB_URL_NOQUERY%/*}/${RESTORE_DB}"

if [[ "$SKIP_DRILL" == "true" ]]; then
  echo "SKIP_DRILL=true — backup/restore drill skipped by operator (must already be on record in DRILL_LOG.md)"
  DRILL_OUTCOME="PREVIOUSLY_COMPLETED"
  BACKUP_FILE="none"
  BACKUP_SIZE=0
  RESTORE_DB="none"
else
  "$PG_DUMP" -Fc "$DATABASE_URL" > "$BACKUP_FILE" || {
    echo "WARN: pg_dump failed — backup artifact not produced. Skipping restore drill." >&2
    echo "      Hint: set PG_BIN_DIR to the directory containing pg_dump matching your server version." >&2
    DRILL_OUTCOME="SKIPPED"
  }

  if [[ "${DRILL_OUTCOME:-}" != "SKIPPED" ]]; then
    BACKUP_SIZE="$(stat -c%s "$BACKUP_FILE" 2>/dev/null || stat -f%z "$BACKUP_FILE" 2>/dev/null || echo 0)"
    DB_BASE_URL="${DB_URL_NOQUERY%/*}/postgres"
    "$PSQL_BIN" "$DB_BASE_URL" -c "DROP DATABASE IF EXISTS $RESTORE_DB;"
    "$PSQL_BIN" "$DB_BASE_URL" -c "CREATE DATABASE $RESTORE_DB;"
    "$PG_RESTORE" -d "$PG_RESTORE_DB_URL" "$BACKUP_FILE"
    DATABASE_URL="$PG_RESTORE_DB_URL" "$PYTHON_BIN" manage.py audit_null_organizations > "$EVIDENCE_DIR/target-restore-audit.txt"
    DATABASE_URL="$PG_RESTORE_DB_URL" "$PYTHON_BIN" manage.py verify_postgres_cutover > "$EVIDENCE_DIR/target-restore-cutover.json"
    DATABASE_URL="$PG_RESTORE_DB_URL" "$PYTHON_BIN" manage.py migrate --check
    DRILL_OUTCOME="PASS"
  fi
fi

DRILL_END="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DRILL_ELAPSED="$(($(date +%s) - DRILL_START_EPOCH))s"

# ── step 4: read artifacts and emit verdict ────────────────────────────────────

echo ""
echo "── Step 4/4: Reading artifacts and computing verdict"

read_json_field() {
  local file="$1" field="$2" default="${3:-MISSING}"
  if [[ -f "$file" ]]; then
    python3 -c "
import json, sys
try:
    d = json.load(open('$file'))
    keys = '$field'.split('.')
    for k in keys:
        d = d[k]
    print(d)
except Exception:
    print('$default')
"
  else
    echo "$default"
  fi
}

CUTOVER_READY="$(read_json_field "$EVIDENCE_DIR/postgres-cutover-evidence.json" "cutover_ready" "false")"
SPRINT3_STATUS="$(read_json_field "$EVIDENCE_DIR/sprint3-integration-report.json" "status" "MISSING")"
ESIGN_STATUS="$(read_json_field "$EVIDENCE_DIR/esign-integration-report.json" "status" "MISSING")"
RELEASE_GATE="$(read_json_field "$EVIDENCE_DIR/release-gate-report.json" "go_no_go" "MISSING")"
BUNDLE_GATE="$(read_json_field "$EVIDENCE_DIR/release-bundle/release-evidence-bundle.json" "go_no_go" "MISSING")"
ANALYTICS_TS="$(read_json_field "$EVIDENCE_DIR/executive-analytics-evidence.json" "captured_at" "MISSING")"
RETENTION_TS="$(read_json_field "$EVIDENCE_DIR/retention-audit-actions.json" "captured_at" "MISSING")"

# compute final verdict
FINAL="GO"
FAILURES=""

[[ "$CUTOVER_READY" != "True" && "$CUTOVER_READY" != "true" ]] && { FINAL="NO-GO"; FAILURES+=" postgres_cutover_not_ready"; }
[[ "$SPRINT3_STATUS" != "GO" ]] && { FINAL="NO-GO"; FAILURES+=" sprint3_integration_not_go"; }
[[ "$ESIGN_STATUS" != "GO" ]] && { FINAL="NO-GO"; FAILURES+=" esign_integration_not_go"; }
[[ "$RELEASE_GATE" != "GO" ]] && { FINAL="NO-GO"; FAILURES+=" release_gate_not_go"; }
[[ "$BUNDLE_GATE" != "GO" ]] && { FINAL="NO-GO"; FAILURES+=" release_bundle_not_go"; }
[[ "$ANALYTICS_TS" == "MISSING" ]] && { FINAL="NO-GO"; FAILURES+=" executive_analytics_missing"; }
[[ "$RETENTION_TS" == "MISSING" ]] && { FINAL="NO-GO"; FAILURES+=" retention_audit_missing"; }
# SKIPPED means pg_dump failed at runtime — operator error; PREVIOUSLY_COMPLETED is an explicit accepted override
_DRILL_VAL="${DRILL_OUTCOME:-SKIPPED}"
[[ "$_DRILL_VAL" != "PASS" && "$_DRILL_VAL" != "PREVIOUSLY_COMPLETED" ]] && { FINAL="NO-GO"; FAILURES+=" backup_drill_skipped"; }

# write machine-readable report
cat > "$SIGNOFF_OUTPUT" <<EOF
{
  "signoff_at": "$SIGNOFF_TS",
  "commit": "$COMMIT_SHORT",
  "commit_sha": "$COMMIT_SHA",
  "environment": {
    "allowed_hosts": "${ALLOWED_HOSTS}",
    "org_slug": "$ORG_SLUG",
    "org_name": "$ORG_NAME"
  },
  "gates": {
    "postgres_cutover_ready": "$CUTOVER_READY",
    "sprint3_integration": "$SPRINT3_STATUS",
    "esign_integration": "$ESIGN_STATUS",
    "release_gate": "$RELEASE_GATE",
    "release_bundle": "$BUNDLE_GATE",
    "executive_analytics_captured_at": "$ANALYTICS_TS",
    "retention_audit_captured_at": "$RETENTION_TS",
    "backup_restore_drill": "${DRILL_OUTCOME:-SKIPPED}"
  },
  "drill": {
    "start": "$DRILL_START",
    "end": "$DRILL_END",
    "elapsed": "$DRILL_ELAPSED",
    "backup_file": "${BACKUP_FILE:-none}",
    "backup_size_bytes": "${BACKUP_SIZE:-0}",
    "restore_db": "${RESTORE_DB:-none}",
    "outcome": "${DRILL_OUTCOME:-SKIPPED}"
  },
  "failures": [$(echo "$FAILURES" | tr ' ' '\n' | grep -v '^$' | sed 's/^/    "/' | sed 's/$/"/' | paste -sd ',' -)],
  "final_decision": "$FINAL"
}
EOF

# ── human-readable readout ─────────────────────────────────────────────────────

echo ""
echo "================================================================"
echo " Live Evidence Readout"
echo " Environment   : ${ALLOWED_HOSTS}"
echo " Commit        : $COMMIT_SHORT"
echo " Postgres Cutover Ready : $CUTOVER_READY"
echo " Sprint3 Integration    : $SPRINT3_STATUS"
echo " E-sign Integration     : $ESIGN_STATUS"
echo " Release Gate           : $RELEASE_GATE"
echo " Release Bundle         : $BUNDLE_GATE"
echo " Executive Analytics    : ${ANALYTICS_TS:0:19}"
echo " Retention Audit        : ${RETENTION_TS:0:19}"
echo " Backup/Restore Drill   : ${DRILL_OUTCOME:-SKIPPED}"
echo "----------------------------------------------------------------"
echo " Final Decision         : $FINAL"
echo "================================================================"
echo ""
echo "Signoff report: $SIGNOFF_OUTPUT"

if [[ "$FINAL" == "NO-GO" ]]; then
  echo "FAILED gates:$FAILURES" >&2
  exit 1
fi
