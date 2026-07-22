# PAR-ID-001 — test results

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-id-001-resolver-parity` @ (see git HEAD)  
**PR #55 merge:** `bb881ac2`  
**Resolver parity:** Authorized + implemented on PR #58 (flag default off; merge blocked)

## Resolver parity gate (local)

| Suite | Result |
|---|---|
| `tests.test_par_id_001_resolver_parity` | **18 PASS** |
| `tests.test_par_id_001_shadow_sync` | **10 PASS** (prior run) |
| `tests.test_par_id_001_role_definition` | **PASS** (prior run) |
| `tests.test_par_id_001_process_role_assignment` | **PASS** (prior run) |
| `tests.test_par_id_001_characterization` | **PASS** |
| `tests.test_approval_authorization` + `tests.test_approval_workflow` + `tests.test_par_apr_001_approval` | **PASS** |
| `tests.test_par_wf_010_characterization` | **PASS** |
| `tests.test_cross_tenant_isolation` | **PASS** |
| Combined gate (this run) | **149 PASS** (`django-tests-resolver-parity-gate.txt`) |

## Flags (default off)

- `PROCESS_ROLE_SHADOW_WRITE_ENABLED`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED`
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED`

Legacy resolvers remain authoritative. Dual-return / privilege cutover / staging flag activation / merge **not** authorized by Slice 4 implementation authorization alone.
