# PAR-EXC-001 evidence index

**Programme ID:** PAR-EXC-001  
**Status:** **In progress** — discovery + canonical foundation delivered; ADR-0015 **Proposed** (not Accepted); production path cutover **not** authorized  
**ADR:** ADR-0015 **Proposed**  
**Branch:** `cursor/feat-par-exc-001-exception-waiver-discovery-d7f1`  
**Explicit non-starts:** PAR-APR-002, PAR-WF-010, PAR-ID-002

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Compliance, planning boundary, vote gate |
| [`DECISION_PACKAGE.md`](DECISION_PACKAGE.md) | Ratification package for Proposed ADR-0015 |
| [`../../../governance/decisions/adr/0015-exception-request-decision-model.md`](../../../governance/decisions/adr/0015-exception-request-decision-model.md) | ADR (**Proposed**) |

---

## Discovery and design

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary |
| [`EXCEPTION_EVIDENCE_MATRIX.md`](EXCEPTION_EVIDENCE_MATRIX.md) | Inventory of every exception-like path |
| [`TARGET_EXCEPTION_MODEL.md`](TARGET_EXCEPTION_MODEL.md) | Target `ExceptionRequest` / `ExceptionDecision` model |
| [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) | Migration `0114` + dual-read cutover plan |
| [`CHARACTERIZATION_TESTS.md`](CHARACTERIZATION_TESTS.md) | Legacy path characterization notes |

---

## Implementation evidence

| Artifact | Purpose |
|---|---|
| `contracts/models.py` — `ExceptionRequest`, `ExceptionDecision` | Additive schema |
| `contracts/services/exception_canonical.py` | Governed write path + invariants |
| `contracts/migrations/0114_exception_request_decision.py` | Additive migration (no legacy backfill) |
| `tests/test_par_exc_001_exception.py` | Invariant + characterization tests |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test run evidence |

---

## Closure gate (not met)

PAR-EXC-001 remains **In progress** until:

1. ADR-0015 Accepted (Product + Engineering; Security for Critical-control clauses);
2. Governed production write paths cut over for priority legacy surfaces (at minimum EXC-POL-001/005/007/009, EXC-DL-001) behind explicit authorization;
3. Expired exceptions stop applying on those paths;
4. Audit evidence of cutover + rollback proof.

---

## Tenant isolation statement

Canonical service denies cross-tenant create/decide. Programme-level repository isolation remains governed by PAR-SEC-003 residual posture.
