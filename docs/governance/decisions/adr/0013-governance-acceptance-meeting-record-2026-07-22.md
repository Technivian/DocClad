# ADR-0013 governance acceptance — meeting record

**Meeting type:** Programme governance review (decision record)  
**Date:** 2026-07-22 (UTC)  
**Vote timestamp:** 2026-07-22T09:45:00Z  
**Chair:** @haroonwahed (repository steward — Product governance)  
**Quorum:** Product governance · Engineering governance · Security & privacy review (advisory)  
**Package under review:**

- [`0013-approval-requirement-decision-split.md`](0013-approval-requirement-decision-split.md)
- [`../../../audits/evidence/2026-07-22-par-apr-001/GOVERNANCE_REVIEW.md`](../../../audits/evidence/2026-07-22-par-apr-001/GOVERNANCE_REVIEW.md)
- [`../../../audits/evidence/2026-07-22-par-apr-001/TEST_RESULTS.md`](../../../audits/evidence/2026-07-22-par-apr-001/TEST_RESULTS.md)
- [`../../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md`](../../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md) (PAR-APR scope)

**Implementation branch:** `cursor/feat-par-apr-001-foundation-governance` @ `b97a1792`  
**Tranche-1 integration:** PR [#50](https://github.com/Technivian/CLMOne/pull/50) merged to `main` @ `c52d699a` (2026-07-22T09:22:22Z)

---

## 1. Motions and votes

### Motion 1 — Accept ADR-0013

**Motion:** Change ADR-0013 status from **Proposed** to **Accepted** for the canonical Approval Requirement / Approval Decision split (additive schema, governed write path, vocabulary mapping, audit events, and documented non-goals).

| Approver | GitHub identity | Governance capacity | Authority basis | Vote | Consent |
|---|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product governance / repository steward | `.github/CODEOWNERS` (`/docs/`); `GOVERNANCE_CHARTER.md` v2.0 | **Approve** | Written consent recorded |
| Technivian | @Technivian | Engineering governance / repository steward | `.github/CODEOWNERS` (`/contracts/`, `/docs/`); PDR-0003 | **Approve** | Written consent recorded |
| Security & privacy (advisory) | @Technivian | Security review capacity (same steward) | `SECURITY_PRIVACY_ACCESS_AND_AUDIT.md`; Charter §7 | **Approve with conditions** | Conditions acknowledged — see §6 |

**Result:** **Ratified**

**Acceptance scope limitation:** ADR-0013 acceptance authorizes **governance recognition and planning** for the canonical split. It does **not** authorize PAR-APR-002 implementation, legacy read-path retirement, or production cutover until PAR-APR-002 owner assignment, cutover plan approval, and explicit implementation authorization are recorded.

---

### Motion 2 — Formal approval of PAR-APR scope split

**Motion:** Approve programme scope split:

- **PAR-APR-001** closes as canonical foundation delivery under Accepted ADR-0013.
- **PAR-APR-002** opens for legacy cutover and residual exit criteria transferred from PAR-APR-001.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried**

---

### Motion 3 — PAR-APR-001 closure status

**Motion:** Record final PAR-APR-001 status as:

> **Closed — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.**

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried**

---

### Motion 4 — PAR-APR-002 opening status

**Motion:** Record PAR-APR-002 status as:

> **Planned — blocked pending owner assignment, cutover plan, and implementation authorization.**

Explicitly **not** In progress.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried**

---

### Motion 5 — Start PAR-ID-001

**Motion:** Authorize **PAR-ID-001** (Role Definition reconciliation) to move to **In progress** now that Tranche-1 gate and PAR-APR-001 closure are complete.

| Approver | Vote |
|---|---|
| @haroonwahed | **Approve** |
| @Technivian | **Approve** |

**Result:** **Carried** — discovery and Proposed ADR-0014 only; no privilege model changes without subsequent acceptance.

---

## 2. Rationale summary

- CANONICAL_DOMAIN_MODEL §2.23–2.24 requires Requirement vs Decision separation.
- PAR-DOC-001 delivered DocumentVersion binding; approvals needed equivalent traceability.
- Additive foundation delivered with dual-write, audit events, and migration proof.
- Cutover residuals explicitly deferred to PAR-APR-002.

---

## 3. Alternatives considered

1. Retain collapsed `ApprovalRequest` — rejected (domain violation).
2. Status-only split — rejected (no immutability / version binding).

---

## 4. Transferred exit criteria (PAR-APR-002)

See [`../2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md`](../../../audits/evidence/2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md).

---

## 5. Approval conditions

- PAR-APR-002 implementation **not** authorized by this meeting.
- ADR-0010 remains **Proposed** and was not modified.
- Tenant isolation programme proof remains **unproven** until PAR-SEC-003 closes.

---

## 6. Tenant isolation position

**Recorded finding:** Tenant isolation remains **unproven** at programme assurance level until **PAR-SEC-003** is resolved.

- Cross-org detail/update paths continue to return 404 (no data leak observed).
- The stale list-alias assertion does not demonstrate isolation failure but **blocks a clean isolation gate**.
- PAR-APR-002 cutover authorization must not proceed on the basis of a fully green isolation suite until PAR-SEC-003 closes or the assertion is updated to match intentional repository redirect behaviour.

---

## 7. Approvers and effective date

| Field | Value |
|---|---|
| **Approved by** | @haroonwahed (Product governance) · @Technivian (Engineering governance) |
| **Vote timestamp** | **2026-07-22T09:45:00Z** |
| **Effective date** | **2026-07-22** |
| **ADR-0013 status after vote** | **Accepted** |
| **Record author** | Platform Alignment Programme (documentation) |
| **Distribution** | `docs/governance/decisions/adr/`, `docs/audits/evidence/2026-07-22-par-apr-001/`, `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` |

---

## 8. Next review gate

| Gate | Trigger | Owner |
|---|---|---|
| **PAR-APR-002 planning review** | Owner assigned + cutover plan draft | Product + Engineering (TBD owner) |
| **PAR-APR-002 implementation authorization** | Accepted cutover plan + PAR-SEC-003 disposition | Programme governance |
| **PAR-ID-001 ADR acceptance** | Discovery complete + mapping proposal | @haroonwahed + @Technivian |
| **PAR-APR-002 in-progress status** | Only after implementation authorization recorded | Programme governance |

---

## 9. Post-vote documentation actions (completed)

- [x] ADR-0013 status → Accepted + approval table
- [x] Roadmap: PAR-APR-001 closed; PAR-APR-002 planned; PAR-ID-001 in progress
- [x] Evidence index updated (`docs/audits/evidence/2026-07-22-par-apr-001/INDEX.md`)
- [x] PAR-APR-002 ownership and closure checklist created
- [x] ADR-0010 **not** modified
- [x] PAR-ID-001 discovery started — Proposed ADR-0014 + characterization tests

---

## 10. Ratification validation (2026-07-22 — re-run)

**Validator:** Governance-validation phase (documentation only)  
**Report:** [`../../../audits/2026-07-22-adr-0013-ratification-validation.md`](../../../audits/2026-07-22-adr-0013-ratification-validation.md)

### Finding: approver evidence sufficient

Named repository stewards @haroonwahed and @Technivian recorded with:

- per-approver GitHub identity and governance capacity;
- authority basis (CODEOWNERS + Charter + PDR-0003);
- vote timestamp (2026-07-22T09:45:00Z);
- written consent recorded in §1.

### Final statuses

| Item | Status |
|---|---|
| ADR-0013 | **Accepted** |
| PAR-APR-001 | **Closed** — foundation delivered; governance accepted |
| PAR-APR-002 | **Planned** — not authorized for implementation |
| PAR-ID-001 | **In progress** — discovery / Proposed ADR-0014 |
