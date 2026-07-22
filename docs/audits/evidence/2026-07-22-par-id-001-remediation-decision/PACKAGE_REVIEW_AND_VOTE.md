# PAR-ID-001 remediation decision package — review motion and votes (PR #63)

**PR:** [#63](https://github.com/Technivian/CLMOne/pull/63)  
**Baseline `main`:** `8316a756`  
**Package path:** `docs/audits/evidence/2026-07-22-par-id-001-remediation-decision/`  
**Package-approved reviewed HEAD:** `8390769d28d4e96599072861d950dc2e4ec8b5e2`  
**Package approval recorded:** 2026-07-22T18:36:00Z  
**Package type:** Policy and planning only — **no** production code, seed, assignment, flag, or authority changes in this PR  
**Package approval ≠ merge authorization:** Package Approve votes do **not** authorize merging PR #63; see § Merge authorization (separate).

---

## Inventory limitation (binding for this review)

| Programme target | Status |
|---|---|
| 14 INACTIVE/MISSING | **Unverified** — not committed row-level inventory |
| 1 LEGACY_ONLY | **Unverified** |
| 13 AMBIGUOUS ADMIN | **Unverified** |
| Local DB migration 0113 | **Not applied** on local `db.sqlite3` |
| In-memory seed result | **Pattern evidence only** |

Verified counts require a separate **R0** implementation authorization (below). This package does **not** authorize R0.

---

## Review disposition

| Decision requested | Review finding |
|---|---|
| Approve **P1 labels + P3 authority** | **Accepted as the package motion** — retain `legacy_process_admin` as AMBIGUOUS diagnostic label; do not automatically grant process authority to workspace ADMIN; require explicit CERTAIN process-role assignments |
| Reject **P2** | **Accepted as binding exclusion** — no automatic ADMIN→CERTAIN process-role mapping |
| Approve threat model + remediation architecture | **Accepted as the package motion** — `THREAT_REVIEW.md` T1–T10 + slices R0–R5 as planning architecture |
| Separate R0 before any data remediation | **Accepted as binding gate** — R0 auth is **Requested**, not granted by package approval alone |

---

## Motion — Approve policy package (not R0, not staging)

**Text:** Approve the PAR-ID-001 remediation decision package as policy/planning only: ADMIN posture **P1+P3**; **P2 rejected**; threat review and remediation architecture accepted; programme targets 14/1/13 remain unverified until R0; **no** staging activation, flag enablement, auto-repair, privilege grant, resolver-authority change, or canonical cutover.

| Approver | GitHub identity | Capacity | Vote | Consent |
|---|---|---|---|---|
| Haroon Wahed | @haroonwahed | Product | **Approve** | `2026-07-22T18:33:34Z` — Reviewed HEAD `8390769d`; P1+P3; P2 rejected; package ≠ merge auth |
| Technivian | @Technivian | Engineering | **Approve** | `2026-07-22T18:35:34Z` |
| Security & privacy (advisory) | @Technivian | Security | **Approve with conditions** | `2026-07-22T18:34:34Z` — Conditions 1–6 acknowledged: yes |

**Package vote status:** **Approved** (policy/planning only). Does **not** authorize PR #63 merge, R0 execution, flag enablement, or cutover.

### Recorded package votes (verbatim)

```text
@haroonwahed Product: Approve
Timestamp: 2026-07-22T18:33:34Z
Reviewed HEAD: 8390769d
# P1+P3; P2 rejected; package ≠ merge auth

@Technivian Engineering: Approve
Timestamp: 2026-07-22T18:35:34Z

@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-22T18:34:34Z
Conditions 1–6 acknowledged: yes
```

---

## Approved ADMIN policy (binding)

**Exactly:**

1. **P1 labels + P3 authority**  
2. Retain `legacy_process_admin` as an **AMBIGUOUS** diagnostic label  
3. No automatic process authority for workspace ADMIN (or via profile ADMIN auto-map)  
4. Explicit **CERTAIN** process-role assignments required for process coverage  
5. **P2** automatic ADMIN→process-role mapping **rejected**

---

## Binding Security conditions (verbatim — acknowledged)

1. Never merge workspace ADMIN with process ADMIN.  
2. No automatic privilege grant via `legacy_process_admin`.  
3. AMBIGUOUS retained in diagnostics until explicit CERTAIN assignment.  
4. Threat review T1–T10 acknowledged; residual legacy ADMIN first-match (T5) accepted only until separate cutover authorization.  
5. No staging activation, dual-return, privilege cutover, or auto-repair by this package vote.  
6. R0 (if later authorized) must remain inventory-only: no assignment repair, no flag enablement, no resolver-authority change.

---

## CI state

| HEAD | Status |
|---|---|
| `8390769d` (package-approved reviewed HEAD) | All 6 required checks **SUCCESS**; merge state CLEAN |
| Tip after this vote-record commit | Must be CI-green (or content-identical) before merge |

Required checks: Forbidden-brand scan · Anti-drift + contrast · pr-release-evidence · security-scans · verify-ui · quality-and-tenancy — all SUCCESS.

---

## Merge authorization (PR #63) — separate from package approval

**Status:** **Authorized and merged**

| Approver | Vote | Timestamp |
|---|---|---|
| @Technivian Engineering | **Approve merge** | `2026-07-22T18:37:34Z` |
| @haroonwahed Product | **Approve merge** | `2026-07-22T18:38:34Z` |

**Merge reviewed HEAD:** `60263068` (`602630684dc423dc58dbc093c4ac965584b10fab`) — CI 6/6 SUCCESS  
**Merge commit on `main`:** `06258d26` (`06258d265471d5e1b4b4baea1ed85cc427e534ed`)  
**Merged at:** `2026-07-22T18:44:14Z`

### Recorded merge votes (verbatim)

```text
PR #63 MERGE AUTHORIZATION — 2026-07-22

PR: #63
Reviewed HEAD: 60263068

@haroonwahed Product: Approve merge
Timestamp: 2026-07-22T18:38:34Z

@Technivian Engineering: Approve merge
Timestamp: 2026-07-22T18:37:34Z

Merge authorization confirms:
- The policy package is Approved
- P1 labels + P3 authority remains binding
- legacy_process_admin remains AMBIGUOUS diagnostic only
- workspace ADMIN receives no automatic process authority
- explicit CERTAIN process-role assignments are required
- P2 remains rejected
- Security conditions 1–6 remain binding
- This is a documentation and governance merge only
- No R0 execution is authorized
- No flag activation, repair, privilege grant, resolver authority, staging activation, or cutover is authorized
```

---

## R0 authorization status

**Gate opened (votes Requested).** PR #63 is merged. R0 execution remains **Not authorized** until separate Product / Engineering / Security votes are recorded in [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md).

R0 allow/deny unchanged: inventory-only in clean staging-equivalent env; apply 0113; deterministic setup; tenant-scoped inventory + provenance; parity rerun; replace 14/1/13; **no** repair, flags, privileges, resolver-authority change, staging activation, or cutover.

---

## Gate sequence (binding)

1. Record package votes (Product / Engineering / Security) — **done; package Approved**.  
2. Separate Product + Engineering **Approve merge** for PR #63 — **done**.  
3. Merge PR #63 (docs-only) — **done** @ `06258d26` / `2026-07-22T18:44:14Z`.  
4. Open R0 inventory authorization gate — **opened**; execute only after separate R0 votes.  
5. R1+ and staging/canonical activation remain later gates.

## Next authorized action

**Await R0 inventory implementation authorization votes** (Product / Engineering / Security).  
Do **not** execute R0 without them. Do **not** enable flags. Do **not** repair assignments or start cutover.  
PAR-ID-001 remains **In progress**.
