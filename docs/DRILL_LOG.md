# CMS Aegis Drill Log

## 2026-04-10: Migration Rollback Drill

- Environment: local scratch SQLite databases
- Scope: `contracts` migration rollback and re-apply around `0006_approvalrequest_organization_and_more`

### Clean Scratch DB

Commands:

```bash
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate contracts 0006_approvalrequest_organization_and_more --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py audit_null_organizations
```

Result:

- success
- reverse path from `0006` to `0005` completed
- re-apply to `0006` completed
- no `NULL organization` rows remained

### Populated Copy

Commands:

```bash
cp db.sqlite3 /tmp/cms-aegis-drill.sqlite3
SQLITE_PATH=/tmp/cms-aegis-drill.sqlite3 python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
```

Result:

- failed
- error: `UNIQUE constraint failed: new__contracts_clausecategory.name`

Conclusion:

- populated downgrade is not currently safe after tenant-owned starter content was duplicated per org
- rollback from `0006` to `0005` needs a dedicated downgrade/data-collapse strategy before it should be attempted on real data

## 2026-04-10: Migration Rollback Drill Re-Run (CMS Aegis Activation)

- Environment: local scratch SQLite databases
- Scope: repeatability verification for `contracts` migration rollback and re-apply around `0006_approvalrequest_organization_and_more`

### Clean Scratch DB

Commands:

```bash
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py migrate contracts 0006_approvalrequest_organization_and_more --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean.sqlite3 python manage.py audit_null_organizations
```

Result:

- success
- reverse path from `0006` to `0005` completed
- re-apply to `0006` completed
- no `NULL organization` rows remained

### Populated Copy

Commands:

```bash
cp db.sqlite3 /tmp/cms-aegis-drill.sqlite3
SQLITE_PATH=/tmp/cms-aegis-drill.sqlite3 python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
```

Result:

- failed
- error: `UNIQUE constraint failed: new__contracts_clausecategory.name`

Conclusion:

- rollback from `0006` to `0005` remains unsafe on populated tenant-owned data without a dedicated downgrade migration

## 2026-04-13: Staging PostgreSQL Rehearsal (ICL-002)

- Environment: local staging simulation, PostgreSQL 14 (`localhost:5432`)
- Operator: Codex
- Start time: 2026-04-13T08:59:50
- End time: 2026-04-13T09:00:23
- Database: `cms_aegis_staging_rehearsal`
- Backup file: `/tmp/cms-aegis-backups/pre-cutover-20260413T085950.dump` (`904B`)

### Command Results

- DB engine check: PASS (`django.db.backends.postgresql`)
- `python manage.py check --deploy --fail-level WARNING`: PASS
- `python manage.py migrate --noinput`: PASS
- `python manage.py audit_null_organizations`: PASS
- `python manage.py test tests.test_cross_tenant_isolation -v 1`: PASS
- Restore rehearsal (`dropdb/createdb/pg_restore` + post-restore checks): PASS

### Timings

- Backup duration: `0s`
- Migrate + verify duration: `16s`
- Restore + verify duration: `16s`
- Total drill wall time: `33s`

### Issues Observed

- For local command-line production-profile test execution, `SECURE_SSL_REDIRECT=true` causes expected 301 redirects in Django test client.
- Mitigation used during this rehearsal: keep `SECURE_SSL_REDIRECT=true` for deploy checks, then set `SECURE_SSL_REDIRECT=false` only for the CLI test commands.
- This is a rehearsal-only adjustment for local validation and does not change application code.

### Conclusion

- Rehearsal status: PASS
- Ready for production cutover mechanics: YES (with normal environment-specific secure settings retained in actual staging/prod traffic)

## 2026-04-13: Observability Alert Fire Drill (ICL-008)

- Environment: local development telemetry simulation
- Operator: Codex
- Start time: 2026-04-13T09:31:40
- End time: 2026-04-13T09:31:41

### Scenarios Executed

1. `scheduler_stale`
- Command: `.venv/bin/python manage.py run_observability_fire_drill --scenario scheduler_stale`
- Result: `PASS`
- Triggered alert(s): `OBS-P1-SCHEDULER-STALLED`

2. `error_rate_spike`
- Command: `.venv/bin/python manage.py run_observability_fire_drill --scenario error_rate_spike`
- Result: `PASS`
- Triggered alert(s): `OBS-P1-5XX-RATE`

### Post-Drill Baseline Check

- Command: `.venv/bin/python manage.py evaluate_observability_alerts --json`
- Result: `PASS`
- Alert status returned to: `OK`

### Conclusion

- Fire drill status: PASS
- Alert policy evaluator and scenarios validated for P1 paths.

## 2026-04-13: Governance Game Day + Security SLA Cycle (ICL-012)

- Environment: local governance rehearsal
- Operator: Codex
- Start time: 2026-04-13T09:54:00
- End time: 2026-04-13T10:00:30

### Security SLA Cycle

Commands:

