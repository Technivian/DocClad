# Sprint 3 Status Update

Date: 2026-06-01

## What Changed

- Wired identity settings to expose the live SCIM and approval-routing endpoints in the UI.
- Surfaced approval rules and approval requests from the workflow dashboard and workflow detail views.
- Kept the signature request detail regression aligned with the expected `Quick Actions` heading.
- Added regression coverage for identity endpoint wiring and workflow routing visibility.

## Verified

- Focused tests passed:
  - `tests.test_identity_settings_and_scim`
  - `tests.test_workflow_routing`
  - `tests.test_mfa_policy`
  - `tests.test_workflow_execution`
  - `tests.test_workflow_transition_guardrails`
- Live browser smoke passed against the local app:
  - SAML selector listed a SAML-enabled org.
  - Identity settings showed SCIM users/groups plus approval-rules and approval-requests links.
  - MFA profile page showed the MFA-required banner and recovery-code generation flow.
  - Organization security page showed the MFA policy controls.
  - Workflow dashboard showed approval-rules and approval-requests actions.
- Evidence artifacts now report:
  - `evidence/release-gate-report.json`: `GO`
  - `evidence/sprint3-integration-report.json`: `GO`
  - `evidence/esign-integration-report.json`: `GO`
  - `evidence/release-bundle/release-evidence-bundle.json`: `GO`
- NetSuite authenticated adapter ran successfully against a local mock service:
  - `evidence/netsuite-sync-live.json`
  - created/updated a contract record via `sync_netsuite_contracts`

## Notes

- Local dev server reported unapplied `contracts` migrations in the shared SQLite database, but the live smoke completed successfully.
- The browser smoke used a dedicated local `smoke-owner` org/user pair plus the seeded `admin` account for workflow navigation.
- `evidence/postgres-cutover-evidence.json` remains a simulation artifact and therefore reports `cutover_ready: false` in this SQLite environment.
