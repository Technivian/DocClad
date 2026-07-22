# PAR-ID-001 evidence summary — 2026-07-22

## Status: In progress — additive catalogue delivered

**Programme:** Role Definition reconciliation (Milestone 3)  
**ADR:** ADR-0014 **Accepted** 2026-07-22T11:00:00Z  
**PR #51 merge:** `21e65f09`  
**Authorized slice:** migration `0112_role_definition_registry`

### Delivered
- Discovery pack (ROLE_USAGE_MATRIX, TARGET_ROLE_MODEL, CUTOVER_PLAN)
- ADR-0014 Accepted with named approvers
- PAR-SEC-003 Closed
- Additive `RoleDefinition` model + service + migration 0112
- Compatibility lookup (no privilege dual-write)
- Ambiguous `UserProfile.ADMIN` → `legacy_process_admin` (LEGACY_UNKNOWN)

### Explicitly unchanged
- Permissions / authorization outcomes
- Runtime assignee resolution
- Navigation access
- `OrganizationMembership` / `UserProfile.role` behaviour

### Not Completed
PAR-ID-001 remains **In progress** until runtime role assignment and compatibility cutover criteria are delivered under separate authorization.

### Next authorized slice (proposed)
Org-scoped process-role dual-read adapter — **not authorized** in this package.
