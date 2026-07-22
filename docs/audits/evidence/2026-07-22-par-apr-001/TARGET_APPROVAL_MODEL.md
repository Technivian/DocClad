# PAR-APR-001 — Target approval model

## ApprovalRequirement

- **Purpose:** Why approval is needed; who must approve; authority basis; evaluated contract/document state at open.
- **Lifecycle:** `OPEN` → `SATISFIED` | `REJECTED` | `RETURNED` | `INVALIDATED` | `CANCELLED`
- **Binding:** `document_version_id` + `document_version_missing`; `contract_status_at_open`; `contract_lifecycle_stage_at_open`
- **Authority:** `authority_basis` (`rule`, `manual`, `workflow_submit`, `ai_ad_hoc`, `legacy_unknown`); `authority_reference` JSON; optional `rule` FK
- **Sequencing:** `sort_order` preserved from legacy chain
- **Delegation:** `assigned_to`, `delegated_to`, `delegation_reason`, `delegation_ends_at` on requirement (mutable while OPEN)

## ApprovalDecision

- **Purpose:** Immutable outcome against a specific requirement episode
- **Outcomes:** `APPROVED`, `REJECTED`, `RETURNED`, `REVOKED`, `ABSTAINED`
- **Attribution:** `decided_by`, `authority_holder_id`, `acting_under_delegation`, `delegation_holder_id`
- **Binding:** contract status + lifecycle stage + `document_version_id` at decision time
- **Immutability:** save + QuerySet.update guards
- **History:** One requirement may have multiple decisions across reopen episodes (new requirement row per resubmit)

## Reset / invalidation

- Material FINAL/EXECUTED document supersession → `invalidate_open_requirements_for_contract`
- Emits `REVOKED` decision + legacy `CHANGES_REQUESTED` sync
- Re-submit creates new OPEN requirement (new episode)

## Permissions

- Existing `authorize_approval_actor` unchanged (tenant 404, assignee/delegate, segregation of duties)
- Decisions only via `ApprovalWorkflowService._decide` → `record_approval_decision`

## Audit events

| Canonical | Legacy (retained) |
|---|---|
| `approval.requirement.created` | `approval.created`, `approval.submitted` |
| `approval.decision.recorded` | `approval.approved`, `approval.rejected`, `approval.returned` |
| `approval.requirement.invalidated` | — |

## Archival

- Decisions never deleted
- Requirements retained for audit; terminal statuses closed with `closed_at`
