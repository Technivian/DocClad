# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — PR #62 **merged** (`4c08fb9c`); canonical authority **default off**; activation votes **Requested**; legacy retained; ADMIN reconciliation deferred; **GI-2026-07-22-PR58-PREAUTH-MERGE Ratified and Closed**  
**ADR:** ADR-0014 **Accepted**  
**PR #58 merge:** `598b7a12` (2026-07-22T14:42:13Z) — reviewed code HEAD `44926da9`  
**PR #62 merge:** `4c08fb9c98e934ece9b1ed00ae788055cccae6f0` (2026-07-22T15:59:25Z)  
**Baseline `main`:** `4c08fb9c`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Accepted ADR |
| [`0112-implementation-authorization.md`](0112-implementation-authorization.md) | Catalogue authorization |
| [`0113-process-role-adapter-implementation-authorization.md`](0113-process-role-adapter-implementation-authorization.md) | Adapter authorization |
| [`SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md`](SHADOW_ROLE_SYNC_IMPLEMENTATION_AUTHORIZATION.md) | Slice 3 implementation + merge authorization (recorded) |
| [`RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`](RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md) | Slice 4 implementation + merge authorization (**Authorized and merged**) |
| [`RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md`](RESOLVER_READINESS_REMEDIATION_AUTHORIZATION.md) | Remediation (**Authorized** 15:27–15:29Z) |
| [`CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md`](CANONICAL_RESOLVER_CUTOVER_AUTHORIZATION.md) | Default-off implementation (**Authorized**; activation not) |
| [`CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md`](CANONICAL_RESOLVER_ACTIVATION_AUTHORIZATION.md) | Staging/production enablement (**Requested**) |
| [`PR62_MERGE_AND_ACTIVATION_GATE.md`](PR62_MERGE_AND_ACTIVATION_GATE.md) | PR #62 merge SHA + activation blocked pending votes |
| [`../2026-07-22-par-id-001-pr58-merge/SUMMARY.md`](../2026-07-22-par-id-001-pr58-merge/SUMMARY.md) | PR #58 merge evidence |
| [`../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md`](../2026-07-22-par-id-001-pr58-merge/GOVERNANCE_INCIDENT_AND_RATIFICATION_ADDENDUM.md) | Pre-auth merge incident — **Ratified and Closed** |
| [`../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md`](../2026-07-22-par-id-001-pr58-merge/REMEDIATION_BACKLOG.md) | Remediation backlog (planning open; no staging request) |
| [`../2026-07-22-par-sec-003/CLOSURE.md`](../2026-07-22-par-sec-003/CLOSURE.md) | PAR-SEC-003 Closed |

---

## Staging + readiness

| Artifact | Purpose |
|---|---|
| [`STAGING_RESOLVER_PARITY_RESULTS.md`](STAGING_RESOLVER_PARITY_RESULTS.md) | Post-remediation READY |
| [`INACTIVE_ASSIGNMENT_REMEDIATION.md`](INACTIVE_ASSIGNMENT_REMEDIATION.md) | CERTAIN reactivation |
| [`RESOLVER_CUTOVER_THREAT_REVIEW.md`](RESOLVER_CUTOVER_THREAT_REVIEW.md) | Threat review |
| [`PROCESS_ROLE_MAPPING_MATRIX.md`](PROCESS_ROLE_MAPPING_MATRIX.md) | Mapping + ADMIN exclusion |
| [`ROLE_USAGE_MATRIX.md`](ROLE_USAGE_MATRIX.md) | Full inventory |
| [`RESOLVER_USAGE_MATRIX.md`](RESOLVER_USAGE_MATRIX.md) | Runtime resolver consumer inventory |
| [`CUTOVER_PLAN.md`](CUTOVER_PLAN.md) | Cutover plan (ADMIN exclusion noted) |

---

## Implementation evidence

| Artifact | Purpose |
|---|---|
| [`migrate-forward.txt`](migrate-forward.txt) / rollback / reforward | 0112 proof |
| [`migrate-0113-forward.txt`](migrate-0113-forward.txt) / rollback / reforward | 0113 proof |
| [`TEST_RESULTS.md`](TEST_RESULTS.md) | Test evidence |
| [`django-tests-canonical-authority.txt`](django-tests-canonical-authority.txt) | Authority + parity suite |
| [`django-tests-canonical-authority-broad.txt`](django-tests-canonical-authority-broad.txt) | Broad 239 OK |
| [`django-tests-post-merge-resolver-parity.txt`](django-tests-post-merge-resolver-parity.txt) | Post-merge #58 suite |
| [`../2026-07-22-pr52-merge/SUMMARY.md`](../2026-07-22-pr52-merge/SUMMARY.md) | PR #52 merge evidence |

---

## Scope boundary

- **Delivered on main (pre-#62):** Catalogue; org-scoped assignments; dual-read; shadow sync; resolver comparison (default-off)
- **Implemented on PR #62 (default off):** `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` + org allowlist; authority on approved paths only
- **Not activated:** flag remains false; allowlist empty by default until activation votes
- **Retained:** legacy resolvers; diagnostic parity flags independent
- **Deferred:** ADMIN reconciliation; production activation; PAR-APR-002; PAR-WF-010
- **Production authority (defaults):** Still uses legacy resolvers while flag is off
