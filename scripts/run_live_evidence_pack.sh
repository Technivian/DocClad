#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
ORG_SLUG="${ORG_SLUG:-demo-firm}"
ORG_NAME="${ORG_NAME:-Demo Firm}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT_DIR/evidence}"
CUTOVER_MODE="${CUTOVER_MODE:-require}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found: $PYTHON_BIN" >&2
  echo "Set PYTHON_BIN or create the virtualenv at .venv." >&2
  exit 1
fi

mkdir -p "$EVIDENCE_DIR"

if [[ "$CUTOVER_MODE" != "require" && "$CUTOVER_MODE" != "warn" ]]; then
  echo "ERROR: CUTOVER_MODE must be 'require' or 'warn' (received: $CUTOVER_MODE)" >&2
  exit 1
fi

echo "==> Running live evidence pack"
echo "Root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
echo "Organization: $ORG_SLUG ($ORG_NAME)"
echo "Evidence dir: $EVIDENCE_DIR"
echo "Cutover mode: $CUTOVER_MODE"

cd "$ROOT_DIR"

echo "==> 1/8 Seed Sprint 3 evidence"
"$PYTHON_BIN" manage.py seed_sprint3_evidence \
  --organization-slug "$ORG_SLUG" \
  --organization-name "$ORG_NAME"

echo "==> 2/8 Verify Postgres cutover"
set +e
"$PYTHON_BIN" manage.py verify_postgres_cutover > "$EVIDENCE_DIR/postgres-cutover-evidence.json"
CUTOVER_EXIT=$?
set -e
if [[ $CUTOVER_EXIT -ne 0 ]]; then
  if [[ "$CUTOVER_MODE" == "require" ]]; then
    echo "ERROR: verify_postgres_cutover returned non-zero and CUTOVER_MODE=require." >&2
    echo "       See $EVIDENCE_DIR/postgres-cutover-evidence.json for details." >&2
    echo "       For local non-Postgres rehearsal only, rerun with CUTOVER_MODE=warn." >&2
    exit 1
  fi
  echo "WARN: verify_postgres_cutover returned non-zero." >&2
  echo "      Continuing because CUTOVER_MODE=warn (local non-Postgres rehearsal)." >&2
fi

echo "==> 3/8 Generate Sprint 3 integration report"
"$PYTHON_BIN" manage.py generate_sprint3_integration_report \
  --days 14 \
  --output "$EVIDENCE_DIR/sprint3-integration-report.json" \
  --fail-on-no-go

echo "==> 4/8 Generate e-sign integration report"
"$PYTHON_BIN" manage.py generate_esign_integration_report \
  --organization-slug "$ORG_SLUG" \
  --days 14 \
  --output "$EVIDENCE_DIR/esign-integration-report.json" \
  --fail-on-no-go

echo "==> 5/8 Generate release gate report"
"$PYTHON_BIN" manage.py generate_release_gate_report \
  --output "$EVIDENCE_DIR/release-gate-report.json" \
  --fail-on-no-go

echo "==> 6/8 Generate executive analytics evidence"
"$PYTHON_BIN" manage.py generate_executive_analytics_evidence \
  --organization-slug "$ORG_SLUG" \
  --output "$EVIDENCE_DIR/executive-analytics-evidence.json"

echo "==> 7/8 Export retention audit actions"
"$PYTHON_BIN" manage.py export_retention_audit_actions \
  --organization-slug "$ORG_SLUG" \
  --days 30 \
  --output "$EVIDENCE_DIR/retention-audit-actions.json"

echo "==> 8/8 Generate release evidence bundle"
"$PYTHON_BIN" manage.py generate_release_evidence_bundle \
  --fail-on-no-go \
  --organization-slug "$ORG_SLUG" \
  --organization-name "$ORG_NAME" \
  --output-dir "$EVIDENCE_DIR/release-bundle"

echo "==> Complete"
echo "Artifacts:"
echo "- $EVIDENCE_DIR/postgres-cutover-evidence.json"
echo "- $EVIDENCE_DIR/sprint3-integration-report.json"
echo "- $EVIDENCE_DIR/esign-integration-report.json"
echo "- $EVIDENCE_DIR/release-gate-report.json"
echo "- $EVIDENCE_DIR/executive-analytics-evidence.json"
echo "- $EVIDENCE_DIR/retention-audit-actions.json"
echo "- $EVIDENCE_DIR/release-bundle/release-evidence-bundle.json"
