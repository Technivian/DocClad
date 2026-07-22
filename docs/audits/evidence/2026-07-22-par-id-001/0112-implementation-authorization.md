# Implementation authorization — migration 0112_role_definition_registry

**Programme:** PAR-ID-001  
**ADR:** ADR-0014 **Accepted** 2026-07-22T11:00:00Z  
**Authorization timestamp:** 2026-07-22T11:00:00Z  
**Motion:** ADR-0014 meeting record Motion 4  
**Status:** **Authorized**

---

## Approvers

| Approver | Capacity | Authority basis | Vote |
|---|---|---|---|
| @haroonwahed | Product governance | CODEOWNERS `/docs/`; Charter v2.0 | **Approve** |
| @Technivian | Engineering governance | CODEOWNERS `/contracts/`; PDR-0003 | **Approve** |

Written consent recorded in `docs/governance/decisions/adr/0014-governance-acceptance-meeting-record-2026-07-22.md`.

---

## Authorized scope

| Item | Authorized |
|---|---|
| Additive `RoleDefinition` model | **Yes** |
| Organization ownership (FK) | **Yes** |
| Stable immutable `code` after creation | **Yes** |
| Unique code per organization | **Yes** |
| Name and description | **Yes** |
| Category (`WORKSPACE`, `WORKFLOW`, `APPROVAL`, `SIGNATURE`, `SYSTEM`, `LEGACY_UNKNOWN`) | **Yes** |
| Active / inactive lifecycle | **Yes** |
| System-managed marker + protection | **Yes** |
| Audit metadata (created/updated by/at) | **Yes** |
| Tenant isolation on catalogue rows | **Yes** |
| Catalogue administration authorization (`can_manage_organization`) | **Yes** |
| Seed of canonical role definitions | **Yes** |
| Compatibility lookup for existing role labels (no privilege dual-write) | **Yes** |
| Audit events: create, update, deactivate, repair | **Yes** |

---

## Explicitly excluded

| Item | Authorized |
|---|---|
| Changing user permissions | **No** |
| Changing `OrganizationMembership` authority | **No** |
| Changing `UserProfile.role` behaviour | **No** |
| Changing approval resolution | **No** |
| Changing signer resolution | **No** |
| Changing workflow assignments | **No** |
| Resolver flip | **No** |
| Legacy field removal | **No** |
| Navigation access changes | **No** |
| Privilege cutover | **No** |

---

## Ambiguous ADMIN rule

- `membership_role` / `ADMIN` → `workspace_admin` (WORKSPACE)
- `profile_role` / `ADMIN` → `legacy_process_admin` (LEGACY_UNKNOWN)
- **Do not merge** these meanings.

---

## Prerequisites met

| Prerequisite | Status |
|---|---|
| ADR-0014 Accepted | **Yes** |
| PAR-SEC-003 Closed | **Yes** |
| Tenant isolation 75/75 | **Yes** |
| PR #51 on `main` | **Yes** @ `21e65f09` |

---

## Next slice (not authorized here)

Org-scoped process-role dual-read / resolver compatibility cutover — requires a **new** implementation authorization record.
