# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — catalogue `0112` + adapter `0113` + feature-flagged shadow sync on `main`; production authority still legacy  
**ADR:** ADR-0014 **Accepted**  
**PR #51 merge:** `21e65f09`  
**PR #53 merge:** `0bf7c9dc`  
**PR #54 merge:** `58966de7`  
**PR #55 merge:** `bb881ac2` (2026-07-22T13:35:32Z) — reviewed HEAD `432a55b1`  
**Branch:** `main` @ `bb881ac2`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Accepted ADR |
| [`0112-implementation-authorization.md`](0112-implementation-authorization.md) | Catalogue authorization |
| [`0113-process-role-adapter-implementation-authorization.md`](0113-process-role-adapter-implementation-authorization.md) | Adapter authorization |
| [`SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md`](SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md) | Slice 3 implementation + merge authorization (recorded) |
| [`../2026-07-22-par-sec-003/CLOSURE.md`](../2026-07-22-par-sec-003/CLOSURE.md) | PAR-SEC-003 Closed |

---

## Discovery + mapping

| Artifact | Purpose |
|---|---|
| [`ROLE_USAGE_MATRIX.md`](ROLE_USAGE_MATRIX.md) | Full inventory |
| [`TARGET_ROLE_MODEL.md`](TARGET_ROLE_MODEL.md) | Five-concept target |
| [`PROCESS_ROLE_MAPPING_MATRIX.md`](PROCESS_ROLE_MAPPING_MATRIX.md) | Mapping rules |
| [`SHADOW_WRITE_PATH_MATRIX.md`](SHADOW_WRITE_PATH_MATRIX.md) | Legacy write → shadow eligibility |
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

---

## Scope boundary

- **Delivered:** Additive catalogue; org-scoped assignment adapter; dual-read parity; feature-flagged shadow sync; parity command
- **Not delivered:** Production resolver flip; privilege cutover; `UserProfile.role` removal
- **Production authority:** Still uses legacy resolvers
