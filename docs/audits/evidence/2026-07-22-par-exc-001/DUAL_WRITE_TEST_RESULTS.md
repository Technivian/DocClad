# PAR-EXC-001 dual-write test results

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-exc-001-priority-dual-write-d7f1`

| Suite | Result |
|---|---|
| `tests.test_par_exc_001_exception` | **11 OK** |
| `tests.test_par_exc_001_dual_write` | **16 OK** |
| `manage.py check` | **0 issues** |

## Migration proof

| Step | Result |
|---|---|
| Forward `0114` + `0115` | OK |
| Rollback to `0113` | OK |
| Re-forward to `0115` | OK |

## Coverage highlights

- Six source classifications mirrored
- Idempotent correlation_id
- Cross-tenant fail-closed
- Critical without Security fail-closed; with Security approval OK
- AI exception = request only (no invented APPROVED)
- Expiry + renewal
- Immutable decisions
- Ordinary dual-write failure audited; legacy preserved via safe wrapper
- Deadline defer dual-write when allowlisted; legacy-only when flag off
- ConflictCheck WAIVED dual-write
