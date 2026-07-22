# PAR-APR-001 — Approval usage matrix

**Date:** 2026-07-22

| Path / model | Current meaning | Req vs decision | Owner | Doc version | Mutability | Audit | Migration risk | Canonical target |
|---|---|---|---|---|---|---|---|---|
| `ApprovalRequest` | Collapsed requirement + decision | Both | `approval_workflow.py` | **None** (pre-0110) | Mutable status | `approval.*` legacy | H | Legacy mirror via `legacy_request` FK |
| `ApprovalRule` | Rule engine trigger | Requirement source | `workflow_routing.py` | N/A | Config mutable | indirect | M | Authority basis on Requirement |
| `ApprovalRoute` | Template step labels | Config only | `workflow_management.py` | N/A | Draft editable | template events | L | Workflow version config (PAR-WF-010) |
| `initiate_approval_workflow` | Rule match → rows | Creates requirement | service | Bound at create | OPEN until decision | `approval.created` + `approval.requirement.created` | M | `create_approval_requirement` |
| `submit_for_review` | Manual/workflow submit | Creates requirement | service | Bound at create | OPEN | `approval.submitted` | M | `workflow_submit` basis |
| `approve` / `reject` / `request_changes` | Decision actions | Appends decision | service + API + HTML | Bound at decision | Decision immutable | `approval.decision.recorded` + legacy | M | `record_approval_decision` |
| `delegate` / `reassign` | Coverage / ownership | Requirement metadata | service | N/A | Delegation fields | `approval.delegated/reassigned` | L | Requirement delegation fields |
| `documents_ai` ad hoc | Exception/confirm tasks | Requirement via save hook | `documents_ai.py` | Bound if doc exists | OPEN | AI + approval events | M | `ai_ad_hoc` basis |
| `ai_actions.py` | AI-created approval | Requirement via save hook | `ai_actions.py` | If doc present | OPEN | varies | M | same |
| `workflow_management` get_or_create | Workflow step approvals | Requirement via save hook | views | If doc present | OPEN | workflow | M | same |
| `DPAReviewPack` | Separate pack approval | Parallel model | `dpa_review.py` | N/A | Mutable | DPA history | H | **Residual** — not merged |
| Signature gating | Block until approvals done | Checks legacy + canonical OPEN | `contract_lifecycle.py` | N/A | N/A | N/A | M | Open `ApprovalRequirement` check added |
| Document supersession | Material change | Invalidates OPEN reqs | `document_version_service` | New version on revoke | INVALIDATED | `approval.requirement.invalidated` | M | `invalidate_open_requirements_for_contract` |
| Seeds (`seed_demo`, etc.) | Demo rows | Backfilled | management commands | `legacy_unknown` if missing | varies | demo | M | Migration 0110 backfill |
| Admin | Direct CRUD | Save hook ensures requirement | `admin.py` | Backfill binding | Legacy mutable | admin | L | Read prefer canonical |
