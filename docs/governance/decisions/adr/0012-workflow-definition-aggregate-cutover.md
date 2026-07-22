# ADR-0012: Workflow Definition aggregate and Definition/Version cutover

- Status: **Proposed**
- Date: 2026-07-22
- Deciders: Engineering / Product (proposed by PAR-WF-010 discovery)
- Related: PAR-WF-010, PAR-WF-002, ADR-0010 (interim pinning only), CANONICAL_DOMAIN_MODEL §2.10–2.12, WORKFLOW_ENGINE_AND_DESIGNER

## Context

Accepted domain documentation requires:

```
Workflow Definition → Workflow Version → Workflow Instance → Contract Record
```

CLM One currently **collapses** Definition and Version into a single `WorkflowTemplate` row (`version`, `parent_template`, `is_active`). Runtime pins via `Workflow.template` FK; Contract Record provenance stores `origin_workflow_template` + `origin_workflow_template_version`.

**ADR-0010** (Proposed, not Accepted) governs **interim instance pinning only** — it does not authorize schema split, dual-write, or production cutover.

PAR-WF-010 discovery (`docs/audits/evidence/2026-07-22-par-wf-010/`) documents current state, target aggregate, cutover plan, and risks.

## Decision (proposed — not Accepted)

### 1. Target schema (additive; no production cutover until Accepted)

Introduce two first-class entities:

| Entity | Purpose |
|---|---|
| **`WorkflowDefinition`** | Stable identity: `organization`, `name`, `category`, `contract_type`, `slug`/stable key, archival flags |
| **`WorkflowVersion`** | Immutable published configuration snapshot; FK `definition`; `version_number`; lifecycle state; `published_at`/`published_by`; child config |

**Compatibility:** retain `WorkflowTemplate` during dual-read period with nullable `workflow_version_id` (or equivalent) back-link. Do **not** drop `WorkflowTemplate` until removal criteria met.

### 2. Version lifecycle mapping

| Canonical state | Interim today | Target `WorkflowVersion.status` |
|---|---|---|
| Draft | `is_active=False`, editable | `DRAFT` |
| In validation / Ready | publish validation gates | `IN_VALIDATION` / `READY` (optional sub-states) |
| Published | `is_active=True`, immutable | `PUBLISHED` |
| Superseded | older published row, instances pinned | `SUPERSEDED` |
| Archived | not first-class today | `ARCHIVED` |

### 3. Pinning surfaces (must remain consistent through cutover)

1. **`Workflow.workflow_version_id`** (new) — canonical pin; `Workflow.template_id` transitional mirror during dual-read.
2. **`Contract.origin_workflow_version_id`** (new) + denormalized `version_number` — canonical record lineage; existing template FKs transitional.
3. **`WorkflowStep.template_step`** — must reference step rows owned by the **pinned version**, not latest published.

### 4. Child configuration ownership

Move FK targets from `WorkflowTemplate` to `WorkflowVersion`:

- `WorkflowTemplateStep` → `WorkflowVersionStep` (or version FK on existing step table)
- `FieldDefinition.workflow_template` → `workflow_version`
- `ApprovalRoute.workflow_template` → `workflow_version`
- `WorkflowTemplateScenario.template` → `workflow_version` (scenarios are version-scoped test fixtures)

### 5. Publication rules

- At most **one** `PUBLISHED` version per Definition for default launch resolution (enforced by DB constraint + service).
- Publishing creates immutable snapshot; edits require new draft version (clone/restore pattern preserved).
- Restoration always creates a **new draft** — never overwrites published bytes (current `clone_template_version` semantics).

### 6. Governed instance migration

Retain PAR-WF-002 semantics:

- Non-empty reason required
- Audit event `workflow_instance_template_migrated` (transitional) → `workflow.instance.version_migrated` (canonical)
- Prefer new launches on new published versions over in-flight rebinding

### 7. Cutover phases (see CUTOVER_PLAN.md)

1. Additive schema + truthful backfill (no write-path redirect)
2. Dual-read compatibility layer behind feature flag (default off)
3. Pilot org opt-in single-write
4. Global single-write + deprecate `WorkflowTemplate` writes
5. Read-path removal after removal criteria

### 8. Explicit non-goals until Accepted + ops window

- No production `WorkflowDefinition` model deployment
- No live launch-path redirect
- No data migration in pilot/production without runbook
- No change to controlled-pilot workflow seeds (DPA/MSA/NDA) without ops approval

## Relationship to ADR-0010

| Topic | ADR-0010 | ADR-0012 |
|---|---|---|
| Interim pin semantics | Proposed | **Superseded on cutover** (pin moves to `WorkflowVersion`) |
| Schema split | Explicitly out of scope | **In scope** |
| Production authorization | **Not authorizing** | **Required for cutover** |
| Instance migrate audit | `workflow_instance_template_migrated` | Preserved + canonical event alias |

**ADR-0010 alone is insufficient** for PAR-WF-010 production cutover. Both remain Proposed until formally Accepted.

## Consequences

- PAR-WF-010 remains **Blocked pending architecture approval** (this ADR or successor).
- Safe preparatory work allowed: characterization tests, evidence docs, additive migration design, compatibility layer stubs behind flags.
- Human approval required: Accept ADR-0012 (or amended successor) + ops migration window sign-off before phase 3+.

## Approval

Proposed only. Do not treat as Accepted until recorded by an authorized approver per GOVERNANCE_CHARTER.
