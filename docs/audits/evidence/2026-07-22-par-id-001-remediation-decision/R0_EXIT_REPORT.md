# PAR-ID-001 R0 exit report — verified inventory

**Authorized:** Product `2026-07-22T18:55:17Z` / Engineering `2026-07-22T18:53:20Z` / Security `2026-07-22T18:53:20Z`  
**Executed:** 2026-07-22T18:56:00Z (approx) on `main` @ `6279713c`+  
**Mode:** Inventory and evidence only — **no** repair, flag enablement, privilege grant, resolver-authority change, staging activation, or cutover  
**Raw inventory:** [`r0_inventory_raw.json`](r0_inventory_raw.json)

---

## Environment and migration evidence

| Item | Result |
|---|---|
| Environment | Clean disposable SQLite staging-equivalent (`r0_staging_env/db.sqlite3`, not committed) |
| Settings | `config.settings_development` + empty/`false` `PROCESS_ROLE_*` env |
| Migrations | Full migrate through **0112** and **0113** applied |
| `contracts_processroleassignment` | **Present** |
| Deterministic seeds | `seed_data`, `seed_demo`, `seed_mvp_demo`, `seed_controlled_pilot`, `seed_payrollminds_demo` |
| `PROCESS_ROLE_SHADOW_WRITE_ENABLED` | **false** |
| `PROCESS_ROLE_PARITY_REPORTING_ENABLED` | **false** |
| `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` | **false** |
| `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` | **false** |

Resolver parity classifications used the same `_classify` / `_canonical_users_for_role` helpers offline so diagnostics could run **without** enabling runtime flags.

---

## Historical programme targets vs verified facts

| Claim | Historical (unverified) | **Verified (R0)** |
|---|---|---|
| INACTIVE / MISSING | 14 | **20** (`MISSING_CANONICAL_SETUP` 20 + `INACTIVE_HISTORY` 0) |
| LEGACY_ONLY orgs | 1 | **4** org slugs (`demo-firm`, `clmone-demo`, `clmone-mvp`, `controlled-pilot-org`); **89** LEGACY_ONLY resolver comparisons |
| AMBIGUOUS ADMIN | 13 | **8** profile-ADMIN membership rows |

**Binding:** Historical 14/1/13 are **superseded** as programme planning assumptions. Verified R0 counts above are authoritative for this clean seed corpus. They are **not** production facts.

---

## Verified row inventory (REM-01)

| inventory_class | Count |
|---|---|
| `MISSING_CANONICAL_SETUP` | 20 |
| `INACTIVE_HISTORY` | 0 |
| `MATCH_ACTIVE` | 0 |

Root-cause: all 20 missing rows are **A/B/C** (migration backfill not run / shadow default off / seed sets profile without PRA). ADMIN-mapped rows also carry **E** (`E_ADMIN_AMBIGUOUS_HOLD`).

Full tenant-scoped rows (permission-safe ids + provenance): see `r0_inventory_raw.json` → `rem01_rows`.

---

## REM-02 — LEGACY_ONLY

| Metric | Verified |
|---|---|
| Orgs with ≥1 LEGACY_ONLY resolver comparison | `demo-firm`, `clmone-demo`, `clmone-mvp`, `controlled-pilot-org` |
| LEGACY_ONLY comparisons | 89 |
| Paths | `resolve_rule_assignee`, `resolve_assignee` |

---

## REM-03 — AMBIGUOUS ADMIN (P1+P3)

| username | org_slug | profile_role | mapped_code |
|---|---|---|---|
| admin | demo-firm | ADMIN | legacy_process_admin |
| demo_admin | clmone-demo | ADMIN | legacy_process_admin |
| mvp_admin | clmone-mvp | ADMIN | legacy_process_admin |
| pilot_owner | controlled-pilot-org | ADMIN | legacy_process_admin |
| pilot_admin | controlled-pilot-org | ADMIN | legacy_process_admin |
| pilot_finance | controlled-pilot-org | ADMIN | legacy_process_admin |
| payrollminds_admin | payrollminds-demo | ADMIN | legacy_process_admin |
| payrollminds_finance | payrollminds-demo | ADMIN | legacy_process_admin |

**Policy:** `legacy_process_admin` remains AMBIGUOUS diagnostic only; no automatic process authority for workspace ADMIN; P2 rejected.

---

## Verified parity counts

### Assignment parity (`process_role_parity_report` logic; flag off)

| Drift | Count |
|---|---|
| Rows | 20 |
| `legacy_without_canonical` | 20 |
| `ambiguous_mapping` | 8 |
| Critical drift rows (per CRITICAL_DRIFT set) | 20 |

Expected under no backfill / shadow off.

### Resolver parity (offline classifiers; runtime flag off)

| Classification | Count |
|---|---|
| Total comparisons | 94 |
| LEGACY_ONLY | 89 |
| AMBIGUOUS | 5 |
| MATCH | 0 |
| INACTIVE_ASSIGNMENT | 0 |
| CROSS_TENANT_ANOMALY | **0** |
| DIFFERENT_USER | **0** |
| RESOLUTION_ERROR | **0** |

---

## Security findings

| Condition | Result |
|---|---|
| Tenant-scoped inventory | **Met** |
| Permission-safe identifiers | **Met** (ids, usernames, org slugs, role codes; no secrets) |
| No automatic repair | **Met** |
| Flags remain false | **Met** |
| No privilege / authority grant | **Met** |
| CROSS_TENANT_ANOMALY / unexpected DIFFERENT_USER | **0 / 0** — no escalation |
| Verified vs historical distinction | **Met** (table above) |
| Staging activation / cutover | **Not performed** |

---

## R0 exit verdict

**PASS — inventory complete.**

R0 exit criteria met for the authorized clean staging-equivalent seed corpus. PAR-ID-001 remains **In progress**. No R1+ writes performed.

---

## Proposed R1–R5 remediation scope (not authorized)

| Slice | Scope (proposal only) |
|---|---|
| **R1** | CERTAIN-only LEGACY_BACKFILL / governed create for `MISSING_CANONICAL_SETUP` non-ADMIN rows (separate auth) |
| **R2** | Document + optionally remediate LEGACY_ONLY resolver paths per org after R1 |
| **R3** | ADMIN AMBIGUOUS hold under P1+P3 — explicit CERTAIN process-role assignments where Product requires coverage (no P2 auto-map) |
| **R4** | Optional shadow-sync staging enablement (separate activation auth) after R1–R3 evidence |
| **R5** | Canonical resolver activation / cutover (separate gates; still blocked) |

---

## Next authorization gate

**R1 CERTAIN missing-assignment remediation** (implementation authorization) — Product + Engineering + Security; inventory-only R0 does **not** authorize R1.
