# PAR-APR-002 — DPA and generic approval relationship decision

**Status:** Planning recommendation only. This record does not amend
ADR-0013, create a domain object, authorize implementation, or change read or
write authority. `ApprovalRequest` remains authoritative for generic approval
reads; `DPAReviewPack.approval_status` remains a separate, human-controlled
privacy-review state.

## Recommendation

**Defer a DPA-to-generic-approval relationship pending a broader
approval-domain redesign.**

The relationship should **not** be introduced in PAR-APR-002 as a local
mapping or inferred from existing rows. Accepted architecture assigns Privacy
Review its own specialist model while requiring deliberate integration with the
Approval domain. ADR-0013 also explicitly leaves `DPAReviewPack.approval_status`
separate. The completed inventory found zero persisted links and no governed
status map.

Keeping the domains permanently separate is not recommended as a final
architecture decision: it would leave unresolved how a future workflow
expresses a privacy-review gate alongside a generic approval requirement.
Introducing a relationship now is also not recommended: it would add a new
cross-domain contract without a stable correlation, DPA document-version
binding, or approved semantics. A broader approval-domain decision must first
determine whether specialist reviews are approval requirements, workflow gates,
or referenced evidence.

## Findings supporting the recommendation

- A DPA pack and a legacy or canonical generic approval share no persisted
  identifier. Contract, organization, reviewer, timing, and terminal labels
  are not a safe substitute.
- DPA states include specialist lifecycle and risk/Security semantics; generic
  approval states and canonical decision outcomes cannot preserve them through
  a status-only conversion.
- DPA approval history is DPA-scoped and human-controlled. Generic decisions
  require a requirement, authority basis, evaluated state, and document-version
  evidence.
- DPA activation currently uses a legacy approval only to select a reviewer.
  That convenience does not establish a business relationship.

## Required design contract before any relationship can exist

The following are constraints for a future approved design, not an
implementation specification.

| Topic | Required decision / rule |
|---|---|
| Relationship | Decide explicitly whether a DPA review is (a) a specialist workflow gate that references generic approval evidence, (b) a generic approval requirement with specialist privacy evidence, or (c) a wholly independent gate. Do not merge the models by label. |
| Stable key | Persist an explicit, immutable association between the DPA pack's opaque identifier and the selected generic `ApprovalRequirement` identifier. A composite of contract, organization, actor, time, or status is prohibited as a key. The exact field or association aggregate needs an ADR/PDR before schema work. |
| Creation | Create the association only through an approved application service at an explicit workflow/privacy-gate event. It must be idempotent, tenant-scoped, auditable, and must not backfill or infer existing records. |
| Ownership | Privacy Review owns DPA lifecycle, risk controls, and DPA history. Approval owns requirement/decision validity. A future application service or governed event coordinates them; neither domain directly treats the other's table as its source of truth. |
| Status semantics | Preserve DPA `DRAFT`, `UNDER_REVIEW`, and `ESCALATED` as specialist states. Do not auto-create `ApprovalDecision` rows from DPA `APPROVED` or `REJECTED`. Any gate-satisfaction relationship must define one explicit transition table, including reset, return, revoke, abstain, and risk-blocker semantics. |
| Document version | A future DPA gate must identify the DPA document version or explicitly record why none exists. A generic decision must retain its own contract-state/document-version binding. A link is invalid if it lets DPA approval bypass either binding. |
| Tenant and permissions | Both linked objects must belong to the same organization. Server-side authorization must independently verify the DPA reviewer/administrator action and generic approval authority; the relationship grants no permission. Cross-tenant lookup, counts, queues, APIs, and audit summaries must deny or omit the other tenant. |
| Audit | Association creation, change, decision/gate evaluation, invalidation, and denial must be append-only audit events with actor, organization, source, correlation, and before/after values. |

## Effects that remain deferred

No route, lifecycle, inbox, API, or operations behavior changes under this
record. A future approved design must assess, separately and in order:

1. workflow route configuration and its relationship to a privacy-review gate;
2. lifecycle signature/activation gates, which still use legacy approval reads;
3. My Work and privacy/approval inbox projections, which must not duplicate or
   leak work across tenants;
4. generic and DPA APIs, exports, Command Center, reminders, monitoring, and
   operations jobs; and
5. audit, cross-tenant, permission-denial, and negative-path behaviour.

## Parity and acceptance evidence for a future proposal

A future relationship proposal must provide, before any authority change:

- an accepted ADR/PDR resolving the relationship choice and stable key;
- an immutable source SHA, green CI, and a complete ownership matrix for every
  changed read/write/projection surface;
- deterministic fixture coverage for each valid link, absent link, duplicate,
  cross-tenant attempt, unauthorized actor, status transition, document-version
  change, invalidation, and rollback path;
- evidence that DPA risk/Security controls and human control remain intact;
- parity counts that distinguish valid links from every mismatch category
  without repairing data; and
- a separate, reversible cutover authorization before generic or canonical
  authority is changed.

## Migration and rollback implications

There is no migration in this slice. If the future decision authorizes a
relationship, it must use an additive, nullable, tenant-scoped association
with no inferred backfill. The migration plan must prove forward, rollback,
and re-forward behavior with counts and audit evidence. Rollback must remove
new association use before any field is removed; it must restore the current
separate DPA and legacy-generic reads without modifying historical DPA status,
generic approval, or decision records.

## Next authorized slice

The only next authorized DPA-related slice is a planning-only ADR/PDR package
for the broader approval-domain redesign. It must choose one of the three
relationship models above and resolve stable-key, lifecycle, version, status,
and authorization semantics. No model, migration, feature flag, mapping,
dual-write, permission, repair, legacy removal, or production action is
authorized until that package is accepted and a separate implementation scope
is approved.
