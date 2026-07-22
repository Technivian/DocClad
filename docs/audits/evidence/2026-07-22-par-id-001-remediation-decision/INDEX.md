# PAR-ID-001 remediation decision package — index

**Baseline `main`:** `8316a756` (pre-package)  
**Merged to `main`:** `06258d26` at `2026-07-22T18:44:14Z` (PR [#63](https://github.com/Technivian/CLMOne/pull/63))  
**Merge reviewed HEAD:** `60263068`  
**Status:** **In progress** — remediation decision package **Approved and merged**; R0 inventory auth gate **opened** (votes Requested)  
**Package vote status:** **Approved** — Product `18:33:34Z` / Engineering `18:35:34Z` / Security `18:34:34Z` (conditions 1–6 acknowledged)  
**PR #63 merge authorization:** **Authorized and merged** — Engineering `18:37:34Z` / Product `18:38:34Z`  
**R0 authorization status:** **Gate opened / Not authorized** — Eng+Sec Approve recorded `18:53:20Z`; Product real timestamp still required  

| Artifact | Purpose |
|---|---|
| [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md) | Locked review motion; recorded package + merge votes |
| [`REMEDIATION_ANALYSIS.md`](REMEDIATION_ANALYSIS.md) | REM-01 / REM-02 analysis, slices, tests, rollback, staging prerequisites |
| [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) | REM-04 / REM-05 ADMIN policy (**P1+P3**; **P2 rejected**) |
| [`THREAT_REVIEW.md`](THREAT_REVIEW.md) | REM-06 threat review |
| [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md) | Separate inventory-only R0 auth (**gate opened; votes Requested**) |

**Package motion (Approved):** Approve P1+P3; reject P2; approve threat model + remediation architecture as planning; require separate R0 before data remediation.

**Not authorized:** R0 execution; R1–R5 writes; staging flag activation; dual-return; privilege/resolver cutover; automatic repair; production data mutation.
