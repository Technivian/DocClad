# PAR-ID-001 evidence summary — 2026-07-22

## Status: In progress

**Programme:** Role Definition reconciliation (Milestone 3)  
**ADR:** ADR-0014 **Proposed** — not Accepted  
**Authorized by:** ADR-0013 governance meeting Motion 5 (2026-07-22T09:45:00Z)

### Problem
Dual role systems conflict with canonical Role Definition (CANONICAL_DOMAIN_MODEL §2.5):

- `OrganizationMembership.Role` — workspace/org permission (`OWNER`, `ADMIN`, `MEMBER`)
- `UserProfile.Role` — process/professional role (`PARTNER`, `ASSOCIATE`, `PARALEGAL`, etc.)

Gap audit flags as **Conflicting / High**. Pilot seeds intentionally set both.

### Discovery deliverables (this slice)
- Proposed ADR-0014 with terminology separation and mapping proposal
- Current role usage matrix (`CURRENT_ROLE_MATRIX.md`)
- Characterization tests (`tests/test_par_id_001_characterization.py`) — lock interim semantics

### Explicit non-goals
- No schema changes
- No privilege model changes
- No enum removal
- No SCIM / RBAC redesign

### Next steps
1. UX copy audit (My Work, Approvals, Admin labels)
2. Authz matrix inventory across views/services
3. Mapping table design for ADR acceptance vote
4. Permission matrix tests before any implementation

### Dependencies
- PAR-APR-001 closed (complete)
- Tranche-1 on `main` (complete)
- ADR-0014 acceptance required before implementation
