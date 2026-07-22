# PAR-ID-001 — test results

**Date:** 2026-07-22  
**Branch:** `main` @ `bb881ac2` (PR #55 merge)  
**PR #54 merge:** `58966de7`  
**PR #55 merge:** `bb881ac2` (reviewed HEAD `432a55b1`)

## Slice 3 gate (shadow sync)

| Suite | Result |
|---|---|
| `tests.test_par_id_001_shadow_sync` | **10 PASS** |
| `tests.test_par_id_001_role_definition` | **PASS** |
| `tests.test_par_id_001_process_role_assignment` | **PASS** |
| Post-merge on `main` (`shadow_sync` + role_definition + process_role_assignment) | **44 PASS** (2026-07-22T13:58:25Z) |
| `scripts/check_governance_authority.sh` | **PASS** |
| `python manage.py check` | **PASS** |
| `tests.test_par_id_001_characterization` | **19 PASS** (pre-merge evidence) |
| `tests.test_approval_authorization` + `tests.test_approval_workflow` + `tests.test_par_apr_001_approval` | **33 PASS** (pre-merge evidence) |
| `tests.test_par_wf_010_characterization` | **4 PASS** (pre-merge evidence) |
| `tests.test_cross_tenant_isolation` | **75 PASS** (pre-merge evidence) |
| Combined gate (incl. self-approval in extended run) | **177 PASS** (pre-merge evidence) |

## Prior slices

| Slice | Migration | Result |
|---|---|---|
| Catalogue | 0112 forward / rollback / re-forward | PASS |
| Process-role adapter | 0113 forward / rollback / re-forward | PASS |

Production authority remains legacy resolvers. Privilege / resolver cutover **not** authorized.
No new migration in Slice 3 (0113 schema sufficient).
