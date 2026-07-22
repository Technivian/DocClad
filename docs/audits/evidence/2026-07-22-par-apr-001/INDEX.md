# PAR-APR-001 evidence index

**Programme ID:** PAR-APR-001  
**Status:** **Closed** — foundation delivered; ADR-0013 Accepted  
**ADR:** ADR-0013 **Accepted** (2026-07-22T09:45:00Z)  
**Branch:** `cursor/feat-par-apr-001-foundation-governance` @ `b97a1792`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Compliance, vote validation, planning boundary |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test evidence and known programme failures |
| [`../../../governance/decisions/adr/0013-approval-requirement-decision-split.md`](../../../governance/decisions/adr/0013-approval-requirement-decision-split.md) | ADR (Accepted) |
| [`../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0013-governance-acceptance-meeting-record-2026-07-22.md) | Meeting record + ratification |
| [`../../../audits/2026-07-22-adr-0013-ratification-validation.md`](../../../audits/2026-07-22-adr-0013-ratification-validation.md) | Ratification validation report |

---

## Design and implementation evidence

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary |
| [`TARGET_APPROVAL_MODEL.md`](TARGET_APPROVAL_MODEL.md) | Target entity model |
| [`APPROVAL_USAGE_MATRIX.md`](APPROVAL_USAGE_MATRIX.md) | Read/write path matrix |
| [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) | Migration `0111` plan |

---

## Test and migration proof

| Artifact | Purpose |
|---|---|
| [`django-tests.txt`](django-tests.txt) | PAR-APR module test run |
| [`migrate-rollback.txt`](migrate-rollback.txt) | Migration 0111 rollback proof |
| [`migrate-reforward.txt`](migrate-reforward.txt) | Migration 0111 re-forward proof |

---

## Successor programme

| Artifact | Purpose |
|---|---|
| [`../2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md`](../2026-07-22-par-apr-002/CLOSURE_CHECKLIST.md) | PAR-APR-002 ownership, exit criteria, authorization gate |

---

## Tenant isolation statement

Programme-level tenant isolation remains **unproven** until **PAR-SEC-003** resolves `ContractIsolationTest.test_list_shows_only_own_org`.
