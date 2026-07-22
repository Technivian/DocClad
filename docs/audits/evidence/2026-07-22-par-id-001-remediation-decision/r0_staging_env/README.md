# R0 staging-equivalent environment (ephemeral)

Disposable SQLite DB used for authorized R0 inventory. **Do not commit `db.sqlite3`.**

Recreate:

```bash
export DJANGO_SETTINGS_MODULE=config.settings_development
export DATABASE_URL="sqlite:///$(pwd)/docs/audits/evidence/2026-07-22-par-id-001-remediation-decision/r0_staging_env/db.sqlite3"
export PROCESS_ROLE_SHADOW_WRITE_ENABLED=false
export PROCESS_ROLE_PARITY_REPORTING_ENABLED=false
export PROCESS_ROLE_RESOLVER_PARITY_ENABLED=false
export PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED=false
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py seed_data
.venv/bin/python manage.py seed_demo
.venv/bin/python manage.py seed_mvp_demo
.venv/bin/python manage.py seed_controlled_pilot
.venv/bin/python manage.py seed_payrollminds_demo
```

Evidence outputs: `../R0_EXIT_REPORT.md`, `../r0_inventory_raw.json`.
