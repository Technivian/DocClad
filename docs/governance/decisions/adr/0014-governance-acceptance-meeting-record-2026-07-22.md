# ADR-0014 governance acceptance — meeting record

**Meeting type:** Programme governance review (decision record)  
**Date:** 2026-07-22 (UTC)  
**Vote timestamp:** 2026-07-22T11:00:00Z  
**Chair:** @haroonwahed (repository steward — Product governance)  
**Quorum:** Product governance · Engineering governance · Security & privacy review (advisory)  
**Package under review:**

- [`0014-role-definition-reconciliation.md`](0014-role-definition-reconciliation.md)
- [`0014-governance-decision-package-2026-07-22.md`](0014-governance-decision-package-2026-07-22.md)
- [`../../../audits/evidence/2026-07-22-par-id-001/`](../../../audits/evidence/2026-07-22-par-id-001/)
- [`../../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md`](../../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md)

**Prerequisite:** PR [#51](https://github.com/Technivian/CLMOne/pull/51) merged to `main` @ `21e65f09`

---

## 1. Motions and votes

### Motion 1 — Accept ADR-0014

**Motion:** Change ADR-0014 status from **Proposed** to **Accepted** for Role Definition reconciliation terminology, five-concept target model, mapping registry design, compatibility period, and documented non-goals.

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance / repository steward | `.github/CODEOWNERS` (`/docs/`); `GOVERNANCE_CHARTER.md` v2.0 | **Approve** | Written consent recorded |
| Technivian | @Technivian | Engineering governance / repository steward | `.github/CODEOWNERS` (`/contracts/`, `/docs/`); PDR-0003 | **Approve** | Written consent recorded |
| Security & privacy (advisory) | @Technivian | Security review capacity | `SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`; Charter §7 | **Approve with conditions** | Conditions in §5 |

**Result:** **Ratified**

**Acceptance scope limitation:** Authorizes target model and planning only. Does **not** authorize permission changes, resolver cutover, membership-role migration, privilege changes, `UserProfile.role` removal, or workflow assignment cutover.

---

### Motion 2 — PAR-ID-001 remains In progress

**Motion:** Record PAR-ID-001 as **In progress** after ADR-0014 Acceptance — discovery complete; additive catalogue may proceed under separate implementation authorization; Completion deferred until runtime assignment and compatibility cutover criteria are delivered.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried**

---

### Motion 3 — PAR-SEC-003 closure

**Motion:** Close PAR-SEC-003 based on corrected `ContractIsolationTest.test_list_shows_only_own_org` and full isolation suite 75/75 PASS. State that programme-level tenant isolation is proven for the **additive RoleDefinition catalogue slice**, and that this does **not** authorize privilege cutover.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried**

---

### Motion 4 — Authorize migration 0112 (narrow)

**Motion:** Authorize implementation of `0112_role_definition_registry` under the explicit scope in `docs/audits/evidence/2026-07-22-par-id-001/0112-implementation-authorization.md`.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried** — additive catalogue only.

---

## 5. Conditions

1. ADR-0010, ADR-0012, ADR-0013 remain unchanged.
2. No PAR-APR-002 implementation.
3. `UserProfile.ADMIN` must map to `legacy_process_admin` (LEGACY_UNKNOWN) — never Workspace ADMIN.
4. No permission, resolver, membership, or assignment behaviour changes in the 0112 slice.
5. Privilege / resolver cutover requires a future separate authorization.

---

## 7. Approvers and effective date

| Field | Value |
|---|---|
| **Approved by** | @haroonwahed (Product) · @Technivian (Engineering) |
| **Vote timestamp** | **2026-07-22T11:00:00Z** |
| **Effective date** | **2026-07-22** |
| **ADR-0014 status after vote** | **Accepted** |

---

## 8. Next review gate

| Gate | Trigger |
|---|---|
| **0112 merge** | Tests + migration proof green |
| **Next PAR-ID slice** | Separate implementation authorization (org-scoped profile role / resolver dual-read) |
| **Privilege cutover** | Explicit future authorization — not this meeting |
