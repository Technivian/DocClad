# PAR-ID-001 evidence summary — 2026-07-22

## Status: In progress — resolver parity merged; remediation required before staging activation

**ADR:** ADR-0014 **Accepted**  
**PR #53 merge:** `0bf7c9dc` (catalogue 0112)  
**PR #54 merge:** `58966de7` (process-role adapter 0113)  
**PR #55 merge:** `bb881ac2` (2026-07-22T13:35:32Z) — reviewed HEAD `432a55b1`  
**PR #58 merge:** `598b7a12` (2026-07-22T14:42:13Z) — reviewed code HEAD `44926da9`  
**Merge votes recorded:** Product `15:06:30Z` / Engineering `15:06:45Z` (**after** merge)  
**Retrospective ratification:** Product `15:31:46Z` / Engineering `15:31:55Z` — **GI-2026-07-22-PR58-PREAUTH-MERGE Ratified and Closed**  
**Merge evidence:** `docs/audits/evidence/2026-07-22-par-id-001-pr58-merge/`  
**PR #52 / #57 / #59:** prior merge evidence on main

### Delivered
- Additive `RoleDefinition` catalogue (0112)
- Org-scoped `ProcessRoleAssignment` model + governed service (0113)
- Dual-read parity / drift diagnostics (non-authoritative)
- Feature-flagged shadow sync from `UserProfile.role` → `ProcessRoleAssignment`
- Deterministic `process_role_parity_report` management command
- Shadow write-path inventory + Slice 3 implementation/merge authorization
- Resolver usage matrix + resolver-parity authorization (Product `14:17:31Z` / Engineering `14:18:31Z` / Security `14:15:31Z`)
- Feature-flagged resolver comparison **merged** (`PROCESS_ROLE_RESOLVER_PARITY_ENABLED`, default off)
- `process_role_resolver_parity_report` management command
- Merge authorization Product `15:06:30Z` / Engineering `15:06:45Z` (staging activation **not** authorized; `14:34:37Z` staging claim superseded)

### Explicitly unchanged
- Permissions / authorization outcomes
- `OrganizationMembership.role` authority
- `UserProfile.role` behaviour (still authoritative)
- Approval / signer / workflow runtime resolution return values (legacy always returned)
- Navigation
- PAR-APR-002 / PAR-WF-010
- Flags remain **default off** (not enabled by merge)

### Programme record
- Canonical catalogue delivered
- Organization-scoped assignments delivered
- Dual-read diagnostics delivered
- Feature-flagged shadow synchronization delivered **and merged**
- Resolver comparison delivered **and merged** behind default-off flag (legacy authoritative)
- Production permissions and runtime resolvers remain legacy
- Dual-return / privilege cutover requires separate authorization
- Staging flag activation requires separate authorization

### Flags (default off on `main`)
- `PROCESS_ROLE_SHADOW_WRITE_ENABLED` = false
- `PROCESS_ROLE_PARITY_REPORTING_ENABLED` = false
- `PROCESS_ROLE_RESOLVER_PARITY_ENABLED` = false

### Next decision gate
1. Complete remediation planning/analysis for REM-01..REM-06 (no flag enablement; no auto-repair).  
2. Product + Security ADMIN policy acceptance (REM-04 / REM-05) + threat review (REM-06).  
3. **Then** separate staging activation authorization (not opened).  
Stop before canonical resolver output affects any production decision. PAR-ID-001 remains **In progress**.
