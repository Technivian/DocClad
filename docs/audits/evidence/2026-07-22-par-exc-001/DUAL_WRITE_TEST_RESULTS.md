# PAR-EXC-001 dual-write test results

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-exc-001-priority-dual-write-d7f1` (rebased onto `main` @ `982b0900`)  
**Flags:** `EXCEPTION_DUAL_WRITE_ENABLED=false`; allowlist empty (default off)

| Suite | Result |
|---|---|
| `tests.test_par_exc_001_exception` | **11 OK** |
| `tests.test_par_exc_001_dual_write` | **16 OK** |
| `tests.test_approval_authorization` | **8 OK** |
| `tests.test_cross_tenant_isolation` | **75 OK** |
| `tests.test_cross_tenant_mutation_guardrails` | **2 OK** |
| `tests.test_ai_contract_review` | **5 OK** |
| `tests.test_dpa_workflow` | 60 OK / **2 FAIL** (pre-existing on `main` @ `982b0900`: Draft label + Governance copy — **not** dual-write regressions) |
| `manage.py check` | **0 issues** |
| `scripts/check_governance_authority.sh` | **OK** |

## Migration proof

| Step | Result |
|---|---|
| Forward `0114` + `0115` | OK |
| Rollback to `0113` | OK |
| Re-forward to `0115` | OK |
| `correlation_id` present after re-forward | True |

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

## Activation

Controlled-pilot package: [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) — **votes Requested**; flags **not** enabled.
