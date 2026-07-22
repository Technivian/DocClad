# PAR-ID-001 remediation decision package — index

**Baseline `main`:** `8316a756` (pre-package)  
**Merged to `main`:** `06258d26` at `2026-07-22T18:44:14Z` (PR [#63](https://github.com/Technivian/CLMOne/pull/63))  
**R0 evidence tip:** `0404e284`  
**Status:** **In progress** — R0 **PASS**; R1 CERTAIN non-ADMIN remediation auth package **Requested**  
**Package vote status:** **Approved** — Product `18:33:34Z` / Engineering `18:35:34Z` / Security `18:34:34Z`  
**PR #63 merge authorization:** **Authorized and merged**  
**R0 authorization status:** **Authorized and executed** — exit **PASS**  
**R1 authorization status:** **Requested** — see [`R1_CERTAIN_REMEDIATION_AUTHORIZATION.md`](R1_CERTAIN_REMEDIATION_AUTHORIZATION.md)  

| Artifact | Purpose |
|---|---|
| [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md) | Locked review motion; recorded package + merge votes |
| [`REMEDIATION_ANALYSIS.md`](REMEDIATION_ANALYSIS.md) | REM-01 / REM-02 analysis (verified counts from R0) |
| [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) | REM-04 / REM-05 ADMIN policy (**P1+P3**; **P2 rejected**) |
| [`THREAT_REVIEW.md`](THREAT_REVIEW.md) | REM-06 threat review |
| [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md) | R0 inventory auth (**Authorized**) |
| [`R0_EXIT_REPORT.md`](R0_EXIT_REPORT.md) | R0 exit verdict + verified counts |
| [`r0_inventory_raw.json`](r0_inventory_raw.json) | Tenant-scoped row inventory + parity rows |
| [`R1_CERTAIN_REMEDIATION_AUTHORIZATION.md`](R1_CERTAIN_REMEDIATION_AUTHORIZATION.md) | R1 CERTAIN non-ADMIN remediation auth (**Requested**) |
| [`R1_MAPPING_MANIFEST.md`](R1_MAPPING_MANIFEST.md) | Deterministic CERTAIN mapping rules |
| [`R1_ROW_SCOPE.md`](R1_ROW_SCOPE.md) | Exact 12 in-scope rows; 8 ADMIN denied |
| [`R1_TEST_MATRIX_AND_ROLLBACK.md`](R1_TEST_MATRIX_AND_ROLLBACK.md) | Tests + rollback plan |

**Verified R0 counts (clean seed corpus, not production):** MISSING/INACTIVE **20**; LEGACY_ONLY orgs **4**; AMBIGUOUS ADMIN **8**.  
**R1 proposed scope:** **12** CERTAIN non-ADMIN creates only.

**Not authorized:** R1 apply (until votes); R2–R5; staging flag activation; dual-return; privilege/resolver cutover; automatic repair; ADMIN/AMBIGUOUS remediation.
