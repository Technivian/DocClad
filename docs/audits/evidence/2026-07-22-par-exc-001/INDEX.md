# PAR-EXC-001 evidence index

**Programme ID:** PAR-EXC-001  
**Status:** **In progress** — ADR-0015 **Accepted**; foundation PR #66 **merged** (`982b0900`); dual-write PR #69 **merged** (`f19eae42`, default-off); Motion 3 **Authorized** (PR #74 @ `058c5ed0`); controlled-pilot operational activation evidence **PASS**; monitoring PR #78 **merged prematurely** `e26a2bdc` (Product Approve only); correction PR #79 **merged** `83a0a00f`; Eng/Sec **post-merge ratification pending**; committed flag defaults remain **off**; canonical read cutover **unauthorized**  
**ADR:** ADR-0015 **Accepted** (`2026-07-22T19:12:39Z`)  
**Foundation:** PR [#66](https://github.com/Technivian/CLMOne/pull/66) merge `982b0900b37f64cf3ce36f44e23a062ae908dbb7`  
**Dual-write:** PR [#69](https://github.com/Technivian/CLMOne/pull/69) merge `f19eae42fd14e310364fb047868abea4951a5efe` (supersedes stacked [#67](https://github.com/Technivian/CLMOne/pull/67))  
**Activation auth:** Motion 3 **Authorized** — PR [#74](https://github.com/Technivian/CLMOne/pull/74) @ `058c5ed0`  
**Activation evidence:** [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md) (**PASS**)  
**Explicit non-starts:** PAR-APR-002, PAR-WF-010, PAR-ID-002

---

## Governance

| Artifact | Purpose |
|---|---|
| [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md) | Compliance, planning boundary, vote gate |
| [`DECISION_PACKAGE.md`](DECISION_PACKAGE.md) | Ratification package for ADR-0015 |
| [`DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md`](DUAL_WRITE_IMPLEMENTATION_AUTHORIZATION.md) | Motion 2 dual-write auth (**Authorized** default-off) |
| [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) | Motion 3 activation package (**Authorized**; operational **PASS**) |
| [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md) | Operational enablement evidence (**PASS**) |
| [`../../../governance/decisions/adr/0015-exception-request-decision-model.md`](../../../governance/decisions/adr/0015-exception-request-decision-model.md) | ADR (**Accepted**) |
| [`../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md) | Motions 1–3 ratified |

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
| [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) | Pilot activation package (**Motion 3 Authorized**; operational **PASS**) |
| [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md) | Operational evidence (**PASS**) |
| [`PILOT_MONITORING_EXTENSION.md`](PILOT_MONITORING_EXTENSION.md) | Read-only pilot_daily_health dual-write monitoring (PR #78 merge `e26a2bdc`; correction PR #79 merge `83a0a00f`; Eng/Sec post-merge ratification **pending**) |

---

## Closure gate (partial — keep In progress)

| Gate | Status |
|---|---|
| ADR-0015 Accepted (genuine Product + Engineering + Security votes) | **Met** |
| Motion 2 dual-write authorization (default-off) | **Met** |
| Six priority dual-write paths delivered and verified (flags off) | **Met** (PR #69 merged `f19eae42`; flags off) |
| Controlled-pilot activation authorization (Motion 3) | **Met** (PR #74 @ `058c5ed0`) |
| Controlled-pilot operational enablement + monitoring evidence | **PASS** — [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md) |
| Remaining production exception paths inventoried or residual | Break-glass + signature-provider inventoried |
| Canonical read authority and legacy retirement | **Unauthorized** |

---

## Tenant isolation statement

Canonical service denies cross-tenant create/decide/dual-write. Programme-level repository isolation remains governed by PAR-SEC-003 residual posture.
