#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT_DIR/evidence}"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found: $PYTHON_BIN" >&2
  exit 1
fi

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "ERROR: DATABASE_URL must be set for target-environment execution." >&2
  exit 1
fi

if [[ -z "${DJANGO_SECRET_KEY:-}" ]]; then
  echo "ERROR: DJANGO_SECRET_KEY must be set for target-environment execution." >&2
  exit 1
fi

if [[ -z "${ORG_SLUG:-}" || -z "${ORG_NAME:-}" ]]; then
  echo "ERROR: ORG_SLUG and ORG_NAME must be set." >&2
  exit 1
fi

echo "==> Running strict target signoff gate"
echo "Root: $ROOT_DIR"
echo "Evidence dir: $EVIDENCE_DIR"

cd "$ROOT_DIR"

CUTOVER_MODE=require ./scripts/run_live_evidence_pack.sh

CUTOVER_JSON="$EVIDENCE_DIR/postgres-cutover-evidence.json"
SPRINT3_JSON="$EVIDENCE_DIR/sprint3-integration-report.json"
ESIGN_JSON="$EVIDENCE_DIR/esign-integration-report.json"
RELEASE_JSON="$EVIDENCE_DIR/release-gate-report.json"
BUNDLE_JSON="$EVIDENCE_DIR/release-bundle/release-evidence-bundle.json"
EXEC_JSON="$EVIDENCE_DIR/executive-analytics-evidence.json"
RET_JSON="$EVIDENCE_DIR/retention-audit-actions.json"

for f in "$CUTOVER_JSON" "$SPRINT3_JSON" "$ESIGN_JSON" "$RELEASE_JSON" "$BUNDLE_JSON" "$EXEC_JSON" "$RET_JSON"; do
  if [[ ! -f "$f" ]]; then
    echo "ERROR: Missing expected artifact: $f" >&2
    exit 1
  fi
done

SUMMARY_JSON="$EVIDENCE_DIR/target-signoff-summary.json"

"$PYTHON_BIN" - <<'PY' "$CUTOVER_JSON" "$SPRINT3_JSON" "$ESIGN_JSON" "$RELEASE_JSON" "$BUNDLE_JSON" "$SUMMARY_JSON"
import json
import sys
from pathlib import Path

cutover_path, sprint3_path, esign_path, release_path, bundle_path, out_path = [Path(p) for p in sys.argv[1:7]]

cutover = json.loads(cutover_path.read_text(encoding="utf-8"))
sprint3 = json.loads(sprint3_path.read_text(encoding="utf-8"))
esign = json.loads(esign_path.read_text(encoding="utf-8"))
release = json.loads(release_path.read_text(encoding="utf-8"))
bundle = json.loads(bundle_path.read_text(encoding="utf-8"))

result = {
    "cutover_ready": bool(cutover.get("cutover_ready")),
    "sprint3_status": sprint3.get("status"),
    "esign_status": esign.get("status"),
    "release_gate": release.get("go_no_go"),
    "bundle_gate": bundle.get("go_no_go"),
}

is_go = (
    result["cutover_ready"]
    and result["sprint3_status"] == "GO"
    and result["esign_status"] == "GO"
    and result["release_gate"] == "GO"
    and result["bundle_gate"] == "GO"
)
result["decision"] = "GO" if is_go else "NO-GO"

out_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(json.dumps(result, indent=2, sort_keys=True))

if not is_go:
    raise SystemExit(2)
PY

echo "==> Target signoff gate result: GO"
echo "Summary: $SUMMARY_JSON"
echo "Next required non-automated steps:"
echo "- Execute manual smoke checklist and update evidence/manual-smoke-signoff.md"
echo "- Run target backup/restore drill and append docs/DRILL_LOG.md"
