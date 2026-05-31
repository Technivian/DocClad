# CMS Aegis Canonical Readiness Scoreboard

Date: 2026-05-31
Owner: Release lead
Purpose: Single source of truth for current readiness and exact path to 100%.

## Definitions

- Launch 100%: Production cutover is complete and post-deploy verification is green.
- North-star 100%: Launch 100% plus all strategic maturity workstreams are complete or formally scheduled with accepted ownership and dates.

## Current State (Canonical)

### Launch Readiness

Source: docs/GO_LIVE_REMAINING_HIGH_PRIO.md

| Item | Status |
|---|---|
| Release gate evidence | Done in tenant-scoped CI evidence run |
| Salesforce sync evidence | Done in rehearsal (live-sync path gated by secrets) |
| Webhook delivery evidence | Done in rehearsal |
| E-sign evidence | Done in rehearsal |
| Staging smoke | Done in rehearsal |
| Backup artifact | Done in rehearsal |
| Restore rehearsal | Done in rehearsal |
| Postgres cutover verification | Done in rehearsal |
| Retention scheduler evidence | Done with non-zero archive actions |
| Contract lifecycle scheduler evidence | Done with non-zero renewal promotion |
| Production deploy | Pending |
| Post-deploy smoke | Pending |

Launch score: 10/12 complete, blocked only on live production-window execution.

Latest positive-path evidence run:
- Workflow: sprint3-go-live-evidence
- Run URL: https://github.com/Technivian/CMS-Aegis/actions/runs/26708926283
- Organization slug: demo-firm
- Retention evidence: contracts_archived=1, policies_scanned=1, audit_entries_created=1
- Lifecycle evidence: contracts_promoted_to_renewal=1, contracts_evaluated=2, audit_entries_created=1

### North-Star Readiness

Source: docs/NORTH_STAR_TRACKER.md

P0 still open:
- SPR3 release gates (live target-env artifacts)
- Salesforce and webhook live proof
- Postgres cutover proof in target environment
- Backup/restore/rollback rehearsal in stable target environment
- Live identity proof (SAML/SCIM/MFA with enterprise systems)

P1 and P2 still open include:
- NetSuite and e-sign live proof
- Workflow/signature hardening acceptance
- Placeholder UI removal and shell consolidation
- Release evidence automation maturity
- Observability/alerts ownership and drift control
- Regression expansion, commercial readiness, AI governance upgrades

North-star score: In progress; launch-near but not full maturity complete.

## Exact Path To Launch 100%

1. Execute production deploy during approved change window.
2. Run migration and gate checks on production target.
3. Run live smoke checklist.
4. Reopen traffic only after all checks pass.
5. Re-run final gate checks after traffic restoration.
6. Archive artifacts in release evidence folder and sign off.

Primary runbook:
- docs/PRODUCTION_CUTOVER_OPERATOR_CHECKLIST.md
- docs/PRODUCTION_CUTOVER_RUNBOOK.md
- docs/STRICT_TARGET_GATE_SIMULATION_2026-05-31.md

## Evidence Required For Launch Signoff

Required artifacts from production window:
- release-gate-report.json with GO
- sprint3-integration-report.json with GO on live data
- at least one SENT webhook delivery in cutover window
- esign-integration-report.json with GO on live data
- fresh backup artifact path and timestamp
- live smoke signoff notes
- post-traffic-restore final gate output

Validated non-production artifacts now available:
- tenant-positive-2026-05-31 run bundle with non-zero retention and lifecycle outcomes
- dedicated retention and contract lifecycle scheduler workflow artifacts

## Documentation Drift (Needs Cleanup)

Validated drift found today:
- PROJECT_STATUS.md still reports a moderate PostCSS issue, but go-live docs and current audit status indicate dependency audits are green.
- PROJECT_STATUS.md still references placeholder TODO actions in templates_list.html, but templates_list.html no longer exists.
- obligations_list.html also no longer exists (prototype retired).

Proposed cleanup rule:
- Treat this file as canonical for release status until PROJECT_STATUS.md is reconciled.

## Exit Criteria

Launch 100% is reached when:
- production deploy is complete
- production checks are green (migrate, audit_null_organizations, verify_postgres_cutover, release gate)
- live smoke passes
- traffic is restored and stable
- final verification remains GO

North-star 100% is reached when:
- all P0 items are done
- all live proof dependencies are captured
- recovery drills are documented and repeatable
- remaining P1/P2 workstreams have completed implementations and ownership signoff