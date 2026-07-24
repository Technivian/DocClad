# PDR-0005: DPA specialist workflow gate (combined ADR/PDR)

**Status:** Proposed — planning only; not binding or implementation authority.
**Date:** 2026-07-24
**Owner:** PAR-APR-002 programme
**Affected Charter sections:** Repository evidence and release control
**Related ADRs:** ADR-0013 (Approval Requirement / Decision split)
**Related programme:** PAR-APR-002
**Evidence:** `docs/audits/evidence/2026-07-22-par-apr-002/`

## Problem and context

`DPAReviewPack.approval_status` is a human-controlled Privacy Review
lifecycle. `ApprovalRequest` remains the authoritative generic approval read
model while PAR-APR-002 is in progress. The completed evidence inventory found
no persisted DPA-to-generic link and no governed status mapping. A common
contract, organization, actor, time, or terminal label is not a safe
correlation.

The product needs a coherent way for a future workflow to wait for a DPA
review without collapsing specialist privacy review into a generic approval.
The architecture also needs a stable boundary that preserves approval
requirement/decision version binding and prevents direct cross-domain table
coupling.

## Proposed decision

Adopt **DPA as a specialist workflow gate** as the target model, subject to
this PDR being accepted and a separate implementation authorization.

The gate is a Privacy Review capability, not a generic approval requirement
and not a fully independent lifecycle with no workflow contract. It may be
referenced by a future workflow instance at an explicit privacy-review step,
but it must never be inferred from a generic approval row. Generic approvals
remain separate workflow steps and continue to use their own requirement and
immutable-decision model.

This proposal introduces no new model, field, status, route, permission,
flag, migration, or runtime behavior.

## Canonical objects and ownership

| Object / concern | Proposed owner | Rule |
|---|---|---|
| `DPAReviewPack` and DPA review history | Privacy Review | Own DPA lifecycle, specialist risk and Security controls, reviewer actions, and DPA evidence. |
| `ApprovalRequirement` / `ApprovalDecision` | Approval | Own generic approval need, authority basis, decision validity, and contract/document-version binding. |
| Future privacy-review gate reference | Workflow Runtime, coordinated through an application service | Reference a DPA pack only at an explicit workflow privacy-review step. It is not a generic requirement or decision. |
| Contract / document version | Contract Records and Documents | Supply immutable contract/document evidence; neither approval domain may silently manufacture it. |

The future stable correlation key must be the workflow instance's opaque ID,
the immutable workflow-version step ID, and the DPA pack's opaque ID, persisted
only by an approved application service. It must not be a composite of contract,
tenant, actor, timestamp, or status. A generic `ApprovalRequirement` may be a
separate peer step in the same workflow; it receives no automatic association
with the DPA gate.

## Lifecycle and status semantics

| DPA state | Proposed workflow-gate interpretation | Generic approval effect |
|---|---|---|
| `DRAFT` | Gate not started / not satisfied | None |
| `UNDER_REVIEW` | Gate active / not satisfied | None |
| `ESCALATED` | Gate blocked pending specialist resolution | None |
| `APPROVED` | Gate satisfied for the bound DPA evidence | Does not create or satisfy a generic approval decision |
| `REJECTED` | Gate rejected; workflow follows its explicit return/block policy | Does not reject a generic approval requirement |

No DPA-to-generic status mapping is proposed. A generic requirement remains
`OPEN`, `SATISFIED`, `REJECTED`, `RETURNED`, `INVALIDATED`, or `CANCELLED`
only through its governed approval service.

### Reset, revoke, and abstain

- A material change to the bound DPA document evidence must invalidate the
  prior gate satisfaction and open a new review cycle; it must not overwrite
  historical DPA approval evidence.
- A future revoke of a satisfied privacy gate must be an explicit,
  permission-gated, audited transition that reopens the workflow gate. It must
  not create a generic `REVOKED` decision.
- DPA review has no `ABSTAIN` outcome in this proposal. A reviewer unable to
  decide must escalate; generic `ABSTAINED` remains confined to the generic
  approval domain until a separate decision changes that vocabulary.

