# PAR-ID-001 remediation decision package — index

**Baseline `main`:** `8316a756` (pre-package)  
**Merged to `main`:** `06258d26` at `2026-07-22T18:44:14Z` (PR [#63](https://github.com/Technivian/CLMOne/pull/63))  
**Status:** **In progress** — package **Approved and merged**; R0 inventory **Authorized and complete** (PASS); R1+ not authorized  
**Package vote status:** **Approved** — Product `18:33:34Z` / Engineering `18:35:34Z` / Security `18:34:34Z`  
**PR #63 merge authorization:** **Authorized and merged** — Engineering `18:37:34Z` / Product `18:38:34Z`  
**R0 authorization status:** **Authorized and executed** — Product `18:55:17Z` / Eng+Sec `18:53:20Z`; exit **PASS** — see [`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md)  

| Artifact | Purpose |
|---|---|
| [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md) | Locked review motion; recorded package + merge votes |
| [`REMEDIATION_ANALYSIS.md`](REMEDIATION_ANALYSIS.md) | REM-01 / REM-02 analysis (verified counts from R0) |
| [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) | REM-04 / REM-05 ADMIN policy (**P1+P3**; **P2 rejected**) |
| [`THREAT_REVIEW.md`](THREAT_REVIEW.md) | REM-06 threat review |
| [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md) | R0 inventory auth (**Authorized**) |
| [`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md) | R0 exit verdict + verified counts |
| [`r0_inventory_raw.json`](r0_inventory_raw.json) | Tenant-scoped row inventory + parity rows |

**Verified R0 counts (clean seed corpus, not production):** MISSING/INACTIVE **20**; LEGACY_ONLY orgs **4**; AMBIGUOUS ADMIN **8**. Historical 14/1/13 superseded.

**Not authorized:** R1–R5 writes; staging flag activation; dual-return; privilege/resolver cutover; automatic repair.
