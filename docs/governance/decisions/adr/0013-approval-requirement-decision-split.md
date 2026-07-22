# ADR-0013: Approval Requirement and Approval Decision split

- Status: **Accepted**
- Date: 2026-07-22
- Effective date: **2026-07-22**
- Deciders: @haroonwahed (Product governance) · @Technivian (Engineering governance)
- Related: PAR-APR-001 (closed — foundation), PAR-APR-002 (Planned), PAR-DOC-001, CANONICAL_DOMAIN_MODEL §2.23–2.24, PDR-0001
- Meeting record: [`0013-governance-acceptance-meeting-record-2026-07-22.md`](0013-governance-acceptance-meeting-record-2026-07-22.md)
- Ratification validation: [`../../../audits/2026-07-22-adr-0013-ratification-validation.md`](../../../audits/2026-07-22-adr-0013-ratification-validation.md)

## Approval metadata

| Field | Value |
|---|---|
| **Submitted for ratification** | 2026-07-22 |
| **Ratified** | 2026-07-22T09:45:00Z |
| **Product governance** | **Approve** — @haroonwahed |
| **Engineering governance** | **Approve** — @Technivian |
| **Security & privacy (advisory)** | **Approve with conditions** — @Technivian (security review capacity) |
| **Authority basis** | `.github/CODEOWNERS` (repository stewards for `/docs/`, `/contracts/`); `GOVERNANCE_CHARTER.md` v2.0; PDR-0003 documentation operating model |
| **Written consent** | Recorded in meeting record §1 — repository steward written consent via governance vote |
| **Acceptance scope** | Canonical foundation (additive schema, governed write path, vocabulary mapping, audit events). **Does not authorize** PAR-APR-002 implementation or legacy cutover. |
| **Evidence** | `docs/audits/evidence/2026-07-22-par-apr-001/` |

## Context

Accepted domain documentation requires:

- **Approval Requirement** — why approval is needed, who must approve, authority basis, conditions, sequence.
- **Approval Decision** — immutable outcome tied to specific contract state and Document Version.

CLM One previously collapsed both into mutable `ApprovalRequest` rows.

PAR-DOC-001 delivered `DocumentVersion` binding for signatures; approvals lacked version binding (gap G-DOM / traceability row).

## Decision

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

### 6. Explicit non-goals / residuals (PAR-APR-002)

- `DPAReviewPack.approval_status` — separate model; not merged in this slice
- `ApprovalRoute` template rows — configuration only; not runtime requirements
- `ABSTAIN` / explicit `REVOKE` UI actions — outcome exists; UI wiring deferred
- Removal of `ApprovalRequest` — deferred until dual-read period completes

## Alternatives considered

1. **Retain collapsed `ApprovalRequest` model** — rejected; violates CANONICAL_DOMAIN_MODEL §2.23–2.24 and breaks version binding.
2. **Status-only split without new entities** — rejected; cannot enforce immutability or version binding on decisions.

## Consequences

- Additive migration `0111_approval_requirement_decision` (renumbered after Tranche-1 `0110_flagship_workflow_template_assignees`).
- Dual-write path active; legacy reads remain valid during transition.
- PAR-APR-002 owns cutover residuals; no legacy removal authorized by this ADR.

## Mandated by accepted documentation (no ADR needed)

- Requirement vs Decision separation (CANONICAL_DOMAIN_MODEL §2.23–2.24)
- Decision references evaluated state/document version (invariant §277)
- Server-side authorization and tenant isolation (SECURITY_PRIVACY_ACCESS_AND_AUDIT)
- Finance threshold single entry (PDR-0001 — unchanged)

## Approval

**Accepted** 2026-07-22T09:45:00Z by @haroonwahed and @Technivian per meeting record. Acceptance gates removal of legacy `ApprovalRequest` write path to **PAR-APR-002** only.
