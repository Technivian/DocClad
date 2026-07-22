# ADR-0013 governance acceptance — meeting record

**Meeting type:** Programme governance review (decision record)  
**Date:** 2026-07-22 (UTC)  
**Chair:** Platform Alignment Programme governance delegate  
**Quorum:** Product governance · Engineering governance · Security & privacy review (advisory)  
**Package under review:**

- [`0013-approval-requirement-decision-split.md`](0013-approval-requirement-decision-split.md)
- [`../../audits/evidence/2026-07-22-par-apr-001/GOVERNANCE_REVIEW.md`](../../audits/evidence/2026-07-22-par-apr-001/GOVERNANCE_REVIEW.md)
- [`../../audits/evidence/2026-07-22-par-apr-001/TEST_RESULTS.md`](../../audits/evidence/2026-07-22-par-apr-001/TEST_RESULTS.md)
- [`../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md`](../../roadmap/PLATFORM_ALIGNMENT_ROADMAP.md) (PAR-APR scope)

**Implementation branch:** `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`  
**Constraint:** Documentation-only governance actions in this record. No implementation code changes authorized by this meeting beyond what already exists on the continuation branch.

---

## 1. Motions and votes

### Motion 1 — Accept ADR-0013

**Motion:** Change ADR-0013 status from **Proposed** to **Accepted** for the canonical Approval Requirement / Approval Decision split (additive schema, governed write path, vocabulary mapping, audit events, and documented non-goals).

| Approver role | Vote | Notes |
|---|---|---|
| Product governance delegate | **Approve** | Aligns with CANONICAL_DOMAIN_MODEL §2.23–2.24 |
| Engineering governance delegate | **Approve** | Additive foundation delivered; dual-write path evidenced |
| Security & privacy reviewer (advisory) | **Approve with conditions** | Tenant isolation suite not fully green — see §6 |

**Result:** **Carried — ADR-0013 Accepted (2026-07-22)**

**Acceptance scope limitation (recorded unanimously):** ADR-0013 acceptance authorizes **governance recognition and planning** for the canonical split. It does **not** authorize PAR-APR-002 implementation, legacy read-path retirement, or production cutover until PAR-APR-002 owner assignment, cutover plan approval, and explicit implementation authorization are recorded.

---

### Motion 2 — Formal approval of PAR-APR scope split

**Motion:** Approve programme scope split:

- **PAR-APR-001** closes as canonical foundation delivery under Accepted ADR-0013.
- **PAR-APR-002** opens for legacy cutover and residual exit criteria transferred from PAR-APR-001.

| Approver role | Vote |
|---|---|
| Product governance delegate | **Approve** |
| Engineering governance delegate | **Approve** |
| Security & privacy reviewer (advisory) | **Approve with conditions** |

**Result:** **Carried**

---

### Motion 3 — PAR-APR-001 closure status

**Motion:** Record final PAR-APR-001 status as:

> **Closed — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.**

| Approver role | Vote |
|---|---|
| Product governance delegate | **Approve** |
| Engineering governance delegate | **Approve** |

**Result:** **Carried**

---

### Motion 4 — PAR-APR-002 opening status

**Motion:** Record PAR-APR-002 status as:

> **Planned — blocked pending owner assignment, cutover plan, and implementation authorization.**

Explicitly **not** In progress.

| Approver role | Vote |
|---|---|
| Product governance delegate | **Approve** |
| Engineering governance delegate | **Approve** |

**Result:** **Carried**

---

## 2. Rationale

1. **Domain alignment:** Accepted CANONICAL_DOMAIN_MODEL requires distinct Approval Requirement and Approval Decision with document-version binding at decision time.
2. **Delivered foundation:** Continuation branch `c9ae7305` delivers additive `ApprovalRequirement` / `ApprovalDecision`, migration `0110`, `approval_canonical.py`, primary dual-write from `ApprovalWorkflowService`, invalidation on document supersession, and targeted PAR-APR tests (33/33 PASS in governance package).
3. **Governance hygiene:** Separating foundation (PAR-APR-001) from cutover (PAR-APR-002) matches Tranche-1 integration normalization and prevents premature “Completed” claims while legacy paths remain.
4. **Residual discipline:** DPAReviewPack, ApprovalRoute runtime mapping, ABSTAIN UI, and legacy `ApprovalRequest` retirement are cutover concerns — not ADR-0013 foundation scope.
5. **ADR-0010 untouched:** Workflow instance pinning interim (ADR-0010) remains **Proposed**; this meeting does not amend ADR-0010.

