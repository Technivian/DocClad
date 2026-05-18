# CMS Aegis Live Evidence Execution Pack

Last updated: 2026-05-16

This pack is the single execution path for moving from local synthetic `GO` to target-environment `GO` with live evidence.

## Objective

Produce target-environment evidence for:

1. release gate (`GO`)
2. Salesforce + webhook integrations (`GO`)
3. Postgres cutover readiness (`cutover_ready=true`)
4. e-sign integration report (`GO`)
5. functional smoke checks (manual pass)
6. rollback and restore drill evidence

## Source Anchors

- [docs/RELEASE_CANDIDATE_GATE_CHECKLIST_2026-04-18.md](docs/RELEASE_CANDIDATE_GATE_CHECKLIST_2026-04-18.md)
- [docs/PRODUCTION_CUTOVER_OPERATOR_CHECKLIST.md](docs/PRODUCTION_CUTOVER_OPERATOR_CHECKLIST.md)
- [docs/PRODUCTION_CUTOVER_RUNBOOK.md](docs/PRODUCTION_CUTOVER_RUNBOOK.md)
- [docs/MANUAL_SMOKE_CHECKLIST.md](docs/MANUAL_SMOKE_CHECKLIST.md)
- [docs/ROLLBACK_RUNBOOK.md](docs/ROLLBACK_RUNBOOK.md)
- [docs/RELEASE_GATE_REVIEW_2026-05-16.md](docs/RELEASE_GATE_REVIEW_2026-05-16.md)

## Preconditions

- target environment is production-like and network-enabled
- PostgreSQL target is reachable
- Salesforce and webhook endpoints are configured for target org
- e-sign provider callback secret and endpoint are configured
- operator has deploy, DB, and workflow artifact permissions

## Environment Contract

Set these before running any commands:

```bash
export DJANGO_ENV=production
export DJANGO_SECRET_KEY='<long-random-secret>'
export ALLOWED_HOSTS='staging.example.com'
export CSRF_TRUSTED_ORIGINS='https://staging.example.com'
export DEFAULT_FROM_EMAIL='ops@example.com'
export DATABASE_URL='postgresql://<user>:<password>@<host>:5432/<db>?sslmode=require'
export DB_CONN_MAX_AGE=60
export DB_SSL_REQUIRE=true
export SECURE_SSL_REDIRECT=true
export SECURE_HSTS_PRELOAD=true
```

## Execution Sequence

Run in this exact order from repo root.

If using the helper script:

```bash
./scripts/run_live_evidence_pack.sh
```

Target-environment strict execution (recommended copy/paste form):

```bash
DJANGO_ENV=production \
DJANGO_SECRET_KEY='<long-random-secret>' \
ALLOWED_HOSTS='staging.example.com' \
CSRF_TRUSTED_ORIGINS='https://staging.example.com' \
DEFAULT_FROM_EMAIL='ops@example.com' \
DATABASE_URL='postgresql://<user>:<password>@<host>:5432/<db>?sslmode=require' \
DB_SSL_REQUIRE=true \
SECURE_SSL_REDIRECT=true \
SECURE_HSTS_PRELOAD=true \
CUTOVER_MODE=require \
ORG_SLUG='<org-slug>' \
ORG_NAME='<org-name>' \
./scripts/run_live_evidence_pack.sh
```

By default, the script requires Postgres cutover readiness (`CUTOVER_MODE=require`) and exits non-zero when cutover fails.
For local non-Postgres rehearsal only:

```bash
CUTOVER_MODE=warn ./scripts/run_live_evidence_pack.sh
```

### Step 1: Baseline and migration safety

```bash
python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['ENGINE'])"
python manage.py check --deploy --fail-level WARNING
python manage.py migrate --noinput
python manage.py audit_null_organizations
python manage.py verify_postgres_cutover > evidence/postgres-cutover-evidence.json
```

Pass criteria:

- DB engine is `django.db.backends.postgresql`
- deploy checks are green
- migrations are clean
- no null-organization violations
- cutover evidence indicates readiness

### Step 2: Live Salesforce integration evidence

```bash
python manage.py sync_salesforce_contracts --organization-slug <org-slug>
python manage.py generate_sprint3_integration_report --days 14 --output evidence/sprint3-integration-report.json --fail-on-no-go
```

Pass criteria:

- successful sync with created or updated records
- webhook sent evidence present
- report status is `GO`

### Step 3: Live e-sign evidence

```bash
python manage.py generate_esign_integration_report --organization-slug <org-slug> --days 14 --output evidence/esign-integration-report.json --fail-on-no-go
```

Pass criteria:

- applied e-sign event is present
- terminal signature state is present
- report status is `GO`

### Step 4: Release gate evidence

```bash
python manage.py generate_release_gate_report --output evidence/release-gate-report.json --fail-on-no-go
```

Pass criteria:

- database gate passes
- security gate passes
- integrations gate passes
- overall `go_no_go` is `GO`

### Step 5: Manual smoke evidence

Execute [docs/MANUAL_SMOKE_CHECKLIST.md](docs/MANUAL_SMOKE_CHECKLIST.md) and store notes in:

- `evidence/manual-smoke-signoff.md`

Minimum pass set:

- auth redirect behavior
- two-org isolation checks
- contract/workflow deny-path checks
- admin/team role boundaries
- search isolation

### Step 6: Rollback/restore drill evidence

Follow [docs/ROLLBACK_RUNBOOK.md](docs/ROLLBACK_RUNBOOK.md) and append drill evidence to:

- [docs/DRILL_LOG.md](docs/DRILL_LOG.md)

Required fields:

- start and finish timestamps
- backup command and restore command
- migration and restore duration
- verification outputs
- outcome and operator signoff

## Artifact Manifest

Store all outputs under `evidence/` and attach these to PR/release notes:

1. `evidence/release-gate-report.json`
2. `evidence/sprint3-integration-report.json`
3. `evidence/esign-integration-report.json`
4. `evidence/postgres-cutover-evidence.json`
5. `evidence/executive-analytics-evidence.json`
6. `evidence/retention-audit-actions.json`
7. `evidence/release-bundle/release-evidence-bundle.json`
8. `evidence/manual-smoke-signoff.md`
9. drill entry link in [docs/DRILL_LOG.md](docs/DRILL_LOG.md)

## Stop Conditions

Stop immediately if any of these occur:

- release gate is `NO-GO`
- migration or cutover check fails
- integration reports are `NO-GO`
- smoke finds cross-tenant leakage
- rollback rehearsal fails

## Operator Readout Template

Use this in PR/release notes:

```text
Live Evidence Readout
- Environment: <env>
- Commit: <sha>
- Release Gate: GO/NO-GO
- Sprint3 Integration: GO/NO-GO
- E-sign Integration: GO/NO-GO
- Postgres Cutover Ready: true/false
- Executive Analytics Evidence: GENERATED/MISSING
- Retention Audit Evidence: GENERATED/MISSING
- Manual Smoke: PASS/FAIL
- Rollback Drill: PASS/FAIL
- Artifacts: <links>
- Decision: GO/NO-GO
```

## Current Known Status

- local synthetic release gate is `GO`
- local synthetic release evidence bundle is `GO`
- local strict Postgres rehearsal using `run_live_evidence_pack.sh` is `GO` with expanded artifacts
- remaining gap is live target-environment proof