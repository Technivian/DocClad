# PAR-ID-001 — Cutover plan (planning only)

**Date:** 2026-07-22  
**Status:** **Planning — not authorized for implementation**  
**Prerequisites:** Accepted ADR-0014 · PAR-SEC-003 formal disposition · implementation authorization vote

> This plan describes the **proposed** migration path. No schema changes, backfills, or privilege cutover may begin until ADR-0014 is Accepted and explicit implementation authorization is recorded.

---

## 1. Guiding principles

1. **Additive first** — no destructive enum drop in initial slices.
2. **Truthful backfill** — unknown meanings remain `legacy_unknown` in mapping table.
3. **No silent merge** — workspace ADMIN ≠ process ADMIN.
4. **Least privilege** — backfill must not widen permissions.
5. **Dual-read period** — interim resolvers read legacy + canonical mapping.
6. **Pilot protection** — `seed_controlled_pilot` and production pilot orgs validated before single-write.
7. **First cutover ADMIN exclusion (2026-07-22)** — `profile_role` ADMIN / `legacy_process_admin` is **out of scope** for the first `PROCESS_ROLE_CANONICAL_RESOLVER_ENABLED` authority flip; legacy continues for those cases; AMBIGUOUS must not be relabeled MATCH; dedicated later reconciliation required before ADMIN cutover. Workspace OWNER/ADMIN/MEMBER remain outside process-role resolution.

---

## 2. Additive schema sequence (proposed)

| Step | Migration | Content | Depends on |
|---|---|---|---|
| **ID-1** | `0112_role_definition_registry` | `RoleDefinition` catalogue (org-scoped, stable key, display label, deprecated flag) | ADR-0014 Accepted |
| **ID-2** | `0113_role_mapping_legacy` | `LegacyRoleMapping` (source_system, source_value, role_definition_id, authority_notes, unknown_flag) | ID-1 |
| **ID-3** | `0114_runtime_assignment_provenance` | Optional FK `role_definition_id` on `WorkflowTemplateStep`, `ApprovalRule`; nullable on existing rows | ID-1 |
| **ID-4** | `0115_org_scoped_profile_role` | `OrganizationUserRole` (org, user, role_definition) — dual-read with `UserProfile.role` | ID-1, ID-3 |
| **ID-5** | `0116_permission_set_documentation` | Optional `PermissionSetEntry` or documented matrix seed (config data) | ID-2 |
| **ID-6** | `0117_single_write_cutover` | Flip resolver to canonical read; legacy write-only | ID-4 + verification |
| **ID-7** | `0118_legacy_deprecation` | Deprecate `UserProfile.role` write path (read-only mirror) | ID-6 + PAR-ID-001 closure |

**No step authorized until ADR-0014 Accepted.**

---

## 3. Truthful backfill rules

### 3.1 Workspace roles (`OrganizationMembership.role`)

| Source value | Target | Action |
|---|---|---|
| `OWNER` | Workspace Role `OWNER` | Direct map |
| `ADMIN` | Workspace Role `ADMIN` | Direct map |
| `MEMBER` | Workspace Role `MEMBER` | Direct map |

### 3.2 Process roles (`UserProfile.role`)

| Source value | Target Role Definition | Unknown? |
|---|---|---|
| `PARTNER` | `partner_reviewer` | No |
| `SENIOR_ASSOCIATE` | `senior_reviewer` | No |
| `ASSOCIATE` | `legal_reviewer` | No |
| `PARALEGAL` | `paralegal_reviewer` | No |
| `LEGAL_ASSISTANT` | `legal_assistant` | No |
| `CLIENT` | `external_participant` | No |
| `ADMIN` | **`legacy_process_admin`** | **Yes — explicit unknown bucket** |

> `UserProfile.ADMIN` must **not** map to Workspace ADMIN. Remains explicit until product owner confirms intended process meaning per org.

### 3.3 Approval steps (`approval_step` char)

| Source | Target Workflow Role Definition |
|---|---|
| `LEGAL` | `legal_reviewer` |
| `FINANCE` | `finance_approver` |
| `PRIVACY` | `privacy_reviewer` |
| `EXECUTIVE` | `executive_approver` |
| `COMPLIANCE` | `compliance_reviewer` |

