# PAR-APR-001 / ADR-0013 — governance review package

**Review date:** 2026-07-22  
**Ratification date:** 2026-07-22T09:45:00Z  
**Branch:** `cursor/feat-par-apr-001-foundation-governance` @ `b97a1792`  
**ADR:** [`docs/governance/decisions/adr/0013-approval-requirement-decision-split.md`](../../../governance/decisions/adr/0013-approval-requirement-decision-split.md) — **Accepted**  
**Meeting record:** [`docs/governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md)  
**Ratification report:** [`docs/audits/2026-07-22-adr-0013-ratification-validation.md`](../../../audits/2026-07-22-adr-0013-ratification-validation.md)

---

## 1. Authority chain

| Document | Status | Relevance |
|---|---|---|
| `GOVERNANCE_CHARTER.md` v2.0 | Active | Constitutional authority |
| PDR-0003 | Accepted | Supporting docs adopted |
| `CANONICAL_DOMAIN_MODEL.md` | Accepted | §2.23–2.24 Requirement vs Decision |
| PDR-0001 | Accepted | Finance threshold single entry (unchanged) |
| ADR-0013 | **Accepted** | Canonical split — binding for foundation scope |
| ADR-0010 | **Proposed** (unchanged) | Not invoked by this review |

---

## 2. Scope under review

### PAR-APR-001 (closed)

**Delivered on follow-up branch `b97a1792`:**

| Deliverable | Evidence |
|---|---|
| Additive `ApprovalRequirement` model | `contracts/models.py`; migration `0111` |
| Additive `ApprovalDecision` model | `contracts/models.py`; migration `0111` |
| Primary dual-write service | `contracts/services/approval_canonical.py` |
| `ApprovalWorkflowService` integration | `contracts/services/approval_workflow.py` |
| Document version binding | FK + `document_version_missing` flag |
| Invalidation on supersession | `invalidate_open_requirements_for_contract()` |
| Legacy mirror | `ApprovalRequirement.legacy_request` OneToOne → `ApprovalRequest` |
| Audit events | `approval.requirement.*`, `approval.decision.recorded` |
| Migration backfill | `migrate-rollback.txt`, `migrate-reforward.txt` |

**Closure status:**

> **Closed** — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.

### PAR-APR-002 (opening — planning only)

**Status:**

> Planned — blocked pending owner assignment, cutover plan, and implementation authorization.

ADR-0013 acceptance authorizes **planning only** — not PAR-APR-002 implementation.

---

## 3. Approver and vote validation

| Required record | Present? |
|---|---|
| Named approvers (@haroonwahed, @Technivian) | **Yes** |
| Authority basis per approver | **Yes** — CODEOWNERS + Charter + PDR-0003 |
| Vote timestamp | **Yes** — 2026-07-22T09:45:00Z |
| Written consent | **Yes** — meeting record §1 |
| Planning-only boundary | **Yes** |
| PAR-APR-002 not authorized | **Yes** |

---

## 4. Conditions and residuals

| Condition | Status |
|---|---|
| Tenant isolation unproven (PAR-SEC-003) | **Open** — recorded; does not block foundation acceptance |
| PAR-APR-002 cutover residuals | Transferred — see CLOSURE_CHECKLIST |
| ADR-0010 unchanged | **Confirmed** |

---

## 5. Programme disposition

| Item | Final status |
|---|---|
| ADR-0013 | **Accepted** |
| PAR-APR-001 | **Closed** |
| PAR-APR-002 | **Planned** |
| PAR-ID-001 | **In progress** (authorized by Motion 5) |
