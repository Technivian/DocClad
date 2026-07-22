# PAR-ID-001 — Remediation analysis (decision package)

**Baseline `main`:** `8316a756`  
**Opened:** 2026-07-22T15:43:00Z  
**Mode:** Analysis / decision package only — **no** production code, seed, assignment, flag, or authority changes  
**Programme status:** **In progress** — remediation decision package pending  
**Incident:** GI-2026-07-22-PR58-PREAUTH-MERGE **Ratified and Closed**

Related:
- [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md)
- [`THREAT_REVIEW.md`](THREAT_REVIEW.md)
- [`../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md`](../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md)

---

## Inventory integrity notice

| Claim | Evidence status |
|---|---|
| Historical 14 inactive/missing | **Superseded** — was unverified programme target |
| Historical 1 LEGACY_ONLY org | **Superseded** |
| Historical 13 AMBIGUOUS ADMIN | **Superseded** |
| **R0 verified INACTIVE/MISSING** | **20** (`MISSING_CANONICAL_SETUP` 20 / `INACTIVE_HISTORY` 0) in clean seed corpus |
| **R0 verified LEGACY_ONLY orgs** | **4** (`demo-firm`, `clmone-demo`, `clmone-mvp`, `controlled-pilot-org`) |
| **R0 verified AMBIGUOUS ADMIN** | **8** |
| Environment | Clean staging-equivalent SQLite; migrate through **0113**; deterministic demo seeds; all `PROCESS_ROLE_*` flags **false** |

