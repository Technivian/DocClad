# PAR-ID-001 evidence summary — 2026-07-22

## Status: In progress — shadow sync on main; resolver comparison pending authorization

**ADR:** ADR-0014 **Accepted**  
**PR #53 merge:** `0bf7c9dc` (catalogue 0112)  
**PR #54 merge:** `58966de7` (process-role adapter 0113)  
**PR #55 merge:** `bb881ac2` (feature-flagged shadow sync + parity)  
**PR #52 / #57:** visual remediation + merge evidence on main

### Delivered
- Additive `RoleDefinition` catalogue (0112)
- Org-scoped `ProcessRoleAssignment` model + governed service (0113)
- Dual-read parity / drift diagnostics (non-authoritative)
- Feature-flagged shadow sync from `UserProfile.role` → `ProcessRoleAssignment`
- Deterministic `process_role_parity_report` management command
- Shadow write-path inventory + Slice 3 authorization (Product / Engineering / Security)

### Prepared (not implemented — Reviewed, Pending Votes)
- `RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md` — scope + binding Security conditions locked; Product/Engineering/Security votes **Requested**
- `RESOLVER_USAGE_MATRIX.md` (parity-candidate: `resolve_assignee`, `resolve_rule_assignee` chains)

### Explicitly unchanged
- Permissions / authorization outcomes
- `OrganizationMembership.role` authority
- `UserProfile.role` behaviour (still authoritative)
- Approval / signer / workflow runtime resolution return values
- Navigation
- PAR-APR-002 / PAR-WF-010

### Programme record
- Canonical catalogue delivered
- Organization-scoped assignments delivered
- Dual-read diagnostics delivered
- Feature-flagged shadow synchronization delivered
- Parity evidence available
- Resolver comparison **not** delivered (authorization pending)
- Production permissions and runtime resolvers remain legacy
- Privilege cutover requires separate authorization

### Flags on main (default off)
- `PROCESS_ROLE_SHADOW_WRITE_ENABLED`
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED`
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` — **not added** until resolver parity authorization is recorded

### Next slice gate
Record verbatim Product, Engineering, and Security votes on `RESOLVER_PARITY_IMPLEMENTATION_AUTHORIZATION.md`, then implement comparison mode that always returns the legacy result.
Stop before canonical resolver output affects any production decision.
