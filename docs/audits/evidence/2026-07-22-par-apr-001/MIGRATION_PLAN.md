# PAR-APR-001 — Migration plan

## Migration `0111_approval_requirement_decision`

> **Renumber note:** Originally authored as `0110` on the continuation branch. Renumbered to `0111` after Tranche-1 merge introduced `0110_flagship_workflow_template_assignees` on `main`.

### Additive schema
- `ApprovalRequirement` + `ApprovalDecision` tables
- Indexes on `(contract, status)` and `(organization, status)`
- OneToOne `legacy_request` → `ApprovalRequest`

### Backfill rules
| Legacy `ApprovalRequest` | Requirement | Decision |
|---|---|---|
| `PENDING` / `ESCALATED` | `OPEN` | none |
| `APPROVED` | `SATISFIED` | `APPROVED` at `decided_at` |
| `REJECTED` | `REJECTED` | `REJECTED` |
| `CHANGES_REQUESTED` | `RETURNED` | `RETURNED` |
| Missing org | skipped | — |
| Document version | latest contract doc `DocumentVersion` if exists; else `document_version_missing=True` |
| Authority | `legacy_unknown` | — |

### Compatibility period
- `ApprovalRequest` remains write path mirror for UI/API
- All new decisions append `ApprovalDecision` rows
- `ApprovalRequest.save` idempotently ensures requirement for paths not yet calling `create_approval_requirement` explicitly

### Rollback
- Reverse `0111` deletes canonical rows; `ApprovalRequest` unchanged

### Removal criteria (future — PAR-APR-002)
- All reads use `ApprovalRequirement` / `ApprovalDecision`
- No production code mutates decision fields on `ApprovalRequest`
- Accepted ADR-0013 + ops sign-off + PAR-APR-002 implementation authorization

### Evidence
- `migrate-rollback.txt` (→ 0110)
- `migrate-reforward.txt` (→ 0111)
- `django-tests.txt` (10 OK PAR-APR-001 + regression)
