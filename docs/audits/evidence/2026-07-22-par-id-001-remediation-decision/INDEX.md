# PAR-ID-001 remediation decision package — index

**Baseline `main`:** `8316a756`  
**Status:** **In progress** — remediation decision package pending votes (PR #63)  
**Branch:** `cursor/docs-par-id-001-remediation-decision-package`  
**Package vote status:** **Requested** — see [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md) (no Approve votes with real timestamps recorded yet; votes not invented)  
**PR #63 merge authorization:** **Requested / blocked** — separate from package approval  
**R0 authorization status:** **Not authorized** — blocked until package Approved + PR #63 merged + separate R0 votes  

| Artifact | Purpose |
|---|---|
| [`PACKAGE_REVIEW_AND_VOTE.md`](PACKAGE_REVIEW_AND_VOTE.md) | Locked review motion; Product/Engineering/Security vote blocks |
| [`REMEDIATION_ANALYSIS.md`](REMEDIATION_ANALYSIS.md) | REM-01 / REM-02 analysis, slices, tests, rollback, staging prerequisites |
| [`ADMIN_ROLE_MAPPING_DECISION.md`](ADMIN_ROLE_MAPPING_DECISION.md) | REM-04 / REM-05 ADMIN policy (motion: **P1+P3**; **P2 rejected**) |
| [`THREAT_REVIEW.md`](THREAT_REVIEW.md) | REM-06 threat review |
| [`R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md`](R0_INVENTORY_IMPLEMENTATION_AUTHORIZATION.md) | Separate inventory-only R0 auth (**Requested**) |

**Package motion (pending votes):** Approve P1+P3; reject P2; approve threat model + remediation architecture as planning; require separate R0 before data remediation.

**Not authorized by this package:** R0 execution; R1–R5 writes; staging flag activation; dual-return; privilege/resolver cutover; automatic repair; production data mutation.
