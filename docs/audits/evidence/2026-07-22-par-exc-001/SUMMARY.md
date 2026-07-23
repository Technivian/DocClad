# PAR-EXC-001 evidence summary — 2026-07-22

## Status: In progress

**ADR-0015:** **Accepted** (`2026-07-22T19:12:39Z`).  
**Motion 2:** Default-off six-path dual-write **Authorized**; PR #69 merged (`f19eae42`).  
**Motion 3:** Controlled-pilot dual-write activation **Authorized** (`2026-07-22T20:04:34Z`; PR #74 @ `058c5ed0`).  
**Operational activation:** **PASS** — [`CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md`](CONTROLLED_PILOT_DUAL_WRITE_ACTIVATION_RESULTS.md).  
**Pilot monitoring:** PR #78 merged prematurely `e26a2bdc`; correction PR #79 merged `83a0a00f`. The historical record is preserved; monitoring remains read-only and does not change runtime authority — [`PILOT_MONITORING_EXTENSION.md`](PILOT_MONITORING_EXTENSION.md).
**Committed flag defaults:** remain **off**.  
**Canonical read authority:** **Not ready** — package [`CANONICAL_READ_AUTHORITY_AUTHORIZATION.md`](CANONICAL_READ_AUTHORITY_AUTHORIZATION.md) on PR [#81](https://github.com/Technivian/CLMOne/pull/81) requires approved Engineering and Security GitHub reviews, green CI, default-off reversible flags, and an operator record; flags are **not** enabled.
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
1. Obtain approved Engineering and Security GitHub reviews and green CI for PR [#81](https://github.com/Technivian/CLMOne/pull/81); do not enable flags.
2. After PR #81 is merged, implement canonical read behind reversible default-off flags in a separate reviewed PR.
3. Keep programme **In progress** until the named-environment operator run passes, flags are returned off, and legacy authority is restored; do not start PAR-APR-002 / PAR-WF-010 / PAR-ID-002 from this slice.
