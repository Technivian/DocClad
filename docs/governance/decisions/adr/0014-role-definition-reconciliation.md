# ADR-0014: Role Definition reconciliation

- Status: **Accepted**
- Date: 2026-07-22
- Effective date: **2026-07-22**
- Deciders: @haroonwahed (Product governance) · @Technivian (Engineering governance)
- Related: PAR-ID-001, CANONICAL_DOMAIN_MODEL §2.5, SECURITY_PRIVACY_ACCESS_AND_AUDIT, WORKFLOW_ENGINE_AND_DESIGNER, PAR-APR-001
- Decision package: [`0014-governance-decision-package-2026-07-22.md`](0014-governance-decision-package-2026-07-22.md)
- Meeting record: [`0014-governance-acceptance-meeting-record-2026-07-22.md`](0014-governance-acceptance-meeting-record-2026-07-22.md)
- Evidence: `docs/audits/evidence/2026-07-22-par-id-001/`

## Approval metadata

| Field | Value |
|---|---|
| **Submitted for ratification** | 2026-07-22 |
| **Ratified** | 2026-07-22T11:00:00Z |
| **Product governance** | **Approve** — @haroonwahed |
| **Engineering governance** | **Approve** — @Technivian |
| **Security & privacy (advisory)** | **Approve with conditions** — @Technivian (security review capacity) |
| **Authority basis** | `.github/CODEOWNERS` (repository stewards for `/docs/`, `/contracts/`); `GOVERNANCE_CHARTER.md` v2.0; PDR-0003 |
| **Written consent** | Recorded in meeting record §1 |
| **Acceptance scope** | Target model, terminology, mapping registry design, compatibility period, and additive catalogue planning. **Does not authorize** permission changes, resolver cutover, membership-role migration, privilege changes, `UserProfile.role` removal, or workflow assignment cutover. |
| **Evidence** | `docs/audits/evidence/2026-07-22-par-id-001/` |

## Problem

Accepted domain documentation defines **Role Definition** (CANONICAL_DOMAIN_MODEL §2.5) as a canonical process responsibility — requester, contract owner, legal reviewer, finance approver, privacy reviewer, signer, archiver — **distinct from workspace permissions**.

CLM One maintains **two incompatible role systems**:

| System | Storage | Scope | Primary use |
|---|---|---|---|
| Workspace permission | `OrganizationMembership.role` | Org-scoped | Admin, configuration, elevated edit |
| Process role (interim) | `UserProfile.role` | **User-global** | Workflow assignee matching, approval rules |

**Conflicts identified (PAR-ID-001 discovery):**

- **C-ID-01:** `ADMIN` exists in both enums with different semantics.
- **C-ID-02:** `UserProfile.role` is user-global; membership is org-scoped — multi-org users ambiguous.
- **C-ID-03:** `ApprovalRoute.role_label` is display-only; `ApprovalRule` is runtime authority — easily conflated.
- **C-ID-04:** SCIM provisions workspace role only; profile role not provisioned.

Gap audit G-DOM rates this **Conflicting / High**. Pilot seeds intentionally set both layers; removal without mapping breaks workflow routing.

## Terminology (canonical)

| Term | Meaning | Interim / additive storage |
|---|---|---|
| **Workspace Role** | Organization membership permission | `OrganizationMembership.role` |
| **Permission Set** | Concrete server-evaluated capabilities | `permissions.py` (implicit today) |
| **Workflow Role Definition** | Stable process responsibility label | `RoleDefinition` catalogue (additive) + transitional `UserProfile.role` on templates/rules |
| **Runtime Role Assignment** | User/resolver bound to instance | `assigned_to`, `owner`, `reviewer`, `signer_email` |
| **Delegation** | Temporary acting authority | `delegated_to`, canonical approval delegation fields |

UI and documentation must label which layer applies. **UI visibility is not authorization.**

## Decision

### 1. Five-concept separation

Adopt the target model in `TARGET_ROLE_MODEL.md`:

1. Workspace Role — org admin authority
2. Permission Set — server-side capability evaluation
3. Workflow Role Definition — configuration-time process labels
4. Runtime Role Assignment — execution-time user/resolver binding
5. Delegation — governed temporary authority

