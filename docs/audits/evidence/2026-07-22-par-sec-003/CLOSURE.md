# PAR-SEC-003 closure evidence

**Programme ID:** PAR-SEC-003  
**Status:** **Closed**  
**Closure date:** 2026-07-22T11:00:00Z  
**Authority:** ADR-0014 governance meeting Motion 3; CODEOWNERS stewards @haroonwahed + @Technivian

---

## 1. Original issue

| Field | Value |
|---|---|
| **Test** | `ContractIsolationTest.test_list_shows_only_own_org` |
| **Module** | `tests/test_cross_tenant_isolation.py` |
| **Previous failure** | `AssertionError: 302 != 200` — test expected HTTP 200 on legacy `contracts:contract_list` |
| **Root cause** | Product intentionally 302-redirects authenticated users from the legacy list alias to `contracts:repository`; the assertion was stale |

This was a **regression-signal defect**, not a tenant data leak. Cross-org detail/update paths already returned 404.

---

## 2. Corrected behavior

| Step | Expected |
|---|---|
| `GET contracts:contract_list` (authenticated) | **302** → `contracts:repository` |
| `GET contracts:repository` | **200** with only own-org contracts |
| Cross-org `contract_detail` / `contract_update` | **404** |

---

## 3. Fix commit

| Field | Value |
|---|---|
| **Commit** | `d9ded244` — `fix(seed): align demo seeds with DOC-001 and PAR-SEC-003 list alias` |
| **Merged via** | PR [#50](https://github.com/Technivian/CLMOne/pull/50) → `main` @ `c52d699a` / PR [#51](https://github.com/Technivian/CLMOne/pull/51) lineage @ `21e65f09` |

---

## 4. Current test results

| Suite | Result | Date |
|---|---|---|
| `ContractIsolationTest.test_list_shows_only_own_org` | **PASS** | 2026-07-22 |
| `tests.test_cross_tenant_isolation` | **75/75 PASS** | 2026-07-22 |

---

## 5. Cross-tenant exposure

| Check | Result |
|---|---|
| Org B list contains Org A contract | **No** |
| Cross-org detail/update | **404** |
| Anonymous alias bypass | Covered by PAR-SEC-001 (Completed) |

**Finding:** No cross-tenant exposure observed on the corrected path.

---

## 6. Assurance limitations (remaining)

| Limitation | Notes |
|---|---|
| Search / analytics / AI uniform authz | Tracked as **PAR-SEC-002** (open) |
| Privilege / resolver cutover | **Not** authorized by this closure |
| Client-hide ≠ authorization | Ongoing ENGINEERING_GUARDRAILS invariant |

---

## 7. Programme-level tenant isolation statement

**For the additive PAR-ID RoleDefinition catalogue slice (`0112`):** programme-level tenant isolation is **proven** — isolation suite green; catalogue rows org-scoped; cross-tenant management denied.

**This does not authorize privilege cutover**, membership-role migration, or resolver flip. Those require separate implementation authorization after ADR-0014 Acceptance conditions are met.