---

## 3. Consequences

| Area | Consequence |
|---|---|
| ADR-0013 | **Accepted** — canonical entity split and governed write path are repository decisions |
| PAR-APR-001 | **Closed** — no further foundation scope; evidence index frozen except governance addenda |
| PAR-APR-002 | **Planned** — owner, cutover plan, and implementation authorization required before any in-progress status |
| Implementation | Existing code on `c9ae7305` remains; **no new capability work** authorized by this meeting |
| Roadmap | Updated per post-vote documentation edits (see programme commit) |
| PAR-ID-001 | Remains blocked behind Tranche-1 programme integration gate (separate track) |
| Tenant isolation | **Unproven** at programme level until PAR-SEC-003 resolves list-alias assertion (see §6) |

---

## 4. Transferred exit criteria (PAR-APR-001 → PAR-APR-002)

The following move to PAR-APR-002 and are **not** closed by ADR-0013 acceptance:

1. Legacy `ApprovalRequest` read-path retirement plan and dual-read sunset
2. `DPAReviewPack.approval_status` reconciliation with canonical model
3. `ApprovalRoute` template configuration → runtime `ApprovalRequirement` mapping
4. `ABSTAIN` / explicit `REVOKE` UI actions
5. Full approval regression sign-off across all suites with zero named residuals
6. Tranche-1 landed on `main` before continuation-branch merge (programme integration gate)
7. Cutover migration/rollback rehearsal for legacy path removal (if any)

---

## 5. Known test issues (recorded; not blocking ADR-0013 foundation acceptance)

| Test | Module | Failure | Disposition |
|---|---|---|---|
| `WorkflowRoutingTests.test_workflow_dashboard_and_detail_surface_routing_endpoints` | `tests/test_workflow_routing.py` | `assertNotContains` fails — `/contracts/approval-rules/` link now present in Workflow Designer workspace tabs | **Pre-existing / orthogonal** to ADR-0013 foundation; track under workflow UX test hygiene (not PAR-APR-002 gate) |
| `ContractIsolationTest.test_list_shows_only_own_org` | `tests/test_cross_tenant_isolation.py` | Expects HTTP 200; receives 302 redirect to repository | **PAR-SEC-003** residual; see §6 |

PAR-APR targeted tests (`test_par_apr_001_approval`, `test_approval_workflow`, `test_approval_authorization`): **33 PASS / 0 FAIL**.

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
| **Approved by** | CLM One Platform Alignment Programme governance review (Product / Engineering) |
| **Effective date** | **2026-07-22** |
| **ADR-0013 status after vote** | **Accepted** |
| **Record author** | Programme governance delegate (documentation) |
| **Distribution** | `docs/governance/decisions/adr/`, `docs/audits/evidence/2026-07-22-par-apr-001/`, `docs/roadmap/PLATFORM_ALIGNMENT_ROADMAP.md` |

---

## 8. Next review gate

| Gate | Trigger | Owner |
|---|---|---|
| **PAR-APR-002 planning review** | Owner assigned + cutover plan draft | Product + Engineering (TBD owner) |
| **PAR-APR-002 implementation authorization** | Accepted cutover plan + Tranche-1 on `main` + PAR-SEC-003 disposition | Programme governance |
| **PAR-APR-002 in-progress status** | Only after implementation authorization recorded | Programme governance |
| **Tranche-1 programme integration** | Separate gate — required before PAR-ID-001 | Engineering |

**Next scheduled governance touchpoint:** PAR-APR-002 owner assignment workshop (date TBD).

---

## 9. Post-vote documentation actions (completed in same programme commit)

- [x] ADR-0013 status → Accepted + approval table
- [x] Roadmap: PAR-APR-001 closed; PAR-APR-002 planned
- [x] Evidence index updated (`docs/audits/evidence/2026-07-22-par-apr-001/INDEX.md`)
- [x] PAR-APR-002 ownership and closure checklist created
- [x] ADR-0010 **not** modified
