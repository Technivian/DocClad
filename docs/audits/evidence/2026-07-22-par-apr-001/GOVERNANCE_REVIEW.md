# PAR-APR-001 / ADR-0013 — governance review package

**Review date:** 2026-07-22  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`  
**ADR:** [`docs/governance/decisions/adr/0013-approval-requirement-decision-split.md`](../../../governance/decisions/adr/0013-approval-requirement-decision-split.md)  
**Meeting record:** [`docs/governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md)

---

## 1. Authority chain

| Document | Status | Relevance |
|---|---|---|
| `GOVERNANCE_CHARTER.md` v2.0 | Active | Constitutional authority |
| PDR-0003 | Accepted | Supporting docs adopted |
| `CANONICAL_DOMAIN_MODEL.md` | Accepted | §2.23–2.24 Requirement vs Decision |
| PDR-0001 | Accepted | Finance threshold single entry (unchanged) |
| ADR-0013 | **Accepted** (2026-07-22) | Canonical split decision |
| ADR-0010 | **Proposed** (unchanged) | Not invoked by this review |

---

## 2. Scope under review

### PAR-APR-001 (closing)

**Delivered on continuation branch:**

| Deliverable | Evidence |
|---|---|
| Additive `ApprovalRequirement` model | `contracts/models.py`; migration `0110` |
| Additive `ApprovalDecision` model | `contracts/models.py`; migration `0110` |
| Primary dual-write service | `contracts/services/approval_canonical.py` |
| `ApprovalWorkflowService` integration | `contracts/services/approval_workflow.py` |
| Document version binding | FK + `document_version_missing` flag |
| Invalidation on supersession | `invalidate_open_requirements_for_contract()` |
| Legacy mirror | `ApprovalRequirement.legacy_request` OneToOne → `ApprovalRequest` |
| Audit events | `approval.requirement.*`, `approval.decision.recorded` |
| Migration backfill | `docs/audits/evidence/2026-07-22-par-apr-001/migrate-*.txt` |

**Formal closure status:**

> Closed — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.

### PAR-APR-002 (opening — planning only)

**Status:**

> Planned — blocked pending owner assignment, cutover plan, and implementation authorization.

ADR-0013 acceptance **does not** authorize PAR-APR-002 implementation.

---

## 3. Governance compliance assessment

| Criterion | Assessment |
|---|---|
| New domain objects introduced with ADR | **Compliant** — ADR-0013 now Accepted |
| Silent legacy removal | **Compliant** — not attempted; mirror retained |
| Tenant scoping on new models | **Compliant** — `organization` FK + queryset managers |
| Document version binding | **Compliant** — aligns with PAR-DOC-001 |
| Finance threshold (PDR-0001) | **Compliant** — no second entry path introduced |
| Charter v3 as authority | **Compliant** — not used |
| ADR-0010 modified | **Compliant** — not touched |

---

## 4. Residuals transferred to PAR-APR-002

1. Legacy `ApprovalRequest` read-path retirement
2. `DPAReviewPack` parallel approval model merge
3. `ApprovalRoute` → runtime requirement mapping
4. `ABSTAIN` / `REVOKE` UI wiring
5. Full-suite regression with zero named residuals
6. Programme integration gate (Tranche-1 on `main`) before continuation merge
7. Cutover plan + owner assignment + implementation authorization

---

## 5. Test and isolation caveats

See [`TEST_RESULTS.md`](TEST_RESULTS.md).

**Programme position:** Tenant isolation remains **unproven** until PAR-SEC-003 resolves `ContractIsolationTest.test_list_shows_only_own_org`.

---

## 6. Vote summary

| Motion | Result |
|---|---|
| ADR-0013 Proposed → Accepted | **Carried** |
| PAR-APR scope split approved | **Carried** |
| PAR-APR-001 closed (foundation) | **Carried** |
| PAR-APR-002 planned (not in progress) | **Carried** |

**Effective:** 2026-07-22
