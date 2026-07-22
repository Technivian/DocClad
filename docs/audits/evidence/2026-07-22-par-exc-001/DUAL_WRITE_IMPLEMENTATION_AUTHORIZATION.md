# Dual-write implementation authorization — PAR-EXC-001 priority paths

**Programme:** PAR-EXC-001  
**Prerequisite:** ADR-0015 **Accepted** (Motion 1) — **met** 2026-07-22T19:12:39Z  
**Status:** **Authorized** (default-off implementation only)  
**Meeting record:** [`../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0015-governance-acceptance-meeting-record-2026-07-22.md)

---

## Motion — Authorize six-path dual-write (legacy authoritative, default-off)

Authorize implementation of dual-write adapters for:

| # | Legacy path | Source classification |
|---|---|---|
| 1 | `keep_exception` | `KEEP_EXCEPTION` |
| 2 | DPARiskItem `ACCEPTED_RISK` | `ACCEPTED_RISK` |
| 3 | AI finding exception | `AI_EXCEPTION` |
| 4 | ConflictCheck `WAIVED` | `CONFLICT_CHECK_WAIVER` |
| 5 | `deadline_defer` | `DEADLINE_DEFER` |
| 6 | DPA approve-with-blockers | `DPA_APPROVE_WITH_BLOCKERS` |

### Authorized behavior

- Legacy behavior remains **authoritative**.
- Each new exception action also creates a canonical `ExceptionRequest`.
- The governing outcome creates an immutable `ExceptionDecision` (AI exception stays SUBMITTED until a later authorized decision).
- Request, decision, and legacy record share a correlation ID.
- Tenant, actor, reason, scope, owner, authority basis, and expiry are preserved (no invented historical fields).
- Compensating controls are recorded.
- Critical bypasses require recorded Security approval (`security_approval=True`).
- Dual-write is idempotent on correlation ID + source.
- Canonical failures are visible and audited (`exception.dual_write_failed`).
- Flags default **off**; controlled-pilot allowlist activation is **separate**.

### Explicitly excluded

- Deletion of legacy exception fields
- Canonical read-path authority
- Automatic privilege expansion
- Silent bypass of Critical controls
- Cross-tenant exceptions
- Automatic repair
- Retrospective bulk invention of historical exceptions
- Controlled-pilot flag enablement (separate activation package)
- PAR-APR-002 / PAR-WF-010 / PAR-ID-002

### Flags (defaults)

| Flag | Default |
|---|---|
| `EXCEPTION_DUAL_WRITE_ENABLED` | `false` |
| `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST` | empty (no orgs) |

### Failure policy

| Class | Behavior |
|---|---|
| Ordinary dual-write failure | Preserve legacy transaction where safe; emit `exception.dual_write_failed` |
| Cross-tenant mismatch | **Fail closed** |
| Critical bypass without Security approval | **Fail closed** + `exception.security_gate_blocked` |
| Malformed privilege scope | **Fail closed** |

---

## Votes (verbatim; authoritative)

| Approver | Capacity | Vote | Timestamp |
|---|---|---|---|
| @haroonwahed | Product | **Approve** | 2026-07-22T19:12:31Z |
| @Technivian | Engineering | **Approve** | 2026-07-22T19:12:35Z |
| @Technivian | Security advisory | **Approve with conditions** | 2026-07-22T19:12:39Z |

**Result:** **Authorized** for default-off implementation. Controlled-pilot activation (Motion 3) separately **Authorized** `2026-07-22T20:04:34Z` — see [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md).
