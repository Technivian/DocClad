# PAR-APR-002 — ownership and closure checklist

**Programme ID:** PAR-APR-002  
**Title:** Approval Requirement/Decision legacy cutover  
**Status:** **Planned — blocked pending owner assignment, cutover plan, and implementation authorization.**  
**Opened:** 2026-07-22 (residuals transferred from closed PAR-APR-001)  
**Predecessor:** PAR-APR-001 (closed) · ADR-0013 (**Accepted** 2026-07-22T09:45:00Z)

> **Authorization boundary:** ADR-0013 acceptance authorizes **planning only**. This checklist must be complete before PAR-APR-002 may move to **In progress** or any implementation work begins.

---

## 1. Ownership (not assigned)

| Role | Owner | Status |
|---|---|---|
| Programme owner | _Unassigned_ | **Blocked** |
| Engineering lead | _Unassigned_ | **Blocked** |
| Product sign-off | _Unassigned_ | **Blocked** |
| Security reviewer | _Unassigned_ | **Blocked** |

**Gate:** Record named owners in this section before cutover plan review.

---

## 2. Entry criteria (before In progress)

- [x] Tranche-1 programme integration gate passed (`main` @ `c52d699a`)
- [x] ADR-0013 **Accepted**
- [x] PAR-APR-001 programme closure ratified
- [ ] Named programme owner assigned
- [ ] Cutover plan draft published under this folder
- [ ] Implementation authorization recorded by programme governance

---

## 3. Exit criteria (closure checklist)

Transferred from PAR-APR-001 / ADR-0013 §6 non-goals:

- [ ] Legacy `ApprovalRequest` read-path retirement plan approved and executed
- [ ] Dual-write sunset — canonical reads authoritative; legacy mirror write-only or removed per plan
- [ ] `DPAReviewPack.approval_status` reconciled with canonical model
- [ ] `ApprovalRoute` template rows mapped to runtime `ApprovalRequirement` where required
- [ ] `ABSTAIN` and explicit `REVOKE` UI actions wired
- [ ] Full approval regression suites PASS (including workflow + authorization)
- [ ] Migration cutover/rollback rehearsed if legacy removal requires schema change
- [ ] Audit evidence updated in `docs/audits/evidence/2026-07-22-par-apr-002/`
- [ ] Roadmap PAR-APR-002 marked Closed with evidence links

---

## 4. Programme test gates

| Gate | Requirement | Current |
|---|---|---|
| PAR-APR targeted tests | 33/33 PASS on foundation branch | **Met** |
| Isolation suite | Full green | **Not met** — PAR-SEC-003 open |
| Workflow routing test | `test_workflow_dashboard_and_detail_surface_routing_endpoints` | **Fail** — orthogonal; fix or waive in cutover plan |
| Tenant isolation proof | Programme-level | **Unproven** until PAR-SEC-003 |

---

## 5. Dependencies

| Dependency | Status |
|---|---|
| PAR-APR-001 foundation (`b97a1792`) | Complete |
| ADR-0013 Accepted | **Complete** |
| PAR-DOC-001 DocumentVersion | Complete |
| Tranche-1 on `main` | Complete |
| PAR-SEC-003 | Open — blocks isolation proof |
| ADR-0010 | **Proposed** — not modified; not required for PAR-APR-002 planning |

---

## 6. Implementation authorization

| Field | Value |
|---|---|
| **Authorized?** | **No** |
| **Reason** | Owner unassigned; cutover plan not approved |
| **What ADR-0013 acceptance allows** | Planning, checklist maintenance, owner workshop |
| **What it does not allow** | Code changes, legacy removal, dual-write sunset |

**Next review gate:** Owner assignment workshop → cutover plan draft → governance implementation authorization vote.
