# PAR-APR-001 evidence index

**Programme ID:** PAR-APR-001  
**Final status:** Closed — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.  
**ADR:** ADR-0013 **Accepted** (2026-07-22)  
**Branch:** `cursor/feat-platform-documentation-alignment-d7f1` @ `c9ae7305`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Governance compliance and vote summary |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test evidence and known residuals |
| [`../../../governance/decisions/adr/0013-approval-requirement-decision-split.md`](../../../governance/decisions/adr/0013-approval-requirement-decision-split.md) | **Accepted** ADR |
| [`../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md) | Formal meeting record |

---

## Design and implementation evidence

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary (updated at closure) |
| [`TARGET_APPROVAL_MODEL.md`](TARGET_APPROVAL_MODEL.md) | Target entity model |
| [`APPROVAL_USAGE_MATRIX.md`](APPROVAL_USAGE_MATRIX.md) | Read/write path matrix |
| [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) | Migration `0110` plan |

---

## Test and migration proof

| Artifact | Purpose |
|---|---|
| [`django-tests.txt`](django-tests.txt) | PAR-APR module test run |
| [`migrate-rollback.txt`](migrate-rollback.txt) | Migration 0110 rollback proof |
| [`migrate-reforward.txt`](migrate-reforward.txt) | Migration 0110 re-forward proof |

---

## Successor programme

| Artifact | Purpose |
|---|---|
| [`../2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md`](../2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md) | PAR-APR-002 ownership, exit criteria, authorization gate |

---

## Explicitly out of scope (transferred)

- Legacy `ApprovalRequest` retirement → PAR-APR-002
- DPAReviewPack merge → PAR-APR-002
- ApprovalRoute runtime mapping → PAR-APR-002
- ABSTAIN/REVOKE UI → PAR-APR-002
