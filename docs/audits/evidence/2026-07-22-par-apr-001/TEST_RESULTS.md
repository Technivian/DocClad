# PAR-APR-001 — test results

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-apr-001-foundation-governance` @ `b97a1792`  
**Settings:** `config.settings_test` (in-memory SQLite)

---

## Targeted PAR-APR suites

| Module | Result |
|---|---|
| `tests.test_par_apr_001_approval` | **10 PASS** |
| `tests.test_approval_workflow` | **15 PASS** |
| `tests.test_approval_authorization` | **8 PASS** |
| **Subtotal** | **33 PASS** |

---

## Migration proof

| Operation | Migration | Result |
|---|---|---|
| Forward | `0111_approval_requirement_decision` | **PASS** |
| Rollback to `0110` | `0111` → `0110` | **PASS** |
| Re-forward | `0110` → `0111` | **PASS** |

Evidence: `migrate-rollback.txt`, `migrate-reforward.txt`

---

## Known programme failures (orthogonal — not PAR-APR blockers)

| Test | Issue | Programme item |
|---|---|---|
| `test_workflow_dashboard_and_detail_surface_routing_endpoints` | Routing surface drift | Milestone 1 hygiene |
| `test_list_shows_only_own_org` | Stale list-alias assertion (302 redirect) | **PAR-SEC-003** |

---

## Tenant isolation statement

PAR-APR foundation tests prove org-scoped requirement/decision isolation within targeted suites. Programme-level tenant isolation remains **unproven** until PAR-SEC-003 closes.
