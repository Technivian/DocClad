# PAR-EXC-001 evidence index

**Programme ID:** PAR-EXC-001  
**Status:** **In progress** — foundation + dual-write adapters (default-off); ADR-0015 **Proposed**; votes **Requested** (not invented)  
**ADR:** ADR-0015 **Proposed**  
**Foundation branch / PR:** `cursor/feat-par-exc-001-exception-waiver-discovery-d7f1` / [#66](https://github.com/Technivian/CLMOne/pull/66)  
**Dual-write branch:** `cursor/feat-par-exc-001-priority-dual-write-d7f1`  
**Explicit non-starts:** PAR-APR-002, PAR-WF-010, PAR-ID-002

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Compliance, planning boundary, vote gate |
| [`DECISION_PACKAGE.md`](DECISION_PACKAGE.md) | Ratification package for Proposed ADR-0015 |
| [`DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md`](DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md) | Motion 2 dual-write auth (**Requested**) |
| [`../../../governance/decisions/adr/0015-exception-request-decision-model.md`](../../../governance/decisions/adr/0015-exception-request-decision-model.md) | ADR (**Proposed**) |
| [`../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md) | Motions 1–2 + ballot templates |

---

## Discovery and design

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary |
| [`EXCEPTION_EVIDENCE_MATRIX.md`](EXCEPTION_EVIDENCE_MATRIX.md) | Inventory of every exception-like path |
| [`TARGET_EXCEPTION_MODEL.md`](TARGET_EXCEPTION_MODEL.md) | Target `ExceptionRequest` / `ExceptionDecision` model |
| [`CANONICAL_MAPPING.md`](CANONICAL_MAPPING.md) | Six-path dual-write outcome mapping |
| [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md) | Migration `0114`/`0115` + dual-read cutover plan |
| [`CHARACTERIZATION_TESTS.md`](CHARACTERIZATION_TESTS.md) | Legacy path characterization notes |

---

## Implementation evidence

| Artifact | Purpose |
|---|---|
| `ExceptionRequest` / `ExceptionDecision` + `correlation_id` | Additive schema (`0114`, `0115`) |
| `contracts/services/exception_canonical.py` | Governed write path + invariants |
| `contracts/services/exception_dual_write.py` | Six-path dual-write (legacy authoritative) |
| Priority path wiring | keep_exception, ACCEPTED_RISK, AI exception, ConflictCheck WAIVED, deadline_defer, DPA approve-with-blockers |
| `tests/test_par_exc_001_exception.py` | 11 OK |
| `tests/test_par_exc_001_dual_write.py` | 16 OK |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) / [`DUAL_WRITE_TEST_RESULTS.md`](DUAL_WRITE_TEST_RESULTS.md) | Test evidence |
| [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) | Pilot template (**not activated**) |

---

## Closure gate (not met)

PAR-EXC-001 remains **In progress** until:

1. ADR-0015 Accepted (genuine Product + Engineering + Security advisory votes);
2. Motion 2 dual-write authorization Accepted;
3. Six priority dual-write paths delivered and verified (**code ready, flags off**);
4. Controlled-pilot activation evidence;
5. Remaining production exception paths inventoried or transferred to named residual;
6. Canonical read authority and legacy retirement criteria documented.

---

## Tenant isolation statement

Canonical service denies cross-tenant create/decide/dual-write. Programme-level repository isolation remains governed by PAR-SEC-003 residual posture.
