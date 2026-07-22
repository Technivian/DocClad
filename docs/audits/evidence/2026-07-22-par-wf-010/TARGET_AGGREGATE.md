# PAR-WF-010 — Target Workflow aggregate

**Date:** 2026-07-22  
**Status:** Design target — **not implemented**  
**Authorizing decision:** Proposed ADR-0012 (not Accepted)

---

## Object chain

```
WorkflowDefinition (stable identity)
    └── WorkflowVersion[] (immutable published snapshots + drafts)
            └── WorkflowInstance (runtime pin to exactly one Version)
                    └── ContractRecord (provenance lineage to Instance + Version)
```

---

## WorkflowDefinition — stable identity

| Field / rule | Specification |
|---|---|
| **Purpose** | Reusable workflow configuration identity across versions |
| **Stable key** | `id` (PK) + optional `slug` unique per `(organization, slug)` |
| **Metadata** | `name`, `description`, `category`, `contract_type` FK, `organization` |
| **Ownership** | Org-scoped; global seeds map to `organization=NULL` with stable slug |
| **Archival** | `is_archived`, `archived_at`, `archived_by` — definition hidden from launch, versions retained |
| **Deprecation** | `deprecated_at` + reason; no new launches; existing instances continue |
| **Deletion** | Soft-delete only when zero instances and zero published versions (or legal hold) |
| **Tenant** | Mandatory org scoping for tenant templates; global definitions read-only for tenants |

**Resolution rules:**

- Default launch: latest `PUBLISHED` version for definition (by `version_number`).
- Explicit launch: user selects definition → system resolves published version (or prompts if multiple published — should be prevented by constraint).
- Contract-type binding: `WorkflowDefinition.contract_type` drives cockpit auto-select (replaces `get_*_workflow_template` row lookup).

---

## WorkflowVersion — lifecycle

| State | Editable | Launchable | Instance pin |
|---|---|---|---|
| `DRAFT` | Yes | No | No |
| `IN_VALIDATION` | Limited (fix validation issues) | No | No |
| `READY` | No (awaiting publish action) | No | No |
| `PUBLISHED` | **No** (immutable) | Yes | Yes |
| `SUPERSEDED` | No | No (existing pins valid) | Yes (historical) |
| `ARCHIVED` | No | No | Yes (historical) |

### Version numbering

- Deterministic `version_number` per definition: `max(existing) + 1` under `select_for_update` on definition row.
- Unique constraint: `(definition_id, version_number)`.
- **At most one `PUBLISHED` version per definition** at a time (DB partial unique index or service enforcement).

### Publication

1. Run `validate_version_for_publish(version)` (port of `validate_template_for_publish`).
2. Transition prior `PUBLISHED` → `SUPERSEDED` (if any).
3. Set `PUBLISHED`, `published_at`, `published_by`.
4. Emit `workflow.version.published` audit (maps from `workflow_template_publish_toggled`).

### Restoration

- **Always** `clone_version_as_draft(source_version)` → new `DRAFT` with `version_number+1`.
- Never mutate published configuration in place (matches current `clone_template_version` / restore views).

### Child configuration (owned by Version)

- Steps, field definitions, approval routes, test scenarios — all FK to `WorkflowVersion`.
- Deep copy on version clone; immutable after publish.

---

## WorkflowInstance pinning

| Rule | Specification |
|---|---|
| **Pin** | `Workflow.workflow_version_id` NOT NULL after materialize |
| **Immutability** | Pin cannot change except via governed `migrate_instance_version(reason, audit)` |
| **Materialize** | `materialize_workflow_from_version(instance)` copies version steps → instance steps |
| **Step linkage** | `WorkflowStep.version_step_id` FK to pinned version's step rows |
| **Transitional** | `Workflow.template_id` mirrored during dual-read for legacy code paths |

**Governed migration** (preserves PAR-WF-002 / ADR-0010 intent):

- Non-empty reason
- Audit: `workflow.instance.version_migrated` with source/target version ids, instance ids, actor
- Re-materialize or remap `WorkflowStep.version_step` when target version step topology differs (explicit policy TBD in ops runbook)

---

## Contract Record lineage

| Field | Target |
|---|---|
| `origin_workflow_id` | Unchanged — instance FK |
| `origin_workflow_version_id` | **New** — canonical version pin |
| `origin_workflow_version_number` | Denormalized int for audit readability |
| `origin_workflow_template_id` | Transitional mirror during dual-read |
| Provenance lock | Unchanged — `provenance_locked_at` immutability (PAR-CORE-003) |

`pin_workflow_provenance()` resolves version from `workflow.workflow_version_id` (canonical) with fallback to `workflow.template_id` during transition.

**Gap to close:** NDA cockpit should call `pin_workflow_provenance` (safe preparatory fix, not cutover).

---

## Permissions

| Action | Who |
|---|---|
| View definitions/versions | Org members with configuration read |
| Edit draft versions | Workflow designer role / org admin (existing designer gates) |
| Publish | Same + validation pass; published immutability enforced server-side |
| Launch instance | Contract/workflow create permissions |
| Migrate instance version | Org admin / governed ops role + reason |
| Archive definition | Org admin |

Tenant isolation: all definition/version queries scoped by `organization_id` (existing `scope_workflow_templates_for_organization` pattern).

---

## Audit events (canonical)

| Event | When | Legacy equivalent |
|---|---|---|
| `workflow.definition.created` | New definition | — |
| `workflow.version.created` | New draft version | `workflow_template_created` / `workflow_template_cloned` |
| `workflow.version.updated` | Draft edit | `workflow_template_updated` |
| `workflow.version.published` | Publish | `workflow_template_publish_toggled` |
| `workflow.version.superseded` | Prior published superseded | (implicit today) |
| `workflow.version.restored` | Restore as new draft | `workflow_template_restored` |
| `workflow.instance.created` | Launch | `workflow_created` |
| `workflow.instance.version_migrated` | Governed rebind | `workflow_instance_template_migrated` |
| `workflow.simulation.run` | Dry-run | `workflow_preview_run` |

Reuse existing event payloads where possible during dual-write audit period.

---

## Deletion and deprecation

| Entity | Rule |
|---|---|
| **Published version** | Never hard-deleted; archive only |
| **Draft version** | Deletable if never published and no instances pinned |
| **Definition** | Archive when no active instances on any version; never delete if audit history requires retention |
| **WorkflowTemplate (legacy)** | Read-only after cutover phase 4; dropped only when removal criteria met |

---

## UI / designer (target IA)

```
Settings → Workflows → [Definition list]
    → Definition detail
        → Versions table (draft / published / superseded)
        → Designer canvas (draft only)
        → Test / simulation tab (draft version)
        → Activity / audit export
```

Launch picker shows **Definitions** resolving to current published version (not raw version rows).

---

## What accepted documentation already mandates (no ADR needed)

- Definition / Version / Instance separation (CANONICAL_DOMAIN_MODEL §2.10–2.12)
- Published versions immutable (invariant §273–274)
- Instance pins exactly one version (invariant §273)
- Contract Record provenance mandatory (§2.13, PAR-CORE-003)
- Designer configures stages, fields, approvals, signatures (WORKFLOW_ENGINE_AND_DESIGNER)
- Published template mutate gates (PAR-WF-001, completed)

## What requires Accepted ADR-0012 (or successor)

- Schema entity names and FK graph
- Dual-read / single-write cutover phases
- Legacy `WorkflowTemplate` removal criteria
- Instance step re-materialize policy on version migrate
