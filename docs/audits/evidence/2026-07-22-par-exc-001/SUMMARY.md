# PAR-EXC-001 evidence summary — 2026-07-22

## Status: Completed

**ADR-0015:** **Accepted** (`2026-07-22T19:12:39Z`).  
**Motion 2:** Default-off six-path dual-write **Authorized**; PR #69 merged (`f19eae42`).  
**Motion 3:** Controlled-pilot dual-write activation **Authorized** (`2026-07-22T20:04:34Z`; PR #74 @ `058c5ed0`).  
**Operational activation:** **PASS** — [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md).  
**Pilot monitoring:** PR #78 merged prematurely `e26a2bdc`; correction PR #79 merged `83a0a00f`. The historical record is preserved; monitoring remains read-only and does not change runtime authority — [`PILOT_MONITORING_EXTENSION.md`](PILOT_MONITORING_EXTENSION.md).
**Committed flag defaults:** remain **off**.  
**Canonical read authority:** **PASS (named non-production observation only)** — authorization package PR [#81](https://github.com/Technivian/CLMOne/pull/81) merged `3eba3602211c58ad73d6612201d6e8587f21f689`; default-off implementation PR [#85](https://github.com/Technivian/CLMOne/pull/85) merged `86625b95cfbc968dea2f7cb31b8fc354a36584cf`; results [`CANONICAL_READ_OPERATOR_RESULTS.md`](CANONICAL_READ_OPERATOR_RESULTS.md). Both flags are now **off**, allowlists empty, and legacy authority restored.
**Not started:** PAR-APR-002, PAR-WF-010, PAR-ID-002.

### Discovery
- No first-class `ExceptionRequest` / `ExceptionDecision` / `Waiver` object existed.
- Exception-like behavior was scattered across RiskSignal keep/accept, DPARiskItem `ACCEPTED_RISK`, AI finding `EXCEPTION_REQUESTED` / dismissal reasons, ConflictCheck `WAIVED`, deadline defer (+7 days, no reason), lifecycle `system=True` skips, repair/`skip_authz`, production emergency flags, and pilot allowlists.
- Full matrix: [`EXCEPTION_EVIDENCE_MATRIX.md`](EXCEPTION_EVIDENCE_MATRIX.md).

### Canonical foundation (additive)
- `ExceptionRequest` — temporary deviation with owner, expiry, scope, authority, compensating controls, risk classification, explicit `granted_privileges`.
- `ExceptionDecision` — immutable decision history.
- Service: `contracts/services/exception_canonical.py`.
- Migrations: `0114_exception_request_decision`, `0115_exception_correlation_id` (additive; **no** silent legacy backfill).

### Dual-write (legacy authoritative)
- Service: `contracts/services/exception_dual_write.py`.
- Six paths: `KEEP_EXCEPTION`, `ACCEPTED_RISK`, `AI_EXCEPTION`, `CONFLICT_CHECK_WAIVER`, `DEADLINE_DEFER`, `DPA_APPROVE_WITH_BLOCKERS`.
- Flags: `EXCEPTION_DUAL_WRITE_ENABLED` / `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST` (committed defaults off).
- Activation package: [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) — Motion 3 **Authorized**; operational evidence **PASS**.

### Next (from evidence)
PAR-EXC-001 is complete. The next unstarted roadmap item is PAR-APR-002; it has not begun in this slice.
