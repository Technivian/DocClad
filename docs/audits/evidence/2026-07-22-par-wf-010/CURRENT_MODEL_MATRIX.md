# PAR-WF-010 — Current workflow model matrix

**Date:** 2026-07-22  
**Scope:** Discovery only — interim `WorkflowTemplate` collapse vs canonical Definition → Version → Instance chain

## Legend

| Column | Meaning |
|---|---|
| **Owner** | Primary module / team surface |
| **Lifecycle** | Create → mutate → publish → pin → archive |
| **Consumers** | Runtime readers/writers |
| **Tenant** | Org scoping rule |
| **Mutability** | Post-publish / post-pin rules |
| **Audit** | Primary events |
| **Migration risk** | Cutover impact (H/M/L) |
| **Canonical target** | PAR-WF-010 target entity/field |

---

## Core models

### `WorkflowTemplate`

| Attribute | Value |
|---|---|
| **Current meaning** | Collapsed **Workflow Definition + Workflow Version** — one row per version |
| **Key fields** | `name`, `description`, `organization`, `category`, `version`, `parent_template`, `contract_type`, `is_active`, `published_at/by`, `created_by`, `fallback_signer` |
| **Owner** | `contracts/models.py`; designer in `workflow_management.py` |
| **Lifecycle** | Create draft (`is_active=False` default) → configure steps/fields → validate → publish (`is_active=True`, immutable) → clone/restore as new draft version |
| **Consumers** | Launch (`Workflow.template`), routing (`workflow_routing.py`), DPA/MSA/NDA cockpits, designer UI, admin, seeds (`0071`/`0075`/`0077`), `migrate_workflow_template` command |
| **Tenant** | `organization` FK; null = global seed templates; scoped via `scope_workflow_templates_for_organization` |
| **Mutability** | Published rows read-only (`can_mutate_workflow_template`, admin readonly); drafts editable |
| **Audit** | `workflow_template_*` events (`workflow_audit.py`) |
| **Migration risk** | **H** — split identity vs version; all child FKs; seeds by name |
| **Canonical target** | Split → `WorkflowDefinition` (identity) + `WorkflowVersion` (config snapshot); `WorkflowTemplate` deprecated compatibility mirror |

### `WorkflowTemplateStep`

| Attribute | Value |
|---|---|
| **Current meaning** | Stage definition on a template **version row** |
| **Key fields** | `template` FK, `name`, `order`, `step_kind`, `condition_expression/rules`, assignee fields, SLA/escalation |
| **Owner** | Designer step CRUD views |
| **Lifecycle** | CRUD on draft template only; copied on clone/restore |
| **Consumers** | `materialize_workflow_from_template`, simulation, publish validation, runtime step transitions |
| **Tenant** | Via parent template org |
| **Mutability** | Immutable when parent published |
| **Audit** | `workflow_template_step_added/updated/deleted`, `workflow_template_reordered` |
| **Migration risk** | **H** — FK moves to `WorkflowVersion`; instance `WorkflowStep.template_step` must stay consistent with pin |
| **Canonical target** | `WorkflowVersionStep` (or version FK on step table) |

### `FieldDefinition`

| Attribute | Value |
|---|---|
| **Current meaning** | Intake/form field schema per template version |
| **Key fields** | `workflow_template` FK, `key`, `label`, `section`, `field_type`, `options`, `maps_to_contract_field` |
| **Owner** | DPA/MSA field designer; `workspace_nav.py` scoping |
| **Lifecycle** | Edited on draft templates; seeded in migrations |
| **Consumers** | Workflow cockpits, `FieldValue` capture, contract field mapping |
| **Tenant** | Via template org |
| **Mutability** | Draft-only |
| **Audit** | Template update events (no dedicated field event) |
| **Migration risk** | **H** — pilot DPA/MSA fields in migrations |
| **Canonical target** | `workflow_version` FK |

### `ApprovalRoute`

| Attribute | Value |
|---|---|
| **Current meaning** | Template-level approval chain definition |
| **Key fields** | `workflow_template` FK, `name`, `order`, `role_label`, conditional flags |
| **Owner** | `workflow_approval_route_*` views |
| **Lifecycle** | Configured per template version |
| **Consumers** | Approval planning in workflow routing |
| **Tenant** | Via template org |
| **Mutability** | Draft-only |
| **Audit** | Indirect via template events |
| **Migration risk** | **M** |
| **Canonical target** | `workflow_version` FK |

