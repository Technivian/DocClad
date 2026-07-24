# PAR-APR-002 — DPA reconciliation planning brief

**Status:** Planning only — no reconciliation implementation is authorized.
**Programme boundary:** `ApprovalRequest` remains the authoritative approval
read model. This brief does not alter a model, migration, route, resolver,
permission, flag, dual-write path, or production behaviour.

## Decision: ownership and current source of truth

`DPAReviewPack.approval_status` is owned by the DPA/privacy-review domain. It
is a human-controlled review-pack lifecycle state, not an instance of the
generic contractual-approval model introduced by ADR-0013. Its transition is
performed only by the permission-gated DPA status endpoint and is recorded in
both `AuditLog` and `DPAApprovalHistoryEntry`.

`ApprovalRequest` remains the authoritative source for generic contractual
approval reads throughout PAR-APR-002. `ApprovalRequirement` and immutable
`ApprovalDecision` are canonical foundation records and evidence, but are not
read authority in this programme phase. There is currently no approved or
implemented one-to-one relationship between a DPA review pack and an
`ApprovalRequirement`; no such relationship is implied by this brief.

The planned reconciliation must therefore begin as an explicit *comparison*
of two distinct domains. It must not overwrite either state, derive a
decision automatically, or make a generic approval record authoritative for a
DPA pack.

## Verified dependency map

| Surface | Current dependency | Planning consequence |
|---|---|---|
| DPA review route and UI | `dpa-reviews/<pk>/approval-status/` changes the pack state; DPA list/detail surfaces display it | Preserve the route and its human-only, permission-gated semantics while collecting evidence. |
| DPA activation | `dpa_activation.ensure_dpa_review_pack()` obtains a reviewer from a legacy `ApprovalRequest` | Linkage and reviewer provenance need explicit analysis; no read or write change is authorized. |
| Contract lifecycle | Lifecycle gates still query legacy approval status alongside canonical requirements | A DPA result cannot be substituted into lifecycle gating in this phase. |
| Approval inbox and API | `privacy_approvals` reads and acts on `ApprovalRequest`; APIs and operations retain legacy dependencies | DPA and generic-inbox records must remain visibly separate until a separately authorized integration plan exists. |
| Workflow and routes | `ApprovalRoute` / workflow routing plans legacy approval requests | Route-template mapping is a separate residual; do not infer DPA mapping from a route configuration. |
| Operations and work queue | assignments, queue rows, Command Center, reminders, monitoring, and seeds contain legacy approval dependencies | Reconciliation evidence must identify each affected projection before any authority change. |

## Parity criteria for a future separately authorized evidence slice

No reconciliation implementation or evidence-test slice is authorized by this
brief. A future separately authorized, read-only inventory and test-fixture
slice would pass only when it can report, per organization and without
exposing review content:

1. every in-scope DPA review pack, its contract, its DPA status, reviewer,
   approver, and available audit-history identifier;
2. any associated legacy approval request and canonical requirement/decision
   through an explicitly documented linkage rule (or an explicit absence of
   linkage);
3. a deterministic, reviewed mapping statement for each compared status. The
   current vocabularies are not assumed equivalent: DPA has `DRAFT`,
   `UNDER_REVIEW`, `ESCALATED`, `APPROVED`, and `REJECTED`; generic approvals
   use legacy `PENDING`, `ESCALATED`, `APPROVED`, `REJECTED`, and
   `CHANGES_REQUESTED`, with canonical outcomes including `RETURNED`,
   `REVOKED`, and `ABSTAINED`;
4. organization, contract, actor, document-version (where applicable), and
   decision-time consistency for every claimed match; and
5. counts for every match and mismatch category, plus cross-tenant and
   permission-denial test results.

No parity result is sufficient to change authority. A future cutover would
also require separately authorized behaviour, rollback, observation, and
release gates.

## Mismatch categories

These are evidence labels only; they do not add database statuses or trigger
repair.

| Category | Meaning | Handling in planning / evidence |
|---|---|---|
| `DPA_ONLY` | A DPA review pack has no documented generic approval linkage. | Count and retain both records unchanged. |
| `GENERIC_ONLY` | A relevant generic approval has no DPA review-pack linkage. | Count; decide whether it is outside the DPA cohort. |
| `UNMAPPABLE_STATUS` | The two state vocabularies have no approved deterministic comparison. | Stop that cohort; no inferred mapping. |
| `STATUS_DIVERGENCE` | A reviewed mapping exists but the compared states differ. | Preserve both values and evidence; no automatic correction. |
| `ACTOR_OR_TIME_DIVERGENCE` | Actor, approval time, delegation, or audit provenance conflicts. | Treat as material evidence gap. |
| `CONTRACT_OR_VERSION_DIVERGENCE` | Contract binding or available document-version context conflicts. | Exclude from parity acceptance pending investigation. |
| `TENANT_OR_AUTHORIZATION_VIOLATION` | Organization scope or permission result is inconsistent. | Critical stop condition; no further reconciliation work. |
| `DUPLICATE_OR_AMBIGUOUS_LINKAGE` | More than one plausible approval record maps to the pack. | Stop the affected cohort pending an explicit linkage decision. |

## Evidence required before a separately authorized reconciliation proposal

- an immutable source SHA and CI result for the evidence-only slice;
- an organization-scoped inventory with identifiers and aggregate counts, not
  DPA content or personal-data payloads;
- documented linkage selection rules and exclusions;
- status-mapping review with unmappable cases retained as such;
- DPA, approval, workflow, inbox, lifecycle, API/operations, cross-tenant,
  and permission-denial characterization results;
- audit-history references for each claimed DPA decision; and
- a written statement that legacy `ApprovalRequest` remained authoritative
  throughout observation.

## Stop conditions and rollback boundary

Stop the proposed evidence slice immediately if it detects a tenant-isolation
or authorization failure, an ambiguous linkage with no approved rule, a
non-deterministic status comparison, an unexpected write to either approval
domain, a legacy-authority change, or a failing required regression test.

This planning artifact has no runtime effect. Its only rollback is a normal
documentation revert. Any later implementation must provide its own
separately authorized rollback plan; it may not rely on this brief as an
authorization to enable a flag, modify data, change permissions, or replace a
legacy read.

## Unresolved questions

1. Which DPA review packs, if any, are intended to participate in a generic
   contractual approval requirement, and what stable linkage proves that
   relationship?
2. Can DPA `ESCALATED` and `UNDER_REVIEW` be compared to a generic approval
   state without losing the specialist DPA risk and Security controls?
3. Should a DPA approval require the same document-version binding as a
   generic `ApprovalDecision`, and how would that be evidenced for existing
   packs?
4. How should DPA `DRAFT` and a generic request that does not yet exist be
   represented in a parity report without treating absence as failure?
5. Which route, lifecycle, inbox, API, and operations consumers need a DPA
   result, versus a generic approval result, before a future cutover plan can
   be assessed?

## Smallest next authorization request

No reconciliation slice is currently authorized. The smallest scope to submit
for separate authorization is an evidence-only, organization-scoped DPA
linkage and status-mapping inventory with mismatch counts and
cross-tenant/permission characterization tests. It must not add a migration,
relationship, flag, resolver change, dual-write change, read-authority change,
permission change, repair, or UI/API behaviour. Further authorization remains
required before any reconciliation implementation, read cutover, or
retirement.
