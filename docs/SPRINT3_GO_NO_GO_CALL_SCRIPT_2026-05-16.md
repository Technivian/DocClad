# Sprint 3 GO NO-GO Call Script

Date: 2026-05-16
Duration: 15-20 minutes
Participants: TL, QA, SRE, Security, Release Operator

## 1) Meeting Open (2 min)

Facilitator prompt:
- We are making the Sprint 3 release decision based on target-environment evidence only.
- Any failed critical gate is an automatic NO-GO.

Record:
- Environment:
- Commit SHA:
- Start time (UTC):

## 2) Evidence Roll Call (8 min)

Read each line and capture PASS or FAIL.

1. Postgres cutover readiness
- Evidence file: evidence/postgres-cutover-evidence.json
- Required: cutover_ready equals true
- Owner call: SRE
- Status: PASS / FAIL

2. Sprint 3 integration report
- Evidence file: evidence/sprint3-integration-report.json
- Required: status equals GO
- Owner call: BE or SRE
- Status: PASS / FAIL

3. E-sign integration report
- Evidence file: evidence/esign-integration-report.json
- Required: status equals GO
- Owner call: BE
- Status: PASS / FAIL

4. Release gate report
- Evidence file: evidence/release-gate-report.json
- Required: go_no_go equals GO
- Owner call: Security and TL
- Status: PASS / FAIL

5. Executive analytics evidence
- Evidence file: evidence/executive-analytics-evidence.json
- Required: file generated and current run timestamp present
- Owner call: BE or PO
- Status: PASS / FAIL

6. Retention audit evidence
- Evidence file: evidence/retention-audit-actions.json
- Required: file generated and current run timestamp present
- Owner call: Security
- Status: PASS / FAIL

7. Release bundle
- Evidence file: evidence/release-bundle/release-evidence-bundle.json
- Required: go_no_go equals GO
- Owner call: TL
- Status: PASS / FAIL

8. Manual smoke signoff
- Evidence file: evidence/manual-smoke-signoff.md
- Required: all critical smoke checks pass
- Owner call: QA
- Status: PASS / FAIL

9. Rollback drill entry
- Evidence file: docs/DRILL_LOG.md
- Required: backup, restore, timings, and result recorded for this run
- Owner call: SRE
- Status: PASS / FAIL

## 3) Decision Rule (2 min)

Decision logic:
- GO only if every critical gate is PASS.
- Any critical FAIL means NO-GO and immediate remediation ticketing.

Critical gates:
- Postgres cutover readiness
- Release gate report
- Manual smoke signoff
- Rollback drill entry

## 4) Remediation Path (if NO-GO) (3 min)

For each FAIL, capture:
- Owner:
- Root cause summary:
- Fix action:
- ETA:
- Re-run command:

Default re-run sequence:
1. Fix issue
2. Re-run strict evidence pack
3. Re-run failed manual checks
4. Reconvene decision call

## 5) Final Readout Template

Live Evidence Readout
- Environment:
- Commit:
- Postgres Cutover Ready: true/false
- Sprint3 Integration: GO/NO-GO
- E-sign Integration: GO/NO-GO
- Release Gate: GO/NO-GO
- Executive Analytics Evidence: GENERATED/MISSING
- Retention Audit Evidence: GENERATED/MISSING
- Manual Smoke: PASS/FAIL
- Rollback Drill: PASS/FAIL
- Final Decision: GO/NO-GO
- Notes:

## 6) Signoff

- TL:
- QA:
- SRE:
- Security:
- End time (UTC):
