# Controlled-pilot dual-write evidence — PAR-EXC-001

**Status:** **Prepared / not activated**  
**Org allowlist (proposed):** `controlled-pilot-org`  
**Flags:** `EXCEPTION_DUAL_WRITE_ENABLED=false` (default); allowlist empty by default

## Activation gate

Do **not** enable flags until:

1. ADR-0015 Motion 1 Accepted (genuine votes);
2. Motion 2 dual-write authorization Accepted;
3. Dual-write PR merged;
4. Separate activation note with Product + Engineering (+ Security) consent.

## Counts template (fill after activation)

| Metric | Count |
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
| Dual-write failures | 0 |
| Security gate blocks | 0 |
| Expired exceptions recorded | 0 |
| Cross-tenant anomalies | 0 |
| Missing owners / expiry | 0 |
| User-visible regressions | 0 |

## Required result (acceptance)

- no cross-tenant anomaly
- no unauthorized Critical bypass
- no lost legacy action
- no duplicate canonical decisions
- every approved exception has owner and expiry
- every decision is immutable

## Parity note

Legacy remains authoritative. When canonical expiry is reached while legacy still applies, record under parity evidence — do not silently extend canonical applicability.
