# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — resolver parity merged (`598b7a12`); remediation required before staging activation; flags default off; production authority still legacy; **GI-2026-07-22-PR58-PREAUTH-MERGE Ratified and Closed**  
**ADR:** ADR-0014 **Accepted**  
**PR #51 merge:** `21e65f09`  
**PR #53 merge:** `0bf7c9dc`  
**PR #54 merge:** `58966de7`  
**PR #52 merge:** `3c5e628b`  
**PR #55 merge:** `bb881ac2` (2026-07-22T13:35:32Z) — reviewed HEAD `432a55b1`  
**PR #57 merge (PR #52 evidence):** `2f14c034`  
**PR #59 merge (PR #55 merge evidence):** `0d9712ca`  
**PR #58 merge:** `598b7a12` (2026-07-22T14:42:13Z) — reviewed code HEAD `44926da9`  
**Baseline `main`:** `598b7a12`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Accepted ADR |
| [`0112-implementation-authorization.md`](0112-implementation-authorization.md) | Catalogue authorization |
| [`0113-process-role-adapter-implementation-authorization.md`](0113-process-role-adapter-implementation-authorization.md) | Adapter authorization |
| [`SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md`](SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md) | Slice 3 implementation + merge authorization (recorded) |
| [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md) | Slice 4 implementation + merge authorization (**Authorized and merged**) |
| [`../2026-07-22-par-id-001-pr58-merge/SUMMARY.md`](../2026-07-22-par-id-001-pr58-merge/SUMMARY.md) | PR #58 merge evidence |
| [`../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md) | Pre-auth merge incident — **Ratified and Closed** |
| [`../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md`](../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md) | Remediation backlog (planning open; no staging request) |
| [`../2026-07-22-par-id-001-pr58-merge/REMEDIATION_PLANNING.md`](../2026-07-22-par-id-001-pr58-merge/REMEDIATION_PLANNING.md) | Analysis/planning order for REM-01..06 |
| [`../2026-07-22-par-sec-003/CLOSURE.md`](../2026-07-22-par-sec-003/CLOSURE.md) | PAR-SEC-003 Closed |

---

## Discovery + mapping

| Artifact | Purpose |
|---|---|
| [`ROLE_USAGE_MATRIX.md`](ROLE_USAGE_MATRIX.md) | Full inventory |
| [`TARGET_ROLE_MODEL.md`](TARGET_ROLE_MODEL.md) | Five-concept target |
| [`PROCESS_ROLE_MAPPING_MATRIX.md`](PROCESS_ROLE_MAPPING_MATRIX.md) | Mapping rules |
| [`SHADOW_WRITE_PATH_MATRIX.md`](SHADOW_WRITE_PATH_MATRIX.md) | Legacy write → shadow eligibility |
| [`RESOLVER_USAGE_MATRIX.md`](RESOLVER_USAGE_MATRIX.md) | Runtime resolver consumer inventory |
| [`RESOLVER_PARITY_TEST_MATRIX.md`](RESOLVER_PARITY_TEST_MATRIX.md) | Slice 4 test matrix (implemented) |
| [`CUTOVER_PLAN.md`](CUTOVER_PLAN.md) | Later cutover plan (not authorized) |

---

## Implementation evidence

| Artifact | Purpose |
|---|---|
| [`migrate-forward.txt`](migrate-forward.txt) / rollback / reforward | 0112 proof |
| [`migrate-0113-forward.txt`](migrate-0113-forward.txt) / rollback / reforward | 0113 proof |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test evidence |
| [`django-tests-post-merge-resolver-parity.txt`](django-tests-post-merge-resolver-parity.txt) | Post-merge #58 suite |
| [`governance-authority-post-merge.txt`](governance-authority-post-merge.txt) | Post-merge governance check |
| [`django-tests-slice3.txt`](django-tests-slice3.txt) | Slice 3 captured run |
| [`django-tests.txt`](django-tests.txt) | Prior adapter run |
| [`../2026-07-22-pr52-merge/SUMMARY.md`](../2026-07-22-pr52-merge/SUMMARY.md) | PR #52 merge evidence |

---

## Scope boundary

- **Delivered on main:** Additive catalogue; org-scoped assignment adapter; dual-read parity; feature-flagged shadow sync; Slice 4 resolver comparison (default-off)
- **Not delivered:** Dual-return; production resolver flip; privilege cutover; staging flag activation; `UserProfile.role` removal
- **Production authority:** Still uses legacy resolvers
