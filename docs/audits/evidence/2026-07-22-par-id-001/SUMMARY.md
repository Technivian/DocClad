# PAR-ID-001 evidence summary — 2026-07-22

## Status: In progress — shadow sync merged to main (non-authoritative)

**ADR:** ADR-0014 **Accepted**  
**PR #53 merge:** `0bf7c9dc` (catalogue 0112)  
**PR #54 merge:** `58966de7` (process-role adapter 0113)  
**PR #55 merge:** `bb881ac2` (2026-07-22T13:35:32Z) — reviewed HEAD `432a55b1`  
**This slice:** feature-flagged shadow synchronization + parity evidence (no new migration)

### Delivered
- Additive `RoleDefinition` catalogue (0112)
- Org-scoped `ProcessRoleAssignment` model + governed service (0113)
- Dual-read parity / drift diagnostics (non-authoritative)
- Feature-flagged shadow sync from `UserProfile.role` → `ProcessRoleAssignment`
- Deterministic `process_role_parity_report` management command
- Shadow write-path inventory + Slice 3 implementation authorization + merge authorization

### Explicitly unchanged
- Permissions / authorization outcomes
- `OrganizationMembership.role` authority
- `UserProfile.role` behaviour (still authoritative)
- Approval / signer / workflow runtime resolution
- Navigation
- PAR-APR-002 / PAR-WF-010
- Flags remain **default off** on `main` (not enabled by merge)

### Programme record
- Canonical catalogue delivered
- Organization-scoped assignments delivered
- Dual-read diagnostics delivered
- Feature-flagged shadow synchronization delivered **and merged**
- Parity evidence available
- Production permissions and runtime resolvers remain legacy
- Resolver cutover / flag activation requires separate authorization

### Flags (default off on `main`)
- `PROCESS_ROLE_SHADOW_WRITE_ENABLED` = `default=False`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED` = `default=False`

### Next slice (not authorized)
Feature-flagged production resolver dual-read comparison (non-authoritative) — **new implementation authorization required**.
Stop before canonical output influences any production decision. No flag enablement without separate activation authorization.
