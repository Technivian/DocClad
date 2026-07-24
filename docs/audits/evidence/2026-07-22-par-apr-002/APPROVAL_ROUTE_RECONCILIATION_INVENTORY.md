# PAR-APR-002 ApprovalRoute reconciliation inventory

## Scope and boundary

This is evidence-only characterization. It records the current relationship
between template routes, legacy approvals, and canonical requirements. It
does not create a relationship, alter route resolution, enable a flag, change
authority, or modify production behaviour. `ApprovalRequest` remains the
authoritative approval read model.

## Ownership and creation findings

| Concern | Current owner / source | Verified finding |
|---|---|---|
| Route configuration | `ApprovalRoute`, owned by `WorkflowTemplate` | A route stores a template FK, name, order, UI role label, and optional condition text. It has no direct organization field, runtime workflow FK, document version, actor, or requirement/request FK. Tenant scope is inherited through `WorkflowTemplate.organization`. |
| Route configuration seeding | Workflow seed migrations and workflow seed services | DPA, MSA, and NDA seeded templates provide ordered route rows. They are configuration and presentation evidence, not a runtime authorization source. |
| Route display | Workflow Designer route list and workflow detail contexts | The route list scopes templates to the current organization plus permitted global templates. Workflow detail reads routes from its selected template for display. |
| Runtime approval selection | `ApprovalRule` plus `build_approval_request_plan_for_contract()` | The plan evaluates active organization-scoped rules against the contract. It does not read `ApprovalRoute`; a plan item contains a rule, step, assignee, due date, and legacy pending status. |
| Runtime record creation | `ApprovalWorkflowService` and workflow-creation views | The service creates a legacy `ApprovalRequest` and its canonical mirror. Workflow creation views directly create legacy requests from the rule plan; the legacy model's creation hook supplies the canonical mirror. Neither path carries a route ID. |
| Canonical requirement ownership | `ApprovalRequirement` / `ApprovalDecision` | A requirement can retain the legacy-request one-to-one link, rule, authority basis/reference, tenant, contract, actor, and document-version snapshot. It has no route FK or route identifier in its authority reference. |

## Binding and dependency findings

| Binding / consumer | Current behaviour | Reconciliation implication |
|---|---|---|
| Contract | Rule plans and both approval models bind to the contract. Routes bind only to a template. | A route cannot be correlated to a requirement from contract equality. |
| Workflow and workflow version | A route is attached to a template row; the runtime requirement contains no workflow/template/route ID. | No durable route-to-runtime or template-version binding exists. |
| Actor | Route `role_label` is presentational. Runtime assignment derives from `ApprovalRule` or workflow submission. | Route labels cannot be used to infer an approver or authority holder. |
| Tenant | Route list derives tenant scope through template organization; legacy/canonical approvals carry organization IDs. | Any future relationship must reject cross-tenant template, contract, and requirement combinations. |
| Lifecycle | Signature and activation still query legacy approvals in addition to canonical requirements. | Legacy remains authoritative; no route row can satisfy a lifecycle gate. |
| Inbox and API | Approval inbox/service DTOs and API surfaces consume `ApprovalRequest`; canonical mirroring is not a read cutover. | A route mapping must not change inbox or API sources without separate authority. |
| Operations | Workflow Designer, operations counts, queues, reminders, monitoring, and audit consume template routes or legacy approvals separately. | Route labels/counts are not parity proof for pending approval work. |

## Structural mismatch inventory

Counts below are deterministic characterization-fixture counts from
`tests/test_par_apr_002_approval_route_inventory.py`; they are not production
data counts.

| Category | Count | Evidence / interpretation |
|---|---:|---|
| Valid direct route-to-requirement links | 0 | No model field, authority-reference key, or creation-plan value carries a route ID. |
| Valid direct route-to-legacy-request links | 0 | `ApprovalRequest` has no route FK; creation is rule-plan driven. |
| Missing mapping | 1 | One configured route produces no plan or requirement until an independent matching rule exists. |
| Duplicate route order | 2 rows at one template/order | `ApprovalRoute` has ordering only; it has no uniqueness constraint for template/order or a stable route key. |
| Ambiguous route-to-runtime correlation | 1 category | Contract, template label/order, actor, or step equality has no governed route correlation key. |
| Stale-route protection | 0 explicit controls | A requirement records no route/template/version snapshot; a template route cannot prove that it governed an existing runtime approval. |

## Current parity position and acceptance criteria

The only current parity is legacy-to-canonical mirroring after a legacy
approval is created. It is **not** route parity. Before any separately
authorized reconciliation implementation, evidence must show:

1. an explicit, immutable route identity and an approved owner for route
   configuration;
2. an unambiguous creation rule from an approved route to a requirement;
3. same-tenant contract, workflow/template-version, actor, and document-version
   binding;
4. deterministic handling of missing, duplicate, ambiguous, and stale routes;
5. parity counts for legacy request, canonical requirement, decision, inbox,
   lifecycle, API, and operations projections; and
6. tenant-isolation, permission-denial, rollback, and audit evidence.

## Tests and result

`tests/test_par_apr_002_approval_route_inventory.py` records that:

- a route does not produce a plan or requirement; a matching `ApprovalRule`
  does, and the resulting canonical authority reference contains only the rule;
- duplicate route order is currently allowed and no direct tenant/requirement
  key exists on the route; and
- the route list requires login and does not disclose a route attached to a
  foreign organization template.

Focused regression selection: **98 passed** — existing APR-002 baseline,
this route inventory, approval workflow, cross-tenant isolation, and
permission-matrix modules. `manage.py check` passed.

`tests.test_workflow_operations` is a separate known residual: all six tests
currently fail in setup because their fixture pairs record status `ACTIVE`
with workflow stage `INTERNAL_REVIEW`, which the current lifecycle validator
rejects. This slice does not alter either model, lifecycle validation, or
workflow-operations code; the residual is not attributed to this evidence-only
change.

## Blockers and smallest safe reconciliation slice

**Blockers:** no stable route ID, no route-to-requirement relation, no
workflow/template-version or document-version snapshot on requirements, and
no approved semantics for duplicate, ambiguous, or stale configurations.

The smallest safe next slice is a separate planning/authorization package that
chooses the route identity, lifecycle ownership, and invalidation semantics.
It must remain additive and non-authoritative; it must not create a model,
migration, mapping, dual-write, or read cutover until separately authorized.
