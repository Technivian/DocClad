# PAR-APR-001 evidence summary — 2026-07-22

## Status: Completed

### Canonical split
- `ApprovalRequirement` — why/who/authority/state at open
- `ApprovalDecision` — immutable outcome with document version + contract state binding
- `ApprovalRequest` — legacy compatibility mirror (`legacy_request` OneToOne)

### Implementation
- `contracts/services/approval_canonical.py`
- `ApprovalWorkflowService` wired for decisions + delegation sync
- `ApprovalRequest.save` idempotent requirement fallback
- Document supersession invalidates open requirements
- Signature gating checks open canonical requirements

### Migration
- `0110_approval_requirement_decision` — truthful backfill; rollback/re-forward proven

### Audit
- `approval.requirement.created`, `approval.decision.recorded`, `approval.requirement.invalidated`
- Legacy `approval.approved/rejected/returned` retained

### Tests
- `tests/test_par_apr_001_approval.py` — **10 OK**
- `tests/test_approval_workflow.py` — **15 OK**
- `tests/test_approval_authorization.py` — **8 OK**

### Proposed ADR
- **ADR-0013** (not Accepted) — documents split + residuals

### Residual
- `DPAReviewPack` parallel approval model not merged
- `ApprovalRoute` template config not runtime requirements
- `ABSTAIN` outcome defined; no UI action yet
- Legacy `CHANGES_REQUESTED` char retained (maps to `RETURNED` decision)

### Next unblocked roadmap item
**PAR-ID-001** (Role Definition reconciliation) or Milestone 1 hygiene (`PAR-SEC-002`, `PAR-SEC-003`)
