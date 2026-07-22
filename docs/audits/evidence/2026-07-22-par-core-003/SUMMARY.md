# PAR-CORE-003 evidence summary — 2026-07-22

## Status: Completed

### Suites
- `provenance-suite.txt` — 19 OK (`tests.test_par_core_003_provenance`)
- `django-tests.txt` — 34 OK (provenance + PAR-CORE-001 ownership)

### New modules
- `contracts/services/contract_provenance.py`

### Schema
- Migration `contracts/migrations/0106_contract_record_provenance.py`
- Additive fields on `Contract`: `origin_kind`, `origin_channel`, `origin_workflow`, `origin_workflow_template`, `origin_workflow_template_version`, `origin_reason`, `provenance_correlation_id`, `provenance_locked_at`
- Indexes: `ctr_org_origin_ix`, `ctr_org_prov_corr_ix`
- No DB CHECK (data not proven safe for NOT NULL / CHECK yet)

### Backfill (truthful)
1. Contracts with a linked `Workflow` → `WORKFLOW` + pinned instance/template/version
2. Rows with `source_system` + `source_system_id` → `INTEGRATION`
3. All other existing rows → `LEGACY_UNKNOWN` (never invent creators/reasons)

### Audit events
- `contract.record.created` (new creates via import helper / admin / pin)
- `contract.record.provenance_assigned`
- `contract.record.provenance_repaired`
- Equivalents retained (no duplicate semantics): `contract_created`, `contract.uploaded`

### Rollback evidence
- `migrate-rollback.txt` — unapply 0106 OK
- `migrate-reforward.txt` — re-apply 0106 OK
- Migration test covers forward / rollback / re-forward classification

### Next roadmap item
**PAR-CORE-002**
