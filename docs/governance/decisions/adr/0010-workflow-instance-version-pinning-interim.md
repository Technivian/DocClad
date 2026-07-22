# ADR-0010: Workflow instance version pinning during Definition/Version interim

- Status: Proposed
- Date: 2026-07-21
- Deciders: Engineering (proposed by platform alignment programme)
- Related: PAR-WF-002, PAR-WF-010, CANONICAL_DOMAIN_MODEL, WORKFLOW_ENGINE_AND_DESIGNER

## Context

The accepted domain model requires:

> Every live Workflow Instance is pinned to one immutable Workflow Version.

Today CLM One stores versions as `WorkflowTemplate` rows (`version`, `parent_template`, `is_active`) and pins runtime via `Workflow.template` FK. A helper `migrate_workflows_to_template` can rebind that FK.

## Decision (proposed — not Accepted)

Until a first-class Workflow Definition / Workflow Version schema ships (PAR-WF-010):

1. Treat each `WorkflowTemplate` row as the interim Workflow Version.
2. Treat `Workflow.template_id` as the pin.
3. Forbid silent rebinding: migrations require a non-empty reason and emit an AuditLog event `workflow_instance_template_migrated`.
4. Prefer launching new instances on new published versions rather than migrating in-flight work.

## Consequences

- Management command `migrate_workflow_template` requires `--migration-reason` when migrating.
- Full Definition/Version split remains Future/Core and must not ship without a separate Accepted ADR covering migrations and rollback.

## Approval

Proposed only. Do not treat as Accepted until recorded by an authorized approver.
