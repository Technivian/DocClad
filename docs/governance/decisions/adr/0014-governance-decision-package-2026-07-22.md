# ADR-0014 governance decision package

**Package date:** 2026-07-22 (UTC)  
**Status:** **Ratified** — see meeting record  
**ADR:** [`0014-role-definition-reconciliation.md`](0014-role-definition-reconciliation.md) — **Accepted**  
**Programme:** PAR-ID-001 — discovery complete; additive catalogue authorized  
**Meeting record:** [`0014-governance-acceptance-meeting-record-2026-07-22.md`](0014-governance-acceptance-meeting-record-2026-07-22.md)

> **No votes recorded.** This package prepares motions and approver requirements only. Per `docs/governance/decisions/README.md`, do not mark ADR-0014 Accepted without documented approval metadata.

---

## 1. Recommended decision

**Accept ADR-0014** for the five-concept Role Definition reconciliation model (Workspace Role, Permission Set, Workflow Role Definition, Runtime Role Assignment, Delegation), additive mapping registry design, compatibility period rules, and explicit non-goals — **planning and terminology authority only**.

**Do not authorize** schema migrations, backfill, resolver cutover, or privilege changes in the same vote.

---

## 2. Motions (draft — not voted)

### Motion 1 — Accept ADR-0014 (terminology and architecture)

**Text:** Change ADR-0014 status from **Proposed** to **Accepted** for Role Definition reconciliation terminology, five-concept target model, mapping registry design, compatibility period, and documented non-goals.

**Recommended vote:** Approve (pending named approvers)

**Scope limitation:** Acceptance authorizes planning and ID-1 branch preparation only. Does **not** authorize migration 0112+ execution, privilege cutover, or legacy enum removal.

---

### Motion 2 — PAR-ID-001 phase transition

**Text:** Record PAR-ID-001 status as:

> **In progress** — discovery complete; ADR-0014 ratification pending; implementation blocked pending ADR-0014 Acceptance + implementation authorization + PAR-SEC-003 disposition.

**Recommended vote:** Approve (pending named approvers)

---

### Motion 3 — PAR-SEC-003 disposition before cutover

**Text:** Record that **privilege cutover for PAR-ID-001** requires formal PAR-SEC-003 closure or approved disposition, regardless of isolation suite pass count.

**Recommended vote:** Approve (pending named approvers)

---

## 3. Required approvers

| Approver | GitHub identity | Governance capacity | Authority basis |
|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance / repository steward | `.github/CODEOWNERS` (`/docs/`); `GOVERNANCE_CHARTER.md` v2.0 |
| Technivian | @Technivian | Engineering governance / repository steward | `.github/CODEOWNERS` (`/contracts/`, `/docs/`); PDR-0003 |
| Security & privacy (advisory) | @Technivian | Security review capacity | `SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`; Charter §7 |

**Written consent:** Required per approver before Acceptance — repository steward written consent or documented attendance record with UTC timestamp.

---

## 4. Conditions (recommended)

| # | Condition |
|---|---|
| 1 | ADR-0010, ADR-0012, ADR-0013 remain unchanged by this vote |
| 2 | No PAR-APR-002 implementation authorized |
| 3 | PAR-SEC-003 formal disposition required before privilege cutover |
| 4 | `UserProfile.ADMIN` must map to explicit unknown bucket — never Workspace ADMIN |
| 5 | Pilot seeds (`seed_controlled_pilot`) protected in any backfill plan |
| 6 | Implementation authorization vote required before migration 0112+ |

---

## 5. Unresolved risks

| Risk | Severity | Mitigation |
|---|---|---|
| C-ID-01 ADMIN name collision | **High** | Explicit unknown mapping; UI disambiguation |
| C-ID-02 user-global profile role | **High** | Org-scoped `OrganizationUserRole` in cutover plan |
| C-ID-04 SCIM profile gap | **Medium** | Document; separate IdP programme |
| Multi-org user role conflict | **Medium** | Per-org role table; conflict flag on backfill |
| Unused `UserProfile.can_approve` | **Low** | Remove or wire only with authz review |
| Programme isolation proof vs PAR-SEC-003 status | **Medium** | Formal disposition before cutover |

---

## 6. Implementation boundaries

| In scope after Acceptance | Out of scope |
|---|---|
| ADR-0014 binding terminology | Django Group RBAC |
| Mapping registry design | SCIM process role sync |
| Cutover plan maintenance | Client portal roles |
| Characterization tests | Permission widening |
| UX copy audit planning | Single-write cutover |
| ID-1 branch (registry migration only, when authorized) | Legacy enum removal |

---

## 7. Evidence reviewed

| Artifact | Path |
|---|---|
| Role usage matrix | `docs/audits/evidence/2026-07-22-par-id-001/ROLE_USAGE_MATRIX.md` |
| Target role model | `docs/audits/evidence/2026-07-22-par-id-001/TARGET_ROLE_MODEL.md` |
| Cutover plan | `docs/audits/evidence/2026-07-22-par-id-001/CUTOVER_PLAN.md` |
| Characterization tests | `tests/test_par_id_001_characterization.py` (19 tests) |
| Charter | `docs/governance/GOVERNANCE_CHARTER.md` |
| Domain model §2.5 | `docs/product/CANONICAL_DOMAIN_MODEL.md` |
| Security model | `docs/architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md` |

---

## 8. Next review gate

| Gate | Trigger | Owner |
|---|---|---|
| **ADR-0014 ratification vote** | This package circulated | @haroonwahed + @Technivian |
| **Implementation authorization** | ADR-0014 Accepted + PAR-SEC-003 disposed | Programme governance |
| **ID-1 migration branch** | Implementation authorization recorded | Engineering |
| **Privilege cutover** | ID-6 verification gates + pilot sign-off | Product + Engineering + Security |

---

## 9. Comparison to ADR-0013 precedent

ADR-0013 ratification required named approvers (@haroonwahed, @Technivian), authority basis (CODEOWNERS + Charter), vote timestamp, and written consent. ADR-0014 must meet the same bar before Acceptance.

**Current status:** Motions drafted · votes **not recorded** · ADR-0014 remains **Proposed**.
