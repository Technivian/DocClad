# Live Evidence Readout

Date: 2026-05-16
Environment: local workspace
Decision: GO for PostgreSQL cutover rehearsal and evidence bundle; NO-GO for final production signoff until manual smoke and target rollback drill are complete

## Commands Executed

- `./.venv/bin/python manage.py seed_sprint3_evidence --organization-slug demo-firm --organization-name 'Demo Firm'`
- `./.venv/bin/python manage.py verify_postgres_cutover > evidence/postgres-cutover-evidence.json`
- `./.venv/bin/python manage.py generate_sprint3_integration_report --days 14 --output evidence/sprint3-integration-report.json --fail-on-no-go`
- `./.venv/bin/python manage.py generate_esign_integration_report --organization-slug demo-firm --days 14 --output evidence/esign-integration-report.json --fail-on-no-go`
- `./.venv/bin/python manage.py generate_release_gate_report --output evidence/release-gate-report.json --fail-on-no-go`
- `./.venv/bin/python manage.py generate_release_evidence_bundle --fail-on-no-go --output-dir evidence/release-bundle`
- `DATABASE_URL=postgresql://lessonry:lessonry@127.0.0.1:5432/cms_aegis_cutover_rehearsal DJANGO_ENV=production ... ./scripts/run_live_evidence_pack.sh` (strict mode)

## Results

- Sprint 3 integration report: GO
- E-sign integration report: GO
- Release gate report: GO
- Executive analytics evidence: generated
- Retention audit actions export: generated
- Release evidence bundle: GO
- Postgres cutover evidence: READY (`cutover_ready=true`, PostgreSQL engine)
- Automated smoke-equivalent isolation tests: PASS (`tests.test_cross_tenant_isolation`, 55 tests)
- Rollback drill replay:
	- clean scratch DB: PASS
	- populated copy downgrade: FAIL (data/migration integrity constraint)
	- PostgreSQL backup/restore rehearsal: PASS (local; target-env replay pending)

## Remaining Blockers

Primary blocker for final production signoff:

- Full manual/browser smoke checklist is still pending in the target environment.

Secondary blocker for rollback confidence on populated SQLite copy:

- downgrade to `contracts 0005` failed with `django.db.utils.IntegrityError: NOT NULL constraint failed: new__contracts_trustaccount.client_id`

Risk reduction completed:

- PostgreSQL backup/restore rehearsal succeeded locally with clean post-restore cutover/audit checks.
- Remaining rollback gate for launch: execute the same backup/restore drill in target environment and attach artifacts.

## Artifacts Produced

- [evidence/sprint3-integration-report.json](sprint3-integration-report.json)
- [evidence/esign-integration-report.json](esign-integration-report.json)
- [evidence/release-gate-report.json](release-gate-report.json)
- [evidence/postgres-cutover-evidence.json](postgres-cutover-evidence.json)
- [evidence/executive-analytics-evidence.json](executive-analytics-evidence.json)
- [evidence/retention-audit-actions.json](retention-audit-actions.json)
- [evidence/release-bundle/release-evidence-bundle.json](release-bundle/release-evidence-bundle.json)
- [evidence/manual-smoke-signoff.md](manual-smoke-signoff.md)
- rollback drill evidence in [docs/DRILL_LOG.md](../docs/DRILL_LOG.md)

## Next Required Actions (Target Environment)

1. Run this same sequence in a PostgreSQL-backed staging/production-like environment.
2. Re-run manual smoke using [docs/MANUAL_SMOKE_CHECKLIST.md](../docs/MANUAL_SMOKE_CHECKLIST.md).
3. Append rollback/restore drill evidence to [docs/DRILL_LOG.md](../docs/DRILL_LOG.md).
