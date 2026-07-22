# PAR-EXC-001 — Controlled-pilot dual-write activation results

**Programme:** PAR-EXC-001  
**Authorization:** Motion 3 **Authorized** `2026-07-22T20:04:34Z` — [`CONTROLLED_PILOT_DUAL_WRITE.md`](CONTROLLED_PILOT_DUAL_WRITE.md)  
**Authorization merge:** PR [#74](https://github.com/Technivian/CLMOne/pull/74) @ `058c5ed0`  
**Environment:** `par-exc-001-controlled-pilot-activation` (`activation_env/`; SQLite gitignored)  
**Deployed revision:** `058c5ed0` (contains PR #66 foundation, PR #69 dual-write, PR #74 Motion 3 auth)  
**Verdict:** **PASS**  
**Machine evidence:** [`activation_results.json`](activation_results.json)

---

## Scope

| Item | Value |
|---|---|
| Org allowlist | `controlled-pilot-org` **only** |
| Paths | Six authorized sources only |
| Authority | **Legacy remains authoritative** |
| Committed defaults | **Unchanged** (`EXCEPTION_DUAL_WRITE_ENABLED=false`; empty allowlist) |
| Operational flags (env only) | `EXCEPTION_DUAL_WRITE_ENABLED=true`; `EXCEPTION_DUAL_WRITE_ORG_ALLOWLIST=controlled-pilot-org` |

**Explicitly not activated:** canonical read cutover; automatic repair; historical invention; legacy retirement; break-glass; signature-provider paths; PAR-APR-002 / PAR-WF-010 / PAR-ID-002.

---

## Preflight

| Check | Result |
|---|---|
| Revision contains PR #66 / #69 / #74 | **Pass** (`058c5ed0`) |
| Exactly one org with slug `controlled-pilot-org` | **Pass** (count=1) |
| No other org allowlisted | **Pass** (`demo-firm` present for negatives; not allowlisted) |
| Migrations `0114` and `0115` applied | **Pass** |
| Flag resolves true; allowlist exact | **Pass** |
| Legacy remains authoritative | **Pass** |

---

## Six-path results

| Path | Legacy | Canonical request | Decision | Owner present | Expiry present | Correlation ID | Idempotency | User-visible |
|---|---|---|---|---|---|---|---|---|
| `KEEP_EXCEPTION` | mirrored keep | Yes (ACTIVE) | APPROVED | Yes | Yes | `KEEP_EXCEPTION:RiskSignal:9001:kept` | hit | legacy unchanged |
| `ACCEPTED_RISK` | mirrored accept | Yes (ACTIVE) | APPROVED | Yes | Yes | `ACCEPTED_RISK:DPARiskItem:9002:accepted` | — | legacy unchanged |
| `AI_EXCEPTION` | mirrored request | Yes (SUBMITTED) | **None** (submitted-only) | Yes | Yes | `AI_EXCEPTION:ContractReviewFinding:9003:requested` | — | legacy unchanged |
| `CONFLICT_CHECK_WAIVER` | status → WAIVED | Yes (ACTIVE) | APPROVED | Yes | Yes | `CONFLICT_CHECK_WAIVER:ConflictCheck:2:waived` | — | legacy unchanged |
| `DEADLINE_DEFER` | due +7 days (HTTP 302) | Yes (ACTIVE) | APPROVED | Yes | Yes | deadline correlation | — | legacy unchanged |
| `DPA_APPROVE_WITH_BLOCKERS` | mirrored approve-with-blockers (Security approval true) | Yes (ACTIVE) | APPROVED | Yes | Yes | `DPA_APPROVE_WITH_BLOCKERS:DPAReviewPack:9006:PENDING->APPROVED` | — | legacy unchanged |

Evidence omits contract content, credentials, and restricted identity data.

---

## Monitoring (activation package counters)

| Metric | Count |
|---|---:|
| Actions per KEEP_EXCEPTION | 1 |
| Actions per ACCEPTED_RISK | 1 |
| Actions per AI_EXCEPTION | 1 |
| Actions per CONFLICT_CHECK_WAIVER | 1 |
| Actions per DEADLINE_DEFER | 1 |
| Actions per DPA_APPROVE_WITH_BLOCKERS | 1 |
| Canonical requests created | 6 |
| Canonical decisions created | 5 |
| Duplicate-prevention hits | 1 |
| Dual-write failures | 0 |
| Security gate blocks | 0 |
| Expired exceptions | 0 |
| Cross-tenant anomalies | 0 |
| Missing owners or expiry | 0 |
| User-visible regressions | 0 |

---

## Binding negative checks

| Check | Result |
|---|---|
| Non-allowlisted org does not dual-write | **Pass** |
| Cross-tenant attempt fails closed | **Pass** |
| Critical bypass without Security approval fails closed | **Pass** |
| Duplicate correlation ID does not create duplicate request/decision | **Pass** |
| Missing owner fails closed | **Pass** |
| Malformed privilege token fails closed | **Pass** |
| Disabling the flag restores legacy-only behavior | **Pass** (see rollback) |

---

## Rollback drill

1. Set `EXCEPTION_DUAL_WRITE_ENABLED=false` and clear allowlist (env override).
2. Deadline defer still succeeded (HTTP 302; due date +7).
3. No new canonical rows created while flags off.
4. Existing canonical rows were **not** deleted or auto-repaired.
5. Stop conditions remained clear → restored authorized env config (`ENABLED=true`, allowlist=`controlled-pilot-org`).

Committed defaults in `config/settings_base.py` / `settings_test.py` remain **off**.

---

## Stop conditions

All listed stop conditions **clear** (no disable-and-leave-off required).

---

## Next (derived from evidence)

- Controlled-pilot dual-write activation evidence: **PASS**
- Keep PAR-EXC-001 **In progress**
- Legacy remains authoritative; canonical read remains **unauthorized**
- Monitor pilot dual-write in `controlled-pilot-org` only; honour stop conditions
- Do **not** start PAR-APR-002 / PAR-WF-010 / PAR-ID-002 from this slice
