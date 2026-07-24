# PAR-APR-002 — DPA inventory evidence

**Status:** Evidence-only inventory. It does not create a DPA-to-approval
relationship, change a read path, or authorize reconciliation. `ApprovalRequest`
remains authoritative for generic approval reads. `DPAReviewPack.approval_status`
remains a separate, human-controlled privacy-review state.

## Valid linkage finding

There is **no valid persisted DPA-to-generic-approval linkage** in the current
model. A review pack has an organization, contract, reviewer, approver, and
DPA-scoped approval history. A generic approval has its own organization,
contract, assignee, decision actor, and (through its canonical requirement)
document-version evidence. Neither model stores the other's identifier or a
common correlation identifier.

The DPA activation helper may use the latest legacy approval on the contract to
select a reviewer. That is an assignment convenience, not a durable approval
relationship. A shared organization, contract, actor, timing, or matching
terminal label is therefore **not** sufficient evidence of a valid linkage.

## Status-mapping finding

No governed DPA-to-generic status map exists. The inventory deliberately
classifies every DPA status as `UNMAPPABLE_STATUS` until a separately approved
linkage rule exists:

| DPA state | Generic approval state | Inventory conclusion |
|---|---|---|
| `DRAFT` | No equivalent (`PENDING` is not a draft) | Unmappable |
| `UNDER_REVIEW` | `PENDING` is not a proven equivalent | Unmappable |
| `ESCALATED` | `ESCALATED` has a similar label but no linkage or shared semantics | Unmappable |
| `APPROVED` | `APPROVED` is a similar terminal label only | Unmappable |
| `REJECTED` | `REJECTED` is a similar terminal label only | Unmappable |

This is a deterministic evidence classification, not a decision mapping. It
avoids silently losing specialist DPA risk, Security, reviewer, and audit
semantics.

## Contract, actor, and version consistency

The contract is shared by both domains but cannot establish causation. DPA
state retains `reviewer`, `approved_by`, `approved_at`, and
`DPAApprovalHistoryEntry`; generic approvals retain `assigned_to`,
`decided_by`, `decided_at`, and canonical requirement/decision history.

`DPAReviewPack` has no document-version binding. Generic canonical decisions
do. Consequently, actor, time, and document-version consistency cannot be
claimed for any DPA/generic pair at this stage. They remain evidence fields for
a future separately authorized reconciliation proposal.

## Fixture-bound mismatch counts

No deployed or customer data was read by this evidence slice. The focused test
fixture creates one DPA pack and one generic approval for the same organization
and contract specifically to prove that proximity is not a valid linkage.

| Category | Count | Meaning |
|---|---:|---|
| Valid links | 0 | No persisted relationship exists. |
| `DPA_ONLY` | 1 | The DPA pack remains unlinked. |
| `GENERIC_ONLY` | 1 | The generic approval remains unlinked. |
| `UNMAPPABLE_STATUS` | 1 | The unlinked DPA state is not compared to a generic state. |
| `STATUS_DIVERGENCE` | 0 | No valid pair exists to compare. |
| `ACTOR_OR_TIME_DIVERGENCE` | 0 | No valid pair exists to compare. |
| `CONTRACT_OR_VERSION_DIVERGENCE` | 0 | No valid pair exists to compare. |
| `TENANT_OR_AUTHORIZATION_VIOLATION` | 0 | The org-scoped inventory excludes a second-tenant fixture. |
| `DUPLICATE_OR_AMBIGUOUS_LINKAGE` | 0 | No linkage inference is attempted. |

These fixture counts are test evidence, not a production inventory or a claim
about deployed data.

## Dependency evidence

| Dependency | Verified current boundary |
|---|---|
| Route/UI | DPA status changes use the DPA-specific status route; generic inbox/actions use `ApprovalRequest`. |
| Lifecycle | Signature and activation gates still read legacy approval status; DPA status is not substituted. |
| Inbox | My Work keeps DPA privacy rows and generic approval rows as separate projections. |
| API | Generic approval APIs query `ApprovalRequest`; no DPA-to-generic API mapping exists. |
| Operations | DPA activation can select a reviewer from the latest legacy approval, while reminders, Command Center, queues, and monitoring retain legacy approval dependencies. |

## Test and stop boundary

`tests.test_par_apr_002_dpa_inventory` proves the no-linkage boundary,
fixture counts, status non-equivalence, non-mutation of DPA state by generic
approval activity, and organization-scoped inventory. Existing DPA
cross-tenant and permission tests remain required evidence.

Local verification for this evidence slice:

- `tests.test_par_apr_002_dpa_inventory`: **5/5 passed**;
- `tests.test_dpa_review.DPACrossTenantIsolationTests`: **4/4 passed**;
- `tests.test_permission_matrix`: **2/2 passed**;
- `tests.test_par_apr_002_cutover_baseline`: **3/3 passed**;
- `manage.py check`: passed; and
- `manage.py audit_null_organizations`: no NULL organization rows found
  (after applying the existing migrations to this disposable local database).

Stop any future reconciliation proposal on tenant or authorization failure,
ambiguous linkage, non-deterministic comparison, any unexpected write, or any
attempt to make either model authoritative without its separately required
authorization. The rollback for this evidence-only change is a normal commit
revert.
