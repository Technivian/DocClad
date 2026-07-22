# Controlled-pilot dual-write activation environment

Named non-production environment for PAR-EXC-001 Motion 3 operational enablement.

**Do not commit `db.sqlite3`.**

Authorized operational flags (committed defaults remain off):

```bash
export EXCEPTION_DUAL_WRITE_ENABLED=true
export EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=controlled-pilot-org
```

Immediate rollback: set `EXCEPTION_DUAL_WRITE_ENABLED=false` and clear `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST`.
