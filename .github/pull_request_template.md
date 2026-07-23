## Summary

- What changed:
- Why:

## Governance and agent context

Before material product, architecture, design, security, workflow, AI, or engineering work, follow root [`AGENTS.md`](../AGENTS.md). The active Governance Charter is [`docs/governance/GOVERNANCE_CHARTER.md`](../docs/governance/GOVERNANCE_CHARTER.md). Accepted supporting docs (PDR-0003) remain subordinate to the active Charter. Proposed Charter v3 does not supersede approved governance until separately approved.

If this PR requests a governance decision, use the GitHub evidence model in
[`GITHUB_VOTE_EVIDENCE_GUIDANCE.md`](../docs/governance/GITHUB_VOTE_EVIDENCE_GUIDANCE.md).
Votes link to the genuine GitHub comment or review; do not enter a manual UTC
timestamp in the PR or vote template. This guidance becomes binding when
PDR-0004 is accepted.

## Risk and Scope

- Tenant isolation impact: `none | low | medium | high`
- RBAC/permissions impact: `none | low | medium | high`
- Migration impact: `none | backward-compatible | breaking`
- Data/privacy impact: `none | low | medium | high`

## Verification

- [ ] `python manage.py check`
- [ ] `python manage.py test tests.test_cross_tenant_isolation -v 1`
- [ ] `python manage.py test tests.test_permission_matrix -v 1`
- [ ] `python manage.py audit_null_organizations`
- [ ] Manual smoke paths validated (if UI behavior changed)
- [ ] Manual smoke not required (no UI/UX change)

## Release and Rollback

- Deploy steps:
- Rollback steps:
- Feature flag / kill switch (if any):
- [ ] Rollback steps tested on staging or drill link added below

## Evidence

- Screenshots / logs / links:
- Smoke evidence:
- Rollback evidence:
- Governance vote evidence (when applicable):
