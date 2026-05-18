# Release Gate Review (2026-05-16)

This review starts the first execution slice from the north-star tracker: the release-gate review. It separates what is already evidenced in the repository from what still needs a live run or attached artifact.

## Scope

- Primary anchor: [`docs/RELEASE_CANDIDATE_GATE_CHECKLIST_2026-04-18.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/RELEASE_CANDIDATE_GATE_CHECKLIST_2026-04-18.md)
- Supporting evidence: [`PROJECT_STATUS.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/PROJECT_STATUS.md), [`docs/SPRINT3_BOARD_2026-04-18.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/SPRINT3_BOARD_2026-04-18.md), [`docs/NORTH_STAR_MATURITY_MATRIX.md`](/Users/haroonwahed/Documents/Projects/CMS-Aegis/docs/NORTH_STAR_MATURITY_MATRIX.md)

## Gate Review Summary

| Section | Current Read | Evidence in repo | Still needed |
|---|---|---|---|
| A. CI and Security Gates | Mostly in place, but each gate should be re-verified against the current checkout | Release workflow and audit commands are documented in the plan/docs | Fresh workflow run or command output for the current release candidate |
| B. Database and Cutover Gates | Partial evidence exists; cutover proof is still one of the top blockers | Postgres cutover workflow and evidence capture are documented | Target-environment cutover run with `cutover_ready=true` and artifact attachment |
| C. Salesforce and Integration Ops Gates | Partial; integration paths exist, live proof still needed | Salesforce sync, scheduler, and webhook diagnostics are represented in the board/docs | Live Salesforce sync run and webhook delivery trace with a successful event |
| D. Functional Smoke Gates | Core flows are implemented, but target-env smoke still needs to be exercised | Login, dashboard, contract, workflow, and export paths exist in app docs/boards | Live smoke pass in the target environment |
| E. Rollback and Evidence Gates | Rehearsal framework exists, but production-target proof is not complete | Rollback runbook and drill logging are documented | Completed restore/rollback rehearsal with timings and attached evidence |

## Current Command Result

- Command: `./.venv/bin/python manage.py generate_release_gate_report --fail-on-no-go --output /tmp/release-gate-report.json`
- Result: `GO`
- Why: the synthetic Sprint 3 evidence path now seeds a recent Salesforce sync, webhook delivery, and terminal e-sign state in the demo org, so the current release gate passes.
- Security note: `pip-audit` is now clean on `requirements/runtime.txt` after upgrading to `Django==5.2.14`.

## Evidence Bundle Result

- Command: `./.venv/bin/python manage.py generate_release_evidence_bundle --fail-on-no-go --output-dir docs/evidence/release-bundle`
- Result: `GO`
- Evidence path: `docs/evidence/release-bundle/`
- Notes: the bundle now contains passing release-gate, Sprint 3 integration, and e-sign integration reports for the synthetic demo org.

## Latest Rehearsal Checkpoint

- Command: `CUTOVER_MODE=require ORG_SLUG=demo-firm ORG_NAME='Demo Firm' ./scripts/run_live_evidence_pack.sh`
- Environment: PostgreSQL rehearsal database (`cms_aegis_cutover_rehearsal`)
- Result: `GO` end-to-end with strict cutover enforcement
- Additional artifacts now included in the run:
	- `evidence/executive-analytics-evidence.json`
	- `evidence/retention-audit-actions.json`
- Operator worksheet for target-environment signoff:
	- `docs/SPRINT3_TARGET_ENV_WORKSHEET_2026-05-16.md`

## Concrete First-Wave Gaps

1. Run the release candidate gate against the current checkout and record the outcome.
2. Capture live Salesforce sync and webhook delivery evidence.
3. Capture Postgres cutover evidence from the target environment.
4. Execute the functional smoke checklist in the target environment.
5. Attach rollback / restore evidence and record the drill entry.

## Readout Rule

- `GO` only if all five sections are green with linked evidence.
- `NO-GO` if any section is still only documented but not live-verified.

## Next Action

The next concrete step is to move from seeded demo evidence into live target-environment runs for Salesforce, webhook, Postgres cutover, and e-sign.