# Implementation authorization — PAR-ID-001 Slice R0 verified inventory (only)

**Programme:** PAR-ID-001  
**Prerequisite:** Remediation decision package (PR #63) **Approved** (Product `18:33:34Z` / Engineering `18:35:34Z` / Security `18:34:34Z`)  
**Additional prerequisite:** PR #63 **merged** — **met** @ `06258d26` / `2026-07-22T18:44:14Z` (merge reviewed HEAD `60263068`; Eng `18:37:34Z` / Product `18:38:34Z`)  
**Baseline `main` at package:** `8316a756`  
**Package-approved reviewed HEAD:** `8390769d`  
**Merge reviewed HEAD:** `60263068`  
**Status:** **Authorized** — Product `18:55:17Z` / Engineering `18:53:20Z` / Security `18:53:20Z`  
**Depends on:** [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md)

---

## Motion — Authorize inventory-only R0

**Text:** Authorize a **read/setup inventory** slice that applies required migrations in a **clean staging-equivalent environment**, runs deterministic seed/setup as needed for that environment, generates tenant-scoped row-level inventory, records stable identifiers and assignment provenance, reruns parity reports, replaces unverified programme target counts with verified counts, and updates the remediation decision package — **without** auto-repair, flag enablement, resolver-authority change, privilege grants, staging activation, or canonical cutover.

| Approver | Vote | Consent |
|---|---|---|
| @haroonwahed Product | **Approve** | `2026-07-22T18:55:17Z` — inventory-only; no repair/flags/cutover |
| @Technivian Engineering | **Approve** | `2026-07-22T18:53:20Z` — conditions acknowledged: yes; inventory-only: yes; no data repair or runtime authority change: yes |
| @Technivian Security advisory | **Approve with conditions** | `2026-07-22T18:53:20Z` — conditions acknowledged: yes; binding conditions 1–8 below |

**R0 authorization status:** **Authorized** (inventory-only). Does **not** authorize R1–R5 writes, flag enablement, staging activation, or cutover.

### Recorded votes (verbatim)

```text
@haroonwahed Product: Approve
Timestamp: 2026-07-22T18:55:17Z

@Technivian Engineering: Approve
Timestamp: 2026-07-22T18:53:20Z
Conditions acknowledged: yes
R0 remains inventory-only: yes
No data repair or runtime authority change: yes

@Technivian Security advisory: Approve with conditions
Timestamp: 2026-07-22T18:53:20Z
Conditions acknowledged: yes

Binding conditions:
1. Inventory must be tenant-scoped.
2. Evidence must use permission-safe identifiers and metadata.
3. No automatic repair or assignment mutation.
4. No feature flags may be enabled.
5. No privileges or process authority may be granted.
6. CROSS_TENANT_ANOMALY or unexpected DIFFERENT_USER findings require escalation.
7. R0 results must distinguish verified facts from historical programme targets.
8. Staging activation and canonical cutover remain separately gated.
```

### Binding Security conditions (verbatim — acknowledged)

1. Inventory must be tenant-scoped.  
2. Evidence must use permission-safe identifiers and metadata.  
3. No automatic repair or assignment mutation.  
4. No feature flags may be enabled.  
5. No privileges or process authority may be granted.  
6. CROSS_TENANT_ANOMALY or unexpected DIFFERENT_USER findings require escalation.  
7. R0 results must distinguish verified facts from historical programme targets.  
8. Staging activation and canonical cutover remain separately gated.

---

## Allowed (authorized)

1. Apply required migrations (including 0113) in a **clean staging-equivalent** environment (not silent mutation of unreviewed production DBs).  
2. Run deterministic seed/setup **in that environment only** if required for inventory reproducibility.  
3. Generate tenant-scoped row-level inventory (INACTIVE / MISSING / LEGACY_ONLY / AMBIGUOUS ADMIN).  
4. Record stable identifiers and assignment provenance.  
5. Rerun assignment / resolver parity reports as diagnostics (flags remain default **false**).  
6. Replace programme target counts (14 / 1 / 13) with **verified** counts.  
7. Update the remediation decision package docs with verified evidence.

---

## Forbidden

| Item | Authorized |
|---|---|
| Auto-repair of assignments | **No** |
| Enable `PROCESS_ROLE_*` feature flags | **No** |
| Alter resolver authority / return values | **No** |
| Grant privileges / permission changes | **No** |
| Staging activation (as a product gate) | **No** |
| Canonical cutover / dual-return | **No** |
| Membership-authority or navigation changes | **No** |
| Beginning R1–R5 remediation writes | **No** |

---

## Verified-inventory requirements (R0 exit criteria)

| Requirement | Done when |
|---|---|
| Environment | Clean staging-equivalent with 0113 applied |
| Scope | Tenant-scoped; permission-safe fields only |
| REM-01 | Row list of inactive vs missing with root-cause class |
| REM-02 | Named LEGACY_ONLY org(s) + resolver path evidence |
| REM-03 | AMBIGUOUS ADMIN row list under P1+P3 policy |
| Provenance | Stable ids + assignment_source / confidence where present |
| Counts | Verified totals replace 14/1/13 (or document residual delta) |
| Package update | Decision package evidence files updated; no false “complete” status |

See [`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md) after execution.
