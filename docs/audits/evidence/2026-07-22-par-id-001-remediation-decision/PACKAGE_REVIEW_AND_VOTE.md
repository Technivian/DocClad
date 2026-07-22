# PAR-ID-001 remediation decision package — review motion and votes (PR #63)

**PR:** [#63](https://github.com/Technivian/CLMOne/pull/63)  
**Baseline `main`:** `8316a756`  
**Package path:** `docs/audits/evidence/2026-07-22-par-id-001-remediation-decision/`  
**Reviewed HEAD:** `4a8b1aa9be08ed45e6ad72420d50b26d3e52fb5e`  
**Review timestamp:** 2026-07-22T15:56:14Z  
**Vote-gate processing timestamp:** 2026-07-22T16:01:57Z  
**CI on reviewed HEAD:** see § CI state (must be green before merge auth)  
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
| Haroon Wahed | @haroonwahed | Product | **Requested** | Pending real ISO-8601 UTC timestamp |
| Technivian | @Technivian | Engineering | **Requested** | Pending real ISO-8601 UTC timestamp |
| Security & privacy (advisory) | @Technivian | Security | **Requested (advisory, with binding conditions)** | Pending real ISO-8601 UTC timestamp + conditions acknowledged |

**Package vote status:** **Not authorized** until all three votes are recorded verbatim.

---

## Approved ADMIN policy (motion — effective only when package votes recorded)

**Exactly:**

1. **P1 labels + P3 authority**  
2. Retain `legacy_process_admin` as an **AMBIGUOUS** diagnostic label  
3. No automatic process authority for workspace ADMIN (or via profile ADMIN auto-map)  
4. Explicit **CERTAIN** process-role assignments required for process coverage  
5. **P2** automatic ADMIN→process-role mapping **rejected**

---

## Binding Security conditions (verbatim — must be acknowledged in Security vote)

1. Never merge workspace ADMIN with process ADMIN.  
2. No automatic privilege grant via `legacy_process_admin`.  
3. AMBIGUOUS retained in diagnostics until explicit CERTAIN assignment.  
4. Threat review T1–T10 acknowledged; residual legacy ADMIN first-match (T5) accepted only until separate cutover authorization.  
5. No staging activation, dual-return, privilege cutover, or auto-repair by this package vote.  
6. R0 (if later authorized) must remain inventory-only: no assignment repair, no flag enablement, no resolver-authority change.

---

## Explicit package vote blocks (paste verbatim; do not invent)

### Product — @haroonwahed

```text
PAR-ID-001 REMEDIATION DECISION PACKAGE (PR #63) — 2026-07-22
Baseline main: 8316a756
Reviewed HEAD: 4a8b1aa9

@haroonwahed Product: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Approved:
- P1 labels + P3 authority
- retain legacy_process_admin as AMBIGUOUS diagnostic label
- no automatic process authority for workspace ADMIN
- explicit CERTAIN process-role assignments required
- P2 automatic ADMIN mapping rejected
- Threat model + remediation architecture (planning)
- Separate R0 authorization required before data remediation

Confirms:
- 14/1/13 remain unverified until R0
- No staging activation
- No cutover / flag enablement / auto-repair
- Package approval is not PR merge authorization
- PAR-ID-001 remains In progress
```

### Engineering — @Technivian

```text
@Technivian Engineering: Approve | Reject
Timestamp: <actual ISO-8601 UTC>

Engineering confirms:
- Package is docs/policy only
- Motion is exactly P1+P3; P2 rejected
- R0–R5 each need separate implementation authorization
- R0 is inventory-only when authorized
- Package approval is not PR #63 merge authorization
```

### Security advisory — @Technivian

```text
@Technivian Security advisory: Approve with conditions | Reject
Timestamp: <actual ISO-8601 UTC>

Binding Security conditions (verbatim):
1. Never merge workspace ADMIN with process ADMIN.
2. No automatic privilege grant via legacy_process_admin.
3. AMBIGUOUS retained in diagnostics until explicit CERTAIN assignment.
4. Threat review T1–T10 acknowledged; residual legacy ADMIN first-match (T5) accepted only until separate cutover authorization.
5. No staging activation, dual-return, privilege cutover, or auto-repair by this package vote.
6. R0 (if later authorized) must remain inventory-only: no assignment repair, no flag enablement, no resolver-authority change.

Conditions acknowledged: yes | no
P1+P3 / P2 rejected acknowledged: yes | no
No staging activation by this vote: yes | no
Package approval is not PR merge authorization: yes | no
```

---

## CI state (reviewed HEAD `4a8b1aa9`)

Recorded at vote-gate processing; refresh before merge:

| Check | Required |
|---|---|
| Forbidden-brand scan | SUCCESS |
| Anti-drift + contrast | SUCCESS |
| pr-release-evidence | SUCCESS |
| security-scans | SUCCESS |
| verify-ui | SUCCESS |
| quality-and-tenancy | SUCCESS |

Merge only if HEAD remains `4a8b1aa9` or content-identical **and** all required checks SUCCESS.

---

## Merge authorization (PR #63) — separate from package approval

**Status:** **Requested** — blocked until (a) package votes recorded Approve, (b) CI green on reviewed HEAD, (c) Product + Engineering **Approve merge** votes below.

Package approval does **not** authorize merge.

### Merge vote blocks

```text
PR #63 MERGE AUTHORIZATION — 2026-07-22

PR: #63
Reviewed HEAD: 4a8b1aa9
Package: docs/audits/evidence/2026-07-22-par-id-001-remediation-decision/

@haroonwahed Product: Approve merge | Reject merge
Timestamp: <actual ISO-8601 UTC>

Merge authorization confirms:
- Policy package Product/Engineering/Security votes recorded Approve
- Motion remains P1+P3; P2 rejected
- Docs-only PR; no code/flag/data mutation
- Does not authorize R0 execution
- Does not authorize staging activation or cutover
```

```text
@Technivian Engineering: Approve merge | Reject merge
Timestamp: <actual ISO-8601 UTC>
```

---

## R0 authorization status

**Not authorized.** Blocked until:

1. Policy package **Approved** (three votes), and  
2. PR #63 **merged** under separate merge authorization, and  
3. Separate R0 votes recorded in [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md).

R0 allow/deny unchanged: inventory-only in clean staging-equivalent env; apply 0113; deterministic setup; tenant-scoped inventory + provenance; parity rerun; replace 14/1/13; **no** repair, flags, privileges, resolver-authority change, staging activation, or cutover.

---

## Gate sequence (binding)

1. Record package votes (Product / Engineering / Security) — **current step; votes not yet received with real timestamps**.  
2. Separate Product + Engineering **Approve merge** for PR #63.  
3. Merge PR #63 (docs-only) when CI green.  
4. Open/execute R0 only after separate R0 authorization.  
5. R1+ and staging activation remain later gates.

## Next authorized action

**Await and record** verbatim package Approve votes with real ISO-8601 UTC timestamps.  
Do **not** merge PR #63. Do **not** start R0. Do **not** enable flags.
