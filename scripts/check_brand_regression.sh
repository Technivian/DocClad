#!/usr/bin/env bash
# check_brand_regression.sh — Fail if forbidden CMS Aegis branding is reintroduced.
# Run in CI to prevent regressions after the CLM One rename.
#
# ALLOWLISTED FILES (intentional technical remnants — must not be broadened without
# documenting a new reason):
#
#   contracts/api/integrations.py
#     Accepts legacy 'cms-aegis-{org}-{id}' Documenso external IDs for in-flight signatures
#     created before the rename. Remove check once all pre-rename signature records reach
#     a terminal state in Documenso.
#
#   contracts/context_processors.py
#     CMS_AEGIS_MODE context key is a deprecated template alias for CLMONE_MODE.
#     Remove after all templates are migrated to use CLMONE_MODE.
#
#   config/settings_base.py
#     CMS_AEGIS_MODE settings alias + session cookie comment referencing old name.
#     Remove alongside context_processors.py alias.
#
#   config/settings_production.py
#     Guard still accepts noreply@cms-aegis.local as a sentinel for unconfigured email.
#     Remove after settings_base.py default is confirmed updated in all environments.
#
#   config/feature_flags.py
#     is_cms_aegis_mode_enabled() deprecated alias. Remove after all callers migrate
#     to is_clmone_mode_enabled().
#
#   tests/test_salesforce_sprint2_ingestion.py
#     Mocks PostgreSQL db name 'cms_aegis' as returned by pg_catalog in the
#     verify_postgres_cutover management command test. This is an infrastructure
#     mock, not product branding. Remove after CI db is renamed to 'clmone'.
#
#   theme/templates/base.html, theme/templates/base_fullscreen.html
#     localStorage fallback reads 'cms-aegis-theme' for existing users' saved preference
#     before migrating to 'clmone-theme'. Remove once the transition period ends.
#
#   theme/static/js/csp-handlers.js
#     Removes 'cms-aegis-theme' localStorage key during theme migration. Remove this
#     localStorage.removeItem call once all active sessions have migrated.
#
#   tests/test_5f_role_walkthrough.py
#     assertNotIn('CMS Aegis', body) — a regression test proving the old brand
#     name never renders. The forbidden string exists only inside this negative
#     assertion, never as leaked output. Remove the allowlist entry only if the
#     assertion itself is removed.

set -euo pipefail

LEGACY_APP_PATTERN='[Dd]oc[Cc]''lad|DOCC''LAD'
LEGACY_MODULAR_PATTERN='[Mm]odu[Cc]''lad|MODUC''LAD'
FORBIDDEN_PATTERN="CMS Aegis|CMSAegis|CMS_AEGIS|cms-aegis|cmsaegis|${LEGACY_APP_PATTERN}|${LEGACY_MODULAR_PATTERN}"

# Files with permitted technical remnants (exact paths from repo root)
ALLOWLIST_FILES=(
  'contracts/api/integrations.py'
  'contracts/context_processors.py'
  'config/settings_base.py'
  'config/settings_production.py'
  'config/feature_flags.py'
  'tests/test_salesforce_sprint2_ingestion.py'
  'tests/test_5f_role_walkthrough.py'
  'theme/templates/base.html'
  'theme/templates/base_fullscreen.html'
  'theme/static/js/csp-handlers.js'
  'staticfiles/js/csp-handlers.js'
  'scripts/check_brand_regression.sh'
)

# Directories to skip entirely
EXCLUDE_DIRS=(
  'docs'
  'evidence'
  'backups'
  '.git'
  '__pycache__'
  '.venv'
  '.venv.py315.bak'
  'node_modules'
  '.pytest_cache'
  '.mypy_cache'
  'staticfiles'
)

# Individual files to skip (historical / planning docs, and this script itself)
EXCLUDE_FILES=(
  'README_CMS_AEGIS.md'
  'README_LEGACY.md'
  'brand-guardrail.yml'
  'BATCH3_POST_MIGRATION_AUDIT.md'
  'BATCH3_WORKSPACE_MIGRATION_PLAN.md'
  'DESIGN_ARCHETYPE_PATTERNS.md'
  'DESIGN_CONSTITUTION.md'
  'DESIGN_SYSTEM_AUDIT.md'
  'DESIGN_UNIFICATION_ROADMAP.md'
  'FEATURE_INVENTORY.md'
  'FIGMA_REDESIGN_PREP.md'
  'PILOT_LAUNCH_CHECKLIST.md'
  'PROJECT_STATUS.md'
  'QA_CHECKLIST.md'
  'TECH_DEBT.md'
  'DECISIONS.md'
  # Canonical governance charter — deliberately retains legacy-brand references
  # only in its migration/supersession/traceability notes (see the file header).
  'GOVERNANCE_CHARTER.md'
  # Internal readiness/audit reports — legacy-brand strings appear as tracked
  # audit findings (issues to remediate) and negative "not found" assertions,
  # not as product surface copy.
  'PRE_DEMO_READINESS_REPORT.md'
  'PAYROLLMINDS_CLM_READINESS_AUDIT.md'
)

# Build grep exclude args
EXCLUDE_ARGS=()
for d in "${EXCLUDE_DIRS[@]}"; do
  EXCLUDE_ARGS+=(--exclude-dir="$d")
done
for f in "${EXCLUDE_FILES[@]}"; do
  EXCLUDE_ARGS+=(--exclude="$(basename "$f")")
done

echo "=== CLM One brand regression check ==="

FINDINGS=0
while IFS=: read -r file _rest; do
  # Strip leading ./ for comparison
  clean_file="${file#./}"

  # Skip binary files
  if echo "$file" | grep -q "^Binary file"; then
    continue
  fi

  # Check allowlist
  allowed=false
  for af in "${ALLOWLIST_FILES[@]}"; do
    if [[ "$clean_file" == "$af" ]]; then
      allowed=true
      break
    fi
  done
  $allowed && continue

  echo "FAIL: $file:$_rest"
  FINDINGS=$((FINDINGS + 1))
done < <(grep -rniE --binary-files=without-match "$FORBIDDEN_PATTERN" "${EXCLUDE_ARGS[@]}" . 2>/dev/null | grep -v '\.pyc:' || true)

if [[ $FINDINGS -gt 0 ]]; then
  echo ""
  echo "ERROR: $FINDINGS forbidden branding reference(s) found. Update to CLM One."
  exit 1
fi

echo "OK: No forbidden branding references found (${#ALLOWLIST_FILES[@]} allowlisted files skipped)."
exit 0
