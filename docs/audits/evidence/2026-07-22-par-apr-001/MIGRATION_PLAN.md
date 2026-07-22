# PAR-APR-001 — Migration plan

## Migration `0110_approval_requirement_decision`

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
- Reverse `0110` deletes canonical rows; `ApprovalRequest` unchanged

### Removal criteria (future)
- All reads use `ApprovalRequirement` / `ApprovalDecision`
- No production code mutates decision fields on `ApprovalRequest`
- Accepted ADR-0013 + ops sign-off

### Evidence
- `migrate-rollback.txt` (→ 0109)
- `migrate-reforward.txt` (→ 0110)
- `django-tests.txt` (10 OK PAR-APR-001 + regression)
