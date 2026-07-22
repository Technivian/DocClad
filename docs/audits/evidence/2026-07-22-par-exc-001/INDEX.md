# PAR-EXC-001 evidence index

**Programme ID:** PAR-EXC-001  
**Status:** **In progress** — ADR-0015 **Accepted**; foundation PR #66 **merged** (`982b0900`); dual-write PR #67 (default-off); controlled-pilot activation **Requested** / **not** activated; canonical read cutover **unauthorized**  
**ADR:** ADR-0015 **Accepted** (`2026-07-22T19:12:39Z`)  
**Foundation:** PR [#66](https://github.com/Technivian/CLMOne/pull/66) merge `982b0900b37f64cf3ce36f44e23a062ae908dbb7`  
**Dual-write branch / PR:** `cursor/feat-par-exc-001-dual-write-main-d7f1` / [#69](https://github.com/Technivian/CLMOne/pull/69) (supersedes stacked [#67](https://github.com/Technivian/CLMOne/pull/67))  
**Explicit non-starts:** PAR-APR-002, PAR-WF-010, PAR-ID-002

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Compliance, planning boundary, vote gate |
| [`DECISION_PACKAGE.md`](DECISION_PACKAGE.md) | Ratification package for ADR-0015 |
| [`DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md`](DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md) | Motion 2 dual-write auth (**Authorized** default-off) |
| [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) | Motion 3 activation package (**Requested**; flags off) |
| [`../../../governance/decisions/adr/0015-exception-request-decision-model.md`](../../../governance/decisions/adr/0015-exception-request-decision-model.md) | ADR (**Accepted**) |
| [`../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md) | Motions 1–2 ratified; Motion 3 not opened here |

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
| [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) | Pilot activation package (**votes Requested**; **not activated**) |

---

## Closure gate (partial — keep In progress)

| Gate | Status |
|---|---|
| ADR-0015 Accepted (genuine Product + Engineering + Security votes) | **Met** |
| Motion 2 dual-write authorization (default-off) | **Met** |
| Six priority dual-write paths delivered and verified (flags off) | Code on PR #69; merge pending |
| Controlled-pilot activation evidence | Package **Requested**; **not** activated |
| Remaining production exception paths inventoried or residual | Break-glass + signature-provider inventoried |
| Canonical read authority and legacy retirement | **Unauthorized** |

---

## Tenant isolation statement

Canonical service denies cross-tenant create/decide/dual-write. Programme-level repository isolation remains governed by PAR-SEC-003 residual posture.
