# Active Todo

Last updated: 2026-06-01

Canonical remaining worklist:
- [`docs/COMPLETE_REMAINING_WORKLIST.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/COMPLETE_REMAINING_WORKLIST.md)
- [`docs/SPRINT3_BOARD_2026-04-18.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/SPRINT3_BOARD_2026-04-18.md)
- [`docs/READINESS_SCOREBOARD_2026-05-31.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/READINESS_SCOREBOARD_2026-05-31.md)

## In Progress

## Completed

- Public API versioning and token scoping
- Clause variant resolver and playbook model
- Workflow escalation timers and delegation UX
- Search relevance and semantic filters
- Operational dashboards and drill automation
- Identity telemetry dashboards and recovery-code handling
- SAML attribute reconciliation and SLO/error telemetry
- SCIM PATCH/query edge cases and IdP reconciliation
- Admin MFA enrollment flow and second-factor verification
- Device/session policy controls and audit/export views
- Redlining and version-compare UI
- Bulk record-operation hardening and audit coverage
- Deterministic workflow routing, approvals, and escalation
- SAML telemetry follow-up: logout error handling and attr mapping hardening
- Clause policy edge cases and fallback playbook reconciliation
- `TKT-003` Manual smoke checklist for two-org validation
- `TKT-004` Centralize scoped form/query helpers
- Document versioning + immutable history (`ContractVersion`, `ContractVersionService`, diff API)
- AI clause drafting with citations (`ClauseRecommendation`, `AIClauseDraftingService`)
- Enterprise admin console (`OrgPolicy`, `AdminConsoleService`, settings/policy/integrations/audit API)
- Permission transparency (`PermissionTransparencyService`, matrix + access APIs)
- Self-serve onboarding (`OnboardingProgress`, `OnboardingService`, advance/complete API)
- Billing + subscription controls (`BillingPlan`, `UsageRecord`, `BillingService`, usage/plan API)
- Compliance portal (`CompliancePortalService`, trust-report + export-bundle API)
- `TKT-005` Structured request logging and correlation IDs
- `TKT-006` Overdue work and deadline health reporting
- `TKT-007` Formalize production env contract
- `TKT-008` Export/download permission tests
- `TKT-009` Split `contracts/views.py` by domain
- `TKT-010` Add staging rollback and migration drill evidence
- Salesforce Sprint 1 foundation (OAuth, mapping, control evidence)
- Salesforce Sprint 2 ingestion and reconciliation (API/CLI)
- Salesforce sync run tracking + sync history API
- Scheduled Salesforce sync with overlap lock protection
- Background retry/dead-letter handling for sync jobs
- Webhook queue/dispatch retries + dead-letter diagnostics
- Sprint 3 integration evidence command (`generate_sprint3_integration_report`)
- E-sign integration evidence command (`generate_esign_integration_report`)
- NetSuite authenticated sync command baseline (`sync_netsuite_contracts`)
- E-sign webhook reconciliation command baseline (`reconcile_esign_events`)
- E-sign provider webhook callback endpoint baseline (`/contracts/api/integrations/esign/webhook/`)
- Retention job runner with immutable retention audit traces (`run_retention_jobs`)
- Retention scheduled execution workflow + evidence artifact export (`retention-jobs-scheduler.yml`)
- Contract lifecycle scheduled execution workflow + evidence artifact export (`contract-lifecycle-jobs-scheduler.yml`)
- Tamper-evident compliance evidence bundle export/verify commands
- AI governance final archive generation and SHA256 verification
- Tenant-scoped positive-path evidence run with non-zero retention + lifecycle outcomes (`run 26708926283`)
- Executive analytics and saved dashboard preset APIs
- Reports dashboard executive analytics panel integration
- Multi-org executive analytics evidence snapshot command
- `SPR3-001` Release gate evidence run (2026-06-01): release-gate-report GO, sprint3-integration-report GO, esign-integration-report GO, release-bundle GO — artifacts in `evidence/spr3-cutover-20260601/`
- `SPR3-002` Salesforce + webhook E2E evidence run (2026-06-01): Salesforce sync SUCCESS created_count=1, webhook SENT confirmed — `evidence/spr3-cutover-20260601/sprint3-integration-report.json` status=GO
- `SPR3-003` Postgres cutover simulation evidence run (2026-06-01): `--simulation` flag + 5 passing tests; rehearsal artifact in `evidence/spr3-003-postgres-cutover/postgres-cutover-simulation.json` (simulation=true, migrations clean)
- `SPR3-005` e-sign rehearsal evidence run (2026-06-01): full PENDING→SIGNED lifecycle + dedup; report in `evidence/spr3-005-esign-rehearsal/esign-integration-report.json` status=GO
- AI clause-span citations + confidence thresholds + PDF/DOCX upload pipeline (`AIExtractionSpan` model, `/api/documents/upload/`, `/api/contracts/<id>/ai-extract/`, commit `ee655e1`)
- Obligation tracker: RENEWAL/PAYMENT/NDA_EXPIRY/SLA types, renewal playbook, reminder cadence, obligation CRUD API, management commands (`generate_renewal_tasks`, `run_obligation_reminders`, commit `31378da`)
- DSAR SLA countdown + evidence bundle export: `DSARService`, `export_dsar_evidence` command, DSAR CRUD + evidence API, commit `75166a5`
- Async job system: `run_worker` daemon, `review_dead_letter_jobs`, `queue_background_jobs` extended, job status API, GitHub Actions cron scheduler (every 15 min), commit `a945238`
- Document versioning + immutable history: `ContractVersion` model, `ContractVersionService` (diff via difflib), versions + diff API, commit `518194b`
- AI-assisted clause drafting: `ClauseRecommendation` model, `AIClauseDraftingService` (template library NDA/MSA/EMPLOYMENT/VENDOR), suggest/accept/draft-section API, commit `518194b`
- Enterprise admin console: `OrgPolicy` model, `AdminConsoleService` (settings, policy, integrations, audit), admin API, commit `518194b`
- Postgres cutover verification command + scheduled CI workflow
- Optional observability HTTP sink transport
- NetSuite ingestion adapter/command baseline
- Runtime vulnerability hardening (`cryptography==46.0.7`, pip-audit clean)
- Release gate security checks fail-closed (`pip-audit` + `npm` required)
- Semantic clause search mode with tenant-safe ACL scoping (`search_mode=semantic|hybrid|keyword`)
- AI prompt-injection controls + output policy on contract assistant endpoint
- Agentic AI actions with approval gates + rollback trace logs on contract assistant endpoint
- Sprint 3 go-live evidence orchestration workflow (`sprint3-go-live-evidence.yml`)
- Sprint 1 + Sprint 2 closeout verification bundle (`docs/SPRINT_1_2_COMPLETION_2026-04-18.md`)

## Next Up

1. **Permission transparency UI** — record-level access visibility for org members
2. **Self-serve onboarding + guided setup** — org creation wizard, first-contract flow
3. **Billing and subscription controls** — usage tracking, plan enforcement
4. **Customer-facing trust/compliance portal** — exportable compliance artifacts

## Source Of Truth

- Broader remaining worklist: `docs/COMPLETE_REMAINING_WORKLIST.md`
- Parity tracker: `docs/MASTER_TODO_CMS_AEGIS_PARITY.md`
