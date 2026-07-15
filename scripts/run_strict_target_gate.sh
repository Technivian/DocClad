#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/.venv/bin/python}"
TARGET_HOST="${TARGET_HOST:-clmone-preview.onrender.com}"
TARGET_ORIGIN="${TARGET_ORIGIN:-https://$TARGET_HOST}"
TARGET_DB_URL="${TARGET_DB_URL:-}"
TARGET_SECRET_KEY="${TARGET_SECRET_KEY:-}"
RELEASE_COMMIT_SHA="${RELEASE_COMMIT_SHA:-fe77689e61163763a7836b9359c57281cb1b04db}"
ORG_SLUG="${ORG_SLUG:-demo-firm}"
ORG_NAME="${ORG_NAME:-Demo Firm}"
EVIDENCE_DIR="${EVIDENCE_DIR:-$ROOT_DIR/evidence/strict-target-gate-$(date +%Y%m%dT%H%M%S)}"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "ERROR: Python executable not found: $PYTHON_BIN" >&2
  echo "Run ./scripts/bootstrap_python312.sh or set PYTHON_BIN." >&2
  exit 1
fi

if [[ -z "$TARGET_DB_URL" ]]; then
  echo "ERROR: TARGET_DB_URL must be set." >&2
  exit 1
fi

if [[ -z "$TARGET_SECRET_KEY" ]]; then
  echo "ERROR: TARGET_SECRET_KEY must be set." >&2
  exit 1
fi

if [[ ${#TARGET_SECRET_KEY} -lt 50 ]]; then
  echo "ERROR: TARGET_SECRET_KEY must be at least 50 characters for production profile checks." >&2
  exit 1
fi

UNIQUE_SECRET_CHARS="$(printf '%s' "$TARGET_SECRET_KEY" | fold -w1 | sort -u | wc -l | tr -d ' ')"
if [[ "$UNIQUE_SECRET_CHARS" -lt 5 ]]; then
  echo "ERROR: TARGET_SECRET_KEY must contain at least 5 unique characters." >&2
  exit 1
fi

export DJANGO_ENV=production
export DJANGO_SECRET_KEY="$TARGET_SECRET_KEY"
export DATABASE_URL="$TARGET_DB_URL"
export ALLOWED_HOSTS="$TARGET_HOST,localhost,.onrender.com"
export CSRF_TRUSTED_ORIGINS="$TARGET_ORIGIN,https://*.onrender.com"
export DEFAULT_FROM_EMAIL='ops@example.com'
export ALLOW_SQLITE_IN_PRODUCTION='false'
export DB_SSL_REQUIRE='true'
export SECURE_SSL_REDIRECT='true'
export SECURE_HSTS_PRELOAD='true'
export ORG_SLUG
export ORG_NAME
export EVIDENCE_DIR

mkdir -p "$EVIDENCE_DIR"

echo "==> Strict target gate preflight"
echo "Root: $ROOT_DIR"
echo "Python: $PYTHON_BIN"
echo "Target host: $TARGET_HOST"
echo "Expected release commit: $RELEASE_COMMIT_SHA"
echo "Org: $ORG_SLUG ($ORG_NAME)"
echo "Evidence dir: $EVIDENCE_DIR"

cd "$ROOT_DIR"

CURRENT_SHA="$(git rev-parse HEAD)"
if [[ "$CURRENT_SHA" != "$RELEASE_COMMIT_SHA" ]]; then
  echo "ERROR: current commit $CURRENT_SHA does not match expected release commit $RELEASE_COMMIT_SHA" >&2
  echo "       Checkout the approved commit before running strict target gate." >&2
  exit 1
fi

"$PYTHON_BIN" manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
"$PYTHON_BIN" manage.py check --deploy --fail-level WARNING
"$PYTHON_BIN" manage.py migrate --noinput
"$PYTHON_BIN" manage.py audit_null_organizations
"$PYTHON_BIN" manage.py test tests.test_cross_tenant_isolation -v 1

echo "==> Running strict target signoff gate"
PYTHON_BIN="$PYTHON_BIN" EVIDENCE_DIR="$EVIDENCE_DIR" ./scripts/run_target_signoff_gate.sh

echo "==> Strict target gate complete"
echo "Summary: $EVIDENCE_DIR/target-signoff-summary.json"
echo "Next steps:"
echo "- Execute docs/MANUAL_SMOKE_CHECKLIST.md"
echo "- Capture backup/restore evidence and append docs/DRILL_LOG.md"