### `WorkflowTemplateScenario`

| Attribute | Value |
|---|---|
| **Current meaning** | Designer Test-tab saved simulation payloads |
| **Key fields** | `organization`, `template` FK, `name`, `payload` JSON |
| **Owner** | `workflow_template_scenario_save` |
| **Lifecycle** | CRUD on designer Test tab |
| **Consumers** | Simulation preview |
| **Tenant** | `organization` + template scope |
| **Mutability** | Editable |
| **Audit** | `workflow_template_scenario_saved` |
| **Migration risk** | **L** |
| **Canonical target** | `workflow_version` FK |

### `Workflow` (Instance)

| Attribute | Value |
|---|---|
| **Current meaning** | Live **Workflow Instance** |
| **Key fields** | `title`, `organization`, **`template`** FK (version pin), `contract`, `status`, `created_by` |
| **Owner** | `workflow_management.py`, cockpit services |
| **Lifecycle** | Create → materialize steps → advance → complete/cancel |
| **Consumers** | My Work, Command Center projection, contract detail, provenance |
| **Tenant** | `organization` FK; isolation tests in `test_cross_tenant_isolation.py` |
| **Mutability** | Status/steps mutable; **template pin** change only via governed migrate |
| **Audit** | `workflow_created`, `workflow_step_*`, `workflow_instance_template_migrated` |
| **Migration risk** | **H** — pin FK rename/split; active instances |
| **Canonical target** | `workflow_version_id` pin; `template_id` transitional |

### `WorkflowStep`

| Attribute | Value |
|---|---|
| **Current meaning** | Instance stage execution row |
| **Key fields** | `workflow` FK, **`template_step`** FK, `status`, `assigned_to`, dates, `order` |
| **Owner** | Runtime transition views |
| **Lifecycle** | Materialized at launch; transitions governed |
| **Consumers** | Approvals, signatures, SLA escalation |
| **Tenant** | Via workflow org |
| **Mutability** | Runtime state mutable; definition via pinned `template_step` |
| **Audit** | Step transition events |
| **Migration risk** | **H** — `template_step` must map to version-owned steps after migrate |
| **Canonical target** | `version_step` FK to pinned version's step rows |

### `FieldValue`

| Attribute | Value |
|---|---|
| **Current meaning** | Captured intake answers per instance |
| **Key fields** | `workflow` FK, `field_definition` FK, value columns |
| **Owner** | Cockpit submit handlers |
| **Lifecycle** | Written during workflow execution |
| **Consumers** | DPA/MSA/NDA workflows, contract field sync |
| **Tenant** | Via workflow org |
| **Mutability** | Mutable during active workflow |
| **Audit** | Workflow/contract events |
| **Migration risk** | **M** — field_definition version binding |
| **Canonical target** | Unchanged instance semantics; definition FK via version |

### `DraftDocument`

| Attribute | Value |
|---|---|
| **Current meaning** | Workflow scratch draft text (not file Document Version) |
| **Key fields** | `workflow` FK, `content`, `version`, `is_current` |
| **Owner** | NDA/MSA/DPA workflow services |
| **Lifecycle** | Updated during drafting; exported to `Document` on generate |
| **Consumers** | Cockpit editors, export paths |
| **Tenant** | Via workflow org |
| **Mutability** | Mutable |
| **Audit** | Export events (`msa.*_exported`) |
| **Migration risk** | **L** — instance-scoped, not template FK |
| **Canonical target** | Unchanged (instance artifact) |

### `Contract` (provenance fields)

| Attribute | Value |
|---|---|
| **Current meaning** | **Contract Record** with workflow lineage |
| **Key fields** | `origin_workflow`, `origin_workflow_template`, `origin_workflow_template_version`, `origin_kind/channel`, `provenance_locked_at` |
| **Owner** | `contract_provenance.py` |
| **Lifecycle** | Assigned at workflow launch (`pin_workflow_provenance`); locked after execution milestones |
| **Consumers** | Record shell, audit, imports |
| **Tenant** | `organization` |
| **Mutability** | Immutable after `provenance_locked_at` |
| **Audit** | `contract.provenance.*` events |
| **Migration risk** | **H** — template FK → version FK; denormalized version int |
| **Canonical target** | `origin_workflow_version_id` + `version_number` mirror |

