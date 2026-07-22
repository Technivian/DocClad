# PAR-ID-001 — test results (additive catalogue slice)

**Date:** 2026-07-22  
**Branch:** `cursor/feat-par-id-001-role-definition-registry-d7f1`  
**Settings:** `config.settings_test`

---

## Suites

| Module | Result |
|---|---|
| `tests.test_par_id_001_role_definition` | **17 PASS** |
| `tests.test_par_id_001_characterization` | **19 PASS** |
| `tests.test_par_apr_001_approval` + approval workflow/authorization | **33 PASS** |
| `tests.test_par_wf_010_characterization` | **4 PASS** |
| `tests.test_cross_tenant_isolation` | **75 PASS** |
| **Combined gate run** | **148 PASS** |

---

## Migration proof

| Operation | Result |
|---|---|
| Forward `0112` | **PASS** |
| Rollback → `0111` | **PASS** |
| Re-forward → `0112` | **PASS** |

---

## Tenant isolation conclusion

Programme isolation suite **75/75 PASS**. PAR-SEC-003 **Closed**. Programme-level tenant isolation is **proven for the additive RoleDefinition catalogue slice**. Privilege / resolver cutover remains **not authorized**.
