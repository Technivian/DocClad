#!/usr/bin/env bash
# Fail if the archived design constitution is treated as live authority without
# the historical supersession banner, or if the active Governance Charter is missing.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

CHARTER="docs/governance/GOVERNANCE_CHARTER.md"
HISTORICAL="docs/governance/archive/DESIGN_CONSTITUTION.md"
ADR0009="docs/governance/decisions/adr/0009-governance-charter-supersession.md"

if [[ ! -f "$CHARTER" ]]; then
  echo "FAIL: $CHARTER missing (active charter required)"
  exit 1
fi

if ! grep -q 'canonical repository governance document' "$CHARTER"; then
  echo "FAIL: $CHARTER is not marked canonical"
  exit 1
fi

if [[ ! -f "$HISTORICAL" ]]; then
  echo "FAIL: $HISTORICAL must be retained as historical"
  exit 1
fi

if ! grep -q 'HISTORICAL — SUPERSEDED' "$HISTORICAL"; then
  echo "FAIL: $HISTORICAL lacks historical supersession banner"
  exit 1
fi

if ! grep -q '0009-governance-charter-supersession' "$HISTORICAL"; then
  echo "FAIL: $HISTORICAL must link ADR-0009"
  exit 1
fi

if ! grep -q 'Approved by' "$ADR0009"; then
  echo "FAIL: ADR-0009 missing approval authority metadata"
  exit 1
fi

if ! grep -q 'GOVERNANCE_CHARTER.md' docs/design-system/README.md; then
  echo "FAIL: design-system README must reference GOVERNANCE_CHARTER.md"
  exit 1
fi

# Authority order: charter must appear before historical constitution in design-system README.
charter_line=$(rg -n 'GOVERNANCE_CHARTER' docs/design-system/README.md | head -1 | cut -d: -f1)
hist_line=$(rg -n 'DESIGN_CONSTITUTION' docs/design-system/README.md | head -1 | cut -d: -f1)
if [[ -z "$charter_line" || -z "$hist_line" || "$charter_line" -ge "$hist_line" ]]; then
  echo "FAIL: design-system authority order must list GOVERNANCE_CHARTER before DESIGN_CONSTITUTION"
  exit 1
fi

# Proposed Charter v3 must not be presented as approved/active/effective.
if [[ -f docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md ]]; then
  if ! grep -q 'PROPOSED — NOT YET APPROVED' docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md; then
    echo "FAIL: GOVERNANCE_CHARTER_V3_PROPOSED.md must carry a prominent proposed notice"
    exit 1
  fi
  if grep -qiE 'Status:\s*\*\*Approved\*\*|Status:\s*Approved|Status:\s*\*\*Active\*\*|Status:\s*Active' docs/governance/GOVERNANCE_CHARTER_V3_PROPOSED.md; then
    echo "FAIL: GOVERNANCE_CHARTER_V3_PROPOSED.md must not claim Approved/Active status"
    exit 1
  fi
fi
if [[ -f docs/governance/GOVERNANCE_CHARTER_V2_PROPOSED.md ]]; then
  echo "FAIL: stale GOVERNANCE_CHARTER_V2_PROPOSED.md present; use GOVERNANCE_CHARTER_V3_PROPOSED.md"
  exit 1
fi

echo "OK: governance amendment integrity checks passed"
exit 0
