# ADR-0013: Approval Requirement and Approval Decision split

- Status: **Proposed**
- Date: 2026-07-22
- Deciders: Engineering / Product (proposed by PAR-APR-001)
- Related: PAR-APR-001, PAR-DOC-001, CANONICAL_DOMAIN_MODEL §2.23–2.24, PDR-0001

## Context

Accepted domain documentation requires:

- **Approval Requirement** — why approval is needed, who must approve, authority basis, conditions, sequence.
- **Approval Decision** — immutable outcome tied to specific contract state and Document Version.

CLM One previously collapsed both into mutable `ApprovalRequest` rows.

PAR-DOC-001 delivered `DocumentVersion` binding for signatures; approvals lacked version binding (gap G-DOM / traceability row).

## Decision (proposed — not Accepted)

### 1. Canonical entities (implemented additively)

| Entity | Role |
|---|---|
| `ApprovalRequirement` | Open need for approval; binds contract + document version at open |
| `ApprovalDecision` | Immutable outcome (`APPROVED`, `REJECTED`, `RETURNED`, `REVOKED`, `ABSTAINED`) |

`ApprovalRequest` remains as **legacy compatibility mirror** linked via `ApprovalRequirement.legacy_request` OneToOne.

### 2. Governed write path

- **Create requirement:** `create_approval_requirement()` (+ `ApprovalRequest.save` idempotent fallback)
- **Record decision:** `record_approval_decision()` via `ApprovalWorkflowService._decide`
- **Invalidate on material doc change:** `invalidate_open_requirements_for_contract()` from document supersession path

### 3. Binding rules

- Requirement captures `contract_status_at_open`, `contract_lifecycle_stage_at_open`, `document_version_id` (or `document_version_missing=True`)
- Decision captures state + version at decision time
- Material FINAL/EXECUTED document supersession invalidates open requirements (`REVOKED` decision + legacy `CHANGES_REQUESTED`)

### 4. Vocabulary mapping

| Legacy `ApprovalRequest.status` | Canonical decision outcome | Requirement status |
|---|---|---|
| `PENDING` / `ESCALATED` | (none yet) | `OPEN` |
| `APPROVED` | `APPROVED` | `SATISFIED` |
| `REJECTED` | `REJECTED` | `REJECTED` |
| `CHANGES_REQUESTED` | `RETURNED` | `RETURNED` |

`CHANGES_REQUESTED` char value retained on legacy row; canonical uses `RETURNED`.

### 5. Audit events

| Event | When |
|---|---|
| `approval.requirement.created` | New requirement |
| `approval.requirement.invalidated` | Material state/doc change |
| `approval.decision.recorded` | Immutable decision appended |
| Legacy `approval.approved` / `approval.rejected` / `approval.returned` | Retained on `ApprovalRequest` path |

### 6. Explicit non-goals / residuals

- `DPAReviewPack.approval_status` — separate model; not merged in this slice
- `ApprovalRoute` template rows — configuration only; not runtime requirements
- `ABSTAIN` / explicit `REVOKE` UI actions — outcome exists; UI wiring deferred
- Removal of `ApprovalRequest` — deferred until dual-read period completes

## Mandated by accepted documentation (no ADR needed)

- Requirement vs Decision separation (CANONICAL_DOMAIN_MODEL §2.23–2.24)
- Decision references evaluated state/document version (invariant §277)
- Server-side authorization and tenant isolation (SECURITY_PRIVACY_ACCESS_AND_AUDIT)
- Finance threshold single entry (PDR-0001 — unchanged)

## Approval

Proposed only. Acceptance gates removal of legacy `ApprovalRequest` write path.