## Document-version binding

A future DPA gate must bind the DPA document version (or record an explicit
governed missing-version condition) when the review cycle is opened. Its
approval is valid only for that evidence. Generic decisions retain their own
contract-state and document-version binding from ADR-0013. A DPA gate cannot
stand in for, reset, or bypass a generic decision's binding.

## Product and operational effects

| Surface | Proposed effect after separate implementation authorization |
|---|---|
| Workflow routes | Configure an explicit Privacy Review gate step; do not materialize it as a generic approval request. |
| Contract lifecycle | Evaluate the privacy gate separately from legacy and generic approval gates; no substitution until an approved cutover plan. |
| My Work and inboxes | Project privacy work and generic approval work as distinct, authorized rows; avoid duplicates and existence leakage. |
| APIs and exports | Keep separate resource semantics and authorization checks; an optional workflow reference must not expose cross-tenant identifiers. |
| Operations | Command Center, reminders, queues, monitoring, and audit projections must represent a privacy gate distinctly from generic approval counts. |

None of these effects is implemented or authorized by this proposal.

## Tenant, permission, and audit constraints

- A future workflow, DPA pack, and bound DPA document version must belong to
  the same organization. All cross-tenant reads, writes, counts, queues,
  exports, notifications, and audit summaries must deny or omit foreign data.
- DPA review actions remain server-side permission checks for the assigned
  reviewer or authorized organization administrator. A privacy-gate reference
  grants no generic approval permission; generic approval authority grants no
  DPA-review permission.
- Creation, state transition, escalation, invalidation, revoke, workflow-gate
  evaluation, and denial events require append-only audit evidence with actor,
  organization, source, object IDs, correlation, and before/after values.

## Migration, rollback, and compatibility

No migration is authorized by this PDR while Proposed. If accepted and later
implemented, the first slice must be additive and nullable, preserve legacy
and DPA reads, use no inferred backfill, and include forward/rollback/re-forward
verification. Rollback must disable use of the new workflow-gate reference
before removing it and leave historical DPA and approval evidence unchanged.

## Alternatives considered

### Generic approval requirement with specialist DPA evidence

Rejected for this proposal. It risks treating DPA `APPROVED` / `REJECTED` as a
generic decision despite distinct Security/risk semantics, no existing stable
link, and no DPA document-version binding. It would also blur which domain
owns the review lifecycle.

### Fully independent DPA lifecycle

Rejected for this proposal. It preserves specialist semantics but leaves no
governed workflow gate contract, making lifecycle, queue, operations, and
audit behaviour inconsistent across workflow-launched DPA reviews.

### Infer a relationship from current rows

Rejected. The completed PAR-APR-002 inventory proved that shared contract,
organization, actor, timing, or label is not a durable relationship key.

## Unresolved decisions

1. How a DPA review not launched by a workflow should obtain an optional
   workflow-gate reference, if one is ever needed.
2. The exact DPA document-version source and governed missing-version policy.
3. The authorized actor and policy for a future DPA gate revoke.
4. Whether a specialized gate needs a separate workflow state or can reuse an
   existing explicit blocked/returned policy without a new status.
5. The route-template and operations migration sequence after a future
   implementation authorization.

## Acceptance evidence required before implementation

- acceptance of this PDR through the applicable GitHub review evidence;
- a separately approved implementation scope and immutable reviewed SHA;
- focused tests for each DPA state, reset, revoke, escalation, absent version,
  generic-approval coexistence, tenant isolation, unauthorized actors, and
  audit events;
- route, lifecycle, inbox, API, operations, and negative-path evidence;
- migration and rollback/re-forward rehearsal if schema is added; and
- green CI. Any canonical-authority or legacy-retirement step remains subject
  to its separate governance gate.

## Approval

Proposed only. Approval must be recorded by the applicable submitted GitHub
reviews and immutable reviewed SHA. This record creates no implementation or
release authority.
