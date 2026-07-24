# PDR-0006: ApprovalRoute versioned selector and runtime boundary

**Status:** Proposed — planning decision only; not implementation authority.
**Date:** 2026-07-24
**Owner:** PAR-APR-002 programme
**Affected Charter sections:** Repository evidence and release control
**Related ADRs:** ADR-0013 (Approval Requirement / Decision split)
**Related PDRs:** PDR-0005 (DPA specialist workflow gate)
**Related programme:** PAR-APR-002
**Evidence:** `docs/audits/evidence/2026-07-22-par-apr-002/APPROVAL_ROUTE_RECONCILIATION_INVENTORY.md`

## Problem and context

`ApprovalRoute` is currently template configuration.  Runtime legacy approval
requests are selected from `ApprovalRule`; canonical `ApprovalRequirement`
records mirror those legacy requests.  There is no route identifier on either
runtime object, no tenant-owned route key, and no workflow/template-version or
document-version route snapshot.  The completed evidence inventory found zero
direct route-to-request or route-to-requirement links, one fixture missing
mapping, two duplicate-order rows, one ambiguous category, and no explicit
stale-route control.

`ApprovalRequest` remains the authoritative read model.  This PDR neither
changes that authority nor introduces a route-to-requirement mapping.

## Proposed decision

Adopt **ApprovalRoute as a versioned selector for a separate runtime approval
service** as the target model.  A separately authorised implementation would
allow that service, not a configuration save hook or route model, to resolve a
route and create the applicable runtime approval requirement.  Until a
separately authorised cutover, the existing legacy request remains the
authoritative runtime record and canonical requirements remain its governed
mirror.

This PDR creates no model, field, migration, mapping, feature flag, route,
permission, dual-write change, read-authority change, repair operation, or
runtime behaviour.

## Canonical objects and ownership

| Object / concern | Proposed owner | Rule |
|---|---|---|
| Route definition and ordering | Workflow Configuration | A route is immutable configuration belonging to one immutable workflow-template version. It selects an approval policy; it does not itself create approval state. |
| Requirement and decision | Approval | The runtime approval service creates and governs requirements and immutable decisions. Route configuration cannot mutate or decide them directly. |
| Workflow launch and version snapshot | Workflow Runtime | A launch supplies the immutable workflow-template version and records the resolved route snapshot. |
| Contract and document version | Contract Records and Documents | Supply the same-tenant contract and immutable document evidence required for a requirement; a route cannot manufacture or omit that evidence. |

### Immutable route identity and version binding

A future implementation must give every route an opaque, immutable route ID
and bind it to one immutable workflow-template version ID.  The durable source
tuple for an approval requirement must contain, at minimum, organization ID,
workflow-instance ID, workflow-template version ID, route ID, contract ID,
document-version ID (or an explicit governed missing-version marker), and the
approved authority-basis or actor context.  It must not be inferred from a
route name, sort order, contract, actor, status, or time.

Changing route configuration must create a new workflow-template version and
new route identities; it must not edit a route used by a launched workflow.
An active workflow retains its recorded version and resolved-route snapshot.

## Runtime requirement creation

Only the future runtime approval service may resolve a route.  It must:

1. receive an explicit workflow launch and immutable workflow-template version;
2. verify that the workflow, contract, document evidence, route, and actor
   context are in the same organization and that the actor may launch the
   workflow;
3. evaluate the route condition against the bound launch snapshot;
4. validate that one unambiguous, active route applies;
5. deduplicate by the durable source tuple before creating a requirement; and
6. record the resolved route/version and creation outcome in audit evidence.

It must not create a requirement from a configuration edit, a list or detail
view, a background scan, a guessed correlation, or a cross-tenant lookup.
This is future behaviour only; no service is introduced by this PDR.

## Invalidation, replacement, and invalid configuration

- A new route configuration is a new workflow-template version.  It applies to
  future launches only unless a separately approved transition policy handles
  existing workflows.
- A material contract or document-version change must follow the separate
  approval invalidation policy from ADR-0013.  A route must not silently
  recreate, satisfy, or remap an existing requirement.
- Duplicate route IDs or precedence, ambiguous matching routes, an inactive or
  stale template version, an absent document-version binding, or a failed
  authorization check must block creation, leave legacy authority unchanged,
  and produce an auditable failure.  There is no deterministic "first route
  wins" or fail-open rule.
