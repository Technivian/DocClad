# Decision package — ADR-0015 Exception Request / Decision model

**Programme:** PAR-EXC-001  
**Record:** [`../../governance/decisions/adr/0015-exception-request-decision-model.md`](../../governance/decisions/adr/0015-exception-request-decision-model.md)  
**Status sought:** Acceptance of ADR-0015 (**currently Proposed**)  
**Evidence:** `docs/audits/evidence/2026-07-22-par-exc-001/`

## Ask

Ratify the canonical Exception/Waiver split:

- `ExceptionRequest` — temporary approved deviation with owner, expiry, scope, authority, compensating controls, risk class, explicit privileges;
- `ExceptionDecision` — immutable decision history;
- server-side applicability and authorization;
- tenant isolation;
- Critical security-control bypass requires explicit Security approval.

## Scope of acceptance (if ratified)

| In scope | Out of scope |
|---|---|
| Canonical foundation vocabulary + invariants | Immediate cutover of all legacy paths |
| Additive schema already landed under Proposed posture | PAR-APR-002, PAR-WF-010, PAR-ID-002 |
| Dual-path cutover **planning** | Silent privilege grants / invented backfill authorities |

Production path cutover remains separately authorized after Acceptance.

## Required votes

| Role | Actor | Decision | Timestamp (UTC) |
|---|---|---|---|
| Product governance | _pending_ | | |
| Engineering governance | _pending_ | | |
| Security & privacy | _pending_ (required for Critical clauses) | | |

## Conditions anticipated

- Default temporary; permanent only with explicit decision flag.
- No exception may expand privileges beyond declared tokens.
- Expired exceptions must stop applying on any cut-over enforcement path.
- Platform break-glass paths need Security review before dual-write.

## Links

- Evidence index: [`INDEX.md`](INDEX.md)
- Matrix: [`EXCEPTION_EVIDENCE_MATRIX.md`](EXCEPTION_EVIDENCE_MATRIX.md)
- Target model: [`TARGET_EXCEPTION_MODEL.md`](TARGET_EXCEPTION_MODEL.md)
- Migration plan: [`MIGRATION_PLAN.md`](MIGRATION_PLAN.md)
