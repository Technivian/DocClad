# ADR-0014: Role Definition reconciliation

- Status: **Proposed**
- Date: 2026-07-22
- Deciders: Engineering / Product (proposed by PAR-ID-001 discovery)
- Related: PAR-ID-001, CANONICAL_DOMAIN_MODEL §2.5, SECURITY_PRIVACY_ACCESS_AND_AUDIT, PAR-APR-001

## Context

Accepted domain documentation defines **Role Definition** as a canonical process responsibility (requester, contract owner, legal reviewer, finance approver, signer, etc.) distinct from **workspace permissions**.

CLM One currently maintains **two role systems**:

| System | Model | Values | Primary use |
|---|---|---|---|
| **Workspace / org membership** | `OrganizationMembership.Role` | `OWNER`, `ADMIN`, `MEMBER` | Tenant admin, billing, org-wide configuration |
| **Process / professional role** | `UserProfile.Role` | `PARTNER`, `SENIOR_ASSOCIATE`, `ASSOCIATE`, `PARALEGAL`, `LEGAL_ASSISTANT`, `ADMIN`, `CLIENT` | Workflow assignees, approval routes, task routing |

These overlap in naming (`ADMIN` exists in both) but serve different purposes. Pilot seeds intentionally set both (e.g. `OrganizationMembership.Role.MEMBER` + `UserProfile.Role.ASSOCIATE`). Gap audit G-DOM flags this as **Conflicting / High**.

PAR-ID-001 discovery (`docs/audits/evidence/2026-07-22-par-id-001/`) documents current usage without changing runtime behaviour.

## Decision (proposed — not Accepted)

### 1. Terminology separation (target)

| Concept | Canonical name | Storage (interim) |
|---|---|---|
| Workspace permission | **Organization role** | `OrganizationMembership.role` |
| Process responsibility | **Role Definition** | `UserProfile.role` (transitional) |

UI and documentation must not conflate the two. Labels in My Work, Approvals, and Admin should identify which layer applies.

### 2. Mapping table (additive; no destructive drop initially)

Introduce a governed mapping registry (configuration or model) that documents:

- which `UserProfile.Role` values qualify for which process Role Definitions;
- which `OrganizationMembership.Role` values gate configuration vs execution surfaces;
- explicit **non-mapping** where values must not imply privilege escalation.

No mapping row may grant server-side permissions not already enforced by existing authz checks.

### 3. Server-side authority unchanged until Accepted

- `OrganizationMembership.Role` continues to gate org admin surfaces (`OWNER`/`ADMIN`).
- `UserProfile.Role` continues to gate workflow assignee matching and approval route resolution.
- **No privilege widening** during discovery or dual-read period.

### 4. Pilot seed compatibility

Seeds (`seed_controlled_pilot`, `seed_demo`, `seed_payrollminds_demo`, etc.) may continue setting both role layers until cutover. Any backfill must preserve least privilege.

### 5. Explicit non-goals (this ADR slice)

- SCIM / external IdP role sync redesign
- Fine-grained permission matrix (RBAC overhaul)
- Removal of `UserProfile.Role` or `OrganizationMembership.Role`
- Client portal role model changes

## Alternatives considered

1. **Collapse to single role enum** — rejected; conflates workspace admin with process responsibilities.
2. **Rename only (no mapping)** — insufficient; does not resolve `ADMIN` ambiguity or audit requirements.
3. **Immediate removal of `UserProfile.Role`** — rejected; breaks workflow assignee matching and seeds.

## Consequences

- Characterization tests lock interim dual-role semantics (`tests/test_par_id_001_characterization.py`).
- Future migration may add mapping table; no schema change authorized until this ADR is Accepted.
- UX copy audit required before marking PAR-ID-001 complete.

## Approval

**Proposed only.** Acceptance required before mapping implementation, backfill, or role enum changes.
