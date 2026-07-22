# PAR-ID-001 evidence index

**Programme ID:** PAR-ID-001  
**Status:** **In progress** — discovery complete; ADR-0014 Accepted; additive catalogue `0112` delivered  
**ADR:** ADR-0014 **Accepted**  
**Branch:** `cursor/feat-par-id-001-role-definition-registry-d7f1`  
**PR #51 merge:** `21e65f09`

---

## Governance

| Artifact | Purpose |
|---|---|
| [`../../../governance/decisions/adr/0014-role-definition-reconciliation.md`](../../../governance/decisions/adr/0014-role-definition-reconciliation.md) | Accepted ADR |
| [`../../../governance/decisions/adr/0014-governance-acceptance-meeting-record-2026-07-22.md`](../../../governance/decisions/adr/0014-governance-acceptance-meeting-record-2026-07-22.md) | Ratification votes |
| [`../../../governance/decisions/adr/0014-governance-decision-package-2026-07-22.md`](../../../governance/decisions/adr/0014-governance-decision-package-2026-07-22.md) | Decision package |
| [`0112-implementation-authorization.md`](0112-implementation-authorization.md) | Narrow authorization for migration 0112 |
| [`../2026-07-22-par-sec-003/CLOSURE.md`](../2026-07-22-par-sec-003/CLOSURE.md) | PAR-SEC-003 Closed |

---

## Discovery evidence

| Artifact | Purpose |
|---|---|
| [`SUMMARY.md`](SUMMARY.md) | Programme summary |
| [`CURRENT_ROLE_MATRIX.md`](CURRENT_ROLE_MATRIX.md) | Dual-role overview (initial) |
| [`ROLE_USAGE_MATRIX.md`](ROLE_USAGE_MATRIX.md) | Full role-like concept inventory |
| [`TARGET_ROLE_MODEL.md`](TARGET_ROLE_MODEL.md) | Five-concept target model |
| [`CUTOVER_PLAN.md`](CUTOVER_PLAN.md) | Full cutover plan (later slices not authorized) |
| [`CHARACTERIZATION_TESTS.md`](CHARACTERIZATION_TESTS.md) | Test inventory |

---

## Implementation evidence (0112)

| Artifact | Purpose |
|---|---|
| [`migrate-forward.txt`](migrate-forward.txt) | Migration 0112 forward |
| [`migrate-rollback.txt`](migrate-rollback.txt) | Rollback to 0111 |
| [`migrate-reforward.txt`](migrate-reforward.txt) | Re-forward to 0112 |
| [`django-tests.txt`](django-tests.txt) | Test evidence |

---

## Scope boundary

- **Complete:** Discovery; ADR-0014 Accepted; PAR-SEC-003 Closed; additive `RoleDefinition` catalogue
- **Not complete:** Runtime role assignment cutover; privilege changes; `UserProfile.role` removal
- **Next authorized slice:** Requires new implementation authorization (org-scoped dual-read / resolver compatibility)
