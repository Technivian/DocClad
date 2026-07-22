# PAR-EXC-001 evidence summary — 2026-07-22

## Status: In progress

**ADR-0015:** **Accepted** (`2026-07-22T19:12:39Z`).  
**Motion 2:** Default-off six-path dual-write **Authorized**; PR #69 merged (`f19eae42`).  
**Motion 3:** Controlled-pilot dual-write activation **Authorized** (`2026-07-22T20:04:34Z`) for `controlled-pilot-org` only.  
**Committed flag defaults:** remain **off**.  
**Canonical read authority:** **Unauthorized**.  
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
- Activation package: [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md) — Motion 3 **Authorized**.

### Next
1. Operational enablement in the controlled-pilot environment only (`EXCEPTION_DUAL_WRITE_ENABLED=true`, `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=controlled-pilot-org`).
2. Capture monitoring counters; honour stop conditions / rollback.
3. Keep programme **In progress** until pilot evidence + residual path decisions; do not cut over canonical read without a separate vote.
