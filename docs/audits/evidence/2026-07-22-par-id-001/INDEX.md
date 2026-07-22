# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — catalogue `0112` + adapter `0113` + shadow sync on `main`; Slice 4 resolver-parity authorization **Reviewed — Pending Votes**; production authority still legacy  
**ADR:** ADR-0014 **Accepted**  
**PR #51 merge:** `21e65f09`  
**PR #53 merge:** `0bf7c9dc`  
**PR #54 merge:** `58966de7`  
**PR #52 merge:** `3c5e628b`  
**PR #55 merge:** `bb881ac2` (2026-07-22T13:35:32Z) — reviewed HEAD `432a55b1`  
**PR #57 merge (PR #52 evidence):** `2f14c034`  
**PR #59 merge (PR #55 merge evidence):** `0d9712ca`  
**Baseline `main`:** `0d9712ca`  
**Branch:** `cursor/feat-par-id-001-resolver-parity` (PR [#58](https://github.com/Technivian/CLMOne/pull/58))

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Accepted ADR |
| [`0112-implementation-authorization.md`](0112-implementation-authorization.md) | Catalogue authorization |
| [`0113-process-role-adapter-implementation-authorization.md`](0113-process-role-adapter-implementation-authorization.md) | Adapter authorization |
| [`SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md`](SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md) | Slice 3 implementation + merge authorization (recorded) |
| [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md) | Slice 4 resolver comparison authorization (**Reviewed — Pending Votes**) |
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
| [`RESOLVER_PARITY_TEST_MATRIX.md`](RESOLVER_PARITY_TEST_MATRIX.md) | Planned Slice 4 tests (implement after authorization) |
| [`CUTOVER_PLAN.md`](CUTOVER_PLAN.md) | Later cutover plan (not authorized) |

---

## Implementation evidence

| Artifact | Purpose |
|---|---|
| [`migrate-forward.txt`](migrate-forward.txt) / rollback / reforward | 0112 proof |
| [`migrate-0113-forward.txt`](migrate-0113-forward.txt) / rollback / reforward | 0113 proof |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test evidence |
| [`django-tests-slice3.txt`](django-tests-slice3.txt) | Slice 3 captured run |
| [`django-tests.txt`](django-tests.txt) | Prior adapter run |
| [`../2026-07-22-pr52-merge/SUMMARY.md`](../2026-07-22-pr52-merge/SUMMARY.md) | PR #52 merge evidence |

---

## Scope boundary

- **Delivered:** Additive catalogue; org-scoped assignment adapter; dual-read parity; feature-flagged shadow sync; parity command
- **Prepared (not implemented):** Resolver comparison authorization package + usage matrix + test matrix
- **Not delivered:** Resolver comparison wiring; production resolver flip; privilege cutover; `UserProfile.role` removal
- **Production authority:** Still uses legacy resolvers
