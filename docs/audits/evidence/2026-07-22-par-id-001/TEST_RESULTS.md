# PAR-ID-001 — test results

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-id-001-resolver-parity`  
**PR #55 merge:** `bb881ac2`  
**Resolver parity:** Authorized + implementing on PR #58

## Resolver parity gate

| Suite | Result |
|---|---|
| `tests.test_par_id_001_resolver_parity` | **15 PASS** |
| `tests.test_par_id_001_shadow_sync` | **10 PASS** |
| `tests.test_par_id_001_role_definition` | **PASS** |
| `tests.test_par_id_001_process_role_assignment` | **PASS** |
| `tests.test_par_id_001_characterization` | **19 PASS** |
| `tests.test_approval_authorization` + `tests.test_approval_workflow` + `tests.test_par_apr_001_approval` | **33 PASS** |
| `tests.test_par_wf_010_characterization` | **4 PASS** |
| `tests.test_cross_tenant_isolation` | **75 PASS** |
| Combined gate | **190 PASS** |
| `make check` / governance authority | **PASS** |

## Flags (default off)

- `PROCESS_ROLE_SHADOW_WRITE_ENABLED`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED`
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED`

Legacy resolvers remain authoritative. Dual-return / privilege cutover **not** authorized.
