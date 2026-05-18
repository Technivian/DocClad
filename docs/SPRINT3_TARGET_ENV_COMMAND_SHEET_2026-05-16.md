# Sprint 3 Target Environment Command Sheet

Date: 2026-05-16
Use this sheet during staging or production-like execution. Replace placeholders before running.

## 0) Fill These Variables First

```bash
export TARGET_HOST='staging.example.com'
export TARGET_ORIGIN="https://${TARGET_HOST}"
export TARGET_DB_URL='postgresql://<user>:<password>@<host>:5432/<db>?sslmode=require'
export TARGET_ORG_SLUG='demo-firm'
export TARGET_ORG_NAME='Demo Firm'
export TARGET_SECRET_KEY='<long-random-secret>'
```

Known defaults from current Sprint 3 rehearsal evidence:

- `TARGET_HOST=staging.example.com`
- `TARGET_ORG_SLUG=demo-firm`
- `TARGET_ORG_NAME=Demo Firm`

## 1) Production-Shape Environment

```bash
export DJANGO_ENV=production
export DJANGO_SECRET_KEY="$TARGET_SECRET_KEY"
export ALLOWED_HOSTS="$TARGET_HOST"
export CSRF_TRUSTED_ORIGINS="$TARGET_ORIGIN"
export DEFAULT_FROM_EMAIL='ops@example.com'
export DATABASE_URL="$TARGET_DB_URL"
export DB_CONN_MAX_AGE=60
export DB_SSL_REQUIRE=true
export SECURE_SSL_REDIRECT=true
export SECURE_HSTS_PRELOAD=true
export CUTOVER_MODE=require
export ORG_SLUG="$TARGET_ORG_SLUG"
export ORG_NAME="$TARGET_ORG_NAME"
```

## 2) Preflight

```bash
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py audit_null_organizations
python manage.py test tests.test_cross_tenant_isolation -v 1
```

Expected:
- database engine is django.db.backends.postgresql
- deploy checks pass
- migrations are clean
- no null organization rows
- isolation tests pass

## 3) Strict Sprint 3 Evidence Pack

```bash
./scripts/run_live_evidence_pack.sh
```

This generates the required evidence artifacts under evidence/.

## 4) Validate Gate Outputs Quickly

```bash
python manage.py verify_postgres_cutover > evidence/postgres-cutover-evidence.json
python manage.py generate_sprint3_integration_report --days 14 --output evidence/sprint3-integration-report.json --fail-on-no-go
python manage.py generate_esign_integration_report --organization-slug "$ORG_SLUG" --days 14 --output evidence/esign-integration-report.json --fail-on-no-go
python manage.py generate_release_gate_report --output evidence/release-gate-report.json --fail-on-no-go
```

## 5) Manual Smoke and Rollback Proof

```bash
# Execute manual checklist and record signoff
# docs/MANUAL_SMOKE_CHECKLIST.md -> evidence/manual-smoke-signoff.md

# Run rollback/restore rehearsal per runbook and append drill log
# docs/ROLLBACK_RUNBOOK.md -> docs/DRILL_LOG.md
```

## 6) Artifact Checklist

Confirm all files exist:

```bash
ls -lh \
  evidence/postgres-cutover-evidence.json \
  evidence/sprint3-integration-report.json \
  evidence/esign-integration-report.json \
  evidence/release-gate-report.json \
  evidence/executive-analytics-evidence.json \
  evidence/retention-audit-actions.json \
  evidence/release-bundle/release-evidence-bundle.json \
  evidence/manual-smoke-signoff.md
```

## 7) Stop Conditions

Stop and mark NO-GO if any of these occurs:
- release gate is NO-GO
- cutover check is not ready
- sprint3 or e-sign report is NO-GO
- smoke reveals cross-tenant leakage
- rollback rehearsal fails

## 8) Write Final Readout

Use the template in docs/LIVE_EVIDENCE_EXECUTION_PACK_2026-05-16.md and attach all artifacts in release notes.

## 9) Optional Render Preview Variant

Use this only when executing on a Render preview host.

```bash
export TARGET_HOST='cms-aegis-preview.onrender.com'
export TARGET_ORIGIN="https://${TARGET_HOST}"
```
