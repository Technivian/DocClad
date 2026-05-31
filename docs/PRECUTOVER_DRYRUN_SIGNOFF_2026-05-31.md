# Pre-Cutover Dry Run Signoff

Date: 2026-05-31
Type: Local rehearsal (non-production)
Scope: Execute scripted live evidence pack and verify artifact completeness for cutover readiness workflow.

## Execution

Command run:

```bash
EVIDENCE_DIR="$PWD/evidence/precutover-dryrun-2026-05-31" \
PYTHON_BIN="$PWD/.venv/bin/python" \
ORG_SLUG="demo-firm" \
ORG_NAME="Demo Firm" \
CUTOVER_MODE=warn \
./scripts/run_live_evidence_pack.sh
```

Prerequisite command run before execution:

```bash
.venv/bin/python manage.py migrate --noinput
```

## Outcome

- Dry run status: PASS (local rehearsal mode)
- Release gate result: GO
- Release evidence bundle result: GO
- Sprint 3 integration report: GO
- E-sign integration report: GO

Additional tenant-scoped positive-path run (GitHub Actions):

- Workflow: `sprint3-go-live-evidence`
- Run: `26708926283`
- URL: https://github.com/Technivian/CMS-Aegis/actions/runs/26708926283
- Organization slug: `demo-firm`
- Result: PASS
- Retention outcome: `contracts_archived=1`, `policies_scanned=1`, `audit_entries_created=1`
- Lifecycle outcome: `contracts_promoted_to_renewal=1`, `contracts_evaluated=2`, `audit_entries_created=1`

Important caveat:
- `verify_postgres_cutover` returned non-zero in local SQLite context and was allowed because `CUTOVER_MODE=warn`.
- This is expected for local non-Postgres rehearsal and is not a production signoff.

## Evidence Artifacts

Primary artifact directory:
- evidence/precutover-dryrun-2026-05-31

Artifacts generated:
- evidence/precutover-dryrun-2026-05-31/postgres-cutover-evidence.json
- evidence/precutover-dryrun-2026-05-31/sprint3-integration-report.json
- evidence/precutover-dryrun-2026-05-31/esign-integration-report.json
- evidence/precutover-dryrun-2026-05-31/release-gate-report.json
- evidence/precutover-dryrun-2026-05-31/executive-analytics-evidence.json
- evidence/precutover-dryrun-2026-05-31/retention-audit-actions.json
- evidence/precutover-dryrun-2026-05-31/release-bundle/release-evidence-bundle.json

Positive-path artifact (workflow download):
- sprint3-go-live-evidence-tenant-positive-2026-05-31
- includes: `retention-jobs-run.json`, `contract-lifecycle-jobs-run.json`, `retention-audit-actions.json`, `metadata.txt`

## Decision

- Local pre-cutover rehearsal: ACCEPTED
- Tenant-scoped positive-path evidence run: ACCEPTED
- Production cutover: NOT YET EXECUTED

## Required Production-Window Steps Remaining

1. Run the same sequence in target production-like/prod environment with PostgreSQL and `CUTOVER_MODE=require`.
2. Execute live smoke checklist and capture operator signoff.
3. Attach live backup artifact details and final post-traffic gate results.

Execution docs:
- docs/PRODUCTION_CUTOVER_COMMAND_SHEET_2026-05-31.md
- docs/PRODUCTION_CUTOVER_RUN_LOG_TEMPLATE_2026-05-31.md
- docs/PRODUCTION_CUTOVER_OPERATOR_CHECKLIST.md