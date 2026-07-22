# PAR-APR-001 evidence summary — 2026-07-22

## Status: Closed

> **Closed — canonical foundation delivered and governance accepted; cutover residuals transferred to PAR-APR-002.**

### Canonical split (delivered)
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
- See [`TEST_RESULTS.md`](TEST_RESULTS.md) for programme residuals

### ADR
- **ADR-0013 Accepted** (2026-07-22) — see [`GOVERNANCE_REVIEW.md`](GOVERNANCE_REVIEW.md)

### Residual → PAR-APR-002
- `DPAReviewPack` parallel approval model not merged
- `ApprovalRoute` template config not runtime requirements
- `ABSTAIN` outcome defined; no UI action yet
- Legacy read-path retirement and dual-write sunset

### Successor
**PAR-APR-002** — Planned; blocked pending owner assignment, cutover plan, and implementation authorization.
