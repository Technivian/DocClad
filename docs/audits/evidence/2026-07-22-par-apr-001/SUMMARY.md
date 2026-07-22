# PAR-APR-001 evidence summary — 2026-07-22

## Status: Closed

**Closure:** Canonical foundation delivered; ADR-0013 **Accepted** 2026-07-22T09:45:00Z. Cutover residuals → PAR-APR-002.

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
- `0111_approval_requirement_decision` — truthful backfill; rollback/re-forward proven (renumbered after Tranche-1 `0110_flagship_workflow_template_assignees`)

### Audit
- `approval.requirement.created`, `approval.decision.recorded`, `approval.requirement.invalidated`
- Legacy `approval.approved/rejected/returned` retained

### Tests
- `tests/test_par_apr_001_approval.py` — **10 OK**
- `tests/test_approval_workflow.py` — **15 OK**
- `tests/test_approval_authorization.py` — **8 OK**

### Accepted ADR
- **ADR-0013** — canonical split + residuals documented

### Residual (PAR-APR-002)
- `DPAReviewPack` parallel approval model not merged
- `ApprovalRoute` template config not runtime requirements
- `ABSTAIN` outcome defined; no UI action yet
- Legacy `CHANGES_REQUESTED` char retained (maps to `RETURNED` decision)

### Next programme item
**PAR-ID-001** (Role Definition reconciliation) — **In progress**
