# Evidence Index

## Audit provenance

| Item | Value |
|---|---|
| Repository baseline | `308d63f462be546efef0b1794f1268cf2443cd2f` |
| Branch | `codex/commercial-readiness-audit` |
| Scope | Documentation-only commercial-readiness assessment; no production behaviour changed |
| Authority order | [active Charter](../governance/GOVERNANCE_CHARTER.md) → accepted decision records → accepted supporting documentation → proposed/archive documents |
| Proposed documents excluded as authority | [Charter v3](../governance/GOVERNANCE_CHARTER_V3_PROPOSED.md), [PDR-0004](../governance/decisions/pdr/PDR-0004-github-review-and-release-evidence.md), [ADR-0010](../governance/decisions/adr/0010-workflow-instance-version-pinning-interim.md) |

## Evidence map

| Evidence ID | Supports findings | Repository evidence | Limits |
|---|---|---|---|
| E-01 | CR-01–CR-02 | [docs index](../README.md), [PDR-0003](../governance/decisions/pdr/PDR-0003-documentation-operating-model.md), [domain model](../product/CANONICAL_DOMAIN_MODEL.md) | Governing intent, not proof of implementation or release approval |
| E-02 | CR-03, CR-07 | [NDA service](../../contracts/services/nda_workflow.py#L353), [NDA routes](../../contracts/urls.py#L315), [NDA tests](../../tests/test_nda_workflow.py) | Focused suite has an NDA projection failure |
| E-03 | CR-04, CR-08, CR-17 | [MSA service](../../contracts/services/msa_workflow.py#L97), [MSA factory](../../contracts/services/msa_workflow.py#L490), [MSA tests](../../tests/test_msa_workflow.py) | Does not prove relationship/execution/record end to end |
| E-04 | CR-06, CR-15 | [DPA service](../../contracts/services/dpa_workflow.py#L334), [DPA model](../../contracts/models.py#L3992), [DPA tests](../../tests/test_dpa_workflow.py) | Two DPA assertions fail in focused suite |
| E-05 | CR-09–CR-10 | [document model](../../contracts/models.py#L1288), [version model](../../contracts/models.py#L1522), [version service](../../contracts/services/document_version_service.py#L140), [migration 0018](../../contracts/migrations/0018_document_file_hash_and_immutable_versions.py), [tests](../../tests/test_document_versioning.py) | Local tests cannot prove production storage durability |
| E-06 | CR-12, CR-15 | [approval canonical service](../../contracts/services/approval_canonical.py#L77), [decision model](../../contracts/models.py#L4541), [approval tests](../../tests/test_approval_workflow.py), [ADR-0013](../governance/decisions/adr/0013-approval-requirement-decision-split.md) | Role resolution/interim architecture and reset coverage remain incomplete |
| E-07 | CR-13 | [workflow designer](../../contracts/services/workflow_designer.py), [simulation service](../../contracts/services/workflow_simulation.py#L209), [version tests](../../tests/test_workflow_template_versioning.py), [simulation tests](../../tests/test_workflow_simulation.py) | ADR-0010 is Proposed; current runtime is interim |
| E-08 | CR-14 | [signature model](../../contracts/models.py#L3633), [e-sign service](../../contracts/services/esign.py#L80), [signature tests](../../tests/test_signature_workspace.py), [release workflow](../../.github/workflows/sprint3-go-live-evidence.yml) | No live provider credentials/webhook/reconciliation evidence inspected |
| E-09 | CR-16 | [Contract provenance](../../contracts/models.py#L1056), [service](../../contracts/services/contract_provenance.py), [migration 0106](../../contracts/migrations/0106_contract_record_provenance.py), [tests](../../tests/test_par_core_003_provenance.py) | No golden-path transaction proof across all contract types |
| E-10 | CR-17–CR-19 | [renewal playbook](../../contracts/services/renewal_playbook.py), [search service](../../contracts/services/search_api.py#L29), [obligation tests](../../tests/test_obligation_tracker.py), [search tests](../../tests/test_search_api.py) | Operational delivery/quality coverage is incomplete |
| E-11 | CR-20–CR-22 | [permission functions](../../contracts/permissions.py#L70), [session tests](../../tests/test_session_security.py), [isolation suite](../../tests/test_cross_tenant_isolation.py), [security authority](../architecture/SECURITY_PRIVACY_ACCESS_AND_AUDIT.md) | Does not establish full object-policy or non-leakage coverage |
| E-12 | CR-23–CR-24 | [AuditLog](../../contracts/models.py#L2126), [audit tests](../../tests/test_audit_integrity.py), [export routes](../../contracts/urls.py#L214), [privacy-export test](../../tests/test_identity_telemetry_and_exports.py#L47) | Production PostgreSQL trigger/export-control verification was not available |
| E-13 | CR-25–CR-28 | [backup](../../scripts/db_backup.sh), [restore drill](../../scripts/db_restore_drill.sh), [monitoring rules](../../ops/monitoring/prometheus-alert-rules.yml), [performance tests](../../tests/test_performance_guardrails.py) | Scripts/configuration are not proof of operating performance, RPO/RTO, or on-call response |
| E-14 | CR-29–CR-32 | [onboarding](../../contracts/services/onboarding.py), [onboarding tests](../../tests/test_onboarding.py), [demo seed](../../contracts/management/commands/seed_mvp_demo.py), [pilot checklist](../../PILOT_LAUNCH_CHECKLIST.md) | No commercial package, live customer, or reference evidence available |

## Commands executed

| Command | Exit | Generated result |
|---|---:|---|
| `make PYTHON=/Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python check` | 0 | `System check identified no issues (0 silenced).` |
| `make PYTHON=/Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python test` | 2 | 2,486 tests in 49.857s; 44 failures, 45 errors, 32 skips. Known drift is documented in `AGENTS.md`, but this audit did not attribute every failure to that drift. No claim of green CI is made. |
| `DJANGO_SETTINGS_MODULE=config.settings_test /Users/haroonwahed/Documents/Projects/CLMOne/.venv/bin/python manage.py test tests.test_nda_workflow tests.test_msa_workflow tests.test_dpa_workflow tests.test_approval_workflow tests.test_signature_workspace tests.test_document_versioning tests.test_par_doc_001_document_version tests.test_par_core_003_provenance tests.test_cross_tenant_isolation tests.test_audit_integrity tests.test_workflow_template_versioning tests.test_workflow_simulation tests.test_obligation_tracker tests.test_search_api tests.test_session_security tests.test_identity_telemetry_and_exports tests.test_performance_guardrails -v 1` | 1 | `Ran 351 tests`; 3 failures listed in the Executive Summary. |

## Evidence not available / not inferred

- GitHub submitted-review status, CI status for the audited SHA, and immutable merge evidence.
- Production deployment, operator, backup/restore, incident, support, or customer-reference logs.
- Live e-signature, SSO, SCIM, CRM/ERP, storage, or AI-provider evidence.
- Performance testing at a customer-like volume or concurrent workload.

No manual approval table, copied approval statement, or manually entered approval timestamp has been created by this audit.
