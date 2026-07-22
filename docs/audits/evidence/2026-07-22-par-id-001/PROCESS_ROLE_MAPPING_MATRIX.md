# PAR-ID-001 — Process role mapping matrix (migration 0113)

**Date:** 2026-07-22  
**Authorization:** `0113-process-role-adapter-implementation-authorization.md`  
**Scope:** Truthful legacy → org-scoped `ProcessRoleAssignment` backfill + dual-read diagnostics

---

## Mapping rules (user process roles)

| Legacy source | Legacy value | Org scope of legacy | Canonical target code | Confidence | Ambiguity | Backfill action | Rollback |
|---|---|---|---|---|---|---|---|
| `profile_role` | `PARTNER` | User-global | `partner_reviewer` | CERTAIN | None | Create active `LEGACY_BACKFILL` assignment per org membership | Delete `LEGACY_BACKFILL` rows |
| `profile_role` | `SENIOR_ASSOCIATE` | User-global | `senior_reviewer` | CERTAIN | None | Create per org membership | Delete backfill rows |
| `profile_role` | `ASSOCIATE` | User-global | `legal_reviewer` | CERTAIN | None | Create per org membership | Delete backfill rows |
| `profile_role` | `PARALEGAL` | User-global | `paralegal_reviewer` | CERTAIN | None | Create per org membership | Delete backfill rows |
| `profile_role` | `LEGAL_ASSISTANT` | User-global | `legal_assistant` | CERTAIN | None | Create per org membership | Delete backfill rows |
| `profile_role` | `CLIENT` | User-global | `external_participant` | CERTAIN | None | Create per org membership | Delete backfill rows |
| `profile_role` | `ADMIN` | User-global | `legacy_process_admin` | **AMBIGUOUS** | **Must not merge with Workspace ADMIN** | Create assignment to `LEGACY_UNKNOWN` category role | Delete backfill rows |
| `profile_role` | *(unknown)* | User-global | `legacy_unknown` | UNKNOWN | Unmapped historical value | Create assignment to catch-all if catalogue present | Delete backfill rows |

---

## Explicit non-mappings (not backfilled as process roles)

| Legacy source | Legacy value | Why excluded |
|---|---|---|
| `membership_role` | `OWNER` | Workspace Role — not a process responsibility |
| `membership_role` | `ADMIN` | Workspace Role — **separate** from `UserProfile.ADMIN` |
| `membership_role` | `MEMBER` | Workspace Role |
| `approval_step` | `LEGAL` / `FINANCE` / … | Configuration template labels — not user assignments |
| `signer_role_label` | display strings | Display metadata; auth remains email-based |

Dual-read may **report** workspace membership for drift awareness; it does **not** create process-role assignments from membership roles.

---

## ADMIN collision rule

| Source | Maps to | Category |
|---|---|---|
| `OrganizationMembership.Role.ADMIN` | `workspace_admin` (catalogue label only; not assigned here) | WORKSPACE |
| `UserProfile.Role.ADMIN` | `legacy_process_admin` | LEGACY_UNKNOWN |
| Workflow / approval “administrator” labels | Remain distinct; no silent merge | — |

### First cutover exclusion (2026-07-22)

Formal disposition for the **first** canonical resolver cutover scope (votes for remediation/cutover packages remain Requested where noted):

1. `profile_role` / `ADMIN` remains mapped to `legacy_process_admin` with confidence **AMBIGUOUS**.
2. ADMIN is **excluded** from canonical resolver authority in the first cutover.
3. Workspace `OWNER`, `ADMIN`, and `MEMBER` remain outside process-role resolution.
4. Legacy resolution **continues** for excluded ADMIN cases after any future authority flag is enabled for in-scope CERTAIN roles.
5. A later dedicated reconciliation is required before ADMIN cutover.
6. Parity must **not** reclassify `AMBIGUOUS` as `MATCH`; treat as **accepted exclusion**.

---

## Dual-read policy

| Allowed | Prohibited |
|---|---|
| Diagnostics | Authorization |
| Parity reporting | Approval gating |
| Migration planning | Signer resolution |
| Non-authoritative admin display | Workflow routing / contract access / runtime assignment |

`authoritative_for_runtime` is always `False` in dual-read output.

---

## Backfill invariants

1. Does not modify `UserProfile.role` or `OrganizationMembership.role`.
2. Requires active org membership + existing `RoleDefinition` row.
3. Skips when active assignment already exists.
4. Marks `is_system_managed=True`, `assignment_source=LEGACY_BACKFILL`.
5. Records `legacy_source_field` / `legacy_source_value` and `mapping_confidence`.