### `ContractType`

| Attribute | Value |
|---|---|
| **Current meaning** | Catalogue binding for template lookup |
| **Key fields** | `code`, name; reverse `workflow_templates` |
| **Owner** | `contract_type_catalogue.py` (PAR-CORE-002) |
| **Lifecycle** | Seeded catalogue; templates bind via FK |
| **Consumers** | `get_*_workflow_template()`, routing |
| **Tenant** | Global catalogue; templates org-scoped |
| **Mutability** | Governed catalogue updates |
| **Audit** | `contract_type.catalogue.updated` |
| **Migration risk** | **M** — Definition should FK to catalogue, not each version row redundantly |
| **Canonical target** | `WorkflowDefinition.contract_type` FK |

---

## Implicit “definition family” (not a model)

| Attribute | Value |
|---|---|
| **Current meaning** | Template versions grouped by `(name, category, organization)` — see `list_template_versions()` |
| **Owner** | `workflow_templates.py` |
| **Lifecycle** | Implicit; no stable definition ID |
| **Consumers** | Version list UI, compare, clone lineage |
| **Tenant** | Org in family filter |
| **Mutability** | N/A |
| **Audit** | Clone/restore events |
| **Migration risk** | **H** — must become explicit `WorkflowDefinition.id` |
| **Canonical target** | `WorkflowDefinition` stable primary key |

---

## Production path summary

| Path | Entry | Pin / version behavior |
|---|---|---|
| Generic workflow create | `workflow_create` POST | `materialize_workflow_from_template`; template from suggest or `?template_pk=` |
| DPA cockpit | `create_dpa_workflow_instance` | Materialize + `pin_workflow_provenance` |
| MSA cockpit | `create_msa_workflow_instance` | Same |
| NDA cockpit | `create_nda_workflow_instance` | Materialize only — **provenance gap** vs DPA/MSA |
| Publish | `workflow_template_publish_toggle` | `validate_template_for_publish`; `is_active=True` |
| Clone version | `clone_template_version` | New row, `version+1`, `is_active=False` |
| Restore | `workflow_template_restore_version` | Clone as new draft; never overwrites published |
| Instance migrate | `migrate_workflows_to_template` | Reason required; audit `workflow_instance_template_migrated` |
| Simulation | `simulate_workflow_template` | No DB writes |
| Admin | `WorkflowTemplateAdmin` | Published readonly (PAR-WF-001/AUD-001) |

---

## String / integration references

| Reference | Location | Risk |
|---|---|---|
| `workflow_template` Salesforce field map key | `salesforce.py`, fixture JSON | **M** — map to definition code |
| Seed template names (`DPA Privacy Review`, etc.) | Migrations `0071`/`0075`/`0077` | **H** — backfill definition stable keys |
| URL names `workflow_template_*` | `urls.py`, nav | **L** — UI rename later |
| `get_dpa/msa/nda_workflow_template()` | Cockpit services | **M** — resolve via Definition + published version |

---

## Test coverage map

| Area | Primary tests |
|---|---|
| Versioning / clone / restore | `test_workflow_template_versioning.py` |
| Designer / publish gates | `test_workflow_designer_canvas.py`, `test_platform_workflow_invariants.py` |
| Instance migrate + audit | `test_platform_workflow_invariants.py` |
| Simulation | `test_workflow_simulation.py` |
| Execution / materialize | `test_workflow_execution.py` |
| Routing / launch | `test_workflow_routing.py` |
| Audit trail | `test_workflow_audit_trail.py` |
| Provenance | `test_par_core_003_provenance.py` |
| Pilot cockpits | `test_dpa_workflow.py`, `test_msa_workflow.py`, `test_nda_workflow.py` |
| Tenant isolation | `test_cross_tenant_isolation.py` |
| **PAR-WF-010 baseline** | `test_par_wf_010_characterization.py` (new) |