### 2. Additive RoleDefinition catalogue (authorized separately)

Introduce org-scoped `RoleDefinition` rows with stable immutable `code`, category, active lifecycle, and system-managed protection. Labels **do not grant permissions**.

### 3. Mapping registry (additive)

Document every legacy value → canonical Definition or explicit `LEGACY_UNKNOWN`.

- **`UserProfile.ADMIN` maps to `legacy_process_admin` (LEGACY_UNKNOWN)** — never to Workspace ADMIN.
- No mapping row may grant permissions not already enforced today.

### 4. Compatibility period

- Dual-read / lookup for catalogue labels without dual-writing privilege state.
- Runtime resolvers, membership authority, and navigation remain unchanged until a later implementation authorization.
- Pilot seeds continue dual-set until a future backfill is authorized.

### 5. Server-side authority unchanged until cutover authorization

Until a separate implementation authorization for resolver/privilege cutover:

- `OrganizationMembership.Role` gates org admin surfaces.
- `UserProfile.Role` gates workflow/approval matching.
- **No privilege widening.**

### 6. Explicit non-goals

- SCIM / IdP process role sync redesign
- Django Group / `has_perm` adoption
- Client portal role overhaul
- Removal of legacy enums before dual-read verification
- Permission, resolver, or assignment cutover without separate authorization

## Alternatives considered

| Alternative | Outcome |
|---|---|
| **Collapse to single role enum** | **Rejected** — conflates workspace admin with process responsibilities; violates §2.5 |
| **Rename only (no mapping table)** | **Rejected** — insufficient for `ADMIN` ambiguity, audit, backfill |
| **Immediate `UserProfile.role` removal** | **Rejected** — breaks resolvers, seeds, pilot |
| **Django Groups RBAC** | **Deferred** — large scope; Permission Set may remain custom functions initially |
| **Keep status quo indefinitely** | **Rejected** — gap audit High; multi-org and SCIM gaps worsen |

## Authorization implications

| Area | Implication |
|---|---|
| Contract EDIT | Remains: admin OR owner/creator — not profile role |
| Approval decisions | Remains: `authorize_approval_actor` |
| Configuration nav | Remains: `can_manage_organization` |
| Workflow assignee | Unchanged until separate authorization |
| API tokens | Unchanged |
| Background jobs | System actor explicit |

**Acceptance does not authorize changing these rules** — only the target model, terminology, and additive catalogue architecture.

## Migration strategy

See `CUTOVER_PLAN.md` and `0112-implementation-authorization.md`. First authorized slice: migration `0112_role_definition_registry` (catalogue only).

## Compatibility period

- Catalogue lookup available without changing privilege state.
- Minimum one release cycle before any single-write resolver cutover.
- Further slices require separate implementation authorization.

## Consequences

- Characterization and catalogue tests lock interim + additive semantics.
- UX copy audit still required before PAR-ID-001 Completion.
- PAR-ID-001 remains **In progress** until runtime assignment and compatibility cutover criteria are delivered under separate authorization.

## Rollback approach

Reverse migration `0112` removes catalogue rows. Feature flag for future canonical-read cutover remains reserved. Legacy write paths untouched by this ADR acceptance.

## Tenant-isolation requirements

- All catalogue rows org-scoped; cross-tenant management denied.
- Programme isolation suite must remain green.
- Additive catalogue slice may proceed after PAR-SEC-003 closure; **privilege cutover still requires separate authorization**.

## Implementation authorization boundary

| ADR-0014 Accepted authorizes | Does **not** authorize |
|---|---|
| Target model + terminology | Permission changes |
| Mapping / catalogue design | Resolver cutover |
| Additive `RoleDefinition` when separately authorized | Membership-role migration |
| Characterization / catalogue tests | Privilege changes |
| | `UserProfile.role` removal |
| | Workflow assignment cutover |

## Approval

**Accepted** 2026-07-22T11:00:00Z by @haroonwahed and @Technivian per meeting record. Separate implementation authorization required before migration `0112` execution and any later cutover slices.