See [`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md) and [`r0_inventory_raw.json`](r0_inventory_raw.json). Verified counts are for this corpus only — **not** production facts.

---

## REM-01 — Inactive or missing assignments

### Method (proposed; not executed against production)

1. For each active `OrganizationMembership`, read `UserProfile.role`.  
2. Map via `resolve_legacy_process_role_code('profile_role', …)`.  
3. Look up `ProcessRoleAssignment` for `(org, user, mapped_code)`.  
4. Classify:
   - `MISSING_CANONICAL_SETUP` — no PRA row  
   - `INACTIVE_HISTORY` — only inactive PRA  
   - `MATCH_ACTIVE` — active PRA present  
5. Attach workflow/approval paths that consume the legacy role (`resolve_assignee` / `resolve_rule_assignee`).

### Root-cause taxonomy

| Class | Meaning | Typical cause | Proposed remediation (do **not** apply yet) |
|---|---|---|---|
| A — Migration gap | 0113 backfill not run / incomplete | Env never migrated or backfill skipped | Authorized one-time LEGACY_BACKFILL for CERTAIN mappings only |
| B — Shadow never enabled | Shadow flag default off; no PRA writes | Expected under current flags | Optional flag-gated shadow sync after staging auth |
| C — Seed gap | Seeds set `UserProfile.role` without PRA | Seed design (process labels only) | Seed update **only** under separate seed-change auth; or backfill |
| D — Expected inactive history | Prior deactivate left inactive row | Role change / membership leave | Leave inactive; create new active CERTAIN assignment if still needed |
| E — ADMIN / AMBIGUOUS hold | Mapped to `legacy_process_admin` | Policy intentionally AMBIGUOUS | Blocked on REM-04/05; do not auto-repair as CERTAIN |
| F — Missing membership | Profile role without active org membership | Orphan profile | Out of process-role scope; tenancy cleanup separate |

### Illustrative seed inventory (in-memory; disposable)

After `migrate` + `seed_data` / `seed_demo` / `seed_mvp_demo` / `seed_controlled_pilot` / `seed_payrollminds_demo` in an **in-memory** DB:

| Metric | Count |
|---|---|
| Active membership × profile-role rows | 20 |
| `MISSING_CANONICAL_SETUP` | **20** (PRA active=0, inactive=0) |
| `INACTIVE_HISTORY` | **0** |
| Profile ADMIN → AMBIGUOUS | **8** |

**Interpretation:** Under default-off shadow + no backfill execution in that disposable DB, **all** expected CERTAIN and AMBIGUOUS mappings appear as missing canonical setup — consistent with **migration/shadow/seed gap (classes A–C)**, not inactive history (D).

### Proposed REM-01 record template (for verified env)

| # | org_id | org_slug | user_id | username | profile_role | mapped_code | confidence | class | workflow/approval path | legacy result | proposed action |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1..N | … | … | … | … | … | … | CERTAIN/AMBIGUOUS | A–F | `resolve_assignee` / `resolve_rule_assignee` / none | User or None | create CERTAIN PRA / hold ADMIN / leave inactive |

**Gate:** Replace this template with a verified export before any implementation authorization. Target count may land at 14, or may differ — **do not force-fit**.

### Proposed remediation (not applied)

1. Run read-only verified inventory on a migrated staging/dev DB (separate activation if resolver flag needed for LEGACY_ONLY).  
2. For **CERTAIN** + `MISSING_CANONICAL_SETUP`: authorize a non-runtime backfill/shadow slice.  
3. For **INACTIVE_HISTORY**: document; reactivate only with explicit reason + authz.  
4. For **AMBIGUOUS ADMIN**: defer to REM-04/05 policy; no silent CERTAIN promotion.

---

## REM-02 — LEGACY_ONLY organization

### Definition

Resolver parity class `LEGACY_ONLY`: legacy resolver returns a user for a role label; canonical active `ProcessRoleAssignment` set for the mapped code is empty (and not merely inactive — else `INACTIVE_ASSIGNMENT`).

### Why canonical assignments are absent (structural)

| Hypothesis | Fit |
|---|---|
| Seed gap | **High** — seeds set profile roles; do not create PRA |
| Migration gap | **High** — 0113 backfill not applied / not re-run after seed |
| Configuration gap | **Medium** — approval rules / template steps reference `approver_role` / `assignee_role` without PRA |
| Intentional exception | **Low** unless Product documents an org as legacy-only forever |

### Illustrative candidates (in-memory seeds)

Orgs with role-based rules/steps whose legacy profile holders lack active PRA for mapped codes included `demo-firm` and `clmone-demo` (PARTNER / SENIOR_ASSOCIATE paths). Treat as **pattern evidence**, not the named “1 org” production target.

### Proposed remediation (not applied)

1. Identify the verified LEGACY_ONLY org via `process_role_resolver_parity_report` **only after** staging/diagnostic flag authorization (default remains off).  
2. If seed/migration gap: CERTAIN backfill for mapped roles used by rules/steps.  
3. If intentional exception: record EXC with owner/expiry; keep legacy authoritative.  
4. Do **not** change resolver return values.

---

## REM-03 — Ambiguous ADMIN mappings (preview; full reclass in ADMIN decision)

See [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) § reclassification.

Illustrative seed AMBIGUOUS ADMIN rows: **8** (usernames: `admin`, `demo_admin`, `mvp_admin`, `pilot_owner`, `pilot_admin`, `pilot_finance`, `payrollminds_admin`, `payrollminds_finance`).  
Programme target **13** remains unverified.

---

## Proposed remediation implementation slices (authorization required separately)

| Slice | Scope | Mutates data? | Flag? |
|---|---|---|---|
| **R0** | Verified read-only inventory command/export (no ensure-write side effects) | No | No |
| **R1** | CERTAIN missing PRA backfill (org allow-list) | Yes (PRA only) | Optional shadow |
| **R2** | Inactive-history triage report + optional reactivate | Yes if reactivate | No |
| **R3** | ADMIN policy wiring per accepted REM-04/05 | Mapping/confidence only or PRA rules | No runtime cutover |
| **R4** | LEGACY_ONLY org repair for CERTAIN roles | Yes (PRA) | Diagnostic flag for proof only |
| **R5** | Threat-review residual close-out evidence | Docs | No |

**None of R1–R5 are authorized by this decision package.** Staging activation remains a later gate after policy approval + authorized/verified implementation.

---

## Test matrix (for future implementation authorization)

| Case | Expectation |
|---|---|
| Inventory R0 flag-off | No PRA writes; deterministic JSON |
| CERTAIN missing → backfill (R1) | Active PRA created; legacy resolvers unchanged |
| ADMIN under retained AMBIGUOUS policy | Never auto-MATCH for cutover; never map to workspace ADMIN |
| ADMIN under “no automatic process role” | No PRA from profile ADMIN; resolver parity AMBIGUOUS/LEGACY_ONLY as designed |
| Inactive history | Not auto-reactivated |
| Resolver return with any remediation | Byte-identical to legacy when comparison flag off |
| Tenant isolation | No cross-org PRA |
| Rollback | Deactivate/delete system-managed LEGACY_BACKFILL/shadow rows only |

---

## Rollback plan (future slices)

| Layer | Action |
|---|---|
| Flags | Remain / return to default **false** |
| PRA backfill | Deactivate or delete `assignment_source` in `{LEGACY_BACKFILL, SHADOW}` per org allow-list |
| Mapping policy | Revert code/docs to prior Accepted mapping matrix via PR revert |
| Runtime | Legacy resolvers unchanged throughout |

---

## Staging activation prerequisites

Staging activation may be **requested** only when all are true:

1. Remediation **policy** approved (Product + Engineering + Security votes on this package).  
2. Required remediation **implementation** separately authorized, merged, and verified.  
3. Verified inventory replaces provisional 14/1/13 (or documents residuals).  
4. ADMIN policy (REM-04/05) accepted; REM-06 threat review accepted.  
5. Explicit staging activation authorization with real ISO-8601 timestamps.  

Until then: all `PROCESS_ROLE_*` flags remain default **false**.

---

## Vote blocks

See end of [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) (policy) and [`THREAT_REVIEW.md`](THREAT_REVIEW.md) (security). Combined package votes:

### Product — @haroonwahed

```text
PAR-ID-001 REMEDIATION DECISION PACKAGE — 2026-07-22
Baseline main: 8316a756

@haroonwahed Product: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Approves analysis + ADMIN policy option selected in ADMIN_ROLE_MAPPING_DECISION.md: <option id>
Confirms: no staging activation; no cutover; PAR-ID-001 remains In progress
```

### Engineering — @Technivian

```text
@Technivian Engineering: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Confirms slices R0–R5 require separate implementation authorization before any writes.
```

### Security advisory — @Technivian

```text
@Technivian Security advisory: Approve with conditions | Reject
Timestamp: <actual ISO-8601 UTC>

Threat review THREAT_REVIEW.md conditions acknowledged: yes | no
```
