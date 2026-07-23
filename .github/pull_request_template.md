## Summary

- What changed:
- Why:

## Governance and agent context

Before material product, architecture, design, security, workflow, AI, or engineering work, follow root [`AGENTS.md`](../AGENTS.md). The active Governance Charter is [`docs/governance/GOVERNANCE_CHARTER.md`](../docs/governance/GOVERNANCE_CHARTER.md). Accepted supporting docs (PDR-0003) remain subordinate to the active Charter. Proposed Charter v3 does not supersede approved governance until separately approved.

For authorization or release work, use the GitHub review-and-release evidence
model in [`GITHUB_REVIEW_AND_RELEASE_EVIDENCE.md`](../docs/governance/GITHUB_REVIEW_AND_RELEASE_EVIDENCE.md).
The PR, its submitted reviews, CI results, immutable SHAs, and operator or
release record are the evidence; do not add a manual approval table.

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
- Required GitHub review roles and release/operator record (when applicable):
