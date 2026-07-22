# Controlled-pilot dual-write — PAR-EXC-001 activation package

**Status:** **Authorization Requested** (not activated)  
**Package type:** Separate activation authorization (Motion 3)  
**Does not invent votes.** Do not enable flags until Product + Engineering + Security record genuine activation votes.

| Field | Value |
|---|---|
| Proposed org allowlist | `controlled-pilot-org` **only** |
| Paths in scope | Six Motion-2 paths only (below) |
| Authority model | **Legacy remains authoritative** |
| Flags (current) | `EXCEPTION_DUAL_WRITE_ENABLED=false`; `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=` (empty) |
| Prerequisites met | ADR-0015 **Accepted**; Motion 2 dual-write **Authorized** (default-off); PR #66 merged (`982b0900`); PR #69 dual-write merged (`f19eae42`) |
| **Not** authorized by this package alone | Canonical read authority; legacy retirement; automatic repair; historical invention; any org beyond allowlist |

## Six approved source paths only

| Path key | Legacy surface |
|---|---|
| `KEEP_EXCEPTION` | Drafting workspace keep-exception |
| `ACCEPTED_RISK` | DPA risk item accepted risk |
| `AI_EXCEPTION` | AI finding exception (**SUBMITTED** only until authorized decision) |
| `CONFLICT_CHECK_WAIVER` | Conflict check waived |
| `DEADLINE_DEFER` | Deadline deferral |
| `DPA_APPROVE_WITH_BLOCKERS` | DPA approve-with-blockers (Critical requires Security approval) |

## Activation gate (all required)

1. ADR-0015 Motion 1 **Accepted** — **met** (`2026-07-22T19:12:39Z`).
2. Motion 2 default-off six-path dual-write **Authorized** — **met**.
3. Dual-write PR #69 **merged** to `main` (`f19eae42`) — **met** (supersedes stacked #67).
4. **Separate** Product + Engineering + Security activation votes recorded on this package (Motion 3).
5. Allowlist set to `controlled-pilot-org` only; global enable without allowlist **prohibited**.

## Exact activation vote required (Motion 3)

Record verbatim votes — do **not** invent:

```
ACTIVATE — PAR-EXC-001 Controlled-Pilot Dual-Write

Approver: @<handle>
Capacity: Product governance | Engineering governance | Security advisory
Timestamp: <ISO-8601 UTC>

Motion 3:
Authorize controlled-pilot dual-write activation for:
- org allowlist: controlled-pilot-org only;
- six approved source paths only (KEEP_EXCEPTION, ACCEPTED_RISK, AI_EXCEPTION,
  CONFLICT_CHECK_WAIVER, DEADLINE_DEFER, DPA_APPROVE_WITH_BLOCKERS);
- legacy-authoritative dual-write;
- monitoring and rollback plan in this package;
- stop conditions binding.

Vote: Approve | Approve with conditions | Reject

Binding conditions (minimum):
- flags enabled only with EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=controlled-pilot-org;
- legacy behavior remains authoritative;
- no canonical read cutover;
- no automatic repair;
- no historical invention;
- Security conditions from ADR-0015 remain binding;
- stop on any listed stop condition.
```

**Required capacities:** Product governance, Engineering governance, and Security advisory (Security vote required given Critical-control / fail-closed conditions).

## Monitoring

| Metric | Count (post-activation) |
|---|---:|
| Actions per KEEP_EXCEPTION | 0 |
| Actions per ACCEPTED_RISK | 0 |
| Actions per AI_EXCEPTION | 0 |
| Actions per CONFLICT_CHECK_WAIVER | 0 |
| Actions per DEADLINE_DEFER | 0 |
| Actions per DPA_APPROVE_WITH_BLOCKERS | 0 |
| Canonical requests created | 0 |
| Canonical decisions created | 0 |
| Duplicate prevention hits | 0 |
| Dual-write failures (`exception.dual_write_failed`) | 0 |
| Security gate blocks | 0 |
| Expired exceptions recorded | 0 |
| Cross-tenant anomalies | 0 |
| Missing owners / expiry | 0 |
| User-visible regressions | 0 |

## Required stop conditions (immediate disable)

Disable `EXCEPTION_DUAL_WRITE_ENABLED` (and clear allowlist) on **any** of:

1. any cross-tenant anomaly;
2. any unauthorized Critical bypass;
3. duplicate canonical decision;
4. missing owner or expiry on an approved/active exception;
5. lost legacy action (legacy write failed or rolled back while dual-write proceeded incorrectly);
6. user-visible regression attributable to dual-write.

## Rollback

1. Set `EXCEPTION_DUAL_WRITE_ENABLED=false` and clear `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST`.
2. Leave canonical rows in place (no automatic repair / deletion).
3. Legacy paths continue as sole authority.
4. Capture audit evidence of the stop event; do not invent remediation decisions.

## Parity note

Legacy remains authoritative. When canonical expiry is reached while legacy still applies, record under parity evidence — do not silently extend canonical applicability.

## Remaining residual paths (not in this pilot)

Inventoried; **not** activated here:

- Platform break-glass (`EXC-SEC` / `EXC-ADM` / `EXC-REP`) — Security review before any dual-write.
- Signature-provider paths (`EXC-SIG-*`) — non-user / operational; not product Exception dual-write without separate authorization.
- Other matrix residuals (policy/workflow/repair) — separate packages after pilot evidence.

## Activation status

| Item | Status |
|---|---|
| Package prepared | **Yes** |
| Votes | **Requested** (none recorded) |
| Flags enabled | **No** |
| Canonical read authority | **Unauthorized** |