```bash
.venv/bin/pip-audit --disable-pip --no-deps -r requirements/runtime.txt
npm --prefix client audit --audit-level=high --json
npm --prefix theme/static_src audit --audit-level=high --json
.venv/bin/bandit -q -r contracts config -lll
```

Result:

- PASS
- Python high-severity vulnerabilities: 0
- Node high/critical vulnerabilities: 0 (both trees)
- Bandit high-severity findings: 0

### Game Day Alert Path Verification

Commands:

```bash
.venv/bin/python manage.py run_observability_fire_drill --scenario scheduler_stale
.venv/bin/python manage.py run_observability_fire_drill --scenario error_rate_spike
```

Result:

- PASS
- `scheduler_stale` triggered `OBS-P1-SCHEDULER-STALLED`
- `error_rate_spike` triggered `OBS-P1-5XX-RATE`

### Conclusion

- ICL-012 evidence objectives met for:
  - one documented game-day simulation
  - one documented security SLA cycle

## 2026-05-16: Rollback Drill Replay (Live Evidence Pack)

- Environment: local SQLite rehearsal
- Operator: GitHub Copilot
- Scope: re-run rollback drill path and capture current downgrade behavior

### Clean Scratch DB

Commands:

```bash
SQLITE_PATH=/tmp/cms-aegis-drill-clean-20260516.sqlite3 .venv/bin/python manage.py migrate --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean-20260516.sqlite3 .venv/bin/python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean-20260516.sqlite3 .venv/bin/python manage.py migrate contracts 0006_approvalrequest_organization_and_more --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean-20260516.sqlite3 .venv/bin/python manage.py migrate --noinput
SQLITE_PATH=/tmp/cms-aegis-drill-clean-20260516.sqlite3 .venv/bin/python manage.py audit_null_organizations
```

Result:

- PASS after full re-apply
- no `NULL organization` rows remained

### Populated Copy

Commands:

```bash
cp db.sqlite3 /tmp/cms-aegis-drill-populated-20260516.sqlite3
SQLITE_PATH=/tmp/cms-aegis-drill-populated-20260516.sqlite3 .venv/bin/python manage.py migrate contracts 0005_add_org_fk_to_budget_and_due_diligence --noinput
```

Result:

- FAIL
- error: `django.db.utils.IntegrityError: NOT NULL constraint failed: new__contracts_trustaccount.client_id`

Conclusion:

- rollback downgrade on populated data remains unsafe without dedicated downgrade/data-remediation work
- rollback confidence should rely on backup/restore drill execution in target PostgreSQL environment

## 2026-05-16: PostgreSQL Backup/Restore Rehearsal (Rollback Confidence Increment)

- Environment: local PostgreSQL rehearsal (`127.0.0.1:5432`)
- Operator: GitHub Copilot
- Source database: `cms_aegis_cutover_rehearsal`
- Restore database: `cms_aegis_cutover_restore_20260516`

### Commands

```bash
/opt/homebrew/opt/postgresql@16/bin/pg_dump -h 127.0.0.1 -p 5432 -U lessonry -Fc cms_aegis_cutover_rehearsal > /tmp/cms-aegis-backups/pre-cutover-20260516T133345.dump
/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 5432 -U lessonry -d postgres -c "DROP DATABASE IF EXISTS cms_aegis_cutover_restore_20260516;"
/opt/homebrew/opt/postgresql@16/bin/psql -h 127.0.0.1 -p 5432 -U lessonry -d postgres -c "CREATE DATABASE cms_aegis_cutover_restore_20260516 OWNER lessonry;"
/opt/homebrew/opt/postgresql@16/bin/pg_restore -h 127.0.0.1 -p 5432 -U lessonry -d cms_aegis_cutover_restore_20260516 /tmp/cms-aegis-backups/pre-cutover-20260516T133345.dump
DATABASE_URL=postgresql://lessonry:lessonry@127.0.0.1:5432/cms_aegis_cutover_restore_20260516 .venv/bin/python manage.py audit_null_organizations
DATABASE_URL=postgresql://lessonry:lessonry@127.0.0.1:5432/cms_aegis_cutover_restore_20260516 .venv/bin/python manage.py verify_postgres_cutover
DATABASE_URL=postgresql://lessonry:lessonry@127.0.0.1:5432/cms_aegis_cutover_restore_20260516 .venv/bin/python manage.py migrate --check
```

### Timings and Backup Metadata

- Start: `2026-05-16T11:33:45Z`
- End: `2026-05-16T11:33:48Z`
- Total elapsed: `3s`
- Backup file: `/tmp/cms-aegis-backups/pre-cutover-20260516T133345.dump`
- Backup size: `406,937 bytes`

### Verification Results

- `audit_null_organizations`: PASS (`No NULL organization rows found`)
- `verify_postgres_cutover`: PASS (`cutover_ready=true`, engine `django.db.backends.postgresql`, migrations clean)
- `migrate --check`: PASS (no output; no unapplied migrations)

### Outcome

- PostgreSQL backup/restore rollback mechanics are validated in local rehearsal.
- Remaining requirement for final launch signoff: execute the same backup/restore drill in target staging/production-like environment and attach artifacts.