### 3.4 Contract accountability

| Field | Target |
|---|---|
| `Contract.owner` | Runtime Assignment `contract_owner` |
| `Contract.created_by` | Runtime Assignment `requester` |

### 3.5 Unmappable historical rows

- Set `unknown_flag=True` on mapping row.
- Preserve original char value in `legacy_mirror` column.
- Do not assign default admin resolver.

---

## 4. Ambiguous role handling

| Ambiguity | Handling |
|---|---|
| C-ID-01 `ADMIN` collision | Separate mapping rows; UI disambiguation labels |
| C-ID-02 user-global profile | Backfill `OrganizationUserRole` per active membership; flag conflicts |
| C-ID-03 ApprovalRoute vs ApprovalRule | Route labels reference Definition ID; no runtime authority |
| Multi-org user different roles | Org-scoped role table; resolver uses contract.org |
| Missing assignee match | `fail_closed=True` — no approval auto-assigned to admin |

---

## 5. Compatibility adapter (dual-read)

**Phase A — dual-write:**
- New assignments write both legacy char and `role_definition_id`.
- Resolvers try canonical FK first, fall back to legacy char via mapping table.

**Phase B — dual-read:**
- Reads prefer canonical; legacy mirror for rows without FK.

**Phase C — single-write:**
- Legacy char computed from canonical for display only (or frozen).

**Adapter location (proposed):** `contracts/services/role_resolution.py` (not implemented).

---

## 6. Permission verification gates

Before single-write (ID-6):

| Gate | Command / suite |
|---|---|
| Permission matrix | `tests/test_permission_matrix.py` + expanded PAR-ID suite |
| Approval authz | `tests/test_approval_authorization.py` |
| Cross-tenant | `tests/test_cross_tenant_isolation.py` (75 tests) |
| Pilot smoke | `seed_controlled_pilot` + manual checklist |
| No privilege widening | Diff permission matrix before/after backfill |

---

## 7. Tenant-isolation verification

| Check | Requirement |
|---|---|
| Cross-org resolver | Must return None / 404 — never foreign org user |
| Cross-org assignment mutation | 404 |
| Programme isolation suite | Full green |
| PAR-SEC-003 | **Formal disposition required** before privilege cutover |

**Current state:** Isolation suite **75/75 PASS** on branch; PAR-SEC-003 roadmap item **not formally closed** — cutover **blocked**.

---

## 8. Pilot protection

1. Run backfill dry-run against `seed_controlled_pilot` fixtures only.
2. Verify pilot users retain same effective permissions (matrix diff).
3. No production pilot org changes without ops window + rollback checkpoint.
4. Feature flag `ROLE_DEFINITION_CANONICAL_READ` (proposed) — default off until verification.

---

## 9. Rollback checkpoints

| Checkpoint | After | Rollback action |
|---|---|---|
| **CP-1** | ID-1 registry migration | Reverse migration; no runtime change |
| **CP-2** | ID-4 org-scoped roles | Disable canonical read flag; legacy resolver only |
| **CP-3** | ID-6 single-write | Re-enable dual-write; restore legacy write path |
| **CP-4** | ID-7 deprecation | Restore `UserProfile.role` write + backfill from mirror |

Each checkpoint requires migration reverse proof in evidence folder.

---

## 10. Legacy removal criteria

`UserProfile.role` write path may be removed only when:

- [ ] ADR-0014 Accepted
- [ ] All resolvers use canonical Role Definition + org scope
- [ ] Backfill 100% mapped or explicitly flagged unknown
- [ ] Permission matrix tests prove no widening
- [ ] Tenant isolation programme proof complete (PAR-SEC-003 disposed)
- [ ] Pilot sign-off recorded
- [ ] Implementation authorization for removal slice

---

## 11. Authorization boundary

| Authorized now (discovery) | Not authorized |
|---|---|
| Evidence, ADR proposal, characterization tests, cutover plan | Schema migrations ID-1+ |
| | Backfill execution |
| | Resolver cutover |
| | Permission model changes |
| | Legacy enum removal |

**Next implementation step after ADR-0014 Accepted:** Migration ID-1 (`RoleDefinition` registry) on a dedicated branch with characterization test updates only — no resolver flip.