- Replacing a route cannot rewrite historical snapshots, approval evidence, or
  audit history.  A future rollback disables use of the new service and
  restores the pre-existing legacy selection/read path; it does not mutate
  historical rows.

## Tenant, actor, and document-version constraints

- The workflow, route configuration, contract, document version, requirement,
  decision, and audit event must have the same organization.  Route lookup,
  evaluation, inbox projection, API serialization, exports, counts, and
  operational queues must not reveal foreign identifiers or existence.
- Workflow-launch authority, route-configuration authority, and approval
  decision authority are separate permission checks.  A route selection never
  grants an actor approval, administrator, or configuration-edit permission.
- The bound document version is required unless an accepted future decision
  defines an explicit missing-version state and its stop condition.  A changed
  version cannot silently reuse a prior route result or requirement.

## Lifecycle, inbox, API, and operations effects

No surface changes are authorised by this PDR.  A later implementation must
preserve the following boundary:

| Surface | Required future behaviour |
|---|---|
| Lifecycle | Treat the resolved route as configuration evidence, not an approval decision. Keep legacy lifecycle reads authoritative until separately approved cutover parity. |
| Inbox | Project only authorized requirement work; do not duplicate rows or expose route configuration across tenants. |
| API and routes | Keep configuration and runtime resources distinct, version-aware, and tenant-scoped. Do not add implicit route-to-requirement API links. |
| Operations | Record resolution, duplicate/ambiguity, stale-version, denied, fallback, and rollback counters without sensitive document content. |

## Migration, rollback, and acceptance evidence

No migration is authorised.  If a later, separately approved implementation
needs persistence, it must be additive, nullable where appropriate, and
preserve the legacy route and `ApprovalRequest` paths.  It must not infer or
repair historical links.  Rollback must disable use of the new runtime
service, retain the immutable configuration and audit snapshots, and restore
legacy reads before any removal is considered.

Required evidence before implementation includes:

- an accepted decision and separate implementation authorization;
- immutable reviewed and merged SHAs, required GitHub review, and green CI;
- tests for route identity/version binding, one valid resolution, no matching
  route, duplicate, ambiguous, stale, changed document version, retry,
  rollback, tenant isolation, and permission denial;
- parity and mismatch counts across lifecycle, inbox, API, and operations;
- a demonstrated legacy fallback/restore procedure; and
- an operator or release record for any authority-affecting use.

## Alternatives considered

### Routes create canonical requirements directly

Rejected.  Configuration persistence would become a runtime write path, while
the evidence shows no stable route identity, version snapshot, source tuple,
or authorization boundary today.  It would blur Workflow Configuration and
Approval ownership and risks duplicate or cross-tenant requirement creation.

### Replace routes now with workflow-version approval configuration

Rejected for this scope.  It would be a broader workflow-domain redesign that
requires its own accepted workflow-version decision, transition policy, and
implementation authorization.  The current evidence does not establish that
replacement is necessary to make the bounded runtime-service boundary safe.

### Keep the current implicit route/rule split indefinitely

Rejected as a target model.  It has no governed route-to-runtime correlation
and leaves duplicate, ambiguous, and stale cases without an explicit control.

## Unresolved decisions

1. The authoritative workflow-template version aggregate and its compatibility
   with the future ADR-0012 workflow-definition work.
2. The exact route condition vocabulary and whether route precedence can be
   represented without new lifecycle or configuration terminology.
3. The approved transition policy for already-launched workflows when a later
   configuration version replaces a route.
4. The governed missing-document-version state, if any, and its stop
   condition.
5. The API and inbox projection shapes after a separately authorised runtime
   service exists.
6. The exact parity threshold and observation window required before any
   canonical read-cutover proposal.

## Baseline defect record

`tests.test_workflow_operations` has six existing setup errors.  Each is
caused by the fixture's invalid `ACTIVE` contract status with
`INTERNAL_REVIEW` lifecycle stage under the current validator.  PR #105 and
this planning-only PDR do not touch that fixture, model, lifecycle validator,
route code, or runtime approval service.  The errors are recorded as unrelated
baseline defects and are not evidence for or against the proposed model.

## Approval

This is a Proposed planning decision.  Its status may change only through the
applicable GitHub PR review and CI evidence on the immutable reviewed SHA.
Acceptance would not authorize implementation, migration, authority change,
dual-write, read cutover, repair, permission change, or legacy retirement.
