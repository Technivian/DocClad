# PAR-EXC-001 evidence summary — 2026-07-22

## Status: In progress

**PAR-ID-001:** Closed (prior programme).  
**This slice:** Discovery + canonical Exception/Waiver foundation.  
**ADR-0015:** **Proposed** — do not treat as Accepted.  
**Not started:** PAR-APR-002, PAR-WF-010, PAR-ID-002.

### Discovery
- No first-class `ExceptionRequest` / `ExceptionDecision` / `Waiver` object existed.
- Exception-like behavior was scattered across RiskSignal keep/accept, DPARiskItem `ACCEPTED_RISK`, AI finding `EXCEPTION_REQUESTED` / dismissal reasons, ConflictCheck `WAIVED`, deadline defer (+7 days, no reason), lifecycle `system=True` skips, repair/`skip_authz`, production emergency flags, and pilot allowlists.
- Full matrix: [`EXCEPTION_EVIDENCE_MATRIX.md`](EXCEPTION_EVIDENCE_MATRIX.md).

### Canonical foundation (additive)
- `ExceptionRequest` — temporary deviation with owner, expiry, scope, authority, compensating controls, risk classification, explicit `granted_privileges`.
- `ExceptionDecision` — immutable decision history.
- Service: `contracts/services/exception_canonical.py`.
- Migration: `0114_exception_request_decision` (additive; **no** silent legacy backfill).

### Invariants enforced in service
- Temporary unless explicitly approved permanent (`is_permanent_approved`).
- Owner + expiry required (expiry waived only when permanent approved).
- Approval authority explicit; Critical security bypass requires `security_approval=True`.
- Unknown privilege tokens rejected; decisions cannot invent privileges.
- Expired exceptions stop applying (`exception_is_applicable` / `privilege_granted`).
- Renewal creates a **new** ExceptionRequest; prior superseded via governed decision.
- Decisions immutable after create.
- Cross-tenant operations prohibited.
- UI visibility is not authorization (server-side checks).

### Explicit non-goals this slice
- No production path cutover (keep/accept, DPA accepted risk, deadline defer, etc. still legacy).
- No Acceptance of ADR-0015.
- No PAR-APR-002 / PAR-WF-010 / PAR-ID-002 work.

### Next
1. Ratify ADR-0015.
2. Authorize per-path cutover (dual-read → dual-write → canonical authority) starting with highest-risk product paths.
3. Keep programme **In progress** until governed production paths are delivered.
